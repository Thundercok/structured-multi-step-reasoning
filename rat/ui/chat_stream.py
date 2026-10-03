"""
rat.ui.chat_stream — Minimalist Conversational AI Chat Stream Widget.
Features:
- macOS Sequoia Liquid Glass styling (translucent frosted acrylic, specular highlights)
- Conversational message bubbles (User & Assistant)
- Collapsible Thinking Process Accordion (Chain-of-Thought / Escalation)
- Inline embedded interactive cards (Agenda, File results, Campus navigation, Math)
- Minimalist welcome empty state with clickable prompt chips
"""

from __future__ import annotations

import html
import os
import platform
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QCursor, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from rat.engine.reasoning_trace import ReasoningTrace
from rat.engine.reranker import SearchResultItem
from rat.ui.theme import get_ext_badge_info

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


class ThinkingAccordion(QFrame):
    """Collapsible Thinking Process Card (CoT / Escalation Ladder)."""

    def __init__(self, steps: List[str], latency_ms: float = 0.0, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.steps = steps
        self.is_expanded = False
        self._init_ui(latency_ms)

    def _init_ui(self, latency_ms: float) -> None:
        self.setObjectName("ThinkingAccordion")
        self.setStyleSheet("""
            QFrame#ThinkingAccordion {
                background-color: #F8F5F0;
                border: 1px dashed #C8BDB0;
                border-radius: 8px;
                padding: 6px 10px;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(4)

        # Header Toggle Row
        self.latency_ms = latency_ms
        lat_txt = f" ({int(self.latency_ms)}ms)" if self.latency_ms > 0 else ""
        self._header_prefix = f"🧀 Xem Chuột suy nghĩ · {len(self.steps)} bước{lat_txt}"
        self.header_btn = QPushButton(f"{self._header_prefix}  ▸")
        self.header_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #2B261F;
                font-size: 11.5px;
                font-weight: 800;
                text-align: left;
                padding: 2px 0px;
            }
            QPushButton:hover {
                color: #FFA000;
            }
        """)
        self.header_btn.clicked.connect(self._toggle_expanded)
        self.main_layout.addWidget(self.header_btn)

        # Steps container (collapsed by default)
        self.steps_container = QWidget()
        self.steps_layout = QVBoxLayout(self.steps_container)
        self.steps_layout.setContentsMargins(4, 4, 4, 4)
        self.steps_layout.setSpacing(4)

        for idx, step_txt in enumerate(self.steps):
            step_lbl = QLabel(f"<b>Bước {idx + 1}:</b> {step_txt}")
            step_lbl.setStyleSheet("color: #2B261F; font-size: 11px; line-height: 1.4;")
            step_lbl.setWordWrap(True)
            step_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.steps_layout.addWidget(step_lbl)

        self.steps_container.hide()
        self.main_layout.addWidget(self.steps_container)

    def _toggle_expanded(self) -> None:
        self.is_expanded = not self.is_expanded
        arrow = "▾" if self.is_expanded else "▸"
        self.header_btn.setText(f"{self._header_prefix}  {arrow}")
        self.steps_container.setVisible(self.is_expanded)


class InlineFileCard(QFrame):
    """Skeuomorphic Inline File Card inside the chat stream."""

    def __init__(self, item: SearchResultItem, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.item = item
        self._init_ui()

    def _init_ui(self) -> None:
        self.setObjectName("InlineFileCard")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(6)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(43, 38, 31, 22))
        self.setGraphicsEffect(shadow)

        self.setStyleSheet("""
            QFrame#InlineFileCard {
                background-color: #FFFDF9;
                border: 1.5px solid #D8CFBE;
                border-bottom: 2px solid #C4B8A4;
                border-radius: 9px;
                padding: 7px 10px;
            }
            QFrame#InlineFileCard:hover {
                background-color: #FFF9E8;
                border-color: #DEC88E;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # File Badge
        badge_info = get_ext_badge_info(self.item.file_ext)
        badge_lbl = QLabel(badge_info["label"])
        badge_lbl.setFixedSize(28, 20)
        badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_lbl.setStyleSheet(f"""
            background-color: {badge_info['bg']};
            color: {badge_info['fg']};
            font-size: 9px;
            font-weight: 700;
            border-radius: 4px;
            border: 1px solid rgba(0,0,0,0.15);
        """)
        layout.addWidget(badge_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        # Info
        info_col = QVBoxLayout()
        info_col.setSpacing(2)

        name_lbl = QLabel(self.item.file_name)
        name_lbl.setStyleSheet("color: #1c1917; font-size: 12px; font-weight: 700;")
        info_col.addWidget(name_lbl)

        p = self.item.file_path
        if len(p) > 50:
            p = "..." + p[-46:]
        sub_lbl = QLabel(f"{p}  •  {self.item.file_size_formatted}")
        sub_lbl.setStyleSheet("color: #78716c; font-size: 10px;")
        info_col.addWidget(sub_lbl)
        layout.addLayout(info_col, 1)

        # Action Buttons
        btn_open = QPushButton("Mở")
        btn_open.setStyleSheet("""
            QPushButton {
                background-color: #f7e4ae;
                color: #59451f;
                border: 1px solid #e0be68;
                border-radius: 7px;
                padding: 4px 10px;
                font-size: 10.5px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #fbeec4;
            }
            QPushButton:pressed {
                background-color: #f0d78d;
            }
        """)
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.clicked.connect(lambda: open_file_default(self.item.file_path))
        layout.addWidget(btn_open)

        btn_find = QPushButton("Hiện trong Finder")
        btn_find.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #70665c;
                border: 1px solid #e0d8ce;
                border-radius: 7px;
                padding: 4px 9px;
                font-size: 10.5px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #f6f1ea;
            }
            QPushButton:pressed {
                background-color: #eee8df;
            }
        """)
        btn_find.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_find.clicked.connect(lambda: reveal_in_finder(self.item.file_path))
        layout.addWidget(btn_find)


class MascotBackdrop(QWidget):
    """Transparent container widget inside ChatStreamWidget scroll area."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_ambient_mascot(self, visible: bool) -> None:
        pass  # Watermark is handled by viewportEvent for stationary pin


class ChatStreamWidget(QScrollArea):
    """
    Conversational AI Chat Stream Widget.
    Renders message stream, thinking ladder accordions, and interactive inline cards.
    Pins the rat mascot watermark to the viewport background when active.
    """
    prompt_clicked = pyqtSignal(str)

    def __init__(self, user_name: str = "Huy", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.user_name = user_name
        self._message_count = 0
        self._mascot_pixmap = QPixmap(str(MASCOT_PATH)) if MASCOT_PATH.exists() else QPixmap()
        self._show_watermark = False
        self._init_ui()

    def viewportEvent(self, event: object) -> bool:
        res = super().viewportEvent(event)
        # Pin cute rat watermark to the bottom-right of viewport when active
        if getattr(event, "type", None) and event.type() == QEvent.Type.Paint:
            if getattr(self, "_show_watermark", False) and not self._mascot_pixmap.isNull():
                vp = self.viewport()
                painter = QPainter(vp)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                painter.setOpacity(0.08)
                mascot = self._mascot_pixmap.scaled(
                    260,
                    290,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = vp.width() - mascot.width() - 16
                y = vp.height() - mascot.height() - 10
                painter.drawPixmap(x, y, mascot)
                painter.end()
        return res

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

        self.container = MascotBackdrop()
        self.container.setStyleSheet("background: transparent;")
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(14, 8, 14, 8)
        self.layout.setSpacing(10)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.setWidget(self.container)
        self._render_welcome_state()

    def is_empty(self) -> bool:
        return self._message_count == 0

    def _render_welcome_state(self) -> None:
        """Cozy, tactile welcome state with tongue-in-cheek suggestions."""
        self._show_watermark = False
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

        header_title = QLabel("Chuột nghe đây! 🧀")
        header_title.setStyleSheet("color: #1F1A16; font-size: 16px; font-weight: 800; letter-spacing: -0.2px;")
        top_row.addWidget(header_title)
        w_layout.addLayout(top_row)

        sub_desc = QLabel("Hỏi lịch học, tìm phòng C302, bới file cũ hay tính toán...\nCứ gõ tự nhiên, đừng hỏi bài tập lớn sát deadline là được nha.")
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
                border-bottom: 2px solid #CFC4B2;
                border-radius: 9px;
                padding: 7px 12px;
                font-size: 11.5px;
                font-weight: 650;
                text-align: left;
            }
            QPushButton.PromptSuggestionBtn:hover {
                background-color: #FFFDF9;
                color: #1F1A16;
                border-color: #D4B872;
                border-bottom: 2px solid #C49F4E;
            }
            QPushButton.PromptSuggestionBtn:pressed {
                background-color: #FEE8A2;
                border-bottom: 1px solid #D4B872;
                padding-top: 8px;
                padding-bottom: 6px;
            }
        """)
        c_layout = QGridLayout(chips_frame)
        c_layout.setContentsMargins(0, 8, 0, 0)
        c_layout.setHorizontalSpacing(8)
        c_layout.setVerticalSpacing(8)

        prompts = [
            ("📅 Hôm nay tui có học môn gì?", "Hôm nay tôi có học môn gì không?"),
            ("📍 Phòng C302 ở đâu vậy Chuột?", "Phòng C302 ở đâu?"),
            ("📂 Tìm slide bài giảng gần nhất", "Tìm slide bài giảng gần đây"),
            ("⚡ Tính CPA tích lũy 7.20", "Tính CPA tích lũy 64 tín chỉ điểm 7.20 học thêm 4 môn"),
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
        self._message_count = 0
        self._show_watermark = False
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._render_welcome_state()
        self.viewport().update()

    def add_user_message(self, text: str) -> None:
        """Render a user prompt speech bubble."""
        if self._message_count == 0 and hasattr(self, "welcome_widget"):
            self.welcome_widget.hide()
            self._show_watermark = True
            self.viewport().update()

        self._message_count += 1

        bubble_row = QHBoxLayout()
        bubble_row.setContentsMargins(0, 2, 0, 2)
        bubble_row.addStretch()

        bubble = QFrame()
        bubble.setObjectName("UserBubble")
        bubble.setMaximumWidth(460)
        bubble.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        b_shadow = QGraphicsDropShadowEffect(bubble)
        b_shadow.setBlurRadius(6)
        b_shadow.setOffset(0, 2)
        b_shadow.setColor(QColor(43, 38, 31, 14))
        bubble.setGraphicsEffect(b_shadow)
        bubble.setStyleSheet("""
            QFrame#UserBubble {
                background-color: #F4EFE6;
                border: 1px solid #DECFC0;
                border-bottom: 2px solid #CCC0B0;
                border-radius: 13px;
                border-bottom-right-radius: 3px;
                padding: 8px 14px;
            }
            QLabel {
                color: #1F1A16;
                font-size: 13px;
                font-weight: 550;
                border: none;
                background: transparent;
            }
        """)

        b_layout = QVBoxLayout(bubble)
        b_layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        b_layout.addWidget(lbl)

        bubble_row.addWidget(bubble, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        self.layout.addLayout(bubble_row)
        self._scroll_to_bottom()

    def add_assistant_message(
        self,
        answer: str,
        reasoning_steps: Optional[List[str]] = None,
        latency_ms: float = 0.0,
        strategy: str = "Meta-RL",
        confidence: float = 0.95,
        inline_files: Optional[List[SearchResultItem]] = None,
        custom_widget: Optional[QWidget] = None,
    ) -> None:
        """Render an AI Assistant response with thinking process and rich cards."""
        if self._message_count == 0 and hasattr(self, "welcome_widget"):
            self.welcome_widget.hide()
            self._show_watermark = True
            self.viewport().update()

        self._message_count += 1

        card = QFrame()
        card.setObjectName("AssistantCard")
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        c_shadow = QGraphicsDropShadowEffect(card)
        c_shadow.setBlurRadius(8)
        c_shadow.setOffset(0, 2)
        c_shadow.setColor(QColor(43, 38, 31, 16))
        card.setGraphicsEffect(c_shadow)
        card.setStyleSheet("""
            QFrame#AssistantCard {
                background-color: #FFFFFF;
                border: 1px solid rgba(43, 38, 31, 0.10);
                border-bottom: 2px solid rgba(43, 38, 31, 0.14);
                border-radius: 14px;
                padding: 10px 14px;
            }
            QLabel {
                border: none;
                background: transparent;
                color: #1F1A16;
            }
        """)

        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(6)

        # Header tag row
        h_row = QHBoxLayout()
        h_row.setSpacing(6)

        pm = get_mascot_pixmap(20, 20, bust_only=True)
        if pm and not pm.isNull():
            mascot_icon = QLabel()
            mascot_icon.setPixmap(pm)
            mascot_icon.setFixedSize(20, 20)
            h_row.addWidget(mascot_icon)

        ai_tag = QLabel("Chuột")
        ai_tag.setStyleSheet("color: #7A5800; font-size: 12px; font-weight: 800;")
        h_row.addWidget(ai_tag)

        sub_tag = QLabel("· Thư ký lanh chanh 🧀")
        sub_tag.setStyleSheet("color: #9E8F7A; font-size: 11px; font-weight: 550;")
        h_row.addWidget(sub_tag)

        h_row.addStretch()
        c_layout.addLayout(h_row)

        # Optional Collapsible Thinking Process Accordion
        if reasoning_steps and len(reasoning_steps) > 0:
            accordion = ThinkingAccordion(reasoning_steps, latency_ms=latency_ms)
            c_layout.addWidget(accordion)

        # Main Answer Text
        ans_lbl = QLabel(answer)
        ans_lbl.setTextFormat(Qt.TextFormat.MarkdownText)
        ans_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        ans_lbl.setStyleSheet("color: #1F2937; font-size: 13px; line-height: 1.5;")
        ans_lbl.setWordWrap(True)
        c_layout.addWidget(ans_lbl)

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

        # Action Buttons Footer
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        btn_copy = QPushButton("Sao chép")
        btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #F9FAFB;
                border: 1px solid #E5E7EB;
                color: #4B5563;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 12px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #F3F4F6;
                color: #1F2937;
                border-color: #D1D5DB;
            }
            QPushButton:pressed {
                background-color: #E5E7EB;
            }
        """)
        btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)

        def _do_copy():
            QApplication.clipboard().setText(answer)
            btn_copy.setText("✓ Đã sao chép")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: btn_copy.setText("Sao chép"))

        btn_copy.clicked.connect(_do_copy)
        btn_row.addWidget(btn_copy)
        btn_row.addStretch()

        c_layout.addLayout(btn_row)
        self.layout.addWidget(card)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        from PyQt6.QtCore import QTimer
        def _do_scroll():
            sb = self.verticalScrollBar()
            if sb:
                sb.setValue(sb.maximum())
        QTimer.singleShot(10, _do_scroll)

    def create_streaming_message(
        self,
        strategy: str = "On-Device Qwen",
        badge: str = "Qwen2.5 (Metal)",
    ) -> Dict[str, Any]:
        """Creates an Assistant card ready to stream tokens with a real-time thinking indicator."""
        if self._message_count == 0 and hasattr(self, "welcome_widget"):
            self.welcome_widget.hide()
            self._show_watermark = True
            self.viewport().update()

        self._message_count += 1

        card = QFrame()
        card.setObjectName("AssistantCard")
        c_shadow = QGraphicsDropShadowEffect(card)
        c_shadow.setBlurRadius(10)
        c_shadow.setOffset(0, 3)
        c_shadow.setColor(QColor(0, 0, 0, 15))
        card.setGraphicsEffect(c_shadow)
        card.setStyleSheet("""
            QFrame#AssistantCard {
                background-color: #FFFFFF;
                border: 1px solid rgba(0, 0, 0, 0.06);
                border-radius: 14px;
                padding: 10px 14px;
            }
            QLabel {
                border: none;
                background: transparent;
                color: #1F2937;
            }
        """)

        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(6)

        # Header tag row
        h_row = QHBoxLayout()
        h_row.setSpacing(6)

        ai_tag = QLabel("Chuột")
        ai_tag.setStyleSheet("color: #1F2937; font-size: 12px; font-weight: 750;")
        h_row.addWidget(ai_tag)

        sub_tag = QLabel(f"· {badge}")
        sub_tag.setStyleSheet("color: #9CA3AF; font-size: 11px; font-weight: 500;")
        h_row.addWidget(sub_tag)

        h_row.addStretch()
        c_layout.addLayout(h_row)

        # Thinking Status Indicator
        status_lbl = QLabel("Chuột đang suy nghĩ...")
        status_lbl.setStyleSheet("color: #9CA3AF; font-size: 12px; font-style: italic; padding: 4px 0px;")
        c_layout.addWidget(status_lbl)

        # Main Answer Text Label (hidden initially)
        ans_lbl = QLabel("")
        ans_lbl.setTextFormat(Qt.TextFormat.MarkdownText)
        ans_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        ans_lbl.setStyleSheet("color: #1F2937; font-size: 13px; line-height: 1.5;")
        ans_lbl.setWordWrap(True)
        ans_lbl.hide()
        c_layout.addWidget(ans_lbl)

        self.layout.addWidget(card)
        self._scroll_to_bottom()

        return {
            "card": card,
            "c_layout": c_layout,
            "status_lbl": status_lbl,
            "ans_lbl": ans_lbl,
            "tokens": [],
            "full_text": "",
            "accordion_added": False,
        }

    def append_stream_token(self, handle: Dict[str, Any], token: str) -> None:
        """Append streamed token and update message live with smooth scrolling."""
        handle["tokens"].append(token)
        handle["full_text"] += token

        status_lbl = handle["status_lbl"]
        if status_lbl.isVisible():
            status_lbl.hide()

        ans_lbl = handle["ans_lbl"]
        if not ans_lbl.isVisible():
            ans_lbl.show()

        ans_lbl.setText(handle["full_text"])
        self._scroll_to_bottom()

    def finalize_stream(
        self,
        handle: Dict[str, Any],
        reasoning_steps: Optional[List[str]] = None,
        latency_ms: float = 0.0,
    ) -> None:
        """Finalize streamed message with thinking accordion and action buttons."""
        c_layout = handle["c_layout"]
        ans_lbl = handle["ans_lbl"]
        full_text = handle["full_text"]

        ans_lbl.setText(full_text)
        ans_lbl.show()

        status_lbl = handle["status_lbl"]
        if status_lbl.isVisible():
            status_lbl.hide()

        # Insert ThinkingAccordion above ans_lbl if steps provided
        if reasoning_steps and len(reasoning_steps) > 0 and not handle.get("accordion_added"):
            accordion = ThinkingAccordion(reasoning_steps, latency_ms=latency_ms)
            idx = c_layout.indexOf(ans_lbl)
            c_layout.insertWidget(idx, accordion)
            handle["accordion_added"] = True

        # Copy button footer
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        btn_copy = QPushButton("📋 Sao chép")
        btn_copy.setStyleSheet("""
            QPushButton {
                background-color: #FFB800;
                border: 1px solid #E2A200;
                color: #1A1816;
                font-size: 11px;
                font-weight: 700;
                padding: 4px 12px;
                border-radius: 7px;
            }
            QPushButton:hover {
                background-color: #FFA500;
            }
            QPushButton:pressed {
                background-color: #E29300;
                padding-top: 5px;
            }
        """)
        btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)

        def _do_copy():
            QApplication.clipboard().setText(full_text)
            btn_copy.setText("✓ Đã sao chép")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: btn_copy.setText("📋 Sao chép"))

        btn_copy.clicked.connect(_do_copy)
        btn_row.addWidget(btn_copy)
        btn_row.addStretch()

        c_layout.addLayout(btn_row)
        self._scroll_to_bottom()
