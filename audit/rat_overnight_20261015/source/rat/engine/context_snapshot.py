"""rat.engine.context_snapshot — Headless context projection compiler.

Implements ADR-004 and decisions for Package B1:
- Pure functional context projection compiler without new state stores or Qt dependencies.
- Single representation of proposal, obligations, observed state, entities, and indexes.
- Provisional progress evaluation via the existing pure reconciler (reconcile_turn).
  Global matched receipt evidence only; no manufactured outcome-to-receipt map.
- Distinct epochs: generation (notebook/journal) and artifact_store_generation (ArtifactStore).
  Explicit selection_set boolean to distinguish "not set" from "empty selection".
- Lossless entity projections with RFC 6901 $value_ref pointers for registered projection slots.
- Security guard: untrusted user JSON with $value_ref is never decoded as a runtime pointer.
- Full note text inline across all active and historical revisions; no ID-only old notes.
- Native expected args and operation arguments remain literal and unrewritten.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, Union
from uuid import uuid4

from jsonschema import Draft202012Validator

from rat.engine.completion import (
    ExecutionJournal,
    ReceiptEnvelope,
    TurnContract,
    TurnReconciliation,
    reconcile_turn,
)

SCHEMA_VERSION = "rat.context/1"
VALID_VIEWS = ("planner", "actor", "repair", "finish")

# Exact structural paths authorized for $value_ref expansion.
# Leaf names at arbitrary depths or inside raw proposal/obligations payloads are strictly forbidden.
AUTHORIZED_PROJECTOR_PATHS = frozenset({
    "quote",
    "source_ref.quote",
    "replaces_text",
    "replaced_by_text",
    "snapshot",
    "operation_result",
    "note_event",
    "verification_report",
    "note",
})

# Backward compatibility alias
ALLOWED_VALUE_REF_SLOTS = AUTHORIZED_PROJECTOR_PATHS


def exact_json_equal(a: Any, b: Any) -> bool:
    """Recursively compare two JSON-compatible objects with strict type and value equality.

    Distinguishes:
    - bool from int/float (True != 1, False != 0)
    - int from float (1 != 1.0)
    - dict key-set equality and per-key exact values
    - list length, order and per-item exact values
    - exact string characters (no stripping/coercion)
    - None from other types
    """
    if a is b:
        return True
    if type(a) is not type(b):
        return False
    if isinstance(a, bool):
        return a is b
    if isinstance(a, (int, float, str)):
        return a == b
    if a is None:
        return b is None
    if isinstance(a, list):
        if len(a) != len(b):
            return False
        return all(exact_json_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        if a.keys() != b.keys():
            return False
        return all(exact_json_equal(a[k], b[k]) for k in a)
    return a == b

_SCHEMA_CACHE: Optional[Dict[str, Any]] = None
_VALIDATOR_CACHE: Optional[Draft202012Validator] = None


def _find_schema_path() -> Path:
    candidates = [
        Path(__file__).resolve().parent / "snapshot.schema.json",
        Path(__file__).resolve().parent.parent.parent / "audit/rat_context_B_assignment_20261014/snapshot.schema.json",
        Path(__file__).resolve().parent.parent.parent / "audit/rat_context_snapshot_design_20261014/snapshot.schema.json",
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError(f"Could not find snapshot.schema.json in candidate locations: {candidates}")


def get_snapshot_schema() -> Dict[str, Any]:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        path = _find_schema_path()
        _SCHEMA_CACHE = json.loads(path.read_text(encoding="utf-8"))
    return copy.deepcopy(_SCHEMA_CACHE)


def get_snapshot_validator() -> Draft202012Validator:
    global _VALIDATOR_CACHE
    if _VALIDATOR_CACHE is None:
        schema = get_snapshot_schema()
        Draft202012Validator.check_schema(schema)
        _VALIDATOR_CACHE = Draft202012Validator(schema)
    return _VALIDATOR_CACHE


# ---------------------------------------------------------------------------
# RFC 6901 JSON Pointer helpers
# ---------------------------------------------------------------------------


def unescape_json_pointer_token(token: str) -> str:
    """Unescape an RFC 6901 JSON Pointer reference token (~1 -> /, ~0 -> ~)."""
    return token.replace("~1", "/").replace("~0", "~")


def escape_json_pointer_token(token: str) -> str:
    """Escape an RFC 6901 JSON Pointer reference token (~ -> ~0, / -> ~1)."""
    return token.replace("~", "~0").replace("/", "~1")


def resolve_json_pointer(doc: Any, pointer: str) -> Any:
    """Resolve an RFC 6901 JSON Pointer against a Python dict/list structure."""
    if not pointer:
        return doc
    if not pointer.startswith("/"):
        raise ValueError(f"Invalid JSON pointer '{pointer}': must start with '/' or be empty")
    tokens = [unescape_json_pointer_token(t) for t in pointer[1:].split("/")]
    current = doc
    for token in tokens:
        if isinstance(current, Mapping):
            if token not in current:
                raise KeyError(f"Key '{token}' not found while resolving pointer '{pointer}'")
            current = current[token]
        elif isinstance(current, (list, tuple)):
            try:
                idx = int(token)
            except ValueError:
                raise IndexError(f"List index '{token}' is not an integer while resolving pointer '{pointer}'")
            if idx < 0 or idx >= len(current):
                raise IndexError(f"List index {idx} out of range (length {len(current)}) while resolving pointer '{pointer}'")
            current = current[idx]
        else:
            raise TypeError(
                f"Cannot resolve token '{token}' on non-container type {type(current).__name__} at pointer '{pointer}'"
            )
    return current


# ---------------------------------------------------------------------------
# Value Reference resolution and security validation
# ---------------------------------------------------------------------------


def is_value_ref(obj: Any) -> bool:
    """Check if an object has the canonical $value_ref transport structure."""
    if not (isinstance(obj, dict) and "$value_ref" in obj and isinstance(obj["$value_ref"], dict)):
        return False
    vref = obj["$value_ref"]
    return "entity_ref" in vref and "pointer" in vref and isinstance(vref["entity_ref"], dict) and isinstance(vref["pointer"], str)


def find_entity(entities: Sequence[Dict[str, Any]], entity_ref: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Find the entity matching the exact entity_ref dictionary."""
    for e in entities:
        if e.get("ref") == entity_ref:
            return e
    return None


def resolve_value_ref(snapshot: Dict[str, Any], value_ref_obj: Dict[str, Any]) -> Any:
    """Resolve a typed $value_ref against the entities in a context snapshot."""
    if not is_value_ref(value_ref_obj):
        raise ValueError("Invalid value_ref object structure")
    vref = value_ref_obj["$value_ref"]
    entity_ref = vref["entity_ref"]
    pointer = vref["pointer"]

    entities = snapshot.get("entities", [])
    entity = find_entity(entities, entity_ref)
    if entity is None:
        raise ValueError(f"Entity reference {entity_ref} not found in snapshot entities")
    return resolve_json_pointer(entity.get("body", {}), pointer)


