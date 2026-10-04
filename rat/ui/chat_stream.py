"""Quiet conversation cards, optional processing metadata and inline results."""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from rat.engine.reranker import SearchResultItem
from rat.ui.compact_results import CompactFileRow
from rat.ui.preview_panel import trigger_quicklook
from rat.ui.reply_text import ConversationReplyBody
from rat.ui.theme import CHAT_ACTION_QSS, CHAT_CARD_QSS, CHAT_COLORS, CHAT_JUMP_QSS, CHAT_USER_QSS

MASCOT_PATH = Path(__file__).resolve().parent.parent / "assets" / "rat_mascot_cutout.png"
MASCOT_BUST_PATH = Path(__file__).resolve().parent.parent / "assets" / "rat_mascot_bust.png"


def get_mascot_pixmap(w: int, h: int, bust_only: bool = True) -> Optional[QPixmap]:
    target_path = MASCOT_BUST_PATH if (bust_only and MASCOT_BUST_PATH.exists()) else MASCOT_PATH
    if not target_path.exists():
        fallback = Path(__file__).resolve().parent.parent / "assets" / "rat_mascot.png"
        if fallback.exists():
            target_path = fallback
    if target_path.exists():
        pm = QPixmap(str(target_path))
        if not pm.isNull():
            return pm.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return None


def open_file_default(file_path: str) -> None:
    if not os.path.exists(file_path):
        return
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["open", file_path])
    elif system == "Windows":
        os.startfile(file_path)
    else:
        subprocess.run(["xdg-open", file_path])


def reveal_in_finder(file_path: str) -> None:
    if not os.path.exists(file_path):
        return
    system = platform.system()
    if system == "Darwin":
        subprocess.run(["open", "-R", file_path])
    elif system == "Windows":
        subprocess.run(["explorer", "/select,", os.path.normpath(file_path)])
    else:
        parent_dir = str(Path(file_path).parent)
        subprocess.run(["xdg-open", parent_dir])


