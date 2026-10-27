"""
rat.kernel.capabilities — Bundled capability implementations and core registry builder.
"""
from __future__ import annotations

import os
from typing import List, Optional, Sequence

from rat.engine.task_state import TASK_STATE_SCHEMA, validate_task_state
from rat.kernel.registry import Capability, CapabilityRegistry, OperationDefinition


def build_core_registry(
    db: Optional[Database] = None,
    enable_web: bool = False,
) -> CapabilityRegistry:
    """
    Build and populate a CapabilityRegistry for the General Reasoning Desktop Shell.

    Contains only general reasoning and desktop shell tools:
    - Document search, content reading, and PDF evidence extraction
    - System application discovery and launching
    - Formatted result tables
    - Core reasoning utilities (task state, calculate, inspect artifact)

    No specialized domain verticals (astrology, divination, timetable) are registered.
    """
    from rat.kernel.capabilities.applications import create_applications_capability
    from rat.kernel.capabilities.documents import create_documents_capability
    from rat.kernel.capabilities.finder import create_finder_capability
    from rat.kernel.capabilities.result_tables import create_result_tables_capability
    from rat.kernel.capabilities.smart_notes import create_smart_notes_capability
    from rat.kernel.capabilities.web import create_web_capability
    registry = CapabilityRegistry()

    # General Reasoning Desktop Shell Core Capabilities
    registry.register_capability(create_documents_capability(db=db))
    registry.register_capability(create_applications_capability())
    registry.register_capability(create_finder_capability(db=db))
    registry.register_capability(create_result_tables_capability())
    registry.register_capability(create_smart_notes_capability())

    if enable_web:
        registry.register_capability(create_web_capability(enabled=True))

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
        artifact_kind="calculation",
        present_result=False,
    ))
    from rat.engine.verification import CalculationVerifier
    util_cap.operations["calculate"].verifier = CalculationVerifier()

    def inspect_artifact(args, **context):
        artifact = context["artifact_store"].get(args["artifact_id"], args.get("revision"))
        if artifact is None:
            raise ValueError("Kết quả không còn trong cuộc hội thoại hoặc phiên bản không tồn tại.")
        return {"artifact_id": artifact.id, "revision": artifact.revision, **artifact.payload}

    util_cap.register_operation(OperationDefinition(
        "inspect_artifact",
        "Read actual data of an existing result by its observed artifact_id and optional revision. "
        "Use before discussing an earlier result whose contents are not in current observations.",
        {
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string"},
                "revision": {"type": "integer", "minimum": 1},
            },
            "required": ["artifact_id"],
        },
        inspect_artifact,
    ))
    registry.register_capability(util_cap)

    # Core view factories
    from rat.kernel.capabilities.views import (
        view_application_launch,
        view_book_page_content,
        view_book_page_search,
        view_document_content,
        view_document_file,
        view_document_search,
        view_file_export,
        view_finder_results,
        view_web_page_snapshot,
    )
    core_factories = {
        "document_search": view_document_search,
        "document_content": view_document_content,
        "file_export": view_file_export,
        "book_page_search": view_book_page_search,
        "book_page_content": view_book_page_content,
        "document_file": view_document_file,
        "web_page_snapshot": view_web_page_snapshot,
        "application_launch": view_application_launch,
        "finder_results": view_finder_results,
    }

    for op in registry.list_operations():
        op.view_factory = core_factories.get(op.artifact_kind, op.view_factory)

    return registry


def build_default_registry(
    db: Optional[Database] = None,
    compositor: Optional[TimetableCompositor] = None,
    enable_web: bool = False,
    active_tool_packs: Optional[Sequence[str]] = None,
) -> CapabilityRegistry:
    """
    Build a CapabilityRegistry with core desktop shell capabilities, optionally
    loading specified dynamic domain tool packs via PluginManager.
    """
    registry = build_core_registry(db=db, enable_web=enable_web)

    # Resolve tool packs to load
    packs_to_load: List[str]
    if active_tool_packs is not None:
        packs_to_load = list(active_tool_packs)
    else:
        env_packs = os.getenv("RAT_TOOL_PACKS")
        if env_packs is not None:
            packs_to_load = [p.strip() for p in env_packs.split(",") if p.strip() and p.strip() not in ("none", "core")]
        else:
            packs_to_load = ["astrology", "divination", "timetable"]

    if packs_to_load:
        from rat.plugins import get_plugin_manager
        manager = get_plugin_manager()
        context = {"db": db, "compositor": compositor}
        for pack_id in packs_to_load:
            manager.load_pack(pack_id, registry, context=context)

    return registry
