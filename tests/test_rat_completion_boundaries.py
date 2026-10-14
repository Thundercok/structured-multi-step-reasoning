"""Completion contract regressions. Native clients are mocks, not model evidence."""
import json
from unittest.mock import MagicMock

import pytest

from rat.engine.assistant_runtime import AssistantRuntime, ModelDecision
from rat.engine.completion import ExecutionJournal, OutcomeSpec, TurnContract, reconcile_turn
from rat.kernel.contracts import Artifact
from rat.timetable.compositor import TimetableCompositor


def runtime():
    return AssistantRuntime(db=MagicMock(), compositor=TimetableCompositor([]), use_live_model=False)


def action(name, **args):
    return ModelDecision("", tool_name=name, tool_args=args)


def run_choices(rt, contract, choices):
    sequence = iter(choices)
    def choose(goal, trajectory):
        item = next(sequence)
        return item() if callable(item) else item
    rt.model_callable = choose
    return rt.run("Thực hiện các mục tiêu đã khai", contract=contract, max_steps=6)


def bound_contract(outcomes):
    return TurnContract(conversation_id="c", turn_id="t", execution_id="e", generation=2, outcomes=outcomes)


def test_frozen_nested_expected_args_can_serialize_to_json():
    args = {"text": "126", "source_result": {"artifact_id": "a", "revision": 1, "field": "result"}}
    contract = bound_contract([OutcomeSpec("save", kind="registered_effect", effect_type="record_work_note", expected_args=args)])
    contract.freeze()
    exported = json.loads(json.dumps(contract.to_dict()))
    assert exported["outcomes"][0]["expected_args"] == args


def test_actual_selection_array_matches_frozen_expected_array():
    rt = runtime()
    rt.artifact_store.put(Artifact("a", "sample", payload={"result": "126"}))
    contract = TurnContract(outcomes=[OutcomeSpec("select", kind="registered_effect", effect_type="select_work_results", expected_args={"artifact_ids": ["a"]})])
    response = run_choices(rt, contract, [action("select_work_results", artifact_ids=["a"]), ModelDecision("", final_answer="Đã chọn")])
    assert rt.notebook.result_ids() == ["a"]
    assert response.reconciliation.declared_scope_completion == "satisfied"


@pytest.mark.parametrize("actual,expected_satisfied", [("(18 * 7)", True), ("63 * 2", False)])
def test_calculation_matches_requested_expression_not_only_its_value(actual, expected_satisfied):
    rt = runtime()
    contract = TurnContract(outcomes=[OutcomeSpec("calc", kind="registered_effect", effect_type="calculate", expected_args={"expression": "18 * 7"}, required_proof_scope="calculation_execution")])
    response = run_choices(rt, contract, [action("calculate", expression=actual), ModelDecision("", final_answer="126")])
    assert response.artifacts[0].payload["result"] == "126"
    assert (response.reconciliation.declared_scope_completion == "satisfied") is expected_satisfied


@pytest.mark.parametrize("correct_source", [True, False])
def test_generic_consumer_must_read_declared_producer_result(correct_source):
    rt = runtime()
    rt.artifact_store.put(Artifact("unrelated", "sample", payload={"result": "999"}))
    contract = TurnContract(outcomes=[
        OutcomeSpec("calc", kind="registered_effect", effect_type="calculate", expected_args={"expression": "18 * 7"}),
        OutcomeSpec("read", kind="registered_effect", effect_type="inspect_artifact", source_ref={"producer_outcome_id": "calc"}, dependency_ids=["calc"]),
    ])
    def inspect():
        produced = rt.artifact_store.list("calculation")[-1]
        return action("inspect_artifact", artifact_id=produced.id if correct_source else "unrelated", revision=1)
    response = run_choices(rt, contract, [action("calculate", expression="18 * 7"), inspect, ModelDecision("", final_answer="Đã đọc")])
    assert response.steps[1].tool_result["result"] == ("126" if correct_source else "999")
    assert (response.reconciliation.declared_scope_completion == "satisfied") is correct_source


@pytest.mark.parametrize("expected_text", ["162", "126"])
def test_note_operation_respects_typed_expected_text(expected_text):
    rt = runtime()
    rt.artifact_store.put(Artifact("source", "sample", payload={"result": "162"}))
    contract = TurnContract(outcomes=[OutcomeSpec("save", kind="registered_effect", effect_type="record_work_note", expected_args={"text": expected_text})])
    response = run_choices(rt, contract, [action("record_work_note", text="162", source_result={"artifact_id": "source", "revision": 1, "field": "result"}), ModelDecision("", final_answer="Đã ghi")])
    assert rt.notebook.snapshot()[0]["text"] == "162"
    assert rt.notebook.snapshot()[0]["confirmed"]
    assert (response.reconciliation.declared_scope_completion == "satisfied") is (expected_text == "162")


