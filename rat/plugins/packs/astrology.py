"""
rat.plugins.packs.astrology — Astrology & Natal Chart domain vertical tool pack.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from rat.plugins.manifest import ToolPack, ToolPackManifest


class AstrologyToolPack(ToolPack):
    """Dynamic tool pack for geocentric natal chart calculations, aspect interpretation, and chart export."""

    manifest = ToolPackManifest(
        id="astrology",
        name="Chiêm tinh & Lá số cá nhân (Astrology)",
        description="Lập bản đồ sao chiêm tinh chính xác, tính toán vị trí thiên thể, góc chiếu và xuất biểu đồ.",
        version="1.0.0",
        category="vertical",
        enabled_by_default=False,
        tags=["astrology", "natal", "ephemeris", "swisseph"],
    )

    def create_capabilities(self, context: Optional[Dict[str, Any]] = None) -> List[Any]:
        from rat.kernel.capabilities.natal import create_natal_capability
        return [create_natal_capability()]

    def get_view_factories(self) -> Dict[str, Callable]:
        from rat.kernel.capabilities.views import view_natal_chart
        return {"natal_chart": view_natal_chart}
