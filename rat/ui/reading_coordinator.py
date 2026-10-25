"""
rat.ui.reading_coordinator — Coordinator for Tarot & Natal reading desk lifecycle and execution.
Enforces that reading tool invocations route through unified AgentExecutionService.
"""
from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from rat.engine.execution import ExecutionRequest
from rat.engine.execution_service import AgentExecutionService
from rat.ui.reading_presentation import reading_profile_view

logger = logging.getLogger("rat.ui.reading_coordinator")


class ReadingDeskCoordinator:
    """Manages reading desk domain state and dispatches reading actions via AgentExecutionService."""

    def __init__(self, controller) -> None:
        self.controller = controller
        self.cards: List[str] = []
        self.chart: Optional[Dict[str, Any]] = None
        self.saved_draft: str = ""
        self.return_view: str = "chat"
        self.result_refs: Dict[str, Dict[str, Any]] = {}

    @property
    def profile_name(self) -> str:
        if self.chart:
            b = self.chart.get("birth", {})
            return str(b.get("name") or "Lá số cá nhân")
        return ""

    def open_desk(self) -> None:
        ctrl = self.controller
        if ctrl._closed or ctrl.snapshot["busy"]:
            return
        try:
            if hasattr(ctrl, "assistant_runtime") and ctrl.assistant_runtime:
                ctrl.assistant_runtime.load_tool_pack("divination")
                ctrl.assistant_runtime.load_tool_pack("astrology")
        except Exception as e:
            logger.debug(f"Note dynamically loading reading pack: {e}")
        if ctrl._view != "reading":
            self.return_view = ctrl._view
        ctrl._view = "reading"
        ctrl._expanded = True
        ctrl._unread = False
        ctrl._status = "Đang mở Bàn đọc bài · chuẩn bị lá bài và lá số…"
        ctrl.changed.emit()

    def close_desk(self) -> None:
        ctrl = self.controller
        if ctrl._closed:
            return
        ctrl._view = self.return_view if self.return_view != "reading" else "chat"
        ctrl._status = "Chuột sẵn sàng. Bạn cần gì?" if not ctrl._last_assistant_answer else "Đã trả lời · có thể hỏi tiếp"
        ctrl.changed.emit()

    def set_cards(self, text: str) -> bool:
        ctrl = self.controller
        if ctrl._closed:
            return False
        raw = (text or "").strip()
        if not raw:
            self.cards = []
            ctrl._status = "Đã xóa danh sách lá bài."
            ctrl.changed.emit()
            return True
        try:
            payload = self.execute_reading_tool("prepare_reading_spread", {"text": raw})
            self.cards = [c["name"] for c in payload.get("cards", [])]
            ctrl._status = f"Đã ghi nhận {len(self.cards)} lá: {', '.join(self.cards)}"
            ctrl.changed.emit()
            return True
        except Exception as e:
            ctrl._status = f"Chưa nhận diện được lá bài: {e}"
            ctrl.changed.emit()
            return False

    def import_profile(self, path: str) -> bool:
        ctrl = self.controller
        if ctrl._closed or not path:
            return False
        p = Path(path)
        if not p.is_file():
            ctrl._status = f"Tệp lá số không tồn tại: {path}"
            ctrl.changed.emit()
            return False
        try:
            payload = self.execute_reading_tool("load_reading_profile", {"file_path": str(p)})
            self.chart = reading_profile_view(payload)
            ctrl._status = f"Đã nạp lá số: {self.profile_name}"
            ctrl.changed.emit()
            return True
        except Exception as e:
            ctrl._status = f"Không đọc được tệp lá số: {e}"
            ctrl.changed.emit()
            return False

    def execute_reading_tool(self, name: str, args: Dict[str, Any], *, selected_path: Optional[str] = None, extra_context: Optional[Dict[str, Any]] = None) -> Any:
        ctrl = self.controller
        exec_id = "reading-" + uuid4().hex
        ctx = {
            "selected_document_path": selected_path,
            "reading_cards": list(self.cards),
            "reading_chart": copy.deepcopy(self.chart) if self.chart else None,
            "context_notes": str(self.saved_draft or ""),
        }
        if extra_context:
            for k, v in extra_context.items():
                if k not in ("runtime", "model_client", "db"):
                    ctx[k] = v

        req = ExecutionRequest(
            f"Thực thi {name}",
            execution_id=exec_id,
            origin="ui_action",
            requested_action={"name": name, "args": args},
            context=ctx,
        )
        service = AgentExecutionService(ctrl.assistant_runtime)
        resp = service.execute(req)
        if resp.error or not resp.artifacts:
            raise ValueError(resp.error or "Chưa chuẩn bị được dữ liệu phiên xem.")
        artifact = resp.artifacts[0]
        self.result_refs[name] = {"artifact_id": artifact.id, "revision": artifact.revision}
        return artifact.payload

    def synthesize_draft(self, query: str = "") -> bool:
        ctrl = self.controller
        if ctrl._closed or ctrl.snapshot["busy"]:
            return False
        if not self.cards:
            ctrl._status = "Cần ít nhất một lá bài để tổng hợp luận giải."
            ctrl.changed.emit()
            return False
        ctrl._status = "Đang tổng hợp bản nháp luận giải từ các lá bài và lá số…"
        ctrl.changed.emit()
        try:
            payload = self.execute_reading_tool(
                "synthesize_reading_draft",
                {"query": (query or "").strip()},
                selected_path=str(ctrl._selection.path) if ctrl._selection else None,
            )
            draft = payload.get("draft") or ""
            if not draft:
                raise ValueError("Bản nháp luận giải rỗng.")
            self.saved_draft = draft
            ctrl._status = "Đã tổng hợp bản nháp luận giải."
            ctrl.changed.emit()
            return True
        except Exception as e:
            ctrl._status = f"Lỗi tổng hợp bản nháp: {e}"
            ctrl.changed.emit()
            return False

    def save_draft(self, text: str) -> bool:
        ctrl = self.controller
        if ctrl._closed:
            return False
        self.saved_draft = text or ""
        ctrl._status = "Đã lưu bản nháp."
        ctrl.changed.emit()
        return True
