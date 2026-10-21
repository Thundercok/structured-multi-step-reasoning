"""Ensure registered operation names do not authorize copied raw result children."""
import copy

import pytest

from rat.engine.completion import ExecutionJournal
from rat.engine.context_snapshot import compile_context_snapshot, expand_value_refs, validate_context_snapshot


CONV, TURN, EXEC = "review-conv", "review-turn", "review-exec"
NOTE = {"id": "n1", "revision": 1, "text": "Canonical note", "quote": "Canonical quote",
        "source": "user_quote", "confirmed": True, "owner_turn_id": TURN}
EVENT = {"event_id": "evt1", "kind": "created", "note_id": "n1", "after_revision": 1, "owner_turn_id": TURN}


def snapshot(result, target_present=True):
    journal = ExecutionJournal(CONV, TURN, EXEC, generation=0)
    journal.record_operation("record_work_note", {}, result)
    return compile_context_snapshot(
        "actor", conversation_id=CONV, turn_id=TURN, execution_id=EXEC,
        generation=0, artifact_store_generation=0, note_event_cursor=0,
        current_query="Synthetic registered-result origin review", snapshot_id="registered-result-origin",
        execution_journal=journal, notebook_notes=[copy.deepcopy(NOTE)] if target_present else [],
        recent_events=[copy.deepcopy(EVENT)] if target_present else [],
    )


@pytest.mark.parametrize("slot", ["note", "note_event"])
@pytest.mark.parametrize("target_present", [True, False])
def test_registered_result_child_wrapper_not_emitted_by_projector_stays_literal(slot, target_present):
    # Kind, target and pointer match an actual adapter-emitted link. The native
    # value is a literal wrapper, so the compiler's id/revision/equality checks
    # do not substitute it and cannot grant permission to decode it later.
    ref = ({"kind": "note_version", "conversation_id": CONV, "note_id": "n1", "revision": 1}
           if slot == "note" else {"kind": "note_event", "conversation_id": CONV, "event_id": "evt1"})
    result = {slot: {"$value_ref": {"entity_ref": ref, "pointer": ""}}}
    snap = snapshot(result, target_present)
    entity = next(e for e in snap["entities"] if e["ref"]["kind"] == "operation_result")
    assert entity["body"] == result
    valid, errors = validate_context_snapshot(snap)
    assert valid, errors
    restored = expand_value_refs(snap["observed_state"]["receipts"][0], snap)
    assert restored["operation_result"] == result


def test_canonical_registered_note_and_event_roundtrip_control():
    result = {"note": copy.deepcopy(NOTE), "note_event": copy.deepcopy(EVENT)}
    snap = snapshot(result)
    valid, errors = validate_context_snapshot(snap)
    assert valid, errors
    restored = expand_value_refs(snap["observed_state"]["receipts"][0], snap)
    assert restored["operation_result"] == result
