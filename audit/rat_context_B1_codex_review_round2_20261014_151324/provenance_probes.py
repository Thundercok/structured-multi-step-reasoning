"""Independent B1 repair probes: projector origin, exact values and proof scope."""
import copy

import pytest

from rat.engine.completion import ExecutionJournal, ReceiptEnvelope
from rat.engine.context_snapshot import compile_context_snapshot, expand_value_refs, validate_context_snapshot
from rat.kernel.contracts import Artifact


CONV, TURN, EXEC = "review-conv", "review-turn", "review-exec"


def snapshot(**inputs):
    return compile_context_snapshot(
        view="actor", conversation_id=CONV, turn_id=TURN, execution_id=EXEC,
        generation=0, artifact_store_generation=0, note_event_cursor=0,
        current_query="Synthetic B1 provenance review", snapshot_id="review-round2", **inputs,
    )


def artifact_ref(artifact_id="a", conversation_id=CONV):
    return {"kind": "artifact", "conversation_id": conversation_id, "artifact_id": artifact_id, "revision": 1}


def value_ref(ref, pointer):
    return {"$value_ref": {"entity_ref": copy.deepcopy(ref), "pointer": pointer}}


def note(**fields):
    return {"id": "n1", "revision": 1, "text": "Canonical note", "quote": "Canonical quote",
            "source": "user_quote", "confirmed": True, "owner_turn_id": TURN, **fields}


def operation_snapshot(result, operation="unknown_plugin", **inputs):
    journal = ExecutionJournal(CONV, TURN, EXEC, generation=0)
    journal.record_operation(operation, {}, result)
    return snapshot(execution_journal=journal, **inputs)


@pytest.mark.parametrize("raw_key", ["quote", "note", "snapshot", "verification_report"])
def test_raw_unknown_result_familiar_key_does_not_authorize_decode(raw_key):
    result = {raw_key: value_ref(artifact_ref(), "/payload/value")}
    snap = operation_snapshot(result, artifact_store_items=[Artifact("a", "fixture", payload={"value": "RESOLVED_TARGET"})])
    valid, errors = validate_context_snapshot(snap)
    assert valid, errors
    restored = expand_value_refs(snap["observed_state"]["receipts"][0], snap)
    assert restored["operation_result"] == result


def test_raw_unknown_result_dangling_literal_ref_is_not_structural_reference():
    result = {"quote": value_ref(artifact_ref("missing"), "/payload/value")}
    snap = operation_snapshot(result)
    valid, errors = validate_context_snapshot(snap)
    assert valid, errors
    restored = expand_value_refs(snap["observed_state"]["receipts"][0], snap)
    assert restored["operation_result"] == result


def test_raw_artifact_literal_cycle_is_not_projector_graph_edge():
    literal = value_ref(artifact_ref(), "/payload/quote")
    snap = snapshot(artifact_store_items=[Artifact("a", "fixture", payload={"quote": literal})])
    valid, errors = validate_context_snapshot(snap)
    assert valid, errors
    assert snap["entities"][0]["body"]["payload"]["quote"] == literal


def test_note_and_source_ref_quote_preserve_independent_exact_values():
    raw = note(quote="Canonical source", source="artifact_result", source_ref={
        "artifact_id": "a", "artifact_revision": 1, "field": "value", "quote": "Different literal source quote",
    })
    snap = snapshot(artifact_store_items=[Artifact("a", "fixture", payload={"value": raw["quote"]})], notebook_notes=[raw])
    entity = next(e for e in snap["entities"] if e["ref"]["kind"] == "note_version")
    restored = expand_value_refs(entity["body"], snap)
    assert restored["quote"] == raw["quote"]
    assert restored["source_ref"]["quote"] == raw["source_ref"]["quote"]


def test_replacement_text_is_not_rewritten_without_exact_value_match():
    prior = note(text="Canonical prior text")
    current = note(revision=2, text="Current text", replaces_revision=1, replaces_text="Different literal prior text")
    snap = snapshot(notebook_notes=[current], notebook_history=[prior])
    entity = next(e for e in snap["entities"] if e["ref"].get("revision") == 2)
    restored = expand_value_refs(entity["body"], snap)
    assert restored["replaces_text"] == current["replaces_text"]


def test_trusted_note_result_equality_must_distinguish_bool_from_number():
    canonical = note()
    literal = note(confirmed=1)
    snap = operation_snapshot({"note": literal}, operation="record_work_note", notebook_notes=[canonical])
    restored = expand_value_refs(snap["observed_state"]["receipts"][0], snap)
    assert type(restored["operation_result"]["note"]["confirmed"]) is int
    assert restored["operation_result"]["note"] == literal


def test_receipt_event_same_id_different_body_is_not_silently_replaced():
    event = {"event_id": "evt", "kind": "created", "note_id": "n1", "after_revision": 1}
    literal = {**event, "kind": "different literal kind", "extra": "keep"}
    journal = ExecutionJournal(CONV, TURN, EXEC, generation=0)
    journal.receipts.append(ReceiptEnvelope(
        issuer="notebook", conversation_id=CONV, turn_id=TURN, execution_id=EXEC, generation=0, note_event=literal,
    ))
    snap = snapshot(execution_journal=journal, recent_events=[event])
    valid, _ = validate_context_snapshot(snap)
    if valid:
        restored = expand_value_refs(snap["observed_state"]["receipts"][0], snap)
        assert restored["note_event"] == literal


def test_proof_without_generation_is_not_current_generation_proof():
    journal = ExecutionJournal(CONV, TURN, EXEC, generation=0)
    journal.receipts.append(ReceiptEnvelope(
        issuer="verification", conversation_id=CONV, turn_id=TURN, execution_id=EXEC, generation=None,
        verification_report={"status": "PASS", "scope": "fixture"},
    ))
    snap = snapshot(execution_journal=journal)
    valid, _ = validate_context_snapshot(snap)
    assert not valid or snap["observed_state"]["proof_refs"] == []


def test_missing_typed_proof_ref_requires_explicit_unavailable():
    snap = snapshot()
    snap["observed_state"]["proof_refs"] = [{"kind": "verification_report", "execution_id": EXEC, "receipt_id": "missing"}]
    valid, errors = validate_context_snapshot(snap)
    assert not valid, errors


def test_unknown_result_equal_canonical_note_remains_raw_control():
    literal = {"note": note()}
    snap = operation_snapshot(literal, notebook_notes=[note()])
    entity = next(e for e in snap["entities"] if e["ref"]["kind"] == "operation_result")
    assert entity["body"] == literal
    assert expand_value_refs(snap["observed_state"]["receipts"][0], snap)["operation_result"] == literal


def test_same_id_revision_in_distinct_conversations_is_distinct_identity_control():
    snap = snapshot(artifact_store_items=[Artifact("a", "fixture", payload={"value": "first"})])
    other = copy.deepcopy(snap["entities"][0])
    other["ref"]["conversation_id"] = "other-conversation"
    other["body"]["payload"]["value"] = "second"
    snap["entities"].append(other)
    valid, errors = validate_context_snapshot(snap)
    assert valid, errors
