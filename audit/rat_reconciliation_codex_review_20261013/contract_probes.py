"""Independent offline contract probes. Expected failures reproduce review findings.
No model HTTP calls; do not treat these fixtures as model-quality evidence.
"""
import json
from unittest.mock import MagicMock
import pytest

from rat.engine.assistant_runtime import AssistantRuntime, ModelDecision
from rat.engine.completion import ExecutionJournal, OutcomeKind, OutcomeSpec, TurnContract, reconcile_turn
from rat.kernel.contracts import Artifact
from rat.timetable.compositor import TimetableCompositor
from rat.ui.chat_session import ConversationHistory


def runtime():
    return AssistantRuntime(db=MagicMock(), compositor=TimetableCompositor([]),
                            use_live_model=False, plan_tasks=False)


def action(name, **args):
    return ModelDecision("", tool_name=name, tool_args=args)


def run_choices(rt, choices, declared):
    items = iter(choices)
    def decide(goal, steps):
        item = next(items)
        return item() if callable(item) else item
    rt.model_callable = decide
    return rt.run("Thực hiện công việc đã khai", contract=declared, max_steps=6)


def standalone(outcomes):
    contract = TurnContract(conversation_id="conv", turn_id="turn", execution_id="exec",
                            generation=1, outcomes=outcomes)
    contract.freeze()
    return contract, ExecutionJournal("conv", "turn", "exec", 1)


def test_native_planner_schema_can_express_outcomes():
    client = MagicMock()
    rt = AssistantRuntime(db=MagicMock(), compositor=TimetableCompositor([]),
                          use_live_model=True, plan_tasks=True, model_client=client)
    rt._plan_task("Ghi lại kết quả")
    schema = client.chat_with_meta.call_args.kwargs["response_format"]
    assert "outcomes" in schema["properties"], "Native planning schema excludes the declared contract"


def test_native_planner_outcomes_are_not_rejected_as_task_state():
    plan = {"goal": "Ghi kết quả", "constraints": [], "success_criteria": ["Có note"],
            "known_facts": [], "completed": [], "remaining": ["Ghi note"], "status": "in_progress",
            "outcomes": [{"outcome_id": "save", "kind": "registered_effect", "effect_type": "record_work_note"}]}
    client = MagicMock()
    client.chat_with_meta.side_effect = [
        {"message": {"content": json.dumps(plan)}, "prompt_tokens": 1, "completion_tokens": 1},
        {"message": {"content": "Đã ghi"}, "prompt_tokens": 1, "completion_tokens": 1},
    ]
    rt = AssistantRuntime(db=MagicMock(), compositor=TimetableCompositor([]),
                          use_live_model=True, plan_tasks=True, model_client=client)
    result = rt.run("Ghi lại kết quả")
    assert result.error is None, result.error
    assert result.reconciliation.intent_coverage == "model_proposed"
    assert any(item["outcome_id"] == "save" for item in result.reconciliation.unmet_outcomes)


def test_correct_producer_consumer_source_satisfies_contract():
    rt = runtime()
    declared = TurnContract(outcomes=[
        OutcomeSpec("calc", kind=OutcomeKind.REGISTERED_EFFECT, effect_type="calculate"),
        OutcomeSpec("save", kind=OutcomeKind.REGISTERED_EFFECT, effect_type="record_work_note",
                    source_ref={"producer_outcome_id": "calc"}, dependency_ids=["calc"]),
    ])
    def save_result():
        source = rt.artifact_store.list("calculation")[-1]
        return action("record_work_note", text="126", source_result={
            "artifact_id": source.id, "revision": source.revision, "field": "result"})
    result = run_choices(rt, [action("calculate", expression="18 * 7"), save_result,
                             ModelDecision("", final_answer="Đã ghi 126")], declared)
    assert result.note_events[0]["snapshot"]["source_ref"]["artifact_id"] == result.artifacts[0].id
    assert result.reconciliation.declared_scope_completion == "satisfied", result.reconciliation.to_dict()


def test_freeze_prevents_mutating_existing_outcome():
    declared = TurnContract(outcomes=[OutcomeSpec("save", kind=OutcomeKind.REGISTERED_EFFECT,
                                                effect_type="record_work_note")])
    declared.freeze()
    with pytest.raises((RuntimeError, AttributeError, TypeError)):
        declared.outcomes[0].allow_proposal = True


