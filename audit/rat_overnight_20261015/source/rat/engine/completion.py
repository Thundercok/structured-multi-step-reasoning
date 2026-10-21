"""rat.engine.completion — Headless completion reconciliation and contract validation.

Implements ADR-003:
- Declared outcome contracts (frozen before first effect, immutable afterwards)
- Strict validation: empty/unknown schema/kind/invalid dependencies marked invalid/unresolved
- Trusted execution journal with structured, deepcopied receipt envelopes
- Producer-consumer dependency matching across artifacts and notes
- Registered effect matching with target_ref, proof lineage, and terminal note verification
- Separation of lifecycle, declared-scope completion, intent coverage, and scoped proof quality
- Zero Qt dependencies. Pure functional reconciler.
"""
from __future__ import annotations

import copy
import ast
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
import time
from types import MappingProxyType
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4


def _freeze_nested(val: Any) -> Any:
    if isinstance(val, Mapping):
        return MappingProxyType({k: _freeze_nested(v) for k, v in val.items()})
    if isinstance(val, (list, tuple)):
        return tuple(_freeze_nested(v) for v in val)
    return val


def _json_value(value: Any) -> Any:
    """Export immutable internal JSON containers without copying mapping proxies."""
    if isinstance(value, Mapping):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _valid_json(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _valid_json(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_valid_json(item) for item in value)
    return value is None or type(value) in (str, bool, int) or (type(value) is float and math.isfinite(value))


def _json_equal(left: Any, right: Any) -> bool:
    # JSON booleans must not compare equal to numbers via Python's bool/int alias.
    left, right = _json_value(left), _json_value(right)
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_json_equal(value, right[key]) for key, value in left.items())
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_json_equal(a, b) for a, b in zip(left, right))
    if type(left) in (int, float) and type(right) in (int, float):
        return left == right
    return type(left) is type(right) and left == right


def _args_match(expected: Optional[Mapping], actual: Mapping, *, skip=()) -> bool:
    return not expected or all(key in actual and _json_equal(value, actual[key]) for key, value in expected.items() if key not in skip)


OUTCOME_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "outcome_id": {"type": "string", "minLength": 1, "maxLength": 100},
        "kind": {"type": "string", "enum": ["response", "registered_effect"]},
        "effect_type": {"type": "string", "minLength": 1, "maxLength": 100},
        "description": {"type": "string", "maxLength": 500},
        "expected_args": {"type": "object"},
        "target_ref": {"type": "object"}, "source_ref": {"type": "object"},
        "dependency_ids": {"type": "array", "items": {"type": "string"}},
        "allow_proposal": {"type": "boolean"},
        "required_proof_scope": {"type": "string", "minLength": 1, "maxLength": 100},
        "required_authority": {"type": "string", "minLength": 1, "maxLength": 100},
    },
    "required": ["outcome_id", "kind"],
}


class OutcomeKind:
    RESPONSE = "response"
    REGISTERED_EFFECT = "registered_effect"
    VALID_KINDS = (RESPONSE, REGISTERED_EFFECT)


@dataclass
class OutcomeSpec:
    """Declared expectation for a turn."""

    outcome_id: str
    kind: str = OutcomeKind.RESPONSE  # "response" | "registered_effect"
    effect_type: Optional[str] = None  # e.g. "calculate", "record_work_note", "select_work_results"
    description: str = ""
    expected_args: Optional[Dict[str, Any]] = None  # Typed arguments expected for the operation
    target_ref: Optional[Dict[str, Any]] = None  # e.g. {"note_id": ..., "expected_revision": ...}
    source_ref: Optional[Dict[str, Any]] = None  # e.g. {"producer_outcome_id": ...} or {"artifact_id": ...}
    dependency_ids: List[str] = field(default_factory=list)
    allow_proposal: bool = False
    required_proof_scope: Optional[str] = None  # e.g. "source_calculation_note", "literal_arithmetic_answer"
    required_authority: Optional[str] = None
    is_valid: bool = True
    validation_error: Optional[str] = None

    def __post_init__(self):
        object.__setattr__(self, "_frozen", False)
        errors = []
        if not isinstance(self.outcome_id, str) or not self.outcome_id:
            errors.append("invalid_outcome_id")
        if not isinstance(self.kind, str) or self.kind not in OutcomeKind.VALID_KINDS:
            errors.append(f"invalid_outcome_kind:{self.kind}")
        if self.kind == OutcomeKind.REGISTERED_EFFECT and (not isinstance(self.effect_type, str) or not self.effect_type):
            errors.append("invalid_effect_type")
        for name in ("expected_args", "source_ref", "target_ref"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, Mapping) or not _valid_json(value)):
                errors.append(f"invalid_{name}")
        for ref in (self.source_ref, self.target_ref):
            if isinstance(ref, Mapping):
                for key in ("artifact_id", "id", "note_id", "producer_outcome_id", "field"):
                    if key in ref and (not isinstance(ref[key], str) or not ref[key]):
                        errors.append(f"invalid_reference_{key}")
                for key in ("revision", "artifact_revision", "expected_revision"):
                    if key in ref and (type(ref[key]) is not int or ref[key] < 1):
                        errors.append(f"invalid_reference_{key}")
        if not isinstance(self.dependency_ids, (list, tuple)) or not all(isinstance(dep, str) and dep for dep in self.dependency_ids):
            errors.append("invalid_dependency_ids")
        if type(self.allow_proposal) is not bool:
            errors.append("invalid_allow_proposal")
        for name in ("required_proof_scope", "required_authority"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value):
                errors.append(f"invalid_{name}")
        if errors:
            self.is_valid = False
            self.validation_error = ";".join(errors)

    def freeze(self) -> None:
        object.__setattr__(self, "_frozen", True)
        if isinstance(self.dependency_ids, (list, tuple)):
            object.__setattr__(self, "dependency_ids", _freeze_nested(self.dependency_ids))
        if isinstance(self.source_ref, Mapping):
            object.__setattr__(self, "source_ref", _freeze_nested(self.source_ref))
        if isinstance(self.target_ref, Mapping):
            object.__setattr__(self, "target_ref", _freeze_nested(self.target_ref))
        if isinstance(getattr(self, "expected_args", None), Mapping):
            object.__setattr__(self, "expected_args", _freeze_nested(self.expected_args))

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_frozen", False) and not name.startswith("_"):
            raise RuntimeError(f"Cannot mutate frozen OutcomeSpec attribute '{name}'")
        super().__setattr__(name, value)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome_id": self.outcome_id,
            "kind": self.kind,
            "effect_type": self.effect_type,
            "description": self.description,
            "expected_args": _json_value(self.expected_args),
            "target_ref": _json_value(self.target_ref),
            "source_ref": _json_value(self.source_ref),
            "dependency_ids": _json_value(self.dependency_ids),
            "allow_proposal": self.allow_proposal,
            "required_proof_scope": self.required_proof_scope,
            "required_authority": self.required_authority,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> OutcomeSpec:
        raw_allow = data.get("allow_proposal", False)
        allow_prop = {"true": True, "false": False, "1": True, "0": False}.get(raw_allow.lower(), raw_allow) if isinstance(raw_allow, str) else raw_allow

        raw_kind = data.get("kind", OutcomeKind.RESPONSE)
        spec = cls(
            outcome_id=data.get("outcome_id", "out-" + uuid4().hex[:8]),
            kind=raw_kind,
            effect_type=data.get("effect_type"),
            description=str(data.get("description") or ""),
            expected_args=copy.deepcopy(data.get("expected_args")),
            target_ref=copy.deepcopy(data.get("target_ref")),
            source_ref=copy.deepcopy(data.get("source_ref")),
            dependency_ids=copy.deepcopy(data.get("dependency_ids", [])),
            allow_proposal=allow_prop,
            required_proof_scope=data.get("required_proof_scope"),
            required_authority=data.get("required_authority"),
        )
        return spec


