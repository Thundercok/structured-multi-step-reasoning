"""
rat.plugins.packs.timetable — Timetable & Schedule Compositor domain vertical tool pack.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from rat.plugins.manifest import ToolPack, ToolPackManifest


class TimetableToolPack(ToolPack):
    """Dynamic tool pack for student course timetables, shift matrix, and free-time golden windows."""

    manifest = ToolPackManifest(
        id="timetable",
        name="Thời khóa biểu & Điều phối lịch học (Timetable)",
        description="Tra cứu lịch học, phân tích xung đột, tìm giờ trống chung và trích xuất lịch ICS.",
        version="1.0.0",
        category="vertical",
        enabled_by_default=False,
        tags=["timetable", "schedule", "academic", "calendar"],
    )

    def create_capabilities(self, context: Optional[Dict[str, Any]] = None) -> List[Any]:
        compositor = context.get("compositor") if context else None
        from rat.kernel.capabilities.timetable import create_timetable_capability
        return [create_timetable_capability(compositor=compositor)]

    def get_view_factories(self) -> Dict[str, Callable]:
        from rat.kernel.capabilities.views import view_schedule
        return {"schedule": view_schedule}
