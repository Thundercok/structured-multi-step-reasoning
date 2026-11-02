"""
tests/test_plugin_tool_packs.py — Verification of decoupled domain vertical tool packs.
"""
from __future__ import annotations

import pytest

from rat.kernel.capabilities import build_core_registry, build_default_registry
from rat.plugins import PluginManager, get_plugin_manager
from rat.engine.assistant_runtime import AssistantRuntime


def test_core_registry_has_no_domain_verticals():
    """Verify that build_core_registry creates a pure General Reasoning Desktop Shell."""
    core = build_core_registry()
    op_names = {op.name for op in core.list_operations()}

    # Core reasoning and desktop shell tools must be present
    assert "search_documents" in op_names
    assert "read_document" in op_names
    assert "open_document" in op_names
    assert "deliver_document" in op_names
    assert "open_application" in op_names
    assert "compose_result_table" in op_names
    assert "update_task_state" in op_names
    assert "calculate" in op_names
    assert "inspect_artifact" in op_names

    # Specialized domain verticals must NOT be hard-wired into core
    assert "create_natal_chart" not in op_names
    assert "interpret_aspect" not in op_names
    assert "export_natal_chart" not in op_names
    assert "prepare_reading_spread" not in op_names
    assert "load_reading_profile" not in op_names
    assert "synthesize_reading_draft" not in op_names
    assert "get_schedule" not in op_names
    assert "get_group_availability" not in op_names
    assert "locate_room" not in op_names


def test_dynamic_pack_loading_and_unloading():
    """Verify that domain verticals can be loaded and unloaded dynamically via PluginManager."""
    manager = get_plugin_manager()
    registry = build_core_registry()

    # 1. Astrology Tool Pack
    assert not manager.is_pack_loaded("astrology", registry)
    loaded = manager.load_pack("astrology", registry)
    assert loaded
    assert manager.is_pack_loaded("astrology", registry)
    assert "create_natal_chart" in [op.name for op in registry.list_operations()]

    unloaded = manager.unload_pack("astrology", registry)
    assert unloaded
    assert not manager.is_pack_loaded("astrology", registry)
    assert "create_natal_chart" not in [op.name for op in registry.list_operations()]

    # 2. Divination / Tarot Tool Pack
    assert not manager.is_pack_loaded("divination", registry)
    loaded = manager.load_pack("divination", registry)
    assert loaded
    assert manager.is_pack_loaded("divination", registry)
    assert "prepare_reading_spread" in [op.name for op in registry.list_operations()]
    assert "synthesize_reading_draft" in [op.name for op in registry.list_operations()]

    unloaded = manager.unload_pack("divination", registry)
    assert unloaded
    assert not manager.is_pack_loaded("divination", registry)
    assert "prepare_reading_spread" not in [op.name for op in registry.list_operations()]

    # 3. Timetable Tool Pack
    assert not manager.is_pack_loaded("timetable", registry)
    loaded = manager.load_pack("timetable", registry)
    assert loaded
    assert manager.is_pack_loaded("timetable", registry)
    assert "get_schedule" in [op.name for op in registry.list_operations()]

    unloaded = manager.unload_pack("timetable", registry)
    assert unloaded
    assert not manager.is_pack_loaded("timetable", registry)
    assert "get_schedule" not in [op.name for op in registry.list_operations()]


def test_assistant_runtime_core_mode_and_dynamic_load():
    """Verify AssistantRuntime starting in pure core mode can dynamically load a tool pack."""
    # Start runtime in pure core mode
    runtime = AssistantRuntime(active_tool_packs=[], use_live_model=False)

    assert not runtime.is_tool_pack_loaded("divination")
    assert not runtime.registry.has_operation("prepare_reading_spread")

    # Dynamically load divination tool pack
    ok = runtime.load_tool_pack("divination")
    assert ok
    assert runtime.is_tool_pack_loaded("divination")
    assert runtime.registry.has_operation("prepare_reading_spread")

    # Execute tool via standard dispatcher
    res = runtime.dispatcher.execute_operation("prepare_reading_spread", {"text": "ace wands, 3 cups rev"})
    assert res.status == "success"
    assert res.artifact.kind == "reading_spread"
    assert len(res.artifact.payload["cards"]) == 2

    # Dynamically unload pack
    runtime.unload_tool_pack("divination")
    assert not runtime.is_tool_pack_loaded("divination")
    assert not runtime.registry.has_operation("prepare_reading_spread")

    # Subsequent execution must fail cleanly because tool is no longer available
    failed = runtime.dispatcher.execute_operation("prepare_reading_spread", {"text": "ace wands"})
    assert failed.status == "error"
    assert "không xác định" in failed.error.lower() or "chưa đăng ký" in failed.error.lower()


def test_quick_pdf_controller_lazy_loads_reading_pack():
    """Verify QuickPDFController dynamically activates the divination pack when opening reading desk."""
    from rat.ui.quick_pdf_controller import QuickPDFController

    # Controller starts with runtime
    controller = QuickPDFController(auto_init_finder=False)
    controller.ready()
    try:
        # Before opening reading desk, divination tool pack should not be required
        controller.openReadingDesk()
        assert controller.snapshot["view"] == "reading"

        # Reading pack was loaded dynamically by openReadingDesk()
        assert controller.assistant_runtime.is_tool_pack_loaded("divination")
        assert controller.assistant_runtime.registry.has_operation("prepare_reading_spread")

        # Now setting reading cards executes the dynamically loaded tool
        assert controller.setReadingCards("2 pent, 4 swords rev")
        cards = controller.snapshot["readingSession"]["cards"]
        assert len(cards) == 2
        assert cards[0]["numeral"] == "2" and cards[0]["suit"] == "Pentacles"
        assert cards[1]["reversed"] is True
    finally:
        controller.close()
