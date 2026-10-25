"""
rat.ui.reading_coordinator — Coordinator for Tarot & Natal reading desk lifecycle and execution.
Enforces that reading tool invocations route through unified AgentExecutionService.
"""
from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from PyQt6.QtCore import QUrl
from rat.engine.execution import ExecutionRequest
from rat.engine.execution_service import AgentExecutionService
from rat.ui.reading_presentation import reading_profile_view

logger = logging.getLogger("rat.ui.reading_coordinator")


class ReadingDeskCoordinator:
    """Manages reading desk domain state and dispatches reading actions via AgentExecutionService."""

    def __init__(self, controller) -> None:
        self.controller = controller
        self.cards: List[Any] = []
        self.chart: Optional[Dict[str, Any]] = None
        self.draft: Dict[str, Any] = {}
        self.cot_steps: List[Dict[str, Any]] = []
        self.grounds: List[Dict[str, Any]] = []
        self.error: str = ""
        self.return_view: str = "none"
        self.return_expanded: bool = False
        self.result_refs: Dict[str, Dict[str, Any]] = {}

    @property
    def snapshot_data(self) -> Dict[str, Any]:
        return {
            "cards": list(self.cards),
            "chart": self.chart,
            "draft": dict(self.draft),
            "cotSteps": list(self.cot_steps),
            "grounds": list(self.grounds),
            "error": self.error,
            "resultRefs": dict(self.result_refs),
        }

    def open_desk(self) -> None:
        ctrl = self.controller
        if ctrl._closed or ctrl.snapshot["busy"]:
            return
        # Dynamically load optional domain tool pack into the runtime
        try:
            if hasattr(ctrl, "assistant_runtime") and ctrl.assistant_runtime:
                ctrl.assistant_runtime.load_tool_pack("divination")
                ctrl.assistant_runtime.load_tool_pack("astrology")
        except Exception as e:
            logger.debug(f"Note dynamically loading reading pack: {e}")
        if ctrl._view != "reading":
            self.return_view = ctrl._view
            self.return_expanded = ctrl._expanded
        if ctrl._finder_coordinator:
            ctrl._finder_coordinator.cancel()
        ctrl._view = "reading"
        ctrl._expanded = True
        ctrl._status = "Bàn xem · bài và lá số"
        ctrl.changed.emit()

    def close_desk(self) -> None:
        ctrl = self.controller
        if ctrl._view == "reading":
            ctrl._view = self.return_view
            ctrl._expanded = self.return_expanded
            ctrl._status = "Chuột sẵn sàng. Bạn cần gì?"
            ctrl.changed.emit()

    def set_cards(self, text: str) -> bool:
        ctrl = self.controller
        if ctrl._closed:
            return False
        try:
            result = self.execute_reading_tool("prepare_reading_spread", {"text": text})
        except ValueError as exc:
            self.error = str(exc)
            ctrl.changed.emit()
            return False
        self.cards = result["cards"]
        self.error = ""
        ctrl.changed.emit()
        return True

    def import_profile(self, path: str) -> bool:
        ctrl = self.controller
        if ctrl._closed:
            return False
        url = QUrl(path)
        local = url.toLocalFile() if url.isLocalFile() else path
        try:
            result = self.execute_reading_tool("load_reading_profile", {"file_path": local}, selected_path=local)
            chart = reading_profile_view(result)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            self.error = "Không mở được hồ sơ: " + str(exc)
            ctrl.changed.emit()
            return False
        self.chart = chart
        self.error = ""
        ctrl.changed.emit()
        return True

    def execute_reading_tool(
        self,
        name: str,
        args: Dict[str, Any],
        *,
        selected_path: Optional[str] = None,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        # Explicit user action is the plan input. Domain execution uses the unified
        # AgentExecutionService with envelope validation and journal lifecycle.
        ctrl = self.controller
        exec_id = "reading-" + uuid4().hex
        ctx = {
            "selected_document_path": selected_path,
            "reading_cards": list(self.cards),
            "reading_chart": copy.deepcopy(self.chart) if self.chart else None,
            "context_notes": str(self.draft.get("draft_markdown", "") if isinstance(self.draft, dict) else ""),
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
            self.error = "Hãy đặt bài lên bàn trước khi soạn bản luận."
            ctrl.changed.emit()
            return False
        self.error = ""
        q = query.strip() or "Soạn bản luận cho trải bài hiện tại"
        try:
            result = self.execute_reading_tool("synthesize_reading_draft", {"query": q})
            self.draft = result
            self.cot_steps = result.get("cot_steps", [])
            self.grounds = result.get("grounds", [])
            self.error = ""
            ctrl._status = "Đã soạn bản luận có cấu trúc"
            ctrl._events.append(f"Đã soạn bản luận CoT: {result.get('title', '')}")
            ctrl.changed.emit()
            return True
        except Exception as exc:
            self.error = f"Lỗi soạn bản luận: {exc}"
            ctrl.changed.emit()
            return False

    def save_draft(self, text: str) -> bool:
        ctrl = self.controller
        if ctrl._closed:
            return False
        if self.draft:
            self.draft["draft_markdown"] = text
            self.draft["user_edited"] = True
            ctrl._events.append("Người dùng đã chỉnh sửa và lưu bản luận nháp")
            ctrl.changed.emit()
            return True
        return False
