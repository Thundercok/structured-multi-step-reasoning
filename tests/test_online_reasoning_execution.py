"""Tests for OnlineReasoningController execution contracts, budget accounting,
cooperative cancellation, deadline timeouts, and worker integration in RAT.
"""
from pathlib import Path
import time
from typing import Any, Callable, List, Optional, Tuple
import numpy as np
import pytest
from PyQt6.QtCore import QCoreApplication

from reasoning.bundle import create_synthetic_specimen_bundle
from reasoning.reasoning_env import LLMBackend, ReasoningAction as A
from reasoning.runtime import (
    BackendExecutionError,
    ExecutionCostLedger,
    OnlineReasoningController,
    OnlineReasoningResult,
    StrategyObservation,
)
from rat.engine.meta_reasoner import MetaReasonerEngine, build_composed_meta_reasoner
from rat.ui.reasoning_worker import OnlineReasoningWorker


class ControllableCancelBackend:
    """Controllable backend double supporting cooperative cancellation during prefill and decode."""
    hidden_size = 2

    def __init__(
        self,
        *,
        prefill_delay_s: float = 0.0,
        decode_delay_s: float = 0.0,
        cancel_check_fn: Optional[Callable[[], bool]] = None,
        fail_on_strategy: Optional[A] = None,
        sc_samples: int = 5,
        tot_branches: int = 3,
    ):
        self.prefill_delay_s = prefill_delay_s
        self.decode_delay_s = decode_delay_s
        self.cancel_check_fn = cancel_check_fn
        self.fail_on_strategy = fail_on_strategy
        self.sc_samples = sc_samples
        self.tot_branches = tot_branches
        self.dispatched_calls: List[Tuple[A, str]] = []
        self.last_trace: dict = {"generations": []}

    def embed(self, query: str) -> np.ndarray:
        return np.zeros(self.hidden_size, dtype=np.float32)

    def run(self, strategy: A, query: str) -> Tuple[str, float, int]:
        self.dispatched_calls.append((strategy, query))

        # Check cooperative cancel during prefill
        if self.cancel_check_fn and self.cancel_check_fn():
            raise RuntimeError("Cancelled during prefill phase")
        if self.prefill_delay_s > 0:
            time.sleep(self.prefill_delay_s)
            if self.cancel_check_fn and self.cancel_check_fn():
                raise RuntimeError("Cancelled during prefill delay")

        if self.fail_on_strategy == strategy:
            raise RuntimeError(f"Simulated failure on strategy {strategy.name}")

        # Check cooperative cancel during decode
        if self.decode_delay_s > 0:
            time.sleep(self.decode_delay_s)
            if self.cancel_check_fn and self.cancel_check_fn():
                raise RuntimeError("Cancelled during decode phase")

        # Record underlying generation subcalls
        if strategy == A.SELF_CONSISTENCY:
            n_gen = self.sc_samples
        elif strategy == A.TOT:
            n_gen = self.tot_branches + 1
        else:
            n_gen = 1
        self.last_trace = {"generations": [{}] * n_gen}

        return f"answer-{strategy.name}", 0.3, 100 * n_gen


def test_multi_call_budget_accounting_counts_all_subcalls():
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    backend = ControllableCancelBackend(sc_samples=5, tot_branches=3)

    controller = OnlineReasoningController(
        backend, policy, bundle=bundle, allow_synthetic_bundle=True,
    )

    # Ladder query with raw 0.3 confidence will escalate COT -> SC -> TOT
    res = controller.solve("query needing deep ladder")
    assert res.status == "completed"
    assert len(res.observations) == 3

    obs_cot, obs_sc, obs_tot = res.observations
    assert obs_cot.underlying_requests == 1
    assert obs_sc.underlying_requests == 5
    assert obs_tot.underlying_requests == 4

    assert res.cost_ledger is not None
    assert res.cost_ledger.strategy_invocations == 3
    # Total underlying requests: 1 (COT) + 5 (SC) + 4 (TOT) = 10 requests
    assert res.cost_ledger.underlying_requests_dispatched == 10
    assert res.cost_ledger.underlying_requests_succeeded == 10
    assert res.cost_ledger.underlying_requests_failed == 0
    assert res.cost_ledger.all_requests_succeeded


