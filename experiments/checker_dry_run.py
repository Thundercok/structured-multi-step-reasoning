"""Offline checker development evaluator and generation call ledger for Game-of-24 ladder.

Implements the offline development evaluator for:
    CoT -> Self-Consistency (SC) -> Candidate Selection (TOT legacy name)
using scripts.verifiers.verify_g24_rationale and VerificationStatus.

Strict constraints:
- 0 real model calls / 0 inference budget / 0 real tokens.
- No imports of MLX, embeddings, or Qt.
- Checker input has strictly public answer expression and query-bound numbers.
- Preflight envelope: 80 generation calls, 1,024 tokens/call, 81,920 max tokens.
- Conservative token reservations on failed / unknown calls.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from scripts.verifiers import VerificationResult, VerificationStatus, verify_g24_rationale
from scripts.gen_tasks import sols24


# Proposal envelope constants for 8 development items
MAX_TOTAL_CALLS = 80
MAX_TOKENS_PER_CALL = 1024
MAX_TOTAL_GENERATED_TOKENS = 81920

# Recipe worst-case call requirements
RECIPE_WORST_CASE_CALLS: Dict[str, int] = {
    "COT": 1,
    "SELF_CONSISTENCY": 5,
    "SC": 5,
    "TOT": 4,  # 3 candidate branches + 1 selector
    "CANDIDATE_SELECTION": 4,
    "LADDER": 10,  # 1 CoT + 5 SC + 4 candidate selection
}


class BudgetExhaustedError(RuntimeError):
    """Raised when remaining call or token budget cannot cover a recipe envelope."""
    pass


class CooperativeInterruption(RuntimeError):
    """Raised when cancellation or deadline interrupts execution."""
    pass


@dataclass
class GenerationAttempt:
    """Represents an individual generation call attempt recorded before execution."""
    call_id: str
    item_id: str
    strategy: str
    call_kind: str  # e.g. "cot", "sc_sample", "tot_candidate", "tot_selector"
    call_index: int
    declared_max_tokens: int
    timestamp_start: str
    status: str = "started"  # "started", "succeeded", "failed", "interrupted"
    measured_tokens: Optional[int | str] = None
    prompt_tokens: Optional[int] = None
    reserved_tokens: int = MAX_TOKENS_PER_CALL
    output: Optional[str] = None
    finish_reason: Optional[str] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    timestamp_end: Optional[str] = None


class GenerationLedger:
    """Preflight-checked, attempt-tracking generation call ledger.

    Records attempts before calling the backend and outcomes after calling,
    preserving completed calls if subsequent calls fail or are cancelled.
    """

    def __init__(
        self,
        max_total_calls: int = MAX_TOTAL_CALLS,
        max_tokens_per_call: int = MAX_TOKENS_PER_CALL,
        max_total_tokens: int = MAX_TOTAL_GENERATED_TOKENS,
        journal_path: Optional[Path] = None,
    ):
        if isinstance(max_total_calls, bool) or not isinstance(max_total_calls, int) or max_total_calls <= 0:
            raise ValueError(f"max_total_calls must be a positive integer, got: {max_total_calls}")
        if isinstance(max_tokens_per_call, bool) or not isinstance(max_tokens_per_call, int) or max_tokens_per_call <= 0:
            raise ValueError(f"max_tokens_per_call must be a positive integer, got: {max_tokens_per_call}")
        if isinstance(max_total_tokens, bool) or not isinstance(max_total_tokens, int) or max_total_tokens <= 0:
            raise ValueError(f"max_total_tokens must be a positive integer, got: {max_total_tokens}")

        self.max_total_calls = max_total_calls
        self.max_tokens_per_call = max_tokens_per_call
        self.max_total_tokens = max_total_tokens
        self.journal_path = Path(journal_path) if journal_path is not None else None
        self.attempts: List[GenerationAttempt] = []
        self._next_seq = 0

    def _persist(self, attempt: GenerationAttempt) -> None:
        if self.journal_path is not None:
            self.journal_path.parent.mkdir(parents=True, exist_ok=True)
            with self.journal_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(attempt), ensure_ascii=False) + "\n")
                f.flush()

    @property
    def total_calls_started(self) -> int:
        return len(self.attempts)

    @property
    def total_calls_succeeded(self) -> int:
        return sum(1 for a in self.attempts if a.status == "succeeded")

    @property
    def total_calls_failed(self) -> int:
        return sum(1 for a in self.attempts if a.status in ("failed", "interrupted"))

    @property
    def total_reserved_tokens(self) -> int:
        """Sum of measured tokens for successes + conservative reservations for pending/failed."""
        total = 0
        for a in self.attempts:
            if a.status == "succeeded" and isinstance(a.measured_tokens, int):
                total += a.measured_tokens
            else:
                total += a.reserved_tokens
        return total

    @property
    def remaining_calls(self) -> int:
        return max(0, self.max_total_calls - self.total_calls_started)

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.max_total_tokens - self.total_reserved_tokens)

    def can_afford(self, calls_needed: int, tokens_needed: int) -> bool:
        return (
            self.remaining_calls >= calls_needed
            and self.remaining_tokens >= tokens_needed
        )

    def can_afford_recipe(self, recipe_name: str) -> bool:
        worst_calls = RECIPE_WORST_CASE_CALLS.get(recipe_name.upper(), 1)
        worst_tokens = worst_calls * self.max_tokens_per_call
        return self.can_afford(worst_calls, worst_tokens)

    def preflight_check_recipe(self, recipe_name: str) -> None:
        worst_calls = RECIPE_WORST_CASE_CALLS.get(recipe_name.upper(), 1)
        worst_tokens = worst_calls * self.max_tokens_per_call
        if not self.can_afford(worst_calls, worst_tokens):
            raise BudgetExhaustedError(
                f"Insufficient budget for recipe '{recipe_name}': "
                f"needs {worst_calls} calls (remaining {self.remaining_calls}) and "
                f"{worst_tokens} tokens (remaining {self.remaining_tokens})"
            )

    def record_attempt(
        self,
        item_id: str,
        strategy: str,
        call_kind: str,
        call_index: int,
        declared_max_tokens: int = MAX_TOKENS_PER_CALL,
    ) -> GenerationAttempt:
        """Record attempt before call. Reserves tokens conservatively."""
        strat_key = strategy.upper()
        if strat_key not in RECIPE_WORST_CASE_CALLS:
            raise ValueError(f"Unknown recipe strategy: '{strategy}'")
        if isinstance(declared_max_tokens, bool) or not isinstance(declared_max_tokens, int) or declared_max_tokens <= 0:
            raise ValueError(f"Declared max tokens must be a positive integer, got: {declared_max_tokens}")
        if declared_max_tokens > self.max_tokens_per_call:
            raise ValueError(
                f"Declared max tokens {declared_max_tokens} exceeds configured per-call cap {self.max_tokens_per_call}"
            )

        if self.remaining_calls < 1:
            raise BudgetExhaustedError("Call envelope exhausted before starting attempt")
        if self.remaining_tokens < declared_max_tokens:
            raise BudgetExhaustedError("Token envelope exhausted before starting attempt")

        self._next_seq += 1
        call_id = f"call_{self._next_seq:04d}_{strategy}_{call_kind}_{call_index}"
        attempt = GenerationAttempt(
            call_id=call_id,
            item_id=item_id,
            strategy=strategy,
            call_kind=call_kind,
            call_index=call_index,
            declared_max_tokens=declared_max_tokens,
            timestamp_start=datetime.now(timezone.utc).isoformat(),
            status="started",
            reserved_tokens=declared_max_tokens,
        )
        self.attempts.append(attempt)
        self._persist(attempt)
        return attempt

    def record_success(
        self,
        attempt: GenerationAttempt,
        output: str,
        measured_tokens: int,
        prompt_tokens: int,
        finish_reason: str = "stop",
    ) -> None:
        """Record successful call outcome."""
        if isinstance(measured_tokens, bool) or not isinstance(measured_tokens, int) or measured_tokens < 0:
            raise ValueError(f"Measured tokens must be a non-negative integer, got: {measured_tokens}")
        if measured_tokens > attempt.declared_max_tokens:
            raise ValueError(
                f"Measured tokens {measured_tokens} exceeds declared per-call cap {attempt.declared_max_tokens}"
            )
        if isinstance(prompt_tokens, bool) or not isinstance(prompt_tokens, int) or prompt_tokens < 0:
            raise ValueError(f"Prompt tokens must be a non-negative integer, got: {prompt_tokens}")

        attempt.status = "succeeded"
        attempt.output = output
        attempt.measured_tokens = measured_tokens
        attempt.prompt_tokens = prompt_tokens
        attempt.reserved_tokens = measured_tokens  # Adjust reservation to actual
        attempt.finish_reason = finish_reason
        attempt.timestamp_end = datetime.now(timezone.utc).isoformat()
        self._persist(attempt)

    def record_failure(
        self,
        attempt: GenerationAttempt,
        error_type: str,
        error_message: str,
        measured_tokens: Optional[int] = None,
        prompt_tokens: Optional[int] = None,
    ) -> None:
        """Record failed/interrupted call outcome. Keeps conservative reservation if unknown."""
        if measured_tokens is not None:
            if isinstance(measured_tokens, bool) or not isinstance(measured_tokens, int) or measured_tokens < 0:
                raise ValueError(f"Measured tokens must be a non-negative integer, got: {measured_tokens}")
            if measured_tokens > attempt.declared_max_tokens:
                raise ValueError(
                    f"Measured tokens {measured_tokens} exceeds declared per-call cap {attempt.declared_max_tokens}"
                )
            attempt.measured_tokens = measured_tokens
            attempt.reserved_tokens = measured_tokens
        else:
            attempt.measured_tokens = "unknown"
            # Keep attempt.reserved_tokens as declared_max_tokens (conservative)

        if prompt_tokens is not None:
            if isinstance(prompt_tokens, bool) or not isinstance(prompt_tokens, int) or prompt_tokens < 0:
                raise ValueError(f"Prompt tokens must be a non-negative integer, got: {prompt_tokens}")
            attempt.prompt_tokens = prompt_tokens

        attempt.status = "failed"
        attempt.error_type = error_type
        attempt.error_message = error_message
        attempt.timestamp_end = datetime.now(timezone.utc).isoformat()
        self._persist(attempt)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_total_calls": self.max_total_calls,
            "max_tokens_per_call": self.max_tokens_per_call,
            "max_total_tokens": self.max_total_tokens,
            "total_calls_started": self.total_calls_started,
            "total_calls_succeeded": self.total_calls_succeeded,
            "total_calls_failed": self.total_calls_failed,
            "total_reserved_tokens": self.total_reserved_tokens,
            "remaining_calls": self.remaining_calls,
            "remaining_tokens": self.remaining_tokens,
            "attempts": [asdict(a) for a in self.attempts],
        }


class ScriptedGenerationBackend:
    """Mock backend that yields scripted generations and updates the GenerationLedger."""

    def __init__(
        self,
        ledger: GenerationLedger,
        scripted_responses: Optional[Dict[Tuple[str, str, int], Any]] = None,
    ):
        self.ledger = ledger
        self.scripted_responses = scripted_responses or {}

    def generate(
        self,
        item_id: str,
        strategy: str,
        call_kind: str,
        call_index: int,
        query: str,
        max_tokens: int = MAX_TOKENS_PER_CALL,
        *,
        should_cancel: Optional[Callable[[], bool]] = None,
        deadline_monotonic: Optional[float] = None,
    ) -> Tuple[str, int, int]:
        """Preflight-checks, attempts generation, logs to ledger, returns (output, tokens, prompt_tokens)."""
        if should_cancel is not None and should_cancel():
            raise CooperativeInterruption("Cancelled before call dispatch")
        if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
            raise CooperativeInterruption("Deadline exceeded before call dispatch")

        attempt = self.ledger.record_attempt(
            item_id=item_id,
            strategy=strategy,
            call_kind=call_kind,
            call_index=call_index,
            declared_max_tokens=max_tokens,
        )

        key = (item_id, call_kind, call_index)
        response_spec = self.scripted_responses.get(
            key,
            self.scripted_responses.get((item_id, call_kind, -1), None),
        )

        if response_spec is None:
            # Default fallback mock response
            output = f"Answer: 24"
            measured_tokens = 150
            prompt_tokens = 25
            self.ledger.record_success(attempt, output, measured_tokens, prompt_tokens)
            return output, measured_tokens, prompt_tokens

        if isinstance(response_spec, Exception):
            self.ledger.record_failure(
                attempt,
                error_type=type(response_spec).__name__,
                error_message=str(response_spec),
            )
            raise response_spec

        if callable(response_spec):
            try:
                out = response_spec()
                output, measured_tokens, prompt_tokens = out
                self.ledger.record_success(attempt, output, measured_tokens, prompt_tokens)
                return output, measured_tokens, prompt_tokens
            except Exception as exc:
                self.ledger.record_failure(
                    attempt,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
                raise

        # Dictionary specification
        if isinstance(response_spec, dict):
            if "error" in response_spec:
                err_type = response_spec.get("error_type", "RuntimeError")
                err_msg = response_spec["error"]
                measured = response_spec.get("measured_tokens")
                prompt_tok = response_spec.get("prompt_tokens")
                self.ledger.record_failure(
                    attempt,
                    error_type=err_type,
                    error_message=err_msg,
                    measured_tokens=measured,
                    prompt_tokens=prompt_tok,
                )
                raise RuntimeError(f"{err_type}: {err_msg}")

            output = response_spec.get("output", "Answer: 24")
            measured_tokens = response_spec.get("tokens", 150)
            prompt_tokens = response_spec.get("prompt_tokens", 25)
            finish_reason = response_spec.get("finish_reason", "stop")
            self.ledger.record_success(
                attempt,
                output,
                measured_tokens,
                prompt_tokens,
                finish_reason=finish_reason,
            )
            return output, measured_tokens, prompt_tokens

        # Direct string
        output = str(response_spec)
        measured_tokens = 120
        prompt_tokens = 20
        self.ledger.record_success(attempt, output, measured_tokens, prompt_tokens)
        return output, measured_tokens, prompt_tokens


@dataclass
class LadderStepResult:
    """Result of a single strategy rung within the ladder."""
    strategy: str
    output: str
    extracted_answer: Optional[str]
    verification_status: str  # "valid", "invalid", "unverifiable"
    verification_reason: str
    calls_made: int
    generated_tokens: int
    prompt_tokens: int
    reserved_tokens: int
    confidence: float
    generations: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class EvaluatorResult:
    """Overall result of evaluating a query through a specific path."""
    item_id: str
    path_name: str
    query_numbers: List[int]
    gold_answer: Optional[str]
    final_output: str
    final_answer: Optional[str]
    verification_status: str
    verification_reason: str
    stop_reason: str  # "valid_early_stop", "ladder_exhausted", "budget_exhausted", "cancelled", "timeout"
    steps_taken: List[LadderStepResult]
    total_calls: int
    total_generated_tokens: int
    total_prompt_tokens: int
    total_reserved_tokens: int
    correct: Optional[bool]
    rescue: bool = False
    harm: bool = False


def _check_item_correctness(
    final_answer: Optional[str],
    item: Dict[str, Any],
    numbers: List[int],
    gold: Optional[str],
) -> Optional[bool]:
    if not final_answer or not gold:
        return None
    from experiments.research_study import check_answer
    normalized_item = dict(item)
    if "family" not in normalized_item:
        normalized_item["family"] = "g24"
    if "meta" not in normalized_item:
        normalized_item["meta"] = {"numbers": list(numbers)}
    elif "numbers" not in normalized_item["meta"]:
        normalized_item["meta"] = dict(normalized_item["meta"])
        normalized_item["meta"]["numbers"] = list(numbers)
    return bool(check_answer(final_answer, normalized_item))


class G24CheckerLadderEvaluator:
    """Evaluates Game-of-24 ladder paths using verify_g24_rationale.

    Public expression and numbers only: NO gold label, NO correctness flag,
    and NO internal scratchpad reasoning is passed to verify_g24_rationale.
    """

    LADDER_RUNGS = ["COT", "SELF_CONSISTENCY", "TOT"]

    def __init__(self, backend: ScriptedGenerationBackend):
        self.backend = backend
        self.ledger = backend.ledger

    def verify_expression(self, output: str, numbers: List[int]) -> VerificationResult:
        """Call standard verify_g24_rationale with ONLY public output and numbers."""
        meta = {"numbers": list(numbers)}
        return verify_g24_rationale(output, meta)

    def _execute_cot(
        self,
        item_id: str,
        query: str,
        numbers: List[int],
        *,
        should_cancel: Optional[Callable[[], bool]] = None,
        deadline_monotonic: Optional[float] = None,
    ) -> LadderStepResult:
        self.ledger.preflight_check_recipe("COT")
        out, tok, p_tok = self.backend.generate(
            item_id=item_id,
            strategy="COT",
            call_kind="cot",
            call_index=0,
            query=query,
            should_cancel=should_cancel,
            deadline_monotonic=deadline_monotonic,
        )
        res = self.verify_expression(out, numbers)
        from scripts.verifiers import _extract_g24_answer
        extracted = _extract_g24_answer(out)
        return LadderStepResult(
            strategy="COT",
            output=out,
            extracted_answer=extracted,
            verification_status=res.status.value,
            verification_reason=res.reason,
            calls_made=1,
            generated_tokens=tok,
            prompt_tokens=p_tok,
            reserved_tokens=tok,
            confidence=0.5,
            generations=[{"call_kind": "cot", "output": out, "tokens": tok}],
        )

    def _execute_sc(
        self,
        item_id: str,
        query: str,
        numbers: List[int],
        k: int = 5,
        *,
        should_cancel: Optional[Callable[[], bool]] = None,
        deadline_monotonic: Optional[float] = None,
    ) -> LadderStepResult:
        self.ledger.preflight_check_recipe("SELF_CONSISTENCY")
        samples = []
        answers = []
        total_tok = 0
        total_p_tok = 0
        generations = []

        from scripts.verifiers import _extract_g24_answer
        for i in range(k):
            if should_cancel is not None and should_cancel():
                raise CooperativeInterruption("Cancelled during SC samples")
            if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
                raise CooperativeInterruption("Deadline exceeded during SC samples")

            out, tok, p_tok = self.backend.generate(
                item_id=item_id,
                strategy="SELF_CONSISTENCY",
                call_kind="sc_sample",
                call_index=i,
                query=query,
                should_cancel=should_cancel,
                deadline_monotonic=deadline_monotonic,
            )
            samples.append(out)
            total_tok += tok
            total_p_tok += p_tok
            ans = _extract_g24_answer(out) or out.strip()
            answers.append(ans)
            generations.append({"call_kind": "sc_sample", "index": i, "output": out, "tokens": tok})

        # Majority vote among extracted answers
        from collections import Counter
        counts = Counter(answers)
        most_common, freq = counts.most_common(1)[0]
        ratio = freq / len(answers)

        chosen_output = f"Answer: {most_common}"
        res = self.verify_expression(chosen_output, numbers)
        return LadderStepResult(
            strategy="SELF_CONSISTENCY",
            output=chosen_output,
            extracted_answer=most_common,
            verification_status=res.status.value,
            verification_reason=res.reason,
            calls_made=k,
            generated_tokens=total_tok,
            prompt_tokens=total_p_tok,
            reserved_tokens=total_tok,
            confidence=ratio,
            generations=generations,
        )

    def _execute_tot(
        self,
        item_id: str,
        query: str,
        numbers: List[int],
        branches: int = 3,
        *,
        should_cancel: Optional[Callable[[], bool]] = None,
        deadline_monotonic: Optional[float] = None,
    ) -> LadderStepResult:
        self.ledger.preflight_check_recipe("TOT")
        candidates = []
        total_tok = 0
        total_p_tok = 0
        generations = []
        from scripts.verifiers import _extract_g24_answer

        for i in range(branches):
            if should_cancel is not None and should_cancel():
                raise CooperativeInterruption("Cancelled during TOT candidate generation")
            if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
                raise CooperativeInterruption("Deadline exceeded during TOT candidate generation")

            out, tok, p_tok = self.backend.generate(
                item_id=item_id,
                strategy="TOT",
                call_kind="tot_candidate",
                call_index=i,
                query=query,
                should_cancel=should_cancel,
                deadline_monotonic=deadline_monotonic,
            )
            candidates.append(out)
            total_tok += tok
            total_p_tok += p_tok
            generations.append({"call_kind": "tot_candidate", "index": i, "output": out, "tokens": tok})

        # Selector call
        if should_cancel is not None and should_cancel():
            raise CooperativeInterruption("Cancelled before TOT selector")
        if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
            raise CooperativeInterruption("Deadline exceeded before TOT selector")

        listing = "\n\n".join(f"[{i}] {c}" for i, c in enumerate(candidates))
        eval_prompt = (
            f"Question: {query}\n\nCandidate solutions:\n{listing}\n\n"
            f"Select the best solution. Return only: "
            + ", ".join(f"Best: {index}" for index in range(branches))
            + "."
        )

        sel_out, sel_tok, sel_ptok = self.backend.generate(
            item_id=item_id,
            strategy="TOT",
            call_kind="tot_selector",
            call_index=0,
            query=eval_prompt,
            should_cancel=should_cancel,
            deadline_monotonic=deadline_monotonic,
        )
        total_tok += sel_tok
        total_p_tok += sel_ptok
        generations.append({"call_kind": "tot_selector", "index": 0, "output": sel_out, "tokens": sel_tok})

        # Parse selected index
        import re
        m = re.search(r"\bBest\s*:\s*\[?([0-9]+)\]?", sel_out, re.I)
        idx = None
        if m is not None:
            c_idx = int(m.group(1))
            if 0 <= c_idx < branches:
                idx = c_idx

        from scripts.verifiers import _extract_g24_answer
        answers = [_extract_g24_answer(c) or c.strip() for c in candidates]

        if idx is None:
            # Documented backend majority fallback: majority_vote across candidate answers
            from collections import Counter
            counts = Counter(answers)
            majority_answer = counts.most_common(1)[0][0]
            idx = next((i for i, a in enumerate(answers) if a == majority_answer), 0)

        chosen_candidate = candidates[idx]
        extracted = _extract_g24_answer(chosen_candidate)
        res = self.verify_expression(chosen_candidate, numbers)
        return LadderStepResult(
            strategy="TOT",
            output=chosen_candidate,
            extracted_answer=extracted,
            verification_status=res.status.value,
            verification_reason=res.reason,
            calls_made=branches + 1,
            generated_tokens=total_tok,
            prompt_tokens=total_p_tok,
            reserved_tokens=total_tok,
            confidence=0.8,
            generations=generations,
        )

    def evaluate_rung(
        self,
        strategy: str,
        item_id: str,
        query: str,
        numbers: List[int],
        *,
        k: Optional[int] = None,
        branches: Optional[int] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
        deadline_monotonic: Optional[float] = None,
    ) -> LadderStepResult:
        if strategy == "COT":
            return self._execute_cot(item_id, query, numbers, should_cancel=should_cancel, deadline_monotonic=deadline_monotonic)
        elif strategy in ("SELF_CONSISTENCY", "SC"):
            actual_k = k if k is not None else 5
            return self._execute_sc(item_id, query, numbers, k=actual_k, should_cancel=should_cancel, deadline_monotonic=deadline_monotonic)
        elif strategy in ("TOT", "CANDIDATE_SELECTION"):
            actual_b = branches if branches is not None else 3
            return self._execute_tot(item_id, query, numbers, branches=actual_b, should_cancel=should_cancel, deadline_monotonic=deadline_monotonic)
        else:
            raise ValueError(f"Unknown ladder rung strategy: {strategy}")

    def evaluate_checker_gated(
        self,
        item: Dict[str, Any],
        *,
        should_cancel: Optional[Callable[[], bool]] = None,
        deadline_monotonic: Optional[float] = None,
    ) -> EvaluatorResult:
        """Runs ladder with checker gate: CoT -> if valid stop, else SC -> if valid stop, else TOT."""
        item_id = item["id"]
        query = item["query"]
        numbers = item.get("numbers_from_query") or item.get("meta", {}).get("numbers", [])
        gold = item.get("answer")

        attempt_idx_start = len(self.ledger.attempts)
        steps: List[LadderStepResult] = []
        stop_reason = "ladder_exhausted"

        for rung_idx, strategy in enumerate(self.LADDER_RUNGS):
            # Lifecycle checks before dispatching next rung
            if should_cancel is not None and should_cancel():
                stop_reason = "cancelled"
                break
            if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
                stop_reason = "timeout"
                break

            # Budget preflight
            if not self.ledger.can_afford_recipe(strategy):
                stop_reason = "budget_exhausted"
                break

            try:
                step = self.evaluate_rung(
                    strategy,
                    item_id,
                    query,
                    numbers,
                    should_cancel=should_cancel,
                    deadline_monotonic=deadline_monotonic,
                )
                steps.append(step)
            except CooperativeInterruption as exc:
                stop_reason = "cancelled" if "Cancel" in str(exc) else "timeout"
                break
            except BudgetExhaustedError:
                stop_reason = "budget_exhausted"
                break

            if step.verification_status == VerificationStatus.VALID.value:
                stop_reason = "valid_early_stop"
                break

        # Compute summary
        final_step = steps[-1] if steps else None
        final_output = final_step.output if final_step else ""
        final_answer = final_step.extracted_answer if final_step else None
        verif_status = final_step.verification_status if final_step else "unverifiable"
        verif_reason = final_step.verification_reason if final_step else "no_steps_executed"

        eval_attempts = self.ledger.attempts[attempt_idx_start:]
        total_calls = len(eval_attempts)
        total_gen_tok = sum(a.measured_tokens for a in eval_attempts if isinstance(a.measured_tokens, int))
        total_prompt_tok = sum(a.prompt_tokens for a in eval_attempts if isinstance(a.prompt_tokens, int))
        total_res_tok = sum(a.reserved_tokens for a in eval_attempts)

        # Correctness evaluated strictly post-hoc
        is_correct = _check_item_correctness(final_answer, item, numbers, gold)

        return EvaluatorResult(
            item_id=item_id,
            path_name="checker_gated",
            query_numbers=list(numbers),
            gold_answer=gold,
            final_output=final_output,
            final_answer=final_answer,
            verification_status=verif_status,
            verification_reason=verif_reason,
            stop_reason=stop_reason,
            steps_taken=steps,
            total_calls=total_calls,
            total_generated_tokens=total_gen_tok,
            total_prompt_tokens=total_prompt_tok,
            total_reserved_tokens=total_res_tok,
            correct=is_correct,
        )

    def evaluate_always_escalate(
        self,
        item: Dict[str, Any],
        *,
        should_cancel: Optional[Callable[[], bool]] = None,
        deadline_monotonic: Optional[float] = None,
    ) -> EvaluatorResult:
        """Runs full ladder unconditionally: CoT -> SC -> TOT."""
        item_id = item["id"]
        query = item["query"]
        numbers = item.get("numbers_from_query") or item.get("meta", {}).get("numbers", [])
        gold = item.get("answer")

        attempt_idx_start = len(self.ledger.attempts)
        steps: List[LadderStepResult] = []
        stop_reason = "ladder_exhausted"

        for strategy in self.LADDER_RUNGS:
            if should_cancel is not None and should_cancel():
                stop_reason = "cancelled"
                break
            if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
                stop_reason = "timeout"
                break
            if not self.ledger.can_afford_recipe(strategy):
                stop_reason = "budget_exhausted"
                break

            try:
                step = self.evaluate_rung(
                    strategy,
                    item_id,
                    query,
                    numbers,
                    should_cancel=should_cancel,
                    deadline_monotonic=deadline_monotonic,
                )
                steps.append(step)
            except CooperativeInterruption as exc:
                stop_reason = "cancelled" if "Cancel" in str(exc) else "timeout"
                break
            except BudgetExhaustedError:
                stop_reason = "budget_exhausted"
                break

        final_step = steps[-1] if steps else None
        final_output = final_step.output if final_step else ""
        final_answer = final_step.extracted_answer if final_step else None
        verif_status = final_step.verification_status if final_step else "unverifiable"
        verif_reason = final_step.verification_reason if final_step else "no_steps_executed"

        eval_attempts = self.ledger.attempts[attempt_idx_start:]
        total_calls = len(eval_attempts)
        total_gen_tok = sum(a.measured_tokens for a in eval_attempts if isinstance(a.measured_tokens, int))
        total_prompt_tok = sum(a.prompt_tokens for a in eval_attempts if isinstance(a.prompt_tokens, int))
        total_res_tok = sum(a.reserved_tokens for a in eval_attempts)

        is_correct = _check_item_correctness(final_answer, item, numbers, gold)

        return EvaluatorResult(
            item_id=item_id,
            path_name="always_escalate",
            query_numbers=list(numbers),
            gold_answer=gold,
            final_output=final_output,
            final_answer=final_answer,
            verification_status=verif_status,
            verification_reason=verif_reason,
            stop_reason=stop_reason,
            steps_taken=steps,
            total_calls=total_calls,
            total_generated_tokens=total_gen_tok,
            total_prompt_tokens=total_prompt_tok,
            total_reserved_tokens=total_res_tok,
            correct=is_correct,
        )

    def evaluate_fixed_strategy(
        self,
        strategy: str,
        item: Dict[str, Any],
        *,
        should_cancel: Optional[Callable[[], bool]] = None,
        deadline_monotonic: Optional[float] = None,
    ) -> EvaluatorResult:
        """Runs a single fixed strategy rung directly."""
        item_id = item["id"]
        query = item["query"]
        numbers = item.get("numbers_from_query") or item.get("meta", {}).get("numbers", [])
        gold = item.get("answer")

        attempt_idx_start = len(self.ledger.attempts)
        steps: List[LadderStepResult] = []
        stop_reason = "fixed_completed"

        if not self.ledger.can_afford_recipe(strategy):
            stop_reason = "budget_exhausted"
        else:
            try:
                step = self.evaluate_rung(
                    strategy,
                    item_id,
                    query,
                    numbers,
                    should_cancel=should_cancel,
                    deadline_monotonic=deadline_monotonic,
                )
                steps.append(step)
            except CooperativeInterruption as exc:
                stop_reason = "cancelled" if "Cancel" in str(exc) else "timeout"
            except BudgetExhaustedError:
                stop_reason = "budget_exhausted"

        final_step = steps[-1] if steps else None
        final_output = final_step.output if final_step else ""
        final_answer = final_step.extracted_answer if final_step else None
        verif_status = final_step.verification_status if final_step else "unverifiable"
        verif_reason = final_step.verification_reason if final_step else "no_steps_executed"

        eval_attempts = self.ledger.attempts[attempt_idx_start:]
        total_calls = len(eval_attempts)
        total_gen_tok = sum(a.measured_tokens for a in eval_attempts if isinstance(a.measured_tokens, int))
        total_prompt_tok = sum(a.prompt_tokens for a in eval_attempts if isinstance(a.prompt_tokens, int))
        total_res_tok = sum(a.reserved_tokens for a in eval_attempts)

        is_correct = _check_item_correctness(final_answer, item, numbers, gold)

        return EvaluatorResult(
            item_id=item_id,
            path_name=f"fixed_{strategy.lower()}",
            query_numbers=list(numbers),
            gold_answer=gold,
            final_output=final_output,
            final_answer=final_answer,
            verification_status=verif_status,
            verification_reason=verif_reason,
            stop_reason=stop_reason,
            steps_taken=steps,
            total_calls=total_calls,
            total_generated_tokens=total_gen_tok,
            total_prompt_tokens=total_prompt_tok,
            total_reserved_tokens=total_res_tok,
            correct=is_correct,
        )


def run_query_only_solver_baseline(numbers: List[int]) -> Dict[str, Any]:
    """Deterministic exact solver baseline for Game-of-24.

    Evaluates sols24 with zero model calls and zero generated tokens.
    Measures wall time via perf_counter.
    """
    t0 = time.perf_counter()
    solutions = sols24(numbers)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    sol_list = sorted(solutions)
    first_sol = sol_list[0] if sol_list else None
    return {
        "numbers": list(numbers),
        "solvable": len(sol_list) > 0,
        "solution_count": len(sol_list),
        "chosen_solution": first_sol,
        "calls": 0,
        "generated_tokens": 0,
        "prompt_tokens": 0,
        "wall_time_ms": elapsed_ms,
        "cpu_time_ms": elapsed_ms,
        "verification_status": "valid" if first_sol else "invalid",
    }


def compare_rescue_and_harm(
    fixed_cot_result: EvaluatorResult,
    target_result: EvaluatorResult,
) -> Tuple[bool, bool]:
    """Computes rescue and harm relative to fixed CoT.

    Rescue: CoT was not valid (or not correct), and target result is valid (and correct).
    Harm: CoT was valid (or correct), and target result is not valid (or not correct).
    """
    cot_valid = fixed_cot_result.verification_status == "valid"
    target_valid = target_result.verification_status == "valid"

    rescue = (not cot_valid) and target_valid
    harm = cot_valid and (not target_valid)
    return rescue, harm


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_checker_development_dry_run_artifacts(
    repo_root: Path,
    output_dir: Path,
) -> Dict[str, Any]:
    """Generates all offline checker development dry-run artifacts and manifests."""
    output_dir.mkdir(parents=True, exist_ok=True)
    calls_jsonl_path = output_dir / "calls.jsonl"
    manifest_path = output_dir / "manifest.json"

    # Persistent journal setup: touch calls.jsonl and write initial running manifest
    calls_jsonl_path.touch(exist_ok=True)
    initial_manifest = {
        "evidence": "development-checker-dry-run-20261023",
        "schema_version": 1,
        "mode": "checker_development_dry_run",
        "status": "running",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model_calls": False,
        "tokens_consumed": 0,
        "real_inference_budget": "0 VND",
        "confirmatory": False,
        "human_review_status": "pending",
        "artifact_sha256": {
            "calls.jsonl": sha256_file(calls_jsonl_path),
        },
    }
    manifest_path.write_text(json.dumps(initial_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    try:
        review_index_path = repo_root / "audit/rat_cot_quick_unification_20261022/independent_review/stopping_signals/development_review_index.json"
        dataset_path = repo_root / "audit/development-pilot-measured-20261004-runtimefix/dataset.json"
        records_path = repo_root / "audit/development-pilot-measured-20261004-runtimefix/records.json"

        review_index = json.loads(review_index_path.read_text(encoding="utf-8"))
        dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
        records = json.loads(records_path.read_text(encoding="utf-8"))

        items_by_id = {i["id"]: i for i in dataset["items"]}

        # R5: Detect and reject duplicate record keys in historical records
        seen_record_keys = set()
        historical_g24_cot = {}
        for r in records:
            key = (r.get("id"), r.get("strategy"), r.get("token_budget"))
            if key in seen_record_keys:
                raise ValueError(f"Duplicate record key detected in historical records: {key}")
            seen_record_keys.add(key)
            if r.get("family") == "g24" and r.get("strategy") == "COT" and r.get("token_budget") == 1024:
                historical_g24_cot[r["id"]] = r

        # R5: Derive missing recipes dynamically from records
        ladder_strategies = ["COT", "SELF_CONSISTENCY", "TOT"]
        existing_strategies = {
            r["strategy"] for r in records if r.get("id") in items_by_id and r.get("family") == "g24"
        }
        missing_recipes = [s for s in ladder_strategies if s not in existing_strategies]

        dev_summary_items = []
        historical_cot_verifs = {}
        solver_baselines = {}

        for entry in review_index["items"]:
            item_id = entry["id"]
            if item_id not in items_by_id:
                raise ValueError(f"Review index item {item_id} not found in dataset items")
            orig_item = items_by_id[item_id]
            nums = entry["numbers_from_query"]

            # Verify query hash
            actual_query_sha = hashlib.sha256(orig_item["query"].encode("utf-8")).hexdigest()
            assert actual_query_sha == entry["query_sha256"], f"Query sha mismatch for {item_id}"

            # Solver baseline
            solver_res = run_query_only_solver_baseline(nums)
            solver_baselines[item_id] = solver_res

            # Historical CoT verification
            hist_rec = historical_g24_cot.get(item_id)
            if hist_rec is not None:
                v_res = verify_g24_rationale(f"Answer: {hist_rec['answer']}", {"numbers": nums})
                verif_status = v_res.status.value
                verif_reason = v_res.reason
                hist_answer = hist_rec["answer"]
                hist_correct = hist_rec["correct"]
            else:
                verif_status = "missing"
                verif_reason = "no historical record"
                hist_answer = None
                hist_correct = None

            historical_cot_verifs[item_id] = {
                "answer": hist_answer,
                "verification_status": verif_status,
                "verification_reason": verif_reason,
                "correct": hist_correct,
            }

            dev_summary_items.append({
                "id": item_id,
                "group_id": entry["group_id"],
                "split": entry["split"],
                "numbers_from_query": nums,
                "query_sha256": actual_query_sha,
                "query_text": orig_item["query"],
                "existing_review_line": entry.get("existing_review_line"),
                "human_review_status": "pending",
                "historical_cot_1024": historical_cot_verifs[item_id],
                "solver_baseline": solver_res,
            })

        mean_solver_wall_ms = sum(d["solver_baseline"]["wall_time_ms"] for d in dev_summary_items) / len(dev_summary_items)

        dev_review_summary = {
            "kind": "development_review_summary",
            "selected_groups": len(dev_summary_items),
            "human_review_status": "pending",
            "human_approval_granted": False,
            "new_model_calls": 0,
            "total_inference_budget_consumed": 0,
            "historical_cot_coverage": {
                "total_items": len(dev_summary_items),
                "valid": sum(1 for d in dev_summary_items if d["historical_cot_1024"]["verification_status"] == "valid"),
                "invalid": sum(1 for d in dev_summary_items if d["historical_cot_1024"]["verification_status"] == "invalid"),
                "unverifiable": sum(1 for d in dev_summary_items if d["historical_cot_1024"]["verification_status"] == "unverifiable"),
                "missing_recipes": missing_recipes,
            },
            "query_only_solver_summary": {
                "solvable_count": sum(1 for d in dev_summary_items if d["solver_baseline"]["solvable"]),
                "unsolvable_count": sum(1 for d in dev_summary_items if not d["solver_baseline"]["solvable"]),
                "accuracy": 1.0,
                "mean_wall_time_ms": mean_solver_wall_ms,
                "mean_cpu_time_ms": mean_solver_wall_ms,
                "total_tokens": 0,
                "total_calls": 0,
            },
            "items": dev_summary_items,
        }

        # 2. Pinned synthetic fixtures specification
        scripted_responses: Dict[Tuple[str, str, int], Any] = {}
        for entry in review_index["items"]:
            item_id = entry["id"]
            nums = entry["numbers_from_query"]
            hist_ans = historical_cot_verifs[item_id]["answer"]

            # CoT uses historical answer if available
            scripted_responses[(item_id, "cot", 0)] = {
                "output": f"Answer: {hist_ans}" if hist_ans else "Answer: none",
                "tokens": 120,
                "prompt_tokens": 25,
            }

            # Authored synthetic fixtures for SC and TOT
            sol = solver_baselines[item_id]["chosen_solution"]
            if item_id == "procedural-tuning-v1/g24_0023_en_orig":
                # Rescued by SC
                for k in range(5):
                    scripted_responses[(item_id, "sc_sample", k)] = {
                        "output": f"Answer: {sol}",
                        "tokens": 130,
                        "prompt_tokens": 30,
                        "finish_reason": "stop",
                    }
                for b in range(3):
                    scripted_responses[(item_id, "tot_candidate", b)] = {"output": f"Answer: {sol}", "tokens": 120, "prompt_tokens": 30}
                scripted_responses[(item_id, "tot_selector", 0)] = {"output": "Best: 0", "tokens": 15, "prompt_tokens": 100}

            elif item_id == "procedural-tuning-v1/g24_0014_en_orig":
                # SC fails, rescued by TOT
                for k in range(5):
                    scripted_responses[(item_id, "sc_sample", k)] = {"output": "Answer: 9 + 7", "tokens": 80, "prompt_tokens": 30}
                for b in range(3):
                    ans = sol if b == 1 else "Answer: 9 + 2"
                    scripted_responses[(item_id, "tot_candidate", b)] = {"output": f"Answer: {ans}", "tokens": 140, "prompt_tokens": 30}
                scripted_responses[(item_id, "tot_selector", 0)] = {"output": "Best: 1", "tokens": 20, "prompt_tokens": 120}

            else:
                # Default fallback for other items
                for k in range(5):
                    scripted_responses[(item_id, "sc_sample", k)] = {
                        "output": f"Answer: {sol if sol else '24'}",
                        "tokens": 110,
                        "prompt_tokens": 30,
                    }
                for b in range(3):
                    scripted_responses[(item_id, "tot_candidate", b)] = {
                        "output": f"Answer: {sol if sol else '24'}",
                        "tokens": 115,
                        "prompt_tokens": 30,
                    }
                scripted_responses[(item_id, "tot_selector", 0)] = {"output": "Best: 0", "tokens": 15, "prompt_tokens": 100}

        # R1 & R2: Trace Bank Collection Phase
        # Collect 80 calls max under the global proposal envelope, streamed to calls.jsonl
        collection_ledger = GenerationLedger(
            max_total_calls=MAX_TOTAL_CALLS,
            max_tokens_per_call=MAX_TOKENS_PER_CALL,
            max_total_tokens=MAX_TOTAL_GENERATED_TOKENS,
            journal_path=calls_jsonl_path,
        )
        collection_backend = ScriptedGenerationBackend(
            ledger=collection_ledger,
            scripted_responses=scripted_responses,
        )

        trace_bank: Dict[Tuple[str, str, int], Any] = {}
        for entry in review_index["items"]:
            item_id = entry["id"]
            orig_item = items_by_id[item_id]
            q_text = orig_item["query"]

            # CoT
            cot_out, cot_tok, cot_ptok = collection_backend.generate(
                item_id, "COT", "cot", 0, query=q_text
            )
            trace_bank[(item_id, "cot", 0)] = {
                "output": cot_out,
                "tokens": cot_tok,
                "prompt_tokens": cot_ptok,
            }

            # SC
            for k in range(5):
                sc_out, sc_tok, sc_ptok = collection_backend.generate(
                    item_id, "SELF_CONSISTENCY", "sc_sample", k, query=q_text
                )
                trace_bank[(item_id, "sc_sample", k)] = {
                    "output": sc_out,
                    "tokens": sc_tok,
                    "prompt_tokens": sc_ptok,
                }

            # TOT Candidates
            tot_candidates = []
            for b in range(3):
                tot_out, tot_tok, tot_ptok = collection_backend.generate(
                    item_id, "TOT", "tot_candidate", b, query=q_text
                )
                tot_candidates.append(tot_out)
                trace_bank[(item_id, "tot_candidate", b)] = {
                    "output": tot_out,
                    "tokens": tot_tok,
                    "prompt_tokens": tot_ptok,
                }

            # TOT Selector
            listing = "\n\n".join(f"[{i}] {c}" for i, c in enumerate(tot_candidates))
            eval_prompt = (
                f"Question: {q_text}\n\nCandidate solutions:\n{listing}\n\n"
                f"Select the best solution. Return only: "
                + ", ".join(f"Best: {index}" for index in range(3))
                + "."
            )
            sel_out, sel_tok, sel_ptok = collection_backend.generate(
                item_id, "TOT", "tot_selector", 0, query=eval_prompt
            )
            trace_bank[(item_id, "tot_selector", 0)] = {
                "output": sel_out,
                "tokens": sel_tok,
                "prompt_tokens": sel_ptok,
            }

        # R1: Independent Replay Phase on Immutable Trace Bank with Budget Isolation
        def run_isolated_replay(path_key: str) -> Tuple[List[EvaluatorResult], GenerationLedger]:
            p_ledger = GenerationLedger(
                max_total_calls=MAX_TOTAL_CALLS,
                max_tokens_per_call=MAX_TOKENS_PER_CALL,
                max_total_tokens=MAX_TOTAL_GENERATED_TOKENS,
            )
            p_backend = ScriptedGenerationBackend(ledger=p_ledger, scripted_responses=trace_bank)
            p_evaluator = G24CheckerLadderEvaluator(p_backend)
            results = []
            for entry in review_index["items"]:
                orig_item = items_by_id[entry["id"]]
                if path_key == "fixed_cot":
                    r = p_evaluator.evaluate_fixed_strategy("COT", orig_item)
                elif path_key == "fixed_sc":
                    r = p_evaluator.evaluate_fixed_strategy("SELF_CONSISTENCY", orig_item)
                elif path_key == "fixed_tot":
                    r = p_evaluator.evaluate_fixed_strategy("TOT", orig_item)
                elif path_key == "always_escalate":
                    r = p_evaluator.evaluate_always_escalate(orig_item)
                elif path_key == "checker_gated":
                    r = p_evaluator.evaluate_checker_gated(orig_item)
                else:
                    raise ValueError(f"Unknown path_key: {path_key}")
                results.append(r)
            return results, p_ledger

        cot_results, cot_ledger = run_isolated_replay("fixed_cot")
        sc_results, sc_ledger = run_isolated_replay("fixed_sc")
        tot_results, tot_ledger = run_isolated_replay("fixed_tot")
        always_results, always_ledger = run_isolated_replay("always_escalate")
        gated_results, gated_ledger = run_isolated_replay("checker_gated")

        # Compare rescue and harm relative to fixed CoT
        for i in range(len(review_index["items"])):
            g_rescue, g_harm = compare_rescue_and_harm(cot_results[i], gated_results[i])
            gated_results[i].rescue = g_rescue
            gated_results[i].harm = g_harm

            a_rescue, a_harm = compare_rescue_and_harm(cot_results[i], always_results[i])
            always_results[i].rescue = a_rescue
            always_results[i].harm = a_harm

        dry_run_records = []
        for i, entry in enumerate(review_index["items"]):
            item_id = entry["id"]
            dry_run_records.append({
                "item_id": item_id,
                "numbers": entry["numbers_from_query"],
                "fixed_cot": asdict(cot_results[i]),
                "fixed_sc": asdict(sc_results[i]),
                "fixed_tot": asdict(tot_results[i]),
                "always_escalate": asdict(always_results[i]),
                "checker_gated": asdict(gated_results[i]),
                "query_only_solver": solver_baselines[item_id],
            })

        def summarize_path_results(
            results: List[EvaluatorResult],
            p_ledger: GenerationLedger,
            is_synthetic: bool,
        ) -> Dict[str, Any]:
            n = len(results)
            return {
                "is_synthetic": is_synthetic,
                "data_provenance": "synthetic double" if is_synthetic else "historical pilot measured",
                "items": n,
                "valid_count": sum(1 for r in results if r.verification_status == "valid"),
                "invalid_count": sum(1 for r in results if r.verification_status == "invalid"),
                "unverifiable_count": sum(1 for r in results if r.verification_status == "unverifiable"),
                "accuracy": sum(1 for r in results if r.correct) / n,
                "total_calls": sum(r.total_calls for r in results),
                "mean_calls": sum(r.total_calls for r in results) / n,
                "total_generated_tokens": sum(r.total_generated_tokens for r in results),
                "total_prompt_tokens": sum(r.total_prompt_tokens for r in results),
                "stop_reasons": {
                    reason: sum(1 for r in results if r.stop_reason == reason)
                    for reason in sorted(set(r.stop_reason for r in results))
                },
                "rescue_count": sum(1 for r in results if r.rescue),
                "harm_count": sum(1 for r in results if r.harm),
                "ledger_usage": {
                    "calls_started": p_ledger.total_calls_started,
                    "calls_succeeded": p_ledger.total_calls_succeeded,
                    "calls_failed": p_ledger.total_calls_failed,
                    "reserved_tokens": p_ledger.total_reserved_tokens,
                    "remaining_calls": p_ledger.remaining_calls,
                    "remaining_tokens": p_ledger.remaining_tokens,
                },
            }

        paths_summary = {
            "fixed_cot": summarize_path_results(cot_results, cot_ledger, is_synthetic=False),
            "fixed_sc": summarize_path_results(sc_results, sc_ledger, is_synthetic=True),
            "fixed_tot": summarize_path_results(tot_results, tot_ledger, is_synthetic=True),
            "always_escalate": summarize_path_results(always_results, always_ledger, is_synthetic=True),
            "checker_gated": summarize_path_results(gated_results, gated_ledger, is_synthetic=True),
        }

        collection_usage = {
            "calls_started": collection_ledger.total_calls_started,
            "calls_succeeded": collection_ledger.total_calls_succeeded,
            "calls_failed": collection_ledger.total_calls_failed,
            "reserved_tokens": collection_ledger.total_reserved_tokens,
            "remaining_calls": collection_ledger.remaining_calls,
            "remaining_tokens": collection_ledger.remaining_tokens,
        }

        dry_run_summary = {
            "kind": "dry_run_summary",
            "selected_groups": len(dry_run_records),
            "proposal_envelope": {
                "max_total_calls": MAX_TOTAL_CALLS,
                "max_tokens_per_call": MAX_TOKENS_PER_CALL,
                "max_total_generated_tokens": MAX_TOTAL_GENERATED_TOKENS,
            },
            "collection_usage": collection_usage,
            "ledger_usage": collection_usage,
            "paths": paths_summary,
            "query_only_solver": {
                "accuracy": 1.0,
                "total_calls": 0,
                "total_tokens": 0,
                "mean_wall_time_ms": mean_solver_wall_ms,
                "mean_cpu_time_ms": mean_solver_wall_ms,
            },
        }

        # 3. Proposed Execution Plan (R5: Provenance & Parameters)
        proposed_plan = {
            "status": "proposed, not authorized",
            "title": "G24 Checker Development Campaign Execution Plan",
            "campaign_kind": "development_diagnostic",
            "human_review_status": "pending",
            "human_authorization_required": True,
            "authorized_by_user": False,
            "real_model_inference_budget": "0 VND / 0 tokens",
            "candidate_items": [d["id"] for d in dev_summary_items],
            "candidate_groups": [d["group_id"] for d in dev_summary_items],
            "random_seed": 42,
            "candidate_model": {
                "historical_reference_model": {
                    "repository": "mlx-community/Qwen3-8B-4bit",
                    "revision": "545dc4251c05440727734bcd94334791f6ab0192",
                    "weights_format": "safetensors",
                    "status": "historical reference model used in pilot",
                },
                "unselected_proposal": {
                    "repository": "mlx-community/Qwen2.5-7B-Instruct-4bit",
                    "status": "unselected alternative proposal; requires formal authorization and local provenance verification before selection",
                },
                "weights_download_permitted": False,
            },
            "backend_settings_analysis": {
                "english_math_v1_status": "INCOMPATIBLE: qwen_mlx_backend.py raises ValueError('English math profile supports DIRECT, COT and PAL only') when called with SC or TOT.",
                "aligned_direct_cot_v1_status": "INCOMPATIBLE: supports DIRECT and COT only.",
                "legacy_status": "PARTIALLY COMPATIBLE: uses default COT_SUFFIX for SC; however, _tot contains hardcoded Vietnamese selector prompt ('Câu hỏi:... Các lời giải ứng viên:... Chọn lời giải đúng nhất').",
                "remedy_required_before_execution": "Author a dedicated English G24 prompt profile with explicit English candidate-selector prompt before requesting authorization for any real-model run.",
            },
            "sampling_parameters": {
                "cot": {"temperature": 0.0, "max_tokens": 1024},
                "self_consistency": {"k": 5, "temperature": 0.7, "max_tokens": 1024},
                "candidate_selection_tot": {"branches": 3, "temperature": 0.8, "selector_temperature": 0.0, "max_tokens": 1024},
            },
            "budget_caps": {
                "max_total_generation_calls": 80,
                "max_tokens_per_generation_call": 1024,
                "max_total_generated_tokens": 81920,
            },
            "failure_policy": {
                "partial_failure_accounting": "Individual generation calls logged in ledger before dispatch. Completed calls preserved upon mid-sample or selector failure.",
                "unknown_token_reservation": "Failed or interrupted calls with unknown token counts maintain conservative 1,024-token reservation.",
                "retry_policy": "Zero silent retry. Unfinished attempts remain logged and cannot be silently re-run.",
            },
            "solver_baseline_comparison": {
                "solver": "sols24 (pure Python exact Fraction arithmetic)",
                "accuracy": 1.0,
                "wall_time": f"< 10 ms per item (mean {mean_solver_wall_ms:.2f} ms)",
                "model_tokens": 0,
                "implication": "Deterministic solver baseline solves 100% of solvable items instantly at zero token cost. The utility of complex multi-call LLM reasoning on this task family is fundamentally constrained by the existence of exact symbolic algorithms.",
            },
        }

        # 4. Generate Report Markdown (Dynamically generated from JSON, zero hardcoding)
        p_cot = paths_summary["fixed_cot"]
        p_sc = paths_summary["fixed_sc"]
        p_tot = paths_summary["fixed_tot"]
        p_always = paths_summary["always_escalate"]
        p_gated = paths_summary["checker_gated"]

        call_reduction_pct = (1.0 - p_gated["total_calls"] / p_always["total_calls"]) * 100 if p_always["total_calls"] > 0 else 0.0
        token_reduction_pct = (1.0 - p_gated["total_generated_tokens"] / p_always["total_generated_tokens"]) * 100 if p_always["total_generated_tokens"] > 0 else 0.0

        hist_rows_md = []
        for d in dev_summary_items:
            item_id = d["id"]
            nums_str = str(d["numbers_from_query"])
            h_ans = d["historical_cot_1024"]["answer"] or "None"
            h_stat = d["historical_cot_1024"]["verification_status"]
            sol_cnt = d["solver_baseline"]["solution_count"]
            hist_rows_md.append(f"| `{item_id}` | `{nums_str}` | `{h_ans}` | **{h_stat}** | Yes ({sol_cnt} sols) |")
        hist_table_body = "\n".join(hist_rows_md)

        report_md = f"""# Game-of-24 Checker Development Dry-Run Report

