"""
rat.ui.claude_widget — Claude-Style Interactive Timetable & Academic Assistant Widget.

Features:
- Form format inspired by Claude widget mode / interactive artifacts.
- Natural language query parser ("hôm nay", "chiều nay", "phòng C302", "ai rảnh", "tối thứ 2 thạc sĩ").
- Dynamic reactive form controls (Intent pills, Member selector, Degree level, Day & Shift).
- Real-time live status countdown & academic clock.
- Multi-capability cards: Live Agenda, Schedule Browser, WhosFree Club Matrix,
  Conflict & Turnaround Analysis, TDTU Campus Building Navigator, Workload Intensity Meter,
  and Quick Notes Scratchpad.
- Sleek warm Anthropic/Claude palette, floating stay-on-top window or embedded widget.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from rat.timetable.compositor import TimetableCompositor, degree_to_style
from rat.timetable.data import load_club_members
from rat.timetable.model import (
    DAYS,
    SHIFTS,
    ClassSession,
    MemberSchedule,
    resolve_room_location,
)

logger = logging.getLogger(__name__)

# Claude / Anthropic Warm Aesthetic Color Palette
CLAUDE_STYLE = {
    "bg_window": "#fcfbf9",
    "surface": "#ffffff",
    "surface_subtle": "#f7f6f2",
    "surface_hover": "#f0eee6",
    "border": "#e8e6df",
    "border_focus": "#c2410c",
    "text_primary": "#1f2937",
    "text_secondary": "#57534e",
    "text_muted": "#8c857b",
    "accent_terracotta": "#c2410c",
    "accent_amber": "#d97706",
    "accent_warm_bg": "#fffbeb",
    "undergrad_bg": "#eff6ff",
    "undergrad_border": "#bfdbfe",
    "undergrad_text": "#1d4ed8",
    "master_bg": "#faf5ff",
    "master_border": "#e9d5ff",
    "master_text": "#7e22ce",
    "live_bg": "#ecfdf5",
    "live_border": "#a7f3d0",
    "live_text": "#047857",
    "conflict_bg": "#fef2f2",
    "conflict_border": "#fecaca",
    "conflict_text": "#b91c1c",
}


def parse_natural_query(query: str) -> Dict[str, Any]:
    """Parse Vietnamese natural language queries to extract intent, day, shift, degree, room."""
    q = query.strip().lower()
    res: Dict[str, Any] = {
        "intent": "search",
        "day": None,
        "shift": None,
        "degree": None,
        "room": None,
        "raw": q,
    }

    if not q:
        res["intent"] = "today"
        return res

    # Day detection
    day_map = {
        "hôm nay": "TODAY",
        "hom nay": "TODAY",
        "today": "TODAY",
        "ngày mai": "TOMORROW",
        "ngay mai": "TOMORROW",
        "tomorrow": "TOMORROW",
        "thứ 2": "T2", "thứ hai": "T2", "t2": "T2", "monday": "T2",
        "thứ 3": "T3", "thứ ba": "T3", "t3": "T3", "tuesday": "T3",
        "thứ 4": "T4", "thứ tư": "T4", "t4": "T4", "wednesday": "T4",
        "thứ 5": "T5", "thứ năm": "T5", "t5": "T5", "thursday": "T5",
        "thứ 6": "T6", "thứ sáu": "T6", "t6": "T6", "friday": "T6",
        "thứ 7": "T7", "thứ bảy": "T7", "t7": "T7", "saturday": "T7",
        "chủ nhật": "CN", "chu nhat": "CN", "cn": "CN", "sunday": "CN",
    }
    for k, v in day_map.items():
        if re.search(r"\b" + re.escape(k) + r"\b", q):
            res["day"] = v
            break

    # Shift detection
    if any(k in q for k in ["ca 1", "sáng sớm", "tiết 1", "tiết 2", "tiết 3"]):
        res["shift"] = "ca1"
    elif any(k in q for k in ["ca 2", "giữa sáng", "tiết 4", "tiết 5", "tiết 6"]):
        res["shift"] = "ca2"
    elif any(k in q for k in ["ca 3", "đầu giờ chiều", "tiết 7", "tiết 8", "tiết 9"]):
        res["shift"] = "ca3"
    elif any(k in q for k in ["ca 4", "chiều muộn", "tiết 10", "tiết 11", "tiết 12"]):
        res["shift"] = "ca4"
    elif any(k in q for k in ["ca 5", "tối", "ban đêm", "tiết 13", "tiết 14", "tiết 15", "evening"]):
        res["shift"] = "ca5"
    elif "sáng" in q:
        res["shift"] = "morning"
    elif "chiều" in q:
        res["shift"] = "afternoon"

    # Degree detection
    if any(k in q for k in ["thạc sĩ", "thac si", "cao học", "cao hoc", "sau đại học", "master", "ths"]):
        res["degree"] = "master"
    elif any(k in q for k in ["đại học", "dai hoc", "chính quy", "sinh viên", "undergrad", "dh"]):
        res["degree"] = "undergrad"

    # Room detection (e.g. C302, A608, F702, B101, NTD)
    room_match = re.search(r"\b([a-f]\d{3,4}|ntd|tret-ntd-\d|hoctructuyen-\d)\b", q, re.IGNORECASE)
    if room_match:
        res["room"] = room_match.group(1).upper()
        res["intent"] = "room"
        return res

    # Intent routing
    if any(k in q for k in ["ai rảnh", "ai ranh", "bạn rảnh", "trống lịch", "họp nhóm", "clb", "whos free", "free"]):
        res["intent"] = "whos_free"
    elif any(k in q for k in ["xung đột", "trùng lịch", "trung gio", "chuyển ca", "gấp", "conflict"]):
        res["intent"] = "conflicts"
    elif any(k in q for k in ["tải môn", "áp lực", "số tiết", "nặng", "workload"]):
        res["intent"] = "workload"
    elif any(k in q for k in ["ghi chú", "note", "link", "tài liệu"]):
        res["intent"] = "notes"
    elif res["day"] == "TODAY" or any(k in q for k in ["bây giờ", "đang học gì", "tiết tiếp theo", "live"]):
        res["intent"] = "today"
    elif res["day"] or res["shift"] or res["degree"]:
        res["intent"] = "schedule"
    else:
        res["intent"] = "search"

    return res


class ClaudeTimetableWidget(QWidget):
    """
    Interactive Timetable & Academic Assistant Widget in Claude Form Format.
    Features real-time queries, dynamic form state, and instant card rendering.
    """

    open_studio_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        loaded_members = load_club_members()
        self.compositor = TimetableCompositor(loaded_members)
        self.members: List[MemberSchedule] = self.compositor.members
        self.selected_member_id = "m1"  # Default to Huỳnh Nhật Huy (Dual Degree)
        self.current_intent = "today"
        self.filter_degree = "all"
        self.filter_day: Optional[str] = None
        self.filter_shift: Optional[str] = None
        self.search_query = ""

        # Persistence notes
        self.notes_file = Path.home() / ".rat" / "course_notes.json"
        self.course_notes: Dict[str, str] = self._load_notes()

        self._init_ui()
        self._setup_timer()
        self._apply_intent("today")

    def _load_notes(self) -> Dict[str, str]:
        try:
            if self.notes_file.exists():
                with open(self.notes_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.debug(f"Error loading notes: {e}")
        return {}

    def _save_notes(self) -> None:
        try:
            self.notes_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.notes_file, "w", encoding="utf-8") as f:
                json.dump(self.course_notes, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving notes: {e}")

    def _get_selected_member(self) -> MemberSchedule:
        for m in self.members:
            if m.id == self.selected_member_id:
                return m
        if self.members:
            return self.members[0]
        return MemberSchedule(id="m_default", name="Sinh viên")

    def _init_ui(self) -> None:
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {CLAUDE_STYLE['bg_window']};
                color: {CLAUDE_STYLE['text_primary']};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }}
            QLineEdit {{
                background-color: {CLAUDE_STYLE['surface']};
                border: 1px solid {CLAUDE_STYLE['border']};
                border-radius: 10px;
                padding: 10px 14px;
                font-size: 13.5px;
                color: {CLAUDE_STYLE['text_primary']};
            }}
            QLineEdit:focus {{
                border: 1.5px solid {CLAUDE_STYLE['accent_terracotta']};
                background-color: #ffffff;
            }}
            QComboBox {{
                background-color: {CLAUDE_STYLE['surface']};
                border: 1px solid {CLAUDE_STYLE['border']};
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 12px;
                color: {CLAUDE_STYLE['text_primary']};
            }}
            QComboBox:hover {{
                background-color: {CLAUDE_STYLE['surface_hover']};
            }}
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
        """)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(10)

        # 1. Header Card (Claude Widget Aesthetic)
        header_card = QFrame()
        header_card.setStyleSheet(f"""
            background-color: {CLAUDE_STYLE['surface']};
            border: 1px solid {CLAUDE_STYLE['border']};
            border-radius: 12px;
            padding: 10px 14px;
        """)
        hc_layout = QHBoxLayout(header_card)
        hc_layout.setContentsMargins(4, 2, 4, 2)
        hc_layout.setSpacing(10)

        icon_lbl = QLabel("✦")
        icon_lbl.setStyleSheet(f"font-size: 20px; color: {CLAUDE_STYLE['accent_terracotta']}; font-weight: 900;")
        hc_layout.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(1)
        w_title = QLabel("Trợ Lý Lịch Học & Khung Giờ CLB")
        w_title.setStyleSheet("font-size: 14.5px; font-weight: 700; color: #111827;")
        self.live_clock_lbl = QLabel("🕒 Đang đồng bộ thời gian thực...")
        self.live_clock_lbl.setStyleSheet(f"font-size: 11px; color: {CLAUDE_STYLE['text_muted']};")
        title_vbox.addWidget(w_title)
        title_vbox.addWidget(self.live_clock_lbl)
        hc_layout.addLayout(title_vbox)

        hc_layout.addStretch()

        btn_open_studio = QPushButton("🪟 Mở Studio")
        btn_open_studio.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open_studio.setStyleSheet(f"""
            QPushButton {{
                background-color: {CLAUDE_STYLE['surface_subtle']};
                border: 1px solid {CLAUDE_STYLE['border']};
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 11.5px;
                font-weight: 600;
                color: {CLAUDE_STYLE['text_secondary']};
            }}
            QPushButton:hover {{
                background-color: {CLAUDE_STYLE['surface_hover']};
                color: #111827;
            }}
        """)
        btn_open_studio.clicked.connect(self.open_studio_requested.emit)
        hc_layout.addWidget(btn_open_studio)

        root_layout.addWidget(header_card)

        # 2. Interactive Form Section
        form_card = QFrame()
        form_card.setStyleSheet(f"""
            background-color: {CLAUDE_STYLE['surface']};
            border: 1px solid {CLAUDE_STYLE['border']};
            border-radius: 12px;
            padding: 12px;
        """)
        self.fc_layout = QVBoxLayout(form_card)
        self.fc_layout.setContentsMargins(6, 6, 6, 6)
        self.fc_layout.setSpacing(8)

        # 2.1 Natural Language Query Input
        search_box = QHBoxLayout()
        search_box.setSpacing(6)
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("💬 Hỏi tự nhiên: 'hôm nay', 'chiều mai', 'phòng C302', 'ai rảnh', 'thạc sĩ'...")
        self.query_input.textChanged.connect(self._on_query_text_changed)
        search_box.addWidget(self.query_input)

        self.btn_clear_query = QPushButton("✕")
        self.btn_clear_query.setFixedSize(32, 32)
        self.btn_clear_query.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_query.setStyleSheet(f"""
            QPushButton {{
                background-color: {CLAUDE_STYLE['surface_subtle']};
                border: 1px solid {CLAUDE_STYLE['border']};
                border-radius: 8px;
                font-size: 12px;
                color: {CLAUDE_STYLE['text_muted']};
            }}
            QPushButton:hover {{
                background-color: #fee2e2;
                color: #b91c1c;
            }}
        """)
        self.btn_clear_query.clicked.connect(lambda: self.query_input.clear())
        search_box.addWidget(self.btn_clear_query)
        self.fc_layout.addLayout(search_box)

        # 2.2 Dynamic Intent Selector Pills (Claude Segmented Control)
        intent_scroll = QScrollArea()
        intent_scroll.setFixedHeight(38)
        intent_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        intent_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        intent_scroll.setWidgetResizable(True)

        pill_container = QWidget()
        self.pill_layout = QHBoxLayout(pill_container)
        self.pill_layout.setContentsMargins(0, 0, 0, 0)
        self.pill_layout.setSpacing(6)

        self.intent_buttons: Dict[str, QPushButton] = {}
        intents = [
            ("today", "⚡ Hôm Nay & Live"),
            ("schedule", "📅 Theo Lịch"),
            ("whos_free", "👥 Ai Rảnh?"),
            ("conflicts", "⚠️ Xung Đột"),
            ("room", "📍 Phòng TDTU"),
            ("workload", "📊 Tải Môn"),
            ("notes", "📝 Ghi Chú"),
        ]
        for key, label in intents:
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, k=key: self._apply_intent(k))
            self.intent_buttons[key] = btn
            self.pill_layout.addWidget(btn)

        self.pill_layout.addStretch()
        intent_scroll.setWidget(pill_container)
        self.fc_layout.addWidget(intent_scroll)

        # 2.3 Form Row Controls (Member, Degree, Day, Shift)
        self.form_controls_widget = QWidget()
        fc_sub_layout = QHBoxLayout(self.form_controls_widget)
        fc_sub_layout.setContentsMargins(0, 4, 0, 2)
        fc_sub_layout.setSpacing(8)

        # Member Selector
        fc_sub_layout.addWidget(QLabel("Hồ sơ:"))
        self.member_combo = QComboBox()
        for m in self.members:
            suffix = " (Song bằng ĐH+ThS)" if m.is_dual_degree else ""
            self.member_combo.addItem(f"{m.name}{suffix}", m.id)
        self.member_combo.currentIndexChanged.connect(self._on_member_changed)
        fc_sub_layout.addWidget(self.member_combo)

        # Degree Level Selector
        fc_sub_layout.addWidget(QLabel("Bậc:"))
        self.degree_combo = QComboBox()
        self.degree_combo.addItems(["Tất cả", "🎓 ĐH", "🏛️ ThS"])
        self.degree_combo.currentIndexChanged.connect(self._on_degree_changed)
        fc_sub_layout.addWidget(self.degree_combo)

        fc_sub_layout.addStretch()
        self.fc_layout.addWidget(self.form_controls_widget)

        root_layout.addWidget(form_card)

        # 3. Dynamic Results Card Area (Scrollable Feed)
        self.results_scroll = QScrollArea()
        self.results_scroll.setWidgetResizable(True)
        self.results_scroll.setStyleSheet("background-color: transparent;")

        self.results_content = QWidget()
        self.results_layout = QVBoxLayout(self.results_content)
        self.results_layout.setContentsMargins(2, 4, 2, 8)
        self.results_layout.setSpacing(10)

        self.results_scroll.setWidget(self.results_content)
        root_layout.addWidget(self.results_scroll, 1)

        # 4. Action Footer Bar
        footer = QFrame()
        footer.setStyleSheet(f"""
            background-color: {CLAUDE_STYLE['surface']};
            border: 1px solid {CLAUDE_STYLE['border']};
            border-radius: 10px;
            padding: 8px 12px;
        """)
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(4, 2, 4, 2)
        f_layout.setSpacing(8)

        self.btn_copy_all = QPushButton("📋 Sao Chép Kết Quả")
        self.btn_copy_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_all.setStyleSheet(self._action_btn_style())
        self.btn_copy_all.clicked.connect(self._copy_current_view)
        f_layout.addWidget(self.btn_copy_all)

        self.btn_export_ics = QPushButton("📅 Xuất Calendar (.ics)")
        self.btn_export_ics.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export_ics.setStyleSheet(self._action_btn_style())
        self.btn_export_ics.clicked.connect(self._export_current_ics)
        f_layout.addWidget(self.btn_export_ics)

        f_layout.addStretch()

        self.footer_status = QLabel("✨ Cập nhật tự động")
        self.footer_status.setStyleSheet(f"font-size: 11px; color: {CLAUDE_STYLE['text_muted']};")
        f_layout.addWidget(self.footer_status)

        root_layout.addWidget(footer)

    def _action_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {CLAUDE_STYLE['surface_subtle']};
                border: 1px solid {CLAUDE_STYLE['border']};
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 11.5px;
                font-weight: 600;
                color: {CLAUDE_STYLE['text_primary']};
            }}
            QPushButton:hover {{
                background-color: {CLAUDE_STYLE['surface_hover']};
                border-color: {CLAUDE_STYLE['accent_terracotta']};
            }}
        """

    def _setup_timer(self) -> None:
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_live_tick)
        self.timer.start(5000)
        self._on_live_tick()

    def _on_live_tick(self) -> None:
        now = datetime.now()
        dt_str = now.strftime("%H:%M:%S — %A, %d/%m/%Y")
        self.live_clock_lbl.setText(f"🕒 {dt_str}")

        # If currently in 'today' mode and search query is empty, refresh dynamic cards
        if self.current_intent == "today" and not self.search_query:
            self._render_today_view()

    def _on_query_text_changed(self, text: str) -> None:
        self.search_query = text.strip()
        parsed = parse_natural_query(self.search_query)

        if parsed["intent"] != self.current_intent:
            self._apply_intent(parsed["intent"], trigger_render=False)

        if parsed["degree"]:
            deg_idx = 1 if parsed["degree"] == "undergrad" else 2
            self.degree_combo.setCurrentIndex(deg_idx)

        self._render_dynamic_view(parsed)

    def _apply_intent(self, intent: str, trigger_render: bool = True) -> None:
        self.current_intent = intent
        # Update pill button styles
        for key, btn in self.intent_buttons.items():
            if key == intent:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {CLAUDE_STYLE['accent_warm_bg']};
                        border: 1.5px solid {CLAUDE_STYLE['accent_terracotta']};
                        border-radius: 14px;
                        padding: 4px 12px;
                        font-size: 12px;
                        font-weight: 700;
                        color: {CLAUDE_STYLE['accent_terracotta']};
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {CLAUDE_STYLE['surface']};
                        border: 1px solid {CLAUDE_STYLE['border']};
                        border-radius: 14px;
                        padding: 4px 12px;
                        font-size: 12px;
                        color: {CLAUDE_STYLE['text_secondary']};
                    }}
                    QPushButton:hover {{
                        background-color: {CLAUDE_STYLE['surface_hover']};
                        color: {CLAUDE_STYLE['text_primary']};
                    }}
                """)

        if trigger_render:
            parsed = parse_natural_query(self.search_query)
            parsed["intent"] = intent
            self._render_dynamic_view(parsed)

    def _on_member_changed(self, index: int) -> None:
        self.selected_member_id = self.member_combo.currentData()
        self._apply_intent(self.current_intent)

    def _on_degree_changed(self, index: int) -> None:
        mapping = {0: "all", 1: "undergrad", 2: "master"}
        self.filter_degree = mapping.get(index, "all")
        self._apply_intent(self.current_intent)

    def _clear_results(self) -> None:
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _render_dynamic_view(self, parsed: Dict[str, Any]) -> None:
        self._clear_results()
        intent = parsed.get("intent", self.current_intent)

        if intent == "today":
            self._render_today_view()
        elif intent == "schedule":
            self._render_schedule_view(parsed)
        elif intent == "whos_free":
            self._render_whos_free_view(parsed)
        elif intent == "conflicts":
            self._render_conflicts_view()
        elif intent == "room":
            self._render_room_view(parsed.get("room"))
        elif intent == "workload":
            self._render_workload_view()
        elif intent == "notes":
            self._render_notes_view()
        else:
            self._render_search_results(parsed.get("raw", ""))

    # --- Renderers for each dynamic capability ---

    def _render_today_view(self) -> None:
        member = self._get_selected_member()
        now = datetime.now()
        live_status = self.compositor.compute_live_status(member, current_dt=now)
        agenda = self.compositor.get_today_agenda(member, current_dt=now)

        # 1. Live Banner Card
        banner = QFrame()
        if live_status.is_in_class and live_status.current_session:
            s = live_status.current_session
            loc = resolve_room_location(s.room)
            banner.setStyleSheet(f"""
                background-color: {CLAUDE_STYLE['live_bg']};
                border: 1.5px solid {CLAUDE_STYLE['live_border']};
                border-radius: 12px;
                padding: 12px;
            """)
            b_layout = QVBoxLayout(banner)
            b_layout.setContentsMargins(8, 4, 8, 4)
            b_layout.setSpacing(4)

            tag = QLabel(f"🔴 ĐANG DIỄN RA • CÒN {live_status.remaining_minutes} PHÚT")
            tag.setStyleSheet(f"font-size: 11px; font-weight: 800; color: {CLAUDE_STYLE['live_text']}; letter-spacing: 0.5px;")
            b_layout.addWidget(tag)

            c_name = QLabel(f"{s.badge_text} {s.course_name}")
            c_name.setStyleSheet("font-size: 14px; font-weight: 700; color: #064e3b;")
            b_layout.addWidget(c_name)

            details = QLabel(f"📍 {loc} • Tiết {s.start_period}-{s.end_period} ({s.time_range_str})")
            details.setStyleSheet("font-size: 11.5px; color: #065f46;")
            b_layout.addWidget(details)
        elif live_status.next_session:
            s = live_status.next_session
            loc = resolve_room_location(s.room)
            m_left = live_status.minutes_until_next
            time_txt = f"{m_left // 60} giờ {m_left % 60} phút" if m_left >= 60 else f"{m_left} phút"
            banner.setStyleSheet(f"""
                background-color: {CLAUDE_STYLE['accent_warm_bg']};
                border: 1.5px solid #fde68a;
                border-radius: 12px;
                padding: 12px;
            """)
            b_layout = QVBoxLayout(banner)
            b_layout.setContentsMargins(8, 4, 8, 4)
            b_layout.setSpacing(4)

            tag = QLabel(f"⏳ TIẾT HỌC TIẾP THEO • BẮT ĐẦU SAU {time_txt.upper()}")
            tag.setStyleSheet("font-size: 11px; font-weight: 800; color: #b45309; letter-spacing: 0.5px;")
            b_layout.addWidget(tag)

            c_name = QLabel(f"{s.badge_text} {s.course_name}")
            c_name.setStyleSheet("font-size: 14px; font-weight: 700; color: #78350f;")
            b_layout.addWidget(c_name)

            details = QLabel(f"📍 {loc} • Vào lớp lúc {s.time_range_str.split(' - ')[0]}")
            details.setStyleSheet("font-size: 11.5px; color: #92400e;")
            b_layout.addWidget(details)
        else:
            banner.setStyleSheet(f"""
                background-color: {CLAUDE_STYLE['surface_subtle']};
                border: 1px solid {CLAUDE_STYLE['border']};
                border-radius: 12px;
                padding: 12px;
            """)
            b_layout = QVBoxLayout(banner)
            b_layout.setContentsMargins(8, 6, 8, 6)
            tag = QLabel("🌙 HÔM NAY ĐÃ HOÀN THÀNH HOẶC KHÔNG CÓ TIẾT")
            tag.setStyleSheet("font-size: 12px; font-weight: 700; color: #4b5563;")
            b_layout.addWidget(tag)

        self.results_layout.addWidget(banner)

        # 2. Agenda Timeline Cards
        hdr = QLabel(f"📅 Lịch Hôm Nay ({len(agenda)} môn):")
        hdr.setStyleSheet("font-size: 12.5px; font-weight: 700; color: #374151; margin-top: 6px;")
        self.results_layout.addWidget(hdr)

        if not agenda:
            empty_card = self._create_info_card("🌴 Hôm nay bạn hoàn toàn thảnh thơi!", "Không có tiết học nào trên hệ thống.")
            self.results_layout.addWidget(empty_card)
        else:
            for item in agenda:
                s = item["session"]
                extra = f"{item.get('badge', '')} • {item.get('countdown', '')}"
                card = self._create_course_card(s, extra_status=extra)
                self.results_layout.addWidget(card)

        self.results_layout.addStretch()

    def _render_schedule_view(self, parsed: Dict[str, Any]) -> None:
        member = self._get_selected_member()
        filter_deg = self.filter_degree
        target_day = parsed.get("day")
        if target_day in ("TODAY", None):
            weekday_idx = datetime.now().weekday()
            day_keys = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
            target_day = day_keys[weekday_idx] if target_day == "TODAY" else None

        hdr = QLabel(f"📚 Thời Khóa Biểu — {member.name}")
        hdr.setStyleSheet("font-size: 13px; font-weight: 700; color: #1f2937;")
        self.results_layout.addWidget(hdr)

        day_names = {
            "T2": "Thứ 2", "T3": "Thứ 3", "T4": "Thứ 4",
            "T5": "Thứ 5", "T6": "Thứ 6", "T7": "Thứ 7", "CN": "Chủ Nhật"
        }

        days_to_show = [target_day] if target_day in day_names else [d[0] for d in DAYS]
        total_found = 0

        for day in days_to_show:
            sessions = member.schedule.get(day, [])
            if filter_deg == "undergrad":
                sessions = [s for s in sessions if not s.is_master]
            elif filter_deg == "master":
                sessions = [s for s in sessions if s.is_master]

            if not sessions:
                continue

            day_lbl = QLabel(f"🗓️ {day_names.get(day, day)}")
            day_lbl.setStyleSheet("font-size: 12px; font-weight: 700; color: #4b5563; margin-top: 4px;")
            self.results_layout.addWidget(day_lbl)

            for s in sessions:
                total_found += 1
                card = self._create_course_card(s)
                self.results_layout.addWidget(card)

        if total_found == 0:
            self.results_layout.addWidget(self._create_info_card("Không tìm thấy môn học nào", "Thử chọn ngày khác hoặc đổi bộ lọc bậc học."))

        self.results_layout.addStretch()

    def _render_whos_free_view(self, parsed: Dict[str, Any]) -> None:
        now = datetime.now()
        weekday_idx = now.weekday()
        day_keys = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
        curr_day = day_keys[weekday_idx]

        # Determine current or target shift
        hour = now.hour
        if hour < 9:
            shift_id = "ca1"
        elif hour < 12:
            shift_id = "ca2"
        elif hour < 15:
            shift_id = "ca3"
        elif hour < 18:
            shift_id = "ca4"
        else:
            shift_id = "ca5"

        matrix = self.compositor.compute_shift_matrix()
        shift_data = matrix.get(curr_day, {}).get(shift_id)

        title = QLabel(f"👥 Tình Trạng Rảnh/Bận CLB ({curr_day} • {shift_id.upper()})")
        title.setStyleSheet("font-size: 13px; font-weight: 700; color: #111827;")
        self.results_layout.addWidget(title)

        if not shift_data:
            return

        ratio = shift_data.ratio
        color = "#10b981" if ratio >= 0.8 else ("#f59e0b" if ratio >= 0.5 else "#ef4444")

        summary_card = QFrame()
        summary_card.setStyleSheet(f"""
            background-color: {CLAUDE_STYLE['surface']};
            border: 1.5px solid {color};
            border-radius: 12px;
            padding: 12px;
        """)
        sc_layout = QVBoxLayout(summary_card)
        sc_layout.setSpacing(6)

        st = QLabel(f"🌟 Hiện tại: <b>{shift_data.free_count}/{shift_data.total_active_members} bạn rảnh</b> ({ratio * 100:.0f}%)")
        st.setStyleSheet(f"font-size: 13px; color: {color};")
        sc_layout.addWidget(st)

        free_names = ", ".join(shift_data.free_members) if shift_data.free_members else "Không có ai"
        fn = QLabel(f"🌿 Các bạn rảnh: <b>{free_names}</b>")
        fn.setStyleSheet("font-size: 12px; color: #047857;")
        fn.setWordWrap(True)
        sc_layout.addWidget(fn)

        if shift_data.busy_details:
            bd_title = QLabel("📚 Các bạn bận học:")
            bd_title.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #991b1b; margin-top: 4px;")
            sc_layout.addWidget(bd_title)
            for b in shift_data.busy_details:
                b_lbl = QLabel(f"• <b>{b['member']}</b>: {b['course']} ({b['room']} - {b['periods']})")
                b_lbl.setStyleSheet("font-size: 11px; color: #4b5563;")
                sc_layout.addWidget(b_lbl)

        self.results_layout.addWidget(summary_card)
        self.results_layout.addStretch()

    def _render_conflicts_view(self) -> None:
        member = self._get_selected_member()
        conflicts = self.compositor.detect_schedule_conflicts(member)

        hdr = QLabel(f"⚠️ Kiểm Tra Xung Đột Lịch Học ({member.name})")
        hdr.setStyleSheet("font-size: 13px; font-weight: 700; color: #111827;")
        self.results_layout.addWidget(hdr)

        if not conflicts:
            card = self._create_info_card(
                "✅ Lịch học hoàn toàn tối ưu!",
                "Không phát hiện môn trùng giờ và không có ca nào phải chuyển quá gấp (≤ 15 phút)."
            )
            self.results_layout.addWidget(card)
        else:
            for c in conflicts:
                card = QFrame()
                is_overlap = c.conflict_type == "overlap"
                bg = CLAUDE_STYLE["conflict_bg"] if is_overlap else CLAUDE_STYLE["accent_warm_bg"]
                border = CLAUDE_STYLE["conflict_border"] if is_overlap else "#fde68a"
                text_col = CLAUDE_STYLE["conflict_text"] if is_overlap else "#b45309"

                card.setStyleSheet(f"""
                    background-color: {bg};
                    border: 1px solid {border};
                    border-radius: 12px;
                    padding: 12px;
                """)
                c_layout = QVBoxLayout(card)
                c_layout.setSpacing(4)

                badge = "⛔ TRÙNG GIỜ HỌC" if is_overlap else "⚡ CHUYỂN CA GẤP"
                b_lbl = QLabel(f"<b>{badge} ({c.day_name})</b>")
                b_lbl.setStyleSheet(f"font-size: 12px; color: {text_col};")
                c_layout.addWidget(b_lbl)

                desc = QLabel(c.message)
                desc.setStyleSheet(f"font-size: 11.5px; color: {text_col}; font-weight: 500;")
                desc.setWordWrap(True)
                c_layout.addWidget(desc)

                self.results_layout.addWidget(card)

        self.results_layout.addStretch()

    def _render_room_view(self, room_query: Optional[str]) -> None:
        rq = room_query or "C302"
        resolved = resolve_room_location(rq)

        card = QFrame()
        card.setStyleSheet(f"""
            background-color: {CLAUDE_STYLE['surface']};
            border: 1.5px solid {CLAUDE_STYLE['accent_terracotta']};
            border-radius: 12px;
            padding: 14px;
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(6)

        title = QLabel(f"📍 Bản Đồ & Vị Trí Phòng: <b>{rq}</b>")
        title.setStyleSheet(f"font-size: 14px; color: {CLAUDE_STYLE['accent_terracotta']};")
        layout.addWidget(title)

        loc_lbl = QLabel(resolved)
        loc_lbl.setStyleSheet("font-size: 12.5px; color: #111827; font-weight: 600;")
        loc_lbl.setWordWrap(True)
        layout.addWidget(loc_lbl)

        tips = QLabel(
            "🏢 <b>Sơ đồ cơ sở Tân Phong TDTU:</b>\n"
            "• Tòa A: CNTT, Máy tính, Khu Thí nghiệm Lab\n"
            "• Tòa B: Giảng đường chuẩn, Hội trường\n"
            "• Tòa C: Viện Sau Đại Học (ThS), Khoa Dược & KHUD\n"
            "• Tòa D: Mỹ thuật Công nghiệp, Kiến trúc, QTKD\n"
            "• Tòa F: Khu giảng đường trung tâm đa năng"
        )
        tips.setStyleSheet("font-size: 11.5px; color: #4b5563; padding-top: 6px;")
        tips.setWordWrap(True)
        layout.addWidget(tips)

        self.results_layout.addWidget(card)
        self.results_layout.addStretch()

    def _render_workload_view(self) -> None:
        member = self._get_selected_member()
        stats = self.compositor.compute_workload_stats(member)

        card = QFrame()
        card.setStyleSheet(f"""
            background-color: {CLAUDE_STYLE['surface']};
            border: 1px solid {CLAUDE_STYLE['border']};
            border-radius: 12px;
            padding: 14px;
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(8)

        title = QLabel(f"📊 Phân Tích Áp Lực Học Tập — {member.name}")
        title.setStyleSheet("font-size: 13.5px; font-weight: 700; color: #111827;")
        layout.addWidget(title)

        meter = QLabel(f"Thang đo: <b>{stats['intensity_label'].upper()}</b>")
        meter.setStyleSheet(f"font-size: 12.5px; color: {stats['intensity_color']}; font-weight: 700;")
        layout.addWidget(meter)

        p1 = QLabel(f"• Tổng số tiết trong tuần: <b>{stats['total_periods']} tiết</b>")
        p2 = QLabel(f"• Số tiết Cử nhân / ĐH: <b>{stats['undergrad_periods']} tiết</b>")
        p3 = QLabel(f"• Số tiết Thạc sĩ / Cao học: <b>{stats['master_periods']} tiết</b>")
        p4 = QLabel(f"• Số ca học buổi tối (Ca 5): <b>{stats['evening_classes']} ca</b>")

        for p in (p1, p2, p3, p4):
            p.setStyleSheet("font-size: 12px; color: #374151;")
            layout.addWidget(p)

        self.results_layout.addWidget(card)
        self.results_layout.addStretch()

    def _render_notes_view(self) -> None:
        member = self._get_selected_member()
        card = QFrame()
        card.setStyleSheet(f"""
            background-color: {CLAUDE_STYLE['surface']};
            border: 1px solid {CLAUDE_STYLE['border']};
            border-radius: 12px;
            padding: 12px;
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(8)

        lbl = QLabel(f"📝 Sổ Tay Ghi Chú Học Tập ({member.name})")
        lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #111827;")
        layout.addWidget(lbl)

        note_edit = QTextEdit()
        note_edit.setPlaceholderText("Lưu link Drive môn học, deadline đồ án, mã nhóm Zalo...")
        note_edit.setStyleSheet(f"""
            background-color: {CLAUDE_STYLE['surface_subtle']};
            border: 1px solid {CLAUDE_STYLE['border']};
            border-radius: 8px;
            padding: 8px;
            font-size: 12px;
        """)
        note_text = self.course_notes.get(member.id, self.course_notes.get("general", ""))
        note_edit.setText(note_text)
        layout.addWidget(note_edit)

        btn_save = QPushButton("💾 Lưu Ghi Chú")
        btn_save.setStyleSheet(self._action_btn_style())
        btn_save.clicked.connect(lambda: self._save_note_text(member.id, note_edit.toPlainText()))
        layout.addWidget(btn_save)

        self.results_layout.addWidget(card)
        self.results_layout.addStretch()

    def _save_note_text(self, member_id: str, text: str) -> None:
        self.course_notes[member_id] = text
        self.course_notes["general"] = text
        self._save_notes()
        self.footer_status.setText("✅ Đã lưu ghi chú thành công!")

    def _render_search_results(self, raw_query: str) -> None:
        member = self._get_selected_member()
        q = raw_query.lower()
        matched: List[ClassSession] = []

        for day, sessions in member.schedule.items():
            for s in sessions:
                match_txt = f"{s.course_name} {s.room} {s.lecturer} {s.course_code} {s.notes}".lower()
                if q in match_txt:
                    matched.append(s)

        hdr = QLabel(f"🔍 Kết quả tìm kiếm cho: \"{raw_query}\" ({len(matched)} môn)")
        hdr.setStyleSheet("font-size: 12.5px; font-weight: 700; color: #111827;")
        self.results_layout.addWidget(hdr)

        if not matched:
            self.results_layout.addWidget(self._create_info_card("Không tìm thấy kết quả phù hợp", "Thử tìm theo tên môn, mã phòng (ví dụ 'C302') hoặc tên giảng viên."))
        else:
            for s in matched:
                self.results_layout.addWidget(self._create_course_card(s))

        self.results_layout.addStretch()

    # --- Helper Card Constructors ---

    def _create_course_card(self, s: ClassSession, extra_status: Optional[str] = None) -> QFrame:
        card = QFrame()
        style = degree_to_style(s.degree_level)
        card.setStyleSheet(f"""
            background-color: {style['bg']};
            border: 1px solid {style['border']};
            border-radius: 12px;
            padding: 10px 12px;
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(8, 6, 8, 6)
        c_layout.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        deg_badge = QLabel(f"{s.badge_text} {s.course_name}")
        deg_badge.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {style['text']};")
        top_row.addWidget(deg_badge, 1)

        if extra_status:
            stat_lbl = QLabel(extra_status)
            stat_lbl.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {style['text']}; opacity: 0.85;")
            top_row.addWidget(stat_lbl)

        c_layout.addLayout(top_row)

        loc = resolve_room_location(s.room)
        loc_row = QLabel(f"📍 {loc} • Tiết {s.start_period}-{s.end_period} ({s.time_range_str})")
        loc_row.setStyleSheet(f"font-size: 11.5px; color: {style['text']}; opacity: 0.9;")
        c_layout.addWidget(loc_row)

        if s.lecturer or s.notes:
            extra_txt = f"👨‍🏫 {s.lecturer}" if s.lecturer else ""
            if s.notes:
                extra_txt += f" — 📝 {s.notes}"
            extra_lbl = QLabel(extra_txt)
            extra_lbl.setStyleSheet(f"font-size: 11px; color: {style['text']}; opacity: 0.75;")
            extra_lbl.setWordWrap(True)
            c_layout.addWidget(extra_lbl)

        btn_copy = QPushButton("📋 Sao chép môn")
        btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy.setFixedWidth(110)
        btn_copy.setStyleSheet(f"""
            QPushButton {{
                background-color: {style['bg']};
                border: 1px solid {style['border']};
                border-radius: 6px;
                padding: 3px 6px;
                font-size: 10.5px;
                font-weight: 600;
                color: {style['text']};
            }}
            QPushButton:hover {{
                background-color: #ffffff;
            }}
        """)
        btn_copy.clicked.connect(lambda: self._copy_single_course(s))
        c_layout.addWidget(btn_copy)

        return card

    def _create_info_card(self, title: str, subtitle: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            background-color: {CLAUDE_STYLE['surface']};
            border: 1px solid {CLAUDE_STYLE['border']};
            border-radius: 12px;
            padding: 14px;
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(4)
        t = QLabel(title)
        t.setStyleSheet("font-size: 13px; font-weight: 700; color: #374151;")
        st = QLabel(subtitle)
        st.setStyleSheet("font-size: 11.5px; color: #6b7280;")
        layout.addWidget(t)
        layout.addWidget(st)
        return card

    # --- Actions ---

    def _copy_single_course(self, s: ClassSession) -> None:
        loc = resolve_room_location(s.room)
        txt = (
            f"[{s.badge_text}] {s.course_name}\n"
            f"• Thời gian: Tiết {s.start_period}-{s.end_period} ({s.time_range_str})\n"
            f"• Vị trí: {loc}\n"
            f"• Giảng viên: {s.lecturer or 'N/A'}\n"
            f"• Bậc: {'Thạc sĩ' if s.is_master else 'Đại học'}"
        )
        QApplication.clipboard().setText(txt)
        self.footer_status.setText(f"📋 Đã chép môn: {s.course_name[:20]}...")

    def _copy_current_view(self) -> None:
        member = self._get_selected_member()
        txt = self.compositor.generate_unified_clipboard_text(member, filter_level=self.filter_degree)
        QApplication.clipboard().setText(txt)
        self.footer_status.setText(f"✨ Đã sao chép TKB {member.name} vào Clipboard!")

    def _export_current_ics(self) -> None:
        member = self._get_selected_member()
        filename = f"tkb_{member.id}.ics"
        content = self.compositor.generate_unified_ics(member, filter_level=self.filter_degree)
        path = Path.home() / "Downloads" / filename
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        self.footer_status.setText(f"✅ Đã lưu {filename} vào Downloads!")


class ClaudeTimetableWindow(QMainWindow):
    """
    Floating, macOS-native desktop window container for ClaudeTimetableWidget.
    Supports stay-on-top, dragging, dynamic resizing, and Studio mode toggling.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("rat — Claude Timetable Assistant")
        self.resize(520, 680)
        self.setMinimumSize(440, 520)

        # Frameless or subtle native look
        self.is_pinned = False
        self._drag_pos = QPoint()

        self.widget = ClaudeTimetableWidget(self)
        self.widget.open_studio_requested.connect(self._open_studio_window)
        self.setCentralWidget(self.widget)

        # Apply drop shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 8)
        self.widget.setGraphicsEffect(shadow)

    def toggle_pin(self) -> None:
        self.is_pinned = not self.is_pinned
        flags = self.windowFlags()
        if self.is_pinned:
            self.setWindowFlags(flags | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowType.WindowStaysOnTopHint)
        self.show()

    def _open_studio_window(self) -> None:
        try:
            from rat.ui.schedule_window import ScheduleCompositorWindow
            self.studio = ScheduleCompositorWindow()
            self.studio.show()
            self.studio.raise_()
            self.studio.activateWindow()
        except Exception as e:
            logger.error(f"Error opening studio: {e}", exc_info=True)

    def _summon_spotlight(self) -> None:
        try:
            from rat.ui.spotlight_window import SpotlightWindow
            if not hasattr(self, "_spotlight_win") or not self._spotlight_win:
                self._spotlight_win = SpotlightWindow()
            self._spotlight_win.show_spotlight()
        except Exception as e:
            logger.error(f"Error summoning spotlight from widget: {e}", exc_info=True)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        modifiers = event.modifiers()
        is_cmd = bool(modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))

        if key == Qt.Key.Key_Escape:
            self.hide()
            return
        elif is_cmd and key == Qt.Key.Key_T:
            self._open_studio_window()
            return
        elif is_cmd and key == Qt.Key.Key_K:
            self._summon_spotlight()
            return

        super().keyPressEvent(event)

