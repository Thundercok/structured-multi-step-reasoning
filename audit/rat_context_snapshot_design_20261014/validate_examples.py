"""Offline consistency checks for authored ADR-004 examples, not runtime tests."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def read(name):
    return json.loads((HERE / name).read_text())


def key(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


schema = read("snapshot.schema.json")
Draft202012Validator.check_schema(schema)
validator = Draft202012Validator(schema)
snapshot = read("after.snapshot.json")
declared = read("declared_args.snapshot.json")
before = read("before.request.json")
after = read("after.request.json")
canonical = read("canonical_example_values.json")
provenance = read("provenance.json")
checks = []


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    checks.append(name)


validator.validate(snapshot)
validator.validate(declared)
checks.append("Both authored snapshots conform to the proposed transport schema")
check("Entity identities are unique",
      len(snapshot["entities"]) == len({key(e["ref"]) for e in snapshot["entities"]}))
entities = {key(e["ref"]): e for e in snapshot["entities"]}


def pointer(body, ptr):
    if not ptr:
        return body
    if not ptr.startswith("/"):
        raise AssertionError("Invalid RFC6901 pointer")
    for token in ptr[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        body = body[int(token)] if isinstance(body, list) else body[token]
    return body


def resolve_projection(value, active=()):
    # This checker operates on these authored projection bodies only. Production
    # must use registered typed slots, never recurse into raw fallback payloads.
    if isinstance(value, dict) and set(value) == {"$value_ref"}:
        r = value["$value_ref"]
        target = (key(r["entity_ref"]), r["pointer"])
        if target in active:
            raise AssertionError("Cyclic value reference")
        body = entities[target[0]]["body"]
        return resolve_projection(pointer(body, target[1]), active + (target,))
    if isinstance(value, dict):
        return {k: resolve_projection(v, active) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_projection(v, active) for v in value]
    return value


resolved = {k: resolve_projection(e["body"]) for k, e in entities.items()}
notes = [e for e in snapshot["entities"] if e["ref"]["kind"] == "note_version"]
for e in notes:
    revision = e["ref"]["revision"]
    check(f"Note revision {revision} expands exactly to canonical example values",
          resolved[key(e["ref"])] == canonical[f"note_revision_{revision}"])
    check(f"Note revision {revision} keeps full text inline",
          isinstance(e["body"]["text"], str) and e["body"]["text"] == canonical[f"note_revision_{revision}"]["text"])
    check(f"Note revision {revision} remains an unconfirmed model suggestion",
          e["authority"] == "unconfirmed_model_suggestion" and e["body"]["confirmed"] is False)
for kind, expected in (("note_event", "note_event"), ("operation_result", "operation_result")):
    e = next(e for e in snapshot["entities"] if e["ref"]["kind"] == kind)
    check(f"{kind} expands without losing canonical example fields", resolved[key(e["ref"])] == canonical[expected])

# All transport refs are mechanically closed; native operation source/target
# IDs and contract IDs are validated separately below, not rewritten to refs.
def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


for value in walk(snapshot):
    if value.get("kind") in {"artifact", "note_version", "operation_result", "note_event", "verification_report"}:
        check("Typed reference resolves to an inline entity", key(value) in entities)
unique_checks = list(dict.fromkeys(checks))
checks[:] = unique_checks
check("Contract is the A export with example identity substitutions, not strengthened",
      snapshot["runtime_obligations"]["contract"] == canonical["contract_from_A_after_ID_rewrite"])
check("A's undeclared expected args and target remain null",
      snapshot["runtime_obligations"]["contract"]["outcomes"][0]["expected_args"] is None
      and snapshot["runtime_obligations"]["contract"]["outcomes"][0]["target_ref"] is None)
binding = snapshot["runtime_obligations"]["contract"]["outcomes"][0]["source_ref"]
bound_source = next(e for e in snapshot["entities"] if e["ref"]["kind"] == "artifact"
                    and e["ref"]["artifact_id"] == binding["artifact_id"]
                    and e["ref"]["revision"] == binding["revision"])
check("Native contract source binding resolves to the exact inline field",
      bound_source["body"]["payload"][binding["field"]] == canonical["source_content"])
check("Contract identity/generation matches the boundary",
      all(snapshot["runtime_obligations"]["contract"][k] == snapshot["boundary"][k]
          for k in ("conversation_id", "turn_id", "execution_id", "generation")))
target = declared["runtime_obligations"]["contract"]["outcomes"][0]["target_ref"]
check("Hypothetical native target binding resolves to the old note revision",
      any(e["ref"]["kind"] == "note_version" and e["ref"]["note_id"] == target["note_id"]
          and e["ref"]["revision"] == target["expected_revision"] for e in snapshot["entities"]))
check("Separate declared-args example keeps literal expectation values",
      declared["runtime_obligations"]["contract"]["outcomes"][0]["expected_args"]
      == before["messages"][-2]["tool_calls"][0]["function"]["arguments"])
check("Expected args contain no generated value references",
      not any("$value_ref" in x for x in walk(declared["runtime_obligations"]["contract"]["outcomes"][0]["expected_args"])))
check("Existing tools, order and input definitions are exactly retained", before["tools"] == after["tools"])
check("Native assistant tool call is exactly retained", before["messages"][-2] == after["messages"][-2])
check("Tool role and name are retained", before["messages"][-1]["role"] == after["messages"][-1]["role"] == "tool"
      and before["messages"][-1]["tool_name"] == after["messages"][-1]["tool_name"])
check("History roles, order, text and window are retained", before["messages"][1:9] == after["messages"][1:9])
check("Runtime clock/member system message is retained", before["messages"][15] == after["messages"][9])
check("Persona prefix is retained and extended by a static protocol clause",
      after["messages"][0]["content"].startswith(before["messages"][0]["content"]))
snapshot_message = after["messages"][10]
check("Snapshot is in a data message and matches the standalone artifact",
      snapshot_message["role"] == "user" and json.loads(snapshot_message["content"]) == snapshot)
query_index = int(snapshot["current_request"]["message_ref"].split("/")[1])
check("Current query message reference resolves", after["messages"][query_index] == before["messages"][16])
check("Current query has one instruction message",
      sum(m.get("content") == before["messages"][16]["content"] for m in after["messages"]) == 1)
check("History message references resolve with the original roles",
      [after["messages"][int(r.split("/")[1])] for r in snapshot["current_request"]["history_message_refs"]]
      == before["messages"][1:9])
for m in after["messages"]:
    if m["role"] == "system":
        check("No source/note body is promoted into a system message",
              canonical["source_content"] not in m["content"]
              and canonical["note_revision_1"]["text"] not in m["content"]
              and canonical["note_revision_2"]["text"] not in m["content"])
tool_reply = json.loads(after["messages"][-1]["content"])
check("Tool reply result reference resolves inline", key(tool_reply["result_ref"]) in entities)
check("Tool reply receipt reference resolves in the scoped current journal",
      any(r["receipt_id"] == tool_reply["receipt_ref"]["receipt_id"]
          and r["execution_id"] == tool_reply["receipt_ref"]["execution_id"]
          for r in snapshot["observed_state"]["receipts"]))
for receipt in snapshot["observed_state"]["receipts"]:
    check("Receipt scope matches the boundary",
          all(receipt[k] == snapshot["boundary"][k] for k in ("conversation_id", "turn_id", "execution_id", "generation")))
    check("Receipt args retain the observed native arguments", receipt["operation_args"] == before["messages"][-2]["tool_calls"][0]["function"]["arguments"])
    for parent in receipt["parent_receipt_ids"]:
        check("Parent receipt exists in the current scoped journal", any(r["receipt_id"] == parent for r in snapshot["observed_state"]["receipts"]))
check("No content-verification proof is invented", snapshot["observed_state"]["proof_refs"] == [])
check("Response remains provisional/pending", snapshot["observed_state"]["progress"]["assessment"] == "provisional"
      and snapshot["observed_state"]["progress"]["outcomes"][1]["status"] == "pending_response")
check("Source capture hash still matches fixture provenance", sha(ROOT / provenance["source_capture"]) == provenance["source_capture_sha256"])

# Fail fast for a dangling or cyclic generated reference. These are design
# resolver checks; not a claim the production module exists or passed tests.
bad_ref = deepcopy(notes[0]["body"]["quote"])
bad_ref["$value_ref"]["entity_ref"]["artifact_id"] = "example-absent"
try:
    resolve_projection(bad_ref)
except KeyError:
    checks.append("Dangling generated value ref is rejected by the example checker")
else:
    raise AssertionError("Dangling ref accepted")

checks = list(dict.fromkeys(checks))
result = {
    "status": "design_examples_consistent_not_runtime_validation",
    "production_implemented": False, "live_model_calls": 0,
    "schema_standard": "JSON Schema draft 2020-12",
    "checks": checks,
    "limitations": [
        "Receipt/progress/coherence values are authored design assumptions, not observed journal evidence.",
        "This example resolver is limited to known generated projection bodies; production needs a typed slot registry and scope validation.",
        "No actor policy, concurrency, cache reuse, latency, token cost or full runtime regression was measured.",
    ],
    "files_sha256": {p.name: sha(p) for p in sorted(HERE.iterdir()) if p.is_file() and p.name != "validation.json"},
}
(HERE / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(f"Consistent authored design examples: {len(checks)} offline checks; no runtime implementation/model run.")
