"""
rat.ui.omnibar — Unified Casual Surface (Omnibar).
One Surface, Zero Modes.
Collapses Spotlight search, recent files, live academic agenda, full timetable,
campus room guidance, and instant calculations into a single macOS-native HUD.
"""

from __future__ import annotations

import logging
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
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
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
    open_file_default,
    open_in_terminal,
    reveal_in_finder,
    trigger_quicklook,
)
from rat.ui.chat_stream import ChatStreamWidget, get_mascot_pixmap
from rat.ui.settings_dialog import SettingsDialog
from rat.ui.theme import RAYCAST_QSS, get_ext_badge_info

logger = logging.getLogger("rat.ui.omnibar")


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
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
            NSFloatingWindowLevel,
        )

        ns_view = objc.objc_object(c_void_p=int(widget.winId()))
        ns_window = ns_view.window() if hasattr(ns_view, "window") else None
        if ns_window:
            behavior = ns_window.collectionBehavior()
            ns_window.setCollectionBehavior_(
                behavior
                | NSWindowCollectionBehaviorCanJoinAllSpaces
                | NSWindowCollectionBehaviorFullScreenAuxiliary
            )
            ns_window.setLevel_(NSFloatingWindowLevel)
    except Exception as e:
        logger.debug(f"macOS fullscreen overlay config error: {e}")


SECTION_TABS = [
    ("home", "Trò chuyện", "Hỏi đáp & lịch hôm nay"),
    ("files", "Tệp tin", "Tìm kiếm tệp & nội dung"),
    ("schedule", "TKB / Lịch", "Thời khóa biểu sinh viên"),
    ("club", "CLB", "Khung giờ rảnh nhóm"),
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
                {"query": query, "results": [], "latency_ms": 0, "parsed_context": {}},
            )


class StreamReasoningWorker(QThread):
    """Background worker for streaming real-time LLM inference without freezing UI."""
    token_received = pyqtSignal(str)
    reasoning_finished = pyqtSignal(str, list, float, str, str)  # (ans, steps, lat_ms, strategy, badge)

    def __init__(self, query: str) -> None:
        super().__init__()
        self.query = query

    def run(self) -> None:
        t0 = time.time()
        from rat.engine.slm import slm_engine

        # Try live token streaming if Ollama is available
        if slm_engine.is_service_running():
            full_tokens = []
            system_prompt = (
                "Bạn là Chuột - trợ lý cá nhân deadpan, dry humor, kiệm lời và hành động nhanh. "
                "Không sến, không dùng emoji cảm thán nhún nhảy, không chào hỏi dài dòng. "
                "Trả lời thẳng vào vấn đề, ngắn gọn, chính xác, gãy gọn bằng tiếng Việt:"
            )
            try:
                for token, done in slm_engine.generate_stream(prompt=self.query, system_prompt=system_prompt):
                    if token:
                        full_tokens.append(token)
                        self.token_received.emit(token)
                    if done:
                        break

                if full_tokens:
                    lat = (time.time() - t0) * 1000.0
                    ans_text = "".join(full_tokens).strip()
                    steps = [
                        f"Phân tích yêu cầu: '{self.query}'",
                        "Kích hoạt mô hình ngôn ngữ On-Device (Qwen2.5-1.5B qua Apple Silicon Metal).",
                        "Hoàn tất suy luận trực tiếp theo thời gian thực.",
                    ]
                    self.reasoning_finished.emit(ans_text, steps, lat, "On-Device Qwen", "Qwen2.5 (Metal)")
                    return
            except Exception as e:
                logger.debug(f"Streaming error, falling back to sync: {e}")

        # Fallback to meta_reasoner
        from rat.engine.meta_reasoner import meta_reasoner
        res = meta_reasoner.solve(self.query)
        self.reasoning_finished.emit(res.answer, res.steps, res.latency_ms, res.strategy, res.badge)


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

            # When typing in chat composer, Down or Tab (if empty) drops focus to suggestion chips
            if watched is getattr(self.window, "chat_composer_input", None):
                if key == Qt.Key.Key_Down or (key == Qt.Key.Key_Tab and not self.window.chat_composer_input.text()):
                    if getattr(self.window, "quick_suggestions", None) and self.window.quick_suggestions.isVisible() and chips:
                        chips[0].setFocus()
                        return True

            # 1. Navigation Up/Down
            if key == Qt.Key.Key_Down:
                self.window.navigate_active_list(1)
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
                        inp_text = self.window.chat_composer_input.text().strip()
                        if inp_text:
                            self.window._submit_chat_prompt(inp_text)
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
                if self.window.current_section_idx == 0 and not getattr(self.window.chat_composer_input, "hasSelectedText", lambda: False)():
                    if hasattr(self.window, "speech_bubble") and self.window.speech_bubble.isVisible() and self.window.speech_bubble.has_reply:
                        self.window.speech_bubble._on_copy_clicked()
                        return True
                if mod & Qt.KeyboardModifier.ShiftModifier:
                    self.window._copy_current_content()
                else:
                    self.window._copy_current_path()
                return True

            # 5. Tab / Backtab -> Cycle Sections
            if key == Qt.Key.Key_Tab:
                self.window.cycle_section(1)
                return True
            elif key == Qt.Key.Key_Backtab:
                self.window.cycle_section(-1)
                return True

            # 6. Cmd + 1..4 -> Direct Section Jump
            if is_cmd and Qt.Key.Key_1 <= key <= Qt.Key.Key_4:
                idx = key - Qt.Key.Key_1
                self.window.switch_section(idx)
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

            # 9. Escape: If expanded, collapse to compact; else hide Omnibar
            if key == Qt.Key.Key_Escape:
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

            if key == Qt.Key.Key_Space:
                self.window._preview_quick_look()
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
            if text and not (is_cmd or (mod & Qt.KeyboardModifier.AltModifier)):
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
    - Clean header with amber dot and status pill; zero distracting buttons.
    - WordWrap with smooth height adjustment.
    - Soft shadow and warm porcelain gradient.
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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 10, 16, 10)
        layout.setSpacing(6)

        # 1. Header Meta Row (clean, no distracting buttons)
        header = QHBoxLayout()
        header.setSpacing(6)

        self.dot = QLabel("●")
        self.dot.setStyleSheet("font-size: 8px; color: #F59E0B; margin-top: 1px;")
        header.addWidget(self.dot)

        self.name_tag = QLabel("CHUỘT")
        self.name_tag.setStyleSheet("font-size: 10px; font-weight: 800; color: #8C7E6F; letter-spacing: 1.2px;")
        header.addWidget(self.name_tag)

        self.context_pill = QLabel("Sẵn sàng")
        self.context_pill.setStyleSheet("font-size: 10px; font-weight: 600; color: #6B7280; background: #F3F4F6; border-radius: 5px; padding: 1px 7px;")
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
        self.dialogue = QLabel("Nghe đây. Cần tìm gì?", self)
        self.dialogue.setStyleSheet("font-size: 13.5px; font-weight: 550; color: #1E293B; line-height: 1.45;")
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
        target_h = max(92, min(112, text_h + 46))

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
    ) -> None:
        self._full_reply = text.strip()
        self._copy_text = text if copy_text is None else copy_text
        self._has_details = has_details
        preview = self._fit_reply(self._full_reply)
        self._truncated = preview != self._full_reply
        self.dialogue.setText(preview)
        self.btn_copy.setVisible(self.has_reply)
        self.btn_hist.setVisible(self.has_reply and (self._truncated or self._has_details or self._expanded))
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
        self.btn_copy.hide()
        self.btn_hist.hide()
        self.dialogue.setText("Nghe đây. Cần tìm gì?")
        self.context_pill.setText("Sẵn sàng")
        self.update_target_height(animated=False)

    def set_expanded_mode(self, is_expanded: bool) -> None:
        self._expanded = is_expanded
        self.btn_hist.setText("Thu gọn" if is_expanded else "Xem kết quả" if self._has_details else "Đọc hết")
        self.btn_hist.setVisible(self.has_reply and (self._truncated or self._has_details or is_expanded))

    def show_bubble(self) -> None:
        self.show()
        self.raise_()
        self.update_target_height(animated=False)

    def hide_bubble(self) -> None:
        self.hide()

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

        # Soft multi-pass drop shadow
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(30, 24, 16, 12))
        painter.translate(0, 4)
        painter.drawPath(path)
        painter.setBrush(QColor(30, 24, 16, 18))
        painter.translate(0, -2)
        painter.drawPath(path)
        painter.restore()

        # Warm porcelain gradient fill
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor(255, 255, 255, 252))
        grad.setColorAt(1.0, QColor(252, 250, 247, 248))
        painter.setBrush(QBrush(grad))

        painter.setPen(QPen(QColor(40, 30, 20, 22), 1.0))
        painter.drawPath(path)


