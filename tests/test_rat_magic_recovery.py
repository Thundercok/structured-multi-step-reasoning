"""Recovery contracts on scripted model replies and temporary data; no inference."""
import json
from unittest.mock import Mock

import pytest

from rat.crawler.db import Database
from rat.engine.assistant_runtime import AgentStep, AssistantRuntime
from rat.engine.completion import ExecutionJournal, TurnContract, reconcile_turn
from rat.engine.runtime_context import collect_runtime_context
from rat.kernel.contracts import Artifact
from rat.timetable.compositor import TimetableCompositor


@pytest.fixture
def runtime(tmp_path):
    db = Database(str(tmp_path / "fixture-index.db"))
    obj = AssistantRuntime(db=db, compositor=TimetableCompositor([]), use_live_model=True,
                           plan_tasks=True, model_client=Mock())
    yield obj
    db.get_connection().close()


def reply(content="", *, operation=None, args=None):
    message = {"role": "assistant", "content": content}
    if operation:
        message["tool_calls"] = [{"function": {"name": operation, "arguments": args or {}}}]
    return {"message": message}


def plan(*operations):
    return reply(json.dumps({"outcomes": [
        *({"outcome_id": f"effect-{i}", "kind": "registered_effect", "effect_type": operation}
          for i, operation in enumerate(operations)),
        {"outcome_id": "reply", "kind": "response"},
    ]}))


def tool_names(call):
    return {tool["function"]["name"] for tool in call.args[1]}


def test_accepted_answer_repair_reopens_tools_for_the_unfinished_source_bound_note(runtime):
    replies = iter([
        plan("calculate", "record_work_note"),
        reply(operation="calculate", args={"expression": "18 * 7"}),
        reply("125"),
        reply('{"answer":"126"}'),
    ])
    count = 0
    def scripted(*args, **kwargs):
        nonlocal count
        count += 1
        if count <= 4:
            return next(replies)
        if count == 5:
            actual = runtime.artifact_store.find_by_kind("calculation")[0]
            return reply(operation="record_work_note", args={
                "text": actual.payload["result"],
                "source_result": {"artifact_id": actual.id, "revision": actual.revision, "field": "result"},
            })
        return reply("126")
    runtime.model_client.chat_with_meta.side_effect = scripted
    result = runtime.run("Tính 18 * 7 rồi ghi lại kết quả đó.", max_steps=6)
    calls = runtime.model_client.chat_with_meta.call_args_list
    assert calls[3].kwargs.get("response_format") and calls[3].args[1] == []
    assert not calls[4].kwargs.get("response_format")
    assert "record_work_note" in tool_names(calls[4])
    assert result.error is None and result.answer == "126"
    assert result.reconciliation.declared_scope_completion == "satisfied"
    notes = runtime.notebook.snapshot()
    assert len(notes) == 1 and notes[0]["confirmed"] is True
    operations = [r.operation_name for r in result.execution_journal.receipts if r.issuer == "dispatcher"]
    assert operations == ["calculate", "record_work_note"]


def seed_pending(runtime):
    result = runtime.dispatcher.execute_operation(
        "create_natal_chart", {}, context={"execution_id": "fixture-seed", "turn_id": "fixture-seed-turn"})
    assert result.status == "needs_input"
    request = runtime.dispatcher.state.pending_input_request
    assert request is not None and runtime.artifact_store.get(request.id) is not None
    return request


def test_explicit_model_dismissal_uses_observed_id_and_retains_unrelated_results(runtime):
    retained = Artifact("fixture-retained", "sample", payload={"result": "keep this"})
    runtime.artifact_store.put(retained)
    pending = seed_pending(runtime)
    runtime.model_client.chat_with_meta.side_effect = [
        plan("dismiss_pending_input", "calculate"),
        reply(operation="dismiss_pending_input", args={"request_id": pending.id}),
        reply(operation="calculate", args={"expression": "18 * 7"}),
        reply("126"),
    ]
    result = runtime.run("Bỏ việc lập lá số đi. Tính 18 * 7.", max_steps=5)
    first_actor = runtime.model_client.chat_with_meta.call_args_list[1]
    assert "dismiss_pending_input" in tool_names(first_actor)
    # The ID was available as canonical observed data before the scripted choice.
    snapshots = [m["content"] for m in first_actor.args[0]
                 if m.get("content", "").startswith(("Runtime context snapshot", "Work context"))]
    assert snapshots and pending.id in snapshots[0]
    assert result.error is None and result.answer == "126"
    assert result.pending_input_request is None and result.completion_status == "satisfied"
    assert result.turn_reference["status"] == "completed"
    assert runtime.dispatcher.state.pending_input_request is None
    assert runtime.artifact_store.get(pending.id) is None
    assert runtime.artifact_store.get(retained.id).to_dict() == retained.to_dict()
    receipt = next(r for r in result.execution_journal.receipts if r.operation_name == "dismiss_pending_input")
    assert receipt.committed and receipt.operation_args == {"request_id": pending.id}
    assert receipt.operation_result == {"dismissed": True, "request_id": pending.id,
                                        "operation_name": "create_natal_chart"}


