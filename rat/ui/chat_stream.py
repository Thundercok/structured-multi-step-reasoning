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
from rat.ui.compact_results import CompactFileRow
from rat.ui.preview_panel import trigger_quicklook

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
    """Collapsible Thinking Process Card (CoT / Escalation Ladder / VGC Verifier)."""

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

        # Detect verification or escalation flags in steps
        is_verified = any("✓" in s or "hợp lệ" in s.lower() for s in self.steps)
        is_escalated = any("escalat" in s.lower() or "bị từ chối" in s.lower() for s in self.steps)

        if is_verified and not is_escalated:
            self._header_prefix = f"✓ Đã kiểm chứng (VGC) · {len(self.steps)} bước"
            header_color = "#166534"
        elif is_escalated:
            self._header_prefix = f"⚡ Leo thang suy luận (ESCALATED) · {len(self.steps)} bước"
            header_color = "#92400E"
        else:
            self._header_prefix = f"Chi tiết xử lý · {len(self.steps)} mục"
            header_color = "#2B261F"

        self.latency_ms = latency_ms
        self.setToolTip(f"Thời gian xử lý: {latency_ms:.0f} ms")
        self.header_btn = QPushButton(f"{self._header_prefix}  ▸")
        self.header_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {header_color};
                font-size: 11.5px;
                font-weight: 800;
                text-align: left;
                padding: 2px 0px;
            }}
            QPushButton:hover {{
                color: #FFA000;
            }}
        """)
        self.header_btn.clicked.connect(self._toggle_expanded)
        self.main_layout.addWidget(self.header_btn)

        # Steps container (collapsed by default)
        self.steps_container = QWidget()
        self.steps_layout = QVBoxLayout(self.steps_container)
        self.steps_layout.setContentsMargins(4, 4, 4, 4)
        self.steps_layout.setSpacing(4)

        for idx, step_txt in enumerate(self.steps):
            if "✓" in step_txt or "hợp lệ" in step_txt.lower():
                step_color = "#166534"
            elif "từ chối" in step_txt.lower() or "escalat" in step_txt.lower() or "⚠️" in step_txt:
                step_color = "#92400E"
            else:
                step_color = "#2B261F"

            step_lbl = QLabel(f"<b>Bước {idx + 1}:</b> {step_txt}")
            step_lbl.setStyleSheet(f"color: {step_color}; font-size: 11px; line-height: 1.4;")
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


class CitationChip(QFrame):
    """
    Native macOS Liquid Glass Citation Chip.
    Displays: 📄 <FileName> [· Trang <Page>]
    Hover: Rich tooltip preview of the grounded quotation witness.
    Click: Directly invokes trigger_quicklook(file_path).
    """

    def __init__(self, citation: Dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.citation = citation
        self.file_path = citation.get("file_path", "")
        self.file_name = citation.get("file_name") or (Path(self.file_path).name if self.file_path else "Tài liệu")
        self.page = citation.get("page")
        self.snippet = citation.get("snippet", "")
        self._init_ui()

    def _init_ui(self) -> None:
        self.setObjectName("CitationChip")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QFrame#CitationChip {
                background-color: #F3F4F6;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                padding: 3px 8px;
            }
            QFrame#CitationChip:hover {
                background-color: #E5E7EB;
                border-color: #D1D5DB;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(5)

        icon_lbl = QLabel("📄")
        icon_lbl.setStyleSheet("font-size: 11px;")
        layout.addWidget(icon_lbl)

        label_txt = self.file_name
        if self.page:
            label_txt += f" · Trang {self.page}"

        text_lbl = QLabel(label_txt)
        text_lbl.setStyleSheet("color: #374151; font-size: 11px; font-weight: 600;")
        layout.addWidget(text_lbl)

        # Tooltip snippet preview
        tip = f"<b>{html.escape(self.file_name)}</b>"
        if self.page:
            tip += f" (Trang {self.page})"
        if self.snippet:
            tip += f"<br/><br/><i>\"{html.escape(self.snippet)}\"</i>"
        if self.file_path and os.path.exists(self.file_path):
            tip += "<br/><br/><span style='color: #2563EB;'>Nhấn để xem trước (QuickLook)</span>"
        self.setToolTip(tip)

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self.file_path and os.path.exists(self.file_path):
                trigger_quicklook(self.file_path)
            elif self.file_path:
                open_file_default(self.file_path)
        super().mousePressEvent(event)


class InlineFileCard(CompactFileRow):
    """The expanded conversation uses the same restrained, actionable file row."""

    def __init__(self, item: SearchResultItem, parent: Optional[QWidget] = None) -> None:
        super().__init__(item, parent)
        self.open_requested.connect(lambda result: open_file_default(result.file_path))
        self.reveal_requested.connect(lambda result: reveal_in_finder(result.file_path))
        self.preview_requested.connect(lambda result: trigger_quicklook(result.file_path))


class TimetableSessionCard(QFrame):
    """
    Native macOS Session Card representing an individual class session.
    Features:
    - Course name with degree badge (🎓 ĐH / 🏛️ ThS)
    - Time range & shift description (e.g. 07:40 - 11:10 · Ca 1-2)
    - Room & resolved building/floor location
    - Direct Action Buttons (Feature A):
      * 📂 Tìm tài liệu: Searches RAT file index for slides/notes of this course
      * 🗺️ Vị trí: Triggers campus map / navigation assistance for the classroom
      * 📋 Chép: Copies structured class info to clipboard with visual feedback
    """
    prompt_requested = pyqtSignal(str)

    def __init__(self, session: Any, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.session = session
        self._init_ui()

    def _init_ui(self) -> None:
        from rat.timetable.model import TDTU_PERIODS, resolve_room_location
        s = self.session
        self.setObjectName("TimetableSessionCard")
        self.setStyleSheet("""
            QFrame#TimetableSessionCard {
                background-color: #FAF8F5;
                border: 1px solid #E6DFD5;
                border-radius: 9px;
                padding: 8px 12px;
            }
            QFrame#TimetableSessionCard:hover {
                background-color: #FDFBF8;
                border-color: #D6CBBC;
            }
            QLabel {
                background: transparent;
                border: none;
            }
            QPushButton.CardActionBtn {
                background-color: #FFFFFF;
                border: 1px solid #DCD4C4;
                border-radius: 6px;
                color: #4B4136;
                font-size: 11px;
                font-weight: 550;
                padding: 3px 9px;
            }
            QPushButton.CardActionBtn:hover {
                background-color: #F7F3EC;
                border-color: #BDB09E;
                color: #1F1A16;
            }
            QPushButton.CardActionBtn:pressed {
                background-color: #EDE5D8;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Extract session details safely
        if isinstance(s, dict):
            course_name = s.get("course_name") or s.get("course") or "Môn học"
            course_code = s.get("course_code") or ""
            room = s.get("room") or ""
            p_start = s.get("start_period", 1)
            p_end = s.get("end_period", 3)
            degree_level = s.get("degree_level", "undergrad")
            badge_txt = "🏛️ ThS" if degree_level in ("master", "ths", "caohoc", "postgrad") else "🎓 ĐH"
        else:
            course_name = getattr(s, "course_name", "Môn học")
            course_code = getattr(s, "course_code", "")
            room = getattr(s, "room", "")
            p_start = getattr(s, "start_period", 1)
            p_end = getattr(s, "end_period", 3)
            badge_txt = getattr(s, "badge_text", "🎓 ĐH")

        # Row 1: Course Name + Degree Badge (Left) and Time Range (Right)
        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        badge_lbl = QLabel(badge_txt)
        badge_lbl.setStyleSheet("""
            background-color: #EDE7DC;
            color: #5A5043;
            border-radius: 4px;
            padding: 1px 5px;
            font-size: 10px;
            font-weight: bold;
        """)
        top_row.addWidget(badge_lbl)

        course_lbl = QLabel(course_name)
        course_lbl.setStyleSheet("color: #1F1A16; font-size: 12.5px; font-weight: 700;")
        top_row.addWidget(course_lbl)

        if course_code:
            code_lbl = QLabel(f"({course_code})")
            code_lbl.setStyleSheet("color: #8C8275; font-size: 11px; font-weight: 550;")
            top_row.addWidget(code_lbl)

        top_row.addStretch()

        p_start_str = TDTU_PERIODS.get(p_start, ("00:00", "", "", ""))[0]
        p_end_str = TDTU_PERIODS.get(p_end, ("", "23:59", "", ""))[1]
        start_ca = TDTU_PERIODS.get(p_start, ("", "", "", "Ca 1"))[3]
        end_ca = TDTU_PERIODS.get(p_end, ("", "", "", "Ca 1"))[3]
        ca_desc = start_ca if start_ca == end_ca else f"{start_ca}-{end_ca}"

        time_lbl = QLabel(f"{p_start_str} - {p_end_str} ({ca_desc})")
        time_lbl.setStyleSheet("color: #786F66; font-size: 11.5px; font-weight: 600;")
        top_row.addWidget(time_lbl)
        layout.addLayout(top_row)

        # Row 2: Location
        loc_str = resolve_room_location(room) if room else "Chưa xác định phòng"
        loc_lbl = QLabel(f"📍 Phòng {room or '—'} · {loc_str}")
        loc_lbl.setStyleSheet("color: #4B4136; font-size: 11px;")
        layout.addWidget(loc_lbl)

        # Row 3: Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        # Smart File Bridge: Combine course_code and course_name
        search_terms = f"{course_code} {course_name}".strip() if course_code else course_name
        self.btn_files = QPushButton("📂 Tìm tài liệu")
        self.btn_files.setProperty("class", "CardActionBtn")
        self.btn_files.setCursor(Qt.CursorShape.PointingHandCursor)
        tip_code = f" [{course_code}]" if course_code else ""
        self.btn_files.setToolTip(f"Tìm slide, bài giảng, bài tập môn {course_name}{tip_code}")
        self.btn_files.clicked.connect(lambda: self.prompt_requested.emit(f"tìm tài liệu {search_terms}"))
        btn_row.addWidget(self.btn_files)

        if room:
            self.btn_room = QPushButton("🗺️ Vị trí")
            self.btn_room.setProperty("class", "CardActionBtn")
            self.btn_room.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_room.setToolTip(f"Xem vị trí và chỉ đường phòng {room}")
            self.btn_room.clicked.connect(lambda: self.prompt_requested.emit(f"phòng {room}"))
            btn_row.addWidget(self.btn_room)

        self.btn_copy = QPushButton("📋 Chép")
        self.btn_copy.setProperty("class", "CardActionBtn")
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)

        code_tag = f" [{course_code}]" if course_code else ""
        copy_text = f"{course_name}{code_tag} ({p_start_str}-{p_end_str}, Phòng {room or '—'}) — {loc_str}"
        def _copy_info():
            QApplication.clipboard().setText(copy_text)
            self.btn_copy.setText("✓ Đã chép")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: self.btn_copy.setText("📋 Chép"))

        self.btn_copy.clicked.connect(_copy_info)
        btn_row.addWidget(self.btn_copy)

        btn_row.addStretch()
        layout.addLayout(btn_row)