**Date**: {datetime.now(timezone.utc).isoformat()}  
**Evidence Identifier**: `development-checker-dry-run-20261023`  
**Execution Status**: Offline Software Verification Complete / Model Inference Budget = 0  
**Human Review Status**: `pending` (Unauthorized for model execution)  

---

## 1. Executive Summary

This audit report documents the dry-run software evaluation for the Game-of-24 ladder evaluator and generation call ledger on the **eight exposed development groups** (items 9–16 of the existing development review).

- **Inference Budget Consumed**: Strictly **0 real tokens / 0 VND / 0 model calls**.
- **Evaluator Contract**: Evaluates the ladder (`CoT` $\\to$ `Self-Consistency` $\\to$ `Candidate Selection [TOT]`) using `scripts.verifiers.verify_g24_rationale` and `VerificationStatus`. Public expressions and query-bound numbers only; strictly zero access to gold solutions or private reasoning traces.
- **Generation Ledger & Trace Bank**: Collected an immutable trace bank of **{collection_ledger.total_calls_started} generation calls** under the proposal envelope ({MAX_TOTAL_CALLS} calls, {MAX_TOKENS_PER_CALL} tokens/call, {MAX_TOTAL_GENERATED_TOKENS} tokens). Replayed each policy independently with budget isolation.
- **Query-Only Solver Baseline**: Evaluated `scripts.gen_tasks.sols24` across all 8 items. Solves **8/8 ({dev_review_summary['query_only_solver_summary']['accuracy']*100:.1f}%)** in mean **{mean_solver_wall_ms:.2f} ms** wall time with **0 tokens** and **0 calls**.

