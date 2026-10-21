"""
rat.ui.omnibar — Unified Casual Surface (Omnibar).
One Surface, Zero Modes.
Collapses Spotlight search, recent files, live academic agenda, full timetable,
campus room guidance, and instant calculations into a single macOS-native HUD.
"""

from __future__ import annotations

from pathlib import Path

import logging
import os
import re
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QParallelAnimationGroup,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QThread,
    QTimer,
    pyqtProperty,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QGuiApplication,
    QKeyEvent,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QTextCursor,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from rat.ui.surface_layout import ChatComposer, CurrentPageStack, motion_enabled
from rat.ui.experience import debug_ui_enabled
from rat.ui.live_companion import LiveCompanion
from rat.ui.workbench import (
    WorkbenchCanvas,
    WorkbenchDialogueRegion,
    WorkbenchThoughtTrail,
    WorkbenchTokens,
    is_expand_command,
    is_collapse_command,
    is_stop_command,
)
from rat.ui.workbench_scene import (
    SceneResultNode,
    WorkbenchScene,
    sanitize_public_text,
    workbench_scene_enabled,
    workbench_finder_enabled,
)
from rat.engine.app_resolver import ApplicationCatalog
from rat.engine.progressive_search import (
    ProgressiveSearch,
    SearchCoordinator,
    SearchFilters,
    SearchHit,
    SearchSnapshot,
)

from rat.config import config
from rat.crawler.db import Database
from rat.engine.hybrid_search import SearchEngine
from rat.engine.reranker import SearchResultItem, sort_search_results
from rat.ui.feedback import SearchFeedback
from rat.timetable.compositor import TimetableCompositor, availability_to_color, degree_to_style
from rat.timetable.data import load_club_members
from rat.timetable.model import (
    DAYS,
    SHIFTS,
    ClassSession,
    MemberSchedule,
    resolve_room_location,
)
from rat.ui.action_menu import ActionMenuDialog
from rat.ui.apple_item_delegate import AppleSpotlightDelegate
from rat.ui.preview_panel import (
    PreviewPanel,
    close_quicklook,
    open_file_default,
    open_in_terminal,
    reveal_in_finder,
    trigger_quicklook,
)
from rat.ui.chat_stream import ChatStreamWidget, get_mascot_pixmap
from rat.ui.compact_cot import CompactCoTBar
from rat.ui.compact_results import CompactFileRow, ElidedLabel
from rat.ui.chat_session import (
    CHAT_SYSTEM_PROMPT,
    ConversationHistory,
    build_chat_prompt,
)
from rat.ui.settings_dialog import SettingsDialog
from rat.ui.theme import RAYCAST_QSS, get_ext_badge_info

logger = logging.getLogger("rat.ui.omnibar")


def lower_overlay_geometry(available: QRect, width: int, height: int) -> QRect:
    """Compact summon sits low; expanded reading grows upward from the same bottom, safely uncropped."""
    width = min(width, max(300, available.width() - 24))
    height = min(height, max(180, available.height() - 32))
    # Margin from bottom of screen, guaranteed positive and reasonable on all aspect ratios
    margin = max(12, min(36, round(available.height() * 0.06)))
    target_x = available.x() + max(0, (available.width() - width) // 2)
    target_y = available.y() + available.height() - margin - height
    # Ensure window is never pushed off the top or bottom of the screen
    target_y = max(available.y() + 8, min(target_y, available.y() + available.height() - height - 8))
    return QRect(target_x, target_y, width, height)


def configure_macos_fullscreen_overlay(widget: QWidget) -> None:
    """
    Ensure the overlay window floats on top of all macOS Spaces
    including native full-screen apps (VS Code, Chrome, etc.).
    """
    try:
        import sys
        if sys.platform != "darwin":
            return
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app and app.platformName() == "offscreen":
            return
        import objc
        from ctypes import c_void_p
        from AppKit import (
            NSApplication,
            NSApplicationActivationPolicyAccessory,
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
            NSWindowCollectionBehaviorIgnoresCycle,
            NSWindowCollectionBehaviorTransient,
            NSPopUpMenuWindowLevel,
        )

        ns_app = NSApplication.sharedApplication()
        ns_app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

        ns_view = objc.objc_object(c_void_p=int(widget.winId()))
        ns_window = ns_view.window() if hasattr(ns_view, "window") else None
        if ns_window:
            behavior = (
                NSWindowCollectionBehaviorCanJoinAllSpaces
                | NSWindowCollectionBehaviorFullScreenAuxiliary
                | NSWindowCollectionBehaviorIgnoresCycle
                | NSWindowCollectionBehaviorTransient
            )
            ns_window.setCollectionBehavior_(behavior)
            ns_window.setLevel_(NSPopUpMenuWindowLevel)
            ns_window.orderFrontRegardless()
    except Exception as e:
        logger.debug(f"macOS fullscreen overlay config error: {e}")


SECTION_TABS = [
    ("home", "Trò chuyện", "Hỏi đáp & lịch hôm nay"),
    ("files", "Tệp tin", "Tìm kiếm tệp & nội dung"),
    ("schedule", "Lịch học", "Thời khóa biểu sinh viên"),
    ("club", "CLB", "Khung giờ rảnh nhóm"),
    ("settings", "Cài đặt", "Quản lý thư mục & hệ thống"),
]

FILTER_CATEGORIES = [
    ("all", "Tất cả", []),
    ("docs", "Văn bản", [".docx", ".doc", ".pdf", ".txt", ".md"]),
    ("sheets", "Bảng tính", [".xlsx", ".xls", ".csv"]),
    ("slides", "Slide", [".pptx", ".ppt"]),
    ("code", "Code", [".py", ".js", ".ts", ".html", ".css", ".json", ".sh", ".sql"]),
    ("images", "Hình ảnh", [".png", ".jpg", ".jpeg", ".webp"]),
]


class SearchWorker(QObject):
    """Long-lived background search worker for Omnibar."""
    search_completed = pyqtSignal(int, dict)

    def __init__(self, engine: SearchEngine) -> None:
        super().__init__()
        self.engine = engine
        self._latest_id = 0
        self._lock = threading.Lock()
        try:
            self.engine.embedder.embed_query("warmup")
            self.engine.vector_cache.preload()
        except Exception as e:
            logger.warning(f"SearchWorker warmup error: {e}")

    @pyqtSlot(int, str, list)
    def do_search(self, request_id: int, query: str, extensions: list) -> None:
        with self._lock:
            if request_id < self._latest_id:
                return
            self._latest_id = request_id

        try:
            response = self.engine.search(
                query,
                limit=30,
                use_hyde=False,
                use_vector=True,
            )
            with self._lock:
                if request_id < self._latest_id:
                    return

            if extensions:
                filtered = [r for r in response.get("results", []) if r.file_ext.lower() in extensions]
                response["results"] = filtered

            self.search_completed.emit(request_id, response)
        except Exception as e:
            logger.error(f"SearchWorker error: {e}")
            self.search_completed.emit(
                request_id,
                {"query": query, "results": [], "latency_ms": 0, "parsed_context": {}, "error": True},
            )


class StreamReasoningWorker(QThread):
    """Background worker for streaming real-time LLM inference without freezing UI."""
    token_received = pyqtSignal(str)
    reasoning_finished = pyqtSignal(str, list, float, str, str)  # (ans, steps, lat_ms, strategy, badge)

    def __init__(self, query: str, history: Optional[List[Dict[str, str]]] = None) -> None:
        super().__init__(QApplication.instance())
        self.query = query
        self.history = [dict(message) for message in (history or [])]

    def run(self) -> None:
        t0 = time.time()
        from rat.engine.slm import slm_engine

        if self.isInterruptionRequested():
            return
        # Try live token streaming if Ollama is available
        if slm_engine.is_service_running():
            full_tokens = []
            completed = False
            try:
                for token, done in slm_engine.generate_stream(
                    prompt=build_chat_prompt(self.query, self.history),
                    system_prompt=CHAT_SYSTEM_PROMPT,
                ):
                    if self.isInterruptionRequested():
                        return
                    if token:
                        full_tokens.append(token)
                        self.token_received.emit(token)
                    if done:
                        completed = True
                        break

                if full_tokens and "".join(full_tokens).strip():
                    lat = (time.time() - t0) * 1000.0
                    ans_text = "".join(full_tokens).strip()
                    if not completed:
                        self.reasoning_finished.emit(
                            ans_text + "\n\n[Phản hồi bị ngắt. Kiểm tra kết nối AI rồi thử lại.]",
                            [], lat, "Phản hồi bị ngắt", slm_engine.model,
                        )
                        return
                    steps = [
                        f"Yêu cầu hiện tại: '{self.query}'",
                        f"Ngữ cảnh: {len(self.history) // 2} lượt trao đổi trước.",
                        f"Mô hình cục bộ: {slm_engine.model}.",
                    ]
                    self.reasoning_finished.emit(ans_text, steps, lat, "AI cục bộ", slm_engine.model)
                    return
            except Exception as e:
                logger.debug(f"Chat streaming error: {e}")

        if not self.isInterruptionRequested():
            # A canned/demo controller cannot answer a real, contextual conversation.
            self.reasoning_finished.emit(
                "AI cục bộ chưa trả lời được. Kiểm tra Ollama và mô hình trong Cài đặt, rồi thử lại. "
                "Phép tính, tìm tệp và lịch học vẫn dùng được.",
                [], (time.time() - t0) * 1000.0, "AI chưa sẵn sàng", "Chưa kết nối",
            )


class OmnibarModeFilter(QObject):
    """Keep the mode shortcut available in every editor belonging to this box."""
    def __init__(self, window):
        super().__init__(window)
        self.window = window

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.ShortcutOverride) and isinstance(
            watched, QWidget) and watched.window() is self.window:
            if event.key() == Qt.Key.Key_Escape and self.window._pending_chat_query is not None:
                if event.type() == QEvent.Type.KeyPress:
                    self.window._cancel_assistant()
                event.accept()
                return True
            if event.key() == Qt.Key.Key_L and event.modifiers() & (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                if event.type() == QEvent.Type.KeyPress:
                    self.window.toggle_expand()
                event.accept()
                return True
        return False


class OmnibarInputFilter(QObject):
    """Keyboard-first event filter for Omnibar input."""

    def __init__(self, window: "OmnibarWindow") -> None:
        super().__init__(window)
        self.window = window

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            key_event: QKeyEvent = event
            key = key_event.key()
            mod = key_event.modifiers()
            is_cmd = bool(mod & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))

            # Preserve native text-editing shortcuts in the dedicated chat composer.
            if watched is getattr(self.window, "chat_composer_input", None) and is_cmd and key in (
                Qt.Key.Key_A, Qt.Key.Key_C, Qt.Key.Key_V, Qt.Key.Key_X, Qt.Key.Key_Z,
            ):
                return super().eventFilter(watched, event)

            if watched is getattr(self.window, "chat_composer_input", None):
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and mod & Qt.KeyboardModifier.ShiftModifier:
                    return False
                if getattr(self.window.chat_composer_input, "is_composing", lambda: False)():
                    return False

                # When cursor cannot move down further, Down key drops focus to finder suggestions, compact list, or chips
                if key == Qt.Key.Key_Down and not is_cmd:
                    cursor = self.window.chat_composer_input.textCursor()
                    test_cursor = QTextCursor(cursor)
                    can_move_down = test_cursor.movePosition(QTextCursor.MoveOperation.Down)
                    if not can_move_down:
                        scene = getattr(self.window, "workbench_scene", None)
                        finder_box = getattr(scene, "finder_box", None) if scene else None
                        if (
                            getattr(self.window, "workbench_finder_enabled", False)
                            and finder_box is not None
                            and finder_box.isVisible()
                            and getattr(finder_box, "_row_order", [])
                        ):
                            finder_box.setFocus()
                            if not finder_box.selected_resource_id:
                                finder_box.navigate(1)
                            self.window._finder_selected_id = finder_box.selected_resource_id
                            return True
                        results = getattr(self.window, "compact_file_list", None)
                        if results is not None and results.isVisible() and results.count():
                            results.setFocus()
                            if results.currentRow() < 0:
                                results.setCurrentRow(0)
                            return True
                        chips = getattr(self.window, "chip_buttons", [])
                        if getattr(self.window, "quick_suggestions", None) and self.window.quick_suggestions.isVisible() and chips:
                            chips[0].setFocus()
                            return True
                    return False

                # Tab navigation from composer to suggestions
                if key == Qt.Key.Key_Tab and not (mod & Qt.KeyboardModifier.ShiftModifier):
                    scene = getattr(self.window, "workbench_scene", None)
                    finder_box = getattr(scene, "finder_box", None) if scene else None
                    if (
                        getattr(self.window, "workbench_finder_enabled", False)
                        and finder_box is not None
                        and finder_box.isVisible()
                        and getattr(finder_box, "_row_order", [])
                    ):
                        finder_box.setFocus()
                        if not finder_box.selected_resource_id:
                            finder_box.navigate(1)
                        self.window._finder_selected_id = finder_box.selected_resource_id
                        return True
                    results = getattr(self.window, "compact_file_list", None)
                    if results is not None and results.isVisible() and results.count():
                        results.setFocus()
                        if results.currentRow() < 0:
                            results.setCurrentRow(0)
                        return True
                    chips = getattr(self.window, "chip_buttons", [])
                    if getattr(self.window, "quick_suggestions", None) and self.window.quick_suggestions.isVisible() and chips:
                        chips[0].setFocus()
                        return True
                    return False

                if key in (Qt.Key.Key_Up, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown) and not is_cmd:
                    return False
                if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                    return False

            # Chip Button Keyboard Navigation
            chips = getattr(self.window, "chip_buttons", [])
            if chips and watched in chips:
                idx = chips.index(watched)
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                    watched.click()
                    return True
                elif key in (Qt.Key.Key_Right, Qt.Key.Key_Tab):
                    chips[(idx + 1) % len(chips)].setFocus()
                    return True
                elif key in (Qt.Key.Key_Left, Qt.Key.Key_Backtab):
                    if idx > 0:
                        chips[idx - 1].setFocus()
                    else:
                        self.window.chat_composer_input.setFocus()
                    return True
                elif key == Qt.Key.Key_Up:
                    self.window.chat_composer_input.setFocus()
                    return True
                elif key == Qt.Key.Key_Escape:
                    self.window.hide()
                    return True
                elif key_event.text() and not is_cmd:
                    self.window.chat_composer_input.setFocus()
                    self.window.chat_composer_input.setText(key_event.text())
                    return True

            # Suggestions in Workbench Scene (Finder)
            scene = getattr(self.window, "workbench_scene", None)
            finder_box = getattr(scene, "finder_box", None) if scene else None
            if finder_box is not None and (watched is finder_box or finder_box.isAncestorOf(watched)):
                if key == Qt.Key.Key_Down:
                    finder_box.navigate(1)
                    self.window._finder_selected_id = finder_box.selected_resource_id
                    return True
                elif key == Qt.Key.Key_Up:
                    if not finder_box.navigate(-1):
                        self.window.chat_composer_input.setFocus()
                        cursor = self.window.chat_composer_input.textCursor()
                        cursor.movePosition(QTextCursor.MoveOperation.End)
                        self.window.chat_composer_input.setTextCursor(cursor)
                    else:
                        self.window._finder_selected_id = finder_box.selected_resource_id
                    return True
                elif is_cmd and key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    hit = finder_box.current_hit()
                    if hit and hit.kind == "file":
                        reveal_in_finder(hit.path)
                    return True
                elif isinstance(watched, QPushButton) and key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                    return False
                elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    hit = finder_box.current_hit()
                    if hit:
                        if hit.kind == "file":
                            open_file_default(hit.path)
                        else:
                            self.window.show_toast("Ứng dụng macOS (chưa hỗ trợ mở tự động trong lượt này)")
                    return True
                elif key == Qt.Key.Key_Space or (key == Qt.Key.Key_Y and is_cmd):
                    hit = finder_box.current_hit()
                    if hit and hit.kind == "file":
                        trigger_quicklook(hit.path)
                    return True
                elif key == Qt.Key.Key_Escape:
                    self.window.chat_composer_input.setFocus()
                    return True

            # 1. Navigation Up/Down
            if key == Qt.Key.Key_Down:
                self.window.navigate_active_list(1)
                active_list = self.window._active_file_list()
                if active_list and active_list.isVisible() and active_list.count():
                    active_list.setFocus()
                return True
            elif key == Qt.Key.Key_Up:
                self.window.navigate_active_list(-1)
                return True
            elif key == Qt.Key.Key_PageDown:
                self.window.navigate_active_list(5)
                return True
            elif key == Qt.Key.Key_PageUp:
                self.window.navigate_active_list(-5)
                return True

            # 2. Enter activation
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if is_cmd:
                    self.window._reveal_current_in_finder()
                elif mod & Qt.KeyboardModifier.AltModifier:
                    self.window._open_current_in_terminal()
                else:
                    if self.window.current_section_idx == 0:
                        if watched is getattr(self.window, "full_chat_input", None):
                            self.window._submit_full_chat_prompt()
                            return True
                        inp_text = self.window.chat_composer_input.text().strip()
                        if inp_text:
                            self.window._submit_chat_prompt(inp_text)
                        elif self.window.compact_file_list.isVisible() and self.window.compact_file_list.count():
                            self.window._activate_current_item()
                        elif hasattr(self.window, "speech_bubble") and self.window.speech_bubble.isVisible() and self.window.speech_bubble.has_reply:
                            self.window.speech_bubble._on_copy_clicked()
                    else:
                        self.window._activate_current_item()
                return True

            # 3. Quick Look (Space or Cmd+Y)
            if (key == Qt.Key.Key_Y and is_cmd) or (key == Qt.Key.Key_Space and self.window._is_list_focused()):
                self.window._preview_quick_look()
                return True

            # 4. Copy Path or Content / Copy Answer
            if key == Qt.Key.Key_C and is_cmd:
                if self.window.compact_file_list.isVisible() and self.window.compact_file_list.hasFocus():
                    self.window._copy_current_path()
                    return True
                if self.window.current_section_idx == 0 and not getattr(self.window.chat_composer_input, "hasSelectedText", lambda: False)():
                    if hasattr(self.window, "speech_bubble") and self.window.speech_bubble.isVisible() and self.window.speech_bubble.has_reply:
                        self.window.speech_bubble._on_copy_clicked()
                        return True
                if mod & Qt.KeyboardModifier.ShiftModifier:
                    self.window._copy_current_content()
                else:
                    self.window._copy_current_path()
                return True

            # Tab follows visible conversation controls instead of changing pages.
            if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                return False

            # 6. Cmd + 1..4 -> Direct Section Jump
            if is_cmd and Qt.Key.Key_1 <= key <= Qt.Key.Key_4:
                idx = key - Qt.Key.Key_1
                self.window.activate_chat_feature(idx)
                return True

            # 7. Cmd + K -> Action Menu
            if key == Qt.Key.Key_K and is_cmd:
                self.window._open_action_menu()
                return True

            # 7b. Cmd + N -> New Chat
            if key == Qt.Key.Key_N and is_cmd:
                self.window._reset_chat()
                return True

            # 7c. Cmd + L -> Toggle Detail Notebook
            if key == Qt.Key.Key_L and is_cmd:
                self.window.toggle_expand()
                return True

            # 8. Cmd + W -> Hide Omnibar
            if key == Qt.Key.Key_W and is_cmd:
                self.window.hide()
                return True

            # 9. Escape: If in source detail, return to overview; if expanded, collapse; else hide Omnibar
            if key == Qt.Key.Key_Escape:
                if (
                    getattr(self.window, "workbench_scene_enabled", False)
                    and hasattr(self.window, "workbench_scene")
                    and self.window.workbench_scene.mode == "source_detail"
                ):
                    self.window.workbench_scene.show_overview()
                    return True
                if getattr(self.window, "is_expanded", False):
                    self.window.set_expanded(False)
                    return True
                self.window.hide()
                return True

        return super().eventFilter(watched, event)


class OmnibarListFilter(QObject):
    """Event filter on list widgets for quick look and forward typing."""

    def __init__(self, window: "OmnibarWindow") -> None:
        super().__init__(window)
        self.window = window

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            key_event: QKeyEvent = event
            key = key_event.key()
            mod = key_event.modifiers()
            is_cmd = bool(mod & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))

            if key == Qt.Key.Key_C and is_cmd:
                self.window._copy_current_path()
                return True

            if key == Qt.Key.Key_Space:
                self.window._preview_quick_look()
                return True

            if key == Qt.Key.Key_Up:
                curr = watched.currentRow() if hasattr(watched, "currentRow") else 0
                if curr <= 0:
                    active_inp = (
                        getattr(self.window, "chat_composer_input", None)
                        if self.window.current_section_idx == 0
                        else getattr(self.window, "search_input", None)
                    )
                    if active_inp:
                        active_inp.setFocus()
                        return True

            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if is_cmd:
                    self.window._reveal_current_in_finder()
                elif mod & Qt.KeyboardModifier.AltModifier:
                    self.window._open_current_in_terminal()
                else:
                    self.window._activate_current_item()
                return True

            if key == Qt.Key.Key_Escape:
                if getattr(self.window, "is_expanded", False):
                    self.window.set_expanded(False)
                    return True
                self.window.hide()
                return True

            # Forward printable characters back to active input
            text = key_event.text()
            if text and text.isprintable() and not (is_cmd or (mod & Qt.KeyboardModifier.AltModifier)):
                active_inp = (
                    getattr(self.window, "chat_composer_input", None)
                    if self.window.current_section_idx == 0
                    else getattr(self.window, "search_input", None)
                )
                if active_inp:
                    active_inp.setFocus()
                    active_inp.setText(active_inp.text() + text)
                    active_inp.setCursorPosition(len(active_inp.text()))
                return True

        return super().eventFilter(watched, event)