def _find_receipt_for_operation_result(snapshot: Dict[str, Any], entity_ref: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    rcpt_id = entity_ref.get("receipt_id")
    exec_id = entity_ref.get("execution_id")
    conv_id = entity_ref.get("conversation_id")
    turn_id = entity_ref.get("turn_id")
    for r in snapshot.get("observed_state", {}).get("receipts", []):
        if r.get("receipt_id") != rcpt_id:
            continue
        if exec_id is not None and r.get("execution_id") != exec_id:
            continue
        if conv_id is not None and r.get("conversation_id") != conv_id:
            continue
        if turn_id is not None and r.get("turn_id") != turn_id:
            continue
        return r
    return None


def iter_projector_edges(snapshot: Dict[str, Any]) -> List[Tuple[Tuple[str, str, str], Dict[str, Any]]]:
    """Extract all value_ref edges emitted by known typed projectors in their authorized locations.

    Returns a list of ((category, identifier, slot), value_ref_obj).

    Authorized locations are strictly bounded:
    - Receipts:
      - operation_result: pointer to operation_result entity ("" or "/result")
      - note_event: pointer to note_event entity ("")
      - verification_report: pointer to verification_report entity ("")
    - Entities:
      - note_version (issuer=notebook): quote, source_ref.quote, replaces_text, replaced_by_text
      - note_event (issuer=notebook): snapshot
      - operation_result: note and note_event ONLY IF emitted by record_work_note
    - Artifacts, verification reports, raw plugin results, proposals, and obligations NEVER emit edges.
    """
    edges: List[Tuple[Tuple[str, str, str], Dict[str, Any]]] = []

    # 1. Receipts in observed_state.receipts
    for rcpt in snapshot.get("observed_state", {}).get("receipts", []):
        rcpt_id = str(rcpt.get("receipt_id", ""))
        projected_slots = rcpt.get("projected_slots")
        for slot in ("operation_result", "note_event", "verification_report"):
            if projected_slots is not None and slot not in projected_slots:
                continue
            val = rcpt.get(slot)
            if is_value_ref(val):
                if projected_slots is None:
                    eref = val.get("$value_ref", {}).get("entity_ref", {})
                    ekind = eref.get("kind")
                    if slot == "operation_result" and ekind not in ("operation_result", "artifact"):
                        continue
                    if slot == "note_event" and ekind != "note_event":
                        continue
                    if slot == "verification_report" and ekind != "verification_report":
                        continue
                edges.append((("receipt", rcpt_id, slot), val))

        op_res = rcpt.get("operation_result")
        if isinstance(op_res, dict) and not is_value_ref(op_res):
            if projected_slots is not None:
                if ("operation_result.note" in projected_slots or "note" in projected_slots) and is_value_ref(op_res.get("note")):
                    edges.append((("receipt", rcpt_id, "operation_result.note"), op_res["note"]))
                if ("operation_result.note_event" in projected_slots or "note_event" in projected_slots) and is_value_ref(op_res.get("note_event")):
                    edges.append((("receipt", rcpt_id, "operation_result.note_event"), op_res["note_event"]))

    # 2. Entities in snapshot.entities
    for ent in snapshot.get("entities", []):
        ref = ent.get("ref", {})
        kind = ref.get("kind")
        issuer = ent.get("issuer")
        body = ent.get("body", {})
        ref_str = json.dumps(ref, sort_keys=True)

        if kind == "note_version" and issuer == "notebook":
            if is_value_ref(body.get("quote")):
                edges.append((("entity", ref_str, "quote"), body["quote"]))
            if isinstance(body.get("source_ref"), dict) and is_value_ref(body["source_ref"].get("quote")):
                edges.append((("entity", ref_str, "source_ref.quote"), body["source_ref"]["quote"]))
            if is_value_ref(body.get("replaces_text")):
                edges.append((("entity", ref_str, "replaces_text"), body["replaces_text"]))
            if is_value_ref(body.get("replaced_by_text")):
                edges.append((("entity", ref_str, "replaced_by_text"), body["replaced_by_text"]))

        elif kind == "note_event" and issuer == "notebook":
            if is_value_ref(body.get("snapshot")):
                edges.append((("entity", ref_str, "snapshot"), body["snapshot"]))

        elif kind == "operation_result":
            owning_rcpt = _find_receipt_for_operation_result(snapshot, ref)
            projected_slots = owning_rcpt.get("projected_slots") if owning_rcpt else None
            if projected_slots is not None:
                if ("operation_result.note" in projected_slots or "note" in projected_slots) and is_value_ref(body.get("note")):
                    edges.append((("entity", ref_str, "note"), body["note"]))
                if ("operation_result.note_event" in projected_slots or "note_event" in projected_slots) and is_value_ref(body.get("note_event")):
                    edges.append((("entity", ref_str, "note_event"), body["note_event"]))
            else:
                is_record_note = owning_rcpt and owning_rcpt.get("operation_name") == "record_work_note"
                if is_record_note:
                    if is_value_ref(body.get("note")):
                        edges.append((("entity", ref_str, "note"), body["note"]))
                    if is_value_ref(body.get("note_event")):
                        edges.append((("entity", ref_str, "note_event"), body["note_event"]))

    return edges


def _resolve_deref_chain(snapshot: Dict[str, Any], vref_obj: Dict[str, Any], seen_refs: Set[Tuple[str, str]]) -> Any:
    """Resolve a chain of $value_ref pointers, stopping when reaching raw data or terminal value."""
    curr = vref_obj
    current_chain = set(seen_refs)
    # Only links emitted at exact typed entity slots can extend a chain. A
    # trusted receipt link may resolve to raw plugin JSON whose root merely
    # looks like a wrapper; that body has no projector edge at pointer "".
    entity_edges = {
        (location[1], "/" + "/".join(escape_json_pointer_token(part) for part in location[2].split(".")))
        for location, _ in iter_projector_edges(snapshot)
        if location[0] == "entity"
    }
    while is_value_ref(curr):
        vref = curr["$value_ref"]
        eref = vref.get("entity_ref", {})
        ptr = vref.get("pointer", "")
        key = (json.dumps(eref, sort_keys=True), ptr)
        if key in current_chain:
            raise ValueError(f"Dereference cycle detected in value_ref: {key}")
        current_chain.add(key)
        target_ent = find_entity(snapshot.get("entities", []), eref)
        if target_ent is None:
            raise ValueError(f"Entity reference {eref} not found in snapshot entities")
        curr = resolve_json_pointer(target_ent.get("body", {}), ptr)
        if (json.dumps(eref, sort_keys=True), ptr) not in entity_edges:
            break
    return curr


def _expand_note_version_body(body: Dict[str, Any], snapshot: Dict[str, Any], seen_refs: Set[Tuple[str, str]]) -> Dict[str, Any]:
    res = copy.deepcopy(body)
    if is_value_ref(res.get("quote")):
        res["quote"] = copy.deepcopy(_resolve_deref_chain(snapshot, res["quote"], seen_refs))
    if isinstance(res.get("source_ref"), dict) and is_value_ref(res["source_ref"].get("quote")):
        res["source_ref"]["quote"] = copy.deepcopy(_resolve_deref_chain(snapshot, res["source_ref"]["quote"], seen_refs))
    if is_value_ref(res.get("replaces_text")):
        res["replaces_text"] = copy.deepcopy(_resolve_deref_chain(snapshot, res["replaces_text"], seen_refs))
    if is_value_ref(res.get("replaced_by_text")):
        res["replaced_by_text"] = copy.deepcopy(_resolve_deref_chain(snapshot, res["replaced_by_text"], seen_refs))
    return res


def _expand_note_event_body(body: Dict[str, Any], snapshot: Dict[str, Any], seen_refs: Set[Tuple[str, str]]) -> Dict[str, Any]:
    res = copy.deepcopy(body)
    if is_value_ref(res.get("snapshot")):
        target_note = _resolve_deref_chain(snapshot, res["snapshot"], seen_refs)
        if isinstance(target_note, dict):
            res["snapshot"] = _expand_note_version_body(target_note, snapshot, seen_refs)
        else:
            res["snapshot"] = copy.deepcopy(target_note)
    return res


def _expand_operation_result_body(
    body: Dict[str, Any],
    snapshot: Dict[str, Any],
    operation_name: Optional[str],
    seen_refs: Set[Tuple[str, str]],
    projected_slots: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    res = copy.deepcopy(body)
    should_expand_note = False
    should_expand_event = False

    if projected_slots is not None:
        should_expand_note = (
            "operation_result.note" in projected_slots or "note" in projected_slots
        )
        should_expand_event = (
            "operation_result.note_event" in projected_slots or "note_event" in projected_slots
        )
    elif operation_name == "record_work_note":
        should_expand_note = True
        should_expand_event = True

    if should_expand_note and is_value_ref(res.get("note")):
        target_note = _resolve_deref_chain(snapshot, res["note"], seen_refs)
        if isinstance(target_note, dict):
            res["note"] = _expand_note_version_body(target_note, snapshot, seen_refs)
        else:
            res["note"] = copy.deepcopy(target_note)

    if should_expand_event and is_value_ref(res.get("note_event")):
        target_evt = _resolve_deref_chain(snapshot, res["note_event"], seen_refs)
        if isinstance(target_evt, dict):
            res["note_event"] = _expand_note_event_body(target_evt, snapshot, seen_refs)
        else:
            res["note_event"] = copy.deepcopy(target_evt)

    return res


def _expand_receipt(rcpt: Dict[str, Any], snapshot: Dict[str, Any], seen_refs: Set[Tuple[str, str]]) -> Dict[str, Any]:
    res = copy.deepcopy(rcpt)
    op_name = rcpt.get("operation_name")
    projected_slots = rcpt.get("projected_slots")

    # 1. operation_result
    if is_value_ref(res.get("operation_result")):
        should_expand = False
        if projected_slots is not None:
            should_expand = "operation_result" in projected_slots
        else:
            eref = res["operation_result"].get("$value_ref", {}).get("entity_ref", {})
            ekind = eref.get("kind")
            should_expand = ekind in ("operation_result", "artifact")

        if should_expand:
            resolved_op = _resolve_deref_chain(snapshot, res["operation_result"], seen_refs)
            if isinstance(resolved_op, dict):
                res["operation_result"] = _expand_operation_result_body(
                    resolved_op, snapshot, op_name, seen_refs, projected_slots=projected_slots
                )
            else:
                res["operation_result"] = copy.deepcopy(resolved_op)
    elif isinstance(res.get("operation_result"), dict):
        res["operation_result"] = _expand_operation_result_body(
            res["operation_result"], snapshot, op_name, seen_refs, projected_slots=projected_slots
        )

    # 2. note_event
    if is_value_ref(res.get("note_event")):
        should_expand = False
        if projected_slots is not None:
            should_expand = "note_event" in projected_slots
        else:
            eref = res["note_event"].get("$value_ref", {}).get("entity_ref", {})
            ekind = eref.get("kind")
            should_expand = ekind == "note_event"

        if should_expand:
            resolved_evt = _resolve_deref_chain(snapshot, res["note_event"], seen_refs)
            if isinstance(resolved_evt, dict):
                res["note_event"] = _expand_note_event_body(resolved_evt, snapshot, seen_refs)
            else:
                res["note_event"] = copy.deepcopy(resolved_evt)

    # 3. verification_report
    if is_value_ref(res.get("verification_report")):
        should_expand = False
        if projected_slots is not None:
            should_expand = "verification_report" in projected_slots
        else:
            eref = res["verification_report"].get("$value_ref", {}).get("entity_ref", {})
            ekind = eref.get("kind")
            should_expand = ekind == "verification_report"

        if should_expand:
            res["verification_report"] = copy.deepcopy(_resolve_deref_chain(snapshot, res["verification_report"], seen_refs))

    return res


def expand_value_refs(
    target: Any,
    snapshot: Dict[str, Any],
    *,
    allowed_slots: Optional[Set[str]] = None,
    current_path: str = "",
    seen_refs: Optional[Set[Tuple[str, str]]] = None,
    root_context: Optional[str] = None,
) -> Any:
    """Expand $value_ref pointers in registered typed projection slots only.

    Derives decoding authority strictly from trusted typed origin:
    1. Known entity types: note_version, note_event, record_work_note operation_result.
    2. Receipts in observed_state.receipts.
    3. Raw payloads, unknown plugin results, proposal state, and obligations remain literal.
    """
    current_seen = set(seen_refs) if seen_refs is not None else set()

    if not isinstance(target, dict):
        return copy.deepcopy(target)

    # 1. Whole snapshot expansion
    if target is snapshot or root_context == "snapshot":
        snap_copy = copy.deepcopy(target)
        if "observed_state" in snap_copy and "receipts" in snap_copy["observed_state"]:
            snap_copy["observed_state"]["receipts"] = [
                _expand_receipt(r, snapshot, current_seen)
                for r in snap_copy["observed_state"]["receipts"]
            ]
        expanded_entities = []
        for e in snap_copy.get("entities", []):
            e_copy = copy.deepcopy(e)
            kind = e_copy.get("ref", {}).get("kind")
            if kind == "note_version" and e_copy.get("issuer") == "notebook":
                e_copy["body"] = _expand_note_version_body(e_copy.get("body", {}), snapshot, current_seen)
            elif kind == "note_event" and e_copy.get("issuer") == "notebook":
                e_copy["body"] = _expand_note_event_body(e_copy.get("body", {}), snapshot, current_seen)
            elif kind == "operation_result":
                owning_rcpt = _find_receipt_for_operation_result(snapshot, e_copy.get("ref", {}))
                op_name = owning_rcpt.get("operation_name") if owning_rcpt else None
                rcpt_proj = owning_rcpt.get("projected_slots") if owning_rcpt else None
                e_copy["body"] = _expand_operation_result_body(
                    e_copy.get("body", {}), snapshot, op_name, current_seen, projected_slots=rcpt_proj
                )
            expanded_entities.append(e_copy)
        snap_copy["entities"] = expanded_entities
        return snap_copy

    # Literal security boundaries: Proposal and runtime obligations remain strictly literal.
    if target.get("authority") == "model_proposed":
        return copy.deepcopy(target)
    if "contract" in target and "status" in target and "authority" in target:
        return copy.deepcopy(target)

    # 2. Receipt
    if root_context == "receipt" or any(
            target is receipt for receipt in snapshot.get("observed_state", {}).get("receipts", [])):
        return _expand_receipt(target, snapshot, current_seen)

    # 3. Entity envelope
    if root_context == "entity" or any(target is entity for entity in snapshot.get("entities", [])):
        res_ent = copy.deepcopy(target)
        kind = target["ref"]["kind"]
        if kind == "note_version" and target.get("issuer") == "notebook":
            res_ent["body"] = _expand_note_version_body(target["body"], snapshot, current_seen)
        elif kind == "note_event" and target.get("issuer") == "notebook":
            res_ent["body"] = _expand_note_event_body(target["body"], snapshot, current_seen)
        elif kind == "operation_result":
            owning_rcpt = _find_receipt_for_operation_result(snapshot, target.get("ref", {}))
            op_name = owning_rcpt.get("operation_name") if owning_rcpt else None
            rcpt_proj = owning_rcpt.get("projected_slots") if owning_rcpt else None
            res_ent["body"] = _expand_operation_result_body(
                target["body"], snapshot, op_name, current_seen, projected_slots=rcpt_proj
            )
        return res_ent

    # 4. A body inherits its canonical envelope's typed origin only by object
    # identity. Equal values or familiar raw keys never authorize decoding.
    # A caller restoring a serialized typed root can pass root_context explicitly.
    ctx = root_context
    if ctx is None:
        for ent in snapshot.get("entities", []):
            if ent.get("body") is target:
                kind = ent.get("ref", {}).get("kind")
                ctx = kind if ent.get("issuer") == "notebook" else "raw"
                break

    if ctx == "note_version":
        return _expand_note_version_body(target, snapshot, current_seen)
    if ctx == "note_event":
        return _expand_note_event_body(target, snapshot, current_seen)
    if ctx == "operation_result":
        return copy.deepcopy(target)

    # Standalone $value_ref if caller explicitly authorized slot
    if is_value_ref(target):
        if current_path in AUTHORIZED_PROJECTOR_PATHS or (allowed_slots and current_path in allowed_slots):
            return copy.deepcopy(_resolve_deref_chain(snapshot, target, current_seen))
        return copy.deepcopy(target)

    # 5. Fallback: literal/untrusted data
    return copy.deepcopy(target)


def validate_value_refs(snapshot: Dict[str, Any]) -> List[str]:
    """Validate that all $value_ref pointers in authorized typed projection slots resolve cleanly without cycles."""
    errors: List[str] = []
    entities = snapshot.get("entities", [])
    edges = iter_projector_edges(snapshot)

    # 1. Structural resolution check
    for loc, vref_obj in edges:
        vref = vref_obj.get("$value_ref", {})
        eref = vref.get("entity_ref", {})
        ptr = vref.get("pointer", "")
        slot = loc[2]

        target_ent = find_entity(entities, eref)
        if target_ent is None:
            unavail = [
                u for u in snapshot.get("unavailable_refs", [])
                if u.get("ref") == eref
            ]
            if not unavail:
                errors.append(f"Broken value_ref at '{slot}': entity {eref} not found in entities or unavailable_refs")
        else:
            try:
                resolve_json_pointer(target_ent.get("body", {}), ptr)
            except Exception as exc:
                errors.append(f"Broken pointer '{ptr}' at '{slot}': {exc}")

    # 2. Follow exactly the same typed edges as the decoder. Structural
    # resolution above permits explicit unavailable refs; those are unresolved
    # data, while only an actual typed cycle is a cycle validation failure.
    for _, vref_obj in edges:
        try:
            _resolve_deref_chain(snapshot, vref_obj, set())
        except ValueError as exc:
            if "Dereference cycle detected" in str(exc):
                errors.append(f"Cycle detected in value_ref graph: {exc}")

    return errors


# ---------------------------------------------------------------------------
# Provisional progress assessment via existing reconciler
# ---------------------------------------------------------------------------


def _compute_provisional_progress(
    contract: Optional[Union[TurnContract, Dict[str, Any]]],
    journal: Optional[ExecutionJournal],
    *,
    notebook_snapshot: Optional[List[Dict[str, Any]]] = None,
    store: Optional[Any] = None,
    conversation_id: str = "conv-default",
    turn_id: str = "turn-default",
    execution_id: str = "exec-default",
    generation: int = 0,
) -> Dict[str, Any]:
    """Compute observed_state.progress using existing completion reconciler.
    
    Adheres strictly to Package B assignment decisions:
    - Only global matched receipt evidence is reported; no invented outcome-to-receipt map.
    - Eligible contracts: valid, non-empty, intent_coverage not in ('unchecked', 'invalid'), and no validation errors.
    - Non-response outcomes not in unmet set are provisionally 'met' at the snapshot boundary.
    - Response outcomes remain 'pending_response'.
    - Ineligible contracts remain 'unresolved'.
    - Canonical dict exports retain their is_valid/validation_errors/intent_coverage metadata.
    - No terminal lifecycle, summary, or declared_scope_completion copied into progress.
    """
    turn_contract: Optional[TurnContract] = None
    if isinstance(contract, TurnContract):
        turn_contract = contract
    elif isinstance(contract, dict):
        turn_contract = TurnContract.from_dict(contract)
        # Preserve canonical runtime validity and errors from dict exports
        if "is_valid" in contract:
            object.__setattr__(turn_contract, "is_valid", bool(contract["is_valid"]))
        if "validation_errors" in contract:
            object.__setattr__(turn_contract, "validation_errors", tuple(contract["validation_errors"]))
        if "intent_coverage" in contract:
            object.__setattr__(turn_contract, "intent_coverage", str(contract["intent_coverage"]))
        if contract.get("frozen"):
            turn_contract.freeze()

    active_journal = journal
    if active_journal is None:
        active_journal = ExecutionJournal(
            conversation_id=turn_contract.conversation_id if turn_contract else conversation_id,
            turn_id=turn_contract.turn_id if turn_contract else turn_id,
            execution_id=turn_contract.execution_id if turn_contract else execution_id,
            generation=generation,
            receipts=[],
        )

    # Run existing pure reconciler
    recon: TurnReconciliation = reconcile_turn(
        turn_contract,
        active_journal,
        lifecycle="in_progress",
        final_answer="",
        notebook_snapshot=notebook_snapshot,
        store=store,
    )
    report = recon.to_dict()

    eligible = bool(
        turn_contract
        and turn_contract.is_valid
        and turn_contract.intent_coverage not in ("unchecked", "invalid")
        and bool(turn_contract.outcomes)
        and not getattr(turn_contract, "validation_errors", ())
    )

    unmet = {u["outcome_id"]: u for u in report.get("unmet_outcomes", [])}
    rows: List[Dict[str, Any]] = []

    if turn_contract and turn_contract.outcomes:
        for o in turn_contract.outcomes:
            if not eligible:
                state, reason = "unresolved", "contract_not_eligible_for_provisional_match"
            elif o.kind == "response":
                state = "pending_response"
                reason = unmet.get(o.outcome_id, {}).get("reason", "final_response_pending")
            elif o.outcome_id in unmet:
                state = "pending"
                reason = unmet[o.outcome_id]["reason"]
            else:
                state = "met"
                reason = "matched_by_joint_reconciler_at_snapshot_boundary"
            rows.append({"outcome_id": o.outcome_id, "status": state, "reason": reason})

    return {
        "assessment": "provisional",
        "matcher": "existing_completion_reconciler",
        "outcomes": rows,
        "final_response_pending": True,
        "evidence": {
            "intent_coverage": report.get("intent_coverage", "unchecked"),
            "scoped_quality": report.get("scoped_quality", "not_checked"),
            "matched_receipts": copy.deepcopy(report.get("matched_receipts", [])),
            "unmet_outcomes": copy.deepcopy(report.get("unmet_outcomes", [])),
            "unresolved_reasons": copy.deepcopy(report.get("unresolved_reasons", [])),
        },
    }


# ---------------------------------------------------------------------------
# Entity and index builders
# ---------------------------------------------------------------------------


def _normalize_artifact(art: Any) -> Dict[str, Any]:
    if hasattr(art, "to_dict"):
        return art.to_dict()
    if isinstance(art, dict):
        return copy.deepcopy(art)
    raise TypeError(f"Unsupported artifact type: {type(art).__name__}")


def _build_artifact_entities(
    artifact_items: Sequence[Any],
    conversation_id: str,
    turn_id: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    entities: List[Dict[str, Any]] = []
    pins: List[Dict[str, Any]] = []

    for item in artifact_items:
        art_dict = _normalize_artifact(item)
        art_id = str(art_dict["id"])
        rev = int(art_dict.get("revision", 1))
        kind = str(art_dict.get("kind", "artifact"))
        owner_turn = str(art_dict.get("owner_turn_id") or (art_dict.get("provenance", {}) or {}).get("owner_turn_id") or turn_id)

        ref = {
            "kind": "artifact",
            "conversation_id": conversation_id,
            "artifact_id": art_id,
            "revision": rev,
        }
        pins.append(ref)

        if kind == "document_search":
            authority = "observed_search_metadata"
        elif kind == "document_content":
            authority = "observed_source_content"
        elif kind == "calculation":
            authority = "observed_calculation_result"
        else:
            authority = f"observed_{kind}"

        # Preserve all canonical metadata (status, provenance, created_at, inputs, payload, title)
        body = copy.deepcopy(art_dict)
        body["id"] = art_id
        body["kind"] = kind
        body["revision"] = rev
        body["owner_turn_id"] = owner_turn
        if "fields" not in body:
            body["fields"] = copy.deepcopy(art_dict.get("fields") or (list(art_dict.get("payload", {}).keys()) if isinstance(art_dict.get("payload"), dict) else []))
        if "visible" not in body:
            body["visible"] = bool(art_dict.get("visible", False))

        entities.append({
            "ref": ref,
            "authority": authority,
            "issuer": "artifact_store",
            "owner_turn_id": owner_turn,
            "projection_status": "lossless",
            "body": body,
        })

    return entities, pins


def _build_note_entities(
    active_notes: Sequence[Dict[str, Any]],
    historical_notes: Sequence[Dict[str, Any]],
    conversation_id: str,
    turn_id: str,
    artifact_entities: Sequence[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    entities: List[Dict[str, Any]] = []
    active_pins: List[Dict[str, Any]] = []
    historical_pins: List[Dict[str, Any]] = []

    seen_versions: Set[Tuple[str, int]] = set()
    combined_notes: List[Tuple[Dict[str, Any], bool]] = []

    for n in active_notes:
        key = (str(n["id"]), int(n["revision"]))
        if key not in seen_versions:
            seen_versions.add(key)
            combined_notes.append((n, True))

    for n in historical_notes:
        key = (str(n["id"]), int(n["revision"]))
        if key not in seen_versions:
            seen_versions.add(key)
            combined_notes.append((n, False))

    for raw_note, is_active in combined_notes:
        note_id = str(raw_note["id"])
        rev = int(raw_note["revision"])
        owner_turn = str(raw_note.get("owner_turn_id") or turn_id)

        ref = {
            "kind": "note_version",
            "conversation_id": conversation_id,
            "note_id": note_id,
            "revision": rev,
        }
        if is_active:
            active_pins.append(ref)
        else:
            historical_pins.append(ref)

        confirmed = bool(raw_note.get("confirmed", False))
        source = str(raw_note.get("source", "user_quote"))
        if confirmed:
            if source in ("user_quote", "user_message", "user_note", "user_edit"):
                authority = "confirmed_user_fact"
            elif source in ("artifact_result", "user_confirmed"):
                authority = "observed_result"
            else:
                authority = "confirmed_note"
        else:
            authority = "unconfirmed_model_suggestion"

        body = copy.deepcopy(raw_note)
        body["id"] = note_id
        body["revision"] = rev
        body["owner_turn_id"] = owner_turn

        notes_map = {(str(n["id"]), int(n["revision"])): n for n, _ in combined_notes}

        # Link quote to artifact entity via $value_ref ONLY when type and whitespace match EXACTLY
        sref = raw_note.get("source_ref")
        if isinstance(sref, dict) and sref.get("artifact_id") and sref.get("artifact_revision") and sref.get("field"):
            target_art_ref = {
                "kind": "artifact",
                "conversation_id": conversation_id,
                "artifact_id": str(sref["artifact_id"]),
                "revision": int(sref["artifact_revision"]),
            }
            art_ent = find_entity(artifact_entities, target_art_ref)
            field_name = str(sref["field"])
            tokens = [escape_json_pointer_token(t) for t in field_name.split(".")]
            ptr = "/payload/" + "/".join(tokens)
            if art_ent is not None:
                try:
                    val = resolve_json_pointer(art_ent.get("body", {}), ptr)
                    raw_quote = raw_note.get("quote")
                    raw_sref_quote = sref.get("quote")

                    vref = {"$value_ref": {"entity_ref": target_art_ref, "pointer": ptr}}

                    # Exact string type and character equality independently
                    if isinstance(raw_quote, str) and isinstance(val, str) and exact_json_equal(raw_quote, val):
                        body["quote"] = copy.deepcopy(vref)

                    if isinstance(body.get("source_ref"), dict) and isinstance(raw_sref_quote, str) and isinstance(val, str):
                        if exact_json_equal(raw_sref_quote, val):
                            body["source_ref"]["quote"] = copy.deepcopy(vref)
                except Exception:
                    pass

        # Link replacement text to prior/later revision if present and exact
        if raw_note.get("replaces_revision") and raw_note.get("replaces_text") is not None:
            replaces_note_id = str(raw_note.get("replaces_note_id") or note_id)
            replaces_rev = int(raw_note["replaces_revision"])
            target_note = notes_map.get((replaces_note_id, replaces_rev))
            if target_note is not None and exact_json_equal(target_note.get("text"), raw_note.get("replaces_text")):
                target_note_ref = {
                    "kind": "note_version",
                    "conversation_id": conversation_id,
                    "note_id": replaces_note_id,
                    "revision": replaces_rev,
                }
                body["replaces_text"] = {"$value_ref": {"entity_ref": target_note_ref, "pointer": "/text"}}

        if raw_note.get("replaced_by_revision") and raw_note.get("replaced_by_text") is not None:
            replaced_by_note_id = str(raw_note.get("replaced_by_note_id") or note_id)
            replaced_by_rev = int(raw_note["replaced_by_revision"])
            target_note = notes_map.get((replaced_by_note_id, replaced_by_rev))
            if target_note is not None and exact_json_equal(target_note.get("text"), raw_note.get("replaced_by_text")):
                target_note_ref = {
                    "kind": "note_version",
                    "conversation_id": conversation_id,
                    "note_id": replaced_by_note_id,
                    "revision": replaced_by_rev,
                }
                body["replaced_by_text"] = {"$value_ref": {"entity_ref": target_note_ref, "pointer": "/text"}}

        entities.append({
            "ref": ref,
            "authority": authority,
            "issuer": "notebook",
            "owner_turn_id": owner_turn,
            "projection_status": "lossless",
            "body": body,
        })

    return entities, active_pins, historical_pins


def _build_event_entities(
    recent_events: Sequence[Dict[str, Any]],
    conversation_id: str,
    turn_id: str,
    note_entities: Sequence[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    entities: List[Dict[str, Any]] = []
    event_pins: List[Dict[str, Any]] = []

    for raw_evt in recent_events:
        evt = copy.deepcopy(raw_evt)
        evt_id = str(evt["event_id"])
        owner_turn = str(evt.get("owner_turn_id") or turn_id)

        ref = {
            "kind": "note_event",
            "conversation_id": conversation_id,
            "event_id": evt_id,
        }
        event_pins.append(ref)

        # Snapshot in note_event can be projected as $value_ref to the NoteVersion entity
        if evt.get("snapshot") and isinstance(evt["snapshot"], dict) and evt.get("note_id") and evt.get("after_revision"):
            target_note_ref = {
                "kind": "note_version",
                "conversation_id": conversation_id,
                "note_id": str(evt["note_id"]),
                "revision": int(evt["after_revision"]),
            }
            target_ent = find_entity(note_entities, target_note_ref)
            if target_ent is not None and exact_json_equal(target_ent.get("body"), evt["snapshot"]):
                evt["snapshot"] = {"$value_ref": {"entity_ref": target_note_ref, "pointer": ""}}

        entities.append({
            "ref": ref,
            "authority": "runtime_committed_effect",
            "issuer": "notebook",
            "owner_turn_id": owner_turn,
            "projection_status": "lossless",
            "body": evt,
        })

    return entities, event_pins


def _build_journal_entities_and_receipts(
    journal: Optional[ExecutionJournal],
    execution_id: str,
    conversation_id: str,
    turn_id: str,
    generation: int,
    note_entities: Sequence[Dict[str, Any]],
    event_entities: Sequence[Dict[str, Any]],
    artifact_entities: Sequence[Dict[str, Any]] = (),
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    entities: List[Dict[str, Any]] = []
    projected_receipts: List[Dict[str, Any]] = []
    proof_refs: List[Dict[str, Any]] = []

    if journal is None or not journal.receipts:
        return entities, projected_receipts, proof_refs

    for receipt in journal.receipts:
        rcpt_id = receipt.receipt_id
        # Preserve native scope metadata without filling missing/foreign identity with boundary
        rcpt_conv = receipt.conversation_id if receipt.conversation_id else conversation_id
        owner_turn = receipt.turn_id if receipt.turn_id else turn_id
        rcpt_exec = receipt.execution_id if receipt.execution_id else execution_id

        is_current_scope = (
            receipt.conversation_id == conversation_id
            and receipt.turn_id == turn_id
            and receipt.execution_id == execution_id
            and (generation is None or receipt.generation == generation)
        )

        # 1. Operation Result Entity (for operations without an artifact in ArtifactStore)
        has_result_entity = False
        result_pointer = ""
        result_projected_subslots: List[str] = []
        if receipt.operation_result is not None and not receipt.artifact_refs:
            has_result_entity = True
            result_ref = {
                "kind": "operation_result",
                "execution_id": rcpt_exec,
                "receipt_id": rcpt_id,
            }
            raw_res = receipt.operation_result

            # Preserve exact JSON type on roundtrip: wrap scalars/lists in envelope and point to /result
            if isinstance(raw_res, dict):
                res_body = copy.deepcopy(raw_res)
                result_pointer = ""
            else:
                res_body = {"result": copy.deepcopy(raw_res)}
                result_pointer = "/result"

            # Substitute note / note_event only for known trusted operation results where bodies match exactly
            if receipt.operation_name == "record_work_note" and isinstance(res_body, dict):
                if res_body.get("note") and isinstance(res_body["note"], dict) and res_body["note"].get("id") and res_body["note"].get("revision"):
                    target_ref = {
                        "kind": "note_version",
                        "conversation_id": rcpt_conv,
                        "note_id": str(res_body["note"]["id"]),
                        "revision": int(res_body["note"]["revision"]),
                    }
                    target_ent = find_entity(note_entities, target_ref)
                    if target_ent is not None and exact_json_equal(target_ent.get("body"), res_body["note"]):
                        res_body["note"] = {"$value_ref": {"entity_ref": target_ref, "pointer": ""}}
                        result_projected_subslots.append("operation_result.note")

                if res_body.get("note_event") and isinstance(res_body["note_event"], dict) and res_body["note_event"].get("event_id"):
                    target_ref = {
                        "kind": "note_event",
                        "conversation_id": rcpt_conv,
                        "event_id": str(res_body["note_event"]["event_id"]),
                    }
                    target_ent = find_entity(event_entities, target_ref)
                    if target_ent is not None and exact_json_equal(target_ent.get("body"), res_body["note_event"]):
                        res_body["note_event"] = {"$value_ref": {"entity_ref": target_ref, "pointer": ""}}
                        result_projected_subslots.append("operation_result.note_event")

            entities.append({
                "ref": result_ref,
                "authority": "observed_operation_result",
                "issuer": receipt.issuer or "dispatcher",
                "owner_turn_id": owner_turn,
                "projection_status": "lossless",
                "body": res_body,
            })

        # 2. Verification Report Entity
        has_proof_entity = False
        if receipt.issuer == "verification" and receipt.verification_report is not None:
            has_proof_entity = True
            proof_ref = {
                "kind": "verification_report",
                "execution_id": rcpt_exec,
                "receipt_id": rcpt_id,
            }
            # Only current execution receipts become current proof_refs
            if is_current_scope and receipt.committed and receipt.status == "committed":
                proof_refs.append(proof_ref)

            entities.append({
                "ref": proof_ref,
                "authority": "scoped_verification_proof",
                "issuer": "verifier",
                "owner_turn_id": owner_turn,
                "projection_status": "lossless",
                "body": copy.deepcopy(receipt.verification_report),
            })

        # 3. Projected Receipt Header
        header: Dict[str, Any] = {
            "receipt_id": rcpt_id,
            "issuer": receipt.issuer,
            "sequence": receipt.sequence,
            "conversation_id": receipt.conversation_id,
            "turn_id": receipt.turn_id,
            "execution_id": receipt.execution_id,
            "generation": receipt.generation,
            "operation_call_id": receipt.operation_call_id,
            "status": receipt.status,
            "committed": receipt.committed,
            "operation_name": receipt.operation_name,
            "operation_args": copy.deepcopy(receipt.operation_args),
            "operation_result": None,
            "artifact_refs": copy.deepcopy(receipt.artifact_refs),
            "note_event": None,
            "verification_report": None,
            "before_revision": receipt.before_revision,
            "after_revision": receipt.after_revision,
            "parent_receipt_ids": list(receipt.parent_receipt_ids),
            "evidence_hash": receipt.evidence_hash,
            "error": receipt.error,
            "timestamp": receipt.timestamp,
        }
        projected_slots: List[str] = []

        if has_result_entity:
            header["operation_result"] = {
                "$value_ref": {
                    "entity_ref": {
                        "kind": "operation_result",
                        "execution_id": rcpt_exec,
                        "receipt_id": rcpt_id,
                    },
                    "pointer": result_pointer,
                }
            }
            projected_slots.append("operation_result")
            projected_slots.extend(result_projected_subslots)
        elif receipt.operation_result is not None:
            header["operation_result"] = copy.deepcopy(receipt.operation_result)
            if receipt.operation_name == "record_work_note" and isinstance(header["operation_result"], dict):
                if header["operation_result"].get("note") and isinstance(header["operation_result"]["note"], dict) and header["operation_result"]["note"].get("id") and header["operation_result"]["note"].get("revision"):
                    target_ref = {
                        "kind": "note_version",
                        "conversation_id": rcpt_conv,
                        "note_id": str(header["operation_result"]["note"]["id"]),
                        "revision": int(header["operation_result"]["note"]["revision"]),
                    }
                    target_ent = find_entity(note_entities, target_ref)
                    if target_ent is not None and exact_json_equal(target_ent.get("body"), header["operation_result"]["note"]):
                        header["operation_result"]["note"] = {"$value_ref": {"entity_ref": target_ref, "pointer": ""}}
                        projected_slots.append("operation_result.note")

                if header["operation_result"].get("note_event") and isinstance(header["operation_result"]["note_event"], dict) and header["operation_result"]["note_event"].get("event_id"):
                    target_ref = {
                        "kind": "note_event",
                        "conversation_id": rcpt_conv,
                        "event_id": str(header["operation_result"]["note_event"]["event_id"]),
                    }
                    target_ent = find_entity(event_entities, target_ref)
                    if target_ent is not None and exact_json_equal(target_ent.get("body"), header["operation_result"]["note_event"]):
                        header["operation_result"]["note_event"] = {"$value_ref": {"entity_ref": target_ref, "pointer": ""}}
                        projected_slots.append("operation_result.note_event")

            # A dispatcher receipt can point to its exact committed artifact
            # payload once. Equal text without the explicit version pin is
            # never sufficient to merge observations or provenance.
            if len(receipt.artifact_refs) == 1:
                pin = receipt.artifact_refs[0]
                art_ref = {'kind': 'artifact', 'conversation_id': rcpt_conv,
                           'artifact_id': pin.get('artifact_id', pin.get('id')),
                           'revision': pin.get('revision')}
                target = find_entity(artifact_entities, art_ref)
                payload = target.get('body', {}).get('payload') if target else None
                pointer = None
                if target and exact_json_equal(payload, receipt.operation_result):
                    pointer = '/payload'
                elif (target and not isinstance(receipt.operation_result, dict)
                      and isinstance(payload, dict) and set(payload) == {'items'}
                      and exact_json_equal(payload['items'], receipt.operation_result)):
                    pointer = '/payload/items'
                if pointer is not None:
                    header['operation_result'] = {'$value_ref': {'entity_ref': art_ref, 'pointer': pointer}}
                    projected_slots.append("operation_result")

        if receipt.note_event and isinstance(receipt.note_event, dict) and receipt.note_event.get("event_id"):
            evt_ref = {
                "kind": "note_event",
                "conversation_id": rcpt_conv,
                "event_id": str(receipt.note_event["event_id"]),
            }
            target_evt = find_entity(event_entities, evt_ref)
            if target_evt is not None and exact_json_equal(target_evt.get("body"), receipt.note_event):
                header["note_event"] = {"$value_ref": {"entity_ref": evt_ref, "pointer": ""}}
                projected_slots.append("note_event")
            else:
                header["note_event"] = copy.deepcopy(receipt.note_event)
        elif receipt.note_event is not None:
            header["note_event"] = copy.deepcopy(receipt.note_event)

        if has_proof_entity:
            header["verification_report"] = {
                "$value_ref": {
                    "entity_ref": {
                        "kind": "verification_report",
                        "execution_id": rcpt_exec,
                        "receipt_id": rcpt_id,
                    },
                    "pointer": "",
                }
            }
            projected_slots.append("verification_report")
        elif receipt.verification_report is not None:
            header["verification_report"] = copy.deepcopy(receipt.verification_report)

        header["projected_slots"] = projected_slots
        projected_receipts.append(header)

    return entities, projected_receipts, proof_refs


# ---------------------------------------------------------------------------
# Core Pure Compiler
# ---------------------------------------------------------------------------


def compile_context_snapshot(
    view: str,
    *,
    conversation_id: str,
    turn_id: str,
    execution_id: str,
    generation: int,
    artifact_store_generation: int,
    note_event_cursor: int,
    current_query: str,
    message_ref: Optional[str] = None,
    history_message_refs: Optional[List[str]] = None,
    turn_refs: Optional[List[Dict[str, Any]]] = None,
    confirmed_constraint_refs: Optional[List[Dict[str, Any]]] = None,
    task_state: Optional[Dict[str, Any]] = None,
    turn_contract: Optional[Union[TurnContract, Dict[str, Any]]] = None,
    execution_journal: Optional[ExecutionJournal] = None,
    lifecycle_state: Optional[Dict[str, Any]] = None,
    artifact_store_items: Optional[Sequence[Any]] = None,
    current_artifact_refs: Optional[Sequence[Dict[str, Any]]] = None,
    selected_artifact_ids: Optional[Sequence[str]] = None,
    selection_set: bool = False,
    notebook_notes: Optional[Sequence[Dict[str, Any]]] = None,
    notebook_history: Optional[Sequence[Dict[str, Any]]] = None,
    recent_events: Optional[Sequence[Dict[str, Any]]] = None,
    candidate_hash: Optional[str] = None,
    snapshot_id: Optional[str] = None,
    unmodeled_observations: Optional[List[Dict[str, Any]]] = None,
    unavailable_refs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Pure functional compiler projecting canonical runtime copies into a context snapshot.
    
    Zero state store mutation, zero Qt dependencies, zero live model calls.
    """
    if view not in VALID_VIEWS:
        raise ValueError(f"Invalid view '{view}'. Must be one of {VALID_VIEWS}")

    snap_id = snapshot_id or f"snap-{uuid4().hex[:12]}"
    raw_artifacts = list(artifact_store_items or [])
    raw_active_notes = list(notebook_notes or [])
    raw_historical_notes = list(notebook_history or [])
    raw_events = list(recent_events or [])

    # 1. Build Entities & Entity Pins
    artifact_entities, artifact_pins = _build_artifact_entities(raw_artifacts, conversation_id, turn_id)
    note_entities, active_note_pins, historical_note_pins = _build_note_entities(
        raw_active_notes, raw_historical_notes, conversation_id, turn_id, artifact_entities
    )
    event_entities, event_pins = _build_event_entities(raw_events, conversation_id, turn_id, note_entities)
    journal_entities, projected_receipts, proof_refs = _build_journal_entities_and_receipts(
        execution_journal, execution_id, conversation_id, turn_id, generation, note_entities, event_entities, artifact_entities
    )

    all_entities = artifact_entities + note_entities + event_entities + journal_entities

    # 2. Boundary
    all_note_pins = active_note_pins + historical_note_pins
    boundary = {
        "snapshot_id": snap_id,
        "conversation_id": conversation_id,
        "turn_id": turn_id,
        "execution_id": execution_id,
        "generation": int(generation),
        "note_event_cursor": int(note_event_cursor),
        "coherence": "validated_copies",
        "artifact_pins": artifact_pins,
        "note_pins": all_note_pins,
        "candidate_hash": candidate_hash,
        "artifact_store_generation": int(artifact_store_generation),
    }

    # 3. Current Request
    msg_ref = message_ref or "messages/current"
    hist_refs = list(history_message_refs or [])
    current_request = {
        "message_ref": msg_ref,
        "history_message_refs": hist_refs,
    }

    # 4. Continuity
    t_refs = copy.deepcopy(turn_refs or [])
    c_refs = copy.deepcopy(confirmed_constraint_refs or [])
    continuity = {
        "turn_refs": t_refs,
        "confirmed_constraint_refs": c_refs,
    }

    # 5. Proposal
    proposal = {
        "authority": "model_proposed",
        "state": copy.deepcopy(task_state),
    }

    # 6. Runtime Obligations
    if view == "planner" and turn_contract is None:
        runtime_obligations = {
            "status": "not_declared",
            "authority": "runtime_default",
            "contract": None,
        }
    elif turn_contract is not None:
        contract_dict = (
            turn_contract.to_dict()
            if hasattr(turn_contract, "to_dict")
            else copy.deepcopy(turn_contract)
        )
        runtime_obligations = {
            "status": "bound",
            "authority": "runtime_bound_model_proposal",
            "contract": contract_dict,
        }
    else:
        runtime_obligations = {
            "status": "not_declared",
            "authority": "runtime_default",
            "contract": None,
        }

    # 7. Observed State & Provisional Progress
    progress = _compute_provisional_progress(
        turn_contract,
        execution_journal,
        notebook_snapshot=raw_active_notes,
        store=raw_artifacts,
        conversation_id=conversation_id,
        turn_id=turn_id,
        execution_id=execution_id,
        generation=generation,
    )

    observed_lifecycle = copy.deepcopy(
        lifecycle_state or {"state": "running", "cancelled": False, "pending_input": None}
    )

    observed_state = {
        "lifecycle": observed_lifecycle,
        "receipts": projected_receipts,
        "proof_refs": proof_refs,
        "progress": progress,
    }

    # 8. Indexes. Items can include historical revisions for reference closure;
    # only caller-declared current pins belong to current/selected results.
    current_pins = (copy.deepcopy(list(current_artifact_refs))
                    if current_artifact_refs is not None else copy.deepcopy(artifact_pins))
    # Selected results preserve selection_set boolean flag
    selected_refs: List[Dict[str, Any]] = []
    if selection_set and selected_artifact_ids:
        for sid in selected_artifact_ids:
            for art_pin in current_pins:
                if art_pin.get("artifact_id") == sid:
                    selected_refs.append(copy.deepcopy(art_pin))
                    break

    # Previous sources: collected from artifact pins and operation result entities
    prev_sources: List[Dict[str, Any]] = copy.deepcopy(artifact_pins)
    for ent in journal_entities:
        if ent.get("ref", {}).get("kind") == "operation_result":
            prev_sources.append(copy.deepcopy(ent["ref"]))

    indexes = {
        "active_notes": active_note_pins,
        "historical_notes": historical_note_pins,
        "previous_sources": prev_sources,
        "current_results": current_pins,
        "selected_results": selected_refs,
        "selection_set": bool(selection_set),
    }

    # 9. Unavailable Refs & Unmodeled Observations
    unavail = copy.deepcopy(unavailable_refs or [])
    unmodeled = copy.deepcopy(unmodeled_observations or [])

    snapshot: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "view": view,
        "boundary": boundary,
        "current_request": current_request,
        "continuity": continuity,
        "proposal": proposal,
        "runtime_obligations": runtime_obligations,
        "observed_state": observed_state,
        "entities": all_entities,
        "indexes": indexes,
        "unavailable_refs": unavail,
        "unmodeled_observations": unmodeled,
    }

    return snapshot


# ---------------------------------------------------------------------------
# Snapshot Validation
# ---------------------------------------------------------------------------


def validate_context_snapshot(snapshot: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a compiled context snapshot against schema and semantic requirements."""
    errors: List[str] = []

    # 1. JSON Schema validation
    validator = get_snapshot_validator()
    for err in validator.iter_errors(snapshot):
        errors.append(f"Schema error at {err.json_path}: {err.message}")

    if errors:
        return False, errors

    # 2. Entity identity uniqueness across entities
    entities = snapshot.get("entities", [])
    seen_entity_refs: Dict[str, Dict[str, Any]] = {}
    for ent in entities:
        ref = ent.get("ref", {})
        ref_key = json.dumps(ref, sort_keys=True)
        if ref_key in seen_entity_refs:
            prev_ent = seen_entity_refs[ref_key]
            if not exact_json_equal(prev_ent.get("body"), ent.get("body")):
                errors.append(f"Conflicting entity body for duplicate identity: {ref}")
            else:
                errors.append(f"Duplicate entity identity found in entities: {ref}")
        seen_entity_refs[ref_key] = ent

    # 3. Structural typed reference closure (must resolve to an inline entity or explicit unavailable_ref)
    entity_ref_keys = set(seen_entity_refs.keys())
    unavailable_ref_keys = {
        json.dumps(u.get("ref", {}), sort_keys=True)
        for u in snapshot.get("unavailable_refs", [])
    }
    known_ref_keys = entity_ref_keys | unavailable_ref_keys

    indexes = snapshot.get("indexes", {})
    for index_name in ("selected_results", "current_results", "previous_sources", "active_notes", "historical_notes"):
        for ref in indexes.get(index_name, []):
            if isinstance(ref, dict):
                rk = json.dumps(ref, sort_keys=True)
                if rk not in known_ref_keys:
                    errors.append(f"Typed reference in indexes.{index_name} not found in entities or unavailable_refs: {ref}")

    boundary = snapshot.get("boundary", {})
    for pin_name in ("artifact_pins", "note_pins"):
        for ref in boundary.get(pin_name, []):
            if isinstance(ref, dict):
                rk = json.dumps(ref, sort_keys=True)
                if rk not in known_ref_keys:
                    errors.append(f"Typed pin in boundary.{pin_name} not found in entities or unavailable_refs: {ref}")

    continuity = snapshot.get("continuity", {})
    for ref in continuity.get("confirmed_constraint_refs", []):
        if isinstance(ref, dict):
            rk = json.dumps(ref, sort_keys=True)
            if rk not in known_ref_keys:
                errors.append(f"Typed reference in continuity.confirmed_constraint_refs not found in entities or unavailable_refs: {ref}")

    observed_state = snapshot.get("observed_state", {})
    for ref in observed_state.get("proof_refs", []):
        if isinstance(ref, dict):
            rk = json.dumps(ref, sort_keys=True)
            if rk not in known_ref_keys:
                errors.append(f"Typed reference in observed_state.proof_refs not found in entities or unavailable_refs: {ref}")
                continue
            entity = find_entity(entities, ref)
            if entity is None:
                # An explicit unavailable ref does not claim an inline proof.
                continue
            proof_receipts = [
                receipt for receipt in observed_state.get("receipts", [])
                if receipt.get("receipt_id") == ref.get("receipt_id")
                and receipt.get("execution_id") == ref.get("execution_id")
            ]
            current_receipts = [
                receipt for receipt in proof_receipts
                if receipt.get("issuer") == "verification"
                and receipt.get("committed") is True
                and receipt.get("status") == "committed"
                and all(receipt.get(key) == boundary.get(key)
                        for key in ("conversation_id", "turn_id", "execution_id", "generation"))
                and is_value_ref(receipt.get("verification_report"))
                and exact_json_equal(receipt["verification_report"]["$value_ref"].get("entity_ref"), ref)
                and receipt["verification_report"]["$value_ref"].get("pointer") == ""
            ]
            if (ref.get("kind") != "verification_report"
                    or ref.get("execution_id") != boundary.get("execution_id")
                    or entity.get("issuer") != "verifier"
                    or entity.get("authority") != "scoped_verification_proof"
                    or entity.get("owner_turn_id") != boundary.get("turn_id")
                    or len(current_receipts) != 1):
                errors.append(f"Current proof ref lacks one committed verification receipt in boundary scope: {ref}")

    # 4. Value ref pointer integrity & cycle detection
    vref_errors = validate_value_refs(snapshot)
    if vref_errors:
        errors.extend(vref_errors)

    # 5. Semantic invariants
    conv_id = boundary.get("conversation_id")
    if not conv_id:
        errors.append("Boundary conversation_id cannot be empty")

    obligations = snapshot.get("runtime_obligations", {})
    if obligations.get("status") == "bound":
        if obligations.get("contract") is None:
            errors.append("Obligations marked 'bound' but contract is null")
    elif obligations.get("status") == "not_declared":
        if obligations.get("contract") is not None:
            errors.append("Obligations marked 'not_declared' but contract is present")

    progress = snapshot.get("observed_state", {}).get("progress", {})
    if any(k in progress for k in ("summary", "lifecycle", "declared_scope_completion")):
        errors.append("observed_state.progress must not contain terminal summary, lifecycle, or declared_scope_completion")

    for outcome in progress.get("outcomes", []):
        if "receipt_ids" in outcome:
            errors.append(f"Outcome '{outcome.get('outcome_id')}' must not contain receipt_ids; progress must use global evidence only")

    if not isinstance(indexes.get("selection_set"), bool):
        errors.append("indexes.selection_set must be a boolean")

    return len(errors) == 0, errors