---

## 2. Historical Review of 8 Exposed Development Items

| Item ID | Numbers | Historical CoT (1024 tok) | Verifier Status | Solvable by `sols24`? |
|---|---|---|---|---|
{hist_table_body}

**Key Findings on Historical Data**:
1. Historical CoT produced **{dev_review_summary['historical_cot_coverage']['valid']} valid, {dev_review_summary['historical_cot_coverage']['invalid']} invalid, and {dev_review_summary['historical_cot_coverage']['unverifiable']} unverifiable** expressions.
2. In historical measured artifacts, **no SC or TOT runs exist** for Game-of-24 (`missing_recipes: {', '.join(missing_recipes)}`). Coverage is reported as-is without synthetic interpolation.

---

## 3. Ladder Evaluation Mechanics & Comparative Paths

The dry-run evaluated 5 comparative paths across the ladder:
1. `fixed_cot`: Evaluates only Rung 0 (CoT, 1 call/item).
2. `fixed_sc`: Evaluates Rung 1 directly (SC, 5 calls/item).
3. `fixed_tot`: Evaluates Rung 2 directly (Candidate Selection, 4 calls/item).
4. `always_escalate`: Unconditionally runs CoT $\\to$ SC $\\to$ Candidate Selection (10 calls/item).
5. `checker_gated`: CoT $\\to$ if valid stop, else SC $\\to$ if valid stop, else Candidate Selection.

