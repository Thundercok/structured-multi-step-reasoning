"""Desktop dispatch through real workers; zero inference."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import QThread
from PyQt6.QtTest import QSignalSpy
from PyQt6.QtGui import QGuiApplication

from rat.engine.assistant_runtime import AgentResponse
from rat.engine.execution import ExecutionRequest, execution_response
from rat.ui.assistant_worker import AssistantWorker, create_execution_worker


@pytest.fixture(scope="module")
def app():
    return QGuiApplication.instance() or QGuiApplication([])


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


def test_document_selection_goes_to_document_qa(app, monkeypatch):
    from rat.engine import selected_document_qa
    target = runtime()
    answer = Mock(return_value=AgentResponse("document fixture", [], 0, 0, 0))
    monkeypatch.setattr(selected_document_qa, "answer_selected_document", answer)
    request = ExecutionRequest("giải thích fixture", "exec-doc", 2,
                               document_path="/synthetic/document.txt")
    worker = create_execution_worker(target, request)
    response = collect(app, worker)
    assert response.answer == "document fixture" and response.execution_id == "exec-doc"
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
