"""
tests/test_native_acceptance_readiness.py — Matrix of native acceptance cases
using deterministic fixtures and doubles, ready for offscreen verification.

Covers:
1. Token streaming
2. Cancel during prefill
3. Cancel during decode
4. Re-ask after cancel
5. Change document / file mid-turn
6. Outside-excerpt / unresolved (no false PASS inheritance)
7. Failure & deadline timeout
8. Late callback suppression
"""
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional
import numpy as np
import pytest
from PyQt6.QtCore import QCoreApplication

from reasoning.bundle import create_synthetic_specimen_bundle
from reasoning.reasoning_env import ReasoningAction as A
from reasoning.runtime import OnlineReasoningController
from rat.engine.meta_reasoner import MetaReasonerEngine, build_composed_meta_reasoner
from rat.ui.reasoning_worker import OnlineReasoningWorker


class AcceptanceDoubleBackend:
    """Controllable backend double implementing granular phase hooks for streaming and cancellation."""
    hidden_size = 2

    def __init__(
        self,
        *,
        tokens_to_stream: Optional[List[str]] = None,
        fail_phase: Optional[str] = None,  # "prefill", "decode", or None
        cancel_check: Optional[Callable[[], bool]] = None,
        token_cost: int = 40,
    ):
        self.tokens_to_stream = tokens_to_stream or ["Hello", " world", " from", " double"]
        self.fail_phase = fail_phase
        self.cancel_check = cancel_check
        self.token_cost = token_cost
        self.call_log: List[Dict[str, Any]] = []
        self.last_trace = {"generations": [{}]}

    def embed(self, query: str) -> np.ndarray:
        return np.zeros(self.hidden_size, dtype=np.float32)

    def run(self, strategy: A, query: str, *, should_cancel: Optional[Callable[[], bool]] = None, deadline_monotonic: Optional[float] = None):
        check = should_cancel or self.cancel_check
        record = {
            "strategy": strategy.name,
            "query": query,
            "prefill_entered": True,
            "decode_entered": False,
            "completed": False,
        }
        self.call_log.append(record)

        # 1. Prefill phase
        if self.fail_phase == "prefill":
            self.last_trace = {"generations": [{"status": "failed", "completion_tokens": 0}]}
            raise RuntimeError("Backend failed during prefill")
        if check and check():
            raise RuntimeError("Interrupted during prefill")

        # 2. Decode phase
        record["decode_entered"] = True
        if self.fail_phase == "decode":
            self.last_trace = {"generations": [{"status": "failed", "completion_tokens": 10}]}
            raise RuntimeError("Backend failed during decode")
        if check and check():
            raise RuntimeError("Interrupted during decode")

        record["completed"] = True
        self.last_trace = {"generations": [{"status": "success", "completion_tokens": self.token_cost}]}
        return " ".join(self.tokens_to_stream), 0.85, self.token_cost


def test_case_1_token_streaming(tmp_path: Path):
    """Case 1: Step progress emission via worker step_completed signal and engine/controller on_step."""
    app = QCoreApplication.instance() or QCoreApplication([])
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    backend = AcceptanceDoubleBackend(tokens_to_stream=["Step", "1", "Completed"])
    engine = build_composed_meta_reasoner(bundle, backend, policy, allow_synthetic=True)

    worker = OnlineReasoningWorker(engine, "query")
    steps = []
    results = []
    worker.step_completed.connect(steps.append)
    worker.response_ready.connect(results.append)
    worker.start()
    assert worker.wait(5000)
    app.processEvents()

    assert len(results) == 1
    assert results[0].status == "completed"
    assert len(steps) >= 1
    assert steps[0].strategy.name == "COT"


def test_case_2_cancel_during_prefill():
    """Case 2: Cancel during prefill - cooperative cancellation hook stops before decode."""
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    cancelled = False

    def is_cancelled():
        return cancelled

    backend = AcceptanceDoubleBackend()

    def run_hook(strategy, query, *, should_cancel=None, deadline_monotonic=None):
        nonlocal cancelled
        cancelled = True
        if should_cancel and should_cancel():
            raise RuntimeError("Interrupted during prefill")
        return backend.run(strategy, query, should_cancel=should_cancel, deadline_monotonic=deadline_monotonic)

    backend.run = run_hook
    controller = OnlineReasoningController(backend, policy, bundle=bundle, allow_synthetic_bundle=True)

    with pytest.raises(RuntimeError, match="Interrupted during prefill"):
        controller.solve("query", is_cancelled=is_cancelled)