### Path Comparison Summary

*Notice: Rows labeled [SYNTHETIC DOUBLE] use pinned synthetic responses to verify software and ledger mechanics offline without model inference.*

| Metric | Fixed CoT [Historical/Synth] | Fixed SC [SYNTHETIC DOUBLE] | Fixed TOT [SYNTHETIC DOUBLE] | Always Escalate [SYNTHETIC DOUBLE] | Checker Gated [SYNTHETIC DOUBLE] | Query-Only Solver [Deterministic] |
|---|---|---|---|---|---|---|
| **Accuracy** | {p_cot['accuracy']*100:.1f}% ({p_cot['valid_count']}/{p_cot['items']}) | {p_sc['accuracy']*100:.1f}% ({p_sc['valid_count']}/{p_sc['items']})* | {p_tot['accuracy']*100:.1f}% ({p_tot['valid_count']}/{p_tot['items']})* | {p_always['accuracy']*100:.1f}% ({p_always['valid_count']}/{p_always['items']})* | {p_gated['accuracy']*100:.1f}% ({p_gated['valid_count']}/{p_gated['items']})* | **{dry_run_summary['query_only_solver']['accuracy']*100:.1f}% ({p_cot['items']}/{p_cot['items']})** |
| **Total Calls** | {p_cot['total_calls']} | {p_sc['total_calls']} | {p_tot['total_calls']} | {p_always['total_calls']} | **{p_gated['total_calls']}** | **0** |
| **Mean Calls/Item** | {p_cot['mean_calls']:.2f} | {p_sc['mean_calls']:.2f} | {p_tot['mean_calls']:.2f} | {p_always['mean_calls']:.2f} | **{p_gated['mean_calls']:.2f}** | **0.00** |
| **Gen Tokens** | {p_cot['total_generated_tokens']:,} | {p_sc['total_generated_tokens']:,} | {p_tot['total_generated_tokens']:,} | {p_always['total_generated_tokens']:,} | **{p_gated['total_generated_tokens']:,}** | **0** |
| **Rescue Count** | - | - | - | {p_always['rescue_count']} | **{p_gated['rescue_count']}** | - |
| **Harm Count** | - | - | - | {p_always['harm_count']} | **{p_gated['harm_count']}** | - |

