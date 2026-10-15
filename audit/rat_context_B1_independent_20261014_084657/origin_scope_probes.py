"""Independent post-round2 controls for typed origin and current-proof authority."""
import copy

import pytest

from rat.engine.completion import ExecutionJournal, ReceiptEnvelope
from rat.engine.context_snapshot import compile_context_snapshot, expand_value_refs, validate_context_snapshot
from rat.kernel.contracts import Artifact


def snapshot(**inputs):
    return compile_context_snapshot(
        view="actor", conversation_id="review-conv", turn_id="review-turn", execution_id="review-exec",
        generation=0, artifact_store_generation=0, note_event_cursor=0,
        current_query="Synthetic independent origin review", **inputs,
    )


def raw_ref(artifact_id="a"):
    return {"$value_ref": {"entity_ref": {"kind": "artifact", "conversation_id": "review-conv",
        "artifact_id": artifact_id, "revision": 1}, "pointer": "/payload/value"}}


@pytest.mark.parametrize("target_present", [True, False])
def test_unknown_result_root_literal_wrapper_stays_literal(target_present):
    literal = raw_ref("a" if target_present else "missing")
    journal = ExecutionJournal("review-conv", "review-turn", "review-exec", generation=0)
    journal.record_operation("unknown_plugin", {}, literal)
    snap = snapshot(execution_journal=journal,
        artifact_store_items=[Artifact("a", "fixture", payload={"value": "RAW_WAS_DECODED"})] if target_present else [])
    valid, errors = validate_context_snapshot(snap)
    assert valid, errors
    restored = expand_value_refs(snap["observed_state"]["receipts"][0], snap)
    assert restored["operation_result"] == literal


def test_unknown_result_note_shaped_root_does_not_authorize_decode():
    literal = {"id": "raw", "revision": 1, "text": "plugin content", "owner_turn_id": "review-turn", "quote": raw_ref()}
    journal = ExecutionJournal("review-conv", "review-turn", "review-exec", generation=0)
    journal.record_operation("unknown_plugin", {}, literal)
    snap = snapshot(execution_journal=journal,
        artifact_store_items=[Artifact("a", "fixture", payload={"value": "RAW_WAS_DECODED"})])
    entity = next(e for e in snap["entities"] if e["ref"]["kind"] == "operation_result")
    valid, errors = validate_context_snapshot(snap)
    assert valid, errors
    assert expand_value_refs(entity["body"], snap) == literal


def test_foreign_proof_entity_cannot_be_promoted_to_current_proof_ref():
    journal = ExecutionJournal("review-conv", "review-turn", "review-exec", generation=0)
    journal.receipts.append(ReceiptEnvelope(issuer="verification", conversation_id="review-conv",
        turn_id="old-turn", execution_id="old-exec", generation=0,
        verification_report={"status": "PASS", "scope": "fixture"}))
    snap = snapshot(execution_journal=journal)
    assert snap["observed_state"]["proof_refs"] == []
    foreign = next(e for e in snap["entities"] if e["ref"]["kind"] == "verification_report")
    snap["observed_state"]["proof_refs"] = [copy.deepcopy(foreign["ref"])]
    valid, errors = validate_context_snapshot(snap)
    assert not valid, errors


def test_unknown_result_list_wrapper_control():
    literal = [raw_ref()]
    journal = ExecutionJournal("review-conv", "review-turn", "review-exec", generation=0)
    journal.record_operation("unknown_plugin", {}, literal)
    snap = snapshot(execution_journal=journal,
        artifact_store_items=[Artifact("a", "fixture", payload={"value": "RAW_WAS_DECODED"})])
    valid, errors = validate_context_snapshot(snap)
    assert valid, errors
    assert expand_value_refs(snap["observed_state"]["receipts"][0], snap)["operation_result"] == literal