@dataclass
class TurnContract:
    """Pre-execution obligations. Frozen before the first side-effect and immutable thereafter."""

    schema_version: str = "1.0"
    contract_id: str = field(default_factory=lambda: "contract-" + uuid4().hex[:12])
    conversation_id: str = "conv-default"
    turn_id: str = "turn-default"
    execution_id: str = "exec-default"
    generation: Optional[int] = None
    proposed_by: str = "model"  # "model_planner" | "model_decision" | "fixture" | "unspecified"
    source_message_refs: List[str] = field(default_factory=list)
    outcomes: Any = field(default_factory=list)
    intent_coverage: str = "model_proposed"  # "model_proposed" | "ambiguous" | "invalid" | "unchecked"
    frozen: bool = False
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)

    def __post_init__(self):
        # Validate schema_version
        if self.schema_version != "1.0":
            self.is_valid = False
            self.validation_errors.append(f"unsupported_schema_version:{self.schema_version}")
            self.intent_coverage = "invalid"

        # Validate outcomes collection
        if not isinstance(self.outcomes, (list, tuple)):
            self.is_valid = False
            self.validation_errors.append(f"malformed_outcomes:{type(self.outcomes).__name__}")
            self.intent_coverage = "invalid"
            self.outcomes = []
            return

        outcome_ids = set()
        validated_outcomes = []
        for o in self.outcomes:
            if not isinstance(o, OutcomeSpec):
                self.is_valid = False
                self.validation_errors.append(f"malformed_outcome_spec:{type(o).__name__}")
                self.intent_coverage = "invalid"
                continue
            validated_outcomes.append(o)
            if not getattr(o, "is_valid", True):
                self.is_valid = False
                self.validation_errors.append(getattr(o, "validation_error", "invalid_outcome"))
                self.intent_coverage = "invalid"
                continue
            if o.outcome_id in outcome_ids:
                self.is_valid = False
                self.validation_errors.append(f"duplicate_outcome_id:{o.outcome_id}")
                self.intent_coverage = "invalid"
            outcome_ids.add(o.outcome_id)

        self.outcomes = validated_outcomes

        # Validate dependencies & detect DAG cycles
        graph: Dict[str, Set[str]] = {}
        for o in self.outcomes:
            if not o.is_valid:
                continue
            producer = (o.source_ref or {}).get("producer_outcome_id")
            if producer and producer not in o.dependency_ids:
                self.is_valid = False
                self.validation_errors.append(f"source_producer_missing_dependency:{producer}")
                self.intent_coverage = "invalid"
            for dep in o.dependency_ids:
                if dep not in outcome_ids:
                    self.is_valid = False
                    self.validation_errors.append(f"unknown_dependency:{dep}")
                    self.intent_coverage = "invalid"
            graph[o.outcome_id] = set(o.dependency_ids)

        visited: Dict[str, int] = {}  # 0=unvisited, 1=visiting, 2=visited
        has_cycle = False

        def dfs(node: str) -> bool:
            visited[node] = 1
            for neighbor in graph.get(node, ()):
                if neighbor not in graph:
                    continue
                if visited.get(neighbor) == 1:
                    return True
                if visited.get(neighbor, 0) == 0:
                    if dfs(neighbor):
                        return True
            visited[node] = 2
            return False

        for node in graph:
            if visited.get(node, 0) == 0:
                if dfs(node):
                    has_cycle = True
                    break

        if has_cycle:
            self.is_valid = False
            self.validation_errors.append("dependency_cycle")
            self.intent_coverage = "invalid"

    def freeze(self) -> None:
        for o in self.outcomes:
            if hasattr(o, "freeze"):
                o.freeze()
            else:
                object.__setattr__(o, "_frozen", True)
        object.__setattr__(self, "outcomes", tuple(self.outcomes))
        object.__setattr__(self, "source_message_refs", _freeze_nested(self.source_message_refs))
        object.__setattr__(self, "validation_errors", tuple(self.validation_errors))
        object.__setattr__(self, "frozen", True)

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "frozen", False):
            raise RuntimeError(f"Cannot mutate frozen TurnContract attribute '{name}'")
        super().__setattr__(name, value)

    def is_empty(self) -> bool:
        return len(self.outcomes) == 0

    def add_outcome(self, outcome: OutcomeSpec) -> None:
        if self.frozen:
            raise RuntimeError("Cannot add outcome to frozen contract")
        outcomes_list = list(self.outcomes)
        outcomes_list.append(outcome)
        self.outcomes = outcomes_list

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "contract_id": self.contract_id,
            "conversation_id": self.conversation_id,
            "turn_id": self.turn_id,
            "execution_id": self.execution_id,
            "generation": self.generation,
            "proposed_by": self.proposed_by,
            "source_message_refs": list(self.source_message_refs),
            "outcomes": [o.to_dict() for o in self.outcomes],
            "intent_coverage": self.intent_coverage,
            "frozen": self.frozen,
            "is_valid": self.is_valid,
            "validation_errors": list(self.validation_errors),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TurnContract:
        schema_version = str(data.get("schema_version") or "1.0")
        outcomes_raw = data.get("outcomes")
        if outcomes_raw is None:
            outcomes_raw = []
        outcomes = []
        if isinstance(outcomes_raw, (list, tuple)):
            for o in outcomes_raw:
                if isinstance(o, dict):
                    try:
                        outcomes.append(OutcomeSpec.from_dict(o))
                    except Exception:
                        outcomes.append(o)
                else:
                    outcomes.append(o)
        else:
            outcomes = outcomes_raw

        is_valid = True
        val_errors: List[str] = []
        intent_cov = str(data.get("intent_coverage") or ("model_proposed" if outcomes else "unchecked"))

        if schema_version != "1.0":
            is_valid = False
            val_errors.append(f"unsupported_schema_version:{schema_version}")
            intent_cov = "invalid"

        if isinstance(outcomes, (list, tuple)):
            for o in outcomes:
                if not getattr(o, "is_valid", True):
                    is_valid = False
                    val_errors.append(getattr(o, "validation_error", "invalid_outcome"))
                    intent_cov = "invalid"

        contract = cls(
            schema_version=schema_version,
            contract_id=str(data.get("contract_id") or "contract-" + uuid4().hex[:12]),
            conversation_id=str(data.get("conversation_id") or "conv-default"),
            turn_id=str(data.get("turn_id") or "turn-default"),
            execution_id=str(data.get("execution_id") or "exec-default"),
            generation=data.get("generation"),
            proposed_by=str(data.get("proposed_by") or "model"),
            source_message_refs=list(data.get("source_message_refs") or []),
            outcomes=outcomes,
            intent_coverage=intent_cov,
            frozen=False,  # Model cannot forge frozen state; runtime freezes explicitly
            is_valid=is_valid,
            validation_errors=val_errors,
        )
        return contract