class ArtisticSpeechBubble(QFrame):
    """
    Floating Overlay Speech Bubble Component (Independent Layer).
    - Whimsical comic speech bubble with organic bezier tail locked to Chuột's snout.
    - Quiet header with human status and actions only where they are useful.
    - WordWrap with smooth height adjustment.
    - Opaque warm paper, so desktop content never bleeds through a reply.
    """

    def __init__(self, window: "OmnibarWindow", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.window = window
        self.setObjectName("RatSpeechBubble")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(460)
        self.tail_y = 46
        self._bubble_height = 92
        self.setFixedHeight(92)

        self._opacity_effect: Optional[QGraphicsOpacityEffect] = None
        self._height_anim: Optional[QPropertyAnimation] = None
        self._full_reply = ""
        self._copy_text = ""
        self._expanded = False
        self._truncated = False
        self._has_details = False
        self._file_summary = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 10, 16, 10)
        layout.setSpacing(6)

        # 1. Header Meta Row (clean, no distracting buttons)
        header = QHBoxLayout()
        header.setSpacing(6)

        self.dot = QLabel("●")
        self.dot.setStyleSheet("font-size: 8px; color: #F59E0B; margin-top: 1px;")
        header.addWidget(self.dot)

        self.name_tag = QLabel("Chuột")
        self.name_tag.setStyleSheet("font-size: 11px; font-weight: 600; color: #6F6456;")
        header.addWidget(self.name_tag)

        self.context_pill = QLabel("Sẵn sàng")
        self.context_pill.setStyleSheet("font-size: 10px; font-weight: 400; color: #7C7469; padding: 1px 5px;")
        header.addWidget(self.context_pill)

        header.addStretch()
        action_style = """
            QPushButton {
                background: transparent; border: none; border-radius: 4px;
                color: #6B6258; font-size: 10px; padding: 2px 5px;
            }
            QPushButton:hover { background: #F3EFE8; color: #1F1A16; }
        """
        self.btn_copy = QPushButton("Sao chép", self)
        self.btn_copy.setStyleSheet(action_style)
        self.btn_copy.setToolTip("Sao chép toàn bộ đáp án (⌘C)")
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.clicked.connect(self._on_copy_clicked)
        self.btn_copy.hide()
        header.addWidget(self.btn_copy)
        self.btn_hist = QPushButton("Đọc hết", self)
        self.btn_hist.setStyleSheet(action_style)
        self.btn_hist.setToolTip("Mở đáp án đầy đủ (⌘L)")
        self.btn_hist.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_hist.clicked.connect(self.window.toggle_expand)
        self.btn_hist.hide()
        header.addWidget(self.btn_hist)
        layout.addLayout(header)

        # 2. Main Dialogue Text
        self.dialogue = QLabel("Nghe đây. Cần gì?", self)
        self.dialogue.setStyleSheet("font-size: 13px; font-weight: 400; color: #302B24;")
        self.dialogue.setWordWrap(True)
        self.dialogue.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.dialogue)

    @pyqtProperty(int)
    def bubbleHeight(self) -> int:
        return self.height()

    @bubbleHeight.setter
    def bubbleHeight(self, val: int) -> None:
        self.setFixedHeight(val)
        self.update()

    def update_target_height(self, animated: bool = True) -> None:
        """Calculate needed height and smoothly animate size without jitter (100ms - 150ms)."""
        fm = self.dialogue.fontMetrics()
        text = self.dialogue.text()
        rect = fm.boundingRect(QRect(0, 0, 420, 10000), Qt.TextFlag.TextWordWrap, text)
        text_h = max(20, rect.height())
        # Keep the reply inside the existing 120px mascot/bubble headroom.
        target_h = max(76, min(112, text_h + 46))

        if not animated or not self.isVisible():
            self.setFixedHeight(target_h)
            return

        if not self._height_anim:
            self._height_anim = QPropertyAnimation(self, b"bubbleHeight")
            self._height_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        if self.height() != target_h:
            self._height_anim.stop()
            self._height_anim.setDuration(120)
            self._height_anim.setStartValue(self.height())
            self._height_anim.setEndValue(target_h)
            self._height_anim.start()

    @property
    def has_reply(self) -> bool:
        return bool(self._copy_text.strip())

    def _fit_reply(self, text: str) -> str:
        """Fit a preview to the bubble, retaining the full reply separately."""
        fm = self.dialogue.fontMetrics()

        def fits(candidate: str) -> bool:
            rect = fm.boundingRect(QRect(0, 0, 420, 10000), Qt.TextFlag.TextWordWrap, candidate)
            return rect.height() <= 66 and rect.width() <= 420

        if fits(text):
            return text
        low, high = 0, len(text)
        while low < high:
            mid = (low + high + 1) // 2
            if fits(text[:mid].rstrip() + "…"):
                low = mid
            else:
                high = mid - 1
        prefix = text[:low].rstrip()
        boundary = prefix.rfind(" ")
        if boundary > len(prefix) * 0.7:
            prefix = prefix[:boundary].rstrip()
        return prefix + "…"

    def set_reply(
        self,
        text: str,
        context_text: Optional[str] = None,
        *,
        copy_text: Optional[str] = None,
        has_details: bool = False,
        file_summary: bool = False,
    ) -> None:
        self._full_reply = text.strip()
        self._copy_text = text if copy_text is None else copy_text
        self._has_details = has_details
        self._file_summary = file_summary
        # Compact previews don't spend their limited lines on paragraph spacing.
        preview_source = re.sub(r"\s*\n\s*", " ", self._full_reply)
        preview = self._fit_reply(preview_source)
        self._truncated = preview != preview_source
        self.dialogue.setText(preview)
        self.btn_copy.setVisible(self.has_reply and not file_summary)
        self.btn_hist.setVisible(self.has_reply and not file_summary and (self._truncated or self._has_details or self._expanded))
        self.btn_hist.setText("Thu gọn" if self._expanded else "Xem kết quả" if has_details else "Đọc hết")
        if context_text:
            self.context_pill.setText(context_text)
        self.update_target_height(animated=True)

    def _on_copy_clicked(self) -> None:
        if self.has_reply:
            QApplication.clipboard().setText(self._copy_text)
            self.window.show_toast("Đã sao chép toàn bộ đáp án")

    def setText(self, text: str) -> None:
        self.set_reply(text)

    def text(self) -> str:
        return self._full_reply or self.dialogue.text()

    def stream_token(self, token: str) -> None:
        self.set_reply(self._copy_text + token, "Đang gõ")

    def reset_welcome(self) -> None:
        self._full_reply = ""
        self._copy_text = ""
        self._truncated = False
        self._has_details = False
        self._file_summary = False
        self.btn_copy.hide()
        self.btn_hist.hide()
        self.dialogue.setText("Nghe đây. Cần gì?")
        self.context_pill.setText("Sẵn sàng")
        self.update_target_height(animated=False)

    def set_expanded_mode(self, is_expanded: bool) -> None:
        self._expanded = is_expanded
        self.btn_hist.setText("Thu gọn" if is_expanded else "Xem kết quả" if self._has_details else "Đọc hết")
        self.btn_hist.setVisible(self.has_reply and not self._file_summary and (self._truncated or self._has_details or is_expanded))

    def show_bubble(self) -> None:
        self.show()
        self.raise_()
        self.update_target_height(animated=False)

    def hide_bubble(self) -> None:
        self.hide()

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        if getattr(self.window, "speech_bubble", None) is self:
            self.window._position_reply_bubble()

    def paintEvent(self, e: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        tail_w = 12
        tail_h = 14
        tail_y = float(getattr(self, "tail_y", 30))

        w = self.width() - 4
        h = self.height() - 4
        r = 14

        path = QPainterPath()
        path.moveTo(2 + tail_w + r, 2)
        path.lineTo(2 + w - r, 2)
        path.quadTo(2 + w, 2, 2 + w, 2 + r)
        path.lineTo(2 + w, 2 + h - r)
        path.quadTo(2 + w, 2 + h, 2 + w - r, 2 + h)
        path.lineTo(2 + tail_w + r, 2 + h)
        path.quadTo(2 + tail_w, 2 + h, 2 + tail_w, 2 + h - r)

        # Organic smooth bezier tail pointing to Chuột
        path.lineTo(2 + tail_w, tail_y + tail_h)
        tip_x = 2.0
        tip_y = tail_y + tail_h * 0.45
        path.quadTo(2 + tail_w * 0.4, tail_y + tail_h * 0.85, tip_x, tip_y)
        path.quadTo(2 + tail_w * 0.35, tail_y + tail_h * 0.15, 2 + tail_w, tail_y)

        path.lineTo(2 + tail_w, 2 + r)
        path.quadTo(2 + tail_w, 2, 2 + tail_w + r, 2)
        path.closeSubpath()

        # One opaque paper surface, without duplicate shadow outlines or text bleed.
        painter.setBrush(QColor("#FFFDFA"))
        painter.setPen(QPen(QColor("#DDD7CD"), 1.0))
        painter.drawPath(path)


ComicSpeechFrame = ArtisticSpeechBubble


class CompanionAvatarButton(LiveCompanion):
    """Compatibility name for the shared live character."""
    pass



class PeekingRatMascot(QWidget):
    """
    Desktop Mascot Character with 'Núp hở mắt/tay & Pop-out xéo' animation.
    1. Z-INDEX & BÁM GỜ CHATBOX:
       - Layer immediately BEHIND Chatbox card (stackUnder).
       - IDLE (Núp): Tọa độ Y thụt xuống sao cho Chatbox che gần hết,
         CHỈ ĐỂ HỞ: Đôi mắt trố và 2 bàn tay đang bám trên gờ mép Chatbox.
         Góc xoay (Rotation angle): 0 degree.
    2. ANIMATION POP-OUT XÉO (DIAGONAL POP-OUT):
       - Kích hoạt SPEAKING: Animation kết hợp 3 thông số:
         Trượt trục Y (lên trên), Trượt trục X (nhích sang bên 20px),
         và Xoay nghiêng góc (Rotation: +10°).
       - Hiệu ứng nảy nhẹ (QEasingCurve.Type.OutBack, ~350ms duration) khi trượt ra.
       - Toàn thân con chuột được lộ ra trọn vẹn ở góc nghiêng này.
    3. HIỂN THỊ SPEECH BUBBLE:
       - Bong bóng thoại xuất hiện ngay sau khi con chuột hoàn thành animation ló xéo.
       - Đuôi bong bóng thoại chỉ thẳng vào đầu con chuột đang nằm ở vị trí nghiêng đó.
    """
    speaking_popped_out = pyqtSignal()
    idle_retreated = pyqtSignal()

    def __init__(self, window: "OmnibarWindow", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.window = window
        self.setObjectName("PeekingMascot")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.current_state = "idle"
        self._spin_angle = 0
        self._spin_timer = QTimer(self)
        self._spin_timer.timeout.connect(self._on_spin_tick)

        self._rotation: float = 0.0
        self.is_speaking: bool = False

        # Load full mascot cutout sprite (146x146 bust with gripping paws)
        pm = get_mascot_pixmap(146, 146, bust_only=True)
        self._mascot_pixmap = pm if (pm and not pm.isNull()) else QPixmap()

        # Expanded canvas (176x150) so rotating/peeking sprite is never cropped at margins
        self.setFixedSize(176, 150)

        # Coordinate anchors (container top rim is at y=120)
        self.x_idle = 16
        self.y_idle = 8           # paws at bottom of 146px bust rest right at y=120 on rim
        self.x_speaking = 20      # slight natural shift
        self.y_speaking = 4       # slight upward shift
        self.rot_idle = 0.0       # 0 degree khi núp
        self.rot_speaking = 0.0   # 0 degree to guarantee zero ear/paw cropping
        self.move(self.x_idle, self.y_idle)

        # Parallel animation group for smooth synchronous transform
        self._anim_group = QParallelAnimationGroup(self)

        self._pos_anim = QPropertyAnimation(self, b"pos")
        self._pos_anim.setDuration(350)

        self._rot_anim = QPropertyAnimation(self, b"rotation")
        self._rot_anim.setDuration(350)

        self._anim_group.addAnimation(self._pos_anim)
        self._anim_group.addAnimation(self._rot_anim)
        self._anim_group.finished.connect(self._on_animation_finished)

    @pyqtProperty(float)
    def rotation(self) -> float:
        return self._rotation

    @rotation.setter
    def rotation(self, val: float) -> None:
        self._rotation = val
        self.update()

    def set_anchors(self, container_x: int, container_y: int) -> None:
        """Update anchor positions relative to container geometry."""
        cx = container_x if container_x > 0 else 16
        cy = container_y if container_y > 20 else 120

        self.x_idle = cx
        self.y_idle = max(2, cy - 112)
        self.x_speaking = self.x_idle + 6
        self.y_speaking = max(2, self.y_idle - 4)
        if not self.is_speaking:
            self.move(self.x_idle, self.y_idle)
            self._rotation = self.rot_idle
        else:
            self.move(self.x_speaking, self.y_speaking)
            self._rotation = self.rot_speaking
        self.update()

    def pop_out_speaking(self) -> None:
        """Diagonal pop-out animation (~350ms, OutBack easing)."""
        self.is_speaking = True
        self._anim_group.stop()

        self._pos_anim.setDuration(350)
        self._pos_anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self._pos_anim.setStartValue(self.pos())
        self._pos_anim.setEndValue(QPoint(self.x_speaking, self.y_speaking))

        self._rot_anim.setDuration(350)
        self._rot_anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self._rot_anim.setStartValue(self._rotation)
        self._rot_anim.setEndValue(self.rot_speaking)

        self._anim_group.start()

    def retreat_to_idle(self) -> None:
        """Retreat back to hiding/idle position (eyes & paws peeking only, 0 deg)."""
        self.is_speaking = False
        self._anim_group.stop()

        self._pos_anim.setDuration(300)
        self._pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._pos_anim.setStartValue(self.pos())
        self._pos_anim.setEndValue(QPoint(self.x_idle, self.y_idle))

        self._rot_anim.setDuration(300)
        self._rot_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._rot_anim.setStartValue(self._rotation)
        self._rot_anim.setEndValue(self.rot_idle)

        self._anim_group.start()

    def _on_animation_finished(self) -> None:
        if self.is_speaking:
            self.speaking_popped_out.emit()
        else:
            self.idle_retreated.emit()

    def _on_spin_tick(self) -> None:
        self._spin_angle = (self._spin_angle + 25) % 360
        self.update()

    def set_state(self, state: str) -> None:
        self.current_state = state
        if state == "thinking":
            if not self._spin_timer.isActive():
                self._spin_timer.start(40)
        else:
            if self._spin_timer.isActive():
                self._spin_timer.stop()
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # Mascot stays stationary; disabled erratic jumping/popping out per user preference
        pass

    def paintEvent(self, event: Any) -> None:
        if self._mascot_pixmap.isNull():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        pm_w = self._mascot_pixmap.width()
        pm_h = self._mascot_pixmap.height()

        draw_x = (self.width() - pm_w) // 2
        draw_y = (self.height() - pm_h) // 2

        pivot_x = draw_x + pm_w / 2
        pivot_y = draw_y + pm_h * 0.95

        p.save()
        p.translate(pivot_x, pivot_y)
        p.rotate(self._rotation)
        p.translate(-pivot_x, -pivot_y)

        p.drawPixmap(draw_x, draw_y, self._mascot_pixmap)
        p.restore()

        # Draw expressive overhead badge if active
        st = self.current_state
        head_cx = draw_x + int(pm_w * 0.36)
        head_cy = draw_y + 16

        if st == "thinking":
            p.save()
            p.translate(head_cx + 16, head_cy - 12)
            p.rotate(self._spin_angle)
            pen = QPen(QColor("#F59E0B"), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawArc(QRectF(-8, -8, 16, 16), 0, 270 * 16)
            p.restore()
            p.setFont(QFont("Apple Color Emoji", 12))
            p.drawText(QRectF(head_cx + 26, head_cy - 22, 18, 18), Qt.AlignmentFlag.AlignCenter, "💭")
        elif st == "searching":
            p.setFont(QFont("Apple Color Emoji", 18))
            p.drawText(QRectF(head_cx + 10, head_cy - 20, 24, 24), Qt.AlignmentFlag.AlignCenter, "🔍")
        elif st == "angry":
            p.setFont(QFont("Apple Color Emoji", 18))
            p.drawText(QRectF(head_cx - 4, head_cy - 10, 22, 22), Qt.AlignmentFlag.AlignCenter, "💢")

        p.end()


class RatCompanionStage(QWidget):
    """
    Desktop Game Companion Character Stage.
    A dedicated visual stage for the mascot character standing beside the interaction console.
    Supports emotional/operational states:
    - 'idle': Sẵn sàng (Clean, no tryhard AI badge)
    - 'listening': Đang nghe
    - 'thinking': Đang suy nghĩ...
    - 'searching': Đang bới tệp...
    - 'found': Đã tìm thấy!
    - 'happy': Vui vẻ!
    - 'sleepy': Nghỉ ngơi
    """

    def __init__(self, window: "OmnibarWindow", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.window = window
        self.setObjectName("RatStage")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(150)
        self.current_state = "idle"
        self._quote_idx = 0
        self._quotes = [
            "Nghe đây. Cần gì?",
            "Đưa câu hỏi đây, mình gỡ từng ý.",
            "Có mặt. Không cần điểm danh lần nữa đâu.",
            "Ừ, tôi đang nghe. Cứ gõ đi.",
            "Nhấp đúp để mở phần trao đổi đầy đủ.",
        ]
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # Mascot Avatar (Clean crisp sprite without blurry gray shadow box)
        self.mascot_lbl = QLabel(self)
        self.mascot_lbl.setObjectName("RatAvatar")
        self.mascot_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mascot_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mascot_lbl.mousePressEvent = self._on_mascot_pressed

        layout.addWidget(self.mascot_lbl, 0, Qt.AlignmentFlag.AlignCenter)

        # Character Mood / Status Pill (Clean: Hidden by default when idle, appears only during active states)
        self.mood_pill = QLabel("", self)
        self.mood_pill.setObjectName("RatMoodPill")
        self.mood_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mood_pill.setFixedHeight(24)
        self.mood_pill.hide()
        layout.addWidget(self.mood_pill, 0, Qt.AlignmentFlag.AlignCenter)

        # Subtitle hint (kept hidden for clean aesthetic)
        self.hint_lbl = QLabel("", self)
        self.hint_lbl.hide()

        self.update_mascot_size(155)

    def update_mascot_size(self, target_h: int) -> None:
        target_w = int(target_h * (419 / 445))
        pm = get_mascot_pixmap(target_w, target_h)
        if pm and not pm.isNull():
            self.mascot_lbl.setPixmap(pm)
            self.mascot_lbl.setFixedSize(target_w, target_h)
        else:
            self.mascot_lbl.setText("🧀")
            self.mascot_lbl.setStyleSheet("font-size: 48px;")

    def set_state(self, state: str, custom_text: Optional[str] = None) -> None:
        self.current_state = state
        if state == "idle":
            self.mood_pill.hide()
            return

        state_configs = {
            "listening": ("✨ Chuột · Đang nghe", "#EFF8F2", "#1D6B3E", "#A3D9B5"),
            "thinking": ("💭 Chuột · Đang suy nghĩ...", "#EFF6FF", "#1E40AF", "#BFDBFE"),
            "searching": ("🔍 Chuột · Đang bới tệp...", "#FFF2EB", "#9A3412", "#FED7AA"),
            "found": ("📁 Chuột · Đã tìm thấy!", "#F0FDF4", "#166534", "#BBF7D0"),
            "happy": ("🎉 Chuột · Vui vẻ!", "#FFF6DD", "#7A5800", "#E5C470"),
            "sleepy": ("💤 Chuột · Nghỉ ngơi", "#F4F0EA", "#615547", "#D6CDC1"),
        }
        cfg = state_configs.get(state, ("🧀 Chuột", "#FFF6DD", "#7A5800", "#E5C470"))
        text = custom_text or cfg[0]
        bg, col, bd = cfg[1], cfg[2], cfg[3]
        self.mood_pill.setText(text)
        self.mood_pill.setStyleSheet(f"""
            QLabel#RatMoodPill {{
                background-color: {bg};
                color: {col};
                border: 1px solid {bd};
                border-radius: 12px;
                padding: 3px 12px;
                font-size: 11px;
                font-weight: 750;
            }}
        """)
        self.mood_pill.show()

    def _on_mascot_pressed(self, event: QMouseEvent) -> None:
        # Stationary mascot; no state shifts or erratic jumping on click
        pass

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.window.toggle_expand()


class _FinderSignalBridge(QObject):
    snapshot_ready = pyqtSignal(object)
    catalog_ready = pyqtSignal(object)


class OmnibarWindow(QMainWindow):
    """
    Unified Casual Surface (Omnibar).
    Brings together chat, file search, class schedules, and shared free-time windows.
    """

    search_requested = pyqtSignal(int, str, list)

    def __init__(self) -> None:
        super().__init__()
        self.debug_ui = debug_ui_enabled()
        self.workbench_scene_enabled = workbench_scene_enabled()
        self.workbench_finder_enabled = workbench_finder_enabled()
        self._finder_coordinator: Optional[SearchCoordinator] = None
        self._finder_search: Optional[ProgressiveSearch] = None
        self._finder_catalog: Optional[ApplicationCatalog] = None
        self._finder_selected_id: Optional[str] = None
        self._finder_bridge = _FinderSignalBridge(self)
        self._finder_bridge.snapshot_ready.connect(self._on_finder_snapshot_delivered)
        self._finder_bridge.catalog_ready.connect(self._on_finder_catalog_ready)
        if self.workbench_finder_enabled:
            self._init_finder_service()
        self.db = Database(config.db_path)
        self.engine = SearchEngine(self.db)
        self.compositor = TimetableCompositor(load_club_members())
        self.members: List[MemberSchedule] = self.compositor.members
        from rat.engine.assistant_runtime import AssistantRuntime
        from rat.engine.slm import SLMEngine
        self.assistant_runtime = AssistantRuntime(db=self.db, compositor=self.compositor, use_live_model=True,
            plan_tasks=False, discover_tools=True, structured_context=False,
            model_client=SLMEngine(model=config.assistant_model or config.ollama_model))
        self._assistant_sources = []
        self._assistant_task_state = {}
        self._assistant_handle = None
        self._selected_document_path = None

        self.current_section_idx = 0
        self.active_file_filter_idx = 0
        self.is_expanded = False
        self._request_counter = 0
        self._dialog_active = False
        self._is_opening = False
        self._was_activated = False
        self.current_query = ""
        self._conversation = ConversationHistory()
        self._pending_chat_query: Optional[str] = None
        self._last_assistant_query: Optional[str] = None
        self._chat_generation = 0
        self._current_reasoner: Optional[StreamReasoningWorker] = None
        self._reasoning_workers: set[StreamReasoningWorker] = set()
        self._artifact_worker = None
        self._chat_file_request: Optional[Dict[str, Any]] = None
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._restore_toast)
        self._toast_restore: Optional[tuple[str, str, str]] = None

        # Huy is default member
        self.current_member = next((m for m in self.members if "Huy" in m.name), self.members[0])

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(180)
        self.search_timer.timeout.connect(self._execute_search)

        self._drag_pos = QPoint()
        self._init_thread()
        self._surface_fit_pending = False
        self._surface_scroll = {}
        self._init_window()
        self._init_ui()
        self._mode_filter = OmnibarModeFilter(self)
        QApplication.instance().installEventFilter(self._mode_filter)
        self.feedback = SearchFeedback(self, "omnibar", [self.result_list, self.recent_list, self.compact_file_list])
        self._load_initial_data()

    def _init_thread(self) -> None:
        self.search_thread = QThread(None)
        self.worker = SearchWorker(self.engine)
        self.worker.moveToThread(self.search_thread)
        self.search_requested.connect(self.worker.do_search)
        self.worker.search_completed.connect(self._on_search_completed)
        self.search_thread.start()


    def _init_window(self) -> None:
        self.setWindowTitle("rat")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(RAYCAST_QSS)
        self._resize_overlay(652, 238)
        configure_macos_fullscreen_overlay(self)

    def minimumSizeHint(self) -> QSize:
        base = super().minimumSizeHint()
        return QSize(min(380, base.width()), min(200, base.height()))

    def _is_narrow(self, outer_width: Optional[int] = None) -> bool:
        """Apply responsive breakpoint <= 450px to usable content width consistently."""
        w = self.width() if outer_width is None else outer_width
        # Usable content width is outer width minus minimum outer margins (2 * 8px = 16px).
        # At <= 450px of content width (outer width <= 466px), narrow reflow triggers.
        return (w - 16) <= 450

    def _resize_overlay(self, new_width: int, new_height: int, animated: bool = False) -> None:
        """Keep the bottom composer anchored while the result grows upward."""
        minimum = self.minimumSizeHint()
        new_width = int(max(new_width, minimum.width()))
        new_height = int(max(new_height, minimum.height()))
        try:
            cursor_pos = QCursor.pos()
            screen = (self.screen() if self.isVisible() else QGuiApplication.screenAt(cursor_pos)) or QGuiApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                new_width = min(new_width, geo.width() - 24)
                new_height = min(new_height, geo.height() - 24)
                is_narrow = self._is_narrow(new_width)
                if hasattr(self, "workbench_dialogue") and getattr(self.workbench_dialogue, "is_narrow", False) != is_narrow:
                    self.workbench_canvas.set_presentation(self.is_expanded, narrow=is_narrow)
                    self.workbench_dialogue.set_presentation(self.is_expanded, narrow=is_narrow)
                    if hasattr(self, "thought_trail"):
                        self.thought_trail.set_presentation(self.is_expanded, narrow=is_narrow)
                    if hasattr(self, "workbench_scene"):
                        self.workbench_scene.set_presentation(self.is_expanded, narrow=is_narrow)
                if hasattr(self, "main_layout"):
                    content_w = 640 if self.is_expanded else (420 if is_narrow else 520)
                    margin_h = max(8, min(90 if self.is_expanded else 50, (new_width - content_w) // 2))
                    self.main_layout.setContentsMargins(margin_h, 12, margin_h, 12)
                    self.main_layout.activate()
                if self.isVisible():
                    left = max(geo.left() + 12, min(self.x(), geo.right() - new_width - 11))
                    anchor = getattr(self, "_anchor_bottom", None)
                    if anchor is None:
                        anchor = self.geometry().bottom()
                    bottom = min(anchor, geo.bottom() - 12)
                    top = max(geo.top() + 12, min(bottom - new_height + 1, geo.bottom() - new_height - 11))
                    target_rect = QRect(left, top, int(new_width), int(new_height))
                    self._anchor_bottom = bottom
                else:
                    target_rect = lower_overlay_geometry(geo, int(new_width), int(new_height))
                    self._anchor_bottom = target_rect.bottom()

                if hasattr(self, "_geom_anim"):
                    if self._geom_anim.state() == QPropertyAnimation.State.Running and self._geom_anim.endValue() == target_rect:
                        return
                    self._geom_anim.stop()

                if animated and self.isVisible() and motion_enabled():
                    if not hasattr(self, "_geom_anim"):
                        self._geom_anim = QPropertyAnimation(self, b"geometry")
                        self._geom_anim.setDuration(200)
                        self._geom_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                    self._geom_anim.stop()
                    self._geom_anim.setStartValue(self.geometry())
                    self._geom_anim.setEndValue(target_rect)
                    self._geom_anim.start()
                else:
                    self.setGeometry(target_rect)
                    self.resize(new_width, new_height)
                return
        except Exception:
            pass
        self.resize(new_width, new_height)

    def _recenter_window(self) -> None:
        """Position window in the lower half of the active screen."""
        self._resize_overlay(self.width(), self.height())

    def _reset_quick_chat(self) -> None:
        """Start a fresh, clean chat session on every quick mode opening."""
        self.set_expanded(False)
        if hasattr(self, "chat_composer_input"):
            self.chat_composer_input.clear()
            self.chat_composer_input.setFocus()
        self.set_mascot_idle()
        if hasattr(self, "speech_bubble"):
            self.speech_bubble.reset_welcome()

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        if hasattr(self, "chat_composer_input"):
            self.chat_composer_input.setFocus()
        self._animate_mascot_peek()

    def _animate_mascot_peek(self) -> None:
        self.mascot_peeking.hide()

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        is_narrow = self._is_narrow(self.width())
        if hasattr(self, "workbench_dialogue") and getattr(self.workbench_dialogue, "is_narrow", False) != is_narrow:
            self.workbench_canvas.set_presentation(self.is_expanded, narrow=is_narrow)
            self.workbench_dialogue.set_presentation(self.is_expanded, narrow=is_narrow)
            if hasattr(self, "thought_trail"):
                self.thought_trail.set_presentation(self.is_expanded, narrow=is_narrow)
            if hasattr(self, "workbench_scene"):
                self.workbench_scene.set_presentation(self.is_expanded, narrow=is_narrow)
            if hasattr(self, "main_layout"):
                content_w = 640 if self.is_expanded else (420 if is_narrow else 520)
                margin_h = max(8, min(90 if self.is_expanded else 50, (self.width() - content_w) // 2))
                self.main_layout.setContentsMargins(margin_h, 12, margin_h, 12)
                self.main_layout.activate()
        if hasattr(self, "speech_bubble") and hasattr(self, "container"):
            self._position_reply_bubble()
            cx = self.container.x() if self.container.x() > 0 else 16
            cy = self.container.y() if self.container.y() > 20 else 120
            if hasattr(self, "mascot_peeking"):
                self.mascot_peeking.set_anchors(cx, cy)

    def _position_reply_bubble(self) -> None:
        cx = self.container.x() if self.container.x() > 0 else 16
        cy = self.container.y() if self.container.y() > 20 else 120
        by = max(4, cy - self.speech_bubble.height() - 14)
        self.speech_bubble.move(cx + 160, by)
        # Keep the tail near the rat's face while the bubble grows upward.
        self.speech_bubble.tail_y = max(20, min(self.speech_bubble.height() - 28, cy - 44 - by))
        self.speech_bubble.raise_()
        self.speech_bubble.update()

    def set_mascot_speaking(self, text=None):
        if text:
            self.speech_bubble.set_reply(text)
        self.speech_bubble.hide()
        self.mascot_peeking.hide()

    def _on_mascot_speaking_popped_out(self):
        self.speech_bubble.hide()

    def set_mascot_idle(self):
        self.speech_bubble.hide()
        self.mascot_peeking.hide()
        if hasattr(self, "thought_trail"):
            self.thought_trail.set_state("idle")

    def _on_mascot_idle_retreated(self) -> None:
        pass

    def on_mascot_clicked(self) -> None:
        """Forward legacy mascot clicks to the visible live companion."""
        self.companion_avatar_btn.click()

    def set_mascot_state(self, state: str, text: Optional[str] = None) -> None:
        """Unified state setter for Chuột across all UI widgets."""
        self._mascot_state = state
        if hasattr(self, "companion_avatar_btn"):
            self.companion_avatar_btn.set_state(state)
        if hasattr(self, "thought_trail"):
            self.thought_trail.set_state(state)
        if hasattr(self, "mascot_peeking"):
            self.mascot_peeking.set_state(state)
        if hasattr(self, "rat_stage") and self.rat_stage:
            self.rat_stage.set_state(state, text)
        if text:
            if not self.is_expanded:
                self.set_mascot_speaking(text)
            elif hasattr(self, "footer_status"):
                self.footer_status.setText(f"Chuột · {text}")

    def toggle_expand(self) -> None:
        """Toggle between compact HUD overlay and expanded detail notebook."""
        self.set_expanded(not self.is_expanded)

    def set_expanded(self, expanded: bool) -> None:
        """Resize the same editor and result tree; never submit or rebuild a view."""
        old_mode = self.is_expanded
        focus = QApplication.focusWidget()
        if hasattr(self, 'chat_stream'):
            self._surface_scroll[old_mode] = self.chat_stream.verticalScrollBar().value()
        if not hasattr(self, '_anchor_bottom') or self._anchor_bottom is None:
            self._anchor_bottom = self.geometry().bottom()
        self.is_expanded = bool(expanded)
        started_chat = bool(
            (hasattr(self, "chat_stream") and not self.chat_stream.is_empty())
            or (
                getattr(self, "workbench_scene_enabled", False)
                and hasattr(self, "workbench_scene")
                and not self.workbench_scene.is_empty()
            )
        )
        if expanded:
            self._interaction_surface_active = True
        elif not started_chat:
            self._interaction_surface_active = False
        is_narrow = self._is_narrow(self.width())
        margin_h = 90 if expanded else (10 if is_narrow else 50)
        self.main_layout.setContentsMargins(margin_h, 12, margin_h, 12)
        if hasattr(self, "workbench_canvas"):
            self.workbench_canvas.set_presentation(self.is_expanded, narrow=is_narrow)
        if hasattr(self, "thought_trail"):
            self.thought_trail.set_presentation(self.is_expanded, narrow=is_narrow)
        if hasattr(self, "workbench_dialogue"):
            self.workbench_dialogue.set_presentation(self.is_expanded, narrow=is_narrow)
        if hasattr(self, "workbench_scene"):
            self.workbench_scene.set_presentation(self.is_expanded, narrow=is_narrow)
        self.quick_bar.show()
        self.btn_expand.setVisible(self.debug_ui)
        self.btn_expand.setText('−' if expanded else '+')
        self.btn_expand.setAccessibleName('Thu gọn hội thoại' if expanded else 'Mở rộng hội thoại')
        self.btn_expand.setToolTip(('Thu gọn' if expanded else 'Mở rộng') + ' (⌘L)')
        for widget in (self.mascot_peeking, self.speech_bubble, self.section_bar,
                       self.hairline_divider, self.action_footer, self.compact_cot,
                       self.compact_file_list, self.compact_footer):
            if widget is not None:
                widget.hide()
        scene_started = bool(
            getattr(self, "workbench_scene_enabled", False)
            and hasattr(self, "workbench_scene")
            and not self.workbench_scene.is_empty()
        )
        self.content_stack.setVisible(
            self.is_expanded or self.current_section_idx != 0 or not self.chat_stream.is_empty() or scene_started
        )
        self.chat_stream.set_compact(not self.is_expanded)
        self._sync_compact_surface()
        self.main_layout.activate()
        if old_mode != self.is_expanded:
            self._resize_overlay(820 if expanded else (440 if is_narrow else 620), self._surface_height(), animated=True)
            self.chat_stream.restore_reading_position(self._surface_scroll.get(self.is_expanded))
        if focus is not None and self.isAncestorOf(focus) and focus.isVisible():
            focus.setFocus(Qt.FocusReason.OtherFocusReason)

    def _init_ui(self) -> None:
        self.input_filter = OmnibarInputFilter(self)

        main_widget = QWidget(self)
        main_widget.setObjectName("OmnibarCanvas")
        main_widget.setStyleSheet("QWidget#OmnibarCanvas { background: transparent; border: none; }")
        self.setCentralWidget(main_widget)
        self.main_layout = QVBoxLayout(main_widget)
        self.main_layout.setContentsMargins(50, 12, 50, 12)
        self.main_layout.setSpacing(5)

        # Hidden compatibility host for secondary background/debug panels
        compat_host = QWidget(main_widget)
        compat_host.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        compat_host.hide()

        self.speech_bubble = ArtisticSpeechBubble(self, compat_host)
        self.speech_bubble.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.speech_bubble.hide()

        # =============================================================
        # 1. WORKBENCH WORK CANVAS (Paper Card Compartment)
        # =============================================================
        self.workbench_canvas = WorkbenchCanvas(main_widget)
        self.container = self.workbench_canvas
        self.container_layout = self.workbench_canvas.canvas_layout

        # =============================================================
        # 2. CHAT COMPOSER (Persistent Single Editor)
        # =============================================================
        self.chat_composer_input = ChatComposer()
        self.chat_composer_input.setObjectName("ChatComposerInput")
        self.chat_composer_input.setPlaceholderText("Bạn muốn làm gì tiếp?")
        self.chat_composer_input.setAccessibleName("Yêu cầu cho Chuột")
        self.chat_composer_input.installEventFilter(self.input_filter)
        self.chat_composer_input.returnPressed.connect(lambda: self._submit_chat_prompt(self.chat_composer_input.text()))
        self.chat_composer_input.textChanged.connect(lambda: self._on_composer_text_changed(self.chat_composer_input.text()))
        self.chat_composer_input.height_changed.connect(self._schedule_surface_fit)

        # =============================================================
        # 3. WORKBENCH DIALOGUE REGION (RAT Stage + User Lane)
        # =============================================================
        self.workbench_dialogue = WorkbenchDialogueRegion(self.chat_composer_input, main_widget)
        self.companion_avatar_btn = self.workbench_dialogue.actor
        self.workbench_speech_bubble = self.workbench_dialogue.rat_bubble
        self.quick_bar = self.workbench_dialogue.user_lane
        self.workbench_user_lane = self.workbench_dialogue.user_lane

        # Compatibility references
        self.rat_avatar = self.workbench_dialogue.actor
        self.rat_stage = None
        self.rat_perch = None
        self.rat_speech = self.workbench_speech_bubble.dialogue
        self.rat_speech_frame = self.workbench_speech_bubble
        self.btn_close = None
        self.btn_bubble_expand = None
        self.speech_expand_hint = None
        self.rat_tail = None
        self.full_chat_input = self.chat_composer_input

        # Add compartments to window layout: Canvas above, Thought trail in middle, Dialogue below
        self.main_layout.addWidget(self.workbench_canvas)
        self.thought_trail = WorkbenchThoughtTrail(self.companion_avatar_btn, main_widget)
        self.main_layout.addWidget(self.thought_trail)
        self.main_layout.addWidget(self.workbench_dialogue)

        # Minimal model status badge
        has_slm = False
        try:
            from rat.engine.slm import slm_engine
            has_slm = slm_engine.is_service_running()
        except Exception:
            pass
        status_text = "● Qwen2.5" if has_slm else "● TDTU"
        self.chat_header_status = QLabel(status_text, self.workbench_user_lane)
        self.chat_header_status.setObjectName("QuickModelBadge")
        self.chat_header_status.hide()

        self.btn_expand = QPushButton("+", self.workbench_user_lane)
        self.btn_expand.setObjectName("BtnExpand")
        self.btn_expand.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_expand.setToolTip("Mở rộng / Thu nhỏ (⌘L)")
        self.btn_expand.clicked.connect(self.toggle_expand)
        self.btn_expand.setFixedSize(26, 26)
        self.btn_expand.setVisible(self.debug_ui)

        self.btn_surface_menu = QPushButton("⋯", self.workbench_user_lane)
        self.btn_surface_menu.setObjectName("SurfaceMenu")
        self.btn_surface_menu.setAccessibleName("Tùy chọn hội thoại")
        self.btn_surface_menu.setToolTip("Hội thoại và cài đặt")
        self.btn_surface_menu.setFixedSize(28, 28)
        menu = QMenu(self.btn_surface_menu)
        menu.addAction("Hội thoại mới", self._reset_chat)
        menu.addSeparator()
        menu.addAction("Lập lá số", self.open_natal_chart)
        menu.addAction("Tìm tài liệu…", lambda: self.activate_chat_feature(1))
        menu.addAction("Xem lịch học", lambda: self.activate_chat_feature(2))
        menu.addAction("Giờ rảnh của nhóm…", lambda: self.activate_chat_feature(3))
        menu.addSeparator()
        menu.addAction("Cài đặt…", self._open_settings)
        self.btn_surface_menu.setMenu(menu)
        self.btn_surface_menu.setVisible(self.debug_ui)

        self.return_keycap = QLabel("↵", self.workbench_user_lane)
        self.return_keycap.setObjectName("ReturnKeycap")
        self.return_keycap.setToolTip("Nhấn Enter để gửi")
        self.return_keycap.hide()

        self.chat_composer_send = QPushButton("↑", self.workbench_user_lane)
        self.chat_composer_send.setObjectName("ChatComposerSend")
        self.chat_composer_send.setFixedSize(28, 28)
        self.chat_composer_send.setToolTip("Gửi câu hỏi (Enter)")
        self.chat_composer_send.setAccessibleName("Gửi câu hỏi")
        self.chat_composer_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chat_composer_send.setEnabled(False)
        self.chat_composer_send.clicked.connect(self._submit_chat_or_stop)
        self.chat_composer_send.setVisible(self.debug_ui)
        self.full_chat_send = self.chat_composer_send


        self.mascot_peeking = PeekingRatMascot(self, compat_host)
        self.mascot_peeking.hide()
        self.mascot_peeking.speaking_popped_out.connect(self._on_mascot_speaking_popped_out)
        self.mascot_peeking.idle_retreated.connect(self._on_mascot_idle_retreated)

        from rat.ui.work_context import NotebookPane
        self.notebook_pane = NotebookPane(self.assistant_runtime.notebook, compat_host)
        self.notebook_pane.changed.connect(self._schedule_surface_fit)
        self.notebook_pane.error.connect(self.show_toast)
        self.notebook_pane.changed_notes.connect(self._on_notes_changed)

        self.surface_notice = QLabel('', compat_host)
        self.surface_notice.hide()

        self.compact_cot = CompactCoTBar(compat_host)
        self.compact_cot.heightChanged.connect(self._sync_compact_surface)
        self.compact_cot.hide()

        self.hairline_divider = QFrame(compat_host)
        self.hairline_divider.hide()

        self.quick_suggestions = QWidget(compat_host)
        self.quick_suggestions.hide()
        qs_layout = QHBoxLayout(self.quick_suggestions)
        qs_layout.setContentsMargins(2, 0, 2, 0)
        qs_layout.setSpacing(6)
        sugg_chips = [
            ("Gỡ một việc", "Giúp mình ", False),
            ("Tìm tài liệu", "Mình đang tìm tài liệu về ", False),
            ("Chuẩn bị buổi tới", "Buổi học tiếp theo của mình cần chuẩn bị gì?", True),
        ]
        self.chip_buttons: List[QPushButton] = []
        for label, q_text, submit in sugg_chips:
            chip_btn = QPushButton(label, self.quick_suggestions)
            chip_btn.setProperty("class", "QuickSuggestionChip")
            chip_btn.installEventFilter(self.input_filter)
            chip_btn.clicked.connect(
                lambda checked=False, q=q_text, send=submit: self._submit_chat_prompt(q) if send else self._prefill_chat(q)
            )
            qs_layout.addWidget(chip_btn)
            self.chip_buttons.append(chip_btn)

        self.compact_file_list = QListWidget(compat_host)
        self.compact_file_list.setObjectName("CompactFileResults")
        self.compact_file_list.hide()

        self.compact_footer = QWidget(compat_host)
        self.compact_footer.hide()
        compact_footer_layout = QHBoxLayout(self.compact_footer)
        self.keycaps_box = QWidget(self.compact_footer)
        self.keycaps_layout = QHBoxLayout(self.keycaps_box)
        compact_footer_layout.addWidget(self.keycaps_box, 1)
        self.compact_hint = ElidedLabel("")
        self.compact_hint.hide()
        self.compact_new_chat = QPushButton("Chat mới", self.compact_footer)
        self.compact_new_chat.clicked.connect(self._reset_chat)
        compact_footer_layout.addWidget(self.compact_new_chat)

        self.section_bar = QFrame(compat_host)
        self.section_bar.hide()
        section_layout = QHBoxLayout(self.section_bar)
        self.section_buttons: List[QPushButton] = []
        for idx, (sec_id, label, tooltip) in enumerate(SECTION_TABS):
            btn = QPushButton(label, self.section_bar)
            btn.clicked.connect(lambda checked, i=idx: self.switch_section(i))
            section_layout.addWidget(btn)
            self.section_buttons.append(btn)
        section_layout.addStretch()
        self.btn_natal = QPushButton("✧ Lá số", self.section_bar)
        self.btn_natal.clicked.connect(lambda checked=False: self.open_natal_chart())
        section_layout.addWidget(self.btn_natal)
        self.full_model_badge = QLabel("● " + (self.assistant_runtime.model_client.model if self.assistant_runtime.model_client else config.ollama_model), self.section_bar)
        section_layout.addWidget(self.full_model_badge)
        self.btn_full_collapse = QPushButton("⤡", self.section_bar)
        self.btn_full_collapse.clicked.connect(lambda: self.set_expanded(False))
        section_layout.addWidget(self.btn_full_collapse)

        # Content stack embedded inside workbench_canvas content container
        self.content_stack = CurrentPageStack(self.workbench_canvas.content_container)
        self.content_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.content_stack.setStyleSheet("background: transparent;")
        self.home_view = self._create_home_view()
        self.content_stack.addWidget(self.home_view)
        self.files_view = self._create_files_view()
        self.content_stack.addWidget(self.files_view)
        self.schedule_view = self._create_schedule_view()
        self.content_stack.addWidget(self.schedule_view)
        self.club_view = self._create_club_view()
        self.content_stack.addWidget(self.club_view)
        self.settings_view = self._create_settings_view()
        self.content_stack.addWidget(self.settings_view)
        self.content_stack.hide()
        self.workbench_canvas.set_embedded_stack(self.content_stack)

        footer = QFrame(compat_host)
        footer.setObjectName("ActionFooter")
        footer_layout = QHBoxLayout(footer)
        self.footer_status = QLabel("Sẵn sàng", footer)
        footer_layout.addWidget(self.footer_status)
        footer_layout.addStretch()
        self.action_footer_keycaps_box = QWidget(footer)
        self.action_footer_keycaps_layout = QHBoxLayout(self.action_footer_keycaps_box)
        footer_layout.addWidget(self.action_footer_keycaps_box)
        self.footer_hotkey_widgets = []
        self.action_footer = footer
        self.action_footer.hide()

        self.btn_new_chat = QPushButton("⌘N", compat_host)
        self.btn_new_chat.clicked.connect(self._reset_chat)
        self.btn_new_chat.hide()
        self.btn_settings = QPushButton("⚙", compat_host)
        self.btn_settings.clicked.connect(self._open_settings)
        self.btn_settings.hide()

    def _compact_height(self) -> int:
        return self._surface_height()

    def _surface_height(self):
        screen = self.screen() or QGuiApplication.primaryScreen()
        available = screen.availableGeometry().height() if screen else 900
        if self.is_expanded:
            anchor = getattr(self, "_anchor_bottom", None)
            if anchor is None and self.isVisible():
                anchor = self.geometry().bottom()
            room = anchor - screen.availableGeometry().top() - 12 if screen and self.isVisible() and anchor else available - 72
            return min(760, max(300, room))

        margin_top = self.main_layout.contentsMargins().top() if hasattr(self, "main_layout") else 12
        margin_bottom = self.main_layout.contentsMargins().bottom() if hasattr(self, "main_layout") else 12
        spacing = self.main_layout.spacing() if hasattr(self, "main_layout") else 8
        window_chrome = margin_top + margin_bottom + spacing

        dialogue_h = 120
        if hasattr(self, "workbench_dialogue"):
            self.workbench_dialogue.layout().activate()
            dialogue_h = max(120, self.workbench_dialogue.sizeHint().height())

        canvas_chrome = 78
        if hasattr(self, "workbench_canvas"):
            canvas_chrome = self.workbench_canvas.chrome_height()

        content_h = 0
        if hasattr(self, "content_stack") and self.content_stack.isVisible():
            if self.current_section_idx != 0:
                cw = self.content_stack.currentWidget()
                content_h = cw.sizeHint().height() if cw else 200
            elif (
                getattr(self, "workbench_scene_enabled", False)
                and hasattr(self, "workbench_scene")
                and not self.workbench_scene.is_empty()
            ):
                content_h = self.workbench_scene.preferred_height(int(available * 0.55))
            elif hasattr(self, "chat_stream") and not self.chat_stream.is_empty():
                self.chat_stream.container.layout().activate()
                layout = self.chat_stream.container.layout()
                viewport_w = self.chat_stream.viewport().width() or 480
                content_h = layout.totalHeightForWidth(viewport_w)
                if content_h < 0:
                    content_h = layout.sizeHint().height()
                # Ensure a usable viewport for results (e.g. at least 56px for a file card)
                content_h = max(56, min(content_h, min(260, int(available * 0.55))))

        trail_h = 0
        if hasattr(self, "thought_trail") and self.thought_trail.isVisible():
            trail_h = self.thought_trail.sizeHint().height()

        total = window_chrome + dialogue_h + canvas_chrome + content_h + trail_h
        return int(min(max(236, total), max(236, available * 0.75)))

    def _schedule_surface_fit(self):
        if getattr(self, '_surface_fit_pending', False):
            return
        self._surface_fit_pending = True
        QTimer.singleShot(0, self._fit_surface)

    def _fit_surface(self):
        self._surface_fit_pending = False
        if not hasattr(self, 'chat_stream') or getattr(self, '_shutting_down', False):
            return
        target = int(self._surface_height())
        target_w = 820 if self.is_expanded else (min(self.width(), 440) if self._is_narrow() else 620)
        if abs(target - self.height()) > 3:
            self._resize_overlay(target_w, target, animated=True)

    def activate_chat_feature(self, index):
        self.current_section_idx = 0
        self.content_stack.setCurrentIndex(0)
        self._show_interaction_surface()
        if index == 1:
            self._prefill_chat('Tìm tài liệu về ')
        elif index == 2:
            self._submit_chat_prompt('Hôm nay tôi học gì?')
        elif index == 3:
            self._prefill_chat('Tìm khung giờ rảnh cho nhóm ')
        elif index == 4:
            self._open_settings()
        else:
            self.chat_composer_input.setFocus()

    def _render_footer_keycaps(self, shortcuts: List[Tuple[str, str]]) -> None:
        if not hasattr(self, "keycaps_layout"):
            return
        while self.keycaps_layout.count():
            item = self.keycaps_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        for idx, (key, desc) in enumerate(shortcuts):
            if idx > 0:
                dot = QLabel("•")
                dot.setStyleSheet("color: #BDB09E; font-size: 8px; margin: 0 1px;")
                self.keycaps_layout.addWidget(dot)

            badge = QLabel(key)
            badge.setProperty("class", "HotkeyBadge")
            badge.setStyleSheet("""
                background-color: #FFFFFF;
                color: #4B4136;
                border: 1px solid #DCD4C4;
                border-bottom: 2px solid #B8AB98;
                border-radius: 4px;
                padding: 1px 5px;
                font-size: 10px;
                font-weight: 700;
            """)
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet("color: #786F66; font-size: 10px; font-weight: 550;")
            self.keycaps_layout.addWidget(badge)
            self.keycaps_layout.addWidget(desc_lbl)

        self.keycaps_layout.addStretch()

    def _render_action_footer_keycaps(self) -> None:
        """Render raised mechanical keycaps for action footer in expanded mode."""
        if not hasattr(self, "action_footer_keycaps_layout"):
            return
        while self.action_footer_keycaps_layout.count():
            item = self.action_footer_keycaps_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        hotkeys = [
            ("↵", "Mở"),
            ("␣", "Xem nhanh"),
            ("⇥", "Chuyển mục"),
            ("⌘K", "Tác vụ"),
            ("⎋", "Đóng"),
        ]
        if self.current_section_idx == 0:
            hotkeys = [("↵", "Gửi"), ("⇥", "Chuyển mục"), ("⎋", "Thu gọn")]
        for idx, (key, desc) in enumerate(hotkeys):
            if idx > 0:
                dot = QLabel("•")
                dot.setStyleSheet("color: #BDB09E; font-size: 8px; margin: 0 1px;")
                self.action_footer_keycaps_layout.addWidget(dot)

            badge = QLabel(key)
            badge.setProperty("class", "HotkeyBadge")
            badge.setStyleSheet("""
                background-color: #FFFFFF;
                color: #4B4136;
                border: 1px solid #DCD4C4;
                border-bottom: 2px solid #B8AB98;
                border-radius: 4px;
                padding: 1px 5px;
                font-size: 10px;
                font-weight: 700;
            """)
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet("color: #786F66; font-size: 10px; font-weight: 550;")
            self.action_footer_keycaps_layout.addWidget(badge)
            self.action_footer_keycaps_layout.addWidget(desc_lbl)

    def _sync_compact_surface(self) -> None:
        """Only one live composer and one result viewport in both sizes."""
        if getattr(self, '_shutting_down', False):
            return
        busy = self._pending_chat_query is not None
        updating = self._artifact_worker is not None
        scene_started = bool(
            getattr(self, "workbench_scene_enabled", False)
            and hasattr(self, "workbench_scene")
            and not self.workbench_scene.is_empty()
        )
        started = (not self.chat_stream.is_empty()) or scene_started
        self.quick_suggestions.setVisible(self.debug_ui and not started and not busy and not updating and self.current_section_idx == 0)
        for widget in (self.speech_bubble, self.mascot_peeking, self.compact_cot,
                       self.compact_file_list, self.compact_footer, self.section_bar,
                       self.action_footer, self.hairline_divider):
            widget.hide()
        self.quick_bar.setVisible(self.current_section_idx == 0)
        stack_visible = bool(
            started
            or self.is_expanded
            or self.current_section_idx != 0
            or getattr(self, "_interaction_surface_active", False)
        )
        self.content_stack.setVisible(stack_visible)
        if hasattr(self, "workbench_canvas") and hasattr(self.workbench_canvas, "content_container"):
            self.workbench_canvas.content_container.setVisible(stack_visible)
        if hasattr(self, "thought_trail"):
            self.thought_trail.setVisible(self.current_section_idx == 0 and self.workbench_canvas.isVisible())
        selected = getattr(self, '_selected_document_path', None)
        self.chat_composer_input.setPlaceholderText(
            f'Hỏi về {Path(selected).name}…' if selected else
            'Hỏi tiếp hoặc sửa điều gì đó…' if started else 'Bạn muốn làm gì?')
        self.chat_composer_send.setText('■' if busy else '…' if updating else '↑')
        self.chat_composer_send.setToolTip('Dừng xử lý' if busy else 'Đang cập nhật kết quả' if updating else 'Gửi · Enter (Shift+Enter xuống dòng)')
        self.chat_composer_send.setAccessibleName('Dừng xử lý' if busy else 'Đang cập nhật kết quả' if updating else 'Gửi yêu cầu')
        self.chat_composer_send.setEnabled(not updating and (busy or bool(self.chat_composer_input.text().strip())))
        self.chat_composer_send.setVisible(self.debug_ui)
        self.btn_surface_menu.setVisible(self.debug_ui)
        self.btn_expand.setVisible(self.debug_ui)
        self.notebook_pane.set_busy(busy or updating)
        self.companion_avatar_btn.setVisible(self.current_section_idx == 0)
        if getattr(self, "workbench_scene_enabled", False) and hasattr(self, "workbench_scene"):
            snap = self.workbench_scene.current_snapshot
            self.companion_avatar_btn.set_prop_kind(snap.prop_kind)
            if busy or updating:
                self.companion_avatar_btn.set_state(snap.actor_state if snap.actor_state != "idle" else "thinking")
            elif self.assistant_runtime.dispatcher.state.pending_input_request or snap.phase == "waiting":
                self.companion_avatar_btn.set_state("waiting")
            elif getattr(self, "_mascot_state", "idle") == "error" or snap.phase == "error":
                self.companion_avatar_btn.set_state("error")
            else:
                self.companion_avatar_btn.set_state(snap.actor_state if started else "idle")
        else:
            if busy or updating:
                self.companion_avatar_btn.set_state('thinking')
            elif self.assistant_runtime.dispatcher.state.pending_input_request:
                self.companion_avatar_btn.set_state('waiting')
            elif getattr(self, '_mascot_state', 'idle') == 'error':
                self.companion_avatar_btn.set_state('error')
            else:
                self.companion_avatar_btn.set_state('done' if started else 'idle')
        self._schedule_surface_fit()

    def _update_work_results(self, handle, artifacts=()):
        seen = handle.setdefault('seen_result_revisions', {})
        active = self.assistant_runtime.notebook.result_ids()
        for artifact in artifacts:
            if seen.get(artifact.id) != artifact.revision:
                if artifact.id not in active:
                    active.append(artifact.id)
                seen[artifact.id] = artifact.revision
        active = [key for key in active if self.assistant_runtime.artifact_store.get(key) is not None]
        if artifacts:
            self.assistant_runtime.notebook.select_results(active)
        if self.assistant_runtime.notebook.selection_set:
            handle['artifacts'] = {key: self.assistant_runtime.artifact_store.get(key)
                for key in self.assistant_runtime.notebook.result_ids()
                if self.assistant_runtime.artifact_store.get(key) is not None}

    def _work_sources(self, sources):
        return [] if self.assistant_runtime.notebook.selection_set else sources

    def _carry_work_results(self, handle):
        previous = getattr(self, '_latest_assistant_handle', None)
        if previous is None or previous is handle:
            return
        handle['seen_result_revisions'] = dict(previous.get('seen_result_revisions', {}))
        self._update_work_results(handle)
        if self.assistant_runtime.notebook.selection_set and not handle.get('artifacts'):
            return
        if getattr(self, "workbench_scene_enabled", False) and hasattr(self, "workbench_scene"):
            return
        host = previous.pop('sources_widget', None)
        if host is not None:
            previous['c_layout'].removeWidget(host)
            handle['c_layout'].insertWidget(handle['c_layout'].indexOf(handle['work_trace']), host)
            handle['sources_widget'] = host
            self.chat_stream.set_compact(not self.is_expanded)

    def _on_notes_changed(self):
        self.companion_avatar_btn.set_state('noting')
        self._schedule_surface_fit()

    def _append_direct_trace(self, result):
        from rat.engine.assistant_runtime import AgentStep
        handle = getattr(self, '_latest_assistant_handle', None)
        if handle is None:
            return
        events = self.assistant_runtime.dispatcher.state.events
        event = next((event for event in reversed(events) if event.type in ('operation_completed', 'waiting_input', 'operation_failed')), None)
        if event is None:
            return
        trace = handle['work_trace']
        payload = {'status': 'needs_input', 'prompt': result.input_request.prompt} if result.input_request else result.result
        step = AgentStep(len(trace.entries) + 1, '', event.operation_name,
            tool_result=payload, error=result.error, artifacts=[result.artifact] if result.artifact else [])
        trace.add_step(step)
        trace.set_status('Cần thêm dữ kiện' if result.status == 'needs_input' else 'Đã cập nhật' if result.status == 'success' else 'Chưa hoàn tất')

    def _prefill_chat(self, text: str) -> None:
        self.chat_composer_input.setText(text)
        self.chat_composer_input.setFocus()
        self.chat_composer_input.setCursorPosition(len(text))

    def _submit_full_chat_prompt(self) -> None:
        self._submit_chat_prompt(self.chat_composer_input.text())

    def _submit_full_chat_or_stop(self) -> None:
        if self._pending_chat_query is not None:
            self._cancel_assistant()
        else:
            self._submit_full_chat_prompt()

    def _set_compact_files(self, files: Optional[List[SearchResultItem]]) -> None:
        self.compact_file_list.clear()
        for result in (files or [])[:4]:
            list_item = QListWidgetItem()
            list_item.setData(Qt.ItemDataRole.UserRole, result)
            list_item.setData(Qt.ItemDataRole.AccessibleTextRole, result.file_name)
            list_item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, result.file_path)
            list_item.setSizeHint(QSize(1, CompactFileRow.ROW_HEIGHT))
            self.compact_file_list.addItem(list_item)
            row = CompactFileRow(result)
            row.open_requested.connect(lambda item: self.feedback.perform("open", item, open_file_default))
            row.reveal_requested.connect(lambda item: self.feedback.perform("reveal", item, reveal_in_finder))
            row.preview_requested.connect(lambda item: trigger_quicklook(item.file_path))
            row.question_requested.connect(self._select_document_question)
            self.compact_file_list.setItemWidget(list_item, row)
        count = self.compact_file_list.count()
        self.compact_file_list.setFixedHeight(max(1, count) * CompactFileRow.ROW_HEIGHT + 4)
        if count:
            self.compact_file_list.setCurrentRow(0)
        self._sync_compact_surface()
        if not self.is_expanded:
            self._resize_overlay(652, self._compact_height())

    def _init_finder_service(self, catalog: Optional[ApplicationCatalog] = None) -> None:
        if catalog is not None:
            self._on_finder_catalog_ready(catalog)
            return

        def scan_job() -> None:
            try:
                cat = ApplicationCatalog.scan()
                self._finder_bridge.catalog_ready.emit(cat)
            except Exception as ex:
                logger.exception("Finder application catalog scan failed: %s", ex)

        threading.Thread(target=scan_job, name="rat-finder-catalog-init", daemon=True).start()

    def _on_finder_catalog_ready(self, catalog: ApplicationCatalog) -> None:
        if getattr(self, "_shutting_down", False):
            return
        self._finder_catalog = catalog
        self._finder_search = ProgressiveSearch(config.db_path, catalog=catalog)
        self._finder_coordinator = SearchCoordinator(
            self._finder_search,
            on_update=lambda snap: self._finder_bridge.snapshot_ready.emit(snap),
        )
        if hasattr(self, "chat_composer_input") and not getattr(self.chat_composer_input, "is_composing", lambda: False)():
            q = self.chat_composer_input.text().strip()
            if q and len(q) <= 2000 and getattr(self, "workbench_finder_enabled", False):
                self._finder_coordinator.submit(q, limit=15, selected_id=self._finder_selected_id)

    @pyqtSlot(object)
    def _on_finder_snapshot_delivered(self, snapshot: SearchSnapshot) -> None:
        if self._finder_coordinator is None or not self._finder_coordinator.is_current(snapshot.query_id):
            return

        # Maintain selection by resource_id
        current_sel = self._finder_selected_id
        if getattr(self, "workbench_scene_enabled", False) and hasattr(self, "workbench_scene"):
            box_sel = getattr(self.workbench_scene.finder_box, "selected_resource_id", None)
            if box_sel:
                current_sel = box_sel

        if any(h.resource_id == current_sel for h in snapshot.hits):
            self._finder_selected_id = current_sel
        elif snapshot.hits:
            self._finder_selected_id = snapshot.hits[0].resource_id
        else:
            self._finder_selected_id = None

        if getattr(self, "workbench_scene_enabled", False) and hasattr(self, "workbench_scene"):
            self.workbench_scene.set_finder_snapshot(snapshot, selected_id=self._finder_selected_id)
            if snapshot.hits:
                self._interaction_surface_active = True
                self.content_stack.setVisible(True)
                if hasattr(self, "workbench_canvas") and hasattr(self.workbench_canvas, "content_container"):
                    self.workbench_canvas.content_container.setVisible(True)
                self._schedule_surface_fit()
        else:
            file_hits = [
                SearchResultItem(
                    file_path=h.path,
                    file_name=h.title,
                    file_ext=Path(h.path).suffix,
                    file_size=0,
                    modified_at=0.0,
                    score=0.0,
                    explanation="",
                    snippet=h.snippet,
                )
                for h in snapshot.hits
                if h.kind == "file"
            ]
            self._set_compact_files(file_hits)

    def _on_composer_text_changed(self, text: str) -> None:
        if hasattr(self, "chat_composer_input") and getattr(self.chat_composer_input, "is_composing", lambda: False)():
            return

        q = text.strip()
        is_active = bool(q)
        self.chat_composer_send.setEnabled(self._artifact_worker is None and (is_active or self._pending_chat_query is not None))
        if hasattr(self, "return_keycap"):
            self.return_keycap.setProperty("active", "true" if is_active else "false")
            self.return_keycap.style().unpolish(self.return_keycap)
            self.return_keycap.style().polish(self.return_keycap)

        if not q:
            if getattr(self, "rat_stage", None):
                self.rat_stage.set_state("idle")
            if hasattr(self, "speech_bubble") and hasattr(self, "chat_stream") and self.chat_stream.is_empty():
                self.speech_bubble.reset_welcome()
            if getattr(self, "workbench_finder_enabled", False):
                if getattr(self, "_finder_coordinator", None) is not None:
                    self._finder_coordinator.cancel()
                self._finder_selected_id = None
                if getattr(self, "workbench_scene_enabled", False) and hasattr(self, "workbench_scene"):
                    self.workbench_scene.clear_finder_snapshot()
                self._set_compact_files(None)
                if (
                    self.chat_stream.is_empty()
                    and not self.is_expanded
                    and (
                        not hasattr(self, "workbench_scene")
                        or self.workbench_scene.is_empty()
                    )
                ):
                    self._interaction_surface_active = False
                    self.content_stack.setVisible(False)
                    if hasattr(self, "workbench_canvas") and hasattr(self.workbench_canvas, "content_container"):
                        self.workbench_canvas.content_container.setVisible(False)
                    self._schedule_surface_fit()
            return

        if getattr(self, "rat_stage", None):
            self.rat_stage.set_state("listening", "Chuột · Đang nghe")

        # Progressive finder search if enabled and ready
        if getattr(self, "workbench_finder_enabled", False):
            if len(q) > 2000:
                if getattr(self, "_finder_coordinator", None) is not None:
                    self._finder_coordinator.cancel()
                self._finder_selected_id = None
                if getattr(self, "workbench_scene_enabled", False) and hasattr(self, "workbench_scene"):
                    self.workbench_scene.clear_finder_snapshot()
                self._set_compact_files(None)
            elif getattr(self, "_finder_coordinator", None) is not None:
                try:
                    self._finder_coordinator.submit(q, limit=15, selected_id=self._finder_selected_id)
                except ValueError:
                    if getattr(self, "_finder_coordinator", None) is not None:
                        self._finder_coordinator.cancel()
                    self._finder_selected_id = None
                    if getattr(self, "workbench_scene_enabled", False) and hasattr(self, "workbench_scene"):
                        self.workbench_scene.clear_finder_snapshot()
                    self._set_compact_files(None)

    def _on_finder_hit_selected(self, resource_id: str) -> None:
        self._finder_selected_id = resource_id

    def _on_scene_mode_changed(self, mode: str) -> None:
        if not getattr(self, "workbench_scene_enabled", False) or not hasattr(self, "workbench_scene"):
            return
        snap = self.workbench_scene.current_snapshot
        if mode == "source_detail" and self.workbench_scene.selected_source_id:
            src = self.workbench_scene.find_source(self.workbench_scene.selected_source_id)
            if src is not None:
                self.workbench_canvas.set_work(
                    f"Nguồn: {src.title}",
                    status=src.scope_label or "Đi sâu vào nguồn",
                )
                self.workbench_canvas.mode_lbl.setText("Đi sâu vào nguồn")
                self.workbench_speech_bubble.set_reply(
                    f"Đang mở {src.title} ({src.scope_label or 'chi tiết'}). Nhấn ‘← Tổng quan công việc’ hoặc gõ ‘quay lại’ để về bàn.",
                    "Chi tiết nguồn",
                    copy_text=src.snippet or src.title,
                    has_details=True,
                )
        else:
            title = (snap.result_node.title if snap.result_node else None) or snap.query or "Không gian làm việc"
            self.workbench_canvas.set_work(title, status=snap.phase_label or "Đã xong")
            self.workbench_canvas.mode_lbl.setText(
                "Chi tiết công việc" if self.is_expanded else "Tổng quan công việc"
            )
            if snap.phase != "empty":
                copy_txt = (snap.result_node.answer_text if snap.result_node else "") or snap.rat_speech
                self.workbench_speech_bubble.set_reply(
                    snap.rat_speech,
                    snap.phase_label,
                    copy_text=copy_txt,
                    has_details=not self.workbench_scene.is_empty(),
                    is_error=(snap.phase == "error"),
                )
        self._schedule_surface_fit()

    def _sync_workbench_scene(
        self,
        *,
        artifacts: Optional[List[Any]] = None,
        animate: bool = True,
    ) -> None:
        if not getattr(self, "workbench_scene_enabled", False) or not hasattr(self, "workbench_scene"):
            return
        snap = self.workbench_scene.projector.snapshot(store=self.assistant_runtime.artifact_store)
        self.workbench_scene.apply_snapshot(snap, artifacts=artifacts, animate=animate)

        if self.workbench_scene.is_empty():
            self.workbench_canvas.reset_work()
            self.workbench_speech_bubble.reset_welcome()
            self.workbench_user_lane.set_phase("idle")
            self._sync_compact_surface()
            return

        if self.workbench_scene.mode == "source_detail" and self.workbench_scene.selected_source_id:
            self._on_scene_mode_changed("source_detail")
        else:
            title = (snap.result_node.title if snap.result_node else None) or snap.query or "Không gian làm việc"
            self.workbench_canvas.set_work(title, status=snap.phase_label or "Đang xử lý")
            self.workbench_canvas.mode_lbl.setText(
                "Chi tiết công việc" if self.is_expanded else "Tổng quan công việc"
            )
            copy_txt = (snap.result_node.answer_text if snap.result_node else "") or snap.rat_speech
            self.workbench_speech_bubble.set_reply(
                snap.rat_speech,
                snap.phase_label,
                copy_text=copy_txt,
                has_details=True,
                is_error=(snap.phase == "error"),
            )

        lane_phase = {
            "empty": "idle",
            "working": "working",
            "waiting": "waiting",
            "done": "done",
            "error": "error",
            "cancelled": "cancelled",
        }.get(snap.phase, "idle")
        self.workbench_user_lane.set_phase(lane_phase)
        self._sync_compact_surface()

    def _apply_theme(self) -> None:
        if hasattr(self, "workbench_canvas") and hasattr(self.workbench_canvas, "_apply_theme"):
            self.workbench_canvas._apply_theme()
        if hasattr(self, "thought_trail") and hasattr(self.thought_trail, "_apply_theme"):
            self.thought_trail._apply_theme()
        if hasattr(self, "workbench_dialogue") and hasattr(self.workbench_dialogue, "_apply_theme"):
            self.workbench_dialogue._apply_theme()
        if getattr(self, "workbench_scene_enabled", False) and hasattr(self, "workbench_scene") and hasattr(self.workbench_scene, "_apply_theme"):
            self.workbench_scene._apply_theme()


    # -----------------------------------------------------------------
    # PAGE 0: CHAT HOME
    # -----------------------------------------------------------------
    def _create_home_view(self) -> QWidget:
        widget = QWidget()
        root_layout = QVBoxLayout(widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(4)

        first_name = self.current_member.name.split()[-1] if self.current_member.name else "bạn"
        self.chat_stream = ChatStreamWidget(user_name=first_name)

        def _on_chat_prompt_action(prompt: str) -> None:
            if prompt.endswith(" ") or prompt.endswith(": "):
                self._prefill_chat(prompt)
            else:
                self._submit_chat_prompt(prompt)

        self._on_chat_prompt_action = _on_chat_prompt_action
        self.chat_stream.prompt_clicked.connect(_on_chat_prompt_action)
        self.chat_stream.document_question_requested.connect(self._select_document_question)
        self.chat_stream.note_edit_saved.connect(self._on_turn_note_edited)
        self.chat_stream.note_removed.connect(self._on_turn_note_removed)
        self.chat_stream.note_restored.connect(self._on_turn_note_restored)
        self.chat_stream.note_confirmed.connect(self._on_turn_note_confirmed)
        self.chat_stream.navigate_turn_requested.connect(self.chat_stream.navigate_to_turn_note)
        self.chat_stream.edit_replacement_requested.connect(self.chat_stream.open_editor_on_note)

        self.workbench_scene = WorkbenchScene(
            registry=self.assistant_runtime.registry,
            store=self.assistant_runtime.artifact_store,
            on_open_file=open_file_default,
            on_action=self._on_action_dispatched,
            on_input=self._on_input_submitted,
            on_question=self._select_document_question,
            parent=widget,
        )
        self.workbench_scene.mode_changed.connect(self._on_scene_mode_changed)
        self.workbench_scene.content_changed.connect(self._schedule_surface_fit)
        self.workbench_scene.finder_box.set_event_filter(self.input_filter)
        self.workbench_scene.finder_box.hit_selected.connect(self._on_finder_hit_selected)

        if self.workbench_scene_enabled:
            root_layout.addWidget(self.workbench_scene, 1)
            self.workbench_scene.show()
            self.chat_stream.hide()
        else:
            self.workbench_scene.hide()
            root_layout.addWidget(self.chat_stream, 1)

        self.full_chat_input = self.chat_composer_input
        self.full_chat_send = self.chat_composer_send
        self.chat_stream.content_changed.connect(self._sync_compact_surface)

        # Hidden Compatibility Container for Tests
        compat_box = QWidget(widget)
        compat_box.setObjectName("compat_box")
        compat_box.hide()
        compat_box.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        compat_box.setMaximumSize(0, 0)
        compat_layout = QVBoxLayout(compat_box)
        if self.workbench_scene_enabled:
            compat_layout.addWidget(self.chat_stream)

        # Micro footer (kept inside compat container so it never becomes a top-level window)
        self.chat_micro_footer = QWidget(compat_box)
        self.chat_micro_footer.hide()
        self.chat_micro_status = QLabel("● Sẵn sàng", self.chat_micro_footer)
        compat_layout.addWidget(self.chat_micro_footer)

        self.today_date_label = QLabel("Hôm nay", compat_box)
        self.profile_badge = QLabel(self.current_member.name, compat_box)
        self.live_countdown_banner = QFrame(compat_box)
        b_layout = QHBoxLayout(self.live_countdown_banner)
        self.live_banner_text = QLabel("Đang kiểm tra lịch học...", self.live_countdown_banner)
        b_layout.addWidget(self.live_banner_text)

        self.agenda_scroll = QScrollArea(compat_box)
        self.agenda_content = QWidget(self.agenda_scroll)
        self.agenda_layout = QVBoxLayout(self.agenda_content)
        self.agenda_scroll.setWidget(self.agenda_content)

        self.recent_list = QListWidget(compat_box)
        self.recent_list_filter = OmnibarListFilter(self)
        self.recent_list.installEventFilter(self.recent_list_filter)

        compat_layout.addWidget(self.today_date_label)
        compat_layout.addWidget(self.profile_badge)
        compat_layout.addWidget(self.live_countdown_banner)
        compat_layout.addWidget(self.agenda_scroll)
        compat_layout.addWidget(self.recent_list)

        root_layout.addWidget(compat_box)
        return widget

    # -----------------------------------------------------------------
    # PAGE 1: FILES VIEW (Dual-Pane Search & Preview)
    # -----------------------------------------------------------------
    def _create_files_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Search Input Header Row for Files
        search_row = QFrame()
        search_row.setObjectName("FileSearchRow")
        search_row.setStyleSheet("background-color: transparent; border-bottom: 1px solid rgba(43, 38, 31, 0.08); padding: 8px 12px;")
        sr_layout = QHBoxLayout(search_row)
        sr_layout.setContentsMargins(0, 0, 0, 0)
        sr_layout.setSpacing(8)

        self.search_icon = QLabel("🔍")
        self.search_icon.setStyleSheet("font-size: 13px; border: none; background: transparent;")
        sr_layout.addWidget(self.search_icon)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchInput")
        self.search_input.setPlaceholderText("Tìm tên file, nội dung hoặc loại tài liệu…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.search_input.installEventFilter(self.input_filter)
        sr_layout.addWidget(self.search_input, 1)

        self.btn_send = QPushButton("Tìm")
        self.btn_send.setObjectName("SendButton")
        self.btn_send.setProperty("class", "SendButton")
        self.btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send.clicked.connect(self._execute_search)
        sr_layout.addWidget(self.btn_send)

        layout.addWidget(search_row)

        # Sub-category filter pills for files
        sub_bar = QFrame()
        sub_bar.setStyleSheet("background-color: transparent; border-bottom: 1px solid rgba(43, 38, 31, 0.06); padding: 4px 14px;")
        sub_layout = QHBoxLayout(sub_bar)
        sub_layout.setContentsMargins(0, 0, 0, 0)
        sub_layout.setSpacing(6)

        self.file_filter_buttons: List[QPushButton] = []
        for idx, (cat_id, label, _) in enumerate(FILTER_CATEGORIES):
            btn = QPushButton(label)
            btn.setProperty("class", "FilterPill")
            btn.setProperty("active", "true" if idx == 0 else "false")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, i=idx: self._select_file_filter(i))
            sub_layout.addWidget(btn)
            self.file_filter_buttons.append(btn)

        sub_layout.addStretch()
        layout.addWidget(sub_bar)

        # Dual Pane Splitter (50/50)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setStyleSheet("QSplitter::handle { background-color: rgba(43, 38, 31, 0.08); width: 1px; }")

        # Left List
        self.result_list = QListWidget()
        self.result_list.setObjectName("ResultList")
        self.result_list.setFrameShape(QFrame.Shape.NoFrame)
        self.result_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.result_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.result_list.setItemDelegate(AppleSpotlightDelegate(self))
        self.result_list.currentRowChanged.connect(self._on_result_selected)
        self.result_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.list_filter = OmnibarListFilter(self)
        self.result_list.installEventFilter(self.list_filter)
        self.splitter.addWidget(self.result_list)

        # Right Inspector Panel
        self.preview_panel = PreviewPanel()
        self.preview_panel.ask_requested.connect(self._on_selected_document_question)
        self.splitter.addWidget(self.preview_panel)

        self.splitter.setSizes([280, 380])
        layout.addWidget(self.splitter, 1)
        return widget

    # -----------------------------------------------------------------
    # PAGE 2: SCHEDULE VIEW (Integrated Timetable)
    # -----------------------------------------------------------------
    def _create_schedule_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Toolbar: Member Selector, Degree Level, Day Picker
        toolbar = QFrame()
        toolbar.setStyleSheet("background-color: #FAF7F1; border: 1px solid rgba(43, 38, 31, 0.08); border-radius: 8px; padding: 5px 10px;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(0, 0, 0, 0)
        tb_layout.setSpacing(8)

        combo_style = """
        QComboBox {
            background-color: #F8F5F0;
            color: #26221D;
            border: 1px solid rgba(43, 38, 31, 0.12);
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 11.5px;
        }
        QComboBox:hover {
            background-color: #FFFFFF;
            border-color: #FFB800;
        }
        QComboBox::drop-down {
            border: none;
        }
        QComboBox QAbstractItemView {
            background-color: #FFFFFF;
            color: #26221D;
            border: 1px solid rgba(43, 38, 31, 0.12);
            selection-background-color: #FFF4D4;
            selection-color: #26221D;
        }
        """

        lbl_member = QLabel("Hồ sơ:")
        lbl_member.setStyleSheet("color: #887c70; font-size: 11px;")
        tb_layout.addWidget(lbl_member)
        self.sched_member_combo = QComboBox()
        self.sched_member_combo.setStyleSheet(combo_style)
        for m in self.members:
            suffix = " (Song bằng ĐH+ThS)" if m.is_dual_degree else ""
            self.sched_member_combo.addItem(f"{m.name}{suffix}", m.id)
        self.sched_member_combo.currentIndexChanged.connect(self._on_sched_member_changed)
        tb_layout.addWidget(self.sched_member_combo)

        lbl_degree = QLabel("Bậc học:")
        lbl_degree.setStyleSheet("color: #887c70; font-size: 11px;")
        tb_layout.addWidget(lbl_degree)
        self.sched_degree_combo = QComboBox()
        self.sched_degree_combo.setStyleSheet(combo_style)
        self.sched_degree_combo.addItems(["Tất cả bậc", "Đại học", "Thạc sĩ"])
        self.sched_degree_combo.currentIndexChanged.connect(self._refresh_schedule_view)
        tb_layout.addWidget(self.sched_degree_combo)

        tb_layout.addStretch()

        self.btn_copy_schedule = QPushButton("Sao chép TKB")
        self.btn_copy_schedule.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #26221D;
                border: 1px solid rgba(43, 38, 31, 0.12);
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #FFF8E7;
                border-color: #FFB800;
                color: #B27B00;
            }
        """)
        self.btn_copy_schedule.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_schedule.clicked.connect(self._copy_current_schedule)
        tb_layout.addWidget(self.btn_copy_schedule)

        layout.addWidget(toolbar)

        # Day selection pills (Hôm nay, T2..CN)
        day_bar = QFrame()
        day_layout = QHBoxLayout(day_bar)
        day_layout.setContentsMargins(0, 0, 0, 0)
        day_layout.setSpacing(4)

        self.day_buttons: List[QPushButton] = []
        days_list = [("TODAY", "Hôm Nay")] + [(d[0], d[1]) for d in DAYS]
        self.selected_day_code = "TODAY"

        for idx, (d_code, d_name) in enumerate(days_list):
            btn = QPushButton(d_name)
            btn.setProperty("class", "FilterPill")
            btn.setProperty("active", "true" if idx == 0 else "false")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, code=d_code, i=idx: self._select_sched_day(code, i))
            day_layout.addWidget(btn)
            self.day_buttons.append(btn)

        day_layout.addStretch()
        layout.addWidget(day_bar)

        # Sessions Content Area
        self.sched_scroll = QScrollArea()
        self.sched_scroll.setWidgetResizable(True)
        self.sched_scroll.setStyleSheet("border: 1px solid rgba(43, 38, 31, 0.08); border-radius: 10px; background-color: #FFFFFF;")
        self.sched_content = QWidget()
        self.sched_layout = QVBoxLayout(self.sched_content)
        self.sched_layout.setContentsMargins(10, 10, 10, 10)
        self.sched_layout.setSpacing(6)
        self.sched_scroll.setWidget(self.sched_content)
        layout.addWidget(self.sched_scroll, 1)

        return widget

    # -----------------------------------------------------------------
    # PAGE 3: CLUB VIEW (Group Matrix & Golden Slots)
    # -----------------------------------------------------------------
    def _create_club_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Header Info Banner
        banner = QFrame()
        banner.setStyleSheet("background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 8px; padding: 8px 12px;")
        b_layout = QHBoxLayout(banner)
        b_layout.setContentsMargins(0, 0, 0, 0)

        banner_text = QLabel("Khung Giờ Vàng CLB: Các khung giờ có từ 80% đến 100% thành viên rảnh để họp nhóm, làm đồ án.")
        banner_text.setStyleSheet("color: #166534; font-size: 11.5px;")
        banner_text.setWordWrap(True)
        b_layout.addWidget(banner_text)

        btn_copy_club = QPushButton("Sao chép")
        btn_copy_club.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #166534;
                border: 1px solid #BBF7D0;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #DCFCE7;
            }
        """)
        btn_copy_club.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy_club.clicked.connect(self._copy_golden_slots)
        b_layout.addWidget(btn_copy_club)

        layout.addWidget(banner)

        # Golden Slots Scroll Area
        self.club_scroll = QScrollArea()
        self.club_scroll.setWidgetResizable(True)
        self.club_scroll.setStyleSheet("border: 1px solid rgba(43, 38, 31, 0.08); border-radius: 10px; background-color: #FAF7F1;")
        self.club_content = QWidget()
        self.club_layout = QVBoxLayout(self.club_content)
        self.club_layout.setContentsMargins(10, 10, 10, 10)
        self.club_layout.setSpacing(6)
        self.club_scroll.setWidget(self.club_content)
        layout.addWidget(self.club_scroll, 1)

        return widget

    # -----------------------------------------------------------------
    # PAGE 4: SETTINGS VIEW (Seamless System Configuration)
    # -----------------------------------------------------------------
    def _create_settings_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        c_layout = QVBoxLayout(content)
        c_layout.setContentsMargins(2, 2, 2, 2)
        c_layout.setSpacing(10)

        # 1. Indexed Directories Card
        folder_card = QFrame()
        folder_card.setProperty("class", "SettingsCard")
        folder_card.setStyleSheet("""
            QFrame.SettingsCard {
                background-color: #FFFFFF;
                border: 1px solid #E2D9CD;
                border-radius: 10px;
                padding: 12px;
            }
        """)
        fc_layout = QVBoxLayout(folder_card)
        fc_layout.setContentsMargins(12, 10, 12, 10)
        fc_layout.setSpacing(8)

        f_header = QHBoxLayout()
        f_title = QLabel("📁 Thư mục đang giám sát (FSEvents Realtime)")
        f_title.setStyleSheet("color: #1F1A16; font-size: 12.5px; font-weight: 700;")
        f_header.addWidget(f_title)
        f_header.addStretch()

        btn_add_folder = QPushButton("+ Thêm thư mục")
        btn_add_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add_folder.setStyleSheet("""
            QPushButton {
                background-color: #F8F5F0;
                color: #3D352B;
                border: 1px solid #DCD4C4;
                border-bottom: 2px solid #C4B9A8;
                border-radius: 6px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #FFFFFF;
                color: #1F1A16;
            }
        """)
        btn_add_folder.clicked.connect(self._settings_add_folder)
        f_header.addWidget(btn_add_folder)
        fc_layout.addLayout(f_header)

        self.settings_folder_list = QListWidget()
        self.settings_folder_list.setFixedHeight(75)
        self.settings_folder_list.setStyleSheet("""
            QListWidget {
                background-color: #FAF8F5;
                border: 1px solid #EAE3D6;
                border-radius: 6px;
                color: #3D352B;
                font-size: 11px;
                padding: 3px;
            }
            QListWidget::item {
                padding: 3px 6px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #F3ECDf;
                color: #1F1A16;
            }
        """)
        for d in config.indexed_directories:
            self.settings_folder_list.addItem(str(d))
        fc_layout.addWidget(self.settings_folder_list)

        btn_remove_folder = QPushButton("- Xóa thư mục chọn")
        btn_remove_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_remove_folder.setStyleSheet(btn_add_folder.styleSheet())
        btn_remove_folder.clicked.connect(self._settings_remove_folder)
        fc_layout.addWidget(btn_remove_folder, alignment=Qt.AlignmentFlag.AlignRight)

        c_layout.addWidget(folder_card)

        # 2. Hotkey & System Governance Card
        sys_card = QFrame()
        sys_card.setProperty("class", "SettingsCard")
        sys_card.setStyleSheet(folder_card.styleSheet())
        sc_layout = QVBoxLayout(sys_card)
        sc_layout.setContentsMargins(12, 10, 12, 10)
        sc_layout.setSpacing(6)

        sys_title = QLabel("⚡ Hệ thống & Phím tắt toàn cầu")
        sys_title.setStyleSheet("color: #1F1A16; font-size: 12.5px; font-weight: 700;")
        sc_layout.addWidget(sys_title)

        row_hotkey = QHBoxLayout()
        lbl_hk = QLabel("Phím tắt kích hoạt:")
        lbl_hk.setStyleSheet("color: #786F66; font-size: 11px;")
        val_hk = QLabel("⌘ ⇧ Space  /  ⌥ Space  /  ⌥ R")
        val_hk.setStyleSheet("color: #1F1A16; font-size: 11px; font-weight: 700;")
        row_hotkey.addWidget(lbl_hk)
        row_hotkey.addWidget(val_hk)
        row_hotkey.addStretch()
        sc_layout.addLayout(row_hotkey)

        row_sentinel = QHBoxLayout()
        lbl_sen = QLabel("Memory Sentinel:")
        lbl_sen.setStyleSheet("color: #786F66; font-size: 11px;")
        val_sen = QLabel("Tự động giải phóng RAM khi rảnh rỗi (2700s idle)")
        val_sen.setStyleSheet("color: #059669; font-size: 11px; font-weight: 600;")
        row_sentinel.addWidget(lbl_sen)
        row_sentinel.addWidget(val_sen)
        row_sentinel.addStretch()
        sc_layout.addLayout(row_sentinel)

        row_cache = QHBoxLayout()
        lbl_cache = QLabel("FTS5 LRU Cache:")
        lbl_cache.setStyleSheet("color: #786F66; font-size: 11px;")
        val_cache = QLabel("Đang kích hoạt (Phản hồi < 1ms)")
        val_cache.setStyleSheet("color: #059669; font-size: 11px; font-weight: 600;")
        row_cache.addWidget(lbl_cache)
        row_cache.addWidget(val_cache)
        row_cache.addStretch()
        sc_layout.addLayout(row_cache)

        c_layout.addWidget(sys_card)

        assistant_card = QFrame()
        assistant_card.setStyleSheet(folder_card.styleSheet())
        ai_layout = QVBoxLayout(assistant_card)
        ai_layout.setContentsMargins(12, 10, 12, 10)
        ai_layout.addWidget(QLabel("Model cho cuộc trò chuyện"))
        ai_row = QHBoxLayout()
        self.settings_assistant_combo = QComboBox()
        self.settings_assistant_combo.setAccessibleName("Model trợ lý cục bộ")
        self.settings_assistant_combo.addItem("Theo SLM hiện tại · " + config.ollama_model, "")
        self.settings_assistant_combo.currentIndexChanged.connect(self._settings_choose_assistant_model)
        ai_row.addWidget(self.settings_assistant_combo, 1)
        refresh_models = QPushButton("Cập nhật danh sách")
        refresh_models.clicked.connect(self._refresh_assistant_models)
        ai_row.addWidget(refresh_models)
        ai_layout.addLayout(ai_row)
        note = QLabel("Chọn model đã tải trong Ollama. Áp dụng từ lượt chat tiếp theo.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #786F66; font-size: 11px;")
        ai_layout.addWidget(note)
        c_layout.addWidget(assistant_card)

        # 3. Maintenance & Actions Card
        act_card = QFrame()
        act_card.setProperty("class", "SettingsCard")
        act_card.setStyleSheet(folder_card.styleSheet())
        ac_layout = QVBoxLayout(act_card)
        ac_layout.setContentsMargins(12, 10, 12, 10)
        ac_layout.setSpacing(8)

        act_title = QLabel("🛠 Bảo trì chỉ mục tìm kiếm")
        act_title.setStyleSheet("color: #1F1A16; font-size: 12.5px; font-weight: 700;")
        ac_layout.addWidget(act_title)

        act_btn_row = QHBoxLayout()
        self.btn_reindex = QPushButton("🔄 Quét lại toàn bộ (Re-index)")
        self.btn_reindex.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reindex.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F59E0B, stop:1 #D97706);
                color: #FFFFFF;
                border: 1px solid #B45309;
                border-bottom: 2px solid #92400E;
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #F59E0B;
            }
        """)
        self.btn_reindex.clicked.connect(self._settings_run_reindex)
        act_btn_row.addWidget(self.btn_reindex)

        btn_clean_stale = QPushButton("🧹 Dọn tệp tin đã xóa")
        btn_clean_stale.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clean_stale.setStyleSheet(btn_add_folder.styleSheet())
        btn_clean_stale.clicked.connect(self._settings_clean_stale)
        act_btn_row.addWidget(btn_clean_stale)
        act_btn_row.addStretch()
        ac_layout.addLayout(act_btn_row)

        self.settings_progress = QProgressBar()
        self.settings_progress.setFixedHeight(4)
        self.settings_progress.setTextVisible(False)
        self.settings_progress.setRange(0, 0)
        self.settings_progress.setStyleSheet("""
            QProgressBar {
                background: #EAE3D6;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: #D97706;
                border-radius: 2px;
            }
        """)
        self.settings_progress.hide()
        ac_layout.addWidget(self.settings_progress)

        self.settings_status_lbl = QLabel("")
        self.settings_status_lbl.setStyleSheet("color: #786F66; font-size: 10.5px;")
        ac_layout.addWidget(self.settings_status_lbl)

        c_layout.addWidget(act_card)
        c_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return widget

    def _refresh_settings_view(self) -> None:
        self._refresh_assistant_models()
        if hasattr(self, "settings_folder_list"):
            self.settings_folder_list.clear()
            for d in config.indexed_directories:
                self.settings_folder_list.addItem(str(d))

    def _refresh_assistant_models(self):
        from rat.engine.slm import slm_engine
        combo = self.settings_assistant_combo
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Theo SLM hiện tại · " + config.ollama_model, "")
        names = slm_engine.list_installed_models()
        for name in dict.fromkeys(names + ([config.assistant_model] if config.assistant_model else [])):
            combo.addItem(name, name)
        combo.setCurrentIndex(max(0, combo.findData(config.assistant_model)))
        combo.blockSignals(False)

    def _settings_choose_assistant_model(self, index):
        selected = self.settings_assistant_combo.itemData(index)
        if isinstance(selected, str):
            config.assistant_model = selected
            config.save()
            self.settings_status_lbl.setText("Đã lưu model cho lượt chat tiếp theo.")

    def _apply_assistant_model(self):
        from rat.engine.slm import SLMEngine
        chosen = config.assistant_model or config.ollama_model
        client = self.assistant_runtime.model_client
        if client is None or client.model != chosen:
            self.assistant_runtime.model_client = SLMEngine(model=chosen)
        self.full_model_badge.setText("● " + chosen)

    def _settings_add_folder(self) -> None:
        from PyQt6.QtWidgets import QFileDialog
        chosen = QFileDialog.getExistingDirectory(self, "Chọn thư mục lập chỉ mục")
        if chosen and chosen not in config.indexed_directories:
            config.indexed_directories.append(chosen)
            config.save()
            self._refresh_settings_view()
            self.settings_status_lbl.setText(f"Đã thêm: {chosen}")

    def _settings_remove_folder(self) -> None:
        row = self.settings_folder_list.currentRow()
        if row >= 0:
            item = self.settings_folder_list.takeItem(row)
            if item and item.text() in config.indexed_directories:
                config.indexed_directories.remove(item.text())
                config.save()
                self.settings_status_lbl.setText(f"Đã gỡ: {item.text()}")

    def _settings_clean_stale(self) -> None:
        removed = self.db.clean_deleted_files()
        self.settings_status_lbl.setText(f"Đã dọn dẹp {removed} tệp không còn tồn tại trên ổ cứng.")

    def _settings_run_reindex(self) -> None:
        self.settings_progress.show()
        self.btn_reindex.setEnabled(False)
        self.settings_status_lbl.setText("Đang quét và lập chỉ mục lại toàn bộ...")

        from PyQt6.QtCore import QThread
        from rat.os.app import InitialIndexWorker
        self._set_reindex_thread = QThread()
        self._set_reindex_worker = InitialIndexWorker()
        self._set_reindex_worker.moveToThread(self._set_reindex_thread)
        self._set_reindex_thread.started.connect(self._set_reindex_worker.run)

        def _on_reindex_finished(indexed: int, total: int) -> None:
            self.settings_progress.hide()
            self.btn_reindex.setEnabled(True)
            self.settings_status_lbl.setText(f"Hoàn thành! Đã lập chỉ mục {total} tệp.")
            self._set_reindex_thread.quit()

        self._set_reindex_worker.finished.connect(_on_reindex_finished, Qt.ConnectionType.QueuedConnection)
        self._set_reindex_thread.start()

    # -----------------------------------------------------------------
    # SECTION NAVIGATION & SWITCHING
    # -----------------------------------------------------------------
    def switch_section(self, idx: int) -> None:
        if idx < 0 or idx >= len(SECTION_TABS):
            return
        if idx != 0 and self._chat_file_request is not None:
            self._chat_file_request = None
            self._pending_chat_query = None
            self._request_counter += 1
        self.current_section_idx = idx
        self.content_stack.setCurrentIndex(idx)
        show_file_search = idx == 1
        self.search_icon.setVisible(show_file_search)
        self.search_input.setVisible(show_file_search)
        self.btn_send.setVisible(show_file_search)
        self.action_footer.setVisible(self.is_expanded or idx != 0)
        self._render_action_footer_keycaps()

        # Update pill states
        for i, btn in enumerate(self.section_buttons):
            btn.setProperty("active", "true" if i == idx else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        if hasattr(self, "quick_bar"):
            self.quick_bar.setVisible(not self.is_expanded and idx == 0)

        sec_id = SECTION_TABS[idx][0]
        if sec_id == "home":
            if self.is_expanded:
                self.set_expanded(True)
            else:
                self.set_expanded(False)
            self._refresh_home_agenda()
            self._load_recent_files()
            self.footer_status.setText("Chuột đang nghe. Cứ hỏi tự nhiên nha.")
            if hasattr(self, "chat_composer_input"):
                self.chat_composer_input.setFocus()
        else:
            self.set_expanded(True)
            if sec_id == "files":
                self._execute_search()
                self.search_input.setFocus()
            elif sec_id == "schedule":
                self._refresh_schedule_view()
                self.footer_status.setText(f"Thời khóa biểu · {self.current_member.name}")
            elif sec_id == "club":
                self._refresh_club_view()
                self.footer_status.setText("Khung giờ rảnh nhóm & Ma trận CLB")
            elif sec_id == "settings":
                self._refresh_settings_view()
                self.footer_status.setText("Cài đặt hệ thống & Lập chỉ mục · RAT")
                if hasattr(self, "quick_bar"):
                    self.quick_bar.hide()

    def cycle_section(self, delta: int) -> None:
        new_idx = (self.current_section_idx + delta) % len(SECTION_TABS)
        self.switch_section(new_idx)

    # -----------------------------------------------------------------
    # DATA LOADING & REFRESH LOGIC
    # -----------------------------------------------------------------
    def _load_initial_data(self) -> None:
        stats = self.db.get_stats()
        self.footer_status.setText(f"{stats.get('total_files', 0)} tệp trong kho")
        self._refresh_home_agenda()
        self._load_recent_files()
        self.switch_section(0)

    def _load_recent_files(self) -> None:
        try:
            recent_docs = self.db.get_recent_documents(limit=10)
            self.recent_list.clear()

            for doc in recent_docs:
                item = SearchResultItem(
                    file_path=doc.get("file_path", ""),
                    file_name=doc.get("file_name", ""),
                    file_ext=doc.get("file_ext", ""),
                    file_size=doc.get("file_size", 0),
                    modified_at=doc.get("modified_at", time.time()),
                    score=100.0,
                    explanation="Tệp tin gần đây",
                    snippet=f"Đường dẫn: {doc.get('file_path', '')}",
                )
                list_item = QListWidgetItem(self.recent_list)
                list_item.setData(Qt.ItemDataRole.UserRole, item)
                self.recent_list.addItem(list_item)

            if self.recent_list.count() > 0:
                self.recent_list.setCurrentRow(0)
            if hasattr(self, "feedback"):
                self.feedback.refresh(self.recent_list, "")
        except Exception as e:
            logger.debug(f"Error loading recent files: {e}")

    def _refresh_home_agenda(self) -> None:
        # Clear existing
        while self.agenda_layout.count():
            child = self.agenda_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        now = datetime.now()
        weekday_names = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
        day_str = weekday_names[now.weekday()]
        date_str = now.strftime("%d/%m/%Y")
        self.today_date_label.setText(f"{day_str}, {date_str}")

        agenda = self.compositor.get_today_agenda(self.current_member, now)
        if not agenda:
            self.live_countdown_banner.setStyleSheet("background-color: rgba(34, 197, 94, 0.1); border: 1px solid rgba(34, 197, 94, 0.2); border-radius: 8px; padding: 8px 12px;")
            self.live_banner_text.setText("Hôm nay bạn rảnh rồi — không có ca học nào trên lịch.")
            self.live_banner_text.setStyleSheet("color: #22c55e; font-size: 12px; font-weight: 600;")

            empty_lbl = QLabel("Tận hưởng ngày nghỉ hoặc tranh thủ làm đồ án nhé.")
            empty_lbl.setStyleSheet("color: #71717a; font-size: 12px; padding: 16px; qproperty-alignment: AlignCenter;")
            self.agenda_layout.addWidget(empty_lbl)
            self.agenda_layout.addStretch()
            return

        # Check live status
        live_item = next((item for item in agenda if item["status"] == "live"), None)
        upcoming_item = next((item for item in agenda if item["status"] == "upcoming"), None)

        if live_item:
            s = live_item["session"]
            self.live_countdown_banner.setStyleSheet("background-color: rgba(34, 197, 94, 0.1); border: 1.5px solid rgba(34, 197, 94, 0.2); border-radius: 8px; padding: 8px 12px;")
            self.live_banner_text.setText(f"Đang diễn ra: {s.course_name} (Phòng {s.room}) · {live_item['countdown']}")
            self.live_banner_text.setStyleSheet("color: #22c55e; font-size: 12px; font-weight: 700;")
        elif upcoming_item:
            s = upcoming_item["session"]
            deg = "[ThS]" if s.degree_level == "master" else "[ĐH]"
            self.live_countdown_banner.setStyleSheet("background-color: rgba(59, 130, 246, 0.1); border: 1.5px solid rgba(59, 130, 246, 0.2); border-radius: 8px; padding: 8px 12px;")
            self.live_banner_text.setText(f"Ca tiếp theo: [{upcoming_item['start_time']}] {deg} {s.course_name} (Phòng {s.room}) · {upcoming_item['countdown']}")
            self.live_banner_text.setStyleSheet("color: #60a5fa; font-size: 12px; font-weight: 700;")
        else:
            self.live_countdown_banner.setStyleSheet("background-color: #f6f2ec; border: 1px solid #e1d8cc; border-radius: 8px; padding: 6px 10px;")
            self.live_banner_text.setText("Đã hoàn thành các ca học hôm nay.")
            self.live_banner_text.setStyleSheet("color: #6a5e52; font-size: 11.5px; font-weight: 600;")

        # Render list of session cards
        for item in agenda:
            s = item["session"]
            st = degree_to_style(s.degree_level)
            card = QFrame()
            card.setObjectName("AgendaSessionCard")
            card.setStyleSheet(f"""
                QFrame#AgendaSessionCard {{
                    background-color: {st['bg']};
                    border: 1px solid {st['border']};
                    border-radius: 6px;
                    padding: 4px 8px;
                }}
                QFrame#AgendaSessionCard:hover {{
                    background-color: {st['bg_hover']};
                }}
                QLabel {{
                    border: none;
                    background: transparent;
                }}
            """)
            c_layout = QHBoxLayout(card)
            c_layout.setContentsMargins(4, 3, 6, 3)
            c_layout.setSpacing(8)

            badge_lbl = QLabel(st["badge"])
            badge_lbl.setFixedSize(26, 17)
            badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge_lbl.setStyleSheet(f"background-color: {st['tag_bg']}; color: #ffffff; font-size: 8.5px; font-weight: 700; border-radius: 3px; border: none;")
            c_layout.addWidget(badge_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

            v_info = QVBoxLayout()
            v_info.setSpacing(1)
            title_txt = f"<b>{s.course_name}</b> ({s.course_code})"
            t_lbl = QLabel(title_txt)
            t_lbl.setStyleSheet(f"color: {st['text']}; font-size: 11.5px; font-weight: 600;")
            sub_txt = f"{item['start_time']} - {item['end_time']} • Phòng {s.room} • {s.lecturer or 'Chưa rõ'}"
            s_lbl = QLabel(sub_txt)
            s_lbl.setStyleSheet("color: #81766b; font-size: 10px;")
            v_info.addWidget(t_lbl)
            v_info.addWidget(s_lbl)
            c_layout.addLayout(v_info, 1)

            status_tag = QLabel(item["badge"])
            status_tag.setStyleSheet("color: #887c70; font-size: 9.5px; font-weight: 550;")
            c_layout.addWidget(status_tag)

            self.agenda_layout.addWidget(card)

    def _refresh_schedule_view(self) -> None:
        while self.sched_layout.count():
            child = self.sched_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        m = self.current_member
        now = datetime.now()
        deg_filter = self.sched_degree_combo.currentText()

        # Day resolution
        if self.selected_day_code == "TODAY":
            weekday_map = {0: "T2", 1: "T3", 2: "T4", 3: "T5", 4: "T6", 5: "T7", 6: "CN"}
            target_day = weekday_map[now.weekday()]
        else:
            target_day = self.selected_day_code

        sessions = m.schedule.get(target_day, [])
        if "Đại học" in deg_filter:
            sessions = [s for s in sessions if s.degree_level == "undergrad"]
        elif "Thạc sĩ" in deg_filter:
            sessions = [s for s in sessions if s.degree_level == "master"]

        sessions = sorted(sessions, key=lambda s: s.start_period)

        day_full_names = {"T2": "Thứ Hai", "T3": "Thứ Ba", "T4": "Thứ Tư", "T5": "Thứ Năm", "T6": "Thứ Sáu", "T7": "Thứ Bảy", "CN": "Chủ Nhật"}
        header_text = f"Lịch học <b>{day_full_names.get(target_day, target_day)}</b> — {len(sessions)} môn học"
        h_lbl = QLabel(header_text)
        h_lbl.setStyleSheet("color: #493f35; font-size: 13.5px; font-weight: 650; padding: 4px 0px;")
        self.sched_layout.addWidget(h_lbl)

        if not sessions:
            no_c = QLabel(f"Không có ca học nào trong ngày {day_full_names.get(target_day, target_day)}.")
            no_c.setStyleSheet("color: #71717a; font-size: 12px; padding: 24px; qproperty-alignment: AlignCenter;")
            self.sched_layout.addWidget(no_c)
            self.sched_layout.addStretch()
            return

        for s in sessions:
            st = degree_to_style(s.degree_level)
            from rat.timetable.model import TDTU_PERIODS
            p_start_str = TDTU_PERIODS.get(s.start_period, ("00:00", "00:00", "", ""))[0]
            p_end_str = TDTU_PERIODS.get(s.end_period, ("23:59", "23:59", "", ""))[1]

            card = QFrame()
            card.setObjectName("SchedSessionCard")
            card.setStyleSheet(f"""
                QFrame#SchedSessionCard {{
                    background-color: {st['bg']};
                    border: 1px solid {st['border']};
                    border-radius: 6px;
                    padding: 8px 12px;
                }}
                QLabel {{
                    border: none;
                    background: transparent;
                }}
            """)
            c_layout = QHBoxLayout(card)
            c_layout.setContentsMargins(0, 0, 0, 0)
            c_layout.setSpacing(10)

            badge_lbl = QLabel(st["badge"])
            badge_lbl.setFixedSize(28, 18)
            badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge_lbl.setStyleSheet(f"background-color: {st['tag_bg']}; color: #ffffff; font-size: 9px; font-weight: 700; border-radius: 3px; border: none;")
            c_layout.addWidget(badge_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

            v_info = QVBoxLayout()
            v_info.setSpacing(2)
            c_name = QLabel(f"<b>{s.course_name}</b> ({s.course_code})")
            c_name.setStyleSheet(f"color: {st['text']}; font-size: 13px; font-weight: 600;")
            loc_detail = resolve_room_location(s.room)
            meta = QLabel(f"{p_start_str} - {p_end_str} (Tiết {s.start_period}-{s.end_period}) • Phòng {s.room} ({loc_detail}) • {s.lecturer or 'Chưa rõ'}")
            meta.setStyleSheet("color: #8f9299; font-size: 11px;")
            v_info.addWidget(c_name)
            v_info.addWidget(meta)
            if s.notes:
                n_lbl = QLabel(f"Ghi chú: {s.notes}")
                n_lbl.setStyleSheet("color: #71717a; font-size: 10.5px; font-style: italic;")
                v_info.addWidget(n_lbl)

            c_layout.addLayout(v_info, 1)
            self.sched_layout.addWidget(card)

        self.sched_layout.addStretch()

    def _refresh_club_view(self) -> None:
        while self.club_layout.count():
            child = self.club_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        golden_slots = self.compositor.find_golden_windows(min_ratio=0.8)
        if not golden_slots:
            empty_lbl = QLabel("Chưa tìm thấy khung giờ vàng trên 80% rảnh tuần này.")
            empty_lbl.setStyleSheet("color: #71717a; font-size: 12px; padding: 20px; qproperty-alignment: AlignCenter;")
            self.club_layout.addWidget(empty_lbl)
            self.club_layout.addStretch()
            return

        for slot in golden_slots:
            av = availability_to_color(slot.ratio)
            card = QFrame()
            card.setObjectName("ClubSlotCard")
            card.setStyleSheet(f"""
                QFrame#ClubSlotCard {{
                    background-color: {av['bg']};
                    border: 1px solid {av['border']};
                    border-radius: 6px;
                }}
                QLabel {{
                    border: none;
                    background: transparent;
                }}
            """)
            c_layout = QHBoxLayout(card)
            c_layout.setContentsMargins(10, 8, 10, 8)
            c_layout.setSpacing(10)

            ratio_badge = QLabel(f"{int(slot.ratio * 100)}%")
            ratio_badge.setFixedSize(38, 20)
            ratio_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ratio_badge.setStyleSheet(f"background-color: rgba(52, 211, 153, 0.15); color: {av['text']}; border: 1px solid {av['border']}; font-size: 10px; font-weight: 700; border-radius: 4px;")
            c_layout.addWidget(ratio_badge, 0, Qt.AlignmentFlag.AlignVCenter)

            card.setMinimumHeight(48)
            v_info = QVBoxLayout()
            v_info.setContentsMargins(0, 0, 0, 0)
            v_info.setSpacing(3)
            title = QLabel(f"<b>{slot.day_name}</b> — Tiết {slot.start_period}-{slot.end_period} ({slot.time_range})")
            title.setStyleSheet(f"color: {av['text']}; font-size: 12px; font-weight: 600; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;")
            free_names = ", ".join(slot.free_members) if slot.free_members else "Không có ai"
            desc = QLabel(f"{slot.free_count} trên {slot.total_count} bạn rảnh: {free_names}")
            desc.setStyleSheet("color: #81766b; font-size: 10.5px; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;")
            desc.setWordWrap(True)
            v_info.addWidget(title)
            v_info.addWidget(desc)
            c_layout.addLayout(v_info, 1)

            self.club_layout.addWidget(card)

        self.club_layout.addStretch()

    # -----------------------------------------------------------------
    # SEARCH & CARD INJECTION LOGIC
    # -----------------------------------------------------------------
    def _on_search_text_changed(self) -> None:
        q = self.search_input.text().strip()

        # If user cleared input in another section, auto-return to Home (Chatbot)
        if not q and self.current_section_idx != 0:
            self.switch_section(0)
            return

        # If user is in Files view, trigger search debounce
        if self.current_section_idx == 1:
            self.search_timer.start()

    def _select_file_filter(self, idx: int) -> None:
        self.active_file_filter_idx = idx
        for i, btn in enumerate(self.file_filter_buttons):
            btn.setProperty("active", "true" if i == idx else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._execute_search()

    def _execute_search(self) -> None:
        self.search_timer.stop()
        query = self.search_input.text().strip()
        self.current_query = query
        _, _, exts = FILTER_CATEGORIES[self.active_file_filter_idx]

        self._request_counter += 1
        req_id = self._request_counter
        self.footer_status.setText("Đang tìm...")
        self.search_requested.emit(req_id, query, list(exts) if exts else [])

    @pyqtSlot(int, dict)
    def _on_search_completed(self, request_id: int, response: Dict[str, Any]) -> None:
        if self._chat_file_request is not None and request_id == self._chat_file_request["request_id"]:
            request = self._chat_file_request
            self._chat_file_request = None
            if request["generation"] != self._chat_generation:
                return
            files = response.get("results", [])[:4]
            latency = response.get("latency_ms", (time.time() - request["started_at"]) * 1000.0)
            answer = (
                f"{len(files)} tệp khớp ‘{request['target']}’."
                if files else "Chưa thấy tệp khớp trong chỉ mục. Thử một phần tên hoặc từ khóa khác nhé."
            )
            if response.get("error"):
                answer = "Tìm kiếm chưa hoàn tất. Thử lại sau một chút nhé."
            self.feedback.queries[self.compact_file_list] = request["target"]
            trace_steps = []
            trace = response.get("trace")
            if trace and hasattr(trace, "steps") and trace.steps:
                trace_steps = [f"{s.phase.capitalize()}: {s.thought}" for s in trace.steps]
            elif files:
                trace_steps = [
                    f"Phân rã: Nhận diện từ khóa ‘{request['target']}’",
                    f"Truy xuất: Khai thác FTS5 & Vector đa tầng",
                    f"Kiểm chứng: Đối chiếu {len(files)} tài liệu phù hợp",
                ]

            citations = response.get("citations")
            self._deliver_assistant_reply(
                answer,
                latency_ms=latency,
                strategy="Search",
                inline_files=files,
                citations=citations,
                reasoning_steps=trace_steps,
            )
            self.footer_status.setText(f"{len(files)} tệp")
            return
        try:
            if request_id != self._request_counter:
                return

            results: List[SearchResultItem] = response.get("results", [])
            latency = response.get("latency_ms", 0)
            results = sort_search_results(results, "score")

            q_text = getattr(self, "current_query", "") or self.search_input.text().strip()
            q_lower = q_text.lower()

            # 1. Quick Math Card (safe_calculate)
            calc_expr = None
            if re.search(r"\d", q_text) and any(op in q_text for op in ["+", "*", "/", "%", "^", " - "]):
                calc_expr = re.sub(r"^(?:tính|tinh|calc|calculate|\=)\s*", "", q_text, flags=re.I).strip()
            elif re.match(r"^(?:tính|tinh|calc)\s+([0-9\.\+\-\*\/\(\)\s\^]+)$", q_text, flags=re.I):
                m = re.match(r"^(?:tính|tinh|calc)\s+([0-9\.\+\-\*\/\(\)\s\^]+)$", q_text, flags=re.I)
                if m:
                    calc_expr = m.group(1).strip()

            if calc_expr:
                try:
                    try:
                        from rat.engine.meta_reasoner import safe_calculate
                    except ImportError:
                        from reasoning_strategies import safe_calculate
                    res_str = safe_calculate(calc_expr)
                    if res_str and "Lỗi" not in res_str and res_str != "None":
                        calc_item = SearchResultItem(
                            file_path=f"rat://calc_copy/{res_str}",
                            file_name=f"Kết quả tính toán: {res_str}",
                            file_ext=".calc",
                            file_size=0,
                            modified_at=time.time(),
                            score=2000.0,
                            explanation="Tính toán tức thì • Nhấn ↵ để sao chép kết quả",
                            snippet=f"Biểu thức: {calc_expr} = {res_str}\nNhấn Enter để sao chép số này vào clipboard.",
                        )
                        results.insert(0, calc_item)
                except Exception as e:
                    logger.debug(f"Calc card error: {e}")

            # 2. Campus Room Guide Card (TDTU Tân Phong)
            room_match = re.search(r"\b([A-Fa-fCcFf]\d{3}|TRET-NTD-2)\b", q_text)
            if room_match:
                try:
                    rm = room_match.group(1).upper()
                    loc = resolve_room_location(rm)
                    room_item = SearchResultItem(
                        file_path=f"rat://room_location/{rm}",
                        file_name=f"Vị trí phòng {rm}: {loc}",
                        file_ext=".map",
                        file_size=0,
                        modified_at=time.time(),
                        score=1800.0,
                        explanation="Cơ sở Tân Phong, ĐH Tôn Đức Thắng • Nhấn ↵ để xem lịch học",
                        snippet=f"Phòng {rm} tọa lạc tại {loc}.\nNhấn Enter để chuyển sang xem lịch học chi tiết.",
                    )
                    results.insert(0, room_item)
                except Exception as e:
                    logger.debug(f"Room card error: {e}")

            # 3. Live Agenda / Today's Schedule Card
            agenda_kw = ["hôm nay", "hom nay", "chiều nay", "chieu nay", "sáng nay", "sang nay", "tối nay", "toi nay", "tiết sau", "lịch học", "lich hoc", "tkb"]
            if any(k in q_lower for k in agenda_kw):
                try:
                    agenda = self.compositor.get_today_agenda(self.current_member)
                    c_count = len(agenda)
                    if c_count > 0:
                        first_c = agenda[0]
                        first_s = first_c["session"]
                        deg = "[ThS]" if first_s.degree_level == "master" else "[ĐH]"
                        ag_snip = f"Hôm nay ({self.current_member.name}) có {c_count} ca học: [{first_c['start_time']} - {first_c['end_time']}] {deg} {first_s.course_name} (Phòng {first_s.room}) • {first_c['countdown']}"
                    else:
                        ag_snip = f"Hôm nay ({self.current_member.name}) không có ca học nào trên TKB. Bạn đang hoàn toàn rảnh!"

                    ag_item = SearchResultItem(
                        file_path="rat://goto_schedule",
                        file_name=f"Lịch học hôm nay: {c_count} ca học ({self.current_member.name})",
                        file_ext=".app",
                        file_size=0,
                        modified_at=time.time(),
                        score=1500.0,
                        explanation="Nhấn ↵ để xem chi tiết trên thẻ Thời khóa biểu",
                        snippet=ag_snip,
                    )
                    results.insert(0, ag_item)
                except Exception as e:
                    logger.debug(f"Agenda card error: {e}")

            # 4. Club Golden Slot Card
            if any(k in q_lower for k in ["ai rảnh", "ai ranh", "clb", "golden slot", "họp nhóm"]):
                club_item = SearchResultItem(
                    file_path="rat://goto_club",
                    file_name="Khung Giờ Vàng CLB & Ai Đang Rảnh",
                    file_ext=".app",
                    file_size=0,
                    modified_at=time.time(),
                    score=1400.0,
                    explanation="Nhấn ↵ để mở ma trận giờ rảnh CLB",
                    snippet="Tìm khung giờ vàng họp nhóm và kiểm tra ai rảnh theo từng ca học.",
                )
                results.insert(0, club_item)

            # 5. Dynamic RL Reasoning Meta-Controller Card (CoT, PAL, ESCALATE)
            from rat.engine.meta_reasoner import meta_reasoner
            if meta_reasoner.is_reasoning_query(q_text):
                try:
                    r_res = meta_reasoner.solve(q_text)
                    reason_item = SearchResultItem(
                        file_path=f"rat://reasoning_copy/{r_res.answer}",
                        file_name=f"Suy luận AI: {r_res.badge}",
                        file_ext=".ai",
                        file_size=0,
                        modified_at=time.time(),
                        score=2500.0,
                        explanation=f"Định tuyến bởi Meta-Controller RL ({r_res.strategy}) • Nhấn ↵ để sao chép đáp án",
                        snippet=f"{r_res.answer}\n\n[Chiến lược: {r_res.strategy} | Độ tự tin: {int(r_res.confidence*100)}% | Tiêu thụ: {r_res.tokens} tokens]",
                    )
                    results.insert(0, reason_item)

                    # Provide structured reasoning steps to preview panel
                    from rat.engine.reasoning_trace import ReasoningTrace
                    r_trace = ReasoningTrace(raw_query=q_text)
                    for s_idx, s_txt in enumerate(r_res.steps):
                        r_trace.add_step(
                            phase="reason",
                            thought=s_txt,
                            action=f"execute_{r_res.strategy.lower()}",
                            observation="Hoàn tất suy luận qua Meta-Controller",
                            evaluation=f"Độ tự tin: {int(r_res.confidence*100)}%",
                            latency_ms=round(r_res.latency_ms / max(len(r_res.steps), 1), 2),
                        )
                    r_trace.finalize(confidence=r_res.confidence, is_sufficient=True)
                    response["reasoning_trace"] = r_trace
                except Exception as e:
                    logger.debug(f"Reasoning card error: {e}")

            self.result_list.clear()

            for item in results:
                list_item = QListWidgetItem(self.result_list)
                list_item.setData(Qt.ItemDataRole.UserRole, item)
                self.result_list.addItem(list_item)

            trace = response.get("reasoning_trace")
            self.feedback.refresh(
                self.result_list, response.get("query", self.current_query),
                response.get("parsed_context", {}),
                response.get("latency_ms"),
            )
            plan = response.get("plan")
            self.preview_panel.set_reasoning_trace(trace, plan)

            cot_badge = "  •  Có lời giải từng bước" if trace and trace.steps else ""
            if results:
                self.result_list.setCurrentRow(0)
                self.footer_status.setText(f"Tìm thấy {len(results)} tệp{cot_badge}")
            else:
                self.preview_panel.set_item(None)
                query_hint = f" cho '{q_text}'" if q_text else ""
                self.footer_status.setText(f"Chưa thấy tệp nào{query_hint}. Thử từ khóa khác nhé.{cot_badge}")
        except Exception as e:
            logger.error(f"Error handling search completed in Omnibar: {e}", exc_info=True)

    def _on_result_selected(self, row: int) -> None:
        try:
            item = self.result_list.item(row)
            if item:
                search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
                q_text = getattr(self, "current_query", "") or self.search_input.text().strip()
                self.preview_panel.set_item(search_item, query=q_text)
                if getattr(search_item, "file_ext", "") == ".ai":
                    self.preview_panel.set_active_tab(1)
            else:
                self.preview_panel.set_item(None)
        except Exception as e:
            logger.error(f"Error handling result selected: {e}", exc_info=True)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        self._activate_current_item()

    # -----------------------------------------------------------------
    # ITEM ACTIVATION & KEYBOARD NAVIGATION
    # -----------------------------------------------------------------
    def _is_list_focused(self) -> bool:
        return self.result_list.hasFocus() or self.recent_list.hasFocus() or self.compact_file_list.hasFocus()

    def _active_file_list(self) -> QListWidget:
        if self.current_section_idx == 0 and self.compact_file_list.isVisible() and self.compact_file_list.count():
            return self.compact_file_list
        return self.result_list if self.current_section_idx == 1 else self.recent_list

    def navigate_active_list(self, delta: int) -> None:
        active_list = self._active_file_list()
        count = active_list.count()
        if count == 0:
            return
        curr = active_list.currentRow()
        new_row = max(0, min(count - 1, curr + delta))
        active_list.setCurrentRow(new_row)

    def _activate_current_item(self) -> None:
        active_list = self._active_file_list()
        curr_row = active_list.currentRow()
        item = active_list.item(curr_row)
        if not item:
            return

        search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
        if not search_item:
            return

        fp = getattr(search_item, "file_path", "")

        # Virtual URIs routing
        if fp.startswith("rat://calc_copy/"):
            val = fp.split("rat://calc_copy/", 1)[1]
            QApplication.clipboard().setText(val)
            self.show_toast(f"Đã sao chép kết quả: {val}")
            return
        elif fp.startswith("rat://reasoning_copy/"):
            val = fp.split("rat://reasoning_copy/", 1)[1]
            QApplication.clipboard().setText(val)
            self.show_toast("Đã sao chép câu trả lời suy luận vào clipboard.")
            return
        elif fp == "rat://goto_schedule" or fp.startswith("rat://room_location"):
            self.switch_section(2)
            return
        elif fp == "rat://goto_club":
            self.switch_section(3)
            return

        # Real file path
        self.feedback.perform("open", search_item, open_file_default)

    def _reveal_current_in_finder(self) -> None:
        active_list = self._active_file_list()
        curr_row = active_list.currentRow()
        item = active_list.item(curr_row)
        if item:
            search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
            if search_item:
                self.feedback.perform("reveal", search_item, reveal_in_finder)

    def _open_current_in_terminal(self) -> None:
        active_list = self._active_file_list()
        curr_row = active_list.currentRow()
        item = active_list.item(curr_row)
        if item:
            search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
            if search_item:
                self.feedback.perform("terminal", search_item, open_in_terminal)
                self.show_toast(f"💻 Đã mở Terminal: {search_item.file_name}")

    def _preview_quick_look(self) -> None:
        active_list = self._active_file_list()
        curr_row = active_list.currentRow()
        if curr_row < 0 and active_list.count() > 0:
            curr_row = 0
            active_list.setCurrentRow(0)
        item = active_list.item(curr_row)
        if item:
            search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
            if search_item:
                opened = trigger_quicklook(search_item.file_path)
                if opened:
                    self.show_toast(f"👁️ QuickLook: {search_item.file_name}")

    def _copy_current_path(self) -> None:
        active_list = self._active_file_list()
        curr_row = active_list.currentRow()
        item = active_list.item(curr_row)
        if item:
            search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
            cb = QApplication.clipboard()
            if cb and search_item:
                cb.setText(search_item.file_path)
                self.show_toast(f"✓ Đã sao chép đường dẫn: {search_item.file_name}")

    def _copy_current_content(self) -> None:
        active_list = self._active_file_list()
        curr_row = active_list.currentRow()
        item = active_list.item(curr_row)
        if item:
            search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
            if search_item:
                from rat.crawler.extractors import extract_document_content
                text = extract_document_content(search_item.file_path)
                cb = QApplication.clipboard()
                if cb:
                    cb.setText(text)
                    self.show_toast(f"✓ Đã chép nội dung ({len(text)} ký tự)")

    # -------------------------------------------------------------
    # CHATBOT & QUICK HELPERS
    # -------------------------------------------------------------
    def _refresh_notes_surface(self) -> None:
        self.notebook_pane.refresh()
        if hasattr(self, "chat_stream"):
            self.chat_stream.refresh_turn_notes(self.assistant_runtime.notebook)

    def _on_turn_note_edited(self, note_id: str, revision: int, new_text: str) -> None:
        try:
            self.assistant_runtime.notebook.user_edit(note_id, revision, new_text)
        except ValueError as exc:
            if hasattr(self, "chat_stream"):
                for handle in self.chat_stream._turn_handles.values():
                    pane = handle.get("turn_notes")
                    if pane and note_id in pane.rows:
                        row = pane.rows[note_id]
                        row.error_label.setText(str(exc))
                        row.error_label.show()
            return
        if hasattr(self, "chat_stream"):
            for handle in self.chat_stream._turn_handles.values():
                pane = handle.get("turn_notes")
                if pane and note_id in pane.rows:
                    pane.rows[note_id]._cancel_edit()
        self._refresh_notes_surface()
        self.companion_avatar_btn.react("noting")

    def _on_turn_note_removed(self, note_id: str, revision: int) -> None:
        try:
            self.assistant_runtime.notebook.remove(note_id, revision)
        except ValueError as exc:
            self.show_toast(str(exc), 6000)
            return
        self._refresh_notes_surface()

    def _on_turn_note_restored(self, note_id: str) -> None:
        try:
            self.assistant_runtime.notebook.restore(note_id)
        except ValueError as exc:
            self.show_toast(str(exc), 6000)
            return
        self._refresh_notes_surface()
        self.companion_avatar_btn.react("happy")

    def _on_turn_note_confirmed(self, note_id: str) -> None:
        try:
            self.assistant_runtime.notebook.confirm(note_id)
        except ValueError as exc:
            self.show_toast(str(exc), 6000)
            return
        self._refresh_notes_surface()
        self.companion_avatar_btn.react("done")

    def _complete_chat_turn(self, answer: str, *, handle=None, response=None) -> None:
        if self._pending_chat_query is not None:
            turn_ref = handle.get("turn_ref") if isinstance(handle, dict) else None
            exec_id = handle.get("execution_id") if isinstance(handle, dict) else None
            art_refs = [
                {"id": a.id, "kind": a.kind, "revision": a.revision, "title": a.title}
                for a in (getattr(response, "artifacts", []) or [])
            ] if response else []
            note_ids = [
                e.get("note_id")
                for e in (getattr(response, "note_events", []) or [])
                if isinstance(e, dict) and e.get("note_id")
            ] if response else []
            if turn_ref is not None:
                self._conversation.complete_turn(
                    turn_ref.turn_id,
                    answer,
                    execution_id=exec_id,
                    artifact_refs=art_refs,
                    note_ids=note_ids,
                    reconciliation=getattr(response, "reconciliation", None),
                    turn_contract=getattr(response, "turn_contract", None),
                )
            else:
                self._conversation.add_turn(self._pending_chat_query, answer)
            self._pending_chat_query = None

    def _deliver_assistant_reply(
        self,
        answer: str,
        latency_ms: float = 0.0,
        strategy: str = "Direct",
        confidence: float = 1.0,
        reasoning_steps: Optional[List[str]] = None,
        custom_widget: Optional[QWidget] = None,
        strategy_badge: Optional[str] = None,
        inline_files: Optional[List[Any]] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Deliver a completed reply into the persistent conversation viewport.
        """
        self._complete_chat_turn(answer)
        self._set_compact_files(inline_files)
        context_str = {
            "Search": "Tìm tệp", "Math": "Tính nhanh", "Timetable": "Lịch học",
            "CampusMap": "Phòng học", "Club-Matrix": "Giờ rảnh", "Direct": "Trả lời",
            "PAL": "Kiểm chứng (PAL)", "CoT": "Quy chế",
        }.get(strategy, "Trả lời")
        self._present_compact_reply(
            answer, context_str, has_details=bool(custom_widget), file_summary=bool(inline_files)
        )
        if hasattr(self, "workbench_user_lane"):
            self.workbench_user_lane.set_phase("done")
        if hasattr(self, "workbench_canvas"):
            self.workbench_canvas.set_work(
                self._last_assistant_query or context_str,
                status="Đã xong",
            )
        if getattr(self, "workbench_scene_enabled", False) and hasattr(self, "workbench_scene"):
            proj = self.workbench_scene.projector
            proj.query = self._last_assistant_query or context_str
            proj.phase = "done"
            proj.phase_label = "Đã xong"
            proj.actor_state = "done"
            proj.rat_speech = sanitize_public_text(answer, max_chars=240) or "Đã xong kết quả."
            proj.result_node = SceneResultNode(
                node_id=f"reply:{self._chat_generation}",
                title=self._last_assistant_query or context_str,
                answer_text=sanitize_public_text(answer, max_chars=2000),
                status="ready",
                status_label="Đã xong",
            )
            self.workbench_scene._render_snapshot(animate=True)
            self._sync_workbench_scene()
        self.speech_bubble.context_pill.setToolTip(f"{strategy} · {latency_ms:.0f} ms")

        if hasattr(self, "chat_stream"):
            try:
                self._latest_assistant_handle = self.chat_stream.add_assistant_message(
                    answer=answer,
                    reasoning_steps=reasoning_steps,
                    latency_ms=latency_ms,
                    strategy=strategy,
                    confidence=confidence,
                    custom_widget=custom_widget,
                    inline_files=inline_files,
                    citations=citations,
                )
            except Exception as e:
                logger.debug(f"Chat stream add error: {e}")
        if hasattr(self, "compact_cot"):
            if reasoning_steps:
                self.compact_cot.set_steps(
                    reasoning_steps,
                    latency_ms=latency_ms,
                    confidence=confidence,
                    strategy=strategy,
                )
            else:
                self.compact_cot.clear()
        self._sync_compact_surface()

        if getattr(self, "rat_stage", None):
            self.rat_stage.set_state("idle")
        if getattr(self, "set_mascot_state", None) and getattr(self, "_mascot_state", "idle") != "angry":
            self.set_mascot_state("idle")

    def _reset_chat(self) -> None:
        self._interaction_surface_active = False
        self._selected_document_path = None
        self._chat_generation += 1
        self._conversation.clear()
        self._assistant_sources = []
        self._assistant_task_state = {}
        self._assistant_handle = None
        self._pending_chat_query = None
        self._chat_file_request = None
        self._request_counter += 1
        if self._current_reasoner is not None:
            self._current_reasoner.requestInterruption()
            self._current_reasoner = None
        if self._artifact_worker is not None:
            self._artifact_worker.requestInterruption()
            self._artifact_worker = None
        if hasattr(self, "assistant_runtime") and hasattr(self.assistant_runtime, "artifact_store"):
            self.assistant_runtime.dispatcher.reset()
        self._latest_assistant_handle = None
        self._surface_scroll.clear()
        self.assistant_runtime.notebook.clear()
        self.notebook_pane.set_open(False, animate=False)
        self.notebook_pane.refresh()
        if hasattr(self, "chat_stream"):
            self.chat_stream.clear_chat()
        if hasattr(self, "compact_cot"):
            self.compact_cot.clear()
        self._set_compact_files(None)
        self.set_expanded(self.is_expanded)
        self.set_mascot_idle()
        if hasattr(self, "speech_bubble"):
            self.speech_bubble.reset_welcome()
        if hasattr(self, "workbench_speech_bubble"):
            self.workbench_speech_bubble.reset_welcome()
        if hasattr(self, "workbench_canvas"):
            self.workbench_canvas.reset_work()
        if hasattr(self, "workbench_scene"):
            self.workbench_scene.reset()
        if hasattr(self, "workbench_user_lane"):
            self.workbench_user_lane.set_phase("idle")
            self.workbench_user_lane.set_last_user_query("")
        self.search_input.clear()
        if hasattr(self, "chat_composer_input"):
            self.chat_composer_input.clear()
        if getattr(self, "workbench_finder_enabled", False):
            if getattr(self, "_finder_coordinator", None) is not None:
                self._finder_coordinator.cancel()
            self._finder_selected_id = None
            if getattr(self, "workbench_scene_enabled", False) and hasattr(self, "workbench_scene"):
                self.workbench_scene.clear_finder_snapshot()
        self.switch_section(0)
        self.show_toast("Đã làm mới phiên chat")

    def _select_document_question(self, item):
        if not Path(item.file_path).is_absolute():
            self.show_toast('Chọn một tệp trong chỉ mục để hỏi nội dung.')
            return
        if self._pending_chat_query is not None or self._artifact_worker is not None:
            self.show_toast('Chờ câu trả lời hiện tại hoặc dừng trước khi chọn tệp khác.')
            return
        self._selected_document_path = item.file_path
        self._show_interaction_surface()
        self._sync_compact_surface()
        self.chat_composer_input.setFocus()
        self.show_toast(f'Đang hỏi về {item.file_name}. Nhập câu hỏi trong ô chat.')

    def _on_selected_document_question(self, file_path, file_name, question):
        # This signal is an explicit question about the displayed selection;
        # ordinary chat is never routed by filename/topic keyword matching.
        self._submit_chat_prompt(question, selected_document_path=file_path)

    def _submit_chat_prompt(self, query: str, *, selected_document_path=None) -> None:
        q = query.strip()
        if not q:
            return

        from rat.ui.workbench import is_expand_command, is_collapse_command, is_stop_command
        if is_expand_command(q):
            if hasattr(self, "chat_composer_input") and self.chat_composer_input.text().strip() == q:
                self.chat_composer_input.clear()
            self.set_expanded(True)
            return
        if is_collapse_command(q):
            if hasattr(self, "chat_composer_input") and self.chat_composer_input.text().strip() == q:
                self.chat_composer_input.clear()
            self.set_expanded(False)
            return

        if getattr(self, "workbench_scene_enabled", False) and hasattr(self, "workbench_scene"):
            if self.workbench_scene.try_handle_scene_command(q):
                if hasattr(self, "chat_composer_input") and self.chat_composer_input.text().strip() == q:
                    self.chat_composer_input.clear()
                self._sync_workbench_scene()
                self._sync_compact_surface()
                return

        # Control of an active execution is independent of model/domain routing.
        if self._pending_chat_query is not None and is_stop_command(q):
            self._cancel_assistant()
            if self.chat_composer_input.text().strip() == q:
                self.chat_composer_input.clear()
            return
        if self._pending_chat_query is not None or self._artifact_worker is not None:
            # Keep a second draft intact rather than interleaving unfinished turns.
            self.footer_status.setText("Đang trả lời câu trước. Câu đang gõ vẫn được giữ.")
            return

        self._apply_assistant_model()
        selected_document_path = selected_document_path or self._selected_document_path
        self._selected_document_path = None
        self._pending_chat_query = q
        self._last_assistant_query = q
        self._set_compact_files(None)
        if getattr(self, "workbench_finder_enabled", False):
            if getattr(self, "_finder_coordinator", None) is not None:
                self._finder_coordinator.cancel()
            self._finder_selected_id = None
            if getattr(self, "workbench_scene_enabled", False) and hasattr(self, "workbench_scene"):
                self.workbench_scene.clear_finder_snapshot()

        if hasattr(self, "workbench_user_lane"):
            self.workbench_user_lane.set_last_user_query(q)
            self.workbench_user_lane.set_phase("working")
        if hasattr(self, "workbench_canvas"):
            self.workbench_canvas.set_work(q, status="Đang xử lý")

        if self.current_section_idx != 0:
            self.switch_section(0)

        # Keep one conversation surface for requests and their sources.
        self.set_mascot_state("thinking", "Chuột · Suy nghĩ...")
        self.speech_bubble.set_reply("Đang suy nghĩ…", "Đang nghĩ", copy_text="")
        if hasattr(self, "workbench_speech_bubble"):
            self.workbench_speech_bubble.set_reply("Đang suy nghĩ…", "Đang nghĩ", copy_text="")
        if hasattr(self, "compact_cot"):
            self.compact_cot.clear()

        history_messages = self._conversation.messages_with_turn_ids()
        turn_references = self._conversation.turn_references()
        turn_snap = self._conversation.begin_turn(q)
        turn_ref = turn_snap.turn_ref
        execution_id = turn_snap.execution_id

        self.chat_stream.add_user_message(q, turn_id=turn_ref.turn_id)
        self.search_input.clear()
        if hasattr(self, "chat_composer_input"):
            self.chat_composer_input.clear()
        self._sync_compact_surface()
        if hasattr(self, "return_keycap"):
            self.return_keycap.setProperty("active", "false")
            self.return_keycap.style().unpolish(self.return_keycap)
            self.return_keycap.style().polish(self.return_keycap)
        self._show_interaction_surface()
        handle = self.chat_stream.create_streaming_message(
            strategy="Assistant", badge="Đang xử lý", turn_id=turn_ref.turn_id
        )
        handle["generation"] = self._chat_generation
        handle["turn_ref"] = turn_ref
        handle["execution_id"] = execution_id
        handle["observed_sources"] = list(self._assistant_sources)
        handle['selected_document_path'] = selected_document_path
        self._carry_work_results(handle)
        handle["work_trace"].set_status("Đã nhận việc")
        self._assistant_handle = handle
        if getattr(self, "workbench_scene_enabled", False) and hasattr(self, "workbench_scene"):
            self.workbench_scene.begin_turn(
                q,
                generation=self._chat_generation,
                execution_id=execution_id,
                turn_id=turn_ref.turn_id,
                previous_sources=list(self._assistant_sources),
                previous_artifacts=list(handle.get("artifacts", {}).values()),
                artifact_store=self.assistant_runtime.artifact_store,
            )
            self._sync_workbench_scene()
        from rat.ui.assistant_worker import AssistantWorker
        worker = AssistantWorker(
            self.assistant_runtime, q, history=history_messages,
            previous_sources=list(self._assistant_sources), member_id=self.current_member.id,
            task_state=dict(self._assistant_task_state),
            turn_ref=turn_ref, execution_id=execution_id, turn_references=turn_references,
            document_path=selected_document_path,
            parent=QApplication.instance(),
        )
        self._current_reasoner = worker
        self._reasoning_workers.add(worker)
        worker.progress_changed.connect(lambda status, h=handle: self._on_assistant_progress(h, status))
        worker.step_completed.connect(lambda step, h=handle: self._on_assistant_step(h, step))
        worker.response_ready.connect(lambda result, h=handle: self._on_assistant_response(h, result))
        worker.finished.connect(lambda w=worker: self._on_chat_worker_finished(w))
        worker.finished.connect(worker.deleteLater)
        worker.start()
        self._sync_compact_surface()

    def _on_assistant_progress(self, handle, status):
        if getattr(self, "workbench_scene_enabled", False) and hasattr(self, "workbench_scene"):
            self.workbench_scene.on_progress(
                status,
                generation=handle.get("generation", -1),
                execution_id=handle.get("execution_id", ""),
            )
            self._sync_workbench_scene()
        if handle.get("generation") != self._chat_generation or handle is not self._assistant_handle:
            return
        handle["status_lbl"].setText(status)
        self.footer_status.setText(status)
        self.speech_bubble.set_reply(status, "Đang xử lý", copy_text="")
        if hasattr(self, "workbench_speech_bubble"):
            self.workbench_speech_bubble.set_reply(status, "Đang xử lý", copy_text="")
        handle["work_trace"].set_status(status)

    def _on_assistant_step(self, handle, step):
        if getattr(self, "workbench_scene_enabled", False) and hasattr(self, "workbench_scene"):
            self.workbench_scene.on_step(
                step,
                generation=handle.get("generation", -1),
                execution_id=handle.get("execution_id", ""),
                artifact_store=self.assistant_runtime.artifact_store,
            )
            self._sync_workbench_scene()
        if handle.get("generation") != self._chat_generation or handle is not self._assistant_handle:
            return
        handle["work_trace"].add_step(step)
        self._refresh_notes_surface()
        if isinstance(step.tool_result, dict) and step.tool_result.get('notes_updated'):
            self.companion_avatar_btn.set_state('noting')
        from rat.engine.assistant_runtime import observed_sources
        from rat.ui.assistant_presenter import document_cards, source_panel
        sources = observed_sources(step, handle["observed_sources"])
        task_updated = step.tool_name == "update_task_state" and isinstance(step.tool_result, dict) and "task_state" in step.tool_result
        if task_updated:
            handle["task_state"] = step.tool_result["task_state"]
        if getattr(step, "artifacts", None):
            handle.setdefault("artifacts", {}).update({a.id: a for a in step.artifacts})
        selection_updated = isinstance(step.tool_result, dict) and 'result_refs' in step.tool_result
        if selection_updated:
            self._update_work_results(handle)
        else:
            self._update_work_results(handle, getattr(step, 'artifacts', []))
        if sources == handle["observed_sources"] and not task_updated and not getattr(step, "artifacts", None) and not selection_updated:
            return
        handle["observed_sources"] = sources
        if getattr(self, "workbench_scene_enabled", False) and hasattr(self, "workbench_scene"):
            return
        self.chat_stream.update_source_cards(
            handle,
            inline_files=document_cards(self._work_sources(sources)),
            custom_widget=source_panel(
                self._work_sources(sources),
                self.open_natal_chart,
                handle.get("task_state"),
                artifacts=list(handle.get("artifacts", {}).values()),
                registry=self.assistant_runtime.registry,
                on_action=self._on_action_dispatched,
                on_input=self._on_input_submitted,
                on_question=self._select_document_question,
            ),
        )

    def _on_assistant_response(self, handle, response):
        if getattr(self, "workbench_scene_enabled", False) and hasattr(self, "workbench_scene"):
            if handle.get("generation") != self._chat_generation or handle is not self._assistant_handle:
                self.workbench_scene.on_response(
                    response,
                    generation=handle.get("generation", -1),
                    execution_id=handle.get("execution_id", ""),
                    artifact_store=self.assistant_runtime.artifact_store,
                    pending_input_request=self.assistant_runtime.dispatcher.state.pending_input_request,
                )
                return
        if handle.get("generation") != self._chat_generation or handle is not self._assistant_handle:
            return
        failed = bool(response.error)
        handle["work_trace"].finish(response)
        self._refresh_notes_surface()
        turn_ref = handle.get("turn_ref")
        exec_id = handle.get("execution_id")
        art_refs = [{"artifact_id": a.id, "revision": a.revision} for a in getattr(response, "artifacts", [])]
        note_ids = [
            e["note_id"]
            for e in (getattr(response, "note_events", []) or [])
            if isinstance(e, dict) and e.get("note_id")
        ]
        rec = getattr(response, "reconciliation", None)
        if failed:
            if turn_ref is not None:
                if response.error == "cancelled":
                    self._conversation.cancel_turn(
                        turn_ref.turn_id,
                        execution_id=exec_id,
                        artifact_refs=art_refs,
                        note_ids=note_ids,
                        reconciliation=rec,
                        turn_contract=getattr(response, 'turn_contract', None),
                    )
                else:
                    self._conversation.fail_turn(
                        turn_ref.turn_id,
                        error=response.error or "failed",
                        execution_id=exec_id,
                        artifact_refs=art_refs,
                        note_ids=note_ids,
                        reconciliation=rec,
                        turn_contract=getattr(response, 'turn_contract', None),
                    )
            else:
                self._conversation.add_attempt(self._pending_chat_query or self._last_assistant_query,
                                               'cancelled' if response.error == 'cancelled' else 'failed')
            self._pending_chat_query = None
            if response.error == "cancelled":
                answer = "Đã dừng. Bạn có thể đổi yêu cầu hoặc hỏi tiếp."
            elif response.error in {"token_budget_exhausted", "step_budget_exhausted", "controller_finish_refused", "completion_unresolved"}:
                answer = ("Mình chưa hoàn tất yêu cầu trong lượt này. Các nguồn đã tìm được vẫn ở bên dưới; bạn có thể hỏi tiếp về một nguồn."
                          if response.sources else "Mình chưa hoàn tất yêu cầu trong lượt này. Bạn có thể thu hẹp yêu cầu hoặc thử lại.")
            elif response.error == "verification_failed":
                answer = "Mình phát hiện kết luận chưa khớp khi đối chiếu và chưa sửa xong trong lượt này. Bạn có thể xem các bước kiểm tra hoặc thử lại."
            elif response.error == 'selected_document_read_failed':
                answer = 'Không đọc lại được tệp đã chọn. Hãy tìm và chọn lại tệp trong chỉ mục.'
            elif response.error == 'selected_document_no_text':
                answer = 'Phần đã đọc của tệp không có văn bản để trả lời câu hỏi.'
            elif response.error in {'selected_document_context_too_large', 'invalid_selected_document_question'}:
                answer = 'Hãy chọn một tệp và rút gọn câu hỏi để vừa giới hạn đọc.'
            elif response.error in {"verification_unresolved", "invalid_verified_answer_format"}:
                answer = "Mình chưa đối chiếu được kết luận trong lượt này. Bạn có thể ghi rõ biểu thức cần tính hoặc xem các bước kiểm tra."
            else:
                answer = "Mình chưa trả lời được lượt này. Bạn có thể thử lại hoặc kiểm tra Ollama trong Cài đặt."
            if response.pending_input_request is not None and not self.debug_ui:
                answer = response.pending_input_request.prompt
            self.footer_status.setText("Chưa hoàn tất")
        elif response.pending_input_request is not None:
            # The primary path answers in the composer; developer forms are optional.
            answer = '' if self.debug_ui else (response.answer or response.pending_input_request.prompt)
            if turn_ref is not None:
                self._conversation.fail_turn(
                    turn_ref.turn_id,
                    "needs_input",
                    execution_id=exec_id,
                    artifact_refs=art_refs,
                    note_ids=note_ids,
                    reconciliation=rec,
                    partial_answer=response.answer or response.pending_input_request.prompt,
                    task_state=response.task_state if response.task_state_updated else None,
                    turn_contract=getattr(response, 'turn_contract', None),
                )
            else:
                self._conversation.add_attempt(self._pending_chat_query or self._last_assistant_query, 'needs_input')
            self._pending_chat_query = None
            self.footer_status.setText("Cần thêm thông tin")
        else:
            answer = response.answer
            self._complete_chat_turn(answer, handle=handle, response=response)
            self.footer_status.setText("Đã trả lời · có thể hỏi tiếp")
        self._current_reasoner = None
        self._assistant_handle = None
        self._assistant_sources = list(response.sources or self._assistant_sources)[-12:]
        if response.task_state_updated:
            self._assistant_task_state = dict(response.task_state)
        self._latest_assistant_handle = handle
        if response.artifacts:
            handle.setdefault("artifacts", {}).update({a.id: a for a in response.artifacts})
        self._update_work_results(handle, response.artifacts if not self.assistant_runtime.notebook.selection_set else [])
        from rat.ui.assistant_presenter import document_cards, source_panel
        files = document_cards(self._work_sources(self._assistant_sources))
        if getattr(self, "workbench_scene_enabled", False) and hasattr(self, "workbench_scene"):
            agenda = None
        else:
            agenda = source_panel(
                self._work_sources(self._assistant_sources),
                self.open_natal_chart,
                response.task_state if response.task_state_updated else None,
                artifacts=list(handle.get("artifacts", {}).values()),
                registry=self.assistant_runtime.registry,
                on_action=self._on_action_dispatched,
                on_input=self._on_input_submitted,
                on_question=self._select_document_question,
            )
        handle["full_text"] = answer
        handle["badge_lbl"].setText("· Chưa hoàn tất" if failed else "· Chuột")
        handle["card"].setToolTip(f"Thời gian xử lý: {response.total_time_ms / 1000:.1f} giây")
        self.chat_stream.finalize_stream(
            handle, latency_ms=response.total_time_ms, inline_files=files,
            custom_widget=agenda, retry_prompt=self._last_assistant_query if failed and not handle.get('selected_document_path') else None,
        )
        if getattr(self, "workbench_scene_enabled", False) and hasattr(self, "workbench_scene"):
            self.workbench_scene.on_response(
                response,
                generation=handle.get("generation", -1),
                execution_id=handle.get("execution_id", ""),
                artifact_store=self.assistant_runtime.artifact_store,
                pending_input_request=self.assistant_runtime.dispatcher.state.pending_input_request,
            )
            self._sync_workbench_scene()
        self._set_compact_files(files)
        self._present_compact_reply(
            answer,
            "Chưa hoàn tất" if failed else "Trả lời",
            has_details=bool(agenda or getattr(self, "workbench_scene_enabled", False)),
        )
        if hasattr(self, "workbench_user_lane"):
            self.workbench_user_lane.set_phase("error" if failed else "done")
        if hasattr(self, "workbench_canvas"):
            title = self._last_assistant_query or "Không gian làm việc"
            if getattr(response, "artifacts", None):
                for art in response.artifacts:
                    fn = getattr(art, "payload", {}).get("filename")
                    if fn:
                        title = fn
                        break
            self.workbench_canvas.set_work(
                title,
                status="Chưa hoàn tất" if failed else "Đã xong",
            )
        self.compact_cot.clear()
        self.set_mascot_idle()
        self._mascot_state = "error" if failed else "idle"
        self._sync_compact_surface()

    def _cancel_assistant(self):
        worker = self._current_reasoner
        if worker is None:
            return
        worker.requestInterruption()
        handle = self._assistant_handle
        cancelled_gen = handle.get("generation", self._chat_generation) if handle else self._chat_generation
        cancelled_exec_id = handle.get("execution_id", "") if handle else ""
        if handle and handle.get("execution_id"):
            self.assistant_runtime.cancel_execution(handle["execution_id"])
        else:
            self.assistant_runtime.notebook.invalidate_pending()
        self._refresh_notes_surface()
        self._chat_generation += 1
        self._current_reasoner = None
        if self._pending_chat_query:
            if handle and handle.get("turn_ref") is not None:
                self._conversation.cancel_turn(
                    handle["turn_ref"].turn_id,
                    execution_id=handle.get("execution_id"),
                )
            else:
                self._conversation.add_attempt(self._pending_chat_query, 'cancelled')
        self._pending_chat_query = None
        self._assistant_handle = None
        if handle:
            handle["work_trace"].set_status("Đã dừng")
            handle["full_text"] = "Đã dừng. Bạn có thể đổi yêu cầu hoặc hỏi tiếp."
            handle["badge_lbl"].setText("· Đã dừng")
            from rat.ui.assistant_presenter import document_cards, source_panel
            sources = handle.get("observed_sources", [])
            if handle.get("task_state"):
                self._assistant_task_state = dict(handle["task_state"])
            self._assistant_sources = list(sources or self._assistant_sources)[-12:]
            if getattr(self, "workbench_scene_enabled", False) and hasattr(self, "workbench_scene"):
                self.chat_stream.finalize_stream(
                    handle,
                    inline_files=document_cards(self._work_sources(sources)),
                    custom_widget=None,
                )
            else:
                self.chat_stream.finalize_stream(
                    handle,
                    inline_files=document_cards(self._work_sources(sources)),
                    custom_widget=source_panel(
                        self._work_sources(sources),
                        self.open_natal_chart,
                        handle.get("task_state"),
                        artifacts=list(handle.get("artifacts", {}).values()),
                        registry=self.assistant_runtime.registry,
                        on_action=self._on_action_dispatched,
                        on_input=self._on_input_submitted,
                        on_question=self._select_document_question,
                    ),
                )
        if getattr(self, "workbench_scene_enabled", False) and hasattr(self, "workbench_scene"):
            self.workbench_scene.on_cancel(
                generation=cancelled_gen,
                execution_id=cancelled_exec_id,
                new_generation=self._chat_generation,
            )
            self._sync_workbench_scene()
        self.footer_status.setText("Đã dừng")
        self.compact_cot.clear()
        self.set_mascot_idle()
        if hasattr(self, "workbench_user_lane"):
            self.workbench_user_lane.set_phase("cancelled")
        if hasattr(self, "workbench_speech_bubble"):
            self.workbench_speech_bubble.set_reply("Đã dừng.", "Đã dừng")
        if hasattr(self, "workbench_canvas"):
            self.workbench_canvas.set_work(
                self._last_assistant_query or "Không gian làm việc",
                status="Đã dừng",
            )
        self._sync_compact_surface()

    def _submit_chat_or_stop(self):
        if self._pending_chat_query is not None:
            self._cancel_assistant()
        else:
            self._submit_chat_prompt(self.chat_composer_input.text())

    def _show_interaction_surface(self):
        self._interaction_surface_active = True
        self.content_stack.show()
        if getattr(self, "workbench_scene_enabled", False) and hasattr(self, "workbench_scene"):
            self.workbench_scene.show()
            self.chat_stream.hide()
        else:
            self.chat_stream.show()
        self._sync_compact_surface()

    def open_natal_chart(self, birth=None):
        self.switch_section(0)
        self._show_interaction_surface()
        if birth is not None:
            from dataclasses import asdict
            values = dict(birth) if isinstance(birth, dict) else asdict(birth)
            self._start_artifact_operation(lambda: self.assistant_runtime.dispatcher.execute_operation("create_natal_chart", values))
        else:
            charts = self.assistant_runtime.artifact_store.find_by_kind("natal_chart")
            if not charts and not self.assistant_runtime.dispatcher.state.pending_input_request:
                self.assistant_runtime.dispatcher.execute_operation("create_natal_chart", {})
            self._refresh_latest_assistant_panel()

    def _artifact_context(self):
        from datetime import datetime
        return {"member_id": self.current_member.id, "now_dt": datetime.now().astimezone(),
                "get_schedule": self.assistant_runtime.tool_get_schedule}

    def _start_artifact_operation(self, callback, *, note_inputs=None):
        if self._pending_chat_query is not None or self._artifact_worker is not None:
            self.show_toast("Chuột đang xử lý. Chờ xong hoặc dừng trước khi thay đổi kết quả.")
            return
        from rat.ui.assistant_worker import ArtifactWorker
        generation = self._chat_generation
        worker = ArtifactWorker(callback, parent=QApplication.instance())
        self._artifact_worker = worker
        self._reasoning_workers.add(worker)
        worker.result_ready.connect(lambda result: self._on_artifact_result(generation, result, note_inputs=note_inputs))
        def finished():
            self._reasoning_workers.discard(worker)
            if self._artifact_worker is worker:
                self._artifact_worker = None
            self._sync_compact_surface()
        worker.finished.connect(finished)
        worker.finished.connect(worker.deleteLater)
        self.footer_status.setText("Đang xử lý…")
        worker.start()
        self._sync_compact_surface()

    def _on_action_dispatched(self, action, user_inputs):
        context = self._artifact_context()
        fields = (action.input_schema or {}).get('properties', {})
        labels = {name: schema.get('label', schema.get('title', name)) for name, schema in fields.items()}
        self._start_artifact_operation(lambda: self.assistant_runtime.dispatcher.dispatch(action, user_inputs, context),
            note_inputs=(action.target_artifact_id, labels, dict(user_inputs)))

    def _on_input_submitted(self, request_id, values):
        context = self._artifact_context()
        pending = self.assistant_runtime.dispatcher.state.pending_input_request
        labels = {item['name']: item.get('label', item['name']) for item in pending.missing_fields} if pending and pending.id == request_id else {}
        self._start_artifact_operation(lambda: self.assistant_runtime.dispatcher.resume_input(request_id, values, context),
            note_inputs=(request_id, labels, dict(values)))

    def _on_artifact_result(self, generation, result, *, note_inputs=None):
        if generation != self._chat_generation:
            return
        if result.status not in ("success", "needs_input"):
            self.footer_status.setText(result.error or "Không thực hiện được thao tác.")
            self.show_toast(result.error or "Không thực hiện được thao tác.", 8000)
            self._append_direct_trace(result)
            if getattr(self, "workbench_scene_enabled", False) and hasattr(self, "workbench_scene"):
                self.workbench_scene.on_artifact_result(result, artifact_store=self.assistant_runtime.artifact_store)
                self._sync_workbench_scene()
            self._mascot_state = 'error'
            self.companion_avatar_btn.set_state('error')
            return
        self.surface_notice.hide()
        if result.artifact:
            from rat.engine.assistant_runtime import AgentStep, observed_sources
            name = result.artifact.provenance.get("operation_name")
            self._assistant_sources = observed_sources(AgentStep(0, "", name, tool_result=result.result), self._assistant_sources)[-12:]
        self.footer_status.setText("Cần thêm thông tin" if result.status == "needs_input" else "Đã cập nhật")
        if result.artifact:
            active = [key for key in self.assistant_runtime.notebook.result_ids()
                if self.assistant_runtime.artifact_store.get(key) is not None]
            if result.artifact.id not in active:
                active.append(result.artifact.id)
            self.assistant_runtime.notebook.select_results(active)
        self._refresh_latest_assistant_panel(result.artifact)
        self._append_direct_trace(result)
        if note_inputs and result.status in ('success', 'needs_input'):
            key, labels, values = note_inputs
            target = result.artifact.id if result.artifact else key
            handle = getattr(self, "_latest_assistant_handle", None)
            turn_ref = handle.get("turn_ref") if isinstance(handle, dict) else None
            if turn_ref is None and isinstance(handle, dict) and handle.get("turn_id"):
                from rat.engine.work_notes import TurnRef
                turn_ref = TurnRef(conversation_id=self._conversation.conversation_id, turn_id=int(handle["turn_id"]), kind="interaction")
            for field, label in labels.items():
                if field in values and values[field] is not None and values[field] != '':
                    value = values[field]
                    value = ('Có' if value else 'Không') if isinstance(value, bool) else str(value)
                    try:
                        self.assistant_runtime.notebook.record_input('input:' + target + ':' + field,
                            label + ': ' + value, source='control:' + target, turn_ref=turn_ref)
                    except ValueError as exc:
                        self.show_toast('Kết quả đã cập nhật. ' + str(exc), 8000)
            self._refresh_notes_surface()
            self.companion_avatar_btn.react('noting')

    def _refresh_latest_assistant_panel(self, changed=None):
        from rat.ui.assistant_presenter import document_cards, source_panel
        handle = getattr(self, "_latest_assistant_handle", None)
        if handle is None:
            handle = self.chat_stream.create_streaming_message(strategy="Assistant", badge="Kết quả")
            handle["full_text"] = ""
            handle["status_lbl"].hide()
            self._latest_assistant_handle = handle
        artifacts = handle.setdefault("artifacts", {})
        if changed:
            artifacts[changed.id] = changed
        elif not artifacts:
            artifacts.update({a.id: a for a in self.assistant_runtime.artifact_store.list()[-4:]})
        artifacts = {key: self.assistant_runtime.artifact_store.get(key) for key in artifacts}
        artifacts = {key: value for key, value in artifacts.items() if value is not None}
        handle["artifacts"] = artifacts
        if not self.assistant_runtime.notebook.selection_set:
            self._update_work_results(handle, artifacts.values())
        else:
            self._update_work_results(handle)
        artifacts = handle['artifacts']
        if getattr(self, "workbench_scene_enabled", False) and hasattr(self, "workbench_scene"):
            self.workbench_scene.refresh_from_store(
                sources=self._work_sources(self._assistant_sources),
                artifacts=list(artifacts.values()),
                artifact_store=self.assistant_runtime.artifact_store,
                pending_input_request=self.assistant_runtime.dispatcher.state.pending_input_request,
                changed_artifact=changed,
            )
            self._sync_workbench_scene()
            return
        panel = source_panel(self._work_sources(self._assistant_sources), artifacts=list(artifacts.values()),
                             registry=self.assistant_runtime.registry,
                             on_action=self._on_action_dispatched, on_input=self._on_input_submitted,
                             on_question=self._select_document_question)
        self.chat_stream.update_source_cards(handle, inline_files=document_cards(self._work_sources(self._assistant_sources)), custom_widget=panel)

    def _ask_about_natal_chart(self, prompt, chart):
        if self._pending_chat_query is not None:
            if hasattr(self, '_natal_window'):
                self._natal_window.form_status.setText('Chuột đang xử lý một yêu cầu. Dừng hoặc chờ xong rồi hỏi về lá số.')
            return
        self._assistant_sources = [s for s in self._assistant_sources if s.get('type') != 'natal_chart']
        self._assistant_sources.append({'type': 'natal_chart', 'chart': chart})
        self.show_omnibar(initial_section=0)
        self._submit_chat_prompt(prompt)

    def _quick_search(self, query: str) -> None:
        if self.current_section_idx == 0:
            self._submit_chat_prompt(query)
        else:
            self.search_input.setText(query)
            self.switch_section(1)
            self._execute_search()

    def _quick_fill(self, prefix: str) -> None:
        self.switch_section(1)
        self.search_input.setFocus()
        self.search_input.setText(prefix)
        self.search_input.setCursorPosition(len(prefix))

    def _select_sched_day(self, code: str, idx: int) -> None:
        self.selected_day_code = code
        for i, btn in enumerate(self.day_buttons):
            btn.setProperty("active", "true" if i == idx else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._refresh_schedule_view()

    def _on_sched_member_changed(self, idx: int) -> None:
        if 0 <= idx < len(self.members):
            self.current_member = self.members[idx]
            self.profile_badge.setText(self.current_member.name)
            self._refresh_schedule_view()
            self._refresh_home_agenda()

    def _copy_current_schedule(self) -> None:
        m = self.current_member
        lines = [f"=== THỜI KHÓA BIỂU: {m.name} ({m.mssv}) ==="]
        for day_code, day_name, _ in DAYS:
            sessions = m.schedule.get(day_code, [])
            if sessions:
                lines.append(f"\n[{day_name}]")
                for s in sorted(sessions, key=lambda x: x.start_period):
                    deg = "[ThS]" if s.degree_level == "master" else "[ĐH]"
                    lines.append(f"  • Tiết {s.start_period}-{s.end_period}: {deg} {s.course_name} (Phòng {s.room})")
        full_text = "\n".join(lines)
        QApplication.clipboard().setText(full_text)
        self.show_toast("Đã sao chép TKB vào clipboard")

    def _copy_golden_slots(self) -> None:
        slots = self.compositor.find_golden_windows(min_ratio=0.8)
        lines = ["=== KHUNG GIỜ VÀNG CLB (>= 80% RẢNH) ==="]
        for s in slots:
            lines.append(f"• {s.day_name} — Tiết {s.start_period}-{s.end_period} ({s.time_range}): {s.free_count}/{s.total_count} bạn rảnh")
        full_text = "\n".join(lines)
        QApplication.clipboard().setText(full_text)
        self.show_toast("Đã sao chép khung giờ rảnh vào clipboard")

    def show_toast(self, message: str, timeout_ms: int = 2500) -> None:
        self._toast_timer.stop()
        self._restore_toast()
        self._toast_restore = (message, self.footer_status.text(), self.footer_status.styleSheet())
        self.footer_status.setText(message)
        self.footer_status.setStyleSheet("color: #69583D; font-weight: 500;")
        self.surface_notice.setText(message)
        self.surface_notice.show()
        self._schedule_surface_fit()
        if not self.is_expanded and not self.compact_footer.isHidden():
            self.compact_hint.set_full_text(message)
        self._toast_timer.start(timeout_ms)

    def _restore_toast(self) -> None:
        if self._toast_restore is None:
            return
        message, old_text, old_style = self._toast_restore
        self._toast_restore = None
        # A newer search/reply status wins over an old copy confirmation.
        self.surface_notice.hide()
        self._schedule_surface_fit()
        if self.footer_status.text() == message:
            self.footer_status.setText(old_text)
        self.footer_status.setStyleSheet(old_style)
        if self.compact_hint.full_text == message:
            self._sync_compact_surface()

    def _open_action_menu(self) -> None:
        active_list = self._active_file_list()
        curr_row = active_list.currentRow()
        curr_item = active_list.item(curr_row)
        search_item = curr_item.data(Qt.ItemDataRole.UserRole) if curr_item else None

        self._dialog_active = True
        try:
            dialog = ActionMenuDialog(search_item, self)
            dialog.action_triggered.connect(self._handle_action)
            pos = self.mapToGlobal(QPoint((self.width() - dialog.width()) // 2, (self.height() - dialog.height()) // 2))
            dialog.move(pos)
            dialog.exec()
        finally:
            self._dialog_active = False
            if self.current_section_idx == 0:
                self.chat_composer_input.setFocus()
            else:
                self.search_input.setFocus()

    def _handle_action(self, action_id: str) -> None:
        if action_id == "open":
            self._activate_current_item()
        elif action_id == "quicklook":
            self._preview_quick_look()
        elif action_id == "finder":
            self._reveal_current_in_finder()
        elif action_id == "terminal":
            self._open_current_in_terminal()
        elif action_id == "copy_path":
            self._copy_current_path()
        elif action_id == "copy_content":
            self._copy_current_content()
        elif action_id == "suggest_name":
            self._open_naming_dialog()
        elif action_id == "schedule":
            self.switch_section(2)
        elif action_id == "widget":
            self.switch_section(0)
        elif action_id == "settings":
            self._open_settings()

    def _open_naming_dialog(self) -> None:
        curr_row = self.result_list.currentRow()
        curr_item = self.result_list.item(curr_row)
        search_item = curr_item.data(Qt.ItemDataRole.UserRole) if curr_item else None
        if not search_item:
            return

        self._dialog_active = True
        try:
            from rat.ui.naming_dialog import FilenameSuggestionDialog
            dialog = FilenameSuggestionDialog(target_item=search_item, parent=self)
            dialog.file_renamed.connect(self._on_naming_dialog_file_renamed)
            pos = self.mapToGlobal(QPoint((self.width() - dialog.width()) // 2, (self.height() - dialog.height()) // 2))
            dialog.move(pos)
            dialog.exec()
        except Exception as e:
            logger.error(f"Error opening FilenameSuggestionDialog: {e}", exc_info=True)
        finally:
            self._dialog_active = False

    def _on_naming_dialog_file_renamed(self, old_path: str, new_path: str) -> None:
        new_name = os.path.basename(new_path)
        curr_row = self.result_list.currentRow()
        curr_item = self.result_list.item(curr_row)
        if curr_item:
            search_item: Optional[SearchResultItem] = curr_item.data(Qt.ItemDataRole.UserRole)
            if search_item:
                search_item.file_name = new_name
                search_item.file_path = new_path
                search_item.file_ext = os.path.splitext(new_name)[1]
                if hasattr(self, "preview_panel") and self.preview_panel:
                    self.preview_panel.set_item(search_item, query=self.current_query)

    def _open_settings(self) -> None:
        from rat.ui.settings_dialog import SettingsDialog
        focus = QApplication.focusWidget()
        self._dialog_active = True
        try:
            dialog = SettingsDialog(self)
            dialog.exec()
        finally:
            self._dialog_active = False
            if focus is not None and self.isAncestorOf(focus) and focus.isVisible():
                focus.setFocus()

    def _present_compact_reply(self, answer, status, *, has_details=False, file_summary=False):
        # Kept as a read-only compatibility record; the live answer has one view.
        clean_text = answer.replace('**', '').replace('`', '')
        self.speech_bubble.set_reply(clean_text, status,
            copy_text=answer, has_details=has_details, file_summary=file_summary)
        self.speech_bubble.hide()
        if hasattr(self, "workbench_speech_bubble"):
            self.workbench_speech_bubble.set_reply(clean_text, status,
                copy_text=answer, has_details=has_details, file_summary=file_summary)

    def _on_reasoning_token(self, handle: Dict[str, Any], token: str) -> None:
        if handle.get("generation", self._chat_generation) != self._chat_generation:
            return
        self.chat_stream.append_stream_token(handle, token)
        self._present_compact_reply(handle["full_text"], "Đang gõ")
        if getattr(self, "rat_stage", None):
            self.rat_stage.set_state("thinking", "Chuột · Đang gõ...")
        self.set_mascot_state("thinking")

    def _on_reasoning_finished(
        self,
        handle: Dict[str, Any],
        answer: str,
        steps: List[str],
        latency_ms: float,
        strategy: str,
        badge: str,
    ) -> None:
        if handle.get("generation", self._chat_generation) != self._chat_generation:
            return
        # Non-streaming fallback and final corrections must replace partial tokens.
        handle["full_text"] = answer if answer.strip() else handle.get("full_text", "")
        incomplete = strategy in {"AI chưa sẵn sàng", "Phản hồi bị ngắt"}
        if incomplete:
            self._pending_chat_query = None  # Don't treat a connection error as an answer.
        else:
            self._complete_chat_turn(handle["full_text"])
        self._current_reasoner = None
        if "badge_lbl" in handle:
            handle["badge_lbl"].setText(f"· {badge}")
        self.chat_stream.finalize_stream(handle, reasoning_steps=steps, latency_ms=latency_ms)
        status = {"AI chưa sẵn sàng": "Chưa kết nối", "Phản hồi bị ngắt": "Bị ngắt"}.get(strategy, "Xong")
        self._present_compact_reply(handle["full_text"], status)
        self.footer_status.setText(f"Chuột · {strategy} ({latency_ms:.0f}ms)")
        if getattr(self, "rat_stage", None):
            self.rat_stage.set_state("idle")
        self.set_mascot_state("idle")
        self._sync_compact_surface()

    def _on_chat_worker_finished(self, worker) -> None:
        self._reasoning_workers.discard(worker)
        if self._current_reasoner is worker:
            if hasattr(worker, "response_ready") and self._assistant_handle:
                from rat.engine.assistant_runtime import AgentResponse
                self._on_assistant_response(self._assistant_handle,
                    AgentResponse("", [], 0, 0, 0, error="unexpected_worker_exit"))
                return
            self._current_reasoner = None
            self._pending_chat_query = None
            self._deliver_assistant_reply(
                "Chưa nhận được phản hồi từ AI. Kiểm tra mô hình trong Cài đặt rồi thử lại nhé.",
                strategy="AI chưa sẵn sàng", confidence=0.0,
            )

    # -----------------------------------------------------------------
    # LIFECYCLE & WINDOW EVENTS
    # -----------------------------------------------------------------
    def show_omnibar(self, initial_section: int = 0) -> None:
        """Summon Omnibar window instantly (< 16ms) on the current space without switching desktops."""
        self._is_opening = True
        self._was_activated = False

        self.current_section_idx = 0
        self.content_stack.setCurrentIndex(0)
        self.set_expanded(self.is_expanded)
        self._resize_overlay(820 if self.is_expanded else 620, self._surface_height())

        # Configure macOS fullscreen auxiliary overlay so it floats above all spaces
        configure_macos_fullscreen_overlay(self)

        # Gentle entrance animation (160ms OutCubic)
        self.setWindowOpacity(0.0)
        self.show()
        self._resize_overlay(self.width(), self.height())
        self.raise_()
        self.activateWindow()

        if os.getenv("QT_QPA_PLATFORM") != "offscreen":
            try:
                from rat.os.app import activate_macos_app
                activate_macos_app()
            except Exception:
                pass

        self._entrance_anim = QPropertyAnimation(self, b"windowOpacity")
        self._entrance_anim.setDuration(160 if motion_enabled() else 0)
        self._entrance_anim.setStartValue(0.0)
        self._entrance_anim.setEndValue(1.0)
        self._entrance_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._entrance_anim.start()

        self.speech_bubble.hide()
        self.mascot_peeking.hide()
        self.chat_composer_input.setFocus()
        if initial_section:
            self.activate_chat_feature(initial_section)
        QTimer.singleShot(500, self._finish_opening)

    def _finish_opening(self) -> None:
        self._is_opening = False
        if self.isActiveWindow():
            self._was_activated = True

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.ActivationChange:
            if self.isActiveWindow():
                self._was_activated = True
            elif (
                not getattr(self, "_dialog_active", False)
                and QApplication.activePopupWidget() is None
                and not getattr(self, "_is_opening", False)
                and getattr(self, "_was_activated", False)
                and os.getenv("QT_QPA_PLATFORM") != "offscreen"
            ):
                self.hide()
                self._was_activated = False
        super().changeEvent(event)

    def hideEvent(self, event) -> None:
        self._is_opening = False
        self._was_activated = False
        if hasattr(self, "_entrance_anim") and self._entrance_anim.state() == QPropertyAnimation.State.Running:
            self._entrance_anim.stop()
        if hasattr(self, "workbench_scene"):
            self.workbench_scene._stop_all_animations()
        self.setWindowOpacity(1.0)
        close_quicklook()
        super().hideEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def shutdown(self) -> None:
        """Graceful zero-crash thread cleanup."""
        self._shutting_down = True
        QApplication.instance().removeEventFilter(self._mode_filter)
        self._toast_timer.stop()
        self.companion_avatar_btn.timer.stop()
        if hasattr(self, "thought_trail") and hasattr(self.thought_trail, "stop"):
            self.thought_trail.stop()
        self._toast_restore = None
        self._chat_generation += 1
        self._pending_chat_query = None
        self._current_reasoner = None
        workers = list(self._reasoning_workers)
        for worker in workers:
            worker.requestInterruption()
            # No delayed callback may touch widgets while the window is closing.
            if hasattr(worker, "result_ready"):
                worker.result_ready.disconnect()
            elif hasattr(worker, "response_ready"):
                worker.response_ready.disconnect()
                worker.progress_changed.disconnect()
                worker.step_completed.disconnect()
            else:
                worker.token_received.disconnect()
                worker.reasoning_finished.disconnect()
        for worker in workers:
            if worker.isRunning():
                # Streaming I/O has a 30-second timeout; never terminate an inference thread.
                worker.wait(31000)
        self._reasoning_workers.clear()
        try:
            if hasattr(self, "search_timer") and self.search_timer.isActive():
                self.search_timer.stop()
        except Exception:
            pass

        if hasattr(self, "search_thread") and self.search_thread is not None:
            try:
                if self.search_thread.isRunning():
                    self.search_thread.quit()
                    if not self.search_thread.wait(1500):
                        self.search_thread.terminate()
                        self.search_thread.wait(500)
                self.search_thread.deleteLater()
            except Exception as e:
                logger.debug(f"Omnibar shutdown thread cleanup note: {e}")
            finally:
                self.search_thread = None

        if getattr(self, "_finder_coordinator", None) is not None:
            try:
                self._finder_coordinator.close(timeout=2)
            except Exception as e:
                logger.debug(f"Finder coordinator close note: {e}")
            finally:
                self._finder_coordinator = None

    def closeEvent(self, event) -> None:
        app = QApplication.instance()
        if app and not getattr(app, "_is_quitting", False):
            event.ignore()
            self.hide()
            return

        self.shutdown()
        super().closeEvent(event)
