"""Round-2 offline probes for remaining original R1/R3/R4/R5 requirements.
Native clients are mocks; source data and decisions are fixtures.
"""
import json
from unittest.mock import MagicMock
import pytest
from rat.engine.assistant_runtime import AssistantRuntime, ModelDecision
from rat.engine.completion import ExecutionJournal, OutcomeSpec, TurnContract, reconcile_turn
from rat.kernel.contracts import Artifact
from rat.timetable.compositor import TimetableCompositor


def fixture_runtime():
    return AssistantRuntime(db=MagicMock(), compositor=TimetableCompositor([]), use_live_model=False)


def action(name, **args):
    return ModelDecision("", tool_name=name, tool_args=args)


def run_choices(runtime, contract, choices):
    stream = iter(choices)
    def decision(goal, steps):
        next_item = next(stream)
        return next_item() if callable(next_item) else next_item
    runtime.model_callable = decision
    return runtime.run("Làm các mục tiêu đã khai", contract=contract, max_steps=6)


def test_note_cannot_satisfy_required_source_proof_when_no_proof_exists():
    rt = fixture_runtime()
    rt.artifact_store.put(Artifact("source", "sample", payload={"result": "126"}))
    ref = {"artifact_id": "source", "revision": 1, "field": "result"}
    contract = TurnContract(outcomes=[
        OutcomeSpec("save", kind="registered_effect", effect_type="record_work_note",
                    source_ref=ref, required_proof_scope="source_calculation_note")
    ])
    response = run_choices(rt, contract, [
        action("record_work_note", text="126", source_result=ref),
        ModelDecision("", final_answer="Đã ghi"),
    ])
    assert response.note_events[0]["snapshot"]["confirmed"]
    assert "source_verification" not in response.note_events[0]["snapshot"]
    assert response.reconciliation.declared_scope_completion != "satisfied"


def test_terminal_confirmed_note_must_still_match_required_source():
    rt = fixture_runtime()
    rt.artifact_store.put(Artifact("original", "sample", payload={"result": "126"}))
    rt.artifact_store.put(Artifact("other", "sample", payload={"result": "162"}))
    original = {"artifact_id": "original", "revision": 1, "field": "result"}
    other = {"artifact_id": "other", "revision": 1, "field": "result"}
    contract = TurnContract(outcomes=[
        OutcomeSpec("save", kind="registered_effect", effect_type="record_work_note", source_ref=original)
    ])
    def update_to_other_source():
        note = rt.notebook.snapshot()[0]
        return action("record_work_note", text="162", source_result=other,
                      replace_note_id=note["id"], revision=note["revision"])
    response = run_choices(rt, contract, [
        action("record_work_note", text="126", source_result=original),
        update_to_other_source, ModelDecision("", final_answer="Đã ghi"),
    ])
    latest = rt.notebook.snapshot()[0]
    assert latest["confirmed"] and latest["revision"] == 2
    assert latest["source_ref"]["artifact_id"] == "other"
    assert response.reconciliation.declared_scope_completion != "satisfied"


def test_wrong_expression_cannot_match_by_substring():
    rt = fixture_runtime()
    contract = TurnContract(outcomes=[
        OutcomeSpec("calc", kind="registered_effect", effect_type="calculate", description="18 * 7")
    ])
    response = run_choices(rt, contract, [
        action("calculate", expression="118 * 7"), ModelDecision("", final_answer="Đã tính"),
    ])
    assert response.artifacts[0].payload["result"] == "826"
    assert response.reconciliation.declared_scope_completion != "satisfied"


@pytest.mark.parametrize("order", ["producer_first", "consumer_first"])
def test_valid_producer_consumer_matching_is_independent_of_declaration_order(order):
    rt = fixture_runtime()
    producer = OutcomeSpec("calc", kind="registered_effect", effect_type="calculate")
    consumer = OutcomeSpec("save", kind="registered_effect", effect_type="record_work_note",
                           source_ref={"producer_outcome_id": "calc"}, dependency_ids=["calc"])
    contract = TurnContract(outcomes=[producer, consumer] if order == "producer_first" else [consumer, producer])
    def save_result():
        result = rt.artifact_store.list("calculation")[-1]
        return action("record_work_note", text="126", source_result={
            "artifact_id": result.id, "revision": result.revision, "field": "result"})
    response = run_choices(rt, contract, [
        action("calculate", expression="18 * 7"), save_result, ModelDecision("", final_answer="Đã ghi126"),
    ])
    assert response.reconciliation.declared_scope_completion == "satisfied"


