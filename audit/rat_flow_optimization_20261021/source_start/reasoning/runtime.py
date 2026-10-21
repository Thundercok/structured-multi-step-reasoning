"""Explicit online execution of a supplied fitted policy, without gold labels.

No fitting, model loading or artifact deserialization occurs here. Backend token
counts are generated-token counts, not full inference cost. Callers own backend
timeouts, model/prompt identity and approval of fitted policy provenance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import inspect
from numbers import Integral, Real
import sys
from typing import Any, Callable, Dict, Optional, Tuple
import time

import numpy as np

from .entry_predictor import EntryChoice
from .optimal_stopping import OptimalStoppingPolicy
from .reasoning_env import LADDER, LLMBackend, ReasoningAction, complexity_features


class BackendExecutionError(RuntimeError):
    """Raised when an underlying backend execution fails, preserving attempt accounting."""


@dataclass(frozen=True)
class StrategyObservation:
    strategy: ReasoningAction
    answer: str
    confidence: float
    generated_tokens: int
    underlying_requests: int = 1


@dataclass(frozen=True)
class ExecutionCostLedger:
    """Rigorous accounting distinguishing strategy attempts, underlying requests, and tokens."""
    strategy_invocations: int
    underlying_requests_dispatched: int
    underlying_requests_succeeded: int
    underlying_requests_failed: int
    generated_tokens: int
    prompt_tokens: Optional[int] = None
    full_inference_cost_estimated: bool = False
    status: str = "completed"

    @property
    def all_requests_succeeded(self) -> bool:
        return (
            self.underlying_requests_dispatched > 0
            and self.underlying_requests_failed == 0
            and self.underlying_requests_succeeded == self.underlying_requests_dispatched
        )


def estimate_underlying_requests(strategy: ReasoningAction, backend: Any) -> int:
    """Estimate expected underlying requests for budget pre-checking."""
    if strategy in (ReasoningAction.COT, ReasoningAction.DIRECT, ReasoningAction.PAL):
        return 1
    if strategy == ReasoningAction.SELF_CONSISTENCY:
        return int(getattr(backend, "sc_samples", 5))
    if strategy == ReasoningAction.TOT:
        return int(getattr(backend, "tot_branches", 3)) + 1
    if strategy == ReasoningAction.REACT:
        return int(getattr(backend, "react_max_turns", 4))
    return 1


@dataclass(frozen=True)
class OnlineReasoningResult:
    observations: tuple[StrategyObservation, ...]
    latency_ms: float
    policy_source: str
    status: str = "completed"
    bundle_id: Optional[str] = None
    bundle_review_status: Optional[str] = None
    cost_ledger: Optional[ExecutionCostLedger] = None
    execution_id: Optional[str] = None
    query_generation: Optional[int] = None

    @property
    def generated_tokens(self) -> int:
        return sum(row.generated_tokens for row in self.observations)


class OnlineReasoningController:
    """Opt-in controller; construction does not certify a policy or run a model."""

    def __init__(
        self,
        backend: LLMBackend,
        policy: OptimalStoppingPolicy,
        *,
        bundle: Optional[Any] = None,
        policy_source: Optional[str] = None,
        allow_synthetic_bundle: bool = False,
        max_strategy_invocations: Optional[int] = None,
        max_underlying_requests: Optional[int] = None,
        max_generated_tokens: Optional[int] = None,
    ):
        # Strict backend protocol validation: must not be a QA-only session (e.g. MLXDocumentSession)
        if not hasattr(backend, "embed") or not callable(backend.embed):
            raise TypeError("backend does not implement LLMBackend protocol (missing embed)")
        if not hasattr(backend, "run") or not callable(backend.run):
            raise TypeError("backend does not implement LLMBackend protocol (missing run)")
        if not hasattr(backend, "hidden_size") or not isinstance(backend.hidden_size, int):
            raise TypeError("backend does not implement LLMBackend protocol (missing integer hidden_size)")

        # Validate budget types & non-negative bounds
        for name, val in [
            ("max_strategy_invocations", max_strategy_invocations),
            ("max_underlying_requests", max_underlying_requests),
            ("max_generated_tokens", max_generated_tokens),
        ]:
            if val is not None:
                if isinstance(val, bool) or not isinstance(val, int) or val < 0:
                    raise ValueError(f"{name} must be a non-negative integer")

        self.bundle = bundle
        if bundle is not None:
            from .bundle import validate_policy_bundle
            validate_policy_bundle(bundle, policy, backend, allow_synthetic=allow_synthetic_bundle)
            self.policy_source = (policy_source or bundle.bundle_id).strip()
            self.bundle_id = bundle.bundle_id
            self.bundle_review_status = bundle.review_status
        else:
            if not isinstance(policy_source, str) or not policy_source.strip():
                raise ValueError("An explicit policy provenance label is required")
            self.policy_source = policy_source.strip()
            self.bundle_id = None
            self.bundle_review_status = None

        predictor = policy.entry_predictor
        if predictor is None or len(predictor.perf) != len(EntryChoice) or len(predictor.cost) != len(EntryChoice):
            raise ValueError("A fitted entry predictor is required")
        if len(policy.tau) != len(LADDER) - 1 or not np.isfinite(policy.tau).all():
            raise ValueError("Fitted finite stopping thresholds are required")
        if len(policy.mean_cost) != len(LADDER) or not np.isfinite(policy.mean_cost).all():
            raise ValueError("Fitted stopping cost metadata is required")
        if predictor.lam != policy.lam:
            raise ValueError("Predictor and stopping policy must use the same lambda")

        self.backend = backend
        self.policy = policy
        self.max_strategy_invocations = max_strategy_invocations
        self.max_underlying_requests = max_underlying_requests
        self.max_generated_tokens = max_generated_tokens

    def solve(
        self,
        query: str,
        *,
        execution_id: Optional[str] = None,
        query_generation: Optional[int] = None,
        deadline_monotonic: Optional[float] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
        max_strategy_invocations: Optional[int] = None,
        max_underlying_requests: Optional[int] = None,
        max_generated_tokens: Optional[int] = None,
        on_step: Optional[Callable[[StrategyObservation], None]] = None,
    ) -> OnlineReasoningResult:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("A nonempty query is required")

        started = time.monotonic()

        def _is_timeout() -> bool:
            return deadline_monotonic is not None and time.monotonic() >= deadline_monotonic

        def _is_interrupted() -> bool:
            return is_cancelled is not None and is_cancelled()

        # Check budget overrides with strict distinction between 0 and None
        for name, val in [
            ("max_strategy_invocations", max_strategy_invocations),
            ("max_underlying_requests", max_underlying_requests),
            ("max_generated_tokens", max_generated_tokens),
        ]:
            if val is not None:
                if isinstance(val, bool) or not isinstance(val, int) or val < 0:
                    raise ValueError(f"{name} must be a non-negative integer")

        strat_limit = max_strategy_invocations if max_strategy_invocations is not None else self.max_strategy_invocations
        req_limit = max_underlying_requests if max_underlying_requests is not None else self.max_underlying_requests
        tok_limit = max_generated_tokens if max_generated_tokens is not None else self.max_generated_tokens

        # Zero-quota contract enforcement: if any limit is 0, dispatch nothing
        if (strat_limit is not None and strat_limit == 0) or \
           (req_limit is not None and req_limit == 0) or \
           (tok_limit is not None and tok_limit == 0):
            ledger = ExecutionCostLedger(0, 0, 0, 0, 0, status="budget_exceeded")
            return OnlineReasoningResult(
                observations=(), latency_ms=(time.monotonic() - started) * 1000,
                policy_source=self.policy_source, status="budget_exceeded",
                bundle_id=self.bundle_id, bundle_review_status=self.bundle_review_status,
                cost_ledger=ledger, execution_id=execution_id, query_generation=query_generation,
            )

        # Check pre-execution cancellation/timeout
        if _is_interrupted():
            ledger = ExecutionCostLedger(0, 0, 0, 0, 0, status="cancelled")
            return OnlineReasoningResult(
                observations=(), latency_ms=(time.monotonic() - started) * 1000,
                policy_source=self.policy_source, status="cancelled",
                bundle_id=self.bundle_id, bundle_review_status=self.bundle_review_status,
                cost_ledger=ledger, execution_id=execution_id, query_generation=query_generation,
            )
        if _is_timeout():
            ledger = ExecutionCostLedger(0, 0, 0, 0, 0, status="timeout")
            return OnlineReasoningResult(
                observations=(), latency_ms=(time.monotonic() - started) * 1000,
                policy_source=self.policy_source, status="timeout",
                bundle_id=self.bundle_id, bundle_review_status=self.bundle_review_status,
                cost_ledger=ledger, execution_id=execution_id, query_generation=query_generation,
            )

        embedding = np.asarray(self.backend.embed(query))
        if embedding.shape != (self.backend.hidden_size,) or not np.isfinite(embedding).all():
            raise ValueError("Backend embedding must be a finite hidden-size vector")

        # Feature versioning
        feat_version = 1
        if self.bundle is not None:
            feat_version = getattr(self.bundle, "feature_schema_version", 1)

        choice = self.policy.entry_predictor.choose(embedding, complexity_features(query, version=feat_version))
        if choice == EntryChoice.LADDER:
            strategies = LADDER
        elif choice == EntryChoice.REACT:
            strategies = (ReasoningAction.REACT,)
        elif choice == EntryChoice.PAL:
            strategies = (ReasoningAction.PAL,)
        else:
            raise ValueError("Unsupported predictor choice")

        observations = []
        dispatched_strategies = 0
        dispatched_requests = 0
        successful_requests = 0
        failed_requests = 0
        total_tokens = 0
        final_status = "completed"

        # Inspect backend.run signature for supported keyword arguments
        run_accepts_cancel = False
        run_accepts_deadline = False
        run_accepts_max_tokens = False
        try:
            sig = inspect.signature(self.backend.run)
            params = sig.parameters
            has_varkw = any(p.kind == p.VAR_KEYWORD for p in params.values())
            run_accepts_cancel = ("should_cancel" in params) or has_varkw
            run_accepts_deadline = ("deadline_monotonic" in params) or has_varkw
            run_accepts_max_tokens = ("max_tokens" in params) or has_varkw
        except Exception:
            pass

        # Reject unsupported hard cap before generation for all callers
        if tok_limit is not None and not run_accepts_max_tokens:
            raise NotImplementedError("Backend does not accept max_tokens required for hard token cap")

        for rung, strategy in enumerate(strategies):
            # Check deadline and cancellation before strategy invocation
            if _is_interrupted():
                final_status = "cancelled"
                break
            if _is_timeout():
                final_status = "timeout"
                break

            # Budget check: strategy limit
            if strat_limit is not None and dispatched_strategies >= strat_limit:
                final_status = "budget_exceeded"
                break

            # Budget check: generated tokens limit
            if tok_limit is not None and total_tokens >= tok_limit:
                final_status = "budget_exceeded"
                break

            # Budget check: underlying requests limit (pre-check estimate)
            est_reqs = estimate_underlying_requests(strategy, self.backend)
            if strategy != ReasoningAction.COT:
                est_reqs = max(est_reqs, getattr(self.backend, "sc_samples", 0))
            if req_limit is not None and (dispatched_requests + est_reqs > req_limit):
                final_status = "budget_exceeded"
                break

            dispatched_strategies += 1

            # Prepare backend run kwargs
            kwargs: Dict[str, Any] = {}
            if run_accepts_cancel:
                kwargs["should_cancel"] = is_cancelled
            if run_accepts_deadline:
                kwargs["deadline_monotonic"] = deadline_monotonic
            if run_accepts_max_tokens and tok_limit is not None:
                remaining = max(0, tok_limit - total_tokens)
                # Allocate per-subcall share so SC/ToT multiple generations do not multiply cap
                kwargs["max_tokens"] = max(0, remaining // est_reqs) if est_reqs > 0 else remaining

            try:
                answer, confidence, tokens = self.backend.run(strategy, query, **kwargs)
            except Exception as exc:
                # Capture actual subcalls dispatched up to failure
                trace_after = getattr(self.backend, "last_trace", None)
                gens = trace_after.get("generations", []) if (isinstance(trace_after, dict) and "generations" in trace_after) else []
                rung_tokens = sum(g.get("tokens", g.get("completion_tokens", 0)) for g in gens)

                rung_succeeded = sum(
                    1 for g in gens
                    if g.get("status") in ("success", "completed")
                    or (
                        g.get("status") not in ("failed", "error", "cancelled", "timeout")
                        and g.get("finish_reason") not in ("failed", "error", "cancelled", "timeout")
                    )
                )
                rung_failed = len(gens) - rung_succeeded

                # If no generations recorded or exception indicates failure occurred after dispatch:
                extra_failed = 0
                if len(gens) == 0 or "after dispatch" in str(exc).lower():
                    extra_failed = 1

                rung_failed += extra_failed
                rung_dispatched = len(gens) + extra_failed

                dispatched_requests += rung_dispatched
                successful_requests += rung_succeeded
                failed_requests += rung_failed
                total_tokens += rung_tokens

                if _is_interrupted() or "cancel" in str(exc).lower():
                    stop_status = "cancelled"
                elif _is_timeout() or isinstance(exc, TimeoutError) or "deadline" in str(exc).lower() or "timeout" in str(exc).lower():
                    stop_status = "timeout"
                else:
                    stop_status = "failed"

                partial_ledger = ExecutionCostLedger(
                    strategy_invocations=dispatched_strategies,
                    underlying_requests_dispatched=dispatched_requests,
                    underlying_requests_succeeded=successful_requests,
                    underlying_requests_failed=failed_requests,
                    generated_tokens=total_tokens,
                    prompt_tokens=None,
                    full_inference_cost_estimated=False,
                    status=stop_status,
                )
                setattr(exc, "cost_ledger", partial_ledger)
                setattr(exc, "observations", tuple(observations))
                setattr(exc, "bundle_id", self.bundle_id)
                setattr(exc, "policy_source", self.policy_source)
                raise

            trace_after = getattr(self.backend, "last_trace", None)
            actual_failed = 0
            if isinstance(trace_after, dict) and "generations" in trace_after and len(trace_after["generations"]) > 0:
                actual_reqs = len(trace_after["generations"])
                actual_succeeded = sum(
                    1 for g in trace_after["generations"]
                    if g.get("status") in ("success", "completed")
                    or (
                        g.get("status") not in ("failed", "error", "cancelled", "timeout")
                        and g.get("finish_reason") not in ("failed", "error", "cancelled", "timeout")
                    )
                )
                actual_failed = actual_reqs - actual_succeeded
            else:
                actual_reqs = est_reqs
                actual_succeeded = est_reqs
                actual_failed = 0

            # Observation validation wrapped to preserve cost ledger on invalid outputs
            try:
                if not isinstance(answer, str):
                    raise ValueError("Backend answer must be text")
                if isinstance(confidence, bool) or not isinstance(confidence, Real) or not np.isfinite(confidence) or not 0 <= confidence <= 1:
                    raise ValueError("Backend confidence must be finite and within [0, 1]")
                if isinstance(tokens, bool) or not isinstance(tokens, Integral) or tokens < 0:
                    raise ValueError("Backend generated-token count must be a nonnegative integer")
            except Exception as val_err:
                raw_tok = int(tokens) if (isinstance(tokens, (int, float)) and np.isfinite(tokens) and not isinstance(tokens, bool)) else 0
                val_ledger = ExecutionCostLedger(
                    strategy_invocations=dispatched_strategies,
                    underlying_requests_dispatched=dispatched_requests + actual_reqs,
                    underlying_requests_succeeded=successful_requests + actual_succeeded,
                    underlying_requests_failed=failed_requests + actual_failed,
                    generated_tokens=total_tokens + raw_tok,
                    prompt_tokens=None,
                    full_inference_cost_estimated=False,
                    status="failed",
                )
                setattr(val_err, "cost_ledger", val_ledger)
                setattr(val_err, "observations", tuple(observations))
                setattr(val_err, "bundle_id", self.bundle_id)
                setattr(val_err, "policy_source", self.policy_source)
                raise

            raw_tokens = int(tokens)
            obs = StrategyObservation(strategy, answer, float(confidence), raw_tokens, underlying_requests=actual_reqs)
            observations.append(obs)
            total_tokens += raw_tokens
            dispatched_requests += actual_reqs
            successful_requests += actual_succeeded
            failed_requests += actual_failed

            if on_step is not None:
                try:
                    on_step(obs)
                except Exception:
                    pass

            # Check stop events immediately after backend execution completes
            if _is_interrupted():
                final_status = "cancelled"
                break
            if _is_timeout():
                final_status = "timeout"
                break

            if tok_limit is not None and total_tokens >= tok_limit:
                final_status = "budget_exceeded"
                break

            if choice != EntryChoice.LADDER or rung == len(LADDER) - 1:
                break
            if not self.policy.should_escalate(rung, confidence):
                break

        # Final check on stop states: if interrupted or timed out during terminal strategy, override completed
        if _is_interrupted() and final_status == "completed":
            final_status = "cancelled"
        elif _is_timeout() and final_status == "completed":
            final_status = "timeout"

        ledger = ExecutionCostLedger(
            strategy_invocations=dispatched_strategies,
            underlying_requests_dispatched=dispatched_requests,
            underlying_requests_succeeded=successful_requests,
            underlying_requests_failed=failed_requests,
            generated_tokens=total_tokens,
            prompt_tokens=None,
            full_inference_cost_estimated=False,
            status=final_status,
        )

        return OnlineReasoningResult(
            observations=tuple(observations),
            latency_ms=(time.monotonic() - started) * 1000,
            policy_source=self.policy_source,
            status=final_status,
            bundle_id=self.bundle_id,
            bundle_review_status=self.bundle_review_status,
            cost_ledger=ledger,
            execution_id=execution_id,
            query_generation=query_generation,
        )