@pytest.mark.parametrize("proof_status", [None, "UNKNOWN", "FAIL", "PASS"])
def test_response_respects_explicit_required_proof(proof_status):
    contract = bound_contract([OutcomeSpec("answer", kind="response", required_proof_scope="literal_arithmetic_answer")])
    contract.freeze()
    journal = ExecutionJournal("c", "t", "e", 2)
    if proof_status:
        journal.record_verification({"status": proof_status, "scope": "literal_arithmetic_answer", "authority": "runtime_verifier", "evidence_ids": ["final-answer"]})
    result = reconcile_turn(contract, journal, final_answer="126")
    assert (result.declared_scope_completion == "satisfied") is (proof_status == "PASS")


@pytest.mark.parametrize("proof_generation", [2, 1])
def test_calculation_proof_from_foreign_generation_cannot_satisfy_contract(proof_generation):
    contract = bound_contract([OutcomeSpec("calc", kind="registered_effect", effect_type="calculate", expected_args={"expression": "18 * 7"}, required_proof_scope="calculation_execution")])
    contract.freeze()
    journal = ExecutionJournal("c", "t", "e", 2)
    operation = journal.record_operation("calculate", {"expression": "18 * 7"}, {"result": "126"}, artifact_refs=[{"id": "a", "revision": 1}])
    proof = journal.record_verification({"status": "PASS", "scope": "calculation_execution", "authority": "runtime_verifier"}, operation_receipt_id=operation.receipt_id)
    proof.generation = proof_generation
    result = reconcile_turn(contract, journal, final_answer="126")
    assert (result.declared_scope_completion == "satisfied") is (proof_generation == 2)


def test_native_malformed_source_reference_returns_invalid_without_crashing():
    client = MagicMock()
    client.chat_with_meta.side_effect = [
        {"message": {"contract": {"outcomes": [{"outcome_id": "save", "kind": "registered_effect", "effect_type": "record_work_note", "source_ref": "not-an-object"}]}, "tool_calls": [{"function": {"name": "record_work_note", "arguments": {"text": "126", "source_result": {"artifact_id": "source", "revision": 1, "field": "result"}}}}]}, "prompt_tokens": 1, "completion_tokens": 1},
        {"message": {"content": "Đã ghi"}, "prompt_tokens": 1, "completion_tokens": 1},
    ]
    rt = AssistantRuntime(db=MagicMock(), compositor=TimetableCompositor([]), use_live_model=True, model_client=client)
    rt.artifact_store.put(Artifact("source", "sample", payload={"result": "126"}))
    response = rt.run("Ghi kết quả vào note")
    assert response.reconciliation.intent_coverage == "invalid"
    assert response.reconciliation.declared_scope_completion != "satisfied"


def test_native_explicit_empty_contract_stays_unchecked_or_unresolved():
    client = MagicMock()
    client.chat_with_meta.return_value = {"message": {"content": json.dumps({"contract": {"outcomes": []}, "answer": "Xin chào"})}, "prompt_tokens": 1, "completion_tokens": 1}
    rt = AssistantRuntime(db=MagicMock(), compositor=TimetableCompositor([]), use_live_model=True, model_client=client)
    response = rt.run("Chào")
    assert response.reconciliation.declared_scope_completion != "satisfied"
    # ADR-003 permits unchecked/invalid when coverage is not established.
    # An explicit empty contract must not falsely claim satisfaction.
    assert response.reconciliation.intent_coverage in ("unchecked", "invalid") or "empty_contract" in response.reconciliation.unresolved_reasons


def test_planner_schema_advertises_typed_expected_args():
    client = MagicMock()
    client.chat_with_meta.return_value = {"message": {"content": "{}"}}
    rt = AssistantRuntime(db=MagicMock(), compositor=TimetableCompositor([]), use_live_model=True, plan_tasks=True, model_client=client)
    rt._plan_task("Tính 18 * 7")
    schema = client.chat_with_meta.call_args.kwargs["response_format"]
    assert schema["properties"]["outcomes"]["items"]["properties"]["expected_args"]["type"] == "object"