def test_freeze_prevents_deleting_obligations():
    declared = TurnContract(outcomes=[OutcomeSpec("save", kind=OutcomeKind.REGISTERED_EFFECT,
                                                effect_type="record_work_note")])
    declared.freeze()
    with pytest.raises((RuntimeError, AttributeError, TypeError)):
        declared.outcomes.clear()


def test_journal_snapshots_args_and_result_at_commit():
    journal = ExecutionJournal("conv", "turn", "exec", 1)
    args, result = {"expression": "18 * 7"}, {"result": "126"}
    receipt = journal.record_operation("calculate", args, result)
    args["expression"], result["result"] = "18 * 9", "162"
    assert receipt.operation_args == {"expression": "18 * 7"}
    assert receipt.operation_result == {"result": "126"}


@pytest.mark.parametrize("raw", [
    {"outcomes": [], "intent_coverage": "model_proposed"},
    {"schema_version": "unsupported", "outcomes": [{"outcome_id": "response", "kind": "response"}]},
    {"outcomes": [{"outcome_id": "invalid", "kind": "invented_kind"}]},
])
def test_empty_or_invalid_contract_cannot_be_satisfied(raw):
    rt = runtime()
    result = run_choices(rt, [ModelDecision("", final_answer="Đã làm")], raw)
    assert result.reconciliation.declared_scope_completion != "satisfied", result.reconciliation.to_dict()


def test_missing_declared_response_cannot_be_satisfied_with_successful_effect():
    contract, journal = standalone([
        OutcomeSpec("read", kind=OutcomeKind.REGISTERED_EFFECT, effect_type="inspect_artifact"),
        OutcomeSpec("response", kind=OutcomeKind.RESPONSE),
    ])
    journal.record_operation("inspect_artifact", {"artifact_id": "a", "revision": 1}, {"payload": {"x": 1}})
    result = reconcile_turn(contract, journal, lifecycle="completed", final_answer="")
    assert any(item["reason"] == "missing_response" for item in result.unmet_outcomes)
    assert result.declared_scope_completion != "satisfied", result.to_dict()


def test_generic_effect_must_match_target_revision():
    contract, journal = standalone([
        OutcomeSpec("read", kind=OutcomeKind.REGISTERED_EFFECT, effect_type="inspect_artifact",
                    target_ref={"artifact_id": "requested", "revision": 2})
    ])
    journal.record_operation("inspect_artifact", {"artifact_id": "other", "revision": 1}, {"payload": {"x": 1}})
    result = reconcile_turn(contract, journal, lifecycle="completed", final_answer="Đã đọc")
    assert result.declared_scope_completion != "satisfied", result.to_dict()


def test_generic_effect_cannot_skip_a_required_proof():
    contract, journal = standalone([
        OutcomeSpec("read", kind=OutcomeKind.REGISTERED_EFFECT, effect_type="inspect_artifact",
                    required_proof_scope="requested_scope")
    ])
    journal.record_operation("inspect_artifact", {"artifact_id": "a", "revision": 1}, {"payload": {"x": 1}})
    result = reconcile_turn(contract, journal, lifecycle="completed", final_answer="Đã đọc")
    assert result.declared_scope_completion != "satisfied", result.to_dict()


def test_one_calculation_cannot_satisfy_two_distinct_producers():
    contract, journal = standalone([
        OutcomeSpec("left", kind=OutcomeKind.REGISTERED_EFFECT, effect_type="calculate", description="18 * 7"),
        OutcomeSpec("right", kind=OutcomeKind.REGISTERED_EFFECT, effect_type="calculate", description="18 * 9"),
    ])
    journal.record_operation("calculate", {"expression": "18 * 7"}, {"result": "126"},
                             artifact_refs=[{"id": "first", "revision": 1}])
    result = reconcile_turn(contract, journal, lifecycle="completed", final_answer="Đã tính cả hai")
    assert result.declared_scope_completion != "satisfied", result.to_dict()


