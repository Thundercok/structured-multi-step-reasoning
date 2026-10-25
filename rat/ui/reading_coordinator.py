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
        self.active_note: Optional[Dict[str, Any]] = None
        self.active_note_id: Optional[str] = None
        self.active_note_revision: int = 0

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
            "activeNote": dict(self.active_note) if self.active_note else None,
            "activeNoteId": self.active_note_id,
            "activeNoteRevision": self.active_note_revision,
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

    def synthesize_smart_note(
        self,
        raw_content: str,
        domain: str = "auto",
        title: str = "",
        focus_question: str = "",
    ) -> str:
        ctrl = self.controller
        if ctrl._closed:
            return ""
        text = (raw_content or "").strip()
        if not text:
            self.error = "Cần cung cấp nội dung để tạo ghi chú."
            ctrl.changed.emit()
            return ""
        args = {
            "raw_content": text,
            "domain": domain or "auto",
        }
        if title:
            args["title"] = title
        if focus_question:
            args["focus_question"] = focus_question

        exec_id = "smart-note-" + uuid4().hex
        req = ExecutionRequest(
            f"Tổng hợp ghi chú: {title or 'thông minh'}",
            execution_id=exec_id,
            origin="ui_action",
            requested_action={"name": "synthesize_smart_note", "args": args},
            context={
                "reading_cards": list(self.cards),
                "context_notes": str(self.draft.get("draft_markdown", "") if isinstance(self.draft, dict) else ""),
            },
        )
        service = AgentExecutionService(ctrl.assistant_runtime)
        resp = service.execute(req)
        if resp.error or not resp.artifacts:
            self.error = resp.error or "Không thể tổng hợp ghi chú thông minh."
            ctrl.changed.emit()
            return ""

        artifact = resp.artifacts[0]
        self.active_note = artifact.payload
        self.active_note_id = artifact.id
        self.active_note_revision = artifact.revision
        self.result_refs["synthesize_smart_note"] = {"artifact_id": artifact.id, "revision": artifact.revision}
        self.error = ""
        ctrl._status = f"Đã lưu ghi chú: {artifact.payload.get('title', '')}"
        ctrl._events.append(f"Ghi chú thông minh đã tạo (rev {artifact.revision}): {artifact.id}")
        ctrl.changed.emit()
        return artifact.id

    def synthesize_from_current_draft(self, domain: str = "decision", title: str = "") -> str:
        ctrl = self.controller
        if ctrl._closed:
            return ""
        content = ""
        if self.draft and self.draft.get("draft_markdown"):
            content = self.draft["draft_markdown"]
            title = title or self.draft.get("title", "Ghi chú Bàn xem")
        elif self.cards:
            parts = [f"{c.get('title', '')} ({'ngược' if c.get('reversed') else 'xuôi'})" for c in self.cards]
            content = f"Dữ kiện trải bài gồm các lá: {', '.join(parts)}."
            title = title or "Ghi chú Trải bài"
        else:
            self.error = "Chưa có nội dung bản luận hoặc trải bài để tổng hợp ghi chú."
            ctrl.changed.emit()
            return ""
        return self.synthesize_smart_note(raw_content=content, domain=domain, title=title)

    def update_note_action_item(
        self,
        task_match: str = "",
        done: bool = True,
        item_index: Optional[int] = None,
        artifact_id: Optional[str] = None,
        new_task_text: Optional[str] = None,
    ) -> bool:
        ctrl = self.controller
        if ctrl._closed:
            return False
        target_id = artifact_id or self.active_note_id
        target_rev = self.active_note_revision if (not artifact_id or artifact_id == self.active_note_id) else None
        if not target_id:
            self.error = "Chưa có bản ghi chú nào được chọn để cập nhật việc cần làm."
            ctrl.changed.emit()
            return False

        args: Dict[str, Any] = {
            "artifact_id": target_id,
            "done": done,
        }
        if target_rev is not None:
            args["revision"] = target_rev
        if task_match:
            args["task_match"] = task_match
        if item_index is not None:
            args["item_index"] = item_index
        if new_task_text:
            args["new_task_text"] = new_task_text

        exec_id = "update-note-" + uuid4().hex
        req = ExecutionRequest(
            f"Cập nhật việc cần làm trong ghi chú {target_id}",
            execution_id=exec_id,
            origin="ui_action",
            requested_action={"name": "update_note_action_item", "args": args},
            context={},
        )
        service = AgentExecutionService(ctrl.assistant_runtime)
        resp = service.execute(req)
        if resp.error or not resp.artifacts:
            self.error = resp.error or "Không cập nhật được việc cần làm."
            ctrl.changed.emit()
            return False

        artifact = resp.artifacts[0]
        self.active_note = artifact.payload
        self.active_note_id = artifact.id
        self.active_note_revision = artifact.revision
        self.result_refs["update_note_action_item"] = {"artifact_id": artifact.id, "revision": artifact.revision}
        self.error = ""
        action_name = task_match or (f"mục #{item_index}" if item_index is not None else "việc cần làm")
        state_label = "hoàn thành" if done else "chưa xong"
        ctrl._status = f"Đã cập nhật việc cần làm: {action_name} -> {state_label}"
        ctrl._events.append(f"Cập nhật việc cần làm ghi chú: rev {artifact.revision}")
        ctrl.changed.emit()
        return True

    def expand_note_section(
        self,
        section_heading: str,
        expansion_content: str = "",
        expansion_query: str = "",
        artifact_id: Optional[str] = None,
    ) -> bool:
        ctrl = self.controller
        if ctrl._closed:
            return False
        target_id = artifact_id or self.active_note_id
        target_rev = self.active_note_revision if (not artifact_id or artifact_id == self.active_note_id) else None
        if not target_id:
            self.error = "Chưa có bản ghi chú nào được chọn để mở rộng mục."
            ctrl.changed.emit()
            return False

        heading = (section_heading or "").strip()
        if not heading:
            self.error = "Cần chỉ định tên mục cần mở rộng (section_heading)."
            ctrl.changed.emit()
            return False

        content = (expansion_content or "").strip()
        query = (expansion_query or "").strip() or f"Đào sâu mục {heading}"
        if not content:
            content = f"Phân tích bổ sung về {query}: Các khía cạnh thực tế và đề xuất thực hiện chi tiết."

        args: Dict[str, Any] = {
            "artifact_id": target_id,
            "section_heading": heading,
            "expansion_content": content,
            "expansion_query": query,
        }
        if target_rev is not None:
            args["revision"] = target_rev

        exec_id = "expand-note-" + uuid4().hex
        req = ExecutionRequest(
            f"Mở rộng mục {heading} trong ghi chú {target_id}",
            execution_id=exec_id,
            origin="ui_action",
            requested_action={"name": "expand_note_section", "args": args},
            context={},
        )
        service = AgentExecutionService(ctrl.assistant_runtime)
        resp = service.execute(req)
        if resp.error or not resp.artifacts:
            self.error = resp.error or "Không mở rộng được mục ghi chú."
            ctrl.changed.emit()
            return False

        artifact = resp.artifacts[0]
        self.active_note = artifact.payload
        self.active_note_id = artifact.id
        self.active_note_revision = artifact.revision
        self.result_refs["expand_note_section"] = {"artifact_id": artifact.id, "revision": artifact.revision}
        self.error = ""
        ctrl._status = f"Đã mở rộng mục: {heading}"
        ctrl._events.append(f"Mở rộng mục ghi chú: rev {artifact.revision}")
        ctrl.changed.emit()
        return True
