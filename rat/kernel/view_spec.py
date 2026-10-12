"""
rat.kernel.view_spec — Declarative, versioned presentation contracts.

Independent of Qt widgets and AI model inference.
Defines:
- ViewBlock: primitive component vocabulary (summary, table, resource, input_form, actions, details)
- ViewSpec: versioned tree of blocks referencing real artifact data
- ViewProvider protocol & StandardViewProvider
- validate_view_spec: rejects unknown schemas, invented fields, and unregistered actions

Prepares architectural boundaries for future AI view proposals without code execution.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Tuple

from rat.kernel.contracts import Artifact, ArtifactAction, InputRequest
from rat.kernel.registry import CapabilityRegistry


SUPPORTED_SCHEMA_VERSIONS = {1}
SUPPORTED_BLOCK_TYPES = {
    "summary",
    "table",
    "rows",
    "resource",
    "input_form",
    "actions",
    "details",
}


@dataclass
class ViewBlock:
    """A single declarative UI block in a ViewSpec."""

    type: str  # "summary", "table", "rows", "resource", "input_form", "actions", "details"
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "data": copy.deepcopy(self.data),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ViewBlock:
        return cls(
            type=data.get("type", "summary"),
            data=dict(data.get("data", {})),
        )


@dataclass
class ViewSpec:
    """A versioned declarative presentation tree bound to an artifact revision."""

    schema_version: int
    artifact_id: str
    revision: int
    title: str = ""
    blocks: List[ViewBlock] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact_id": self.artifact_id,
            "revision": self.revision,
            "title": self.title,
            "blocks": [b.to_dict() for b in self.blocks],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ViewSpec:
        blocks = [ViewBlock.from_dict(b) for b in data.get("blocks", [])]
        return cls(
            schema_version=data.get("schema_version", 1),
            artifact_id=data.get("artifact_id", ""),
            revision=data.get("revision", 1),
            title=data.get("title", ""),
            blocks=blocks,
        )


class ViewProvider(Protocol):
    """Protocol for providers that produce declarative ViewSpecs from artifacts."""

    def provide_view(self, artifact: Artifact, context: Optional[Dict[str, Any]] = None) -> ViewSpec:
        ...


def validate_view_spec(spec, artifact, registry=None):
    if not isinstance(spec, ViewSpec) or not isinstance(spec.blocks, list):
        return False, "invalid_view_spec"
    if type(spec.schema_version) is not int or spec.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        return False, f"unsupported_schema_version:{spec.schema_version}"
    if spec.artifact_id != artifact.id:
        return False, "artifact_id_mismatch"
    if type(spec.revision) is not int or spec.revision != artifact.revision:
        return False, "revision_mismatch"
    if registry is None:
        from rat.kernel.capabilities import build_default_registry
        registry = build_default_registry()
    actions = {a.id: a.to_dict() for a in registry.actions_for(artifact)}
    op = registry.operation_for_artifact(artifact)
    bindings = op.resource_bindings if op else {}
    for block in spec.blocks:
        if not isinstance(block, ViewBlock):
            return False, "invalid_view_block"
        if block.type not in SUPPORTED_BLOCK_TYPES:
            return False, f"unsupported_block_type:{block.type}"
        data = block.data
        if not isinstance(data, dict):
            return False, "invalid_block_data"
        if not isinstance(data.get("fields", []), list):
            return False, "invalid_field_references"
        for name in data.get("fields", []):
            if not isinstance(name, str):
                return False, "invalid_field_reference"
            value = artifact.payload
            for part in name.split("."):
                if not isinstance(value, dict) or part not in value:
                    return False, f"invalid_field_reference:{name}"
                value = value[part]
        if block.type == "resource":
            name = data.get("resource")
            field_name = bindings.get(name)
            if not field_name or field_name not in artifact.payload:
                return False, f"unknown_resource_reference:{name}"
            if data.get("field") != field_name or "value" in data or "content" in data:
                return False, "resource_payload_mismatch"
        if block.type == "actions":
            if not isinstance(data.get("action_ids", []), list) or not isinstance(data.get("actions", []), list):
                return False, "invalid_action_references"
            for aid in data.get("action_ids", []):
                if not isinstance(aid, str):
                    return False, "invalid_action_reference"
                if aid not in actions:
                    return False, f"unregistered_action_id:{aid}"
            for action in data.get("actions", []):
                if not isinstance(action, dict) or not isinstance(action.get("id"), str):
                    return False, "invalid_action_reference"
                registered = actions.get(action.get("id"))
                if registered is None or action != registered:
                    return False, f"unregistered_action_id:{action.get('id')}"
        if block.type == "input_form":
            expected = artifact.payload
            if artifact.kind != "input_request" or any(data.get(key) != expected.get(key) for key in
                ("operation_name", "missing_fields", "candidate_choices", "supplied_inputs")):
                return False, "input_request_mismatch"
    return True, None


class StandardViewProvider:
    """Use the operation's registered view factory; the provider knows no feature names."""
    def __init__(self, registry=None):
        if registry is None:
            from rat.kernel.capabilities import build_default_registry
            registry = build_default_registry()
        self.registry = registry

    def provide_view(self, artifact, context=None):
        from rat.kernel.capabilities.views import view_generic, view_input_request
        op = self.registry.operation_for_artifact(artifact)
        factory = op.view_factory if op and op.view_factory else view_generic
        if artifact.kind == "input_request":
            factory = view_input_request
        spec = factory(artifact, context or {})
        spec.blocks = [b for b in spec.blocks if b.type != "actions"]
        actions = self.registry.actions_for(artifact)
        if actions:
            spec.blocks.insert(2, ViewBlock("actions", {"action_ids": [a.id for a in actions],
                                                        "actions": [a.to_dict() for a in actions]}))
        return spec

    def _view_generic(self, artifact, context):
        from rat.kernel.capabilities.views import view_generic
        return view_generic(artifact, context)