@dataclass
class ReceiptEnvelope:
    """Authoritative execution receipt emitted by runtime components."""

    receipt_id: str = field(default_factory=lambda: "rcpt-" + uuid4().hex[:12])
    issuer: str = "runtime"  # "dispatcher" | "notebook" | "verification" | "artifact_store"
    sequence: int = 0
    conversation_id: str = ""
    turn_id: str = ""
    execution_id: str = ""
    generation: Optional[int] = None
    operation_call_id: Optional[str] = None
    status: str = "committed"  # "committed" | "error" | "cancelled" | "needs_input"
    committed: bool = True
    operation_name: Optional[str] = None
    operation_args: Optional[Dict[str, Any]] = None
    operation_result: Any = None
    artifact_refs: List[Dict[str, Any]] = field(default_factory=list)
    note_event: Optional[Dict[str, Any]] = None
    verification_report: Optional[Dict[str, Any]] = None
    before_revision: Optional[int] = None
    after_revision: Optional[int] = None
    parent_receipt_ids: List[str] = field(default_factory=list)
    evidence_hash: Optional[str] = None
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "issuer": self.issuer,
            "sequence": self.sequence,
            "conversation_id": self.conversation_id,
            "turn_id": self.turn_id,
            "execution_id": self.execution_id,
            "generation": self.generation,
            "operation_call_id": self.operation_call_id,
            "status": self.status,
            "committed": self.committed,
            "operation_name": self.operation_name,
            "operation_args": copy.deepcopy(self.operation_args) if isinstance(self.operation_args, dict) else self.operation_args,
            "operation_result": copy.deepcopy(self.operation_result) if isinstance(self.operation_result, (dict, list)) else self.operation_result,
            "artifact_refs": copy.deepcopy(self.artifact_refs),
            "note_event": copy.deepcopy(self.note_event) if self.note_event is not None else None,
            "verification_report": copy.deepcopy(self.verification_report) if self.verification_report is not None else None,
            "before_revision": self.before_revision,
            "after_revision": self.after_revision,
            "parent_receipt_ids": list(self.parent_receipt_ids),
            "evidence_hash": self.evidence_hash,
            "error": self.error,
            "timestamp": self.timestamp,
        }