class TimetableDeckWidget(QWidget):
    """
    Composite Timetable Container with Session Cards (Feature A) and Contextual Follow-up Chips (Feature B).
    """
    prompt_requested = pyqtSignal(str)

    def __init__(
        self,
        sessions: List[Any],
        day_label: str = "hôm nay",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.sessions = sessions
        self.day_label = day_label
        self.session_cards: List[TimetableSessionCard] = []
        self.follow_up_chips: List[QPushButton] = []
        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)

        # Feature A: Session Cards
        if self.sessions:
            for s in self.sessions:
                card = TimetableSessionCard(s, parent=self)
                card.prompt_requested.connect(self.prompt_requested.emit)
                self.session_cards.append(card)
                layout.addWidget(card)
        else:
            empty_lbl = QLabel(f"Lịch học {self.day_label}: Không có ca học nào trên trường.")
            empty_lbl.setStyleSheet("color: #786F66; font-size: 11.5px; font-style: italic; padding: 4px 0px;")
            layout.addWidget(empty_lbl)

        # Feature B: Follow-up Contextual Suggestion Chips
        chips_box = QVBoxLayout()
        chips_box.setSpacing(4)

        chips_row = QHBoxLayout()
        chips_row.setSpacing(6)

        chip_style = """
            QPushButton.SuggestionChip {
                background-color: #F5EFEB;
                border: 1px solid #DFD5C6;
                border-radius: 12px;
                color: #5C4E3D;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 11px;
            }
            QPushButton.SuggestionChip:hover {
                background-color: #EDE3D8;
                border-color: #C4B5A0;
                color: #2E2519;
            }
            QPushButton.SuggestionChip:pressed {
                background-color: #DFD2BF;
            }
        """

        follow_ups: List[Tuple[str, str]] = []
        if "mai" in self.day_label.lower():
            follow_ups.append(("⏮️ Lịch hôm nay", "hôm nay học gì?"))
        else:
            follow_ups.append(("⏭️ Lịch ngày mai", "ngày mai học gì?"))

        follow_ups.append(("☕ Khung giờ rảnh", "giờ rảnh hôm nay"))
        follow_ups.append(("👥 Ai trong CLB rảnh?", "ai rảnh hôm nay"))

        for label, prompt in follow_ups:
            chip = QPushButton(label)
            chip.setProperty("class", "SuggestionChip")
            chip.setStyleSheet(chip_style)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda _, p=prompt: self.prompt_requested.emit(p))
            self.follow_up_chips.append(chip)
            chips_row.addWidget(chip)

        chips_row.addStretch()
        chips_box.addLayout(chips_row)
        layout.addLayout(chips_box)


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
        citations: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Render an AI Assistant response with thinking process, grounded citations, and rich cards."""
        if self._message_count == 0 and hasattr(self, "welcome_widget"):
            self.welcome_widget.hide()
            self._show_watermark = True
            self.viewport().update()

        self._message_count += 1

        card = QFrame()
        card.setObjectName("AssistantCard")
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        card.setStyleSheet("""
            QFrame#AssistantCard {
                background-color: #FFFFFF;
                border: 1px solid rgba(43, 38, 31, 0.10);
                border-radius: 12px;
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

        sub_tag = QLabel("· " + {"Search": "Tìm tệp", "Math": "Tính nhanh", "Timetable": "Lịch học", "PAL": "Kiểm chứng (PAL)", "CoT": "Quy chế"}.get(strategy, "Trả lời"))
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

        # Optional Custom Widget (e.g. Agenda, Room guide, Math card, Timetable)
        if custom_widget is not None:
            if hasattr(custom_widget, "prompt_requested"):
                custom_widget.prompt_requested.connect(self.prompt_clicked.emit)
            c_layout.addWidget(custom_widget)

        # Grounded Citation Chips (VGC Anti-Hallucination)
        if citations and len(citations) > 0:
            c_box = QVBoxLayout()
            c_box.setSpacing(4)
            c_title = QLabel("Nguồn trích dẫn:")
            c_title.setStyleSheet("color: #6B7280; font-size: 11px; font-weight: 600; padding-top: 2px;")
            c_box.addWidget(c_title)

            chips_flow = QHBoxLayout()
            chips_flow.setSpacing(6)
            for cit in citations:
                chip = CitationChip(cit)
                chips_flow.addWidget(chip)
            chips_flow.addStretch()
            c_box.addLayout(chips_flow)
            c_layout.addLayout(c_box)

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
            "badge_lbl": sub_tag,
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
        # Compact mode hides the parent; isVisible() is false even for an
        # explicitly shown status. Hide it regardless before expanding later.
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
        citations: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Finalize streamed message with thinking accordion, grounded citations, and action buttons."""
        c_layout = handle["c_layout"]
        ans_lbl = handle["ans_lbl"]
        full_text = handle["full_text"]

        ans_lbl.setText(full_text)
        ans_lbl.show()

        status_lbl = handle["status_lbl"]
        status_lbl.hide()

        # Insert ThinkingAccordion above ans_lbl if steps provided
        if reasoning_steps and len(reasoning_steps) > 0 and not handle.get("accordion_added"):
            accordion = ThinkingAccordion(reasoning_steps, latency_ms=latency_ms)
            idx = c_layout.indexOf(ans_lbl)
            c_layout.insertWidget(idx, accordion)
            handle["accordion_added"] = True

        # Insert Grounded Citation Chips if provided
        if citations and len(citations) > 0 and not handle.get("citations_added"):
            c_box = QVBoxLayout()
            c_box.setSpacing(4)
            c_title = QLabel("Nguồn trích dẫn:")
            c_title.setStyleSheet("color: #6B7280; font-size: 11px; font-weight: 600; padding-top: 2px;")
            c_box.addWidget(c_title)

            chips_flow = QHBoxLayout()
            chips_flow.setSpacing(6)
            for cit in citations:
                chip = CitationChip(cit)
                chips_flow.addWidget(chip)
            chips_flow.addStretch()
            c_box.addLayout(chips_flow)
            c_layout.addLayout(c_box)
            handle["citations_added"] = True

        # Copy button footer
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        btn_copy = QPushButton("Sao chép")
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
            timer = QTimer(btn_copy)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: btn_copy.setText("Sao chép"))
            timer.timeout.connect(timer.deleteLater)
            timer.start(1500)

        btn_copy.clicked.connect(_do_copy)
        btn_row.addWidget(btn_copy)
        btn_row.addStretch()

        c_layout.addLayout(btn_row)
        self._scroll_to_bottom()
