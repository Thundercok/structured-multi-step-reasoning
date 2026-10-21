"""
rat.kernel.registry — CapabilityRegistry and Operation contracts.

Enables modular registration of capabilities and operations with typed schemas,
handlers, and action factories, deriving native tool definitions automatically
rather than hardcoding them in central loops.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from rat.kernel.contracts import Artifact, ArtifactAction


@dataclass
class ToolDefinitionContract:
    """Tool specification compatible with native assistant runtime."""

    name: str
    description: str
    parameters: Dict[str, Any]


@dataclass
class OperationDefinition:
    """A registered executable operation with typed parameters and result contract."""

    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[..., Any]
    result_contract: Optional[Dict[str, Any]] = None
    available_actions: Optional[Callable[[Artifact], List[ArtifactAction]]] = None
    observation_formatter: Optional[Callable[[Any], Any]] = None
    artifact_kind: Optional[str] = None
    target_kind: Optional[str] = None
    updates_target: bool = False
    view_factory: Optional[Callable] = None
    resource_bindings: Dict[str, str] = field(default_factory=dict)
    # A headless checker used automatically by the shared runtime, not a tool.
    verifier: Optional[Any] = None
    # Some observations are shown through the answer/trace and kept as references.
    present_result: bool = True

    def to_tool_definition(self) -> ToolDefinitionContract:
        parameters = copy.deepcopy(self.parameters)
        if self.target_kind:
            parameters.setdefault("properties", {}).update({
                "artifact_id": {"type": "string", "description": "Exact ID of the existing result to act on."},
                "revision": {"type": "integer", "minimum": 1, "description": "Observed target revision."},
            })
        return ToolDefinitionContract(
            name=self.name,
            description=self.description,
            parameters=parameters,
        )


@dataclass
class Capability:
    """A logical bundle of operations addressing a user domain."""

    name: str
    title: str
    description: str
    operations: Dict[str, OperationDefinition] = field(default_factory=dict)

    def register_operation(self, op: OperationDefinition) -> None:
        self.operations[op.name] = op


class CapabilityRegistry:
    """Central registry for capabilities, operations, and tool definitions."""

    def __init__(self) -> None:
        self._capabilities: Dict[str, Capability] = {}
        self._operations: Dict[str, OperationDefinition] = {}
        self._op_to_cap: Dict[str, str] = {}

    def register_capability(self, capability: Capability) -> None:
        self._capabilities[capability.name] = capability
        for op_name, op in capability.operations.items():
            self._operations[op_name] = op
            self._op_to_cap[op_name] = capability.name

    def register_operation(self, operation: OperationDefinition, capability_name: Optional[str] = None) -> None:
        self._operations[operation.name] = operation
        cap_name = capability_name or "default"
        if cap_name not in self._capabilities:
            self._capabilities[cap_name] = Capability(
                name=cap_name,
                title=cap_name.capitalize(),
                description=f"Capability bundle for {cap_name}",
            )
        self._capabilities[cap_name].register_operation(operation)
        self._op_to_cap[operation.name] = cap_name

    def get_operation(self, name: str) -> Optional[OperationDefinition]:
        return self._operations.get(name)

    def has_operation(self, name: str) -> bool:
        return name in self._operations

    def get_capability(self, name: str) -> Optional[Capability]:
        return self._capabilities.get(name)


    def get_capability_for_operation(self, name: str) -> Optional[Capability]:
        cap_name = self._op_to_cap.get(name)
        return self._capabilities.get(cap_name) if cap_name else None

    def list_operations(self) -> List[OperationDefinition]:
        return list(self._operations.values())

    def list_capabilities(self) -> List[Capability]:
        return list(self._capabilities.values())

    def operation_for_artifact(self, artifact):
        origin = self.get_operation(artifact.provenance.get("operation_name", ""))
        if origin and origin.artifact_kind == artifact.kind:
            return origin
        return next((op for op in self.list_operations() if op.artifact_kind == artifact.kind), None)

    def actions_for(self, artifact):
        op = self.operation_for_artifact(artifact)
        return op.available_actions(artifact) if op and op.available_actions else []

    def to_tool_definitions(self) -> List[Any]:
        """Convert registered operations to ToolDefinitions for assistant runtime."""
        # Returns objects with name, description, parameters attributes
        return [op.to_tool_definition() for op in self._operations.values()]

    def execute(self, name: str, args: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
        op = self.get_operation(name)
        if op is None:
            raise ValueError(f"Công cụ không xác định: {name}")
        ctx = context or {}
        from rat.engine.task_state import validate_schema
        validate_schema(args, op.parameters)
        return op.handler(args, **ctx)