@pytest.mark.parametrize("entry", ["provided", "initial_decision", "planner"])
@pytest.mark.parametrize("field,value", [("source_ref", "bad"), ("target_ref", ["bad"]), ("expected_args", "bad")])
def test_malformed_nested_fields_are_invalid_at_all_contract_ingress(entry, field, value):
    proposal = {"outcomes": [{"outcome_id": "reply", "kind": "response", field: value}]}
    rt = runtime()
    if entry == "provided":
        response = run_choices(rt, proposal, [ModelDecision("", final_answer="Đã trả lời")])
    elif entry == "initial_decision":
        response = rt.run("Chào", initial_decision=ModelDecision("", final_answer="Đã trả lời", contract=proposal))
    else:
        plan = {"goal": "Trả lời", "constraints": [], "success_criteria": [], "known_facts": [],
                "completed": [], "remaining": ["Trả lời"], "status": "in_progress", **proposal}
        client = MagicMock()
        client.chat_with_meta.side_effect = [
            {"message": {"content": json.dumps(plan)}, "prompt_tokens": 1, "completion_tokens": 1},
            {"message": {"content": "Đã trả lời"}, "prompt_tokens": 1, "completion_tokens": 1},
        ]
        rt = AssistantRuntime(db=MagicMock(), compositor=TimetableCompositor([]), use_live_model=True, plan_tasks=True, model_client=client)
        response = rt.run("Chào")
    assert response.reconciliation.intent_coverage == "invalid"
    assert response.reconciliation.declared_scope_completion != "satisfied"
    assert any(field in reason for reason in response.turn_contract.validation_errors)


@pytest.mark.parametrize("checked_answer", ["126", "162"])
def test_response_proof_is_bound_to_actual_final_candidate(checked_answer):
    contract = bound_contract([OutcomeSpec("answer", required_proof_scope="literal_arithmetic_answer")])
    journal = ExecutionJournal("c", "t", "e", 2)
    journal.record_verification({"status": "PASS", "scope": "literal_arithmetic_answer"}, candidate_answer=checked_answer)
    result = reconcile_turn(contract, journal, final_answer="126")
    assert (result.declared_scope_completion == "satisfied") is (checked_answer == "126")


def test_latest_recheck_of_same_candidate_can_satisfy_required_proof():
    contract = bound_contract([OutcomeSpec("answer", required_proof_scope="literal_arithmetic_answer")])
    journal = ExecutionJournal("c", "t", "e", 2)
    for status in ("UNKNOWN", "PASS"):
        journal.record_verification({"status": status, "scope": "literal_arithmetic_answer"}, candidate_answer="126")
    assert reconcile_turn(contract, journal, final_answer="126").declared_scope_completion == "satisfied"


@pytest.mark.parametrize("planner", [False, True])
def test_native_mock_final_check_emits_candidate_bound_proof(planner):
    client = MagicMock()
    proposal = {"outcomes": [{"outcome_id": "reply", "kind": "response", "required_proof_scope": "literal_arithmetic_answer"}]}
    final = {"message": {"content": json.dumps({"answer": "126", **({} if planner else proposal)})}, "prompt_tokens": 1, "completion_tokens": 1}
    if planner:
        plan = {"goal": "Tính 18 * 7", "constraints": [], "success_criteria": [], "known_facts": [],
                "completed": [], "remaining": ["Tính"], "status": "in_progress", **proposal}
        client.chat_with_meta.side_effect = [{"message": {"content": json.dumps(plan)}, "prompt_tokens": 1, "completion_tokens": 1}, final]
    else:
        client.chat_with_meta.return_value = final
    rt = AssistantRuntime(db=MagicMock(), compositor=TimetableCompositor([]), use_live_model=True, plan_tasks=planner, model_client=client)
    response = rt.run("Tính 18 * 7")
    assert response.answer == "126"
    assert response.reconciliation.declared_scope_completion == "satisfied"
    proof = next(r for r in response.execution_journal.receipts if r.issuer == "verification")
    assert proof.evidence_hash is not None
    assert proof.generation == response.turn_contract.generation


def test_frozen_contract_can_be_rebound_without_mutating_original():
    contract = bound_contract([OutcomeSpec("reply", expected_args={"nested": {"values": [1, 2]}})])
    contract.freeze()
    before = contract.to_dict()
    response = run_choices(runtime(), contract, [ModelDecision("", final_answer="Xin chào")])
    assert response.reconciliation.declared_scope_completion == "satisfied"
    assert contract.to_dict() == before
    assert response.turn_contract.execution_id != contract.execution_id