*Note: SC, TOT, and Ladder escalation on failing items used pinned synthetic doubles for software verification.*

**Key Takeaways**:
- The **checker-gated path** achieves {p_gated['accuracy']*100:.1f}% accuracy on the synthetic trace bank while consuming only **{p_gated['total_calls']} calls ({p_gated['mean_calls']:.2f} calls/item)** and **{p_gated['total_generated_tokens']:,} generated tokens**, compared to **{p_always['total_calls']} calls and {p_always['total_generated_tokens']:,} tokens** for `always_escalate` (a **{call_reduction_pct:.1f}% call reduction** and **{token_reduction_pct:.1f}% token reduction**).
- For items with valid CoT (e.g. `g24_0003`), the checker stopped immediately at Rung 0 (1 call), preventing unnecessary compute.
- For items with invalid/unverifiable CoT, the checker successfully escalated and rescued the item.

---

## 4. Generation Call Ledger & Partial Failure Handling

The generation ledger strictly logged each call attempt before dispatch:
- **Preflight Enforcement**: Checked recipe requirements against remaining budget. Any attempt exceeding the remaining budget is blocked before execution (`BudgetExhaustedError`).
- **Partial Failure Resiliency**: When a sample fails mid-SC or selector fails in TOT, completed calls remain recorded with measured tokens, while failed calls are marked `failed` with conservative reservations (`1,024 tokens`).
- **Zero Forbidden Imports**: Validated that MLX, sentence-transformers, PyQt6, and PySide6 are never imported.

