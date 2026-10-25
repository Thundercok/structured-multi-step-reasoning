"""Qt bridge for explicitly selected PDFs and shared RAT-CoT execution."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
import hashlib
import html
import logging
from pathlib import Path
import re
import subprocess
import sys
import threading
from xml.parsers.expat import ExpatError
from uuid import uuid4
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QCoreApplication, QObject, QUrl, Qt, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDesktopServices, QGuiApplication

from rat.config import config
from rat.engine.app_resolver import ApplicationCatalog, revalidate_application_bundle
from rat.engine.finder_intent import parse_finder_intent
from rat.engine.progressive_search import ProgressiveSearch, SearchCoordinator, SearchSnapshot
from rat.engine.semantic_reranker import SemanticFuzzyReranker
from rat.engine.selected_pdf import (
    SelectedPDFError, check_current, citation_text, select_pdf,
)
from rat.engine.execution import (
    CONTEXT_ADAPTER_SCHEMA_VERSION,
    ExecutionRequest,
    build_execution_context_snapshot,
    execution_response,
    render_backend_input,
    validate_referenced_context,
)
from rat.engine.assistant_runtime import AgentResponse, AssistantRuntime
from rat.ui.chat_session import ConversationHistory, TurnSnapshot
from rat.ui.answer_presentation import (
    answer_excerpt, answer_html, answer_starts_with_code, answer_one_line, source_rows, page_reading_text, format_process_steps
)
from rat.ui.assistant_worker import create_execution_worker
from rat.ui.pdf_snapshot_provider import PdfSnapshotRenderer
from rat.ui.reading_coordinator import ReadingDeskCoordinator
from rat.kernel.contracts import Artifact, SourceEvidence

logger = logging.getLogger("rat.ui.quick_pdf_controller")

ERROR_MESSAGES = {
    "file_not_found": "Tệp không còn tồn tại. Hãy chọn lại PDF.",
    "file_unreadable": "Không đọc được tệp này. Kiểm tra quyền đọc hoặc chọn PDF khác.",
    "not_pdf": "Hãy chọn một tệp PDF.",
    "pdf_too_large": "Luồng này nhận PDF tối đa 64 MiB. Hãy chọn một phần tài liệu nhỏ hơn.",
    "encrypted_pdf": "PDF yêu cầu mật khẩu. Hãy chọn bản đã mở khóa.",
    "invalid_pdf": "PDF hỏng hoặc không đọc được cấu trúc. Hãy chọn lại hoặc xuất lại PDF.",
    "empty_pdf": "PDF này không có trang nào.",
    "pdf_engine_unavailable": "Bộ đọc PDF hoặc thành phần giải mã cần thiết chưa có sẵn.",
    "no_text_page": "Trang này không có văn bản trích xuất; có thể là trang trắng hoặc scan/ảnh. OCR chưa chạy.",
    "pdf_changed": "PDF đã thay đổi sau khi chọn. Hãy chọn lại trước khi tìm, đọc hoặc chép trích dẫn.",
    "invalid_page": "Số trang nằm ngoài tệp PDF đang chọn.",
    "empty_query": "Hãy nhập từ hoặc cụm từ cần tìm.",
    "invalid_citation": "Đoạn chọn không khớp văn bản trang đã đọc. Hãy chọn lại đoạn trích.",
    "open_failed": "Hệ thống chưa nhận yêu cầu mở PDF gốc.",
}


def format_matched_snippet(hit: Optional[Dict[str, Any]], page_content: str, query: str = "") -> Dict[str, Any]:
    if not hit or not hit.get("snippet"):
        return {
            "snippet": "",
            "rawSnippet": "",
            "snippetHtml": "",
            "truncated": False,
            "hasSnippet": False,
        }

    raw_snippet = hit["snippet"].strip()
    start_offset = hit.get("snippet_start", 0)
    page_len = len(page_content) if page_content else 0

    is_start_truncated = (start_offset > 0)
    is_end_truncated = (page_len > 0 and (start_offset + len(raw_snippet) < page_len))

    display_text = raw_snippet
    if is_start_truncated and not display_text.startswith("…"):
        display_text = "… " + display_text.lstrip()
    if is_end_truncated and not display_text.endswith("…"):
        display_text = display_text.rstrip() + " …"

    escaped = html.escape(display_text)
    terms = hit.get("matched_terms") or ([query.strip()] if query.strip() else [])
    for term in sorted(terms, key=len, reverse=True):
        if not term:
            continue
        pattern = re.compile(rf"({re.escape(html.escape(term))})", re.IGNORECASE)
        escaped = pattern.sub(r'<span style="background-color: #f7e096; color: #1c1d1a; font-weight: bold; border-radius: 2px; padding: 0 2px;">\1</span>', escaped)

    html_text = escaped.replace("\n", "<br/>")

    return {
        "snippet": display_text,
        "rawSnippet": raw_snippet,
        "snippetHtml": html_text,
        "truncated": is_start_truncated or is_end_truncated,
        "hasSnippet": True,
    }



@dataclass(frozen=True)
class _Request:
    serial: int
    kind: str
    args: tuple
    cancelled: threading.Event = field(default_factory=threading.Event)


class _LatestPDFWorker:
    def __init__(self, deliver, execution_service=None):
        self._condition = threading.Condition()
        self._pending = None
        self._closed = False
        self._deliver = deliver
        if execution_service is None:
            from rat.engine.execution_service import AgentExecutionService
            execution_service = AgentExecutionService(None)
        self._execution_service = execution_service
        self._thread = threading.Thread(target=self._run, name="rat-quick-pdf", daemon=True)
        self._thread.start()

    def submit(self, request):
        with self._condition:
            if self._closed:
                return
            if self._pending:
                self._pending.cancelled.set()
            self._pending = request
            self._condition.notify()

    def _run(self):
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._pending is not None or self._closed)
                if self._closed:
                    return
                request, self._pending = self._pending, None
            try:
                kwargs = {"should_cancel": request.cancelled.is_set, "generation": request.serial}
                if request.kind == "select":
                    data = self._execution_service.execute_subplan(
                        "pdf_select",
                        {"path": request.args[0], "select_fn": select_pdf},
                        **kwargs,
                    )
                elif request.kind == "search":
                    selection, query, start = request.args
                    data = self._execution_service.execute_subplan(
                        "pdf_search",
                        {"selection": selection, "query": query, "start_page": start},
                        **kwargs,
                    )
                else:
                    selection, page_number = request.args
                    data = self._execution_service.execute_subplan(
                        "pdf_read_page",
                        {"selection": selection, "page_number": page_number},
                        **kwargs,
                    )
                outcome, value = "ok", data
            except InterruptedError:
                outcome, value = "cancelled", None
            except SelectedPDFError as exc:
                outcome, value = "error", exc.code
            except Exception:
                outcome, value = "error", "invalid_pdf"
            with self._condition:
                if self._closed:
                    return
            if not request.cancelled.is_set():
                try:
                    self._deliver(request.serial, outcome, value)
                except RuntimeError:
                    # The receiver may have been destroyed during app shutdown.
                    return

    def close(self, timeout=0.25):
        with self._condition:
            self._closed = True
            if self._pending:
                self._pending.cancelled.set()
                self._pending = None
            self._condition.notify()
        self._thread.join(timeout)
        return not self._thread.is_alive()


class QuickPDFController(QObject):
    changed = pyqtSignal()
    copyReady = pyqtSignal(str)
    copyConfirmed = pyqtSignal(str)
    _delivered = pyqtSignal(int, str, object)
    _execution_delivered = pyqtSignal(object, object)
    _execution_status_delivered = pyqtSignal(str, int, str)
    _finder_delivered = pyqtSignal(object)
    _catalog_ready = pyqtSignal(object)

    def __init__(
        self,
        parent=None,
        *,
        open_url=None,
        reveal_file=None,
        preview_file=None,
        assistant_runtime: Optional[AssistantRuntime] = None,
        conversation: Optional[ConversationHistory] = None,
        reasoning_engine: Optional[Any] = None,
        allow_synthetic_policy: bool = False,
        finder_search: Optional[ProgressiveSearch] = None,
        finder_catalog: Optional[ApplicationCatalog] = None,
        finder_coordinator: Optional[SearchCoordinator] = None,
        db_path: Optional[str] = None,
        auto_init_finder: bool = True,
    ):
        super().__init__(parent)
        self._ready = False
        self._closed = False
        self._worker = None
        self._request = None
        self._serial = 0
        self._selection = None
        self._search = None
        self._page = None
        self._view = "none"
        self._expanded = False
        self._workspace_mode = "single"
        self._preview_page = 1
        self._preview_snippet = ""
        self._preview_card_index = -1
        self._unread = False
        self._status = "Chuột sẵn sàng. Bạn cần gì?"
        self._error = ""
        self._events = []
        self._open_url = open_url
        self._reveal_file = reveal_file
        self._preview_file = preview_file
        self._launch_feedback = ""
        self._launch_feedback_error = False
        self._snapshot_renderer = PdfSnapshotRenderer()
        self._delivered.connect(self._finish, Qt.ConnectionType.QueuedConnection)
        self._execution_delivered.connect(self._handle_execution_delivered, Qt.ConnectionType.QueuedConnection)
        self._execution_status_delivered.connect(self._on_execution_status, Qt.ConnectionType.QueuedConnection)
        self._finder_delivered.connect(self._handle_finder_snapshot, Qt.ConnectionType.QueuedConnection)
        self._catalog_ready.connect(self._on_catalog_ready, Qt.ConnectionType.QueuedConnection)

        # Unified shared runtime & conversation state
        self._assistant_runtime = assistant_runtime
        self._conversation = conversation
        self._reasoning_engine = reasoning_engine
        self._allow_synthetic_policy = allow_synthetic_policy

        self._current_worker = None
        self._execution_workers = set()
        self._current_execution_id = None
        self._current_turn_id = None
        self._chat_generation = 0
        self._last_user_query = ""
        self._last_assistant_answer = ""
        self._displayed_turn_id = None
        self._telemetry = {}
        self._assistant_sources = []
        self._assistant_task_state = {}

        # Progressive finder integration
        self._finder_coordinator = finder_coordinator
        self._finder_search = finder_search
        self._finder_catalog = finder_catalog
        self._finder_hits: List[Dict[str, Any]] = []
        self._finder_query: str = ""
        self._finder_feedback = ""
        self._reading_coordinator = ReadingDeskCoordinator(self)
        self._db_path = db_path or str(config.db_path)
        self._finder_semantic = SemanticFuzzyReranker(self._db_path)
        self._cached_apps_list: List[Dict[str, Any]] = []
        self._saved_draft: str = ""
        self._prior_view: str = "none"
        self._pre_finder_view: str = "none"
        self._pre_finder_expanded: bool = False
        self._pre_finder_status: Optional[str] = None
        self._auto_read_on_select: bool = False
        self._page_return_view: str = "none"
        self._active_search_hit: Optional[Dict[str, Any]] = None
        self._cached_matched_info: Optional[Dict[str, Any]] = None
        self._cached_matched_key: Optional[tuple] = None

        if self._finder_catalog is not None:
            self._update_cached_apps(self._finder_catalog)

        if self._finder_coordinator is None:
            if self._finder_search is not None:
                self._finder_coordinator = SearchCoordinator(
                    self._finder_search,
                    on_update=lambda snap: self._finder_delivered.emit(snap),
                    execution_service=self._get_execution_service(),
                )
            elif self._finder_catalog is not None:
                self._finder_search = ProgressiveSearch(self._db_path, catalog=self._finder_catalog, semantic=self._finder_semantic)
                self._finder_coordinator = SearchCoordinator(
                    self._finder_search,
                    on_update=lambda snap: self._finder_delivered.emit(snap),
                    execution_service=self._get_execution_service(),
                )
            elif auto_init_finder:
                def scan_catalog():
                    try:
                        cat = ApplicationCatalog.scan()
                        if not self._closed:
                            self._catalog_ready.emit(cat)
                    except RuntimeError:
                        pass
                    except Exception as e:
                        logger.debug(f"Finder catalog scan exception: {e}")
                        try:
                            if not self._closed:
                                self._catalog_ready.emit(ApplicationCatalog())
                        except RuntimeError:
                            pass

                threading.Thread(target=scan_catalog, name="rat-quick-catalog-scan", daemon=True).start()

    @property
    def assistant_runtime(self) -> AssistantRuntime:
        if self._assistant_runtime is None:
            self._assistant_runtime = AssistantRuntime(discover_tools=True)
        return self._assistant_runtime

    @property
    def conversation(self) -> ConversationHistory:
        if self._conversation is None:
            self._conversation = ConversationHistory()
        return self._conversation

    @pyqtProperty("QVariantMap", notify=changed)
    def snapshot(self):
        busy = (self._request is not None or self._current_worker is not None)
        view = "busy" if busy else self._view
        search = self._search or {}
        page = self._page or {}
        displayed = self.conversation.get_turn(self._displayed_turn_id) if self._displayed_turn_id else None
        references = source_rows(
            displayed.source_refs if displayed else [],
            self._selection.path if self._selection else None,
            self._selection.page_count if self._selection else 0,
        )
        process_steps = format_process_steps(
            displayed.steps if displayed else [],
            displayed.answer_verification_status if displayed else "UNKNOWN",
            references,
        )
        if busy:
            if self._request:
                title = {"select": "Đang mở PDF.", "search": "Đang tìm trang khớp.", "page": "Đang đọc trang đã chọn."}[self._request.kind]
            else:
                title = self._status or "Đang suy nghĩ…"
        elif view == "search":
            found = search.get("matched_pages", 0)
            title = f"Tìm thấy {found} trang khớp." if found else "Chưa có trang khớp trong phần đã tìm."
        elif view == "page":
            title = f"Trang PDF {page['page']} · {page['filename']}"
        elif view == "answer":
            title = self._last_user_query or "Câu trả lời"
        elif view == "finder":
            found = len(self._finder_hits)
            title = f"Gợi ý tìm kiếm ({found})" if found else "Không có gợi ý khớp"
        elif view == "error":
            title = "Cần xem lại PDF hoặc yêu cầu."
        else:
            title = self._status

        active_context = None
        if self._selection is not None:
            active_context = {
                "type": "pdf",
                "title": self._selection.path.name,
                "subtitle": f"Trang {page.get('page', 1)}/{self._selection.page_count}" if page else f"{self._selection.page_count} trang",
                "path": str(self._selection.path),
            }
        elif self._assistant_sources:
            src = self._assistant_sources[-1]
            active_context = {
                "type": "file",
                "title": src.get("name", "Tệp"),
                "subtitle": "Tệp đính kèm",
                "path": src.get("path", ""),
            }

        cache_key = (
            id(self._active_search_hit),
            page.get("page", 0),
            len(page.get("content", "")),
            (self._search.get("query", "") if self._search else "")
        )
        if self._cached_matched_info and self._cached_matched_key == cache_key:
            matched_info = self._cached_matched_info
        else:
            matched_info = format_matched_snippet(
                self._active_search_hit,
                page.get("content", ""),
                (self._search.get("query", "") if self._search else "")
            )
            self._cached_matched_info = matched_info
            self._cached_matched_key = cache_key

        quick_prompts = []
        if self._selection is not None:
            quick_prompts = [
                {
                    "label": "Cách giải quyết",
                    "text": "Tác giả đi từng bước giải quyết vấn đề như thế nào?",
                },
                {
                    "label": "Bằng chứng số liệu",
                    "text": "Bằng chứng hay số liệu nào trong bài chứng minh điều đó?",
                },
                {
                    "label": "So sánh trước đây",
                    "text": "So với các phương pháp trước đây thì cách này hơn thua ở đâu?",
                },
                {
                    "label": "Điểm yếu hạn chế",
                    "text": "Phương pháp này có điểm yếu hoặc hạn chế nào chưa giải quyết được không?",
                },
                {
                    "label": "Luận điểm cốt lõi",
                    "text": "Luận điểm cốt lõi và kết luận quan trọng nhất của bài là gì?",
                },
            ]

        return {
            "phase": "startup" if not self._ready else "working" if busy else "result" if self._view != "none" else "idle",
            "busy": busy,
            "expanded": self._expanded,
            "workspaceMode": self._workspace_mode,
            "previewPageNumber": self._preview_page,
            "previewSnippet": self._preview_snippet,
            "previewCardIndex": self._preview_card_index,
            "unread": self._unread,
            "hasWorkbench": busy or self._view != "none",
            "view": view,
            "fileName": self._selection.path.name if self._selection else "",
            "pageCount": self._selection.page_count if self._selection else 0,
            "activeContext": active_context,
            "title": title,
            "status": self._status,
            "query": self._last_user_query or search.get("query", ""),
            "userQuery": self._last_user_query,
            "answerText": self._last_assistant_answer,
            "answerExcerpt": answer_excerpt(self._last_assistant_answer),
            "oneLineAnswer": answer_one_line(self._last_assistant_answer),
            "answerPreviewIsCode": answer_starts_with_code(self._last_assistant_answer),
            "answerOutcome": displayed.status if displayed else "unknown",
            "answerHtml": answer_html(self._last_assistant_answer),
            "answerHtmlDark": answer_html(self._last_assistant_answer, True),
            "answerSources": references,
            "quickPrompts": quick_prompts,
            "processSteps": process_steps,
            "answerReadScope": " · ".join(dict.fromkeys(row["readScope"] for row in references if row["readScope"])),
            "answerVerification": displayed.answer_verification_status if displayed else "UNKNOWN",
            "telemetry": dict(self._telemetry),
            "turnId": self._current_turn_id or "",
            "executionId": self._current_execution_id or "",
            "searchQuery": search.get("query", "") if (view == "search" or bool(self._search)) else "",
            "items": search.get("items", []) if view == "search" else [],
            "nextPage": (search.get("next_start_page") or 0) if view == "search" else 0,
            "pageText": page.get("content", "") if view == "page" else "",
            "pageReadingText": page_reading_text(page.get("content", "")) if view == "page" else "",
            "pageNumber": page.get("page", 0),
            "pageLabel": page.get("page_label", ""),
            "pageTruncated": bool(page.get("truncated")),
            "hasMatchedSnippet": matched_info["hasSnippet"],
            "matchedSnippet": matched_info["snippet"],
            "rawMatchedSnippet": matched_info["rawSnippet"],
            "matchedSnippetHtml": matched_info["snippetHtml"],
            "matchedSnippetTruncated": matched_info["truncated"],
            "matchedQuery": (self._search.get("query", "") if self._search else ""),
            "sourceKind": "search_hit" if self._active_search_hit else ("citation" if self._page_return_view == "answer" else "direct"),
            "canCopy": view == "page" or (view == "answer" and bool(self._last_assistant_answer)),
            "canBack": bool(self._search) and self._page_return_view == "search" and view in ("page", "error"),
            "canBackToAnswer": (view == "page" and self._page_return_view == "answer" and bool(self._last_assistant_answer or self._last_user_query)),
            "errorCode": self._error,
            "errorText": ERROR_MESSAGES.get(self._error, "Không xử lý được yêu cầu này."),
            "events": list(self._events),
            "contradictionReport": self._telemetry.get("contradiction_report"),
            "finderHits": list(self._finder_hits),
            "finderQuery": self._finder_query,
            "finderFeedback": self._finder_feedback,
            "readingSession": self._reading_coordinator.snapshot_data,
            "activeNote": self._reading_coordinator.active_note,
            "installedApps": list(self._cached_apps_list),
            "isAppsView": (view == "apps"),
            "savedDraft": self._saved_draft,
            "launchFeedback": self._launch_feedback,
            "launchFeedbackError": self._launch_feedback_error,
            "isQuestionQuery": self._is_conversational_query(self._finder_query),
        }

    @staticmethod
    def _is_conversational_query(text: str) -> bool:
        q = (text or "").strip()
        if not q:
            return False
        q_low = q.lower()
        if q.startswith(("?", "¿")) or q.endswith(("?", "？")):
            return True
        prefixes = (
            "sao ", "tại sao ", "vì sao ", "giải thích ", "làm sao ",
            "làm thế nào ", "cho mình ", "cho tôi ", "hãy ", "tóm tắt ",
            "so sánh ", "tính ", "viết ", "xin chào", "chào chuột",
            "how ", "why ", "what ", "explain ", "summarize ",
        )
        if any(q_low.startswith(w) for w in prefixes):
            return True
        return len(q.split()) >= 5

    @pyqtSlot()
    def ready(self):
        self._ready = True
        self.changed.emit()

    def _get_execution_service(self):
        from rat.engine.execution_service import AgentExecutionService
        return AgentExecutionService(self.assistant_runtime)

    def _begin(self, kind, *args):
        if self._closed:
            return
        if self._request:
            self._request.cancelled.set()
        self._serial += 1
        self._request = _Request(self._serial, kind, args)
        self._error = ""
        self._unread = False
        self._events = ["Đã nhận yêu cầu.", self._status]
        if self._worker is None:
            self._worker = _LatestPDFWorker(self._delivered.emit, execution_service=self._get_execution_service())
        self._worker.submit(self._request)
        self.changed.emit()

    @pyqtSlot(str)
    def openPdfDocument(self, value: str):
        """Open a PDF file, immediately displaying page 1 in the expanded desk."""
        self.selectFile(value, auto_read=True)

    @pyqtSlot(str)
    def selectFile(self, value, auto_read: bool = False):
        if self._request:
            self._request.cancelled.set()
            self._request = None
        self._auto_read_on_select = auto_read
        if not value:
            self._selection = None
            self._search = self._page = None
            self._active_search_hit = None
            self._page_return_view = "none"
            self._view = "answer" if self._last_assistant_answer else "none"
            self._status = "Chuột sẵn sàng. Bạn cần gì?" if not self._last_assistant_answer else "Đã trả lời · có thể hỏi tiếp"
            self.changed.emit()
            return
        self._selection = None
        self._search = self._page = None
        self._active_search_hit = None
        self._page_return_view = "none"
        if not auto_read:
            self._expanded = False
        self._view = "busy" if auto_read else "none"
        url = QUrl(value)
        if url.isLocalFile():
            path = url.toLocalFile()
        elif url.scheme():
            self._show_error("not_pdf")
            return
        else:
            path = value
        self._status = "Đang kiểm tra PDF…"
        self._begin("select", path)

    @pyqtSlot()
    def clearActiveContext(self):
        """Clear active file or PDF context, allowing the user to ask standalone queries."""
        if self._request:
            self._request.cancelled.set()
            self._request = None
        self._selection = None
        self._assistant_sources = []
        self._search = self._page = None
        self._active_search_hit = None
        self._page_return_view = "none"
        self._view = "answer" if self._last_assistant_answer else "none"
        self._status = "Chuột sẵn sàng. Bạn cần gì?" if not self._last_assistant_answer else "Đã trả lời · có thể hỏi tiếp"
        self.changed.emit()

    @pyqtSlot(result=bool)
    def prevPage(self) -> bool:
        if self._closed or not self._selection or self.snapshot["busy"]:
            return False
        curr = self._page.get("page", 1) if self._page else 1
        if curr > 1:
            self.readPage(curr - 1)
            return True
        return False

    @pyqtSlot(result=bool)
    def nextPage(self) -> bool:
        if self._closed or not self._selection or self.snapshot["busy"]:
            return False
        curr = self._page.get("page", 1) if self._page else 1
        if curr < self._selection.page_count:
            self.readPage(curr + 1)
            return True
        return False

    @pyqtSlot(result=bool)
    def showCurrentPdfPage(self) -> bool:
        """Return to the currently reading PDF page and expand the desk."""
        if self._closed or not self._selection:
            return False
        if self._view == "answer":
            self._page_return_view = "answer"
        else:
            self._page_return_view = "none"
        self._active_search_hit = None
        curr = self._page.get("page", 1) if self._page else 1
        if self._view != "page":
            self.readPage(curr)
        self._expanded = True
        self._unread = False
        self.changed.emit()
        return True

    @pyqtSlot()
    def backToAnswer(self):
        """Return from reading a cited PDF page back to the Answer without re-calling model."""
        if self._closed or self._view != "page" or self._page_return_view != "answer":
            return
        self._view = "answer"
        self._page_return_view = "none"
        self._expanded = True
        self._unread = False
        self._status = "Đã trả lời · có thể hỏi tiếp" if self._last_assistant_answer else "Đã dừng yêu cầu"
        self.changed.emit()

    @pyqtSlot(int, result=bool)
    def jumpToPdfPage(self, page_number: int) -> bool:
        """Jump to a specific PDF page, e.g. from an in-text citation click."""
        if self._closed or self._request is not None or self._current_worker is not None:
            return False
        if self._selection is not None and 1 <= page_number <= self._selection.page_count:
            if self._view == "answer":
                self._page_return_view = "answer"
            self.readPage(page_number)
            self._view = "page"
            self._expanded = True
            self.changed.emit()
            return True
        return False

    @pyqtSlot(int, result=bool)
    def openAnswerSource(self, index: int) -> bool:
        """Read only an explicit page ref for the currently selected PDF."""
        rows = self.snapshot["answerSources"]
        if not 0 <= index < len(rows) or not rows[index]["canOpen"]:
            return False
        return self.jumpToPdfPage(rows[index]["page"])

    @pyqtSlot(str)
    def setWorkspaceMode(self, mode: str) -> None:
        """Set the workspace mode: 'minimal', 'single', or 'multi'."""
        if mode in ("minimal", "single", "multi") and self._workspace_mode != mode:
            self._workspace_mode = mode
            if mode == "minimal":
                self._expanded = False
            else:
                self._expanded = True
            self.changed.emit()

    @pyqtSlot(int, result=bool)
    def previewPdfPage(self, page_number: int) -> bool:
        """Preview a PDF page in side-by-side mode without changing the active answer view."""
        return self.previewPdfPageWithSnippet(page_number, "")

    @pyqtSlot(int, str, result=bool)
    def previewPdfPageWithSnippet(self, page_number: int, snippet: str = "") -> bool:
        """Preview a PDF page and highlight snippet in side-by-side mode without altering answer view."""
        if self._closed or self._selection is None:
            return False
        if not 1 <= page_number <= self._selection.page_count:
            return False
        self._preview_page = page_number
        self._preview_snippet = snippet
        self.changed.emit()
        return True

    @pyqtSlot(int)
    def selectPreviewCard(self, index: int) -> None:
        """Select a tarot or reading card for interactive inspection."""
        self._preview_card_index = index
        self.changed.emit()

    @pyqtSlot(str, int, str, str, result=str)
    def pageSnapshot(self, path: str, page: int, query: str = "", snippet: str = "") -> str:
        """Render a cropped match snapshot only for the currently selected PDF."""
        if self._closed or self._selection is None or not path or page < 1:
            return ""
        try:
            resolved = Path(path).expanduser().resolve()
        except (OSError, RuntimeError, ValueError):
            return ""
        if resolved != self._selection.path or page > self._selection.page_count:
            return ""
        return self._snapshot_renderer.render_data_url(
            self._selection.path,
            page,
            query,
            snippet,
        )

    @pyqtSlot(str, int, int, result=str)
    def fullPageSnapshot(self, path: str, page: int, width: int = 1200) -> str:
        """Render a full crisp PDF page only for the currently selected PDF."""
        if self._closed or self._selection is None or not path or page < 1:
            return ""
        try:
            resolved = Path(path).expanduser().resolve()
        except (OSError, RuntimeError, ValueError):
            return ""
        if resolved != self._selection.path or page > self._selection.page_count:
            return ""
        return self._snapshot_renderer.render_full_page_data_url(
            self._selection.path,
            page,
            width=width,
        )

    @pyqtSlot(str)
    def submitQuery(self, query: str):
        self.submit(query)

    @pyqtSlot(str)
    def search(self, query: str):
        if self._request or self._current_worker:
            return
        if self._selection is not None:
            self._search_from(query, 1)
        else:
            self.submit(query)

    def _search_from(self, query, start):
        end = min(self._selection.page_count, start + 399)
        self._status = f"Đang tìm từ khóa trong trang PDF {start}–{end}…"
        self._begin("search", self._selection, query, start)

    @pyqtSlot()
    def nextBatch(self):
        if not self._request and self._selection and self._search and self._search.get("next_start_page"):
            self._search_from(self._search["query"], self._search["next_start_page"])

    @pyqtSlot(int)
    def openSearchHit(self, page: int):
        """Open a search match page, preparing the matched snippet view."""
        if self._search and self._selection and not self._request:
            self._active_search_hit = next((it for it in self._search.get("items", []) if it.get("page") == page), None)
            self._page_return_view = "search"
        self.readPage(page)

    @pyqtSlot(int)
    def readPage(self, page):
        if self._request or not self._selection:
            return
        if self._search and self._view == "search":
            self._active_search_hit = next((it for it in self._search.get("items", []) if it.get("page") == page), None)
            self._page_return_view = "search"
        elif self._search and self._active_search_hit and self._active_search_hit.get("page") != page:
            self._active_search_hit = next((it for it in self._search.get("items", []) if it.get("page") == page), None)
        self._status = f"Đang đọc trang PDF {page}…"
        self._begin("page", self._selection, page)

    @pyqtSlot()
    def backToSearch(self):
        if self._search and not self._request:
            self._view = "search"
            self._error = ""
            self._expanded = True
            self._unread = False
            self._status = self._search_summary(self._search)
            self.changed.emit()

    @staticmethod
    def _search_summary(data):
        start, end = data["searched_range"]
        return (f"Đã tìm trang PDF {start}–{end} / {data['page_count']}. "
                f"{data['matched_pages']} trang khớp; đang hiện {len(data['items'])}. "
                f"{len(data['textless_pages'])} trang không có văn bản trích xuất. "
                "Tìm theo từ khóa; OCR chưa chạy.")

    def _show_error(self, code):
        if self._request:
            self._request.cancelled.set()
            self._request = None
        self._error = code
        self._view = "error"
        self._status = ERROR_MESSAGES.get(code, f"Lỗi: {code}")
        self._events.append(self._status)
        self._unread = not self._expanded
        self.changed.emit()

    @pyqtSlot(int, str, object)
    def _finish(self, serial, outcome, data):
        if self._closed or self._request is None or serial != self._request.serial:
            return
        request, self._request = self._request, None
        if request.cancelled.is_set() or outcome == "cancelled":
            return
        if outcome == "error":
            self._show_error(data)
            return
        if request.kind == "select":
            self._selection = data
            self._status = f"{data.path.name} · {data.page_count} trang PDF. Hỏi trực tiếp trong ô chat hoặc bấm ⌘F để tìm từ khóa."
            if self._auto_read_on_select:
                self._auto_read_on_select = False
                self._expanded = True
                self.readPage(1)
            else:
                self._view = "none"
        elif request.kind == "search":
            self._search = data
            self._view = "search"
            self._status = self._search_summary(data)
            self._unread = not self._expanded
        else:
            self._page = data
            self._view = "page"
            self._status = (f"Đã đọc trang PDF {data['page']} · nhãn PDF {data['page_label']}. "
                            + ("Văn bản đã cắt ở 8.000 ký tự. " if data["truncated"] else "")
                            + "Bôi chọn đoạn muốn chép; nếu chưa chọn, dùng tối đa 500 ký tự đầu trang.")
            self._unread = not self._expanded
        self._events.append(self._status)
        self.changed.emit()

    @pyqtSlot(bool)
    def setExpanded(self, expanded):
        self._expanded = expanded
        if expanded:
            self._unread = False
        self.changed.emit()

    @pyqtSlot()
    def cancel(self):
        # Cancel PDF job if active
        if self._request:
            self._request.cancelled.set()
            self._request = None

        # Cancel finder coordinator if active
        if self._finder_coordinator:
            self._finder_coordinator.cancel()
        if self._view == "finder":
            self._view = "none"
            self._finder_hits = []

        # Cancel chat / reasoning worker if active
        if self._current_worker:
            if self._current_execution_id:
                self.assistant_runtime.cancel_execution(self._current_execution_id)
            if hasattr(self._current_worker, "requestInterruption"):
                self._current_worker.requestInterruption()
            if self._current_turn_id:
                try:
                    self.conversation.cancel_turn(self._current_turn_id, execution_id=self._current_execution_id)
                except Exception:
                    pass
                self._displayed_turn_id = self._current_turn_id
                self._last_assistant_answer = ""
                self._view = "answer"
                self._unread = False
            self._current_worker = None

        self._status = "Đã dừng yêu cầu. Nội dung đang nhập vẫn được giữ."
        self._events.append(self._status)
        self.changed.emit()

    def _set_and_verify_clipboard(self, text: str) -> bool:
        app_inst = QGuiApplication.instance()
        if app_inst is None:
            return False
        cb = app_inst.clipboard()
        if cb is None:
            return False
        cb.setText(text)
        return cb.text() == text

    @pyqtSlot(str, result=bool)
    def copyCitation(self, selected_text=""):
        if self.snapshot["busy"]:
            return False
        if self._view == "answer":
            text = selected_text.strip() if selected_text.strip() else self._last_assistant_answer
            if self._set_and_verify_clipboard(text):
                self.copyConfirmed.emit(text)
                self.copyReady.emit(text)
                return True
            return False
        if not self._selection or not self._page or self._view != "page":
            return False
        try:
            effective_sel = selected_text.strip()
            if not effective_sel and self._active_search_hit and self._active_search_hit.get("snippet"):
                effective_sel = self._active_search_hit["snippet"].strip()
            text = citation_text(self._selection, self._page, effective_sel)
        except SelectedPDFError as exc:
            self._show_error(exc.code)
            return False
        if self._set_and_verify_clipboard(text):
            self.copyConfirmed.emit(text)
            self.copyReady.emit(text)
            return True
        return False

    @pyqtSlot(result=bool)
    def openOriginal(self):
        if not self._selection:
            return False
        try:
            check_current(self._selection)
        except SelectedPDFError as exc:
            self._show_error(exc.code)
            return False
        if self._open_url is None:
            from PyQt6.QtGui import QDesktopServices
            opener = QDesktopServices.openUrl
        else:
            opener = self._open_url
        accepted = bool(opener(QUrl.fromLocalFile(str(self._selection.path))))
        if not accepted:
            self._show_error("open_failed")
        return accepted

    @pyqtSlot(int, result=str)
    def getExpandedContext(self, source_index: int = 0) -> str:
        """Return extended surrounding context for the primary source reference using registered tool contract."""
        try:
            sources = self.snapshot.get("answerSources", [])
            if 0 <= source_index < len(sources):
                s = sources[source_index]
                ext = (s.get("extendedSnippet") or "").strip()
                if ext and len(ext) > len((s.get("snippet") or "").strip()):
                    return ext
                # Invoke registered expand_document_context operation via AgentExecutionService
                file_path = s.get("path") or (str(self._selection.path) if self._selection else "")
                if file_path and getattr(self, "assistant_runtime", None) is not None:
                    try:
                        from rat.engine.execution import ExecutionRequest
                        from rat.engine.execution_service import AgentExecutionService

                        req = ExecutionRequest(
                            "Mở rộng ngữ cảnh đoạn trích",
                            execution_id=f"expand-{uuid4().hex[:12]}",
                            origin="ui_action",
                            requested_action={
                                "name": "expand_document_context",
                                "args": {
                                    "file_path": file_path,
                                    "target_excerpt": s.get("snippet", ""),
                                    "page": s.get("page"),
                                    "max_chars": 2000,
                                },
                            },
                            context={"selected_document_path": file_path},
                        )
                        service = AgentExecutionService(self.assistant_runtime)
                        resp = service.execute(req)
                        if not resp.error and resp.artifacts:
                            art = resp.artifacts[0]
                            res = art.payload
                            if isinstance(res, dict) and res.get("found"):
                                return str(res.get("content", ""))
                    except Exception:
                        pass
                return s.get("snippet", "")
        except Exception:
            pass
        return ""

    @pyqtSlot(str, result=bool)
    def navigateToTurn(self, turn_id: str) -> bool:
        """View a historical turn without redispatching model or clearing user's composer draft."""
        snap = self.conversation.get_turn(turn_id)
        if snap is None:
            return False
        self._view = "answer"
        self._last_user_query = snap.query
        self._last_assistant_answer = snap.answer or ""
        self._displayed_turn_id = turn_id
        self._status = f"Lượt {turn_id} · {snap.status}"
        self._expanded = True
        self._unread = False
        self.changed.emit()
        return True

    def commit_artifact(self, artifact: Artifact, *, expected_revision: Optional[int] = None) -> Artifact:
        """Commit an artifact to the artifact store under optimistic locking."""
        art_store = getattr(self.assistant_runtime, "artifact_store", None)
        if art_store is None:
            raise ValueError("no_artifact_store")
        committed = art_store.put(artifact, expected_revision=expected_revision)
        if self._current_turn_id:
            try:
                turn = self.conversation.get_turn(self._current_turn_id)
                if turn:
                    turn.artifact_refs = [committed.to_dict()]
                    self.conversation._turn_snapshots[self._current_turn_id] = turn
            except Exception:
                pass
        return committed

    def submit(
        self,
        query: str,
        *,
        target_turn_id: Optional[str] = None,
        target_artifact_id: Optional[str] = None,
        target_revision: Optional[int] = None,
        origin: str = "chat",
    ) -> bool:
        """Submit a query through the shared execution factory and workers."""
        q = query.strip()
        if not q or self.snapshot["busy"] or self._closed:
            return False
        if self._view == 'reading':
            return self.synthesizeReadingDraft(query=q)
        if self._selection is not None:
            try:
                check_current(self._selection)
            except SelectedPDFError as exc:
                self._show_error(exc.code)
                return False

        # Clear finder query and cancel any pending finder jobs
        self._finder_query = ""
        self._finder_hits = []
        if self._finder_coordinator is not None:
            self._finder_coordinator.cancel()

        history_messages = self.conversation.messages_with_turn_ids()
        turn_references = self.conversation.turn_references()
        art_store = getattr(self.assistant_runtime, "artifact_store", None)
        active_arts = [
            {"id": a.id, "kind": a.kind, "revision": a.revision, "title": a.title, "inputs": getattr(a, "inputs", {})}
            for a in (art_store.list() if art_store is not None else [])
        ]
        if art_store is not None and target_artifact_id and target_revision is not None:
            src_art = art_store.get(target_artifact_id, revision=target_revision)
            if src_art is not None and not any(a["id"] == src_art.id and a["revision"] == src_art.revision for a in active_arts):
                active_arts.append(src_art.to_dict())

        turn_snap = self.conversation.begin_turn(
            q,
            target_turn_id=target_turn_id,
            target_artifact_id=target_artifact_id,
            target_revision=target_revision,
        )
        turn_ref = turn_snap.turn_ref
        execution_id = turn_snap.execution_id

        app_inst = QGuiApplication.instance()
        engine = self._reasoning_engine
        if engine is None and app_inst is not None:
            engine = app_inst.property("ratReasoningEngine")
        allow_synth = self._allow_synthetic_policy
        if not allow_synth and app_inst is not None:
            allow_synth = app_inst.property("ratAllowSyntheticPolicy") is True

        lane = "document" if self._selection is not None else ("reasoning" if engine is not None else "auto")

        source_evidence = []
        if self._selection is not None:
            pdf_path_str = str(self._selection.path)
            try:
                pdf_sha = hashlib.sha256(self._selection.path.read_bytes()).hexdigest()
            except Exception:
                pdf_sha = ""
            history_messages = self.conversation.document_messages(pdf_path_str, pdf_sha) if pdf_sha else []
            current_pg = self._page.get("page", 1) if self._page else 1
            excerpt = (self._page.get("content", "") if self._page else "")[:1000]
            source_evidence.append({
                "source_id": f"src-pdf-{self._selection.path.stem}",
                "kind": "pdf_page",
                "path": pdf_path_str,
                "page_num": current_pg,
                "excerpt": excerpt,
                "sha256": pdf_sha,
                "provenance": {"title": self._selection.path.name, "page_count": self._selection.page_count},
            })

        for i, src in enumerate(self._assistant_sources):
            content = src.get("content", "")
            sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
            source_evidence.append({
                "source_id": f"src-file-{i+1}",
                "kind": "file_excerpt",
                "path": src.get("path", ""),
                "excerpt": content[:1000],
                "sha256": sha,
                "provenance": {"name": src.get("name", "")},
            })

        resource_bindings = []
        if self._selection is not None and getattr(self._selection, "path", None) and self._selection.path.is_file():
            try:
                doc_sha = hashlib.sha256(self._selection.path.read_bytes()).hexdigest()
                resource_bindings.append({
                    "kind": "document",
                    "path": str(self._selection.path),
                    "file_path": str(self._selection.path),
                    "sha256": doc_sha,
                })
            except Exception:
                pass

        request = ExecutionRequest(
            q,
            execution_id=execution_id,
            generation=self._chat_generation,
            turn_ref=turn_ref,
            lane=lane,
            origin=origin,
            document_path=str(self._selection.path) if self._selection is not None else None,
            resource_bindings=resource_bindings,
            context={
                "history": history_messages,
                "turn_references": turn_references,
                "artifact_refs": active_arts,
                "previous_sources": list(self._assistant_sources),
                "source_evidence": source_evidence,
                "requires_grounding": bool(source_evidence),
                "task_state": dict(self._assistant_task_state),
            },
        )

        try:
            worker = create_execution_worker(
                self.assistant_runtime,
                request,
                reasoning_engine=engine,
                allow_synthetic_policy=allow_synth,
            )
        except Exception as exc:
            self.conversation.fail_turn(turn_ref.turn_id, "failed", execution_id=execution_id)
            self._show_error(f"worker_creation_failed:{exc}")
            return False

        startup_err = getattr(worker, "startup_error", None)
        if startup_err:
            self.conversation.fail_turn(
                turn_ref.turn_id,
                "failed",
                execution_id=execution_id,
                partial_answer=f"Lỗi: {startup_err}",
            )
            self._last_user_query = q
            self._last_assistant_answer = f"Không thể xử lý yêu cầu: {startup_err}"
            self._status = f"Lỗi khởi tạo: {startup_err}"
            self._view = "answer"
            self._unread = not self._expanded
            self._events.append(self._status)
            self.changed.emit()
            return False

        self._current_worker = worker
        self._current_execution_id = execution_id
        self._current_turn_id = turn_ref.turn_id
        self._last_user_query = q
        self._unread = False
        self._status = "Chuột đang xử lý yêu cầu…"
        self._events.append(f"Đã gửi yêu cầu: {q}")
        self.changed.emit()

        # response_ready arrives before run() has returned. Hold even cancelled
        # workers until QThread.finished, including cleanup after a model timeout.
        self._execution_workers.add(worker)
        worker.finished.connect(lambda w=worker: self._execution_workers.discard(w))
        worker.response_ready.connect(lambda res, req=request: self._execution_delivered.emit(req, res))
        status_signal = (worker.status_changed if hasattr(worker, "status_changed")
                         else worker.progress_changed)
        status_signal.connect(
            lambda st, eid=execution_id, gen=self._chat_generation: self._execution_status_delivered.emit(eid, gen, st)
        )
        worker.start()
        return True

    @pyqtSlot(object, object)
    def _handle_execution_delivered(self, req, raw_result):
        resp = raw_result if isinstance(raw_result, AgentResponse) else execution_response(req, raw_result)
        if req.document_path and not resp.error:
            evidence = next((s for s in req.context_snapshot()["source_evidence"]
                             if s.get("path") == req.document_path and s.get("sha256")), None)
            if evidence and any(s.get("path") == req.document_path and s.get("read") is True
                                for s in resp.sources if isinstance(s, dict)):
                resp.qa_telemetry = {**(resp.qa_telemetry or {}), "document_scope": {
                    "path": req.document_path, "sha256": evidence["sha256"]}}
        self._on_execution_response(resp)

    @pyqtSlot(object)
    def _on_execution_response(self, response: AgentResponse):
        if self._closed or self._current_worker is None:
            return
        if getattr(response, "execution_id", None) != self._current_execution_id:
            return

        self._current_worker = None
        turn_id = self._current_turn_id
        self._displayed_turn_id = turn_id

        err = getattr(response, "error", None) or (getattr(response, "status", None) if getattr(response, "status", None) != "completed" else None)
        if err in ("cancelled", "budget_exceeded", "timeout", "failed", "unresolved") or err is not None:
            status_kind = err if err in ("cancelled", "budget_exceeded", "timeout", "failed", "unresolved") else "failed"
            try:
                self.conversation.fail_turn(
                    turn_id,
                    "cancelled" if status_kind == "cancelled" else "failed",
                    error=status_kind,
                    execution_id=self._current_execution_id,
                    partial_answer=response.answer,
                )
            except Exception:
                pass
            self._last_assistant_answer = response.answer or ""
            self._telemetry = {**(getattr(response, "telemetry_breakdown", {}) or {}),
                               **(getattr(response, "qa_telemetry", {}) or {})}
            if status_kind == "budget_exceeded":
                self._status = "Đã vượt hạn mức ngân sách (0 tokens/requests/strategies)."
            elif status_kind == "timeout":
                self._status = "Hết thời gian xử lý yêu cầu."
            elif status_kind == "unresolved":
                self._status = "Không thể giải quyết yêu cầu với dữ kiện hiện có."
            elif status_kind == "cancelled":
                self._status = "Đã dừng · có thể gửi yêu cầu mới"
            elif err == "empty_model_response":
                self._status = "Model trả về nội dung rỗng. Bạn có thể thử gửi lại."
            else:
                self._status = "Yêu cầu chưa hoàn tất"
            self._view = "answer"
            self._unread = not self._expanded
            self._events.append(self._status)
            self._events.append("Lỗi thực thi: " + " ".join(str(err).split())[:500])
            self.changed.emit()
            return

        curr_telem = {**(getattr(response, "telemetry_breakdown", {}) or {}),
                      **(getattr(response, "qa_telemetry", {}) or {})}
        self._telemetry = curr_telem

        art_refs = None
        if getattr(response, "artifacts", None):
            art_refs = [a.to_dict() for a in response.artifacts]
        elif curr_telem.get("target_artifact_id"):
            art_store = getattr(self.assistant_runtime, "artifact_store", None)
            if art_store:
                art = art_store.get(curr_telem["target_artifact_id"])
                if art:
                    art_refs = [art.to_dict()]

        steps_data = []
        for s in (response.steps or []):
            if hasattr(s, "to_dict"):
                steps_data.append(s.to_dict())
            elif hasattr(s, "__dataclass_fields__"):
                steps_data.append({
                    "step_number": getattr(s, "step_number", 1),
                    "thought": getattr(s, "thought", "") or "",
                    "tool_name": getattr(s, "tool_name", "") or "",
                    "tool_args": dict(getattr(s, "tool_args", {}) or {}),
                    "tool_result": s.tool_result if isinstance(s.tool_result, (dict, list, str, int, float, bool)) else None,
                    "duration_ms": round(float(getattr(s, "duration_ms", 0.0) or getattr(s, "tool_duration_ms", 0.0) or 0.0), 2),
                    "error": getattr(s, "error", "") or "",
                })
            elif isinstance(s, dict):
                steps_data.append(s)

        self.conversation.complete_turn(
            turn_id,
            response.answer,
            execution_id=self._current_execution_id,
            artifact_refs=art_refs,
            task_state={"document_scope": curr_telem["document_scope"]} if curr_telem.get("document_scope") else None,
            source_refs=[s.to_dict() if hasattr(s, "to_dict") else s for s in (response.sources or []) if isinstance(s, dict) or hasattr(s, "to_dict")],
            answer_verification_status=response.answer_verification_status,
            steps=steps_data,
        )

        self._last_assistant_answer = response.answer
        self._view = "answer"
        refs = [s for s in (response.sources or []) if hasattr(s, "page") or (isinstance(s, dict) and "page" in s)]
        if refs:
            p = getattr(refs[0], "page", None) if hasattr(refs[0], "page") else refs[0].get("page")
            if isinstance(p, int) and p > 0:
                self._preview_page = p
        # Respect the user's current mode; a completed answer updates the preview.
        self._unread = not self._expanded

        c_rep = self._telemetry.get("contradiction_report")
        if c_rep and not c_rep.get("passed"):
            count = len(c_rep.get("findings", []))
            self._status = f"Phát hiện {count} mâu thuẫn trong chuỗi suy luận"
            self._events.append(f"⚠️ ContradictionAuditor: {count} mâu thuẫn đơn điệu bị gắn cờ.")
        elif self._telemetry.get("bundle_review_status") == "synthetic_development_only":
            self._status = "Bản thử nghiệm · kết quả fixture, chưa đánh giá model"
        else:
            self._status = "Đã trả lời · có thể hỏi tiếp"

        self._events.append(self._status)
        self.changed.emit()

    @pyqtSlot(str, int, str)
    def _on_execution_status(self, eid: str, gen: int, status: str):
        if self._closed or self._current_worker is None or eid != self._current_execution_id or gen != self._chat_generation:
            return
        if status == "cancel":
            self._status = "Đang dừng xử lý…"
        elif status == "wait":
            self._status = "Đang chờ kết quả…"
        elif status not in ("working", "done", "error"):
            self._status = status
        self.changed.emit()

    def _update_cached_apps(self, catalog: ApplicationCatalog):
        self._cached_apps_list = [
            {
                "resource_id": app.resource_id,
                "name": app.name,
                "path": app.path,
                "bundle_id": app.bundle_id,
                "version": app.version,
                "names": list(app.names),
                "icon_url": f"image://icon/{app.path}",
            }
            for app in sorted(catalog.applications, key=lambda a: a.name.lower())
        ]

    @pyqtSlot(object)
    def _on_catalog_ready(self, catalog: ApplicationCatalog):
        if self._closed or self._finder_coordinator is not None:
            return
        self._finder_catalog = catalog
        self._finder_search = ProgressiveSearch(self._db_path, catalog=catalog, semantic=self._finder_semantic)
        self._finder_coordinator = SearchCoordinator(
            self._finder_search,
            on_update=lambda snap: self._finder_delivered.emit(snap),
            execution_service=self._get_execution_service(),
        )
        self._update_cached_apps(catalog)
        self.changed.emit()
        if self._finder_query and self._selection is None and not self.snapshot["busy"] and self._view != "apps":
            self._finder_coordinator.submit(self._finder_query, limit=10)

    @pyqtSlot(str)
    def onComposerTextChanged(self, text: str):
        if self._closed:
            return
        if self._view == "reading":
            return
        if self._launch_feedback:
            self._launch_feedback = ""
            self._launch_feedback_error = False
            self.changed.emit()
        if self._view == "apps":
            self._finder_query = text.strip()
            self.changed.emit()
            return
        if self._selection is not None:
            return
        if self.snapshot["busy"]:
            return
        q = text.strip()
        had_feedback = bool(self._finder_feedback)
        self._finder_feedback = ""
        query_changed = q != self._finder_query
        self._finder_query = q
        # Do not let Enter open an old query's row while the latest query runs.
        if q and query_changed and self._finder_hits:
            self._finder_hits = []
            self.changed.emit()
        elif had_feedback:
            self.changed.emit()
        if not q:
            if self._finder_coordinator is not None:
                self._finder_coordinator.cancel()
            had_hits = bool(self._finder_hits)
            self._finder_hits = []
            if self._view == "finder":
                self._restore_pre_finder_state()
                self.changed.emit()
            elif had_hits:
                self.changed.emit()
            return
        if self._finder_coordinator is not None:
            self._finder_coordinator.submit(q, limit=10)

    def _restore_pre_finder_state(self):
        """Restore previous view, expanded mode, and status prior to finder suggestions."""
        has_answer_context = bool(
            self._last_assistant_answer
            or self._last_user_query
            or self._displayed_turn_id
            or (self._current_turn_id and self.conversation.get_turn(self._current_turn_id))
        )
        if self._pre_finder_view and self._pre_finder_view != "none":
            target = self._pre_finder_view
        elif has_answer_context:
            target = "answer"
        else:
            target = "none"

        self._view = target
        if target != "none":
            self._expanded = self._pre_finder_expanded
            if self._pre_finder_status:
                self._status = self._pre_finder_status
            elif self._last_assistant_answer:
                self._status = "Đã trả lời · có thể hỏi tiếp"
            elif self._last_user_query:
                self._status = "Đã dừng yêu cầu. Nội dung đang nhập vẫn được giữ."
        else:
            self._expanded = False
            self._status = self._pre_finder_status or "Chuột sẵn sàng. Bạn cần gì?"
        self._pre_finder_view = "none"
        self._pre_finder_status = None

    @pyqtSlot()
    def dismissFinder(self):
        """Dismisses finder suggestions and restores previous workbench state, preserving composer draft."""
        if self._closed:
            return
        if self._finder_coordinator is not None:
            self._finder_coordinator.cancel()
        if self._view == "finder":
            self._restore_pre_finder_state()
            if self._view == "none":
                self._finder_hits = []
                self._finder_query = ""
            self.changed.emit()
        elif not self._last_assistant_answer and not self._last_user_query and self._finder_hits:
            self._finder_hits = []
            self.changed.emit()

    @pyqtSlot(result=bool)
    def openFinderSuggestions(self) -> bool:
        """Explicitly open latent Finder suggestions from the subtle drawer tab."""
        if self._closed or self.snapshot["busy"] or not self._finder_hits:
            return False
        if self._view != "finder":
            self._pre_finder_view = self._view
            self._pre_finder_expanded = self._expanded
            self._pre_finder_status = self._status
        self._view = "finder"
        count = len(self._finder_hits)
        self._status = f"Tìm thấy {count} gợi ý cho '{self._finder_query}'"
        self._expanded = True
        self._unread = False
        self.changed.emit()
        return True

    @pyqtSlot(object)
    def _handle_finder_snapshot(self, snapshot: SearchSnapshot):
        if self._closed:
            return
        if self._finder_coordinator and not self._finder_coordinator.is_current(snapshot.query_id):
            return
        # If composer query changed or was cleared (e.g. submitted), ignore stale hit
        if not self._finder_query or snapshot.query != self._finder_query:
            return
        if self._selection is not None or self.snapshot["busy"]:
            return

        home_str = str(Path.home())
        raw_hits = []
        for h in snapshot.hits:
            display_path = h.path
            if display_path.startswith(home_str):
                display_path = "~" + display_path[len(home_str):]
            snippet = h.snippet or display_path
            if snippet.startswith(home_str):
                snippet = "~" + snippet[len(home_str):]
            p = Path(h.path)
            parent_name = p.parent.name if p.parent and p.parent.name else ""
            raw_hits.append({
                "resource_id": h.resource_id,
                "kind": h.kind,
                "title": h.title,
                "path": h.path,
                "parent_name": parent_name,
                "file_name": p.name,
                "display_path": display_path,
                "origin": h.origin,
                "match_reason": h.match_reason or ("Khớp tên ứng dụng" if h.kind == "application" else "Khớp chỉ mục tài liệu"),
                "snippet": snippet,
                "bundle_id": h.bundle_id or "",
                "is_pdf": h.path.lower().endswith(".pdf"),
            })

        # Group by category: Applications first, then Files & PDFs
        apps = [h for h in raw_hits if h["kind"] == "application"]
        docs = [h for h in raw_hits if h["kind"] != "application"]
        hits = []
        if apps:
            for i, h in enumerate(apps):
                h["is_first_of_section"] = (i == 0)
                h["section_title"] = "ỨNG DỤNG"
                hits.append(h)
        if docs:
            for i, h in enumerate(docs):
                h["is_first_of_section"] = (i == 0)
                h["section_title"] = "TÀI LIỆU & TỆP"
                hits.append(h)

        count = len(hits)
        if count == 0:
            if snapshot.intent and snapshot.intent.resource_kind in ("file", "slide", "report"):
                self._finder_feedback = (
                    "Chưa truy cập được chỉ mục tệp. Bạn có thể chọn tệp bằng nút đính kèm."
                    if 'file_index_unavailable' in snapshot.errors else
                    "Chưa thấy tệp khớp trong chỉ mục. Bạn nhớ thêm chủ đề, loại tệp hoặc thời gian không?"
                )
            had_hits = bool(self._finder_hits)
            self._finder_hits = []
            if self._view == "finder":
                self._restore_pre_finder_state()
                self.changed.emit()
            elif had_hits or self._finder_feedback:
                self.changed.emit()
            return

        # Keep active answer reading or conversational typing intact; expose hits via subtle drawer tab.
        reading_answer = (
            self._view == "answer"
            or (self._view == "finder" and self._pre_finder_view == "answer" and self._is_conversational_query(snapshot.query))
        )
        if reading_answer or self._is_conversational_query(snapshot.query):
            self._finder_hits = hits
            if self._view == "finder" and self._is_conversational_query(snapshot.query):
                self._restore_pre_finder_state()
            self.changed.emit()
            return

        if self._view != "finder":
            self._pre_finder_view = self._view
            self._pre_finder_expanded = self._expanded
            self._pre_finder_status = self._status
        self._finder_hits = hits
        self._view = "finder"
        self._status = f"Tìm thấy {count} gợi ý cho '{snapshot.query}'"
        self._expanded = True
        self._unread = False
        self.changed.emit()

    @pyqtSlot(str, result=bool)
    def openHit(self, path: str) -> bool:
        if not path:
            return False
        p = Path(path)
        if p.suffix.casefold() == ".app":
            return self._open_application(p)
        if not p.exists():
            self._launch_feedback = f"Không thể mở {p.name}: tệp không còn ở vị trí đã tìm thấy."
            self._launch_feedback_error = True
            self.changed.emit()
            return False
        opener = self._open_url if self._open_url is not None else QDesktopServices.openUrl
        try:
            accepted = bool(opener(QUrl.fromLocalFile(str(p.resolve()))))
        except Exception:
            accepted = False
        self._launch_feedback = (f"Đã gửi yêu cầu mở {p.name}." if accepted
                                 else f"Không thể gửi yêu cầu mở {p.name}. Bạn có thể thử lại.")
        self._launch_feedback_error = not accepted
        self.changed.emit()
        return accepted

    def _open_application(self, path: Path) -> bool:
        """Project a checked launch receipt from the shared execution service."""
        try:
            from rat.engine.execution_service import AgentExecutionService

            def ui_launcher(app):
                opener = self._open_url if self._open_url is not None else QDesktopServices.openUrl
                return bool(opener(QUrl.fromLocalFile(app.path)))

            request = ExecutionRequest(
                f"Mở ứng dụng {path.stem}", execution_id=f"app-{uuid4().hex[:12]}", origin="ui_action",
                requested_action={"name": "open_application", "args": {"path": str(path)}},
                context={"catalog": self._finder_catalog, "app_launcher": ui_launcher},
            )
            response = AgentExecutionService(self.assistant_runtime).execute(request)
            accepted = not response.error and bool(response.artifacts)
            name = response.artifacts[0].payload.get("name", path.stem) if accepted else path.stem
        except Exception:
            logger.exception("Application launch through execution service failed")
            accepted, name = False, path.stem
        self._launch_feedback_error = not accepted
        self._launch_feedback = (f"Đã gửi yêu cầu mở {name}." if accepted else
                                 f"Không thể mở {name}. Kiểm tra bản cài đặt hoặc thử lại.")
        self.changed.emit()
        return accepted

    @pyqtSlot(str)
    def openAppsView(self, current_draft: str = ""):
        """Enters Apps Catalog grid mode, preserving composer draft and context."""
        if self._closed or self.snapshot["busy"]:
            return
        if self._view != "apps":
            self._prior_view = self._view
            self._saved_draft = current_draft
        self._view = "apps"
        self._expanded = True
        self._unread = False
        count = len(self._cached_apps_list)
        self._status = f"Ứng dụng đã cài đặt ({count}) · Bấm icon hoặc Enter để mở"
        self.changed.emit()

    @pyqtSlot(result=str)
    def closeAppsView(self) -> str:
        """Exits Apps Catalog grid mode and returns preserved composer draft."""
        if self._closed:
            return ""
        self._view = self._prior_view if self._prior_view != "apps" else ("answer" if self._last_assistant_answer else "none")
        restored = self._saved_draft
        self._saved_draft = ""
        self._finder_query = ""
        self._status = "Chuột sẵn sàng. Bạn cần gì?" if not self._last_assistant_answer else "Đã trả lời · có thể hỏi tiếp"
        self.changed.emit()
        return restored

    @pyqtSlot(str, result=bool)
    def launchApplication(self, path: str) -> bool:
        """Launches application bundle via standard OS handler, preserving draft."""
        if self._closed or not path:
            return False
        return self.openHit(path)

    @pyqtSlot()
    def openReadingDesk(self):
        self._reading_coordinator.open_desk()

    @pyqtSlot()
    def closeReadingDesk(self):
        self._reading_coordinator.close_desk()

    @pyqtSlot(str, result=bool)
    def setReadingCards(self, text: str) -> bool:
        return self._reading_coordinator.set_cards(text)

    @pyqtSlot(str, result=bool)
    def importReadingProfile(self, path: str) -> bool:
        return self._reading_coordinator.import_profile(path)

    @pyqtSlot(result=bool)
    @pyqtSlot(str, result=bool)
    def synthesizeReadingDraft(self, query: str = "") -> bool:
        return self._reading_coordinator.synthesize_draft(query)

    @pyqtSlot(str, result=bool)
    def saveReadingDraft(self, text: str) -> bool:
        return self._reading_coordinator.save_draft(text)

    @pyqtSlot(str, str, str, result=str)
    @pyqtSlot(str, str, result=str)
    @pyqtSlot(str, result=str)
    def synthesizeSmartNote(self, raw_content: str, domain: str = "auto", title: str = "") -> str:
        return self._reading_coordinator.synthesize_smart_note(raw_content, domain, title)

    @pyqtSlot(result=str)
    @pyqtSlot(str, result=str)
    def synthesizeNoteFromReadingDraft(self, domain: str = "decision") -> str:
        return self._reading_coordinator.synthesize_from_current_draft(domain=domain)

    @pyqtSlot(str, str, bool, result=bool)
    @pyqtSlot(str, bool, result=bool)
    def updateNoteActionItem(self, artifact_id_or_match: str, task_match_or_done: Any = True, done: bool = True) -> bool:
        if isinstance(task_match_or_done, bool):
            return self._reading_coordinator.update_note_action_item(task_match=artifact_id_or_match, done=task_match_or_done)
        return self._reading_coordinator.update_note_action_item(artifact_id=artifact_id_or_match, task_match=str(task_match_or_done), done=done)

    @pyqtSlot(int, bool, result=bool)
    @pyqtSlot(str, int, bool, result=bool)
    def updateNoteActionItemByIndex(self, artifact_id_or_index: Any, item_index_or_done: Any = True, done: bool = True) -> bool:
        if isinstance(artifact_id_or_index, int):
            return self._reading_coordinator.update_note_action_item(item_index=artifact_id_or_index, done=bool(item_index_or_done))
        return self._reading_coordinator.update_note_action_item(artifact_id=str(artifact_id_or_index), item_index=int(item_index_or_done), done=done)

    @pyqtSlot(str, str, str, str, result=bool)
    @pyqtSlot(str, str, str, result=bool)
    @pyqtSlot(str, str, result=bool)
    def expandNoteSection(self, section_or_art: str, heading_or_content: str, query_or_art: str = "", content: str = "") -> bool:
        if content:
            return self._reading_coordinator.expand_note_section(section_heading=heading_or_content, expansion_content=content, expansion_query=query_or_art, artifact_id=section_or_art)
        return self._reading_coordinator.expand_note_section(section_heading=section_or_art, expansion_content=heading_or_content, expansion_query=query_or_art)

    @pyqtSlot(str, str, result=str)
    @pyqtSlot(str, result=str)
    def findFileOrApp(self, query: str, resource_kind: str = "any") -> str:
        """Dispatches find_file_or_app through ActionDispatcher, returning artifact_id."""
        if not self._runtime or not self._runtime.dispatcher:
            return ""
        try:
            from rat.crawler.db import Database
            active_db = Database(self._db_path) if self._db_path else None
            res = self._runtime.dispatcher.execute_operation(
                "find_file_or_app",
                {"query": query, "resource_kind": resource_kind},
                context={
                    "db": active_db,
                    "catalog": self._finder_catalog,
                    "platform": sys.platform,
                },
            )
            if res.status != "success" or not res.artifact:
                return ""
            art = res.artifact
            hits = art.payload.get("hits", [])
            self._finder_hits = hits
            self._finder_query = query
            self._view = "finder"
            self._status = f"Tìm thấy {len(hits)} gợi ý cho '{query}'"
            self.snapshotChanged.emit()
            return art.id
        except Exception as exc:
            logger.warning("findFileOrApp dispatch failed: %s", exc)
            return ""

    @pyqtSlot(str)
    def openPdfHit(self, path: str):
        self.openPdfDocument(path)

    @pyqtSlot(str, str, result=bool)
    def askAboutHit(self, path: str, query: str = "") -> bool:
        p = Path(path)
        if not p.exists():
            self._show_error("file_not_found")
            return False
        if p.suffix.lower() == ".pdf":
            q = query.strip()
            if not q:
                self.selectFile(str(p))
                return True
            if self._request:
                self._request.cancelled.set()
                self._request = None
            try:
                service = self._get_execution_service()
                self._selection = service.execute_subplan("pdf_select", {"path": p})
            except SelectedPDFError as exc:
                self._show_error(exc.code)
                return False
            self._search = self._page = None
            return self.submit(q, origin="ui_action")
        else:
            try:
                content = p.read_text(encoding="utf-8", errors="replace")[:4000]
            except Exception:
                content = ""
            q = query.strip() or f"Tóm tắt nội dung tệp {p.name}"
            self._assistant_sources.append({
                "path": str(p),
                "name": p.name,
                "content": content,
            })
            return self.submit(q)

    @pyqtSlot(int, result=bool)
    def openSelectedHit(self, index: int) -> bool:
        if 0 <= index < len(self._finder_hits):
            hit = self._finder_hits[index]
            if hit.get("is_pdf"):
                self.openPdfHit(hit["path"])
                return True
            else:
                return self.openHit(hit["path"])
        return False

    @pyqtSlot(int, str, result=bool)
    @pyqtSlot(int, result=bool)
    def adoptSelectedHit(self, index: int, query: str = "") -> bool:
        """Adopt the selected hit into the active document desk, auto-analyzing draft question if provided."""
        if 0 <= index < len(self._finder_hits):
            hit = self._finder_hits[index]
            path = hit.get("path")
            p = Path(path) if path else None
            if not p or not p.exists():
                self._show_error("file_not_found")
                return False

            is_pdf = bool(hit.get("is_pdf") or str(path).lower().endswith(".pdf"))
            clean_q = (query or "").strip()

            # If user has an active drafted question, automatically begin agentic analysis
            if clean_q:
                plan = parse_finder_intent(clean_q)
                clean_terms = plan.query_terms.strip() if plan.query_terms else clean_q
                if not clean_terms:
                    clean_terms = f"Tóm tắt các điểm chính trong tài liệu {p.name}"

                if is_pdf:
                    try:
                        service = self._get_execution_service()
                        self._selection = service.execute_subplan("pdf_select", {"path": p})
                    except SelectedPDFError as exc:
                        self._show_error(exc.code)
                        return False
                    self._auto_read_on_select = False
                    self._page = None
                    self._search = None
                else:
                    try:
                        content = p.read_text(encoding="utf-8", errors="replace")[:4000]
                    except Exception:
                        content = ""
                    self._assistant_sources.append({
                        "path": str(p),
                        "name": p.name,
                        "content": content,
                    })

                self._finder_hits = []
                self._finder_query = ""
                if self._finder_coordinator is not None:
                    self._finder_coordinator.cancel()
                self._expanded = True
                self._status = f"Chuột đang đọc {p.name} và phân tích câu hỏi…"
                self.changed.emit()
                return self.submit(clean_terms, origin="ui_action")
            else:
                self.selectFile(str(p), auto_read=is_pdf)
                self._finder_hits = []
                self._finder_query = ""
                self._status = f"Đã chọn tài liệu: {p.name}"
                self.changed.emit()
                return True
        return False

    @pyqtSlot(int, str, result=bool)
    def askAboutSelectedHit(self, index: int, query: str = "") -> bool:
        if 0 <= index < len(self._finder_hits):
            hit = self._finder_hits[index]
            return self.askAboutHit(hit["path"], query)
        return False

    @pyqtSlot(str, result=bool)
    def revealInFinder(self, path: str) -> bool:
        if not path:
            return False
        p = Path(path).resolve()
        if not p.exists():
            self._show_error("file_not_found")
            return False
        if self._reveal_file is not None:
            return bool(self._reveal_file(str(p)))
        if sys.platform == "darwin":
            try:
                subprocess.Popen(["open", "-R", str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except Exception:
                return False
        return False

    @pyqtSlot(int, result=bool)
    def revealSelectedInFinder(self, index: int) -> bool:
        if 0 <= index < len(self._finder_hits):
            return self.revealInFinder(self._finder_hits[index]["path"])
        return False

    @pyqtSlot(str, result=bool)
    def previewHit(self, path: str) -> bool:
        if not path:
            return False
        p = Path(path).resolve()
        if not p.exists():
            self._show_error("file_not_found")
            return False
        if self._preview_file is not None:
            return bool(self._preview_file(str(p)))
        if sys.platform == "darwin":
            try:
                subprocess.Popen(["qlmanage", "-p", str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except Exception:
                return False
        return False

    @pyqtSlot(int, result=bool)
    def previewSelectedHit(self, index: int) -> bool:
        if 0 <= index < len(self._finder_hits):
            return self.previewHit(self._finder_hits[index]["path"])
        return False

    @pyqtSlot(result=bool)
    def close(self):
        self._closed = True
        if self._request:
            self._request.cancelled.set()
            self._request = None
        if self._current_worker:
            if hasattr(self._current_worker, "requestInterruption"):
                self._current_worker.requestInterruption()
            if self._current_execution_id:
                try:
                    self.assistant_runtime.cancel_execution(self._current_execution_id)
                except Exception:
                    pass
            if self._current_turn_id:
                try:
                    self.conversation.cancel_turn(self._current_turn_id, execution_id=self._current_execution_id)
                except Exception:
                    pass
            self._current_worker = None
        for worker in self._execution_workers:
            worker.requestInterruption()
        if self._finder_coordinator:
            self._finder_coordinator.close(timeout=0.25)
            self._finder_coordinator = None
        if self._finder_search:
            try:
                self._finder_search.close_connection()
            except Exception:
                pass
            self._finder_search = None
        self._snapshot_renderer.close()
        pdf_closed = self._worker.close() if self._worker else True
        return pdf_closed and all(not worker.isRunning() for worker in self._execution_workers)
