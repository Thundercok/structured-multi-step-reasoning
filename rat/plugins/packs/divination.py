"""
rat.plugins.packs.divination — Divination & Tarot reading domain vertical tool pack.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from rat.plugins.manifest import ToolPack, ToolPackManifest


class DivinationToolPack(ToolPack):
    """Dynamic tool pack for Tarot spreads, divination profiles, and structured reading drafts."""

    manifest = ToolPackManifest(
        id="divination",
        name="Bàn xem Tarot & Chiêm đoán (Divination)",
        description="Ghi nhận trải bài tarot chính xác, nạp hồ sơ lá số, và phối hợp soạn bản luận.",
        version="1.0.0",
        category="vertical",
        enabled_by_default=False,
        tags=["divination", "tarot", "reading", "cards"],
    )

    def create_capabilities(self, context: Optional[Dict[str, Any]] = None) -> List[Any]:
        from rat.kernel.capabilities.reading import create_reading_capability
        return [create_reading_capability()]

    def get_ui_cards(self) -> List[Dict[str, Any]]:
        return [{
            "id": "reading_desk",
            "name": "Bàn xem Chiêm tinh & Tarot",
            "qml": "rat/ui/quick/ReadingDesk.qml",
        }]
