"""
rat.kernel.capabilities — Bundled capability implementations.
"""
from __future__ import annotations

from typing import Optional

from rat.crawler.db import Database
from rat.engine.task_state import TASK_STATE_SCHEMA, validate_task_state
from rat.kernel.capabilities.documents import create_documents_capability
from rat.kernel.capabilities.natal import create_natal_capability
from rat.kernel.capabilities.timetable import create_timetable_capability
from rat.kernel.registry import Capability, CapabilityRegistry, OperationDefinition
from rat.timetable.compositor import TimetableCompositor


def build_default_registry(
    db: Optional[Database] = None,
    compositor: Optional[TimetableCompositor] = None,
) -> CapabilityRegistry:
    """Build and populate a CapabilityRegistry with all core RAT capabilities."""
    registry = CapabilityRegistry()

    # Core capabilities
    registry.register_capability(create_documents_capability(db=db))
    registry.register_capability(create_timetable_capability(compositor=compositor))
    registry.register_capability(create_natal_capability())

    # Utility operations: update_task_state & calculate
    def handle_update_task_state(args, **context):
        return {"task_state": validate_task_state(args), "assessment": "model_report_not_verification"}

    def handle_calculate(args, **context):
        from rat.engine.assistant_runtime import AssistantRuntime
        expr = args.get("expression", "")
        return {"expression": expr, "result": AssistantRuntime.tool_calculate(expr)}

    util_cap = Capability(
        name="utilities",
        title="Tiện ích",
        description="Quản lý trạng thái công việc và tính toán biểu thức số học.",
    )
    util_cap.register_operation(OperationDefinition(
        name="update_task_state",
        description=(
            "Record your current understanding of the task: goal, user constraints, "
            "success criteria, known facts, completed and remaining work. Update at the start of a request "
            "and before answering. Use previous task state only when relevant. Your status is a model report, "
            "not verified success."
        ),
        parameters=TASK_STATE_SCHEMA,
        handler=handle_update_task_state,
    ))
    util_cap.register_operation(OperationDefinition(
        name="calculate",
        description="Evaluate an arithmetic expression with an AST calculator.",
        parameters={
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Arithmetic expression, e.g. 45 * 3 / 2"},
            },
            "required": ["expression"],
        },
        handler=handle_calculate,
    ))
    def inspect_artifact(args, **context):
        artifact = context["artifact_store"].get(args["artifact_id"], args.get("revision"))
        if artifact is None:
            raise ValueError("Kết quả không còn trong cuộc hội thoại hoặc phiên bản không tồn tại.")
        return {"artifact_id": artifact.id, "revision": artifact.revision, **artifact.payload}

    util_cap.register_operation(OperationDefinition("inspect_artifact",
        "Read actual data of an existing result by its observed artifact_id and optional revision. Use before discussing an earlier result whose contents are not in current observations.",
        {"type": "object", "properties": {"artifact_id": {"type": "string"}, "revision": {"type": "integer", "minimum": 1}}, "required": ["artifact_id"]},
        inspect_artifact))
    registry.register_capability(util_cap)

    from rat.kernel.capabilities.views import view_natal_chart, view_schedule, view_document_search, view_document_content, view_file_export
    factories = {"natal_chart": view_natal_chart, "schedule": view_schedule,
                 "document_search": view_document_search, "document_content": view_document_content, "file_export": view_file_export}
    for op in registry.list_operations():
        op.view_factory = factories.get(op.artifact_kind)
    return registry
