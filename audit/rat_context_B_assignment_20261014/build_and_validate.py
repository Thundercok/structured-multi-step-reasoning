"""Revised design examples: real reconciler over authored synthetic receipts.

Not the B compiler, not model inference, not a runtime benchmark. Preserve the
previous design packet and its validation hashes unchanged.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from rat.engine.completion import ExecutionJournal, ReceiptEnvelope, TurnContract, reconcile_turn

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
BASE = ROOT / "audit/rat_context_snapshot_design_20261014"


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


old_manifest = load(ROOT / "audit/rat_context_handoff_review_20261014/manifest_start.json")
protected = dict(old_manifest["protected_inputs_sha256"])
protected.update({str(p.relative_to(ROOT)): sha(p) for p in BASE.iterdir() if p.is_file()})
protected["docs/adr-004-rat-context-snapshot.md"] = sha(ROOT / "docs/adr-004-rat-context-snapshot.md")
manifest_path = HERE / "manifest_start.json"
if manifest_path.exists():
    protected = load(manifest_path)["protected_inputs_sha256"]
else:
    write("manifest_start.json", {"protected_inputs_sha256": protected})
assert all(sha(ROOT / name) == expected for name, expected in protected.items())

schema = load(BASE / "snapshot.schema.json")
snapshot = load(BASE / "after.snapshot.json")
values = load(BASE / "canonical_example_values.json")
progress_schema = schema["properties"]["observed_state"]["properties"]["progress"]
items = progress_schema["properties"]["outcomes"]["items"]
del items["properties"]["receipt_ids"]
items["required"].remove("receipt_ids")
progress_schema["properties"]["evidence"] = {
    "type": "object", "additionalProperties": False,
    "properties": {"intent_coverage": {"type": "string"}, "scoped_quality": {"type": "string"},
                   "matched_receipts": {"type": "array", "items": {"type": "string"}},
                   "unmet_outcomes": {"type": "array", "items": {"type": "object"}},
                   "unresolved_reasons": {"type": "array", "items": {"type": "string"}}},
    "required": ["intent_coverage", "scoped_quality", "matched_receipts", "unmet_outcomes", "unresolved_reasons"],
}
progress_schema["properties"]["final_response_pending"] = {"type": "boolean"}
progress_schema["required"].extend(["evidence", "final_response_pending"])
boundary_schema = schema["properties"]["boundary"]
boundary_schema["properties"]["artifact_store_generation"] = {"type": "integer", "minimum": 0}
boundary_schema["required"].append("artifact_store_generation")
index_schema = schema["properties"]["indexes"]
index_schema["properties"]["selection_set"] = {"type": "boolean"}
index_schema["required"].append("selection_set")
schema["description"] += " Revised proposed progress: only global match evidence; no invented outcome-to-receipt map. Store epochs are distinct."
Draft202012Validator.check_schema(schema)
validator = Draft202012Validator(schema)
write("snapshot.schema.json", schema)


def assessment_for(example):
    canonical_contract = example["runtime_obligations"]["contract"]
    contract = TurnContract.from_dict(canonical_contract)
    if canonical_contract["frozen"]:
        contract.freeze()
    headers = deepcopy(example["observed_state"]["receipts"])
    # These are manually authored receipts. Restore their actual canonical body
    # values before feeding them to the existing pure reconciler.
    headers[0]["operation_result"] = deepcopy(values["operation_result"])
    headers[1]["note_event"] = deepcopy(values["note_event"])
    headers[1]["operation_args"] = None
    headers[1]["operation_call_id"] = None
    receipts = [ReceiptEnvelope(**h) for h in headers]
    journal = ExecutionJournal(contract.conversation_id, contract.turn_id, contract.execution_id,
                               generation=contract.generation, receipts=receipts, _seq=2)
    report = reconcile_turn(contract, journal, lifecycle="in_progress", final_answer="",
                            notebook_snapshot=[values["note_revision_2"]]).to_dict()
    unmet = {u["outcome_id"]: u for u in report["unmet_outcomes"]}
    eligible = contract.is_valid and contract.intent_coverage not in ("unchecked", "invalid") and bool(contract.outcomes)
    rows = []
    for o in contract.outcomes:
        if not eligible:
            state, reason = "unresolved", "contract_not_eligible_for_provisional_match"
        elif o.kind == "response":
            state, reason = "pending_response", unmet.get(o.outcome_id, {}).get("reason", "final_response_pending")
        elif o.outcome_id in unmet:
            state, reason = "pending", unmet[o.outcome_id]["reason"]
        else:
            state, reason = "met", "matched_by_joint_reconciler_at_snapshot_boundary"
        rows.append({"outcome_id": o.outcome_id, "status": state, "reason": reason})
    progress = {
        "assessment": "provisional", "matcher": "existing_completion_reconciler",
        "outcomes": rows, "final_response_pending": True,
        "evidence": {k: deepcopy(report[k]) for k in
                     ("intent_coverage", "scoped_quality", "matched_receipts", "unmet_outcomes", "unresolved_reasons")},
    }
    projected_headers = deepcopy(example["observed_state"]["receipts"])
    projected_headers[1]["operation_args"] = None
    projected_headers[1]["operation_call_id"] = None
    return progress, report, projected_headers


assessment_reports = {}
for name, base_name in (("after.snapshot.json", "after.snapshot.json"),
                        ("declared_args.snapshot.json", "declared_args.snapshot.json")):
    example = load(BASE / base_name)
    example["boundary"]["artifact_store_generation"] = 0  # authored, not captured
    example["indexes"]["selection_set"] = False  # authored, not captured
    progress, report, receipts = assessment_for(example)
    example["observed_state"]["progress"] = progress
    example["observed_state"]["receipts"] = receipts
    validator.validate(example)
    assert report["matched_receipts"] == [receipts[1]["receipt_id"]]
    assert progress["outcomes"][0]["status"] == "met"
    assert progress["outcomes"][1]["status"] == "pending_response"
    assert progress["evidence"]["scoped_quality"] == "not_checked"
    assert all("receipt_ids" not in row for row in progress["outcomes"])
    assert not any(k in progress for k in ("summary", "lifecycle", "declared_scope_completion"))
    assert example["runtime_obligations"] == load(BASE / base_name)["runtime_obligations"]
    write(name, example)
    assessment_reports[name] = report
    if name == "after.snapshot.json":
        snapshot = example

after = load(BASE / "after.request.json")
after["messages"][10]["content"] = json.dumps(snapshot, ensure_ascii=False)
assert after["tools"] == load(BASE / "before.request.json")["tools"]
assert after["messages"][-2] == load(BASE / "before.request.json")["messages"][-2]
write("after.request.json", after)
write("assessment_reports.json", assessment_reports)
write("provenance.json", {
    "status": "authored_design_reconciled_by_existing_pure_software_not_B_runtime",
    "parent_design_packet": str(BASE.relative_to(ROOT)),
    "progress": "Computed by existing reconcile_turn over authored synthetic receipt envelopes; not inferred from live A journals.",
    "boundary_epochs_and_selection": "Authored illustrative values; must be read/rechecked from real state in B2.",
    "scope": "Local design only: no live inference, UI, production compiler, controller or model-default changes.",
    "previous_design_kept_unchanged": True,
})
assert all(sha(ROOT / name) == expected for name, expected in protected.items())
write("validation.json", {
    "status": "revised_B_design_consistent_implementation_pending",
    "protected_input_count": len(protected), "changed_protected_inputs": [],
    "checks": ["Revised transport schema and both example snapshots valid",
               "Existing joint reconciler matches only the notebook receipt for the authored draft effect",
               "Stronger hypothetical expected arguments remain literal and match the authored actual args",
               "Response remains pending before final, source content has no formal proof",
               "No outcome-to-receipt map or terminal completion claim is manufactured",
               "Canonical declarations, native call and tool definitions retained",
               "Prior design packet and protected core/audit inputs unchanged"],
    "live_model_calls": 0, "B_runtime_implemented": False,
    "claims": "Software/design consistency only; no measured AI quality, latency, token or cache savings.",
    "files_sha256": {p.name: sha(p) for p in sorted(HERE.iterdir()) if p.is_file() and p.name != "validation.json"},
})
print(f"Revised B design validated on authored receipts; {len(protected)} input files preserved; no model/runtime implementation.")