@dataclass
class ExecutionJournal:
    """Request-scoped trusted journal recording all runtime events and receipts."""

    conversation_id: str
    turn_id: str
    execution_id: str
    generation: Optional[int] = None
    receipts: List[ReceiptEnvelope] = field(default_factory=list)
    _seq: int = 0

    def record_operation(
        self,
        operation_name: str,
        args: Dict[str, Any],
        result: Any,
        *,
        status: str = "committed",
        committed: bool = True,
        artifact_refs: Optional[List[Dict[str, Any]]] = None,
        error: Optional[str] = None,
        operation_call_id: Optional[str] = None,
    ) -> ReceiptEnvelope:
        self._seq += 1
        args_copy = copy.deepcopy(args) if isinstance(args, dict) else args
        result_copy = copy.deepcopy(result) if isinstance(result, (dict, list)) else result
        refs_copy = copy.deepcopy(artifact_refs) if artifact_refs else []

        digest = None
        try:
            raw = json.dumps({"op": operation_name, "args": args_copy, "result": result_copy}, sort_keys=True, default=str)
            digest = hashlib.sha256(raw.encode()).hexdigest()
        except Exception:
            pass

        rcpt = ReceiptEnvelope(
            issuer="dispatcher",
            sequence=self._seq,
            conversation_id=self.conversation_id,
            turn_id=self.turn_id,
            execution_id=self.execution_id,
            generation=self.generation,
            operation_call_id=operation_call_id or f"call-{self._seq}",
            status=status,
            committed=committed,
            operation_name=operation_name,
            operation_args=args_copy,
            operation_result=result_copy,
            artifact_refs=refs_copy,
            evidence_hash=digest,
            error=error,
        )
        self.receipts.append(rcpt)
        return rcpt

    def record_note_event(self, event_dict: Dict[str, Any], *, operation_receipt_id: Optional[str] = None) -> ReceiptEnvelope:
        self._seq += 1
        rcpt = ReceiptEnvelope(
            issuer="notebook",
            sequence=self._seq,
            conversation_id=self.conversation_id,
            turn_id=self.turn_id,
            execution_id=self.execution_id,
            generation=self.generation,
            status="committed",
            committed=True,
            operation_name="record_work_note",
            note_event=copy.deepcopy(event_dict),
            before_revision=event_dict.get("before_revision"),
            after_revision=event_dict.get("after_revision"),
            parent_receipt_ids=[operation_receipt_id] if operation_receipt_id else [],
        )
        self.receipts.append(rcpt)
        return rcpt

    def record_verification(self, report_dict: Dict[str, Any], *, operation_receipt_id: Optional[str] = None,
                            candidate_answer: Optional[str] = None) -> ReceiptEnvelope:
        self._seq += 1
        rcpt = ReceiptEnvelope(
            issuer="verification",
            sequence=self._seq,
            conversation_id=self.conversation_id,
            turn_id=self.turn_id,
            execution_id=self.execution_id,
            generation=self.generation,
            status="committed",
            committed=True,
            verification_report=copy.deepcopy(report_dict),
            parent_receipt_ids=[operation_receipt_id] if operation_receipt_id else [],
            evidence_hash=hashlib.sha256(candidate_answer.encode()).hexdigest() if candidate_answer is not None else None,
        )
        self.receipts.append(rcpt)
        return rcpt

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "turn_id": self.turn_id,
            "execution_id": self.execution_id,
            "generation": self.generation,
            "receipts": [r.to_dict() for r in self.receipts],
        }


@dataclass
class TurnReconciliation:
    """The honest truth of turn completion based on actual receipts."""

    contract_id: Optional[str] = None
    lifecycle: str = "completed"  # "completed" | "in_progress" | "needs_input" | "failed" | "cancelled"
    intent_coverage: str = "model_proposed"  # "model_proposed" | "ambiguous" | "invalid" | "unchecked"
    declared_scope_completion: str = "satisfied"  # "satisfied" | "partial" | "unresolved" | "unchecked"
    scoped_quality: str = "not_checked"  # "PASS" | "FAIL" | "UNKNOWN" | "not_checked"
    matched_receipts: List[str] = field(default_factory=list)
    unmet_outcomes: List[Dict[str, Any]] = field(default_factory=list)
    unresolved_reasons: List[str] = field(default_factory=list)
    semantic_limitation: str = "Receipt matching validates recorded effects and scoped proofs, but does not prove unverified prose assertions."
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "lifecycle": self.lifecycle,
            "intent_coverage": self.intent_coverage,
            "declared_scope_completion": self.declared_scope_completion,
            "scoped_quality": self.scoped_quality,
            "matched_receipts": list(self.matched_receipts),
            "unmet_outcomes": copy.deepcopy(self.unmet_outcomes),
            "unresolved_reasons": list(self.unresolved_reasons),
            "semantic_limitation": self.semantic_limitation,
            "summary": self.summary,
        }