class MessageDetails(QFrame):
    """Caller-supplied metadata, not a claim about the model's private reasoning."""

    def __init__(self, steps: List[str], latency_ms: float = 0.0,
                 model: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("MessageDetails")
        self.setStyleSheet(f"""
            QFrame#MessageDetails {{ background: {CHAT_COLORS['tint']};
                border: 1px solid {CHAT_COLORS['border']}; border-radius: 7px; }}
            QLabel {{ color: {CHAT_COLORS['secondary']}; font-size: 11px;
                background: transparent; border: none; }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 7, 9, 7)
        layout.setSpacing(5)
        summary = []
        if model:
            summary.append(f"Mô hình: {model}")
        if latency_ms > 0:
            summary.append(f"Thời gian: {latency_ms:.0f} ms")
        lines = ([" · ".join(summary)] if summary else []) + [
            f"{index + 1}. {step}" for index, step in enumerate(steps)
        ]
        for text in lines:
            label = QLabel(text)
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(label)
        self.hide()


class InlineFileCard(CompactFileRow):
    """The expanded conversation uses the same restrained, actionable file row."""

    def __init__(self, item: SearchResultItem, parent: Optional[QWidget] = None) -> None:
        super().__init__(item, parent)
        self.open_requested.connect(lambda result: open_file_default(result.file_path))
        self.reveal_requested.connect(lambda result: reveal_in_finder(result.file_path))
        self.preview_requested.connect(lambda result: trigger_quicklook(result.file_path))


class UserMessageRow(QWidget):
    """Right-aligned bubble sized to the text, then capped to the available width."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self._text = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Maximum)
        self._width_timer = QTimer(self)
        self._width_timer.setSingleShot(True)
        self._width_timer.timeout.connect(self._sync_width)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.addStretch()
        self.bubble = QFrame()
        self.bubble.setObjectName("UserBubble")
        self.bubble.setStyleSheet(CHAT_USER_QSS)
        self.bubble.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Maximum)
        bubble_layout = QVBoxLayout(self.bubble)
        bubble_layout.setContentsMargins(10, 7, 10, 7)
        self.label = QLabel(text)
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setWordWrap(True)
        self.label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bubble_layout.addWidget(self.label)
        layout.addWidget(self.bubble, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._width_timer.start(0)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._width_timer.start(0)

    def _sync_width(self) -> None:
        self.label.ensurePolished()
        natural_width = max((self.label.fontMetrics().horizontalAdvance(line)
                             for line in self._text.splitlines()), default=0) + 22
        width = min(460, max(32, self.width() - 24), max(32, natural_width))
        if self.bubble.width() != width:
            self.bubble.setFixedWidth(width)


class ChatStreamWidget(QScrollArea):
    """Conversation and inline results; the main mascot lives outside the reader."""
    prompt_clicked = pyqtSignal(str)
    navigation_widget_created = pyqtSignal(QWidget)

    def __init__(self, user_name: str = "Huy", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.user_name = user_name
        self._message_count = 0
        self._follow_latest = True
        self._has_unseen_reply = False
        self._last_scroll_value = 0
        self._programmatic_scroll = False
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.timeout.connect(self._scroll_to_bottom_now)
        # Late Qt layout changes follow only while the reader stays at the end.
        self.verticalScrollBar().rangeChanged.connect(self._on_scroll_range_changed)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll_value_changed)
        self.verticalScrollBar().sliderPressed.connect(self._pause_following)
        self.verticalScrollBar().actionTriggered.connect(self._on_scroll_action)
        self._init_ui()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._follow_latest:
            self._scroll_to_bottom()
        self._update_jump_button()

    def wheelEvent(self, event) -> None:
        if event.angleDelta().y() > 0 or event.pixelDelta().y() > 0:
            self._pause_following()
        super().wheelEvent(event)

    def _init_ui(self) -> None:
        self.setObjectName("ChatStreamWidget")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.viewport().setStyleSheet("background: transparent;")
        self.setStyleSheet("""
            QScrollArea#ChatStreamWidget {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 5px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 0, 0, 0.15);
                min-height: 20px;
                border-radius: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(0, 0, 0, 0.30);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(2, 4, 8, 4)
        self.layout.setSpacing(10)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.setWidget(self.container)
        self.jump_button = QPushButton("↓ Về cuối", self.viewport())
        self.jump_button.setObjectName("JumpToLatest")
        self.jump_button.setStyleSheet(CHAT_JUMP_QSS)
        self.jump_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.jump_button.setToolTip("Về cuối hội thoại và theo dõi câu trả lời mới")
        self.jump_button.setAccessibleName("Về cuối hội thoại")
        self.jump_button.clicked.connect(self._jump_to_latest)
        self.jump_button.hide()
        self._render_welcome_state()

    def is_empty(self) -> bool:
        return self._message_count == 0

    def _render_welcome_state(self) -> None:
        """Cozy, tactile welcome state with tongue-in-cheek suggestions."""
        self.welcome_widget = QWidget()
        self.welcome_widget.setObjectName("WelcomeCard")
        w_layout = QVBoxLayout(self.welcome_widget)
        w_layout.setContentsMargins(16, 20, 16, 16)
        w_layout.setSpacing(10)
        w_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Mascot Avatar or Icon Header
        top_row = QHBoxLayout()
        top_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.setSpacing(8)

        pm = get_mascot_pixmap(44, 44, bust_only=True)
        if pm and not pm.isNull():
            avatar_lbl = QLabel()
            avatar_lbl.setPixmap(pm)
            avatar_lbl.setFixedSize(44, 44)
            top_row.addWidget(avatar_lbl)

        header_title = QLabel("Ừ, nói đi.")
        header_title.setStyleSheet("color: #1F1A16; font-size: 16px; font-weight: 800; letter-spacing: -0.2px;")
        top_row.addWidget(header_title)
        w_layout.addLayout(top_row)

        sub_desc = QLabel("Một câu hỏi, một ý chưa rõ, hoặc một việc cần gỡ.\nMình bắt đầu từ đó.")
        sub_desc.setStyleSheet("color: #786F66; font-size: 12px; font-weight: 500; line-height: 1.45;")
        sub_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        w_layout.addWidget(sub_desc)

        # Prompt chip container (Grid of 2 columns)
        chips_frame = QFrame()
        chips_frame.setStyleSheet("""
            QFrame {
                background: transparent;
                border: none;
            }
            QPushButton.PromptSuggestionBtn {
                background-color: #FFFFFF;
                color: #3D352B;
                border: 1px solid #E2D8C8;
                border-radius: 9px;
                padding: 7px 12px;
                font-size: 11.5px;
                font-weight: 500;
                text-align: left;
            }
            QPushButton.PromptSuggestionBtn:hover {
                background-color: #FFFDF9;
                color: #1F1A16;
                border-color: #D4B872;
            }
            QPushButton.PromptSuggestionBtn:pressed {
                background-color: #EEE6D8;
            }
            QPushButton.PromptSuggestionBtn:focus {
                border-color: #B49A6B;
            }
        """)
        c_layout = QGridLayout(chips_frame)
        c_layout.setContentsMargins(0, 8, 0, 0)
        c_layout.setHorizontalSpacing(8)
        c_layout.setVerticalSpacing(8)

        prompts = [
            ("Gỡ một ý tưởng", "Giúp mình nghĩ về "),
            ("Phản biện một ý", "Phản biện giúp mình ý này: "),
            ("Tìm một tệp", "tìm file "),
            ("Lịch hôm nay", "Hôm nay học gì?"),
        ]

        for i, (btn_text, prompt_val) in enumerate(prompts):
            btn = QPushButton(btn_text)
            btn.setProperty("class", "PromptSuggestionBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, p=prompt_val: self.prompt_clicked.emit(p))
            c_layout.addWidget(btn, i // 2, i % 2)

        w_layout.addWidget(chips_frame)

        self.layout.addWidget(self.welcome_widget, 1)
        self.viewport().update()

    def clear_chat(self) -> None:
        """Reset conversation and return to welcome state."""
        self._scroll_timer.stop()
        self._message_count = 0
        self._follow_latest = True
        self._has_unseen_reply = False
        self._last_scroll_value = 0
        self.jump_button.hide()
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        self._render_welcome_state()

    def _begin_message(self) -> None:
        if self._message_count == 0:
            self.welcome_widget.hide()
        self._message_count += 1

    def add_user_message(self, text: str) -> None:
        """Render a user prompt speech bubble."""
        self._begin_message()
        # Own the whole row as a widget so Chat mới removes user messages too.
        row = UserMessageRow(text)
        self.layout.addWidget(row)
        self.navigation_widget_created.emit(row.label)
        # Sending a new prompt is an explicit return to the active conversation.
        self._scroll_to_bottom(force=True)

    def _create_assistant_card(
        self,
        context: str,
        step_number: Optional[int] = None,
        strategy_badge: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Finished and streaming replies share the same quiet header and actions."""
        card = QFrame()
        card.setObjectName("AssistantCard")
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        card.setStyleSheet(CHAT_CARD_QSS)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        header = QHBoxLayout()
        header.setSpacing(5)
        name = QLabel("Chuột")
        name.setStyleSheet("color: #6F6456; font-size: 11px; font-weight: 600;")
        header.addWidget(name)
        if step_number and step_number > 1:
            context_label = QLabel(f"· Bước {step_number} · {context}")
        else:
            context_label = QLabel(f"· {context}")
        context_label.setStyleSheet("color: #807668; font-size: 10px;")
        header.addWidget(context_label)

        if strategy_badge:
            badge_lbl = QLabel(f"✦ {strategy_badge}")
            badge_lbl.setStyleSheet(
                "color: #92400E; background: #FEF3C7; border: 1px solid #FDE68A; "
                "font-size: 9.5px; font-weight: 600; border-radius: 4px; padding: 1px 5px;"
            )
            header.addWidget(badge_lbl)

        header.addStretch()

        details_button = QPushButton("Chi tiết")
        details_button.setCheckable(True)
        details_button.setToolTip("Thông tin xử lý của câu trả lời")
        details_button.setAccessibleName("Chi tiết xử lý")
        details_button.setAccessibleDescription("Thông tin xử lý đang thu gọn")
        copy_button = QPushButton("Sao chép")
        copy_button.setToolTip("Sao chép toàn bộ câu trả lời")
        copy_button.setEnabled(False)
        for button in (details_button, copy_button):
            button.setStyleSheet(CHAT_ACTION_QSS)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            header.addWidget(button)
        details_button.hide()
        layout.addLayout(header)

        answer_label = ConversationReplyBody()
        answer_label.wheel_scrolled.connect(self.wheelEvent)
        layout.addWidget(answer_label)
        for widget in (answer_label, details_button, copy_button):
            self.navigation_widget_created.emit(widget)

        copy_timer = QTimer(copy_button)
        copy_timer.setSingleShot(True)
        copy_timer.timeout.connect(lambda: copy_button.setText("Sao chép"))
        handle = {
            "card": card, "c_layout": layout, "header": header,
            "ans_lbl": answer_label, "copy_button": copy_button,
            "details_button": details_button, "copy_timer": copy_timer,
            "tokens": [], "full_text": "", "accordion_added": False,
        }

        def copy_reply() -> None:
            QApplication.clipboard().setText(handle["full_text"])
            copy_button.setText("Đã chép")
            copy_timer.start(1500)

        copy_button.clicked.connect(copy_reply)
        return handle

    def _add_details(self, handle: Dict[str, Any], steps: Optional[List[str]],
                     latency_ms: float, model: str = "") -> None:
        if handle.get("accordion_added") or not (steps or latency_ms > 0 or model):
            return
        panel = MessageDetails(steps or [], latency_ms, model, handle["card"])
        handle["c_layout"].addWidget(panel)
        handle["details_panel"] = panel
        handle["accordion_added"] = True
        button = handle["details_button"]

        def toggle_details(expanded: bool) -> None:
            panel.setVisible(expanded)
            button.setText("Thu chi tiết" if expanded else "Chi tiết")
            button.setAccessibleDescription(
                "Thông tin xử lý đang mở" if expanded else "Thông tin xử lý đang thu gọn"
            )

        button.toggled.connect(toggle_details)
        button.show()

    def add_assistant_message(
        self,
        answer: str,
        reasoning_steps: Optional[List[str]] = None,
        latency_ms: float = 0.0,
        strategy: str = "Meta-RL",
        confidence: float = 0.95,
        inline_files: Optional[List[SearchResultItem]] = None,
        custom_widget: Optional[QWidget] = None,
        step_number: Optional[int] = None,
        step_suggestions: Optional[List[str]] = None,
    ) -> None:
        """Render an assistant response without elevating secondary metadata."""
        self._begin_message()
        context = {"Search": "Tìm tệp", "Math": "Tính nhanh", "Timetable": "Lịch học"}.get(strategy, "Trả lời")
        strat_badge = strategy if strategy not in ("Direct", "Trả lời", "Meta-RL") else None
        handle = self._create_assistant_card(context, step_number=step_number, strategy_badge=strat_badge)
        card, c_layout = handle["card"], handle["c_layout"]
        handle["full_text"] = answer
        handle["ans_lbl"].setText(answer)
        handle["copy_button"].setEnabled(bool(answer))

        # Optional Custom Widget (e.g. Agenda, Room guide, Math card)
        if custom_widget is not None:
            c_layout.addWidget(custom_widget)

        # Optional Inline File Cards (for file search responses)
        if inline_files and len(inline_files) > 0:
            files_box = QVBoxLayout()
            files_box.setSpacing(4)
            for f_item in inline_files[:4]:
                file_card = InlineFileCard(f_item)
                files_box.addWidget(file_card)
            c_layout.addLayout(files_box)

        # Optional Contextual Follow-up Suggestions
        if step_suggestions and len(step_suggestions) > 0:
            sugg_row = QWidget()
            sugg_row.setObjectName("StepSuggestionsRow")
            sugg_layout = QHBoxLayout(sugg_row)
            sugg_layout.setContentsMargins(0, 4, 0, 2)
            sugg_layout.setSpacing(6)
            hint_lbl = QLabel("Gợi ý bước tiếp:")
            hint_lbl.setStyleSheet("color: #9C9182; font-size: 10px; font-weight: 500;")
            sugg_layout.addWidget(hint_lbl)
            for chip_text in step_suggestions[:3]:
                chip_btn = QPushButton(chip_text)
                chip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                chip_btn.setStyleSheet("""
                    QPushButton {
                        background: #F8F5EE;
                        border: 1px solid #E2D9CB;
                        border-radius: 6px;
                        color: #4A4237;
                        font-size: 10.5px;
                        font-weight: 500;
                        padding: 3px 8px;
                    }
                    QPushButton:hover {
                        background: #ECE5D6;
                        border-color: #CFC3AF;
                        color: #1F1B16;
                    }
                """)
                chip_btn.clicked.connect(lambda checked=False, t=chip_text: self.prompt_clicked.emit(t))
                sugg_layout.addWidget(chip_btn)
            sugg_layout.addStretch()
            c_layout.addWidget(sugg_row)

        self._add_details(handle, reasoning_steps, latency_ms)
        self.layout.addWidget(card)
        self._reply_changed()

    def _pause_following(self) -> None:
        if self.verticalScrollBar().maximum() == 0:
            return
        self._follow_latest = False
        self._scroll_timer.stop()
        self._update_jump_button()

    def _on_scroll_action(self, action: int) -> None:
        # Slider actions precede valueChanged; cancel an already scheduled follow.
        scrollbar = self.verticalScrollBar()
        if scrollbar.sliderPosition() < scrollbar.maximum() - 4:
            self._pause_following()

    def _on_scroll_value_changed(self, value: int) -> None:
        if not self._programmatic_scroll:
            if self.verticalScrollBar().maximum() - value <= 4:
                self._follow_latest = True
                self._has_unseen_reply = False
            elif value < self._last_scroll_value:
                self._pause_following()
        self._last_scroll_value = value
        self._update_jump_button()

    def _reply_changed(self) -> None:
        if self._follow_latest:
            self._scroll_to_bottom()
        else:
            self._has_unseen_reply = True
            self._update_jump_button()

    def _jump_to_latest(self) -> None:
        if self.jump_button.hasFocus():
            # Hiding a focused button must not focus/scroll the first old reply.
            self.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._scroll_to_bottom(force=True)

    def _scroll_to_bottom(self, force: bool = False) -> None:
        if force:
            self._follow_latest = True
            self._has_unseen_reply = False
        if not self._follow_latest:
            return
        self._update_jump_button()
        self._scroll_timer.start(10)

    def _on_scroll_range_changed(self, minimum: int, maximum: int) -> None:
        if maximum == 0:
            self._follow_latest = True
            self._has_unseen_reply = False
        if self._follow_latest:
            self._scroll_timer.start(0)
        self._update_jump_button()

    def _scroll_to_bottom_now(self) -> None:
        if not self._follow_latest:
            return
        sb = self.verticalScrollBar()
        self._programmatic_scroll = True
        sb.setValue(sb.maximum())
        self._programmatic_scroll = False
        self._update_jump_button()

    def _update_jump_button(self) -> None:
        if not hasattr(self, "jump_button"):
            return
        show = not self._follow_latest and self.verticalScrollBar().maximum() > 0
        self.jump_button.setText("↓ Phản hồi mới" if self._has_unseen_reply else "↓ Về cuối")
        self.jump_button.setAccessibleDescription(
            "Có nội dung mới ở cuối hội thoại" if self._has_unseen_reply else "Quay lại cuối hội thoại"
        )
        self.jump_button.adjustSize()
        self.jump_button.move(max(4, self.viewport().width() - self.jump_button.width() - 12),
                              max(4, self.viewport().height() - self.jump_button.height() - 10))
        self.jump_button.setVisible(show)
        if show:
            self.jump_button.raise_()

    def create_streaming_message(
        self,
        strategy: str = "On-Device Qwen",
        badge: str = "Qwen2.5 (Metal)",
    ) -> Dict[str, Any]:
        """Create a card with hidden model metadata and a pending-state label."""
        self._begin_message()
        handle = self._create_assistant_card("Trả lời")
        card, c_layout = handle["card"], handle["c_layout"]
        # Retain the worker's badge handle, but only show it inside Chi tiết.
        sub_tag = QLabel(f"· {badge}", card)
        sub_tag.hide()
        status_lbl = QLabel("Chuột đang suy nghĩ...")
        status_lbl.setStyleSheet("color: #807668; font-size: 12px; font-style: italic;")
        c_layout.insertWidget(1, status_lbl)
        handle["ans_lbl"].hide()
        handle.update({"status_lbl": status_lbl, "badge_lbl": sub_tag})
        self.layout.addWidget(card)
        self._reply_changed()
        return handle

    def append_stream_token(self, handle: Dict[str, Any], token: str) -> None:
        """Append streamed token and update message live with smooth scrolling."""
        handle["tokens"].append(token)
        handle["full_text"] += token

        status_lbl = handle["status_lbl"]
        # Compact mode hides the parent; isVisible() is false even for an
        # explicitly shown status. Hide it regardless before expanding later.
        status_lbl.hide()

        ans_lbl = handle["ans_lbl"]
        if not ans_lbl.isVisible():
            ans_lbl.show()

        ans_lbl.setText(handle["full_text"])
        self._reply_changed()

    def finalize_stream(
        self,
        handle: Dict[str, Any],
        reasoning_steps: Optional[List[str]] = None,
        latency_ms: float = 0.0,
    ) -> None:
        """Finish the existing card; its metadata stays collapsed by default."""
        ans_lbl = handle["ans_lbl"]
        full_text = handle["full_text"]

        ans_lbl.setText(full_text)
        ans_lbl.show()

        status_lbl = handle["status_lbl"]
        status_lbl.hide()

        self._add_details(handle, reasoning_steps, latency_ms,
                          handle["badge_lbl"].text().removeprefix("· "))
        handle["copy_button"].setEnabled(bool(full_text))
        self._reply_changed()
