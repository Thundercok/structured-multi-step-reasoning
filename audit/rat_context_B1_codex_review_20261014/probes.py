"""Adversarial review probes for B1; synthetic data, zero model calls.

Reports expected semantic requirements versus observed behavior. This is a
review artifact, not a production compiler fix or measured AI evaluation.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from rat.engine.completion import ExecutionJournal, OutcomeSpec, ReceiptEnvelope, TurnContract
from rat.engine.context_snapshot import compile_context_snapshot, expand_value_refs, validate_context_snapshot
from rat.kernel.contracts import Artifact

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
records = []


def compile_(**kw):
    defaults = dict(view="actor", conversation_id="conv-review", turn_id="turn-2",
                    execution_id="exec-review", generation=2, artifact_store_generation=4,
                    note_event_cursor=2, current_query="Synthetic review request", snapshot_id="review-snapshot")
    defaults.update(kw)
    return compile_context_snapshot(**defaults)


def note(text="canonical note", **kw):
    result = dict(id="note-review", revision=1, text=text, source="artifact_result",
                  quote="source", confirmed=False, status="proposed", owner_turn_id="turn-1", source_ref={})
    result.update(kw)
    return result


def journal():
    return ExecutionJournal("conv-review", "turn-2", "exec-review", generation=2)


def contract(**kw):
    args = dict(contract_id="contract-review", conversation_id="conv-review", turn_id="turn-2",
                execution_id="exec-review", generation=2,
                outcomes=[OutcomeSpec("effect-review", kind="registered_effect", effect_type="custom_op")])
    args.update(kw)
    return TurnContract(**args)


def body(snap, kind, revision=None):
    return next(e["body"] for e in snap["entities"] if e["ref"]["kind"] == kind
                and (revision is None or e["ref"].get("revision") == revision))


def fake_ref():
    return {"$value_ref": {"entity_ref": {"kind": "artifact", "conversation_id": "conv-review",
                         "artifact_id": "art-review", "revision": 1}, "pointer": "/payload/content"}}


def artifact(content="inline source", **kw):
    args = dict(id="art-review", kind="document_content", revision=1, payload={"content": content})
    args.update(kw)
    return Artifact(**args)


def run(name, requirement, fn):
    try:
        passed, observed = fn()
        records.append(dict(name=name, requirement=requirement,
                            status="satisfies_requirement" if passed else "violates_requirement", observed=observed))
    except Exception as exc:
        records.append(dict(name=name, requirement=requirement, status="probe_error",
                            observed={"exception": type(exc).__name__, "message": str(exc)}))


def literal_payload():
    raw = {"quote": fake_ref()}
    j = journal(); j.record_operation("custom_op", {}, raw)
    s = compile_(execution_journal=j, artifact_store_items=[artifact()])
    expanded = expand_value_refs(s["observed_state"]["receipts"][0], s)["operation_result"]
    return expanded == raw, dict(expected=raw, actual=expanded)


def literal_args():
    args = {"quote": fake_ref()}
    j = journal(); j.record_operation("custom_op", args, {"ok": True})
    s = compile_(execution_journal=j, artifact_store_items=[artifact()])
    expanded = expand_value_refs(s["observed_state"]["receipts"][0], s)["operation_args"]
    return expanded == args, dict(expected=args, actual=expanded)


def unregistered_note_shape():
    original = {"note": note(text="raw output has different text")}
    j = journal(); j.record_operation("custom_op", {}, original)
    s = compile_(execution_journal=j, notebook_notes=[note()])
    expanded = expand_value_refs(s["observed_state"]["receipts"][0], s)["operation_result"]
    return expanded == original, dict(expected=original, actual=expanded)


def scalar_result(value):
    j = journal(); j.record_operation("custom_op", {}, value)
    s = compile_(execution_journal=j)
    expanded = expand_value_refs(s["observed_state"]["receipts"][0], s)["operation_result"]
    return expanded == value and type(expanded) is type(value), dict(expected=value, actual=expanded)


def quote_roundtrip(value, quote, source_quote="same"):
    raw = note(quote=quote, source_ref={"artifact_id": "art-review", "artifact_revision": 1,
                                    "field": "content", "quote": quote if source_quote == "same" else source_quote})
    s = compile_(notebook_notes=[raw], artifact_store_items=[artifact(content=value)])
    expanded = expand_value_refs(body(s, "note_version"), s)
    return expanded == raw, dict(expected=raw, actual=expanded)


def replacement_text():
    old = note(text="actual text in old revision")
    new = note(text="new note", revision=2, replaces_revision=1,
               replaces_note_id="note-review", replaces_text="original link text must survive")
    s = compile_(notebook_notes=[new], notebook_history=[old])
    expanded = expand_value_refs(body(s, "note_version", 2), s)
    return expanded == new, dict(expected=new, actual=expanded)


def event_snapshot():
    original = note()
    historical = {**original, "status": "replaced", "replaced_by_revision": 2,
                  "replaced_by_text": "new note", "replaced_by_turn_id": "turn-2"}
    current = note(text="new note", revision=2)
    event = dict(event_id="event-review", sequence=1, conversation_id="conv-review", kind="create",
                 note_id="note-review", owner_turn_id="turn-1", source_turn_id=None,
                 before_revision=None, after_revision=1, snapshot=original, context={})
    s = compile_(notebook_notes=[current], notebook_history=[historical], recent_events=[event])
    expanded = expand_value_refs(body(s, "note_event"), s)
    return expanded == event, dict(expected_snapshot=original, actual_snapshot=expanded["snapshot"])


def artifact_metadata():
    art = artifact(provenance={"owner_turn_id": "turn-1", "execution_id": "exec-source", "origin": "fixture"},
                   status="waiting_input", created_at=123.0)
    s = compile_(artifact_store_items=[art])
    projected = body(s, "artifact")
    lost = {k: v for k, v in art.to_dict().items() if k not in projected}
    return not lost, dict(dropped_canonical_fields=lost, projection_status=s["entities"][0]["projection_status"])


def foreign_contract():
    old = contract(conversation_id="conv-old", turn_id="turn-old", execution_id="exec-old", generation=0)
    j = ExecutionJournal("conv-old", "turn-old", "exec-old", generation=0)
    j.record_operation("custom_op", {}, {"ok": True})
    try:
        s = compile_(turn_contract=old, execution_journal=j)
        valid, errors = validate_context_snapshot(s)
    except (ValueError, TypeError):
        return True, {"rejected": True}
    return not valid, dict(valid=valid, errors=errors, current_boundary=s["boundary"],
                           progress=s["observed_state"]["progress"])


def stale_proof():
    j = journal()
    j.receipts.append(ReceiptEnvelope(receipt_id="proof-old", issuer="verification", conversation_id="conv-review",
                     turn_id="turn-2", execution_id="exec-review", generation=1,
                     verification_report={"status": "PASS", "scope": "fixture_scope", "authority": "fixture"}))
    try:
        s = compile_(execution_journal=j)
    except (ValueError, TypeError):
        return True, {"rejected": True}
    valid, errors = validate_context_snapshot(s)
    return not valid or not s["observed_state"]["proof_refs"], dict(valid=valid, errors=errors,
            current_generation=2, proof_refs=s["observed_state"]["proof_refs"],
            receipt_generation=s["observed_state"]["receipts"][0]["generation"])


def missing_epoch():
    j = journal(); r = j.record_operation("custom_op", {}, {"ok": True}); r.generation = None
    try:
        s = compile_(execution_journal=j)
    except (ValueError, TypeError):
        return True, {"rejected": True}
    projected = s["observed_state"]["receipts"][0]
    return projected["generation"] is None, dict(expected_generation=None, actual_generation=projected["generation"])


def validator_variant(which):
    s = compile_(notebook_notes=[note()])
    if which == "duplicate":
        s["entities"].append(deepcopy(s["entities"][0]))
        s["entities"][-1]["body"]["text"] = "conflicting body for the same identity"
    elif which == "dangling_index":
        s["indexes"]["active_notes"][0]["note_id"] = "absent-note"
    elif which == "cycle":
        e = s["entities"][0]
        e["body"]["quote"] = {"$value_ref": {"entity_ref": deepcopy(e["ref"]), "pointer": "/quote"}}
    valid, errors = validate_context_snapshot(s)
    extra = {}
    if which == "cycle":
        try:
            expand_value_refs(s["entities"][0]["body"], s)
        except Exception as exc:
            extra["expansion_error"] = type(exc).__name__
    return not valid, dict(valid=valid, errors=errors, **extra)


def missing_selection():
    try:
        s = compile_(selection_set=True, selected_artifact_ids=["absent-selected-artifact"])
    except (ValueError, TypeError):
        return True, {"rejected": True}
    refs = s["indexes"]["selected_results"]
    unavailable = s["unavailable_refs"]
    preserved = any(r.get("artifact_id") == "absent-selected-artifact" for r in refs)
    described = any(u["ref"].get("artifact_id") == "absent-selected-artifact" for u in unavailable)
    return preserved or described, dict(selection_set=s["indexes"]["selection_set"], selected_results=refs, unavailable_refs=unavailable)


def invalid_export():
    c = contract(is_valid=False, validation_errors=["runtime_validation_error"])
    j = journal(); j.record_operation("custom_op", {}, {"ok": True})
    s = compile_(turn_contract=c.to_dict(), execution_journal=j)
    row = s["observed_state"]["progress"]["outcomes"][0]
    return row["status"] == "unresolved", dict(canonical_is_valid=False, emitted_is_valid=s["runtime_obligations"]["contract"]["is_valid"],
                                               progress_status=row["status"], evidence=s["observed_state"]["progress"]["evidence"])


def control():
    c = contract(); j = journal(); j.record_operation("custom_op", {}, {"ok": True})
    s = compile_(turn_contract=c, execution_journal=j)
    valid, errors = validate_context_snapshot(s)
    return valid and s["observed_state"]["progress"]["outcomes"][0]["status"] == "met", dict(valid=valid, errors=errors)


if __name__ == "__main__":
    run("control_current_scope", "Valid scoped fixture remains supported", control)
    run("raw_payload_quote_wrapper", "Unmodeled raw result remains literal despite an allowed-looking key", literal_payload)
    run("operation_args_quote_wrapper", "Operation args remain literal during expansion", literal_args)
    run("unknown_operation_note_shape", "Generic raw note-looking output is not substituted using ID/revision alone", unregistered_note_shape)
    for value in (7, [1, 2], "string-result"):
        run("non_object_result_" + type(value).__name__, "Result type/value survives receipt projection roundtrip", lambda value=value: scalar_result(value))
    run("quote_numeric_type", "String quote stays string, not scalar source value", lambda: quote_roundtrip(42, "42"))
    run("quote_whitespace", "Quote preserves exact bytes, without strip equivalence", lambda: quote_roundtrip("source  \n", "source"))
    run("independent_source_ref_quote", "source_ref.quote is not overwritten from a different quote field", lambda: quote_roundtrip("source", "source", "independent original source_ref quote"))
    run("replacement_link_text", "Original replacement text remains exact unless equal to referenced value", replacement_text)
    run("immutable_event_snapshot", "Original event snapshot is not replaced with a later historical view", event_snapshot)
    run("artifact_metadata", "Canonical provenance/status are retained when marked lossless", artifact_metadata)
    run("foreign_bound_contract", "Bound contract/journal must match the current boundary", foreign_contract)
    run("stale_verification_proof", "Old epoch proof is not exposed as current scoped proof", stale_proof)
    run("missing_receipt_epoch", "Unknown receipt epoch is not filled with current epoch", missing_epoch)
    for variant in ("duplicate", "dangling_index", "cycle"):
        run("validator_" + variant, "Semantic validator rejects " + variant, lambda variant=variant: validator_variant(variant))
    run("missing_selected_artifact", "Missing selected item is explicit, not silently an empty selection", missing_selection)
    run("canonical_invalid_dict", "Canonical invalid state survives assessment of dict export", invalid_export)
    report = dict(scope="synthetic_offline_software_review_not_AI_evaluation", live_model_calls=0,
                  records=records, counts={s: sum(r["status"] == s for r in records)
                                          for s in ("satisfies_requirement", "violates_requirement", "probe_error")},
                  source_sha256={n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in
                                 ("rat/engine/context_snapshot.py", "tests/test_rat_context_snapshot.py", "rat/engine/completion.py")})
    (HERE / "probe_results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["counts"]))
    for r in records:
        print(r["status"], r["name"])
