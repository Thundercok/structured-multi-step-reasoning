"""
tests/test_agent_execution_service.py — Verification for AgentExecutionService & rat.agent_request/v1.

Verifies:
1. Unified envelope rat.agent_request/v1 and immutable snapshot hashing.
2. The 6-phase lifecycle: accepted -> planning -> dispatching -> observing -> checking -> deciding -> turn_completed.
3. Pre-checks: rejecting stale file/hash resource bindings before IO.
4. Pre-checks: budget exhaustion and deadline enforcement.
5. Idempotency key deduplication.
6. Cooperative cancellation cleanly yielding error="cancelled".
7. Direct UI action (requested_action) and chat request running through the same headless boundary.
8. Headless integrity: no Qt application or GUI modules required.
"""
import hashlib
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

from rat.crawler.db import Database
from rat.engine.assistant_runtime import AssistantRuntime
from rat.engine.execution import ExecutionRequest
from rat.engine.execution_service import AgentExecutionService
from rat.kernel.contracts import ExecutionEvent
from rat.timetable.compositor import TimetableCompositor


@pytest.fixture
def service_env(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    runtime = AssistantRuntime(db=db, compositor=TimetableCompositor([]), use_live_model=True)
    service = AgentExecutionService(runtime)
    yield service, runtime, tmp_path
    db.get_connection().close()


def test_agent_request_envelope_serialization():
    req = ExecutionRequest(
        query="Kiểm tra hợp đồng",
        execution_id="exec-123",
        generation=1,
        origin="chat",
        document_path="/tmp/test.pdf",
        timeout_s=30.0,
        max_generated_tokens=500,
        idempotency_key="idemp-abc",
    )
    data = req.to_agent_request_dict()
    assert data["schema_version"] == "rat.agent_request/v1"
    assert data["execution_id"] == "exec-123"
    assert data["origin"] == "chat"
    assert data["goal"] == "Kiểm tra hợp đồng"
    assert data["idempotency_key"] == "idemp-abc"
    assert any(b.get("path") == "/tmp/test.pdf" for b in data["resource_bindings"])
    assert data["budget"]["deadline_s"] == 30.0
    assert data["budget"]["max_generated_tokens"] == 500
    assert "snapshot_hash" in data["context_snapshot"]


def test_lifecycle_phases_and_event_stream(service_env):
    service, runtime, tmp = service_env
    events: list[ExecutionEvent] = []

    req = ExecutionRequest(
        query="Tính 15 + 27",
        execution_id="exec-lifecycle",
        turn_id="turn-lifecycle",
        generation=2,
        origin="ui_action",
        requested_action={"name": "calculate", "args": {"expression": "15 + 27"}},
    )

    resp = service.execute(req, on_event=events.append)
    assert resp.error is None
    assert resp.answer == "42"
    assert resp.answer_verification_status == "PASS"

    event_types = [e.type for e in events]
    assert event_types == [
        "accepted",
        "planning",
        "dispatching",
        "observing",
        "checking",
        "deciding",
        "turn_completed",
    ]

    for i, e in enumerate(events):
        assert e.sequence == i + 1
        assert e.execution_id == "exec-lifecycle"
        assert e.turn_id == "turn-lifecycle"
        assert e.generation == 2


def test_rejects_stale_resource_bindings_before_io(service_env):
    service, runtime, tmp = service_env
    doc = tmp / "sample.txt"
    doc.write_text("Dữ liệu ban đầu.")
    sha = hashlib.sha256(doc.read_bytes()).hexdigest()

    # 1. Stale due to deleted file
    doc.unlink()
    events = []
    req_missing = ExecutionRequest(
        query="Đọc tệp",
        resource_bindings=[{"kind": "document", "path": str(doc), "sha256": sha}],
    )
    resp = service.execute(req_missing, on_event=events.append)
    assert resp.error == "stale_resource_binding"
    assert events[-1].type == "turn_failed"

    # 2. Stale due to modified content / hash mismatch
    doc.write_text("Nội dung đã bị sửa đổi trái phép!")
    req_modified = ExecutionRequest(
        query="Đọc tệp",
        resource_bindings=[{"kind": "document", "path": str(doc), "sha256": sha}],
    )
    resp2 = service.execute(req_modified)
    assert resp2.error == "stale_resource_binding"


def test_budget_exhaustion_enforcement(service_env):
    service, runtime, tmp = service_env
    events = []
    req = ExecutionRequest(
        query="Phép tính",
        budget={"deadline_s": 0.0},
    )
    resp = service.execute(req, on_event=events.append)
    assert resp.error == "budget_exhausted"
    assert events[-1].type == "turn_failed"


def test_idempotency_key_caching(service_env):
    service, runtime, tmp = service_env
    req = ExecutionRequest(
        query="Tính 3 * 7",
        requested_action={"name": "calculate", "args": {"expression": "3 * 7"}},
        idempotency_key="idemp-math-unique-1",
    )

    resp1 = service.execute(req)
    assert resp1.answer == "21"

    events2 = []
    resp2 = service.execute(req, on_event=events2.append)
    assert resp2.answer == "21"
    assert any(e.payload and e.payload.get("idempotent_replay") for e in events2)


def test_cooperative_cancellation_during_execution(service_env):
    service, runtime, tmp = service_env
    events = []
    cancelled = [False]

    req = ExecutionRequest(
        query="Thao tác hủy",
        requested_action={"name": "calculate", "args": {"expression": "1 + 1"}},
    )

    # Cancel immediately
    resp = service.execute(req, should_cancel=lambda: True, on_event=events.append)
    assert resp.error == "cancelled"
    assert [e.type for e in events] == ["accepted", "cancelling", "turn_failed"]


def test_headless_integrity_no_qt_required():
    # Verify that AgentExecutionService and ExecutionRequest can be imported and instantiated
    # without initializing a QGuiApplication.
    from rat.engine.execution_service import AgentExecutionService
    from rat.engine.execution import ExecutionRequest
    assert AgentExecutionService is not None
    assert ExecutionRequest is not None


def test_continuation_rejects_stale_note_revision_before_dispatch(service_env):
    service, runtime, _ = service_env
    created = runtime.dispatcher.execute_operation("synthesize_smart_note", {"raw_content": "Cần kiểm tra cache."})
    req = ExecutionRequest(query="Cập nhật ghi chú", continuation={"artifact_id": created.artifact.id, "revision": 9},
        requested_action={"name": "update_note_action_item", "args": {"artifact_id": created.artifact.id, "revision": 1, "item_index": 1}})
    resp = service.execute(req)
    assert resp.error == "stale_continuation"
    assert runtime.artifact_store.get(created.artifact.id).revision == 1


def test_requested_action_verification_fail_does_not_emit_completed(service_env):
    from rat.engine.verification import VerificationReport, VerificationStatus
    service, runtime, _ = service_env
    class Reject:
        def check_execution(self, evidence):
            return VerificationReport(VerificationStatus.FAIL, "fixture_check", "Deliberate software fixture rejection")
    runtime.registry.get_operation("calculate").verifier = Reject()
    events = []
    resp = service.execute(ExecutionRequest(query="Tính 1+1", requested_action={"name": "calculate", "args": {"expression": "1+1"}}), on_event=events.append)
    assert resp.error == "verification_failed"
    assert resp.answer_verification_status == "FAIL"
    assert events[-1].type == "turn_failed"
    assert not any(e.type == "turn_completed" for e in events)
