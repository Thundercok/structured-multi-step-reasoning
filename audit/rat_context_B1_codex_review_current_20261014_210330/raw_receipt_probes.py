"""Independent receipt-origin tests against the current canonical compiler."""
import copy

import pytest

from rat.engine.completion import ExecutionJournal
from rat.engine.context_snapshot import compile_context_snapshot, expand_value_refs, validate_context_snapshot
from rat.kernel.contracts import Artifact


CONV, TURN, EXEC = "review-conv", "review-turn", "review-exec"


def snapshot(journal, artifacts):
    return compile_context_snapshot(
        "actor", conversation_id=CONV, turn_id=TURN, execution_id=EXEC,
        generation=0, artifact_store_generation=0, note_event_cursor=0,
        current_query="Synthetic receipt-origin review", snapshot_id="raw-receipt-review",
        execution_journal=journal, artifact_store_items=artifacts,
    )


def literal_ref(target_present):
    return {"$value_ref": {"entity_ref": {
        "kind": "artifact", "conversation_id": CONV,
        "artifact_id": "target" if target_present else "literal-missing", "revision": 1,
    }, "pointer": "/payload/value"}}


@pytest.mark.parametrize("slot", ["operation_result", "note_event", "verification_report"])
@pytest.mark.parametrize("target_present", [True, False])
def test_literal_wrapper_in_unprojected_receipt_slot_stays_raw(slot, target_present):
    literal = literal_ref(target_present)
    journal = ExecutionJournal(CONV, TURN, EXEC, generation=0)
    artifacts = [Artifact("produced", "fixture", payload={"value": "Different committed payload"})]
    receipt = journal.record_operation(
        "unknown_plugin", {}, literal if slot == "operation_result" else {"ok": True},
        artifact_refs=[{"artifact_id": "produced", "revision": 1}] if slot == "operation_result" else None,
    )
    if slot != "operation_result":
        setattr(receipt, slot, copy.deepcopy(literal))
    if target_present:
        artifacts.append(Artifact("target", "fixture", payload={"value": "RAW_MUST_STAY_LITERAL"}))
    snap = snapshot(journal, artifacts)
    # All native literal inputs remain data; no compiler substitution occurred in this slot.
    assert snap["observed_state"]["receipts"][0][slot] == literal
    valid, errors = validate_context_snapshot(snap)
    assert valid, errors
    restored = expand_value_refs(snap["observed_state"]["receipts"][0], snap)
    assert type(restored[slot]) is dict
    assert restored[slot] == literal


def test_emitted_receipt_to_artifact_link_still_restores_literal_payload_control():
    literal = literal_ref(True)
    journal = ExecutionJournal(CONV, TURN, EXEC, generation=0)
    journal.record_operation("unknown_plugin", {}, literal,
                             artifact_refs=[{"artifact_id": "produced", "revision": 1}])
    artifacts = [Artifact("produced", "fixture", payload=literal),
                 Artifact("target", "fixture", payload={"value": "RAW_MUST_STAY_LITERAL"})]
    snap = snapshot(journal, artifacts)
    projected = snap["observed_state"]["receipts"][0]["operation_result"]
    assert projected != literal
    assert projected["$value_ref"]["entity_ref"]["artifact_id"] == "produced"
    valid, errors = validate_context_snapshot(snap)
    assert valid, errors
    restored = expand_value_refs(snap["observed_state"]["receipts"][0], snap)
    assert restored["operation_result"] == literal


def test_literal_matching_real_projector_target_and_pointer_still_stays_raw():
    # This is exactly the shape, target identity and pointer that the compiler
    # itself emits for a pinned artifact payload; only the native origin differs.
    literal = {"$value_ref": {"entity_ref": {
        "kind": "artifact", "conversation_id": CONV, "artifact_id": "produced", "revision": 1,
    }, "pointer": "/payload"}}
    journal = ExecutionJournal(CONV, TURN, EXEC, generation=0)
    journal.record_operation("unknown_plugin", {}, literal,
                             artifact_refs=[{"artifact_id": "produced", "revision": 1}])
    snap = snapshot(journal, [Artifact("produced", "fixture", payload={"value": "Different native value"})])
    assert snap["observed_state"]["receipts"][0]["operation_result"] == literal
    valid, errors = validate_context_snapshot(snap)
    assert valid, errors
    assert expand_value_refs(snap["observed_state"]["receipts"][0], snap)["operation_result"] == literal