def topological_sort_outcomes(outcomes: List[OutcomeSpec]) -> Tuple[List[OutcomeSpec], bool]:
    outcome_map = {o.outcome_id: o for o in outcomes}
    in_degree = {o.outcome_id: 0 for o in outcomes}
    dependents: Dict[str, List[str]] = {o.outcome_id: [] for o in outcomes}

    for o in outcomes:
        for dep in o.dependency_ids:
            if dep in outcome_map:
                in_degree[o.outcome_id] += 1
                dependents[dep].append(o.outcome_id)

    queue = [o.outcome_id for o in outcomes if in_degree[o.outcome_id] == 0]
    sorted_ids: List[str] = []

    while queue:
        curr = queue.pop(0)
        sorted_ids.append(curr)
        for dep_id in dependents.get(curr, []):
            in_degree[dep_id] -= 1
            if in_degree[dep_id] == 0:
                queue.append(dep_id)

    has_cycle = len(sorted_ids) < len(outcomes)
    sorted_outcomes = [outcome_map[oid] for oid in sorted_ids]
    if has_cycle:
        for o in outcomes:
            if o.outcome_id not in sorted_ids:
                sorted_outcomes.append(o)
    return sorted_outcomes, has_cycle


@dataclass
class MatchContext:
    producer_artifacts: Dict[str, Dict[str, Any]]
    verification_envelopes: List[ReceiptEnvelope]
    notebook_snapshot: Optional[List[Dict[str, Any]]]
    journal: ExecutionJournal
    store: Optional[Any] = None


def _in_execution(receipt: ReceiptEnvelope, owner: Any) -> bool:
    return (receipt.conversation_id == owner.conversation_id
            and receipt.turn_id == owner.turn_id
            and receipt.execution_id == owner.execution_id
            and (owner.generation is None or receipt.generation == owner.generation))


def _reference(ref: Mapping) -> Dict[str, Any]:
    value = _json_value(ref)
    if "id" in value:
        value.setdefault("artifact_id", value.pop("id"))
    if "artifact_revision" in value:
        value.setdefault("revision", value.pop("artifact_revision"))
    return value


def _source_matches(outcome: OutcomeSpec, actual: Optional[Mapping], context: MatchContext) -> bool:
    if not outcome.source_ref:
        return True
    if actual is None:
        return False  # Unsupported source binding cannot silently satisfy a constraint.
    expected = _reference(outcome.source_ref)
    producer = expected.pop("producer_outcome_id", None)
    if producer:
        produced = context.producer_artifacts.get(producer)
        if not produced:
            return False
        produced = _reference(produced)
        for key in ("artifact_id", "revision"):
            if key not in produced:
                return False
            if key in expected and not _json_equal(expected[key], produced[key]):
                return False
            expected[key] = produced[key]
    return _args_match(expected, _reference(actual))


def _operation_source(receipt: ReceiptEnvelope) -> Optional[Mapping]:
    args = receipt.operation_args or {}
    for name in ("source_result", "source_ref"):
        if isinstance(args.get(name), Mapping):
            return args[name]
    if "artifact_id" in args:
        ref = dict(args)
        # A read may omit a revision and return the version actually resolved.
        result = receipt.operation_result
        if "revision" not in ref and isinstance(result, Mapping) and result.get("artifact_id") == ref["artifact_id"]:
            ref["revision"] = result.get("revision")
        return ref
    return None


def _report_reason(outcome: OutcomeSpec, report: Optional[Mapping]) -> Optional[str]:
    if not outcome.required_proof_scope and not outcome.required_authority:
        return None
    if not report:
        return "missing_proof"
    if outcome.required_proof_scope and report.get("scope") != outcome.required_proof_scope:
        return "unverified_source"
    if report.get("status") != "PASS":
        return "unverified_source"
    if outcome.required_authority and report.get("authority") != outcome.required_authority:
        return "unauthorized_proof"
    return None


def _proof_reason(outcome: OutcomeSpec, envelopes: List[ReceiptEnvelope], *,
                  operation: Optional[ReceiptEnvelope] = None,
                  final_answer: Optional[str] = None) -> Optional[str]:
    if not outcome.required_proof_scope and not outcome.required_authority:
        return None
    candidate_hash = hashlib.sha256(final_answer.encode()).hexdigest() if final_answer is not None else None
    matches = []
    for envelope in envelopes:
        if not envelope.committed or envelope.status != "committed":
            continue
        report = envelope.verification_report or {}
        if outcome.required_proof_scope and report.get("scope") != outcome.required_proof_scope:
            continue
        if operation is not None and not (operation.receipt_id in envelope.parent_receipt_ids
                or (envelope.operation_call_id and envelope.operation_call_id == operation.operation_call_id)):
            continue
        if candidate_hash is not None:
            if envelope.evidence_hash is not None:
                if envelope.evidence_hash != candidate_hash:
                    continue
            elif report.get("evidence_ids") not in (["final-answer"], ("final-answer",)):
                # Explicit legacy trusted marker; native reports use candidate hashes.
                continue
        matches.append(envelope)
    if not matches:
        return "missing_proof"
    return _report_reason(outcome, max(matches, key=lambda envelope: envelope.sequence).verification_report)


class OperationMatchAdapter:
    def match(
        self,
        outcome: OutcomeSpec,
        receipts: List[ReceiptEnvelope],
        used_ids: Set[str],
        context: MatchContext,
    ) -> Tuple[Optional[ReceiptEnvelope], Optional[str]]:
        raise NotImplementedError


