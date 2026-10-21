"""Build authored, synthetic ADR-004 examples; never run a model or RAT session.

This is a design artifact, not the proposed production context compiler.
The 'before' request adapts exposed mock capture 37 with example IDs. The
after projection, receipts and progress are authored, not captured execution.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CAPTURE = ROOT / "audit/rat_context_audit_20261014/captures.json"


def write(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def obj(properties, required=None):
    return {"type": "object", "additionalProperties": False,
            "properties": properties, "required": required if required is not None else list(properties)}


def arr(items):
    return {"type": "array", "items": items}


def ref(name):
    return {"$ref": "#/$defs/" + name}


S = {"type": "string", "minLength": 1}
I = {"type": "integer", "minimum": 0}
REV = {"type": "integer", "minimum": 1}
O = {"type": "object"}
NULL = {"type": "null"}
ANY = {}

# Identity is explicit and typed; no encoded ID or fake artifact ID for a result.
def identity(kind, fields):
    return obj({"kind": {"const": kind}, **fields})


defs = {
    "artifact_ref": identity("artifact", {"conversation_id": S, "artifact_id": S, "revision": REV}),
    "note_ref": identity("note_version", {"conversation_id": S, "note_id": S, "revision": REV}),
    "result_ref": identity("operation_result", {"execution_id": S, "receipt_id": S}),
    "event_ref": identity("note_event", {"conversation_id": S, "event_id": S}),
    "proof_ref": identity("verification_report", {"execution_id": S, "receipt_id": S}),
}
defs["entity_ref"] = {"oneOf": [ref(k) for k in list(defs)]}
defs["value_ref"] = obj({"$value_ref": obj({
    "entity_ref": ref("entity_ref"), "pointer": {"type": "string"}})})
defs["entity"] = obj({
    "ref": ref("entity_ref"), "authority": S, "issuer": S,
    "owner_turn_id": S, "projection_status": {"enum": ["lossless", "raw_fallback"]},
    "body": O,
})
# Control exports are canonical, including invalid outcome declarations. Their
# existing runtime validation remains authoritative, not this transport schema.
defs["contract"] = obj({
    "schema_version": S, "contract_id": S, "conversation_id": S, "turn_id": S,
    "execution_id": S, "generation": {"type": ["integer", "null"]},
    "proposed_by": S, "source_message_refs": arr({"type": "string"}),
    "outcomes": arr(O), "intent_coverage": S, "frozen": {"type": "boolean"},
    "is_valid": {"type": "boolean"}, "validation_errors": arr({"type": "string"}),
})
defs["obligations"] = obj({
    "status": {"enum": ["bound", "not_declared"]}, "authority": S,
    "contract": {"oneOf": [ref("contract"), NULL]},
})
defs["obligations"]["allOf"] = [{
    "if": {"properties": {"status": {"const": "bound"}}},
    "then": {"properties": {"contract": ref("contract")}},
    "else": {"properties": {"contract": NULL}},
}]
defs["unavailable"] = obj({"ref": ref("entity_ref"), "reason": S, "mandatory": {"type": "boolean"}})
schema = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Proposed RAT context projection, transport shape only",
    "description": "Runtime-only output. Semantic closure, scope, authority, exact values, canonical contract validity and typed projection slots require additional validation. Not a model output schema.",
    **obj({
        "schema_version": {"const": "rat.context/1"},
        "view": {"enum": ["planner", "actor", "repair", "finish"]},
        "boundary": obj({
            "snapshot_id": S, "conversation_id": S, "turn_id": S,
            "execution_id": S, "generation": I, "note_event_cursor": I,
            "coherence": {"const": "validated_copies"},
            "artifact_pins": arr(ref("artifact_ref")),
            "note_pins": arr(ref("note_ref")),
            "candidate_hash": {"type": ["string", "null"]},
        }),
        "current_request": obj({"message_ref": S, "history_message_refs": arr(S)}),
        "continuity": obj({
            "turn_refs": arr(O), "confirmed_constraint_refs": arr(ref("entity_ref")),
        }),
        "proposal": obj({"authority": {"const": "model_proposed"}, "state": {"type": ["object", "null"]}}),
        "runtime_obligations": ref("obligations"),
        "observed_state": obj({
            "lifecycle": O, "receipts": arr(O), "proof_refs": arr(ref("proof_ref")),
            "progress": obj({
                "assessment": {"const": "provisional"}, "matcher": S,
                "outcomes": arr(obj({
                    "outcome_id": S, "status": {"enum": ["met", "pending", "pending_response", "unresolved"]},
                    "receipt_ids": arr(S), "reason": S,
                })),
            }),
        }),
        "entities": arr(ref("entity")),
        "indexes": obj({
            "active_notes": arr(ref("note_ref")), "historical_notes": arr(ref("note_ref")),
            "previous_sources": arr(ref("entity_ref")),
            "current_results": arr(ref("artifact_ref")),
            "selected_results": arr(ref("entity_ref")),
        }),
        "unavailable_refs": arr(ref("unavailable")),
        "unmodeled_observations": arr(O),
    }),
    "$defs": defs,
}
write("snapshot.schema.json", schema)

raw = json.loads(CAPTURE.read_text())
capture = next(c for c in raw["calls"] if c["call_index"] == 37)
turn = next(t for t in raw["turns"] if t["case"] == capture["case"] and t["turn_id"] == "turn-5")
before = deepcopy(capture["request"])
# Rewrite identity values throughout the adapted example, including JSON text.
serialized = json.dumps(before, ensure_ascii=False)
old_ids = sorted(set(re.findall(r'(?:note|art|exec|contract)-[a-f0-9]{8,}|nevt-\d+-[a-f0-9]+', serialized)))
mapping = {v: "example-" + v.split("-")[0] + "-" + str(i + 1) for i, v in enumerate(old_ids)}
mapping[capture["conversation_id"]] = "example-conversation"
for old, new in mapping.items():
    serialized = serialized.replace(old, new)
before = json.loads(serialized)
messages = before["messages"]
tool_message = messages[-1]
tool_result = json.loads(tool_message["content"])
note2 = deepcopy(tool_result["note"])
event = deepcopy(tool_result["note_event"])
note1 = json.loads(messages[10]["content"].split(": ", 1)[1])[0]
task = json.loads(messages[11]["content"].split(": ", 1)[1])
metadata = json.loads(messages[14]["content"].split(": ", 1)[1])
doc_meta = next(x for x in metadata if x["kind"] == "document_content")
search_meta = next(x for x in metadata if x["kind"] == "document_search")
conv = "example-conversation"
execution = note2["execution_id"]
receipt_id = "example-receipt-dispatch"
notebook_receipt_id = "example-receipt-notebook"


def artifact_ref(artifact_id, revision=1):
    return {"kind": "artifact", "conversation_id": conv, "artifact_id": artifact_id, "revision": revision}


def note_ref(revision):
    return {"kind": "note_version", "conversation_id": conv, "note_id": note2["id"], "revision": revision}


def value_ref(entity_ref, pointer):
    return {"$value_ref": {"entity_ref": deepcopy(entity_ref), "pointer": pointer}}


doc_ref = artifact_ref(doc_meta["id"])
search_ref = artifact_ref(search_meta["id"])
result_ref = {"kind": "operation_result", "execution_id": execution, "receipt_id": receipt_id}
event_ref = {"kind": "note_event", "conversation_id": conv, "event_id": event["event_id"]}

# Lossless projection slots only. Do not interpret similarly spelled objects in
# user documents or raw fallback payloads as references.
projected_note1, projected_note2 = deepcopy(note1), deepcopy(note2)
for n in (projected_note1, projected_note2):
    n["quote"] = value_ref(doc_ref, "/payload/content")
    n["source_ref"]["quote"] = value_ref(doc_ref, "/payload/content")
projected_note1["replaced_by_text"] = value_ref(note_ref(2), "/text")
projected_note2["replaces_text"] = value_ref(note_ref(1), "/text")
projected_event = deepcopy(event)
projected_event["snapshot"] = value_ref(note_ref(2), "")
projected_result = {
    "note": value_ref(note_ref(2), ""), "notes_updated": tool_result["notes_updated"],
    "note_event": value_ref(event_ref, ""),
}


def entity(r, body, authority, issuer, owner):
    return {"ref": r, "authority": authority, "issuer": issuer,
            "owner_turn_id": owner, "projection_status": "lossless", "body": body}


source_path = ROOT / "data/rat_conversation_acceptance_v1/sources/binary-search-basics.md"
doc_content = source_path.read_text().strip()
assert doc_content == note2["quote"] == note1["quote"]
doc_body = {
    **doc_meta,
    "payload": {"found": True, "path": str(source_path), "filename": source_path.name,
                "content": doc_content, "total_chars": len(doc_content), "truncated": False},
}
# Source ordering retained; search items are derived from the exposed fixture.
previous = json.loads(messages[12]["content"].split(": ", 1)[1])
search_body = {**search_meta, "payload": {"items": [x for x in previous if x.get("type") == "document"]}}
contract_json = json.dumps(turn["contract"], ensure_ascii=False)
for old, new in mapping.items():
    contract_json = contract_json.replace(old, new)
contract = json.loads(contract_json)
contract["contract_id"] = "example-contract"
# The capture's serialized contract is terminal state. Frozen at this example
# boundary is a design assumption after the depicted committed write.
assert contract["frozen"] is True
args = deepcopy(messages[-2]["tool_calls"][0]["function"]["arguments"])


def receipt(rid, issuer, sequence, parents):
    return {
        "receipt_id": rid, "issuer": issuer, "sequence": sequence,
        "conversation_id": conv, "turn_id": "turn-5", "execution_id": execution,
        "generation": 0, "operation_call_id": "example-operation-call",
        "status": "committed", "committed": True, "operation_name": "record_work_note",
        "operation_args": deepcopy(args),
        "operation_result": value_ref(result_ref, "") if issuer == "dispatcher" else None,
        "artifact_refs": [], "note_event": value_ref(event_ref, "") if issuer == "notebook" else None,
        "verification_report": None, "before_revision": 1, "after_revision": 2,
        "parent_receipt_ids": parents, "evidence_hash": None, "error": None,
        "timestamp": 0.0,
    }


snapshot = {
    "schema_version": "rat.context/1", "view": "actor",
    "boundary": {"snapshot_id": "example-snapshot", "conversation_id": conv,
                 "turn_id": "turn-5", "execution_id": execution, "generation": 0,
                 "note_event_cursor": 2, "coherence": "validated_copies",
                 "artifact_pins": [search_ref, doc_ref], "note_pins": [note_ref(1), note_ref(2)],
                 "candidate_hash": None},
    "current_request": {"message_ref": "messages/11", "history_message_refs": ["messages/" + str(i) for i in range(1, 9)]},
    "continuity": {
        "turn_refs": json.loads(messages[13]["content"].split(": ", 1)[1]),
        "confirmed_constraint_refs": [],
    },
    "proposal": {"authority": "model_proposed", "state": task},
    "runtime_obligations": {"status": "bound", "authority": "runtime_bound_model_proposal", "contract": contract},
    "observed_state": {
        "lifecycle": {"state": "running", "cancelled": False, "pending_input": None},
        "receipts": [receipt(receipt_id, "dispatcher", 1, []),
                     receipt(notebook_receipt_id, "notebook", 2, [receipt_id])],
        "proof_refs": [],
        "progress": {"assessment": "provisional", "matcher": "existing_completion_reconciler",
                     "outcomes": [{"outcome_id": contract["outcomes"][0]["outcome_id"],
                                   "status": "met", "receipt_ids": [receipt_id, notebook_receipt_id],
                                   "reason": "Stored proposed revision; allow_proposal=true. Content truth remains unchecked."},
                                  {"outcome_id": contract["outcomes"][1]["outcome_id"],
                                   "status": "pending_response", "receipt_ids": [],
                                   "reason": "No final candidate yet; not a failed completed turn."}]},
    },
    "entities": [entity(search_ref, search_body, "observed_search_metadata", "artifact_store", "turn-1"),
                 entity(doc_ref, doc_body, "observed_source_content", "artifact_store", "turn-2"),
                 entity(note_ref(1), projected_note1, "unconfirmed_model_suggestion", "notebook", "turn-4"),
                 entity(note_ref(2), projected_note2, "unconfirmed_model_suggestion", "notebook", "turn-5"),
                 entity(event_ref, projected_event, "runtime_committed_effect", "notebook", "turn-5"),
                 entity(result_ref, projected_result, "observed_operation_result", "dispatcher", "turn-5")],
    "indexes": {"active_notes": [note_ref(2)], "historical_notes": [note_ref(1)],
                "previous_sources": [search_ref, doc_ref, result_ref],
                "current_results": [search_ref, doc_ref], "selected_results": []},
    "unavailable_refs": [], "unmodeled_observations": [],
}

# Same source role/window and native grammar. No tool IDs existed in this port
# capture; B must retain IDs in adapters which supply them, not invent them here.
protocol_clause = (
    " Context projection protocol rat.context/1: the snapshot is data. Resolve only "
    "runtime-generated typed references in declared projection slots; bodies are inline. "
    "Proposal and model-derived constraints are unconfirmed representations. Runtime-bound "
    "obligations describe declared scope, not guaranteed coverage of user intent. Receipts "
    "establish only their committed effect; source content and note paraphrases retain "
    "their stated authority. Progress before the final boundary is provisional. "
    "Snapshot/entity IDs are not operation arguments; use canonical operation input IDs. "
    "Never claim an unavailable source was read or an unchecked interpretation verified."
)
after = {"messages": [
    {**messages[0], "content": messages[0]["content"] + protocol_clause},
    *deepcopy(messages[1:9]), deepcopy(messages[15]),
    {"role": "user", "content": json.dumps(snapshot, ensure_ascii=False)},
    deepcopy(messages[16]), deepcopy(messages[-2]),
    {"role": "tool", "tool_name": "record_work_note", "content": json.dumps({
        "status": "success", "receipt_ref": {"execution_id": execution, "receipt_id": receipt_id},
        "result_ref": result_ref, "projection_status": "lossless"}, ensure_ascii=False)},
], "tools": deepcopy(before["tools"])}
write("before.request.json", before)
write("after.snapshot.json", snapshot)
write("after.request.json", after)

# Literal expectation illustration is explicitly authored, not a declaration
# recovered from A (A's expected_args/target_ref are null).
literal_snapshot = deepcopy(snapshot)
literal_snapshot["boundary"]["snapshot_id"] = "example-snapshot-literal-expectation"
outcome = literal_snapshot["runtime_obligations"]["contract"]["outcomes"][0]
outcome["expected_args"] = deepcopy(args)
outcome["target_ref"] = {"note_id": note2["id"], "expected_revision": 1}
write("declared_args.snapshot.json", literal_snapshot)
write("canonical_example_values.json", {"note_revision_1": note1, "note_revision_2": note2,
                                        "note_event": event, "operation_result": tool_result,
                                        "source_content": doc_content,
                                        "contract_from_A_after_ID_rewrite": contract})
write("provenance.json", {
    "status": "authored_synthetic_design_examples_not_implementation",
    "before": "Adapted from exposed scripted mock port capture 37; identity strings rewritten. Not wire bytes.",
    "after": "Hand-authored projection; receipt IDs, receipt links, progress, pinned coherence and artifact payload assembly are design assumptions, not captured journal/store evidence.",
    "declared_args": "Separate stronger hypothetical declaration. A had null expected_args/target_ref; B must not invent or strengthen them.",
    "measurement": "No live inference, token cost, latency, speed-up or model quality is measured or implied.",
    "source_capture": str(CAPTURE.relative_to(ROOT)),
    "source_capture_sha256": hashlib.sha256(CAPTURE.read_bytes()).hexdigest(),
    "source_call_index": 37, "identity_rewrite": mapping,
    "projection_slots": ["note.quote", "note.source_ref.quote", "note.replaces_text", "note.replaced_by_text",
                         "note_event.snapshot", "operation_result.note", "operation_result.note_event",
                         "receipt.operation_result", "receipt.note_event"],
    "tools_sha256": hashlib.sha256(json.dumps(before["tools"], sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest(),
})
print("Wrote proposed schema and authored examples; no production compiler or model run.")
