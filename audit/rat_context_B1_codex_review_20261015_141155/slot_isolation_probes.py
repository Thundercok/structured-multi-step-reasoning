"""Projector permissions must identify complete paths, not shared leaf aliases."""
import copy

import pytest

from rat.engine.completion import ExecutionJournal
from rat.engine.context_snapshot import compile_context_snapshot, expand_value_refs, validate_context_snapshot


CONV, TURN, EXEC = "review-conv", "review-turn", "review-exec"
EVENT = {"event_id": "evt1", "kind": "created", "note_id": "n1", "after_revision": 1, "owner_turn_id": TURN}


def snapshot(result, operation):
    journal = ExecutionJournal(CONV, TURN, EXEC, generation=0)
    receipt = journal.record_operation(operation, {}, copy.deepcopy(result))
    receipt.note_event = copy.deepcopy(EVENT)
    return compile_context_snapshot(
        "actor", conversation_id=CONV, turn_id=TURN, execution_id=EXEC,
        generation=0, artifact_store_generation=0, note_event_cursor=0,
        current_query="Synthetic projector slot isolation review", snapshot_id="slot-isolation",
        execution_journal=journal, recent_events=[copy.deepcopy(EVENT)],
    )


@pytest.mark.parametrize("operation", ["record_work_note", "unknown_plugin"])
@pytest.mark.parametrize("target_present", [True, False])
def test_projected_top_level_event_cannot_authorize_raw_result_child(operation, target_present):
    literal = {"$value_ref": {"entity_ref": {
        "kind": "note_event", "conversation_id": CONV,
        "event_id": "evt1" if target_present else "literal-missing",
    }, "pointer": ""}}
    result = {"note_event": literal}
    snap = snapshot(result, operation)
    header = snap["observed_state"]["receipts"][0]
    assert "note_event" in header["projected_slots"]
    assert "operation_result.note_event" not in header["projected_slots"]
    valid, errors = validate_context_snapshot(snap)
    assert valid, errors
    restored = expand_value_refs(header, snap)
    assert restored["note_event"] == EVENT
    assert restored["operation_result"] == result


def test_distinct_legitimate_top_level_and_nested_event_links_control():
    result = {"note_event": copy.deepcopy(EVENT)}
    snap = snapshot(result, "record_work_note")
    header = snap["observed_state"]["receipts"][0]
    assert "note_event" in header["projected_slots"]
    assert "operation_result.note_event" in header["projected_slots"]
    valid, errors = validate_context_snapshot(snap)
    assert valid, errors
    restored = expand_value_refs(header, snap)
    assert restored["note_event"] == EVENT
    assert restored["operation_result"] == result