class CalculateOperationAdapter(OperationMatchAdapter):
    def match(
        self,
        outcome: OutcomeSpec,
        receipts: List[ReceiptEnvelope],
        used_ids: Set[str],
        context: MatchContext,
    ) -> Tuple[Optional[ReceiptEnvelope], Optional[str]]:
        from rat.engine.verification import literal_request, _normalize_expression

        matched_rcpt = None
        for r in receipts:
            if r.receipt_id in used_ids:
                continue
            if r.operation_name == "calculate" and r.committed and r.status == "committed":
                op_args = r.operation_args or {}
                actual_expr = op_args.get("expression")

                # Typed input / expression binding
                expected_expr = None
                if outcome.expected_args and "expression" in outcome.expected_args:
                    expected_expr = outcome.expected_args["expression"]
                elif outcome.description:
                    lit = literal_request(outcome.description)
                    if lit is not None:
                        expected_expr = lit

                if expected_expr is not None:
                    if not actual_expr:
                        continue
                    try:
                        expected_tree = ast.dump(ast.parse(_normalize_expression(str(expected_expr)), mode="eval"))
                        actual_tree = ast.dump(ast.parse(_normalize_expression(str(actual_expr)), mode="eval"))
                        if expected_tree != actual_tree:
                            continue
                    except Exception:
                        if str(expected_expr).strip().replace(" ", "") != str(actual_expr).strip().replace(" ", ""):
                            continue

                if not _args_match(outcome.expected_args, op_args, skip=("expression",)):
                    continue
                if not _source_matches(outcome, _operation_source(r), context):
                    continue

                # Proof verification check using verification envelopes
                if _proof_reason(outcome, context.verification_envelopes, operation=r):
                    continue

                matched_rcpt = r
                break

        if matched_rcpt is not None:
            used_ids.add(matched_rcpt.receipt_id)
            if matched_rcpt.artifact_refs:
                context.producer_artifacts[outcome.outcome_id] = matched_rcpt.artifact_refs[0]
            return matched_rcpt, None
        return None, "omitted_action"


class RecordWorkNoteAdapter(OperationMatchAdapter):
    def match(
        self,
        outcome: OutcomeSpec,
        receipts: List[ReceiptEnvelope],
        used_ids: Set[str],
        context: MatchContext,
    ) -> Tuple[Optional[ReceiptEnvelope], Optional[str]]:
        note_receipts = [
            r for r in receipts
            if r.issuer == "notebook" and r.committed and r.status == "committed" and r.note_event and r.receipt_id not in used_ids
        ]
        if not note_receipts:
            return None, "omitted_action"

        unmet_reason = "omitted_action"
        matched_rcpt = None

        for r in note_receipts:
            evt = r.note_event or {}
            note_id = evt.get("note_id")
            parent = next((operation for operation in receipts
                           if operation.receipt_id in r.parent_receipt_ids
                           and operation.issuer == "dispatcher" and operation.committed
                           and operation.status == "committed"), None)
            parent_args = (parent.operation_args or {}) if parent else {}
            if not _args_match(outcome.expected_args, parent_args):
                unmet_reason = "input_mismatch"
                continue

            # 1. Obtain terminal note
            terminal_note = None
            if context.notebook_snapshot is not None:
                for n in context.notebook_snapshot:
                    if n.get("id") == note_id:
                        terminal_note = n
                        break
            else:
                all_evts = [
                    rec.note_event for rec in context.journal.receipts
                    if rec.issuer == "notebook" and rec.note_event and rec.note_event.get("note_id") == note_id
                ]
                if all_evts:
                    terminal_note = all_evts[-1].get("snapshot")

            if terminal_note is None or terminal_note.get("status") == "removed":
                unmet_reason = "note_removed"
                continue

            terminal_rev = terminal_note.get("revision")
            rcpt_rev = r.after_revision or evt.get("after_revision") or (evt.get("snapshot") or {}).get("revision")
            if terminal_rev is not None and rcpt_rev is not None and rcpt_rev != terminal_rev:
                unmet_reason = "stale_note_revision"
                continue

            # 2. Proposal / confirmed check on terminal note
            if not outcome.allow_proposal:
                if not terminal_note.get("confirmed", False) or terminal_note.get("status") == "proposed":
                    unmet_reason = "unconfirmed_proposal"
                    continue

            # 3. Source linkage check on terminal note
            terminal_source = terminal_note.get("source_ref") or {}
            if not _source_matches(outcome, terminal_source, context):
                unmet_reason = "wrong_source_consumer"
                continue

            # 4. Target note check
            if outcome.target_ref:
                target_id = outcome.target_ref.get("note_id")
                if target_id and note_id != target_id:
                    unmet_reason = "target_mismatch"
                    continue
                expected_rev = outcome.target_ref.get("expected_revision")
                if expected_rev is not None:
                    before_rev = r.before_revision if r.before_revision is not None else evt.get("before_revision")
                    if before_rev is None or before_rev != expected_rev:
                        unmet_reason = "target_revision_mismatch"
                        continue
                if "text" in outcome.target_ref:
                    if terminal_note.get("text") != outcome.target_ref["text"]:
                        unmet_reason = "target_mismatch"
                        continue

            # 5. Required proof scope and required authority on terminal note
            proof_error = _report_reason(outcome, terminal_note.get("source_verification"))
            if proof_error:
                unmet_reason = proof_error
                continue

            matched_rcpt = r
            break

        if matched_rcpt is not None:
            used_ids.add(matched_rcpt.receipt_id)
            return matched_rcpt, None
        return None, unmet_reason