def test_cyclic_dependencies_cannot_be_satisfied():
    contract = TurnContract(conversation_id="c", turn_id="t", execution_id="e", generation=1, outcomes=[
        OutcomeSpec("a", kind="registered_effect", effect_type="read_a", dependency_ids=["b"]),
        OutcomeSpec("b", kind="registered_effect", effect_type="read_b", dependency_ids=["a"]),
    ])
    journal = ExecutionJournal("c", "t", "e", 1)
    journal.record_operation("read_a", {}, {"result": "a"})
    journal.record_operation("read_b", {}, {"result": "b"})
    result = reconcile_turn(contract, journal, lifecycle="completed", final_answer="Đã đọc")
    assert result.declared_scope_completion != "satisfied"


@pytest.mark.parametrize("field", ["source_ref", "target_ref", "dependency_ids"])
def test_freeze_also_protects_nested_refs_and_dependencies(field):
    contract = TurnContract(outcomes=[
        OutcomeSpec("save", kind="registered_effect", effect_type="record_work_note",
                    source_ref={"artifact_id": "a", "revision": 1},
                    target_ref={"note_id": "n", "expected_revision": 1},
                    dependency_ids=["producer"]),
        OutcomeSpec("producer", kind="registered_effect", effect_type="calculate")
    ])
    contract.freeze()
    nested = getattr(contract.outcomes[0], field)
    with pytest.raises((RuntimeError, AttributeError, TypeError)):
        nested.clear()


def native_runtime(content, *, planner=False):
    client = MagicMock()
    client.chat_with_meta.return_value = {"message": {"content": content}, "prompt_tokens": 1, "completion_tokens": 1}
    return AssistantRuntime(db=MagicMock(), compositor=TimetableCompositor([]), use_live_model=True,
                            plan_tasks=planner, model_client=client)


def test_native_off_contract_envelope_is_not_user_facing_answer():
    rt = native_runtime(json.dumps({
        "outcomes": [{"outcome_id": "response", "kind": "response"}], "answer": "Xin chào"
    }))
    response = rt.run("Chào bạn")
    assert response.reconciliation.intent_coverage == "model_proposed"
    assert response.answer == "Xin chào"


def test_malformed_native_outcomes_return_invalid_result_instead_of_crashing():
    rt = native_runtime(json.dumps({"outcomes": ["malformed"], "answer": "Đã làm"}))
    response = rt.run("Làm giúp tôi")
    assert response.error or response.reconciliation.intent_coverage in ("invalid", "unchecked")
    assert response.reconciliation.declared_scope_completion != "satisfied"


def test_untrusted_frozen_contract_metadata_does_not_crash_runtime():
    rt = native_runtime(json.dumps({
        "contract": {"frozen": True, "outcomes": [{"outcome_id": "response", "kind": "response"}]},
        "answer": "Xin chào"
    }))
    response = rt.run("Chào bạn")
    assert response.error or response.reconciliation.declared_scope_completion != "unchecked"


def test_completion_status_does_not_fall_back_to_model_task_report():
    plan = {"goal": "Trả lời", "constraints": [], "success_criteria": [], "known_facts": [],
            "completed": [], "remaining": ["Trả lời"], "status": "in_progress"}
    client = MagicMock()
    client.chat_with_meta.side_effect = [
        {"message": {"content": json.dumps(plan)}, "prompt_tokens": 1, "completion_tokens": 1},
        {"message": {"content": "Xin chào"}, "prompt_tokens": 1, "completion_tokens": 1},
    ]
    rt = AssistantRuntime(db=MagicMock(), compositor=TimetableCompositor([]),
                          use_live_model=True, plan_tasks=True, model_client=client)
    response = rt.run("Chào bạn")
    assert response.reconciliation.intent_coverage == "unchecked"
    assert response.completion_status == response.reconciliation.declared_scope_completion


def test_correct_calculation_with_linked_pass_proof_is_satisfied():
    rt = fixture_runtime()
    contract = TurnContract(outcomes=[
        OutcomeSpec("calc", kind="registered_effect", effect_type="calculate",
                    required_proof_scope="calculation_execution")
    ])
    response = run_choices(rt, contract, [
        action("calculate", expression="18 * 7"), ModelDecision("", final_answer="Đã tính126"),
    ])
    assert response.verification_reports[0]["scope"] == "calculation_execution"
    assert response.verification_reports[0]["status"] == "PASS"
    receipts = response.execution_journal.receipts
    assert receipts[1].parent_receipt_ids == [receipts[0].receipt_id]
    assert response.reconciliation.declared_scope_completion == "satisfied"