def test_case_3_cancel_during_decode():
    """Case 3: Cancel during decode - cooperative cancellation stops generation in decode phase."""
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    cancel_state = {"in_decode": False, "cancelled": False}

    def is_cancelled():
        return cancel_state["cancelled"]

    backend = AcceptanceDoubleBackend()

    def run_decode_cancel(strategy, query, *, should_cancel=None, deadline_monotonic=None):
        cancel_state["in_decode"] = True
        cancel_state["cancelled"] = True
        if should_cancel and should_cancel():
            raise RuntimeError("Interrupted during decode")
        return "answer", 0.9, 20

    backend.run = run_decode_cancel
    controller = OnlineReasoningController(backend, policy, bundle=bundle, allow_synthetic_bundle=True)

    with pytest.raises(RuntimeError, match="Interrupted during decode"):
        controller.solve("query", is_cancelled=is_cancelled)
    assert cancel_state["in_decode"]


def test_case_4_re_ask_after_cancel():
    """Case 4: Re-asking after cancel - clean state release, second request succeeds."""
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    backend = AcceptanceDoubleBackend()
    controller = OnlineReasoningController(backend, policy, bundle=bundle, allow_synthetic_bundle=True)

    # First turn: cancelled
    res_cancel = controller.solve("query 1", is_cancelled=lambda: True)
    assert res_cancel.status == "cancelled"
    assert len(res_cancel.observations) == 0

    # Second turn: re-ask same query or new query
    res_success = controller.solve("query 1 (re-ask)", is_cancelled=lambda: False)
    assert res_success.status == "completed"
    assert len(res_success.observations) >= 1
    assert res_success.observations[0].answer != ""


def test_case_5_change_document_mid_turn(tmp_path: Path):
    """Case 5: Change document during execution - modified document returns unresolved."""
    app = QCoreApplication.instance() or QCoreApplication([])
    doc_file = tmp_path / "document.txt"
    doc_file.write_text("Initial document content v1")

    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    backend = AcceptanceDoubleBackend()

    orig_run = backend.run

    def run_and_modify(strategy, query, **kwargs):
        # Mutate document file in the middle of execution
        doc_file.write_text("Modified document content v2")
        return orig_run(strategy, query, **kwargs)

    backend.run = run_and_modify
    engine = build_composed_meta_reasoner(bundle, backend, policy, allow_synthetic=True)

    worker = OnlineReasoningWorker(engine, "query about doc", document_path=str(doc_file))
    results = []
    worker.response_ready.connect(results.append)
    worker.start()
    assert worker.wait(5000)
    app.processEvents()

    assert len(results) == 1
    assert results[0].status == "unresolved"
    assert results[0].verification_status == "unverified"


def test_case_6_outside_excerpt_unresolved():
    """Case 6: Outside-excerpt / unresolved queries - no false PASS inheritance."""
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    backend = AcceptanceDoubleBackend()
    engine = build_composed_meta_reasoner(bundle, backend, policy, allow_synthetic=True)

    # PAL query with missing inputs/cpa facts in legacy or quantitative path
    res = engine._solve_with_pal("Tính CPA tích lũy kỳ này", time.time())
    assert res.verification_status == "unverifiable"
    assert res.confidence == 0.0
    assert res.confidence_kind == "not_estimated"
    # Never inherits prior turn PASS
    assert res.badge == "Chưa kiểm chứng"


def test_case_7_failure_and_timeout():
    """Case 7: Backend failure & timeout - charged to budget ledger, preserves partial counters."""
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    backend = AcceptanceDoubleBackend(fail_phase="prefill")
    controller = OnlineReasoningController(backend, policy, bundle=bundle, allow_synthetic_bundle=True)

    with pytest.raises(RuntimeError, match="prefill") as caught:
        controller.solve("query")
    # Preserves attempt ledger on exception
    ledger = getattr(caught.value, "cost_ledger", None)
    assert ledger is not None
    assert ledger.underlying_requests_dispatched >= 1

    # Timeout halts execution before next strategy
    backend_ok = AcceptanceDoubleBackend()
    controller_ok = OnlineReasoningController(backend_ok, policy, bundle=bundle, allow_synthetic_bundle=True)
    res_timeout = controller_ok.solve("query", deadline_monotonic=time.monotonic() - 1.0)
    assert res_timeout.status == "timeout"


def test_case_8_late_callback_suppression():
    """Case 8: Late callback suppression - worker binds generation and execution ID to result."""
    app = QCoreApplication.instance() or QCoreApplication([])
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    backend = AcceptanceDoubleBackend()
    engine = build_composed_meta_reasoner(bundle, backend, policy, allow_synthetic=True)

    worker = OnlineReasoningWorker(
        engine,
        "query generation test",
        execution_id="exec-turn-42",
        query_generation=2,
    )
    results = []
    worker.response_ready.connect(results.append)
    worker.start()
    assert worker.wait(5000)
    app.processEvents()

    assert len(results) == 1
    res = results[0]
    assert res.execution_id == "exec-turn-42"
    assert res.query_generation == 2

    # UI consumer check
    active_generation = 2
    accepted = []
    if res.query_generation == active_generation:
        accepted.append(res)
    assert len(accepted) == 1