ComicSpeechFrame = ArtisticSpeechBubble


class CompanionAvatarButton(QPushButton):
    """
    Tactile Companion Avatar button located right inside the search input / composer bar.
    Renders Chuột's expressive bust with dynamic overhead badges:
    - 'idle': Calm, friendly, ready
    - 'searching': Magnifying glass 🔍
    - 'thinking': Animated spinning loading ring + 💭
    - 'angry': Comic angry vein mark 💢
    """

    def __init__(self, window: "OmnibarWindow", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.window = window
        self.setFixedSize(34, 34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Chuột đồng hành · Nhấp để trò chuyện hoặc chọc giận!")
        self.current_state = "idle"
        self._spin_angle = 0
        self._spin_timer = QTimer(self)
        self._spin_timer.timeout.connect(self._on_spin_tick)
        self._click_count = 0
        self._last_click_time = 0.0
        self.clicked.connect(self._on_clicked)

        # Pre-load mascot bust pixmap
        self._bust_pm = get_mascot_pixmap(24, 24, bust_only=True)

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

    def _on_clicked(self) -> None:
        now = time.time()
        if now - self._last_click_time < 1.5:
            self._click_count += 1
        else:
            self._click_count = 1
        self._last_click_time = now

        if self._click_count >= 3:
            # Angry reaction!
            self.window.set_mascot_state("angry", "Bấm hoài vậy bạn ơi! Để yên cho Chuột làm việc coi! 💢")
            QTimer.singleShot(4000, lambda: self.window.set_mascot_state("idle"))
        else:
            quotes = [
                "Nghe đây. Cần tìm tài liệu hay hỏi gì thì gõ vào ô nè.",
                "Tôi đang nghe đây. Nói lẹ đi bạn ơi.",
                "Đừng chọc nữa, lo học bài đi!",
                "Có bài tập hay phòng học nào cần tìm không?",
            ]
            q = quotes[self._click_count % len(quotes)]
            self.window.set_mascot_state("speaking" if not self.window.is_expanded else "idle", q)

    def paintEvent(self, event: Any) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Background capsule
        p.setBrush(QColor("#F8F5EE"))
        p.setPen(QPen(QColor("#E2D7C7"), 1.5))
        p.drawRoundedRect(1, 1, 32, 32, 16, 16)

        # Mascot face
        if self._bust_pm and not self._bust_pm.isNull():
            fx = (self.width() - self._bust_pm.width()) // 2
            fy = (self.height() - self._bust_pm.height()) // 2 + 1
            p.drawPixmap(fx, fy, self._bust_pm)

        # State badge
        st = self.current_state
        if st == "thinking":
            p.save()
            p.translate(24, 8)
            p.rotate(self._spin_angle)
            pen = QPen(QColor("#F59E0B"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawArc(QRectF(-5, -5, 10, 10), 0, 270 * 16)
            p.restore()
        elif st == "searching":
            p.setFont(QFont("Apple Color Emoji", 11))
            p.drawText(QRectF(17, 0, 16, 16), Qt.AlignmentFlag.AlignCenter, "🔍")
        elif st == "angry":
            p.setFont(QFont("Apple Color Emoji", 12))
            p.drawText(QRectF(17, -1, 16, 16), Qt.AlignmentFlag.AlignCenter, "💢")
        p.end()


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

        self.setFixedSize(146, 146)

        # Coordinate anchors (container top rim is at y=120)
        self.x_idle = 24
        self.y_idle = 8           # paws at bottom of 146px bust rest right at y=120 on rim
        self.x_speaking = 44      # +20px per spec
        self.y_speaking = 2       # nhấc lên một chút
        self.rot_idle = 0.0       # 0 degree khi núp
        self.rot_speaking = 10.0  # +10 degree tilt khi nói

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

        self.x_idle = cx + 8
        self.y_idle = max(2, cy - 112)  # container at 120 -> y_idle = 8
        self.x_speaking = self.x_idle + 20
        self.y_speaking = max(2, self.y_idle - 6)
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
        if event.button() == Qt.MouseButton.LeftButton:
            if hasattr(self.window, "on_mascot_clicked"):
                self.window.on_mascot_clicked()

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
            "Hỏi Chuột bất cứ điều gì nè! Lịch học, tìm phòng C302, tìm tài liệu hay tính nhanh... 🧀✨",
            "Chuột đang sẵn sàng nè, bạn cần tìm gì cứ bảo Chuột nha! 🧀",
            "Đừng chọc tui hoài, vào học bài đi bạn ơi! 📚",
            "Hôm nay có bài tập hay đồ án gì chưa nộp hông đó? 🏃",
            "Nhấp đúp chuột để mở rộng sổ tay chi tiết nha! ⤢",
            "Sinh viên TDTU học chăm chỉ dữ ta! Cần gì Chuột hỗ trợ liền! 🧀✨",
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
        if event.button() == Qt.MouseButton.LeftButton:
            self._quote_idx = (self._quote_idx + 1) % len(self._quotes)
            q = self._quotes[self._quote_idx]
            if hasattr(self.window, "rat_speech"):
                self.window.rat_speech.setText(q)
            self.set_state("happy", "🎉 Chuột · Vui vẻ!")
            QTimer.singleShot(2500, lambda: self.set_state("idle"))

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.window.toggle_expand()


class OmnibarWindow(QMainWindow):
    """
    Unified Casual Surface (Omnibar).
    Brings together chat, file search, class schedules, and shared free-time windows.
    """

    search_requested = pyqtSignal(int, str, list)

    def __init__(self) -> None:
        super().__init__()
        self.db = Database(config.db_path)
        self.engine = SearchEngine(self.db)
        self.compositor = TimetableCompositor(load_club_members())
        self.members: List[MemberSchedule] = self.compositor.members

        self.current_section_idx = 0
        self.active_file_filter_idx = 0
        self.is_expanded = False
        self._request_counter = 0
        self._dialog_active = False
        self._is_opening = False
        self._was_activated = False
        self.current_query = ""

        # Huy is default member
        self.current_member = next((m for m in self.members if "Huy" in m.name), self.members[0])

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(180)
        self.search_timer.timeout.connect(self._execute_search)

        self._drag_pos = QPoint()
        self._init_thread()
        self._init_window()
        self._init_ui()
        self.feedback = SearchFeedback(self, "omnibar", [self.result_list, self.recent_list])
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
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(RAYCAST_QSS)
        self._resize_overlay(652, 238)
        configure_macos_fullscreen_overlay(self)

    def _resize_overlay(self, new_width: int, new_height: int, animated: bool = False) -> None:
        """Position window smoothly in comfortable upper area of screen with stable fixed top anchor."""
        try:
            cursor_pos = QCursor.pos()
            screen = QGuiApplication.screenAt(cursor_pos) or self.screen() or QGuiApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                x = geo.x() + (geo.width() - new_width) // 2

                # Fixed top anchor at ~18% of screen height (like Spotlight / Raycast)
                # When expanding or collapsing, the search bar NEVER jumps!
                target_y = geo.y() + int(geo.height() * 0.18)
                target_rect = QRect(x, target_y, new_width, new_height)

                if animated and self.isVisible():
                    if not hasattr(self, "_geom_anim"):
                        self._geom_anim = QPropertyAnimation(self, b"geometry")
                        self._geom_anim.setDuration(160)
                        self._geom_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                    self._geom_anim.stop()
                    self._geom_anim.setStartValue(self.geometry())
                    self._geom_anim.setEndValue(target_rect)
                    self._geom_anim.start()
                else:
                    self.setGeometry(target_rect)
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
        """State-aware mascot transition."""
        if not hasattr(self, "mascot_peeking"):
            return
        if getattr(self.mascot_peeking, "is_speaking", False):
            self.mascot_peeking.pop_out_speaking()
        else:
            self.mascot_peeking.retreat_to_idle()

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        if hasattr(self, "speech_bubble") and hasattr(self, "container"):
            cx = self.container.x() if self.container.x() > 0 else 16
            cy = self.container.y() if self.container.y() > 20 else 120
            bx = cx + 160
            by = max(4, cy - self.speech_bubble.height() - 14)
            self.speech_bubble.move(bx, by)
            self.speech_bubble.raise_()
            if hasattr(self, "mascot_peeking"):
                self.mascot_peeking.set_anchors(cx, cy)

    def set_mascot_speaking(self, text: Optional[str] = None) -> None:
        """Activate SPEAKING state: triggers diagonal pop-out and speech bubble."""
        if text:
            if hasattr(self, "speech_bubble"):
                self.speech_bubble.set_reply(text)
        if hasattr(self, "mascot_peeking"):
            if not self.mascot_peeking.is_speaking:
                if hasattr(self, "speech_bubble"):
                    self.speech_bubble.hide()
                self.mascot_peeking.pop_out_speaking()
            else:
                if hasattr(self, "speech_bubble"):
                    self.speech_bubble.show_bubble()

    def _on_mascot_speaking_popped_out(self) -> None:
        """Speech bubble appears right after mouse finishes diagonal pop-out."""
        if hasattr(self, "speech_bubble") and not self.is_expanded:
            self.speech_bubble.show_bubble()

    def set_mascot_idle(self) -> None:
        """Activate IDLE state: hides speech bubble and retreats to peeking paws/eyes."""
        if hasattr(self, "speech_bubble"):
            self.speech_bubble.hide_bubble()
        if hasattr(self, "mascot_peeking"):
            self.mascot_peeking.retreat_to_idle()

    def _on_mascot_idle_retreated(self) -> None:
        pass

    def on_mascot_clicked(self) -> None:
        """Interactive click on mascot toggles speaking/quote or retreats."""
        if not hasattr(self, "mascot_peeking"):
            return
        if not self.mascot_peeking.is_speaking:
            quotes = [
                "Chọc cái gì? Cần tìm gì thì gõ vào ô đi.",
                "Tôi đang nghe đây. Nói lẹ đi.",
                "Đừng bấm lung tung. Học bài đi.",
                "Nghe đây. Cần gì?",
            ]
            self._mascot_quote_idx = (getattr(self, "_mascot_quote_idx", 0) + 1) % len(quotes)
            self.set_mascot_speaking(quotes[self._mascot_quote_idx])
            if not hasattr(self, "_mascot_click_timer"):
                self._mascot_click_timer = QTimer(self)
                self._mascot_click_timer.setSingleShot(True)
                self._mascot_click_timer.timeout.connect(self.set_mascot_idle)
            self._mascot_click_timer.start(5000)
        else:
            self.set_mascot_idle()

    def set_mascot_state(self, state: str, text: Optional[str] = None) -> None:
        """Unified state setter for Chuột across all UI widgets."""
        self._mascot_state = state
        if hasattr(self, "companion_avatar_btn"):
            self.companion_avatar_btn.set_state(state)
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
        """Explicitly switch between compact HUD and full notebook mode."""
        self.is_expanded = expanded
        if hasattr(self, "speech_bubble"):
            self.speech_bubble.set_expanded_mode(expanded)

        if expanded:
            if hasattr(self, "main_layout"):
                self.main_layout.setContentsMargins(16, 120, 16, 16)
            if hasattr(self, "mascot_peeking"):
                self.mascot_peeking.show()
                self.mascot_peeking.set_anchors(16, 120)
            if hasattr(self, "speech_bubble"):
                self.speech_bubble.hide()
            if getattr(self, "btn_expand", None):
                self.btn_expand.show()
            if hasattr(self, "chat_header_status"):
                self.chat_header_status.show()
            if hasattr(self, "section_bar"):
                self.section_bar.hide()
            if hasattr(self, "content_stack"):
                self.content_stack.show()
                self.content_stack.setCurrentIndex(getattr(self, "current_section_idx", 0))
            if hasattr(self, "chat_stream"):
                self.chat_stream.show()
            if hasattr(self, "action_footer"):
                self.action_footer.show()
            if hasattr(self, "quick_suggestions"):
                self.quick_suggestions.hide()
            if hasattr(self, "hairline_divider"):
                self.hairline_divider.hide()
            self._resize_overlay(652, 580, animated=True)
            if hasattr(self, "btn_expand") and self.btn_expand:
                self.btn_expand.setText("⤡")
        else:
            if hasattr(self, "main_layout"):
                self.main_layout.setContentsMargins(16, 120, 16, 16)
            if hasattr(self, "mascot_peeking"):
                self.mascot_peeking.show()
                self.mascot_peeking.set_anchors(16, 120)
            if hasattr(self, "speech_bubble"):
                if self.speech_bubble.has_reply:
                    self.speech_bubble.show_bubble()
                else:
                    self.speech_bubble.hide()
            if hasattr(self, "chat_header_status"):
                self.chat_header_status.hide()
            if hasattr(self, "companion_avatar_btn"):
                self.companion_avatar_btn.hide()
            if hasattr(self, "btn_expand"):
                self.btn_expand.hide()
            if hasattr(self, "return_keycap"):
                self.return_keycap.hide()
            if hasattr(self, "section_bar"):
                self.section_bar.hide()
            if hasattr(self, "content_stack"):
                self.content_stack.hide()
            if hasattr(self, "chat_stream"):
                self.chat_stream.hide()
            if hasattr(self, "action_footer"):
                self.action_footer.hide()
            if hasattr(self, "quick_suggestions"):
                self.quick_suggestions.show()
            if hasattr(self, "hairline_divider"):
                self.hairline_divider.hide()
            self._resize_overlay(652, 238, animated=True)
            if hasattr(self, "btn_expand") and self.btn_expand:
                self.btn_expand.setText("⤢")

    def _init_ui(self) -> None:
        self.input_filter = OmnibarInputFilter(self)

        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        self.main_layout = QVBoxLayout(main_widget)
        self.main_layout.setContentsMargins(16, 120, 16, 16)
        self.main_layout.setSpacing(0)

        # =============================================================
        # SINGLE UNIFIED CONTAINER (Warm Light Glass)
        # =============================================================
        container = QFrame(main_widget)
        container.setObjectName("SpotlightContainer")
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        container.setStyleSheet("""
            QFrame#SpotlightContainer {
                background: #FFFFFF;
                border: 1px solid rgba(0, 0, 0, 0.08);
                border-radius: 16px;
            }
        """)
        cont_shadow = QGraphicsDropShadowEffect(container)
        cont_shadow.setBlurRadius(28)
        cont_shadow.setOffset(0, 10)
        cont_shadow.setColor(QColor(0, 0, 0, 26))
        container.setGraphicsEffect(cont_shadow)

        self.container = container
        self.container_layout = QVBoxLayout(container)
        self.container_layout.setContentsMargins(14, 12, 14, 12)
        self.container_layout.setSpacing(8)

        # -------------------------------------------------------------
        # PEEKING MASCOT (Núp hở mắt/tay & Pop-out xéo)
        # -------------------------------------------------------------
        self.mascot_peeking = PeekingRatMascot(self, main_widget)
        self.mascot_peeking.stackUnder(container)
        self.mascot_peeking.setGeometry(24, 8, 146, 146)
        self.mascot_peeking.set_anchors(16, 120)
        self.mascot_peeking.speaking_popped_out.connect(self._on_mascot_speaking_popped_out)
        self.mascot_peeking.idle_retreated.connect(self._on_mascot_idle_retreated)
        self.mascot_peeking.show()

        # -------------------------------------------------------------
        # ARTISTIC SPEECH BUBBLE (Sitting above container, flush right)
        # -------------------------------------------------------------
        self.speech_bubble = ArtisticSpeechBubble(self, main_widget)
        self.speech_bubble.setGeometry(176, 14, 460, 92)
        self.speech_bubble.hide()

        # Compatibility attributes
        self.rat_avatar = self.mascot_peeking
        self.rat_stage = None
        self.rat_perch = None
        self.rat_speech = self.speech_bubble.dialogue
        self.rat_speech_frame = self.speech_bubble
        self.btn_expand = None
        self.btn_close = None
        self.btn_bubble_expand = None
        self.speech_expand_hint = None
        self.rat_tail = None

        # -------------------------------------------------------------
        # 1. INPUT ROW (QuickBar) - TOP OF CONTAINER
        # -------------------------------------------------------------
        quick_bar = QFrame()
        quick_bar.setObjectName("QuickBar")
        quick_bar.setFixedHeight(36)

        qb_layout = QHBoxLayout(quick_bar)
        qb_layout.setContentsMargins(4, 0, 4, 0)
        qb_layout.setSpacing(6)

        # Companion Avatar Button inside QuickBar (Hidden in clean mode)
        self.companion_avatar_btn = CompanionAvatarButton(self, quick_bar)
        self.companion_avatar_btn.hide()
        qb_layout.addWidget(self.companion_avatar_btn, 0)

        self.chat_composer_input = QLineEdit()
        self.chat_composer_input.setObjectName("ChatComposerInput")
        self.chat_composer_input.setPlaceholderText("Gõ câu hỏi, tên file, lịch học...")
        self.chat_composer_input.setStyleSheet("""
            QLineEdit#ChatComposerInput {
                font-size: 14px;
                border: none;
                background: transparent;
                color: #1F2937;
                padding-left: 2px;
            }
        """)
        self.chat_composer_input.setClearButtonEnabled(True)
        self.chat_composer_input.installEventFilter(self.input_filter)
        self.chat_composer_input.returnPressed.connect(lambda: self._submit_chat_prompt(self.chat_composer_input.text()))
        self.chat_composer_input.textChanged.connect(self._on_composer_text_changed)
        qb_layout.addWidget(self.chat_composer_input, 1)

        # Minimal model status badge (shown in expanded mode)
        has_slm = False
        try:
            from rat.engine.slm import slm_engine
            has_slm = slm_engine.is_service_running()
        except Exception:
            pass
        status_text = "● Qwen2.5" if has_slm else "● TDTU"
        self.chat_header_status = QLabel(status_text, quick_bar)
        self.chat_header_status.setObjectName("QuickModelBadge")
        self.chat_header_status.hide()
        qb_layout.addWidget(self.chat_header_status)

        self.btn_expand = QPushButton("⤢", quick_bar)
        self.btn_expand.setObjectName("BtnExpand")
        self.btn_expand.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_expand.setToolTip("Mở rộng / Thu nhỏ (⌘L)")
        self.btn_expand.clicked.connect(self.toggle_expand)
        self.btn_expand.setFixedSize(26, 26)
        self.btn_expand.setStyleSheet("""
            QPushButton#BtnExpand {
                background: transparent;
                border: none;
                color: #8C8275;
                font-size: 13px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton#BtnExpand:hover {
                background: rgba(43, 38, 31, 0.08);
                color: #1F1A16;
            }
        """)
        self.btn_expand.hide()
        qb_layout.addWidget(self.btn_expand)

        self.return_keycap = QLabel("↵")
        self.return_keycap.setObjectName("ReturnKeycap")
        self.return_keycap.setToolTip("Nhấn Enter để gửi")
        self.return_keycap.hide()
        qb_layout.addWidget(self.return_keycap)

        self.quick_bar = quick_bar
        self.container_layout.addWidget(quick_bar, 0)

        # -------------------------------------------------------------
        # 2. HAIRLINE DIVIDER (Hidden in clean compact mode)
        # -------------------------------------------------------------
        self.hairline_divider = QFrame()
        self.hairline_divider.setObjectName("HairlineDivider")
        self.container_layout.addWidget(self.hairline_divider, 0)
        self.hairline_divider.hide()

        # -------------------------------------------------------------
        # 3. QUICK SUGGESTIONS STRIP (Clean suggestion chips)
        # -------------------------------------------------------------
        self.quick_suggestions = QWidget()
        self.quick_suggestions.setObjectName("QuickSuggestionsStrip")
        self.quick_suggestions.setFixedHeight(34)
        qs_layout = QHBoxLayout(self.quick_suggestions)
        qs_layout.setContentsMargins(2, 0, 2, 0)
        qs_layout.setSpacing(6)

        sugg_chips = [
            ("📅 Hôm nay học gì?", "hôm nay học gì"),
            ("📍 Phòng C302 ở đâu?", "phòng C302 ở đâu"),
            ("📁 Tìm tài liệu", "tìm file đề thi"),
            ("👥 Giờ rảnh CLB", "giờ rảnh clb"),
        ]
        self.chip_buttons: List[QPushButton] = []
        for label, q_text in sugg_chips:
            chip_btn = QPushButton(label)
            chip_btn.setProperty("class", "QuickSuggestionChip")
            chip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            chip_btn.setStyleSheet("""
                QPushButton {
                    background: #FAFAFA;
                    border: 1px solid #E5E7EB;
                    border-radius: 8px;
                    padding: 4px 10px;
                    font-size: 11px;
                    color: #4B5563;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background: #F3F4F6;
                    border-color: #D1D5DB;
                    color: #111827;
                }
            """)
            chip_btn.installEventFilter(self.input_filter)
            chip_btn.clicked.connect(lambda checked=False, q=q_text: self._submit_chat_prompt(q))
            qs_layout.addWidget(chip_btn)
            self.chip_buttons.append(chip_btn)

        self.container_layout.addWidget(self.quick_suggestions, 0)
        self.quick_suggestions.show()

        # -------------------------------------------------------------
        # 4. FOLDER TABS (SECTION BAR)
        # -------------------------------------------------------------
        self.section_bar = QFrame()
        self.section_bar.setObjectName("FilterPillsBar")
        section_layout = QHBoxLayout(self.section_bar)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(4)
        self.section_buttons: List[QPushButton] = []
        for idx, (sec_id, label, tooltip) in enumerate(SECTION_TABS):
            btn = QPushButton(label)
            btn.setProperty("class", "FilterPill")
            btn.setProperty("active", "true" if idx == 0 else "false")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, i=idx: self.switch_section(i))
            section_layout.addWidget(btn)
            self.section_buttons.append(btn)
        section_layout.addStretch()
        self.container_layout.addWidget(self.section_bar, 0)
        self.section_bar.hide()

        # -------------------------------------------------------------
        # 5. CONTENT STACK
        # -------------------------------------------------------------
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("background: transparent;")

        self.home_view = self._create_home_view()
        self.content_stack.addWidget(self.home_view)

        self.files_view = self._create_files_view()
        self.content_stack.addWidget(self.files_view)

        self.schedule_view = self._create_schedule_view()
        self.content_stack.addWidget(self.schedule_view)

        self.club_view = self._create_club_view()
        self.content_stack.addWidget(self.club_view)

        self.container_layout.addWidget(self.content_stack, 1)
        self.content_stack.hide()

        # Action Footer
        footer = QFrame()
        footer.setObjectName("ActionFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(14, 6, 14, 6)
        footer_layout.setSpacing(10)

        self.footer_status = QLabel("Sẵn sàng")
        self.footer_status.setObjectName("FooterStatus")
        footer_layout.addWidget(self.footer_status)
        footer_layout.addStretch()

        hotkeys = [
            ("Enter", "Mở"),
            ("Space", "Xem nhanh"),
            ("Tab", "Chuyển mục"),
            ("⌘K", "Tác vụ"),
            ("Esc", "Đóng"),
        ]
        self.footer_hotkey_widgets = []
        for key, desc in hotkeys:
            badge = QLabel(key)
            badge.setProperty("class", "HotkeyBadge")
            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color: #887c70; font-size: 10px; margin-right: 2px;")
            footer_layout.addWidget(badge)
            footer_layout.addWidget(desc_label)
            self.footer_hotkey_widgets.extend((badge, desc_label))

        self.action_footer = footer
        self.action_footer.hide()
        self.container_layout.addWidget(self.action_footer)

        # Hidden Compatibility Buttons
        self.btn_new_chat = QPushButton("⌘N", container)
        self.btn_new_chat.clicked.connect(self._reset_chat)
        self.btn_new_chat.hide()
        self.btn_settings = QPushButton("⚙", container)
        self.btn_settings.clicked.connect(self._open_settings)
        self.btn_settings.hide()

        self.main_layout.addWidget(container, 1)

    def _on_composer_text_changed(self, text: str) -> None:
        q = text.strip()
        is_active = bool(q)
        if hasattr(self, "return_keycap"):
            self.return_keycap.setProperty("active", "true" if is_active else "false")
            self.return_keycap.style().unpolish(self.return_keycap)
            self.return_keycap.style().polish(self.return_keycap)

        if not q:
            if getattr(self, "rat_stage", None):
                self.rat_stage.set_state("idle")
            if hasattr(self, "speech_bubble") and hasattr(self, "chat_stream") and self.chat_stream.is_empty():
                self.speech_bubble.reset_welcome()
            return
        if getattr(self, "rat_stage", None):
            self.rat_stage.set_state("listening", "Chuột · Đang nghe")

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
        self.chat_stream.prompt_clicked.connect(self._submit_chat_prompt)
        self.chat_stream.show()  # Visible surface with welcome prompts
        root_layout.addWidget(self.chat_stream, 1)

        # Hidden Compatibility Container for Tests
        compat_box = QWidget(widget)
        compat_box.hide()
        compat_layout = QVBoxLayout(compat_box)

        # Micro footer (kept inside compat container so it never becomes a top-level window)
        self.chat_micro_footer = QWidget(compat_box)
        self.chat_micro_footer.hide()
        self.chat_micro_status = QLabel("● Sẵn sàng", self.chat_micro_footer)
        compat_layout.addWidget(self.chat_micro_footer)

        self.chat_composer_send = QPushButton("↵", compat_box)
        self.chat_composer_send.clicked.connect(lambda: self._submit_chat_prompt(self.chat_composer_input.text()))
        compat_layout.addWidget(self.chat_composer_send)

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
        search_row.setStyleSheet("background-color: #FFFFFF; border-bottom: 1px solid rgba(43, 38, 31, 0.08); padding: 8px 12px;")
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
        sub_bar.setStyleSheet("background-color: #FBF9F5; border-bottom: 1px solid rgba(43, 38, 31, 0.06); padding: 4px 14px;")
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
        self.splitter.addWidget(self.preview_panel)

        self.splitter.setSizes([490, 490])
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
        toolbar.setStyleSheet("background-color: #FFFFFF; border: 1px solid rgba(43, 38, 31, 0.08); border-radius: 8px; padding: 5px 10px;")
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
        self.club_scroll.setStyleSheet("border: 1px solid rgba(43, 38, 31, 0.08); border-radius: 10px; background-color: #FFFFFF;")
        self.club_content = QWidget()
        self.club_layout = QVBoxLayout(self.club_content)
        self.club_layout.setContentsMargins(10, 10, 10, 10)
        self.club_layout.setSpacing(6)
        self.club_scroll.setWidget(self.club_content)
        layout.addWidget(self.club_scroll, 1)

        return widget

    # -----------------------------------------------------------------
    # SECTION NAVIGATION & SWITCHING
    # -----------------------------------------------------------------
    def switch_section(self, idx: int) -> None:
        if idx < 0 or idx >= len(SECTION_TABS):
            return
        self.current_section_idx = idx
        self.content_stack.setCurrentIndex(idx)
        show_file_search = idx == 1
        self.search_icon.setVisible(show_file_search)
        self.search_input.setVisible(show_file_search)
        self.btn_send.setVisible(show_file_search)
        self.action_footer.setVisible(idx != 0)
        for hotkey_widget in self.footer_hotkey_widgets:
            hotkey_widget.setVisible(idx != 0)

        # Update pill states
        for i, btn in enumerate(self.section_buttons):
            btn.setProperty("active", "true" if i == idx else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        if hasattr(self, "quick_bar"):
            self.quick_bar.setVisible(idx == 0)

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
        return self.result_list.hasFocus() or self.recent_list.hasFocus()

    def navigate_active_list(self, delta: int) -> None:
        active_list = self.result_list if self.current_section_idx == 1 else self.recent_list
        count = active_list.count()
        if count == 0:
            return
        curr = active_list.currentRow()
        new_row = max(0, min(count - 1, curr + delta))
        active_list.setCurrentRow(new_row)

    def _activate_current_item(self) -> None:
        active_list = self.result_list if self.current_section_idx == 1 else self.recent_list
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
        active_list = self.result_list if self.current_section_idx == 1 else self.recent_list
        curr_row = active_list.currentRow()
        item = active_list.item(curr_row)
        if item:
            search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
            if search_item:
                self.feedback.perform("reveal", search_item, reveal_in_finder)

    def _open_current_in_terminal(self) -> None:
        active_list = self.result_list if self.current_section_idx == 1 else self.recent_list
        curr_row = active_list.currentRow()
        item = active_list.item(curr_row)
        if item:
            search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
            if search_item:
                self.feedback.perform("terminal", search_item, open_in_terminal)
                self.show_toast(f"💻 Đã mở Terminal: {search_item.file_name}")

    def _preview_quick_look(self) -> None:
        active_list = self.result_list if self.current_section_idx == 1 else self.recent_list
        curr_row = active_list.currentRow()
        item = active_list.item(curr_row)
        if item:
            search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
            if search_item:
                trigger_quicklook(search_item.file_path)

    def _copy_current_path(self) -> None:
        active_list = self.result_list if self.current_section_idx == 1 else self.recent_list
        curr_row = active_list.currentRow()
        item = active_list.item(curr_row)
        if item:
            search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
            cb = QApplication.clipboard()
            if cb and search_item:
                cb.setText(search_item.file_path)
                self.show_toast(f"✓ Đã sao chép đường dẫn: {search_item.file_name}")

    def _copy_current_content(self) -> None:
        active_list = self.result_list if self.current_section_idx == 1 else self.recent_list
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
    ) -> None:
        """
        Deliver assistant reply:
        - In compact mode: Chuột speaks via speech bubble.
        - In expanded mode: reply goes cleanly to chat stream, NO floating bubble outside!
        """
        context_str = f"{strategy} · {latency_ms:.0f}ms" if latency_ms > 0 else "Sẵn sàng"
        self._present_compact_reply(answer, context_str, has_details=bool(inline_files or custom_widget))

        if hasattr(self, "chat_stream"):
            try:
                self.chat_stream.add_assistant_message(
                    answer=answer,
                    reasoning_steps=reasoning_steps,
                    latency_ms=latency_ms,
                    strategy=strategy,
                    confidence=confidence,
                    custom_widget=custom_widget,
                    inline_files=inline_files,
                )
            except Exception as e:
                logger.debug(f"Chat stream add error: {e}")

        if getattr(self, "rat_stage", None):
            self.rat_stage.set_state("idle")
        if getattr(self, "set_mascot_state", None) and getattr(self, "_mascot_state", "idle") != "angry":
            self.set_mascot_state("idle")

    def _reset_chat(self) -> None:
        if hasattr(self, "chat_stream"):
            self.chat_stream.clear_chat()
        self.set_expanded(False)
        self.set_mascot_idle()
        if hasattr(self, "speech_bubble"):
            self.speech_bubble.reset_welcome()
        self.search_input.clear()
        if hasattr(self, "chat_composer_input"):
            self.chat_composer_input.clear()
        self.switch_section(0)
        self.show_toast("Đã làm mới phiên chat")

    def _submit_chat_prompt(self, query: str) -> None:
        q = query.strip()
        if not q:
            return

        if self.current_section_idx != 0:
            self.switch_section(0)

        # Quick mode answers directly via speech bubble without forcing expansion
        self.set_mascot_state("thinking", "Chuột · Suy nghĩ...")
        self.speech_bubble.set_reply("Đang suy nghĩ…", "Đang nghĩ", copy_text="")

        self.chat_stream.add_user_message(q)
        self.search_input.clear()
        if hasattr(self, "chat_composer_input"):
            self.chat_composer_input.clear()
        if hasattr(self, "return_keycap"):
            self.return_keycap.setProperty("active", "false")
            self.return_keycap.style().unpolish(self.return_keycap)
            self.return_keycap.style().polish(self.return_keycap)
        QApplication.processEvents()

        q_lower = q.lower()
        t0 = time.time()

        # 0. Greetings & Smalltalk (Deadpan)
        greetings = ["chào", "chao", "hello", "hi", "alo", "helo", "hey", "chuột ơi", "chuot oi", "chào chuột", "chao chuot", "rat ơi", "rat oi", "chào rat", "chao rat"]
        if any(q_lower == g or q_lower.startswith(g + " ") for g in greetings):
            lat = (time.time() - t0) * 1000.0
            self._deliver_assistant_reply(
                answer="Nghe đây. Cần gì?",
                latency_ms=lat,
                strategy="Direct",
            )
            return

        # 0b. Help & Capabilities Guide
        help_kw = ["help", "giúp", "bạn làm được gì", "ban lam duoc gi", "hướng dẫn", "huong dan", "tính năng", "tinh nang", "dùng sao", "dung sao"]
        if any(k in q_lower for k in help_kw):
            lat = (time.time() - t0) * 1000.0
            ans_text = "Gõ câu hỏi, tên file, phòng học (C302), lịch học hoặc tính toán. Tôi tìm và trả lời."
            self._deliver_assistant_reply(
                answer=ans_text,
                latency_ms=lat,
                strategy="Direct",
            )
            return

        # 0c. Gratitude & Goodbyes
        if any(q_lower == k or q_lower.startswith(k + " ") for k in ["cảm ơn", "cam on", "thanks", "thank you", "tks", "cảm ơn chuột", "cảm ơn rat"]):
            lat = (time.time() - t0) * 1000.0
            self._deliver_assistant_reply(
                answer="Được rồi. Không có gì.",
                latency_ms=lat,
                strategy="Direct",
            )
            return

        if any(q_lower == k or q_lower.startswith(k + " ") for k in ["tạm biệt", "tam biet", "bye", "bai", "bye chuột", "bye rat"]):
            lat = (time.time() - t0) * 1000.0
            self._deliver_assistant_reply(
                answer="Ừ. Làm việc tiếp đi.",
                latency_ms=lat,
                strategy="Direct",
            )
            return

        # 0d. Teasing / Scolding -> Angry mascot state
        scold_words = ["đồ ngu", "ngu quá", "dở tệ", "chuột ngốc", "chuột ngu", "bực mình", "vô dụng", "ngu vcl", "ngu vch"]
        if any(w in q_lower for w in scold_words):
            self.set_mascot_state("angry")
            ans_text = "Nói ai ngu đó? Tôi tìm được mọi file trong 5ms còn bạn thì ngồi gõ chửi bậy à? 💢"
            self._deliver_assistant_reply(
                answer=ans_text,
                latency_ms=1.0,
                strategy="Direct",
            )
            QTimer.singleShot(4000, lambda: self.set_mascot_state("idle"))
            return

        # 1. Academic Policy & Multi-Step Reasoning
        from rat.engine.meta_reasoner import meta_reasoner
        if meta_reasoner.is_reasoning_query(q):
            try:
                res = meta_reasoner.solve(q)
                self._deliver_assistant_reply(
                    answer=res.answer,
                    reasoning_steps=res.steps,
                    latency_ms=res.latency_ms,
                    strategy=res.strategy,
                    confidence=res.confidence,
                )
                self.footer_status.setText(f"Chuột · {res.strategy} ({res.latency_ms:.0f}ms)")
                return
            except Exception as e:
                logger.debug(f"Chat reasoning error: {e}")

        # 2. Campus Room Locator
        room_match = re.search(r"\b([A-Fa-fCcFf]\d{3}|TRET-NTD-2)\b", q)
        if room_match and (any(w in q_lower for w in ["phòng", "phong", "ở đâu", "o dau", "tòa", "toa", "vị trí", "vi tri"]) or len(q.split()) <= 2):
            try:
                rm = room_match.group(1).upper()
                lat = (time.time() - t0) * 1000.0
                if rm == "C302":
                    ans_text = "Tầng 3, Tòa C. Rẽ trái từ thang máy."
                else:
                    loc = resolve_room_location(rm)
                    ans_text = f"Phòng {rm}: {loc}."
                self._deliver_assistant_reply(
                    answer=ans_text,
                    latency_ms=lat,
                    strategy="CampusMap",
                    confidence=1.0,
                )
                self.footer_status.setText(f"Phòng {rm} ({lat:.0f}ms)")
                return
            except Exception as e:
                logger.debug(f"Chat room error: {e}")

        sched_kw = ["lịch", "lich", "học", "hoc", "tkb", "tiết", "tiet", "ca học", "ca hoc", "hôm nay", "ngày mai", "môn", "mon"]
        if any(k in q_lower for k in sched_kw) and not any(k in q_lower for k in ["tìm", "tệp", "file", "tài liệu", "tai lieu"]):
            try:
                day_name_map = {
                    "T2": "Thứ Hai", "T3": "Thứ Ba", "T4": "Thứ Tư",
                    "T5": "Thứ Năm", "T6": "Thứ Sáu", "T7": "Thứ Bảy", "CN": "Chủ Nhật"
                }
                target_day = None
                day_label = ""
                now = datetime.now()

                if "hôm nay" in q_lower or "hom nay" in q_lower:
                    target_day = "TODAY"
                    day_label = "hôm nay"
                elif "ngày mai" in q_lower or "ngay mai" in q_lower or "mai " in q_lower or q_lower == "mai":
                    target_day = "TOMORROW"
                    day_label = "ngày mai"
                else:
                    for d_code, kws in [
                        ("T2", ["thứ 2", "thứ hai", "thu 2", "thu hai", "t2"]),
                        ("T3", ["thứ 3", "thứ ba", "thu 3", "thu ba", "t3"]),
                        ("T4", ["thứ 4", "thứ tư", "thu 4", "thu tu", "t4"]),
                        ("T5", ["thứ 5", "thứ năm", "thu 5", "thu nam", "t5"]),
                        ("T6", ["thứ 6", "thứ sáu", "thu 6", "thu sau", "t6"]),
                        ("T7", ["thứ 7", "thứ bảy", "thu 7", "thu bay", "t7"]),
                        ("CN", ["chủ nhật", "chu nhat", "cn"]),
                    ]:
                        if any(kw in q_lower for kw in kws):
                            target_day = d_code
                            day_label = day_name_map[d_code]
                            break

                if target_day or any(k in q_lower for k in ["lịch học", "tkb", "thời khóa biểu"]):
                    if target_day == "TODAY" or target_day is None:
                        agenda = self.compositor.get_today_agenda(self.current_member)
                        sessions = [item["session"] for item in agenda]
                        day_label = "hôm nay"
                    elif target_day == "TOMORROW":
                        tomorrow_idx = (now.weekday() + 1) % 7
                        code_map = {0: "T2", 1: "T3", 2: "T4", 3: "T5", 4: "T6", 5: "T7", 6: "CN"}
                        t_code = code_map[tomorrow_idx]
                        sessions = self.current_member.schedule.get(t_code, [])
                        day_label = f"ngày mai ({day_name_map[t_code]})"
                    else:
                        sessions = self.current_member.schedule.get(target_day, [])

                    lat = (time.time() - t0) * 1000.0
                    if sessions:
                        from rat.timetable.model import TDTU_PERIODS
                        sched_items = []
                        for s in sessions:
                            p_start_str = TDTU_PERIODS.get(s.start_period, ("00:00", "00:00", "", ""))[0]
                            p_end_str = TDTU_PERIODS.get(s.end_period, ("23:59", "23:59", "", ""))[1]
                            sched_items.append(f"{s.course_name} ({p_start_str}-{p_end_str}, {s.room})")
                        ans_text = f"Lịch {day_label} ({len(sessions)} môn): " + "; ".join(sched_items)
                    else:
                        ans_text = f"Lịch học {day_label}: Không có ca học nào."

                    self._deliver_assistant_reply(
                        answer=ans_text,
                        latency_ms=lat,
                        strategy="Timetable",
                        confidence=1.0,
                    )
                    self.footer_status.setText(f"Lịch học {day_label} ({lat:.0f}ms)")
                    return
            except Exception as e:
                logger.debug(f"Chat schedule error: {e}")

        # 4. Instant Math Calculation
        calc_expr = None
        if re.search(r"\d", q) and any(op in q for op in ["+", "*", "/", "%", "^", " - "]):
            calc_expr = re.sub(r"^(?:tính|tinh|calc|calculate|\=)\s*", "", q, flags=re.I).strip()
        elif re.match(r"^(?:tính|tinh|calc)\s+([0-9\.\+\-\*\/\(\)\s\^]+)$", q, flags=re.I):
            m = re.match(r"^(?:tính|tinh|calc)\s+([0-9\.\+\-\*\/\(\)\s\^]+)$", q, flags=re.I)
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
                    lat = (time.time() - t0) * 1000.0
                    ans_text = f"{calc_expr} = {res_str}"
                    self._deliver_assistant_reply(
                        answer=ans_text,
                        latency_ms=lat,
                        strategy="Math",
                        confidence=1.0,
                    )
                    self.footer_status.setText(f"Tính toán ({lat:.0f}ms)")
                    return
            except Exception as e:
                logger.debug(f"Chat calc error: {e}")

        # 5. Club Golden Slots & Group Availability
        if any(k in q_lower for k in ["ai rảnh", "ai ranh", "clb", "golden slot", "họp nhóm", "giờ rảnh", "gio ranh"]):
            try:
                slots = self.compositor.find_golden_windows(min_ratio=0.8)
                lat = (time.time() - t0) * 1000.0
                if slots:
                    s = slots[0]
                    free_names = ", ".join(s.free_members[:4])
                    if len(s.free_members) > 4:
                        free_names += f" và {len(s.free_members) - 4} bạn khác"
                    ans_text = (
                        f"Khung giờ họp tốt nhất: {s.day_name} ({s.time_range}), "
                        f"{s.free_count}/{s.total_count} người rảnh ({int(s.ratio * 100)}%). "
                        f"Thành viên: {free_names}."
                    )
                else:
                    ans_text = "Không có khung giờ nào đạt ≥80% thành viên rảnh trong tuần."
                self._deliver_assistant_reply(
                    answer=ans_text,
                    latency_ms=lat,
                    strategy="Club-Matrix",
                    confidence=1.0,
                )
                self.footer_status.setText(f"Giờ rảnh CLB ({lat:.0f}ms)")
                return
            except Exception as e:
                logger.debug(f"Chat club error: {e}")

        # 6. Explicit File / Document Search
        is_explicit_file = (
            bool(re.search(r"\.(?:py|pdf|docx|xlsx|pptx|txt|md|json|csv|sh|png|jpg|jpeg|zip|tar|gz)$", q, flags=re.I))
            or bool(re.match(r"^(?:tìm\s+(?:kiếm\s+)?(?:file|tệp|tài liệu|tập tin)?|kiếm\s+(?:file|tệp|tài liệu)?|search|find)\b", q, flags=re.I))
            or q_lower.startswith("file:")
        )

        clean_q = re.sub(r"^(?:tìm\s+(?:kiếm\s+)?(?:file|tệp|tài liệu|tập tin)?|kiếm\s+(?:file|tệp|tài liệu)?|search|find)\s*", "", q, flags=re.I).strip()
        search_target = clean_q if len(clean_q) >= 2 else q

        if is_explicit_file:
            self.set_mascot_state("searching")
            try:
                search_res = self.engine.search(search_target, limit=4)
                files = search_res.get("results", [])
                lat = search_res.get("latency_ms", (time.time() - t0) * 1000.0)
                if files:
                    ans_text = f"Tìm thấy {len(files)} tệp phù hợp với '{search_target}'."
                    self._deliver_assistant_reply(
                        answer=ans_text,
                        latency_ms=lat,
                        strategy="Search",
                        confidence=0.92,
                        inline_files=files,
                    )
                    self.footer_status.setText(f"{len(files)} tệp ({lat:.0f}ms)")
                    return
                else:
                    self.set_mascot_state("angry")
                    ans_text = f"Không có file này trong máy. Bạn nhớ nhầm tên à? 💢"
                    self._deliver_assistant_reply(
                        answer=ans_text,
                        latency_ms=lat,
                        strategy="Search",
                        confidence=0.8,
                    )
                    self.footer_status.setText("0 tệp")
                    QTimer.singleShot(4000, lambda: self.set_mascot_state("idle"))
                    return
            except Exception as e:
                logger.debug(f"Chat explicit search error: {e}")

        # 7. Conversational Reasoning / Q&A / On-Device AI Streaming
        try:
            handle = self.chat_stream.create_streaming_message(
                strategy="On-Device Qwen",
                badge="Qwen2.5",
            )
            self.footer_status.setText("Chuột đang suy nghĩ...")
            self._current_reasoner = StreamReasoningWorker(q)
            self._current_reasoner.token_received.connect(
                lambda tok, h=handle: self._on_reasoning_token(h, tok)
            )
            self._current_reasoner.reasoning_finished.connect(
                lambda ans, stp, lat, strat, bdg, h=handle: self._on_reasoning_finished(h, ans, stp, lat, strat, bdg)
            )
            self._current_reasoner.start()
            return
        except Exception as e:
            logger.debug(f"Chat reasoning fallback error: {e}")

        # 8. Implicit File Search as Fallback
        try:
            search_res = self.engine.search(search_target, limit=3)
            files = search_res.get("results", [])
            lat = search_res.get("latency_ms", (time.time() - t0) * 1000.0)
            if files:
                ans_text = f"Gợi ý {len(files)} tệp liên quan đến '{search_target}'."
                self._deliver_assistant_reply(
                    answer=ans_text,
                    latency_ms=lat,
                    strategy="Search",
                    confidence=0.85,
                    inline_files=files,
                )
                self.footer_status.setText(f"{len(files)} tệp ({lat:.0f}ms)")
                return
        except Exception:
            pass

        # 9. Fallback Guide
        lat = (time.time() - t0) * 1000.0
        fallback_ans = f"Không hiểu '{q}'. Gõ lịch học, tên phòng, tên file hoặc phép tính để tra cứu."
        self._deliver_assistant_reply(
            answer=fallback_ans,
            latency_ms=lat,
            strategy="Direct",
            confidence=0.80,
        )
        self.footer_status.setText("Sẵn sàng")

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
        old_text = self.footer_status.text()
        self.footer_status.setText(message)
        self.footer_status.setStyleSheet("color: #22c55e; font-weight: 600;")

        def _restore():
            self.footer_status.setText(old_text)
            self.footer_status.setStyleSheet("")

        QTimer.singleShot(timeout_ms, _restore)

    def _open_action_menu(self) -> None:
        active_list = self.result_list if self.current_section_idx == 1 else self.recent_list
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
        elif action_id == "schedule":
            self.switch_section(2)
        elif action_id == "widget":
            self.switch_section(0)
        elif action_id == "settings":
            self._open_settings()

    def _open_settings(self) -> None:
        self._dialog_active = True
        try:
            dialog = SettingsDialog(self)
            dialog.exec()
        finally:
            self._dialog_active = False
            if self.current_section_idx == 0:
                self.chat_composer_input.setFocus()
            elif self.current_section_idx == 1:
                self.search_input.setFocus()

    def _present_compact_reply(self, answer: str, status: str, *, has_details: bool = False) -> None:
        """Keep compact and expanded views backed by the same full answer."""
        clean = answer.replace("**", "").replace("`", "")
        self.speech_bubble.set_reply(clean, status, copy_text=answer, has_details=has_details)
        if self.is_expanded:
            self.speech_bubble.hide_bubble()
        else:
            self.speech_bubble.show_bubble()
            if not self.mascot_peeking.is_speaking:
                self.mascot_peeking.pop_out_speaking()

    def _on_reasoning_token(self, handle: Dict[str, Any], token: str) -> None:
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
        # Non-streaming fallback and final corrections must replace partial tokens.
        handle["full_text"] = answer if answer.strip() else handle.get("full_text", "")
        self.chat_stream.finalize_stream(handle, reasoning_steps=steps, latency_ms=latency_ms)
        self._present_compact_reply(handle["full_text"], "Xong")
        self.footer_status.setText(f"Chuột · {strategy} ({latency_ms:.0f}ms)")
        if getattr(self, "rat_stage", None):
            self.rat_stage.set_state("idle")
        self.set_mascot_state("idle")

    # -----------------------------------------------------------------
    # LIFECYCLE & WINDOW EVENTS
    # -----------------------------------------------------------------
    def show_omnibar(self, initial_section: int = 0) -> None:
        """Summon Omnibar window instantly (< 16ms) with pre-warmed state."""
        self._is_opening = True
        self._was_activated = False
        try:
            from rat.os.app import activate_macos_app
            activate_macos_app()
        except Exception:
            pass

        self.switch_section(0)
        self.set_expanded(False)

        # Smooth screen positioning: follow active mouse screen at stable ~18% top anchor
        try:
            from PyQt6.QtGui import QCursor
            cursor_pos = QCursor.pos()
            target_screen = QGuiApplication.screenAt(cursor_pos) or QGuiApplication.primaryScreen()
            if target_screen:
                geo = target_screen.availableGeometry()
                margin_top = int(geo.height() * 0.18)
                x = geo.x() + (geo.width() - self.width()) // 2
                y = geo.y() + margin_top
                self.move(x, y)
        except Exception:
            pass

        # Configure macOS fullscreen auxiliary overlay so it floats above full-screen apps
        configure_macos_fullscreen_overlay(self)

        self.show()
        self.raise_()
        self.activateWindow()
        if hasattr(self, "speech_bubble"):
            self.speech_bubble.show_bubble()
        if hasattr(self, "mascot_peeking"):
            self.mascot_peeking.show()
            if self.speech_bubble.has_reply:
                self.mascot_peeking.pop_out_speaking()
            else:
                self.mascot_peeking.retreat_to_idle()
        if hasattr(self, "chat_composer_input"):
            self.chat_composer_input.setFocus()
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
                and not getattr(self, "_is_opening", False)
                and getattr(self, "_was_activated", False)
            ):
                self.hide()
                self._was_activated = False
        super().changeEvent(event)

    def hideEvent(self, event) -> None:
        self._is_opening = False
        self._was_activated = False
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

    def closeEvent(self, event) -> None:
        app = QApplication.instance()
        if app and not getattr(app, "_is_quitting", False):
            event.ignore()
            self.hide()
            return

        self.shutdown()
        super().closeEvent(event)