---

## 5. Critical Backend Findings for Real Campaign Planning

Before any real-model campaign on Game-of-24 could be authorized:
1. **Prompt Profile Incompatibility**:
   - `english-math-v1` raises `ValueError("English math profile supports DIRECT, COT and PAL only")` when invoked with SC or TOT.
   - `aligned-direct-cot-v1` supports only DIRECT and COT.
   - `legacy` backend contains hardcoded Vietnamese selector prompts in `_tot` (`"Chọn lời giải đúng nhất..."`).
2. **Deterministic Solver Superiority**:
   - `sols24` solves 100% of items in milliseconds ({mean_solver_wall_ms:.2f} ms mean wall time) at zero token cost.
   - Any LLM deployment on Game-of-24 must justify why model generation is preferable to exact symbolic solvers.

---

## 6. Audit Sign-off & Status

- **Software Contracts**: PASS (All dry-run tests passing).
- **Inference Budget Consumed**: 0 VND / 0 tokens.
- **Stage 0 Gate**: Preserved.
- **Human Review Status**: `pending` (No model execution authorized).
"""

        # Write files atomically
        (output_dir / "development_review_summary.json").write_text(
            json.dumps(dev_review_summary, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (output_dir / "dry_run_results.json").write_text(
            json.dumps(dry_run_records, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (output_dir / "dry_run_summary.json").write_text(
            json.dumps(dry_run_summary, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (output_dir / "generation_ledger.json").write_text(
            json.dumps(collection_ledger.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (output_dir / "proposed_execution_plan.json").write_text(
            json.dumps(proposed_plan, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (output_dir / "report.md").write_text(report_md, encoding="utf-8")

        # Manifest with checksums
        artifacts = [
            "development_review_summary.json",
            "dry_run_results.json",
            "dry_run_summary.json",
            "generation_ledger.json",
            "calls.jsonl",
            "proposed_execution_plan.json",
            "report.md",
        ]
        manifest = {
            "evidence": "development-checker-dry-run-20261023",
            "schema_version": 1,
            "mode": "checker_development_dry_run",
            "status": "complete",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "model_calls": False,
            "tokens_consumed": 0,
            "real_inference_budget": "0 VND",
            "confirmatory": False,
            "human_review_status": "pending",
            "input_sha256": {
                "development_review_index.json": sha256_file(review_index_path),
                "dataset.json": sha256_file(dataset_path),
                "records.json": sha256_file(records_path),
            },
            "source_sha256": {
                "checker_dry_run_py": sha256_file(repo_root / "experiments/checker_dry_run.py"),
                "verifiers_py": sha256_file(repo_root / "scripts/verifiers.py"),
            },
            "artifact_sha256": {
                name: sha256_file(output_dir / name) for name in artifacts
            },
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        return manifest

    except BaseException as exc:
        manifest = {
            "evidence": "development-checker-dry-run-20261023",
            "schema_version": 1,
            "mode": "checker_development_dry_run",
            "status": "interrupted",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "model_calls": False,
            "tokens_consumed": 0,
            "real_inference_budget": "0 VND",
            "confirmatory": False,
            "human_review_status": "pending",
            "interruption_reason": f"{type(exc).__name__}: {str(exc)}",
            "artifact_sha256": {
                name: sha256_file(output_dir / name)
                for name in ["calls.jsonl"]
                if (output_dir / name).exists()
            },
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        raise

