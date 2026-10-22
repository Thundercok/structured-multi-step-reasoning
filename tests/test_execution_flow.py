"""Desktop dispatch through real workers and synthetic fitted policy; zero inference."""
from types import SimpleNamespace
from unittest.mock import Mock
import subprocess
import sys

import numpy as np
import pytest
from PyQt6.QtCore import QThread
from PyQt6.QtTest import QSignalSpy
from PyQt6.QtWidgets import QApplication

from rat.engine.assistant_runtime import AgentResponse
from rat.engine.execution import ExecutionRequest, execution_response
from rat.engine.meta_reasoner import build_composed_meta_reasoner
from rat.ui.assistant_worker import AssistantWorker, create_execution_worker
from rat.ui.reasoning_worker import OnlineReasoningWorker
from reasoning.bundle import create_synthetic_specimen_bundle


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def collect(app, worker, signal="response_ready"):
    spy = QSignalSpy(getattr(worker, signal))
    worker.start()
    assert spy or spy.wait(5000), "worker did not deliver a response"
    assert worker.wait(5000)
    app.processEvents()
    return spy[0][0]


def runtime():
    return SimpleNamespace(run=Mock(return_value=AgentResponse("fixture", [], 0, 0, 0)),
                           db=SimpleNamespace(_local=SimpleNamespace(conn=None)))


class Backend:
    hidden_size = 2

    def __init__(self):
        self.calls = []

    def embed(self, query):
        self.calls.append(("embed", QThread.currentThread()))
        return np.zeros(2)

    def run(self, strategy, query):
        self.calls.append((strategy.name, QThread.currentThread()))
        return "synthetic answer", .9, 7


def composed():
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    backend = Backend()
    return build_composed_meta_reasoner(bundle, backend, policy, allow_synthetic=True), backend


def test_assistant_request_keeps_identity_and_runs_off_gui(app):
    target = runtime()
    caller = []
    def answer(*args, **kwargs):
        caller.append(QThread.currentThread())
        return AgentResponse("fixture", [], 0, 0, 0)
    target.run.side_effect = answer
    request = ExecutionRequest("hello", "exec-a", 3, SimpleNamespace(turn_id="turn-a"),
                               context={"history": [{"role": "user", "content": "prior"}]})
    worker = create_execution_worker(target, request)
    response = collect(app, worker)
    assert isinstance(worker, AssistantWorker)
    assert response.execution_id == "exec-a" and response.turn_id == "turn-a"
    assert caller[0] is not app.thread()
    assert target.run.call_args.kwargs["execution_id"] == "exec-a"
    assert target.run.call_args.kwargs["history"] == request.context["history"]


def test_composed_policy_uses_existing_reasoning_worker_and_preserves_cost(app):
    engine, backend = composed()
    request = ExecutionRequest("giải thích fixture", "exec-r", 4,
                               SimpleNamespace(turn_id="turn-r"), lane="reasoning")
    target = runtime()
    worker = create_execution_worker(target, request, reasoning_engine=engine, allow_synthetic_policy=True)
    assert isinstance(worker, OnlineReasoningWorker)
    result = collect(app, worker)
    response = execution_response(request, result)
    assert backend.calls and all(thread is not app.thread() for _, thread in backend.calls)
    assert result.execution_id == response.execution_id == "exec-r"
    assert result.query_generation == 4
    assert response.answer == "synthetic answer"
    assert response.qa_telemetry["cost_ledger"] == result.cost_ledger
    assert response.completion_status == "unchecked"
    assert response.answer_verification_status == "UNKNOWN"
    assert response.steps == []
    target.run.assert_not_called()


def test_production_rejects_synthetic_policy_without_dispatch(app):
    engine, backend = composed()
    target = runtime()
    worker = create_execution_worker(target, ExecutionRequest("fixture", lane="reasoning"), reasoning_engine=engine)
    result = collect(app, worker)
    assert result.error.startswith("reasoning_policy_unavailable")
    assert backend.calls == []
    target.run.assert_not_called()


def test_zero_budget_reaches_controller_without_embedding_or_generation(app):
    engine, backend = composed()
    request = ExecutionRequest("fixture", "exec-zero", 2, lane="reasoning", max_generated_tokens=0)
    worker = create_execution_worker(runtime(), request, reasoning_engine=engine, allow_synthetic_policy=True)
    response = execution_response(request, collect(app, worker))
    assert response.error == "budget_exceeded"
    assert backend.calls == []
    assert response.qa_telemetry["cost_ledger"]["underlying_requests_dispatched"] == 0


def test_document_selection_takes_precedence_over_reasoning(app, monkeypatch):
    from rat.engine import selected_document_qa
    target = runtime()
    answer = Mock(return_value=AgentResponse("document fixture", [], 0, 0, 0))
    monkeypatch.setattr(selected_document_qa, "answer_selected_document", answer)
    engine = Mock()
    request = ExecutionRequest("giải thích fixture", "exec-doc", 2,
                               document_path="/synthetic/document.txt")
    worker = create_execution_worker(target, request, reasoning_engine=engine)
    response = collect(app, worker)
    assert response.answer == "document fixture" and response.execution_id == "exec-doc"
    engine.is_reasoning_query.assert_not_called()
    target.run.assert_not_called()
    assert answer.call_args.args[2] == request.document_path


def test_pre_cancelled_request_does_not_call_runtime(app):
    target = runtime()
    worker = create_execution_worker(target, ExecutionRequest("fixture", "exec-stop"))
    worker.isInterruptionRequested = lambda: True
    result = collect(app, worker)
    assert result.error == "cancelled" and result.execution_id == "exec-stop"
    target.run.assert_not_called()


def test_direct_operation_reuses_artifact_worker(app):
    from rat.kernel.contracts import DispatchResult
    action = Mock(return_value=DispatchResult("success", result={"observed": True}))
    request = ExecutionRequest("explicit action", generation=6, lane="operation")
    worker = create_execution_worker(runtime(), request, operation=action)
    result = collect(app, worker, "result_ready")
    assert result.status == "success" and result.result["observed"]
    assert worker.execution_request is request
    action.assert_called_once_with()


def test_regular_worker_import_does_not_load_strategy_stack():
    result = subprocess.run([sys.executable, '-c', '''
import sys
import rat.ui.assistant_worker
assert 'rat.engine.meta_reasoner' not in sys.modules
assert 'rat.ui.reasoning_worker' not in sys.modules
assert not any(name in sys.modules for name in ('mlx', 'mlx_lm', 'fastembed'))
'''], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_wrong_execution_result_cannot_be_relabelled_as_current():
    request = ExecutionRequest("current", "exec-current", 4)
    response = AgentResponse("stale content", [], 0, 0, 0, execution_id="exec-old")
    accepted = execution_response(request, response)
    assert accepted.error == "stale_execution_result" and not accepted.answer


def test_unsupported_control_is_rejected_instead_of_ignored(app):
    target = runtime()
    worker = create_execution_worker(target, ExecutionRequest("assistant", max_generated_tokens=0))
    result = collect(app, worker)
    assert result.error == "unsupported_execution_controls"
    target.run.assert_not_called()