def test_calculation_proof_must_belong_to_matched_receipt():
    contract, journal = standalone([
        OutcomeSpec("calc", kind=OutcomeKind.REGISTERED_EFFECT, effect_type="calculate",
                    required_proof_scope="calculation_execution")
    ])
    first = journal.record_operation("calculate", {"expression": "18 * 7"}, {"expression": "18 * 7", "result": "999"})
    journal.record_verification({"status": "FAIL", "scope": "calculation_execution", "evidence_ids": ["first"]},
                                operation_receipt_id=first.receipt_id)
    journal.record_verification({"status": "PASS", "scope": "calculation_execution", "evidence_ids": ["unrelated"]},
                                operation_receipt_id="unrelated-call")
    result = reconcile_turn(contract, journal, lifecycle="completed", final_answer="Đã tính")
    assert result.declared_scope_completion != "satisfied", result.to_dict()


def test_unknown_dependency_cannot_be_silently_satisfied():
    contract, journal = standalone([
        OutcomeSpec("read", kind=OutcomeKind.REGISTERED_EFFECT, effect_type="inspect_artifact",
                    dependency_ids=["nonexistent"])
    ])
    journal.record_operation("inspect_artifact", {"artifact_id": "a", "revision": 1}, {"payload": {"x": 1}})
    result = reconcile_turn(contract, journal, lifecycle="completed", final_answer="Đã đọc")
    assert result.declared_scope_completion != "satisfied", result.to_dict()


def test_receipt_scope_must_match_conversation_turn_and_generation():
    contract, journal = standalone([
        OutcomeSpec("read", kind=OutcomeKind.REGISTERED_EFFECT, effect_type="inspect_artifact")
    ])
    receipt = journal.record_operation("inspect_artifact", {"artifact_id": "a", "revision": 1}, {"payload": {"x": 1}})
    receipt.conversation_id, receipt.turn_id, receipt.generation = "another-conversation", "old-turn", 0
    result = reconcile_turn(contract, journal, lifecycle="completed", final_answer="Đã đọc")
    assert result.declared_scope_completion != "satisfied", result.to_dict()


def test_terminal_note_revision_cannot_reuse_an_earlier_confirmed_version():
    rt = runtime()
    rt.artifact_store.put(Artifact("source", "sample", payload={"result": "126"}))
    ref = {"artifact_id": "source", "revision": 1, "field": "result"}
    declared = TurnContract(outcomes=[
        OutcomeSpec("save", kind=OutcomeKind.REGISTERED_EFFECT, effect_type="record_work_note",
                    source_ref={"artifact_id": "source", "revision": 1}, allow_proposal=False)
    ])
    def replace_with_proposal():
        note = rt.notebook.snapshot()[0]
        return action("record_work_note", text="999", source_result=ref,
                      replace_note_id=note["id"], revision=note["revision"])
    result = run_choices(rt, [action("record_work_note", text="126", source_result=ref),
                             replace_with_proposal, ModelDecision("", final_answer="Đã ghi")], declared)
    assert rt.notebook.snapshot()[0]["revision"] == 2 and not rt.notebook.snapshot()[0]["confirmed"]
    assert result.reconciliation.declared_scope_completion != "satisfied", result.reconciliation.to_dict()


def test_cancel_after_commit_retains_matched_effect_in_reconciliation():
    rt = runtime()
    declared = TurnContract(outcomes=[
        OutcomeSpec("calc", kind=OutcomeKind.REGISTERED_EFFECT, effect_type="calculate"),
        OutcomeSpec("save", kind=OutcomeKind.REGISTERED_EFFECT, effect_type="record_work_note"),
    ])
    cancelled = {"value": False}
    choices = iter([action("calculate", expression="18 * 7")])
    rt.model_callable = lambda goal, steps: next(choices)
    def after_step(step):
        if step.tool_name == "calculate":
            cancelled["value"] = True
    result = rt.run("Tính rồi ghi", contract=declared, should_cancel=lambda: cancelled["value"], on_step=after_step)
    assert result.error == "cancelled" and result.artifacts[0].payload["result"] == "126"
    assert result.reconciliation.matched_receipts, result.reconciliation.to_dict()
    assert not any(item["outcome_id"] == "calc" for item in result.reconciliation.unmet_outcomes)


def test_returned_response_preserves_authoritative_journal_and_contract_for_audit():
    rt = runtime()
    declared = TurnContract(outcomes=[OutcomeSpec("response", kind=OutcomeKind.RESPONSE)])
    result = run_choices(rt, [ModelDecision("", final_answer="Xin chào")], declared)
    assert getattr(result, "execution_journal", None) is not None
    assert getattr(result, "turn_contract", None) is not None