def test_budget_limit_halts_ladder_and_charges_dispatched():
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    backend = ControllableCancelBackend(sc_samples=5)

    controller = OnlineReasoningController(
        backend, policy, bundle=bundle, allow_synthetic_bundle=True,
        max_strategy_invocations=1,  # Only allow 1 strategy on ladder
    )

    res = controller.solve("query needing deep ladder")
    assert res.status == "budget_exceeded"
    assert len(res.observations) == 1
    assert res.observations[0].strategy == A.COT
    assert res.cost_ledger.strategy_invocations == 1


def test_cooperative_cancellation_between_ladder_rungs():
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    backend = ControllableCancelBackend()
    controller = OnlineReasoningController(
        backend, policy, bundle=bundle, allow_synthetic_bundle=True,
    )

    cancel_flag = False
    def is_cancelled():
        return cancel_flag

    # Trigger cancellation after COT completes
    def on_step(obs):
        nonlocal cancel_flag
        if obs.strategy == A.COT:
            cancel_flag = True

    res = controller.solve("query ladder", is_cancelled=is_cancelled, on_step=on_step)
    assert res.status == "cancelled"
    assert len(res.observations) == 1
    assert res.observations[0].strategy == A.COT
    assert len(backend.dispatched_calls) == 1  # SC and TOT were never dispatched!


def test_deadline_timeout_halts_before_next_strategy():
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    backend = ControllableCancelBackend(decode_delay_s=0.05)
    controller = OnlineReasoningController(
        backend, policy, bundle=bundle, allow_synthetic_bundle=True,
    )

    # Set deadline very tight so it expires after first strategy
    deadline = time.monotonic() + 0.04
    res = controller.solve("query ladder", deadline_monotonic=deadline)
    assert res.status == "timeout"
    assert len(res.observations) <= 1


def test_backend_failure_is_charged_and_raises_without_canned_answer():
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    backend = ControllableCancelBackend(fail_on_strategy=A.COT)
    controller = OnlineReasoningController(
        backend, policy, bundle=bundle, allow_synthetic_bundle=True,
    )

    with pytest.raises(RuntimeError, match="Simulated failure on strategy COT"):
        controller.solve("query")


def test_qa_document_session_rejected_as_llm_backend():
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)

    class FakeDocumentSession:
        def chat_with_meta(self, messages, *args, **kwargs):
            return {"content": "excerpt response"}

    doc_session = FakeDocumentSession()
    # Must fail with TypeError because document session is NOT an LLMBackend
    with pytest.raises(TypeError, match="backend does not implement LLMBackend protocol"):
        OnlineReasoningController(doc_session, policy, bundle=bundle, allow_synthetic_bundle=True)


def test_worker_qthread_execution_and_signal_emission(tmp_path: Path):
    app = QCoreApplication.instance() or QCoreApplication([])
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    backend = ControllableCancelBackend()
    engine = build_composed_meta_reasoner(bundle, backend, policy, allow_synthetic=True)

    worker = OnlineReasoningWorker(
        engine,
        "tính 120 * 4",
        execution_id="exec-001",
        query_generation=1,
    )

    statuses: List[str] = []
    received_results: List[Any] = []

    worker.status_changed.connect(statuses.append)
    worker.response_ready.connect(received_results.append)

    worker.start()
    worker.wait(5000)
    app.processEvents()

    assert "working" in statuses
    assert "done" in statuses
    assert len(received_results) == 1
    res = received_results[0]
    assert res.execution_mode == "online_policy"
    assert res.execution_id == "exec-001"
    assert res.query_generation == 1


def test_worker_missing_selected_document_returns_unresolved_without_inheriting_pass(tmp_path: Path):
    app = QCoreApplication.instance() or QCoreApplication([])
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    backend = ControllableCancelBackend()
    engine = build_composed_meta_reasoner(bundle, backend, policy, allow_synthetic=True)

    missing_doc = str(tmp_path / "nonexistent.txt")
    worker = OnlineReasoningWorker(
        engine,
        "What is in the document?",
        document_path=missing_doc,
        execution_id="exec-doc-002",
        query_generation=2,
    )

    statuses: List[str] = []
    results: List[Any] = []
    worker.status_changed.connect(statuses.append)
    worker.response_ready.connect(results.append)

    worker.start()
    worker.wait(5000)
    app.processEvents()

    assert "error" in statuses
    assert len(results) == 1
    res = results[0]
    assert res.status == "unresolved"
    assert res.confidence_kind == "not_estimated"
    assert res.verification_status == "unverified"