class GenericOperationAdapter(OperationMatchAdapter):
    def match(
        self,
        outcome: OutcomeSpec,
        receipts: List[ReceiptEnvelope],
        used_ids: Set[str],
        context: MatchContext,
    ) -> Tuple[Optional[ReceiptEnvelope], Optional[str]]:
        matched_rcpt = None
        unmet_reason = "omitted_action"

        for r in receipts:
            if r.receipt_id in used_ids:
                continue
            if r.operation_name == outcome.effect_type and r.committed and r.status == "committed":
                op_args = r.operation_args or {}
                op_res = r.operation_result or {}

                if not _args_match(outcome.expected_args, op_args):
                    unmet_reason = "input_mismatch"
                    continue
                if not _source_matches(outcome, _operation_source(r), context):
                    unmet_reason = "wrong_source_consumer"
                    continue

                if outcome.target_ref:
                    mismatch = False
                    for k, v in outcome.target_ref.items():
                        val = op_args.get(k)
                        if val is None and isinstance(op_res, dict):
                            val = op_res.get(k)
                        if not _json_equal(val, v):
                            mismatch = True
                            break
                    if mismatch:
                        unmet_reason = "target_mismatch"
                        continue

                proof_error = _proof_reason(outcome, context.verification_envelopes, operation=r)
                if proof_error:
                    unmet_reason = proof_error
                    continue

                matched_rcpt = r
                break

        if matched_rcpt is not None:
            used_ids.add(matched_rcpt.receipt_id)
            if matched_rcpt.artifact_refs:
                context.producer_artifacts[outcome.outcome_id] = matched_rcpt.artifact_refs[0]
            return matched_rcpt, None
        return None, unmet_reason


OPERATION_ADAPTERS: Dict[str, OperationMatchAdapter] = {
    "calculate": CalculateOperationAdapter(),
    "record_work_note": RecordWorkNoteAdapter(),
}
DEFAULT_OPERATION_ADAPTER = GenericOperationAdapter()


def register_operation_adapter(op_name: str, adapter: OperationMatchAdapter) -> None:
    OPERATION_ADAPTERS[op_name] = adapter


def get_operation_adapter(op_name: Optional[str]) -> OperationMatchAdapter:
    if op_name and op_name in OPERATION_ADAPTERS:
        return OPERATION_ADAPTERS[op_name]
    return DEFAULT_OPERATION_ADAPTER