def test_unknown_and_cancelled_dismissal_cannot_remove_the_actual_pending_request(runtime):
    pending = seed_pending(runtime)
    unknown = runtime.dispatcher.execute_operation(
        "dismiss_pending_input", {"request_id": "fixture-not-the-request"},
        context={"execution_id": "fixture-attempt"})
    assert unknown.status == "error"
    assert runtime.dispatcher.state.pending_input_request.id == pending.id
    assert runtime.artifact_store.get(pending.id) is not None
    runtime.dispatcher.cancel_execution("fixture-cancelled")
    cancelled = runtime.dispatcher.execute_operation(
        "dismiss_pending_input", {"request_id": pending.id},
        context={"execution_id": "fixture-cancelled"})
    assert cancelled.status == "cancelled"
    assert runtime.dispatcher.state.pending_input_request.id == pending.id
    assert runtime.artifact_store.get(pending.id) is not None
    # Also exercise the dispatcher API itself, rather than only its registered wrapper.
    dismissed = runtime.dispatcher.dismiss_input(pending.id, context={"execution_id": "fixture-valid"})
    assert dismissed == {"dismissed": True, "request_id": pending.id,
                          "operation_name": "create_natal_chart"}
    assert runtime.dispatcher.state.pending_input_request is None


def test_discovery_enables_only_subsequent_schemas_without_read_or_delivery_evidence(runtime):
    runtime.model_client.chat_with_meta.side_effect = [
        plan(),
        reply(operation="request_operation_tools", args={"operation_names": ["read_document", "deliver_document"]}),
        reply("Đã tìm được schema công cụ; chưa đọc hoặc gửi tệp."),
    ]
    result = runtime.run("Xem những công cụ cần cho việc này.", max_steps=3)
    calls = runtime.model_client.chat_with_meta.call_args_list
    initial = tool_names(calls[1])
    assert initial == {"search_documents", "inspect_artifact", "request_operation_tools"}
    after = tool_names(calls[2])
    assert {"read_document", "deliver_document"} <= after
    assert "update_task_state" not in after
    receipts = [r for r in result.execution_journal.receipts if r.issuer == "dispatcher"]
    assert [r.operation_name for r in receipts] == ["request_operation_tools"]
    assert receipts[0].operation_result == {"operation_names": ["read_document", "deliver_document"], "available": True}
    assert not any(a.kind in ("document_content", "document_file") for a in result.artifacts)
    # Metadata access cannot satisfy actual document effects, even with a fluent answer.
    contract = TurnContract.from_dict({"outcomes": [
        {"outcome_id": "read", "kind": "registered_effect", "effect_type": "read_document"},
        {"outcome_id": "deliver", "kind": "registered_effect", "effect_type": "deliver_document"},
    ]})
    journal = result.execution_journal
    contract.conversation_id, contract.turn_id = journal.conversation_id, journal.turn_id
    contract.execution_id, contract.generation = journal.execution_id, journal.generation
    contract.freeze()
    checked = reconcile_turn(contract, journal, final_answer=result.answer, store=runtime.artifact_store,
                             notebook_snapshot=runtime.notebook.snapshot())
    assert {o["outcome_id"] for o in checked.unmet_outcomes} == {"read", "deliver"}
    assert checked.declared_scope_completion == "unresolved"


def actor_snapshot(runtime):
    runtime.notebook.begin_request("fixture", execution_id="fixture-current")
    context = runtime.notebook.current_context()
    journal = ExecutionJournal(context.turn_ref.conversation_id, context.turn_ref.turn_id,
                               context.execution_id, runtime.notebook.generation)
    contract = TurnContract.from_dict({"outcomes": [{"outcome_id": "reply", "kind": "response"}]})
    contract.conversation_id, contract.turn_id = journal.conversation_id, journal.turn_id
    contract.execution_id, contract.generation = journal.execution_id, journal.generation
    return collect_runtime_context(
        view="actor", notebook=runtime.notebook, store=runtime.artifact_store,
        dispatcher=runtime.dispatcher, journal=journal, contract=contract, task_state={}, query="fixture")


@pytest.mark.parametrize("case", ["unexecuted", "failed", "unavailable", "foreign_execution", "document_lookalike"])
def test_only_successful_current_discovery_observations_can_enable_schemas(runtime, case):
    snapshot = actor_snapshot(runtime)
    step = AgentStep(1, "", tool_name="request_operation_tools",
                     tool_args={"operation_names": ["deliver_document"]},
                     tool_result={"operation_names": ["deliver_document"], "available": True},
                     execution_id="fixture-current")
    if case == "unexecuted":
        step.tool_result = None
    elif case == "failed":
        step.error = "fixture operation failed"
        step.tool_result["error"] = "fixture operation failed"
    elif case == "unavailable":
        step.tool_result["available"] = False
    elif case == "foreign_execution":
        step.execution_id = "fixture-previous-execution"
    else:
        step.tool_name = "read_document"
    runtime.model_client.chat_with_meta.return_value = reply("Fixture answer")
    runtime._call_model("fixture", [step], context_snapshot=snapshot)
    assert "deliver_document" not in tool_names(runtime.model_client.chat_with_meta.call_args)


def test_discovery_validates_names_caps_requests_and_deduplicates_metadata(runtime):
    result = runtime.dispatcher.execute_operation("request_operation_tools", {
        "operation_names": ["read_document", "read_document", "deliver_document"]})
    assert result.status == "success"
    assert result.result == {"operation_names": ["read_document", "deliver_document"], "available": True}
    assert result.artifact is None
    unknown = runtime.dispatcher.execute_operation("request_operation_tools", {
        "operation_names": ["fixture_unregistered_operation"]})
    assert unknown.status == "error"
    oversized = runtime.dispatcher.execute_operation("request_operation_tools", {
        "operation_names": ["read_document"] * 5})
    assert oversized.status == "error"


def test_legacy_unchecked_call_keeps_the_full_registered_catalog(runtime):
    runtime.plan_tasks = False
    runtime.model_client.chat_with_meta.return_value = reply("Fixture answer")
    runtime._call_model("fixture", [])
    assert tool_names(runtime.model_client.chat_with_meta.call_args) == {
        operation.name for operation in runtime.registry.list_operations()}
