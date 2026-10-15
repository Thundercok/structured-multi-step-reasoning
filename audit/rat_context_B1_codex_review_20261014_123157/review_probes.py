"""Independent B1 acceptance probes, derived from canonical projection invariants."""
import copy

import pytest

from rat.engine.completion import ExecutionJournal, OutcomeSpec, ReceiptEnvelope, TurnContract
from rat.engine.context_snapshot import compile_context_snapshot, expand_value_refs, validate_context_snapshot
from rat.kernel.contracts import Artifact


def snapshot(**inputs):
    return compile_context_snapshot(
        view="actor", conversation_id="review-conv", turn_id="review-turn", execution_id="review-exec",
        generation=0, artifact_store_generation=0, note_event_cursor=0,
        current_query="Synthetic B1 review", snapshot_id="review-snapshot", **inputs,
    )


def value_ref(ref, pointer):
    return {"$value_ref": {"entity_ref": copy.deepcopy(ref), "pointer": pointer}}


def note(**fields):
    return {"id": "n1", "revision": 1, "text": "Canonical note", "quote": "Canonical quote",
            "source": "user_quote", "confirmed": True, "owner_turn_id": "review-turn", **fields}


@pytest.mark.parametrize("root", ["proposal", "runtime_obligations"])
def test_raw_nested_quote_key_never_authorizes_value_ref_decode(root):
    art = Artifact("a", "fixture", payload={"value": "RESOLVED_TARGET"})
    ref = {"kind": "artifact", "conversation_id": "review-conv", "artifact_id": "a", "revision": 1}
    literal = {"nested": {"quote": value_ref(ref, "/payload/value")}}
    contract = TurnContract(conversation_id="review-conv", turn_id="review-turn", execution_id="review-exec", generation=0,
                            outcomes=[OutcomeSpec("effect", "registered_effect", "fixture", expected_args=literal)])
    snap = snapshot(artifact_store_items=[art], task_state=literal, turn_contract=contract)
    before = copy.deepcopy(snap[root])
    assert expand_value_refs(snap[root], snap) == before


@pytest.mark.parametrize("result", [42, [1, 2], False, "scalar"])
def test_no_artifact_operation_result_roundtrip_preserves_json_type(result):
    journal = ExecutionJournal("review-conv", "review-turn", "review-exec", generation=0)
    journal.record_operation("unknown_fixture", {}, result)
    snap = snapshot(execution_journal=journal)
    restored = expand_value_refs(snap["observed_state"]["receipts"][0], snap)
    assert type(restored["operation_result"]) is type(result)
    assert restored["operation_result"] == result


def test_unknown_result_note_shaped_payload_is_preserved_verbatim():
    result = {"note": {"id": "n1", "revision": 1, "text": "Plugin-specific note", "plugin_field": "keep"}}
    journal = ExecutionJournal("review-conv", "review-turn", "review-exec", generation=0)
    journal.record_operation("unknown_plugin", {}, result)
    snap = snapshot(execution_journal=journal, notebook_notes=[note()])
    restored = expand_value_refs(snap["observed_state"]["receipts"][0], snap)
    assert restored["operation_result"] == result


@pytest.mark.parametrize("field_value,quote", [(42, "42"), (" source text ", "source text")])
def test_quote_projection_preserves_exact_string_and_type(field_value, quote):
    art = Artifact("a", "fixture", payload={"value": field_value})
    raw_note = note(quote=quote, source="artifact_result", source_ref={
        "artifact_id": "a", "artifact_revision": 1, "field": "value", "quote": quote,
    })
    snap = snapshot(artifact_store_items=[art], notebook_notes=[raw_note])
    entity = next(e for e in snap["entities"] if e["ref"]["kind"] == "note_version")
    restored = expand_value_refs(entity["body"], snap)
    assert type(restored["quote"]) is str
    assert restored["quote"] == quote
    assert restored["source_ref"]["quote"] == raw_note["source_ref"]["quote"]


def test_artifact_projection_retains_status_provenance_and_timestamp():
    art = Artifact("a", "fixture", payload={"value": "data"}, status="waiting_input", created_at=7,
                   provenance={"source_artifact_id": "source", "source_revision": 3, "operation_name": "fixture"})
    snap = snapshot(artifact_store_items=[art])
    body = snap["entities"][0]["body"]
    for field in ("status", "provenance", "created_at"):
        assert field in body
        assert body[field] == art.to_dict()[field]


def test_canonical_invalid_dict_cannot_be_reparsed_into_met_progress():
    contract = TurnContract(conversation_id="review-conv", turn_id="review-turn", execution_id="review-exec", generation=0,
                            outcomes=[OutcomeSpec("effect", "registered_effect", "fixture")],
                            is_valid=False, validation_errors=["runtime_binding_error"])
    journal = ExecutionJournal("review-conv", "review-turn", "review-exec", generation=0)
    journal.record_operation("fixture", {}, {"ok": True})
    snap = snapshot(turn_contract=contract.to_dict(), execution_journal=journal)
    assert snap["runtime_obligations"]["contract"]["is_valid"] is False
    assert snap["observed_state"]["progress"]["outcomes"][0]["status"] == "unresolved"


def test_foreign_execution_proof_is_not_current_proof():
    journal = ExecutionJournal("review-conv", "review-turn", "review-exec", generation=0)
    journal.receipts.append(ReceiptEnvelope(
        issuer="verification", conversation_id="other-conv", turn_id="old-turn", execution_id="old-exec", generation=9,
        verification_report={"status": "PASS", "scope": "fixture"},
    ))
    snap = snapshot(execution_journal=journal)
    valid, errors = validate_context_snapshot(snap)
    # Either reject the scope mismatch or exclude it from the current proof view.
    assert not valid or snap["observed_state"]["proof_refs"] == []


def test_missing_typed_index_ref_requires_explicit_unavailable():
    snap = snapshot()
    snap["indexes"]["selection_set"] = True
    snap["indexes"]["selected_results"] = [{
        "kind": "artifact", "conversation_id": "review-conv", "artifact_id": "missing", "revision": 1,
    }]
    valid, errors = validate_context_snapshot(snap)
    assert not valid, errors


def test_duplicate_entity_identity_with_conflicting_bodies_is_rejected():
    snap = snapshot(artifact_store_items=[Artifact("a", "fixture", payload={"value": "first"}),
                                          Artifact("a", "fixture", payload={"value": "second"})])
    valid, errors = validate_context_snapshot(snap)
    assert not valid, errors


def test_cycle_in_projection_quote_refs_is_rejected_before_expansion():
    snap = snapshot(notebook_notes=[note()])
    entity = snap["entities"][0]
    entity["body"]["quote"] = value_ref(entity["ref"], "/source_ref/quote")
    entity["body"]["source_ref"] = {"quote": value_ref(entity["ref"], "/quote")}
    valid, errors = validate_context_snapshot(snap)
    assert not valid, errors