def reconcile_turn(
    contract: Optional[TurnContract],
    journal: ExecutionJournal,
    *,
    execution_id: Optional[str] = None,
    lifecycle: str = "completed",
    final_answer: str = "",
    error: Optional[str] = None,
    notebook_snapshot: Optional[List[Dict[str, Any]]] = None,
    store: Optional[Any] = None,
) -> TurnReconciliation:
    """Pure functional reconciliation matching frozen obligations against trusted journal receipts."""
    # 1. Determine scoped quality from verification reports in current execution receipts
    scoped_quality = "not_checked"
    verif_envelopes = [
        r for r in journal.receipts
        if r.issuer == "verification" and r.verification_report is not None
        and r.committed and r.status == "committed"
        and _in_execution(r, contract or journal)
    ]
    if verif_envelopes:
        statuses = [v.verification_report.get("status") for v in verif_envelopes if v.verification_report]
        if any(s == "FAIL" for s in statuses):
            scoped_quality = "FAIL"
        elif any(s == "UNKNOWN" for s in statuses):
            scoped_quality = "UNKNOWN"
        elif all(s == "PASS" for s in statuses):
            scoped_quality = "PASS"

    # 2. Handle missing or unchecked/invalid contract
    if contract is None or contract.intent_coverage in ("unchecked", "invalid") or not getattr(contract, "is_valid", True):
        intent_cov = "invalid" if (contract and (not contract.is_valid or contract.intent_coverage == "invalid")) else "unchecked"
        c_id = contract.contract_id if contract else None
        if lifecycle == "cancelled":
            return TurnReconciliation(
                contract_id=c_id,
                lifecycle="cancelled",
                intent_coverage=intent_cov,
                declared_scope_completion="unresolved",
                scoped_quality=scoped_quality,
                unresolved_reasons=["cancelled_in_flight"],
                summary="Lượt bị dừng trước khi hoàn tất.",
            )
        if lifecycle == "needs_input":
            return TurnReconciliation(
                contract_id=c_id,
                lifecycle="needs_input",
                intent_coverage=intent_cov,
                declared_scope_completion="unresolved",
                scoped_quality=scoped_quality,
                unresolved_reasons=["pending_input_required"],
                summary="Đang chờ thông tin bổ sung từ người dùng.",
            )
        if lifecycle == "failed" or error:
            return TurnReconciliation(
                contract_id=c_id,
                lifecycle="failed",
                intent_coverage=intent_cov,
                declared_scope_completion="unresolved",
                scoped_quality=scoped_quality,
                unresolved_reasons=[error or "execution_failed"],
                summary=f"Thực thi gặp lỗi: {error}",
            )
        # Normal conversational reply with no declared contract or invalid contract
        return TurnReconciliation(
            contract_id=c_id,
            lifecycle="completed",
            intent_coverage=intent_cov,
            declared_scope_completion="unresolved" if intent_cov == "invalid" else "unchecked",
            scoped_quality=scoped_quality,
            summary="Hợp đồng không hợp lệ." if intent_cov == "invalid" else "Câu trả lời hội thoại (chưa khai hợp đồng công việc cụ thể).",
        )

    # 3. Empty contract check
    if not contract.outcomes:
        return TurnReconciliation(
            contract_id=contract.contract_id,
            lifecycle=lifecycle,
            intent_coverage=contract.intent_coverage,
            declared_scope_completion="unresolved",
            scoped_quality=scoped_quality,
            unmet_outcomes=[],
            unresolved_reasons=["empty_contract"],
            summary="Hợp đồng rỗng; không có mục tiêu để xác nhận hoàn thành.",
        )

    # 4. Filter receipts belonging strictly to the current execution, turn, and generation
    current_receipts = [
        r for r in journal.receipts
        if _in_execution(r, contract)
    ]

    # 5. Dependency pre-check and topological outcome matching
    matched_receipts: List[str] = []
    unmet_outcomes: List[Dict[str, Any]] = []
    used_receipt_ids: Set[str] = set()
    producer_artifacts: Dict[str, Dict[str, Any]] = {}

    sorted_outcomes, has_cycle = topological_sort_outcomes(contract.outcomes)
    satisfied_outcome_ids: Set[str] = set()

    match_context = MatchContext(
        producer_artifacts=producer_artifacts,
        verification_envelopes=verif_envelopes,
        notebook_snapshot=notebook_snapshot,
        journal=journal,
        store=store,
    )

    for outcome in sorted_outcomes:
        # Check unknown dependencies
        contract_outcome_ids = {o.outcome_id for o in contract.outcomes}
        unknown_deps = [dep for dep in outcome.dependency_ids if dep not in contract_outcome_ids]
        if unknown_deps:
            unmet_outcomes.append({
                "outcome_id": outcome.outcome_id,
                "reason": "unknown_dependency",
                "description": f"Phụ thuộc {unknown_deps} không tồn tại trong hợp đồng",
            })
            continue

        # Check unmet dependencies against satisfied IDs
        unmet_deps = [dep for dep in outcome.dependency_ids if dep not in satisfied_outcome_ids]
        if unmet_deps:
            unmet_outcomes.append({
                "outcome_id": outcome.outcome_id,
                "reason": "dependency_unmet",
                "description": f"Phụ thuộc {unmet_deps} chưa hoàn thành",
            })
            continue

        if outcome.kind == OutcomeKind.RESPONSE:
            proof_error = _proof_reason(outcome, verif_envelopes, final_answer=final_answer)
            if final_answer.strip() and not proof_error:
                matched_receipts.append(f"response:{contract.turn_id}")
                satisfied_outcome_ids.add(outcome.outcome_id)
            else:
                unmet_outcomes.append({
                    "outcome_id": outcome.outcome_id,
                    "reason": proof_error if final_answer.strip() else "missing_response",
                    "description": outcome.description or "Chưa có phản hồi văn bản",
                })
            continue

        if outcome.kind == OutcomeKind.REGISTERED_EFFECT:
            adapter = get_operation_adapter(outcome.effect_type)
            matched_rcpt, unmet_reason = adapter.match(
                outcome, current_receipts, used_receipt_ids, match_context
            )

            if matched_rcpt is not None:
                matched_receipts.append(matched_rcpt.receipt_id)
                satisfied_outcome_ids.add(outcome.outcome_id)
            else:
                unmet_outcomes.append({
                    "outcome_id": outcome.outcome_id,
                    "reason": unmet_reason,
                    "description": outcome.description or f"Chưa hoàn tất thao tác {outcome.effect_type}",
                })

    # 6. Final reconciliation status
    unresolved_reasons = [u["reason"] for u in unmet_outcomes]

    if lifecycle == "cancelled":
        completion = "unresolved"
        summary = "Lượt bị dừng; các công việc đã khai chưa hoàn thành."
        if "cancelled_in_flight" not in unresolved_reasons:
            unresolved_reasons.insert(0, "cancelled_in_flight")
    elif lifecycle == "needs_input":
        completion = "unresolved"
        summary = "Đang chờ thông tin bổ sung; các công việc giữ trạng thái chờ."
        if "pending_input_required" not in unresolved_reasons:
            unresolved_reasons.insert(0, "pending_input_required")
    elif lifecycle == "failed" or error:
        completion = "unresolved"
        summary = f"Lỗi thực thi: {error}"
        if (error or "execution_failed") not in unresolved_reasons:
            unresolved_reasons.insert(0, error or "execution_failed")
    else:
        # lifecycle == "completed"
        if unmet_outcomes:
            effect_outcomes = [o for o in contract.outcomes if o.kind == OutcomeKind.REGISTERED_EFFECT]
            unmet_effect_ids = {u["outcome_id"] for u in unmet_outcomes}
            met_effect_count = sum(1 for o in effect_outcomes if o.outcome_id not in unmet_effect_ids)

            if not effect_outcomes:
                completion = "unresolved"
                summary = "Chưa hoàn tất công việc yêu cầu; thiếu phản hồi phù hợp."
            else:
                if met_effect_count == len(effect_outcomes):
                    completion = "partial"
                    summary = "Đã hoàn thành các thao tác nhưng thiếu phản hồi."
                elif met_effect_count > 0:
                    completion = "partial"
                    summary = "Chỉ hoàn thành một phần công việc; còn thiếu một số thao tác/ràng buộc."
                else:
                    completion = "unresolved"
                    summary = "Chưa hoàn tất công việc yêu cầu; thiếu biên nhận thực thi."
        else:
            completion = "satisfied"
            effect_outcomes = [o for o in contract.outcomes if o.kind == OutcomeKind.REGISTERED_EFFECT]
            if effect_outcomes:
                summary = "Đã hoàn thành đầy đủ các công việc đã khai và đối chiếu biên nhận."
            else:
                summary = "Đã hoàn thành phản hồi hội thoại."

    return TurnReconciliation(
        contract_id=contract.contract_id,
        lifecycle=lifecycle,
        intent_coverage=contract.intent_coverage,
        declared_scope_completion=completion,
        scoped_quality=scoped_quality,
        matched_receipts=matched_receipts,
        unmet_outcomes=unmet_outcomes,
        unresolved_reasons=unresolved_reasons,
        summary=summary,
    )
