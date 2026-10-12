"""
rat.ui.schedule_window — Aesthetic Native macOS Spotlight-Like Timetable Compositor Window.
Features:
- SOTA Apple macOS Spotlight-like floating design & Command Bar (⌘K instant search).
- View Toggle: Weekly Grid vs Spotlight Today Focus (⌘T).
- Dual Mode: Unified Dual-Degree (Undergrad & Master) vs Club Group Timetable.
- Integrated Overall Utilities Bar:
  1. Next Class Live Countdown & Alert.
  2. Weekly Workload & Academic Intensity Meter.
  3. Campus Room & Building Navigator (TDTU Building & Facility Locator).
  4. Course Scratchpad & Resource Link Keeper.
- macOS Keyboard Shortcuts (⌘K, ⌘T, ⌘1, ⌘2, ⌘C, ⌘E, Esc).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QPoint, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QKeySequence, QPainter, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from rat.timetable.compositor import (
    TimetableCompositor,
    availability_to_color,
    degree_to_style,
)
from rat.timetable.data import load_club_members, save_club_members
from rat.timetable.model import (
    DAYS,
    SHIFTS,
    TDTU_PERIODS,
    ClassSession,
    GoldenWindow,
    LiveClassStatus,
    MemberSchedule,
    ScheduleConflict,
    ShiftAvailability,
    resolve_room_location,
)

logger = logging.getLogger("rat.ui.schedule_window")

NOTES_FILE = Path.home() / ".rat" / "course_notes.json"


def load_course_notes() -> Dict[str, str]:
    if not NOTES_FILE.exists():
        return {}
    try:
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_course_notes(notes: Dict[str, str]) -> None:
    NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(notes, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


SPOTLIGHT_STYLE = """
QMainWindow {
    background-color: #f8fafc;
}

QWidget#CentralWidget {
    background-color: #f8fafc;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Segoe UI", sans-serif;
}

/* Spotlight Command Bar & Header */
QFrame#SpotlightCommandCard {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 18px;
    padding: 12px 18px;
}

QLineEdit#SpotlightSearchInput {
    background-color: #f1f5f9;
    color: #0f172a;
    font-size: 14px;
    font-weight: 500;
    border: 1px solid #cbd5e1;
    border-radius: 12px;
    padding: 8px 14px;
}

QLineEdit#SpotlightSearchInput:focus {
    background-color: #ffffff;
    border: 2px solid #3b82f6;
}

/* Mode Switcher Buttons */
QPushButton.ModeTab {
    border-radius: 10px;
    padding: 7px 14px;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid #e2e8f0;
    background-color: #f8fafc;
    color: #64748b;
}

QPushButton.ModeTab:hover {
    background-color: #f1f5f9;
    border-color: #cbd5e1;
}

QPushButton.ModeTab[active="true"] {
    background-color: #ffffff;
    border: 2px solid #3b82f6;
    color: #1d4ed8;
    font-weight: 700;
}

/* View Switcher: Weekly vs Today */
QPushButton.ViewTab {
    border-radius: 10px;
    padding: 6px 13px;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid #e2e8f0;
    background-color: #f8fafc;
    color: #475569;
}

QPushButton.ViewTab:hover {
    background-color: #f1f5f9;
}

QPushButton.ViewTab[active="true"] {
    background-color: #e0f2fe;
    border: 1px solid #38bdf8;
    color: #0369a1;
    font-weight: 700;
}

/* Live Status Banner */
QFrame#LiveBanner {
    background-color: #f0fdf4;
    border: 1px solid #86efac;
    border-radius: 12px;
    padding: 8px 14px;
}

QFrame#LiveBanner[in_class="true"] {
    background-color: #ecfdf5;
    border: 1.5px solid #10b981;
}

QLabel#LiveClock {
    font-size: 13px;
    font-weight: 700;
    color: #15803d;
    font-family: Menlo, Monaco, monospace;
}

QLabel#LiveStatusText {
    font-size: 12px;
    font-weight: 600;
    color: #166534;
}

/* Golden Highlights */
QFrame#GoldenHighlightsBar {
    background-color: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 12px;
    padding: 7px 14px;
}

QLabel#GoldenHighlightsLabel {
    font-size: 12px;
    font-weight: 600;
    color: #166534;
}

/* Conflict Alert Bar */
QFrame#ConflictAlertBar {
    background-color: #fffbeb;
    border: 1px solid #fde68a;
    border-radius: 12px;
    padding: 7px 14px;
}

QLabel#ConflictAlertText {
    font-size: 12px;
    font-weight: 600;
    color: #92400e;
}

/* Sub-toolbar Cards */
QFrame#MemberFilterCard, QFrame#UnifiedToolbarCard {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 7px 14px;
}

QPushButton.MemberChip, QPushButton.FilterChip {
    border-radius: 12px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid #e2e8f0;
    background-color: #f8fafc;
    color: #475569;
}

QPushButton.MemberChip:hover, QPushButton.FilterChip:hover {
    background-color: #f1f5f9;
    border-color: #cbd5e1;
}

QPushButton.MemberChip[active="true"], QPushButton.FilterChip[active="true"] {
    background-color: #e0f2fe;
    color: #0369a1;
    border: 1px solid #7dd3fc;
}

QPushButton.MemberChip[active="false"] {
    background-color: #f8fafc;
    color: #94a3b8;
    border: 1px dashed #cbd5e1;
    text-decoration: line-through;
}

QComboBox#MemberComboBox {
    background-color: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 10px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 600;
    color: #1e293b;
}

/* Timetable Grid Container */
QFrame#GridContainer {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 12px;
}

QLabel.DayHeader {
    font-size: 13px;
    font-weight: 700;
    color: #334155;
    padding: 6px 4px;
    qproperty-alignment: AlignCenter;
}

QLabel.ShiftHeader {
    font-size: 12px;
    font-weight: 600;
    color: #475569;
    padding: 6px 8px;
    background-color: #f8fafc;
    border-radius: 8px;
    border: 1px solid #f1f5f9;
}

/* Today Spotlight List Container */
QFrame#TodayContainer {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 16px;
}

/* Utilities / Detail Panel Tabs */
QTabWidget#UtilityTabs::pane {
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    background-color: #ffffff;
    padding: 12px;
}

QTabBar::tab {
    background-color: #f8fafc;
    color: #64748b;
    border: 1px solid #e2e8f0;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 6px 12px;
    font-size: 11.5px;
    font-weight: 600;
    margin-right: 4px;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    color: #1d4ed8;
    font-weight: 700;
    border-color: #cbd5e1;
}

/* Bottom Bar */
QFrame#BottomBar {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 8px 16px;
}

QPushButton.ActionButton {
    border-radius: 10px;
    padding: 7px 14px;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid #e2e8f0;
    background-color: #f8fafc;
    color: #1e293b;
}

QPushButton.ActionButton:hover {
    background-color: #f1f5f9;
    border-color: #cbd5e1;
}

QPushButton.PrimaryActionButton {
    border-radius: 10px;
    padding: 7px 16px;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid #16a34a;
    background-color: #16a34a;
    color: #ffffff;
}

QPushButton.PrimaryActionButton:hover {
    background-color: #15803d;
}
"""


class ShiftCellWidget(QFrame):
    """Interactive cell representing availability for one Shift on one Day (CLB Mode)."""
    clicked = pyqtSignal(object)

    def __init__(self, availability: ShiftAvailability, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.availability = availability
        self.setProperty("class", "ShiftCell")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(66)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        color_info = availability_to_color(availability.ratio)

        self.badge_label = QLabel(f"{color_info['badge']}")
        self.badge_label.setProperty("class", "CellBadge")
        self.badge_label.setStyleSheet(f"color: {color_info['text']}; font-weight: 700; font-size: 11px;")
        layout.addWidget(self.badge_label)

        tot = availability.total_active_members
        free_c = availability.free_count
        ratio_pct = int(availability.ratio * 100)

        if tot == 0:
            count_txt = "Chưa chọn ai"
        elif free_c == tot:
            count_txt = f"{free_c}/{tot} bạn rảnh"
        elif free_c == 0:
            count_txt = "Kẹt cả nhóm"
        else:
            count_txt = f"{free_c}/{tot} bạn ({ratio_pct}%)"

        self.count_label = QLabel(count_txt)
        self.count_label.setStyleSheet(f"color: {color_info['text']}; font-size: 11px; opacity: 0.9;")
        layout.addWidget(self.count_label)

        self.setStyleSheet(f"""
            QFrame.ShiftCell {{
                background-color: {color_info['bg']};
                border: 1px solid {color_info['border']};
                border-radius: 10px;
            }}
            QFrame.ShiftCell:hover {{
                background-color: {color_info['bg_hover']};
                border: 2px solid {color_info['text']};
            }}
        """)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.availability)
        super().mousePressEvent(event)


class ClassSessionCard(QFrame):
    """Card widget for a single class session inside an individual timetable shift cell."""
    clicked = pyqtSignal(object)

    def __init__(self, session: ClassSession, is_live: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.session = session
        self.is_live = is_live
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        style = degree_to_style(session.degree_level)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(4)

        badge_lbl = QLabel(session.badge_text)
        badge_lbl.setStyleSheet(f"""
            background-color: {style['tag_bg']};
            color: {style['tag_fg']};
            border-radius: 4px;
            padding: 1px 5px;
            font-size: 10px;
            font-weight: 700;
        """)
        top_row.addWidget(badge_lbl)

        if is_live:
            live_lbl = QLabel("🔴 LIVE")
            live_lbl.setStyleSheet("""
                background-color: #dc2626;
                color: #ffffff;
                border-radius: 4px;
                padding: 1px 4px;
                font-size: 9px;
                font-weight: 800;
            """)
            top_row.addWidget(live_lbl)

        top_row.addStretch()

        if session.room:
            room_lbl = QLabel(f"📍 {session.room}")
            room_lbl.setStyleSheet(f"font-size: 10px; font-weight: 600; color: {style['text']};")
            top_row.addWidget(room_lbl)

        layout.addLayout(top_row)

        name_lbl = QLabel(session.course_name)
        name_lbl.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {style['text']};")
        name_lbl.setWordWrap(True)
        layout.addWidget(name_lbl)

        period_lbl = QLabel(f"Tiết {session.start_period}-{session.end_period} • {session.time_range_str}")
        period_lbl.setStyleSheet("font-size: 10px; color: #64748b;")
        layout.addWidget(period_lbl)

        if session.lecturer:
            lect_lbl = QLabel(f"GV: {session.lecturer}")
            lect_lbl.setStyleSheet("font-size: 9px; color: #94a3b8;")
            lect_lbl.setWordWrap(True)
            layout.addWidget(lect_lbl)

        border_css = "2px solid #22c55e" if is_live else f"1px solid {style['border']}"
        bg_css = "#f0fdf4" if is_live else style['bg']
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_css};
                border: {border_css};
                border-radius: 8px;
            }}
            QFrame:hover {{
                background-color: {style['bg_hover']};
                border-color: {style['text']};
            }}
        """)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.session)
        super().mousePressEvent(event)


class UnifiedShiftCellWidget(QFrame):
    """Cell container rendering class cards for a specific shift in Unified Individual mode."""
    session_clicked = pyqtSignal(object)

    def __init__(
        self,
        sessions: List[ClassSession],
        current_session: Optional[ClassSession] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(66)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        if not sessions:
            empty_frame = QFrame()
            empty_frame.setStyleSheet("""
                QFrame {
                    background-color: #fafaf9;
                    border: 1px dashed #e2e8f0;
                    border-radius: 8px;
                }
            """)
            e_layout = QVBoxLayout(empty_frame)
            e_layout.setContentsMargins(4, 4, 4, 4)
            lbl = QLabel("—")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #cbd5e1; font-size: 11px;")
            e_layout.addWidget(lbl)
            layout.addWidget(empty_frame)
        else:
            for s in sessions:
                is_live = (
                    current_session is not None
                    and s.course_name == current_session.course_name
                    and s.start_period == current_session.start_period
                )
                card = ClassSessionCard(s, is_live=is_live, parent=self)
                card.clicked.connect(self.session_clicked.emit)
                layout.addWidget(card)


class SpotlightTodayCard(QFrame):
    """Spotlight-style floating result card for today's timeline classes."""
    clicked = pyqtSignal(object)

    def __init__(self, item_data: dict, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.session: ClassSession = item_data["session"]
        status = item_data["status"]
        countdown = item_data["countdown"]

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(80)

        style = degree_to_style(self.session.degree_level)
        loc = resolve_room_location(self.session.room)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        # Header Row: Badge + Status + Countdown
        h_row = QHBoxLayout()
        h_row.setSpacing(8)

        deg_badge = QLabel(self.session.badge_text)
        deg_badge.setStyleSheet(f"""
            background-color: {style['tag_bg']};
            color: {style['tag_fg']};
            border-radius: 5px;
            padding: 2px 7px;
            font-size: 11px;
            font-weight: 700;
        """)
        h_row.addWidget(deg_badge)

        if status == "live":
            status_badge = QLabel("🔴 ĐANG DIỄN RA")
            status_badge.setStyleSheet("""
                background-color: #dc2626;
                color: #ffffff;
                border-radius: 5px;
                padding: 2px 7px;
                font-size: 10px;
                font-weight: 800;
            """)
        elif status == "upcoming":
            status_badge = QLabel("⏳ SẮP TỚI")
            status_badge.setStyleSheet("""
                background-color: #f59e0b;
                color: #ffffff;
                border-radius: 5px;
                padding: 2px 7px;
                font-size: 10px;
                font-weight: 700;
            """)
        else:
            status_badge = QLabel("✓ ĐÃ HOÀN THÀNH")
            status_badge.setStyleSheet("""
                background-color: #e2e8f0;
                color: #64748b;
                border-radius: 5px;
                padding: 2px 7px;
                font-size: 10px;
                font-weight: 700;
            """)
        h_row.addWidget(status_badge)

        h_row.addStretch()

        countdown_lbl = QLabel(countdown)
        countdown_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748b;")
        h_row.addWidget(countdown_lbl)
        layout.addLayout(h_row)

        # Course Title
        title_lbl = QLabel(self.session.course_name)
        title_lbl.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {style['text']};")
        layout.addWidget(title_lbl)

        # Meta Row: Time + Room + Lecturer
        meta_row = QHBoxLayout()
        meta_row.setSpacing(12)

        time_lbl = QLabel(f"🕒 Tiết {self.session.start_period}-{self.session.end_period} ({self.session.time_range_str})")
        time_lbl.setStyleSheet("font-size: 11px; color: #475569;")
        meta_row.addWidget(time_lbl)

        loc_lbl = QLabel(loc)
        loc_lbl.setStyleSheet("font-size: 11px; color: #0369a1; font-weight: 600;")
        meta_row.addWidget(loc_lbl)

        if self.session.lecturer:
            lect_lbl = QLabel(f"👨‍🏫 {self.session.lecturer}")
            lect_lbl.setStyleSheet("font-size: 11px; color: #64748b;")
            meta_row.addWidget(lect_lbl)

        meta_row.addStretch()
        layout.addLayout(meta_row)

        border_css = "2px solid #22c55e" if status == "live" else f"1px solid {style['border']}"
        bg_css = "#f0fdf4" if status == "live" else style['bg']
        opacity = "0.75" if status == "completed" else "1.0"

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_css};
                border: {border_css};
                border-radius: 12px;
                opacity: {opacity};
            }}
            QFrame:hover {{
                background-color: {style['bg_hover']};
                border-color: {style['text']};
            }}
        """)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.session)
        super().mousePressEvent(event)


class ScheduleCompositorWindow(QMainWindow):
    """
    Native macOS Spotlight-Like Timetable Compositor & Utilities Hub.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.members: List[MemberSchedule] = load_club_members()
        self.compositor = TimetableCompositor(self.members)
        self.course_notes: Dict[str, str] = load_course_notes()

        # State
        self.current_mode: str = "unified"   # 'unified' | 'group'
        self.view_mode: str = "weekly"       # 'weekly' | 'today'
        self.filter_level: str = "all"       # 'all' | 'undergrad' | 'master'
        self.search_query: str = ""
        self.selected_member_id: str = "m1"
        self.highlight_golden_only: bool = False
        self.selected_availability: Optional[ShiftAvailability] = None
        self.selected_class_session: Optional[ClassSession] = None

        self._init_window()
        self._init_ui()
        self._init_timer()
        self._refresh_all()

    def _init_window(self) -> None:
        self.setWindowTitle("rat — Ghép Lịch & Khung Giờ Vàng CLB (TKB Hợp Nhất ĐH & Thạc Sĩ)")
        self.resize(1200, 800)
        self.setMinimumSize(1000, 680)
        self.setStyleSheet(SPOTLIGHT_STYLE)

    def _init_timer(self) -> None:
        self.live_timer = QTimer(self)
        self.live_timer.setInterval(5000)
        self.live_timer.timeout.connect(self._on_live_tick)
        self.live_timer.start()

    def _init_ui(self) -> None:
        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(10)

        # 1. Spotlight Command Card (Header + Command Search Bar)
        cmd_card = QFrame()
        cmd_card.setObjectName("SpotlightCommandCard")
        cc_layout = QVBoxLayout(cmd_card)
        cc_layout.setContentsMargins(14, 10, 14, 10)
        cc_layout.setSpacing(8)

        # Top Bar: Title + View Switcher (Weekly/Today) + Mode Switcher (Unified/Group) + Stats
        top_row = QHBoxLayout()
        title_box = QVBoxLayout()
        self.title_lbl = QLabel("🎓 Thời Khóa Biểu Hợp Nhất (Đại Học & Thạc Sĩ)")
        self.title_lbl.setStyleSheet("font-size: 17px; font-weight: 700; color: #1e293b;")
        self.subtitle_lbl = QLabel("Live Updated • Phím tắt ⌘K tìm nhanh, ⌘T xem hôm nay, ⌘1/⌘2 đổi chế độ")
        self.subtitle_lbl.setStyleSheet("font-size: 11.5px; color: #64748b;")
        title_box.addWidget(self.title_lbl)
        title_box.addWidget(self.subtitle_lbl)
        top_row.addLayout(title_box)

        top_row.addStretch()

        # View Switcher (Weekly vs Today)
        vbox = QHBoxLayout()
        vbox.setSpacing(4)
        self.btn_view_weekly = QPushButton("📅 Cả tuần")
        self.btn_view_weekly.setProperty("class", "ViewTab")
        self.btn_view_weekly.setProperty("active", "true")
        self.btn_view_weekly.clicked.connect(lambda: self._set_view_mode("weekly"))
        vbox.addWidget(self.btn_view_weekly)

        self.btn_view_today = QPushButton("⚡ Hôm nay (⌘T)")
        self.btn_view_today.setProperty("class", "ViewTab")
        self.btn_view_today.setProperty("active", "false")
        self.btn_view_today.clicked.connect(lambda: self._set_view_mode("today"))
        vbox.addWidget(self.btn_view_today)

        self.btn_view_widget = QPushButton("✦ Widget (⌘W)")
        self.btn_view_widget.setProperty("class", "ViewTab")
        self.btn_view_widget.setProperty("active", "false")
        self.btn_view_widget.clicked.connect(lambda: self._set_view_mode("widget"))
        vbox.addWidget(self.btn_view_widget)
        top_row.addLayout(vbox)

        top_row.addSpacing(10)

        # Mode Switcher (Unified vs Group)
        mode_box = QHBoxLayout()
        mode_box.setSpacing(4)
        self.btn_mode_unified = QPushButton("🎓 TKB Hợp Nhất")
        self.btn_mode_unified.setProperty("class", "ModeTab")
        self.btn_mode_unified.setProperty("active", "true")
        self.btn_mode_unified.clicked.connect(lambda: self._set_mode("unified"))
        mode_box.addWidget(self.btn_mode_unified)

        self.btn_mode_group = QPushButton("🍵 Lịch CLB")
        self.btn_mode_group.setProperty("class", "ModeTab")
        self.btn_mode_group.setProperty("active", "false")
        self.btn_mode_group.clicked.connect(lambda: self._set_mode("group"))
        mode_box.addWidget(self.btn_mode_group)
        top_row.addLayout(mode_box)

        # Stats Pill
        self.stats_pill = QLabel("👥 Đang tải...")
        self.stats_pill.setStyleSheet("""
            background-color: #f1f5f9;
            color: #475569;
            border-radius: 12px;
            padding: 4px 10px;
            font-size: 11.5px;
            font-weight: 600;
            border: 1px solid #e2e8f0;
        """)
        top_row.addWidget(self.stats_pill)

        cc_layout.addLayout(top_row)

        # Spotlight Command Search Input Bar
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.spotlight_search = QLineEdit()
        self.spotlight_search.setObjectName("SpotlightSearchInput")
        self.spotlight_search.setPlaceholderText("🔍 Tìm nhanh môn học, phòng học, giảng viên, mã môn (Nhấn ⌘K để tìm)...")
        self.spotlight_search.setClearButtonEnabled(True)
        self.spotlight_search.textChanged.connect(self._on_search_text_changed)
        search_row.addWidget(self.spotlight_search, 1)

        cc_layout.addLayout(search_row)

        # Banner Alerts
        # 1. Live Academic Clock & Status
        self.live_banner = QFrame()
        self.live_banner.setObjectName("LiveBanner")
        lb_layout = QHBoxLayout(self.live_banner)
        lb_layout.setContentsMargins(12, 5, 12, 5)
        lb_layout.setSpacing(10)
        self.live_clock_lbl = QLabel("🕒 00:00:00")
        self.live_clock_lbl.setObjectName("LiveClock")
        lb_layout.addWidget(self.live_clock_lbl)
        self.live_status_lbl = QLabel("Đang cập nhật thời gian thực...")
        self.live_status_lbl.setObjectName("LiveStatusText")
        self.live_status_lbl.setWordWrap(True)
        lb_layout.addWidget(self.live_status_lbl, 1)
        cc_layout.addWidget(self.live_banner)

        # 2. Golden Highlights (Group Mode)
        self.golden_bar = QFrame()
        self.golden_bar.setObjectName("GoldenHighlightsBar")
        gb_layout = QHBoxLayout(self.golden_bar)
        gb_layout.setContentsMargins(12, 5, 12, 5)
        gb_layout.setSpacing(8)
        self.golden_icon = QLabel("✨")
        gb_layout.addWidget(self.golden_icon)
        self.golden_text = QLabel("Đang quét khung giờ vàng...")
        self.golden_text.setObjectName("GoldenHighlightsLabel")
        self.golden_text.setWordWrap(True)
        gb_layout.addWidget(self.golden_text, 1)
        cc_layout.addWidget(self.golden_bar)

        # 3. Conflict Alert Bar (Unified Mode)
        self.conflict_bar = QFrame()
        self.conflict_bar.setObjectName("ConflictAlertBar")
        cb_layout = QHBoxLayout(self.conflict_bar)
        cb_layout.setContentsMargins(12, 5, 12, 5)
        cb_layout.setSpacing(8)
        self.conflict_icon = QLabel("⚠️")
        cb_layout.addWidget(self.conflict_icon)
        self.conflict_text = QLabel("Không có xung đột lịch học.")
        self.conflict_text.setObjectName("ConflictAlertText")
        self.conflict_text.setWordWrap(True)
        cb_layout.addWidget(self.conflict_text, 1)
        cc_layout.addWidget(self.conflict_bar)

        main_layout.addWidget(cmd_card)

        # 2. Sub-toolbar Cards
        # Group Member Filter Card
        self.member_filter_card = QFrame()
        self.member_filter_card.setObjectName("MemberFilterCard")
        m_layout = QHBoxLayout(self.member_filter_card)
        m_layout.setContentsMargins(10, 5, 10, 5)
        m_layout.setSpacing(8)
        m_label = QLabel("👥 Thành viên CLB:")
        m_label.setStyleSheet("font-size: 12px; font-weight: 700; color: #475569;")
        m_layout.addWidget(m_label)
        self.member_chips_layout = QHBoxLayout()
        self.member_chips_layout.setSpacing(6)
        m_layout.addLayout(self.member_chips_layout)
        m_layout.addStretch()
        btn_all = QPushButton("Tất cả")
        btn_all.setProperty("class", "ActionButton")
        btn_all.setFixedHeight(26)
        btn_all.clicked.connect(self._select_all_members)
        m_layout.addWidget(btn_all)
        btn_clear = QPushButton("Bỏ hết")
        btn_clear.setProperty("class", "ActionButton")
        btn_clear.setFixedHeight(26)
        btn_clear.clicked.connect(self._clear_all_members)
        m_layout.addWidget(btn_clear)
        main_layout.addWidget(self.member_filter_card)

        # Unified Toolbar Card
        self.unified_toolbar_card = QFrame()
        self.unified_toolbar_card.setObjectName("UnifiedToolbarCard")
        ut_layout = QHBoxLayout(self.unified_toolbar_card)
        ut_layout.setContentsMargins(10, 5, 10, 5)
        ut_layout.setSpacing(8)

        lbl_stu = QLabel("👤 Sinh viên:")
        lbl_stu.setStyleSheet("font-size: 12px; font-weight: 700; color: #475569;")
        ut_layout.addWidget(lbl_stu)

        self.member_combo = QComboBox()
        self.member_combo.setObjectName("MemberComboBox")
        for m in self.members:
            suffix = " (Song bằng ĐH & ThS)" if m.is_dual_degree else ""
            self.member_combo.addItem(f"{m.name}{suffix}", m.id)
        self.member_combo.currentIndexChanged.connect(self._on_member_combo_changed)
        ut_layout.addWidget(self.member_combo)

        ut_layout.addSpacing(10)

        lbl_deg = QLabel("Bậc đào tạo:")
        lbl_deg.setStyleSheet("font-size: 12px; font-weight: 600; color: #64748b;")
        ut_layout.addWidget(lbl_deg)

        self.btn_filter_all = QPushButton("Tất cả (Hợp nhất)")
        self.btn_filter_all.setProperty("class", "FilterChip")
        self.btn_filter_all.setProperty("active", "true")
        self.btn_filter_all.clicked.connect(lambda: self._set_degree_filter("all"))
        ut_layout.addWidget(self.btn_filter_all)

        self.btn_filter_undergrad = QPushButton("🎓 Chỉ Đại học")
        self.btn_filter_undergrad.setProperty("class", "FilterChip")
        self.btn_filter_undergrad.setProperty("active", "false")
        self.btn_filter_undergrad.clicked.connect(lambda: self._set_degree_filter("undergrad"))
        ut_layout.addWidget(self.btn_filter_undergrad)

        self.btn_filter_master = QPushButton("🏛️ Chỉ Thạc sĩ")
        self.btn_filter_master.setProperty("class", "FilterChip")
        self.btn_filter_master.setProperty("active", "false")
        self.btn_filter_master.clicked.connect(lambda: self._set_degree_filter("master"))
        ut_layout.addWidget(self.btn_filter_master)

        ut_layout.addStretch()
        main_layout.addWidget(self.unified_toolbar_card)

        # 3. Middle Area: Stacked Views (Weekly Grid vs Today Spotlight) + Right Utilities Hub
        middle_splitter = QSplitter(Qt.Orientation.Horizontal)
        middle_splitter.setChildrenCollapsible(False)

        # Left Views Stack
        self.views_stack = QStackedWidget()

        # View 0: Weekly Grid
        grid_container = QFrame()
        grid_container.setObjectName("GridContainer")
        self.grid_layout = QGridLayout(grid_container)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setSpacing(6)
        grid_scroll = QScrollArea()
        grid_scroll.setWidgetResizable(True)
        grid_scroll.setWidget(grid_container)
        self.views_stack.addWidget(grid_scroll)

        # View 1: Today Spotlight Focus
        today_container = QFrame()
        today_container.setObjectName("TodayContainer")
        self.today_layout = QVBoxLayout(today_container)
        self.today_layout.setContentsMargins(14, 12, 14, 12)
        self.today_layout.setSpacing(10)
        today_scroll = QScrollArea()
        today_scroll.setWidgetResizable(True)
        today_scroll.setWidget(today_container)
        self.views_stack.addWidget(today_scroll)

        # View 2: Claude Interactive Form Widget Mode
        from rat.ui.claude_widget import ClaudeTimetableWidget
        self.claude_widget = ClaudeTimetableWidget()
        self.views_stack.addWidget(self.claude_widget)

        middle_splitter.addWidget(self.views_stack)

        # Right Utilities & Details Hub
        self.right_hub_frame = QFrame()
        self.right_hub_frame.setMinimumWidth(320)
        self.right_hub_frame.setMaximumWidth(390)
        rh_layout = QVBoxLayout(self.right_hub_frame)
        rh_layout.setContentsMargins(0, 0, 0, 0)
        rh_layout.setSpacing(0)

        self.utility_tabs = QTabWidget()
        self.utility_tabs.setObjectName("UtilityTabs")

        # Tab 1: Chi Tiết Môn Học / Ca Học (Inspector)
        self.tab_inspector = QWidget()
        insp_layout = QVBoxLayout(self.tab_inspector)
        insp_layout.setContentsMargins(10, 10, 10, 10)
        insp_layout.setSpacing(8)

        self.detail_title = QLabel("🔍 Chi Tiết Môn Học")
        self.detail_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #1e293b;")
        insp_layout.addWidget(self.detail_title)

        self.detail_sub = QLabel("Bấm vào một ca học trên bảng để xem chi tiết phòng học và giảng viên.")
        self.detail_sub.setStyleSheet("font-size: 11.5px; color: #64748b;")
        self.detail_sub.setWordWrap(True)
        insp_layout.addWidget(self.detail_sub)

        self.detail_content_scroll = QScrollArea()
        self.detail_content_scroll.setWidgetResizable(True)
        self.detail_content_widget = QWidget()
        self.detail_content_layout = QVBoxLayout(self.detail_content_widget)
        self.detail_content_layout.setContentsMargins(0, 0, 0, 0)
        self.detail_content_layout.setSpacing(8)
        self.detail_content_scroll.setWidget(self.detail_content_widget)
        insp_layout.addWidget(self.detail_content_scroll, 1)

        self.utility_tabs.addTab(self.tab_inspector, "🔍 Chi Tiết")

        # Tab 2: Đo Tải Học Tập (Workload Meter)
        self.tab_workload = QWidget()
        wl_layout = QVBoxLayout(self.tab_workload)
        wl_layout.setContentsMargins(10, 10, 10, 10)
        wl_layout.setSpacing(8)

        wl_title = QLabel("📊 Đo Lường Tải Học Tập Tuần")
        wl_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #1e293b;")
        wl_layout.addWidget(wl_title)

        self.workload_summary_lbl = QLabel("Đang tính toán...")
        self.workload_summary_lbl.setStyleSheet("font-size: 12px; color: #475569;")
        self.workload_summary_lbl.setWordWrap(True)
        wl_layout.addWidget(self.workload_summary_lbl)

        self.workload_progress = QProgressBar()
        self.workload_progress.setRange(0, 45)
        self.workload_progress.setValue(25)
        self.workload_progress.setTextVisible(True)
        self.workload_progress.setFixedHeight(18)
        wl_layout.addWidget(self.workload_progress)

        self.workload_details_box = QLabel("")
        self.workload_details_box.setStyleSheet("font-size: 12px; color: #334155; line-height: 1.5;")
        self.workload_details_box.setWordWrap(True)
        wl_layout.addWidget(self.workload_details_box)
        wl_layout.addStretch()

        self.utility_tabs.addTab(self.tab_workload, "📊 Tải Môn")

        # Tab 3: Tra Cứu Tòa Nhà & Phòng Học (Campus Navigator)
        self.tab_campus = QWidget()
        cam_layout = QVBoxLayout(self.tab_campus)
        cam_layout.setContentsMargins(10, 10, 10, 10)
        cam_layout.setSpacing(8)

        cam_title = QLabel("📍 Tra Cứu Vị Trí Phòng TDTU")
        cam_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #1e293b;")
        cam_layout.addWidget(cam_title)

        self.room_query_input = QLineEdit()
        self.room_query_input.setPlaceholderText("Nhập phòng (vd: A608, C302, F702, NTD)...")
        self.room_query_input.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 6px 10px; font-size: 12px;")
        self.room_query_input.textChanged.connect(self._on_room_query_changed)
        cam_layout.addWidget(self.room_query_input)

        self.room_result_lbl = QLabel("Nhập mã phòng để xem vị trí tòa nhà và công năng.")
        self.room_result_lbl.setStyleSheet("""
            background-color: #f0fdf4;
            border: 1px solid #bbf7d0;
            border-radius: 8px;
            padding: 10px;
            font-size: 12px;
            color: #166534;
        """)
        self.room_result_lbl.setWordWrap(True)
        cam_layout.addWidget(self.room_result_lbl)
        cam_layout.addStretch()

        self.utility_tabs.addTab(self.tab_campus, "📍 Phòng TDTU")

        # Tab 4: Sổ Tay & Ghi Chú Môn Học (Course Scratchpad)
        self.tab_notes = QWidget()
        cn_layout = QVBoxLayout(self.tab_notes)
        cn_layout.setContentsMargins(10, 10, 10, 10)
        cn_layout.setSpacing(8)

        cn_title = QLabel("📝 Sổ Tay & Link Tài Liệu Môn Học")
        cn_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #1e293b;")
        cn_layout.addWidget(cn_title)

        self.course_notes_edit = QTextEdit()
        self.course_notes_edit.setPlaceholderText("Ghi chú link Drive, link Meet, bài tập lớn hoặc lời nhắc cho môn đang chọn...")
        self.course_notes_edit.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 8px; font-size: 12px;")
        cn_layout.addWidget(self.course_notes_edit, 1)

        btn_save_note = QPushButton("💾 Lưu ghi chú")
        btn_save_note.setProperty("class", "ActionButton")
        btn_save_note.clicked.connect(self._save_current_course_note)
        cn_layout.addWidget(btn_save_note)

        self.utility_tabs.addTab(self.tab_notes, "📝 Ghi Chú")

        rh_layout.addWidget(self.utility_tabs)
        middle_splitter.addWidget(self.right_hub_frame)

        middle_splitter.setStretchFactor(0, 3)
        middle_splitter.setStretchFactor(1, 1)

        main_layout.addWidget(middle_splitter, 1)

        # 4. Bottom Actions Bar
        bottom_bar = QFrame()
        bottom_bar.setObjectName("BottomBar")
        bb_layout = QHBoxLayout(bottom_bar)
        bb_layout.setContentsMargins(14, 7, 14, 7)
        bb_layout.setSpacing(10)

        self.chk_golden_only = QCheckBox("🌿 Chỉ tô đậm Khung giờ vàng (≥80% rảnh)")
        self.chk_golden_only.setStyleSheet("font-size: 12px; font-weight: 600; color: #475569;")
        self.chk_golden_only.toggled.connect(self._toggle_golden_only)
        bb_layout.addWidget(self.chk_golden_only)

        self.btn_refresh = QPushButton("🔄 Cập nhật Live")
        self.btn_refresh.setProperty("class", "ActionButton")
        self.btn_refresh.clicked.connect(self._on_refresh_clicked)
        bb_layout.addWidget(self.btn_refresh)

        # Keyboard Cheat Hint
        kbd_hint = QLabel("💡 Phím tắt: <b>⌘K</b> Tìm • <b>⌘T</b> Hôm nay • <b>⌘1/⌘2</b> Chế độ • <b>Esc</b> Đóng")
        kbd_hint.setStyleSheet("font-size: 11px; color: #94a3b8;")
        bb_layout.addWidget(kbd_hint)

        bb_layout.addStretch()

        self.btn_copy = QPushButton("📋 Sao chép TKB tổng hợp")
        self.btn_copy.setProperty("class", "ActionButton")
        self.btn_copy.clicked.connect(self._copy_action)
        bb_layout.addWidget(self.btn_copy)

        self.btn_ics = QPushButton("🍏 Xuất Calendar (.ics)")
        self.btn_ics.setProperty("class", "PrimaryActionButton")
        self.btn_ics.clicked.connect(self._export_ics_action)
        bb_layout.addWidget(self.btn_ics)

        main_layout.addWidget(bottom_bar)

    def _set_mode(self, mode: str) -> None:
        self.current_mode = mode
        self.btn_mode_unified.setProperty("active", "true" if mode == "unified" else "false")
        self.btn_mode_group.setProperty("active", "true" if mode == "group" else "false")
        self.btn_mode_unified.style().unpolish(self.btn_mode_unified)
        self.btn_mode_unified.style().polish(self.btn_mode_unified)
        self.btn_mode_group.style().unpolish(self.btn_mode_group)
        self.btn_mode_group.style().polish(self.btn_mode_group)

        if mode == "unified":
            self.title_lbl.setText("🎓 Thời Khóa Biểu Hợp Nhất (Đại Học & Thạc Sĩ)")
            self.btn_copy.setText("📋 Sao chép TKB tổng hợp")
            self.btn_ics.setText("🍏 Xuất Calendar (.ics) Hợp Nhất")
        else:
            self.title_lbl.setText("🍵 Lịch Trình CLB Chill Chill")
            self.btn_copy.setText("📋 Sao chép cho nhóm chat")
            self.btn_ics.setText("🍏 Xuất file Apple / Google Calendar (.ics)")

        self._refresh_all()

    def _set_view_mode(self, v_mode: str) -> None:
        self.view_mode = v_mode
        self.btn_view_weekly.setProperty("active", "true" if v_mode == "weekly" else "false")
        self.btn_view_today.setProperty("active", "true" if v_mode == "today" else "false")
        self.btn_view_widget.setProperty("active", "true" if v_mode == "widget" else "false")
        for b in [self.btn_view_weekly, self.btn_view_today, self.btn_view_widget]:
            b.style().unpolish(b)
            b.style().polish(b)

        if v_mode == "widget":
            self.views_stack.setCurrentIndex(2)
        elif v_mode == "today":
            self.views_stack.setCurrentIndex(1)
        else:
            self.views_stack.setCurrentIndex(0)
        self._refresh_all()

    def _set_degree_filter(self, level: str) -> None:
        self.filter_level = level
        self.btn_filter_all.setProperty("active", "true" if level == "all" else "false")
        self.btn_filter_undergrad.setProperty("active", "true" if level == "undergrad" else "false")
        self.btn_filter_master.setProperty("active", "true" if level == "master" else "false")

        for b in [self.btn_filter_all, self.btn_filter_undergrad, self.btn_filter_master]:
            b.style().unpolish(b)
            b.style().polish(b)

        self._refresh_all()

    def _on_search_text_changed(self, text: str) -> None:
        self.search_query = text
        self._render_grid()
        if self.view_mode == "today":
            self._render_today_spotlight()

    def _on_member_combo_changed(self, idx: int) -> None:
        mid = self.member_combo.currentData()
        if mid:
            self.selected_member_id = mid
            self._refresh_all()

    def _get_selected_member(self) -> MemberSchedule:
        for m in self.members:
            if m.id == self.selected_member_id:
                return m
        return self.members[0] if self.members else MemberSchedule(id="", name="Sinh viên")

    def _on_live_tick(self) -> None:
        try:
            now = datetime.now()
            self.live_clock_lbl.setText(f"🕒 {now.strftime('%H:%M:%S')}")

            if self.current_mode == "unified":
                member = self._get_selected_member()
                status = self.compositor.compute_live_status(member, current_dt=now)
                self.live_status_lbl.setText(f"<b>{status.day_name}:</b> {status.message}")
                self.live_banner.setProperty("in_class", "true" if status.is_in_class else "false")
                self.live_banner.style().unpolish(self.live_banner)
                self.live_banner.style().polish(self.live_banner)

                if self.view_mode == "today":
                    self._render_today_spotlight()
        except Exception as e:
            logger.debug(f"Error in _on_live_tick: {e}")

    def _on_refresh_clicked(self) -> None:
        self.members = load_club_members(force_reset=False)
        self.compositor.members = self.members
        self._refresh_all()

    def _refresh_all(self) -> None:
        try:
            is_unified = (self.current_mode == "unified")

            self.golden_bar.setVisible(not is_unified)
            self.member_filter_card.setVisible(not is_unified)
            self.chk_golden_only.setVisible(not is_unified)

            self.live_banner.setVisible(is_unified)
            self.conflict_bar.setVisible(is_unified)
            self.unified_toolbar_card.setVisible(is_unified)

            active_count = len(self.compositor.active_members)
            total_count = len(self.members)
            if hasattr(self, "stats_pill") and self.stats_pill:
                self.stats_pill.setText(f"👥 {active_count}/{total_count} bạn tham gia")

            self._render_member_chips()

            if is_unified:
                self._render_unified_state()
            else:
                self._render_group_state()

            if self.view_mode == "today":
                self._render_today_spotlight()
            else:
                self._render_grid()

            self._update_workload_utility()

            if is_unified and self.selected_class_session:
                self._render_class_session_details(self.selected_class_session)
            elif not is_unified and self.selected_availability:
                self._render_details(self.selected_availability)
            else:
                self._render_default_details()

        except Exception as e:
            logger.error(f"Error refreshing schedule compositor: {e}", exc_info=True)

    def _render_group_state(self) -> None:
        self._render_golden_highlights()

    def _render_unified_state(self) -> None:
        self._on_live_tick()
        member = self._get_selected_member()
        conflicts = self.compositor.detect_schedule_conflicts(member)

        if conflicts:
            msgs = [c.message for c in conflicts[:2]]
            alert_txt = f"⚠️ <b>Phát hiện xung đột lịch ({len(conflicts)} điểm lưu ý):</b> " + " | ".join(msgs)
            self.conflict_text.setText(alert_txt)
            self.conflict_bar.setStyleSheet("""
                QFrame#ConflictAlertBar {
                    background-color: #fef2f2;
                    border: 1px solid #fecdd3;
                    border-radius: 12px;
                    padding: 7px 14px;
                }
                QLabel#ConflictAlertText {
                    color: #991b1b;
                    font-size: 12px;
                    font-weight: 600;
                }
            """)
            self.conflict_bar.setVisible(True)
        else:
            self.conflict_text.setText("✨ <b>Lịch trình tối ưu:</b> Không có xung đột trùng giờ hay kẹt ca giữa môn Đại học và Thạc sĩ.")
            self.conflict_bar.setStyleSheet("""
                QFrame#ConflictAlertBar {
                    background-color: #f0fdf4;
                    border: 1px solid #bbf7d0;
                    border-radius: 12px;
                    padding: 7px 14px;
                }
                QLabel#ConflictAlertText {
                    color: #166534;
                    font-size: 12px;
                    font-weight: 600;
                }
            """)
            self.conflict_bar.setVisible(True)

    def _render_member_chips(self) -> None:
        while self.member_chips_layout.count():
            item = self.member_chips_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        for m in self.members:
            btn = QPushButton(f"{'✓ ' if m.active else '✕ '}{m.name}")
            btn.setProperty("class", "MemberChip")
            btn.setProperty("active", "true" if m.active else "false")
            btn.clicked.connect(lambda checked, mid=m.id: self._on_toggle_member(mid))
            self.member_chips_layout.addWidget(btn)

    def _on_toggle_member(self, member_id: str) -> None:
        self.compositor.toggle_member(member_id)
        save_club_members(self.members)
        self._refresh_all()

    def _select_all_members(self) -> None:
        for m in self.members:
            m.active = True
        save_club_members(self.members)
        self._refresh_all()

    def _clear_all_members(self) -> None:
        for m in self.members:
            m.active = False
        save_club_members(self.members)
        self._refresh_all()

    def _render_golden_highlights(self) -> None:
        active = self.compositor.active_members
        if not active:
            self.golden_text.setText("⚠️ Chưa có bạn nào được chọn để tìm khung giờ vàng.")
            return

        windows_100 = self.compositor.find_golden_windows(min_ratio=1.0)
        windows_80 = [w for w in self.compositor.find_golden_windows(min_ratio=0.8) if w.free_count < len(active)]

        parts = []
        if windows_100:
            for w in windows_100[:3]:
                parts.append(f"<b>🌿 {w.day_name}</b> ({w.time_range}) • 100% Rảnh")
        if windows_80:
            for w in windows_80[:2]:
                parts.append(f"<b>☀️ {w.day_name}</b> ({w.time_range}) • {w.free_count}/{len(active)} Rảnh")

        if parts:
            html = "  |  ".join(parts)
            self.golden_text.setText(f"✨ <b>Khung giờ vàng gợi ý:</b>  {html}")
        else:
            self.golden_text.setText("🌿 Tuần này không có khung giờ nào cả nhóm cùng rảnh hoàn toàn.")

    def _render_grid(self) -> None:
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        corner_lbl = QLabel("Ca \\ Thứ")
        corner_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #94a3b8; qproperty-alignment: AlignCenter;")
        self.grid_layout.addWidget(corner_lbl, 0, 0)

        for col_idx, (day_code, day_name, _) in enumerate(DAYS, 1):
            day_lbl = QLabel(day_name)
            day_lbl.setProperty("class", "DayHeader")
            self.grid_layout.addWidget(day_lbl, 0, col_idx)

        if self.current_mode == "group":
            self._render_group_grid()
        else:
            self._render_unified_grid()

    def _render_group_grid(self) -> None:
        shift_matrix = self.compositor.compute_shift_matrix()
        for row_idx, (shift_id, shift_name, time_range, (sp, ep)) in enumerate(SHIFTS, 1):
            shift_lbl = QLabel(f"<b>{shift_name}</b><br><span style='font-size:10px; color:#64748b;'>{time_range}</span>")
            shift_lbl.setProperty("class", "ShiftHeader")
            shift_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(shift_lbl, row_idx, 0)

            for col_idx, (day_code, day_name, _) in enumerate(DAYS, 1):
                availability = shift_matrix[day_code][shift_id]
                cell = ShiftCellWidget(availability)
                cell.clicked.connect(self._on_cell_clicked)
                self.grid_layout.addWidget(cell, row_idx, col_idx)

    def _render_unified_grid(self) -> None:
        member = self._get_selected_member()
        unified_sched = self.compositor.compute_unified_individual_schedule(
            member,
            filter_level=self.filter_level,
            search_query=self.search_query
        )

        live_status = self.compositor.compute_live_status(member)
        curr_session = live_status.current_session if live_status.is_in_class else None

        for row_idx, (shift_id, shift_name, time_range, (sp, ep)) in enumerate(SHIFTS, 1):
            shift_lbl = QLabel(f"<b>{shift_name}</b><br><span style='font-size:10px; color:#64748b;'>{time_range}</span>")
            shift_lbl.setProperty("class", "ShiftHeader")
            shift_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(shift_lbl, row_idx, 0)

            for col_idx, (day_code, day_name, _) in enumerate(DAYS, 1):
                day_sessions = unified_sched.get(day_code, [])
                shift_sessions = [s for s in day_sessions if s.overlaps_range(sp, ep)]

                cell = UnifiedShiftCellWidget(shift_sessions, current_session=curr_session)
                cell.session_clicked.connect(self._on_class_session_clicked)
                self.grid_layout.addWidget(cell, row_idx, col_idx)

    def _render_today_spotlight(self) -> None:
        """Renders vertical Spotlight timeline of today's classes."""
        while self.today_layout.count():
            item = self.today_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        member = self._get_selected_member()
        agenda = self.compositor.get_today_agenda(member)

        # Filter by search query if any
        q = self.search_query.strip().lower()
        if q:
            agenda = [
                item for item in agenda
                if q in f"{item['session'].course_name} {item['session'].room} {item['session'].lecturer}".lower()
            ]

        # Header for Today Spotlight
        now = datetime.now()
        weekday_map = {0: "Thứ Hai", 1: "Thứ Ba", 2: "Thứ Tư", 3: "Thứ Năm", 4: "Thứ Sáu", 5: "Thứ Bảy", 6: "Chủ Nhật"}
        day_str = weekday_map[now.weekday()]

        hdr_box = QFrame()
        hdr_box.setStyleSheet("background-color: #f1f5f9; border-radius: 10px; padding: 10px 14px;")
        hb_layout = QHBoxLayout(hdr_box)
        hb_layout.setContentsMargins(0, 0, 0, 0)

        t_lbl = QLabel(f"⚡ <b>Lịch Trình Hôm Nay ({day_str}, {now.strftime('%d/%m/%Y')}):</b> {len(agenda)} môn học")
        t_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #1e293b;")
        hb_layout.addWidget(t_lbl)
        hb_layout.addStretch()

        self.today_layout.addWidget(hdr_box)

        if not agenda:
            empty_card = QFrame()
            empty_card.setStyleSheet("background-color: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 14px; padding: 30px;")
            ec_layout = QVBoxLayout(empty_card)
            ec_layout.setSpacing(6)
            msg1 = QLabel("🌿 Hôm Nay Bạn Không Có Lịch Học Nào")
            msg1.setStyleSheet("font-size: 15px; font-weight: 700; color: #166534;")
            msg1.setAlignment(Qt.AlignmentFlag.AlignCenter)
            msg2 = QLabel("Hãy tận hưởng ngày nghỉ hoặc tự nghiên cứu đồ án nhé!")
            msg2.setStyleSheet("font-size: 12px; color: #64748b;")
            msg2.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ec_layout.addWidget(msg1)
            ec_layout.addWidget(msg2)
            self.today_layout.addWidget(empty_card)
        else:
            for item in agenda:
                card = SpotlightTodayCard(item, parent=self)
                card.clicked.connect(self._on_class_session_clicked)
                self.today_layout.addWidget(card)

        self.today_layout.addStretch()

    def _update_workload_utility(self) -> None:
        member = self._get_selected_member()
        stats = self.compositor.compute_workload_stats(member)

        self.workload_summary_lbl.setText(
            f"Tổng tải tuần: <b>{stats['total_periods']} tiết</b> • Trạng thái: <b style='color:{stats['intensity_color']};'>{stats['intensity_label']}</b>"
        )
        self.workload_progress.setValue(min(45, stats['total_periods']))
        self.workload_progress.setStyleSheet(f"""
            QProgressBar::chunk {{
                background-color: {stats['intensity_color']};
                border-radius: 6px;
            }}
        """)

        ug_c = stats['undergrad_periods']
        ms_c = stats['master_periods']
        details_txt = (
            f"• 🎓 <b>Đại học (Cử nhân):</b> {ug_c} tiết ({int(stats['ug_ratio']*100)}%)\n"
            f"• 🏛️ <b>Thạc sĩ (Cao học):</b> {ms_c} tiết ({int(stats['ms_ratio']*100)}%)\n\n"
            f"• 🌅 <b>Ca sáng (Tiết 1-6):</b> {stats['morning_classes']} ca\n"
            f"• ☀️ <b>Ca chiều (Tiết 7-12):</b> {stats['afternoon_classes']} ca\n"
            f"• 🌙 <b>Ca tối (Tiết 13-15):</b> {stats['evening_classes']} ca (Thạc sĩ TDTU)"
        )
        self.workload_details_box.setText(details_txt)

    def _on_room_query_changed(self, text: str) -> None:
        res = resolve_room_location(text)
        self.room_result_lbl.setText(res)

    def _save_current_course_note(self) -> None:
        if not self.selected_class_session:
            key = "general"
        else:
            key = f"{self.selected_class_session.course_name}_{self.selected_class_session.start_period}"
        txt = self.course_notes_edit.toPlainText().strip()
        self.course_notes[key] = txt
        save_course_notes(self.course_notes)
        self._show_info_dialog("rat", "Đã lưu ghi chú môn học thành công!")

    def _show_info_dialog(self, title: str, text: str) -> None:
        if hasattr(self, "subtitle_lbl"):
            old_text = self.subtitle_lbl.text()
            self.subtitle_lbl.setText(f"✓ {text}")
            self.subtitle_lbl.setStyleSheet("font-size: 11.5px; color: #16a34a; font-weight: 600;")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(2500, lambda: (
                self.subtitle_lbl.setText(old_text),
                self.subtitle_lbl.setStyleSheet("font-size: 11.5px; color: #64748b; font-weight: normal;")
            ))

    def _on_cell_clicked(self, availability: ShiftAvailability) -> None:
        self.selected_availability = availability
        self.selected_class_session = None
        self.utility_tabs.setCurrentIndex(0)
        self._render_details(availability)

    def _on_class_session_clicked(self, session: ClassSession) -> None:
        self.selected_class_session = session
        self.selected_availability = None
        self.utility_tabs.setCurrentIndex(0)
        self._render_class_session_details(session)

        # Load notes for this session
        key = f"{session.course_name}_{session.start_period}"
        note_text = self.course_notes.get(key, "")
        self.course_notes_edit.setText(note_text)

    def _render_default_details(self) -> None:
        self._clear_detail_layout()
        lbl = QLabel("✨ Chọn một môn học trên bảng hoặc danh sách hôm nay để xem chi tiết.")
        lbl.setStyleSheet("color: #64748b; font-size: 12px; padding: 20px 0;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_content_layout.addWidget(lbl)

    def _clear_detail_layout(self) -> None:
        while self.detail_content_layout.count():
            item = self.detail_content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _render_class_session_details(self, s: ClassSession) -> None:
        self._clear_detail_layout()
        style = degree_to_style(s.degree_level)
        self.detail_title.setText(f"{s.badge_text} {s.course_name}")
        self.detail_sub.setText(f"🕒 Tiết {s.start_period} ➔ {s.end_period} ({s.time_range_str})")

        deg_box = QFrame()
        deg_box.setStyleSheet(f"""
            background-color: {style['bg']};
            border: 1px solid {style['border']};
            border-radius: 10px;
            padding: 10px;
        """)
        db_layout = QVBoxLayout(deg_box)
        db_layout.setContentsMargins(10, 8, 10, 8)
        db_layout.setSpacing(4)

        deg_title = QLabel(f"{style['badge']} Bậc đào tạo: {style['level_name']}")
        deg_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {style['text']};")
        db_layout.addWidget(deg_title)

        loc = resolve_room_location(s.room)
        deg_desc = QLabel(f"{loc}\n{'Viện Sau Đại Học TDTU' if s.is_master else 'Đại học chính quy TDTU'}")
        deg_desc.setStyleSheet(f"font-size: 11.5px; color: {style['text']}; opacity: 0.95;")
        deg_desc.setWordWrap(True)
        db_layout.addWidget(deg_desc)

        self.detail_content_layout.addWidget(deg_box)

        attr_card = QFrame()
        attr_card.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px;")
        ac_layout = QVBoxLayout(attr_card)
        ac_layout.setContentsMargins(10, 8, 10, 8)
        ac_layout.setSpacing(6)

        def make_row(icon: str, label: str, value: str):
            lbl = QLabel(f"{icon} <b>{label}:</b> {value or 'Chưa rõ'}")
            lbl.setStyleSheet("font-size: 12px; color: #1e293b;")
            lbl.setWordWrap(True)
            return lbl

        ac_layout.addWidget(make_row("📍", "Phòng học", s.room))
        ac_layout.addWidget(make_row("👨‍🏫", "Giảng viên", s.lecturer))
        ac_layout.addWidget(make_row("🏷️", "Mã môn học", s.course_code))
        ac_layout.addWidget(make_row("🕒", "Khung giờ", f"Tiết {s.start_period}-{s.end_period} ({s.time_range_str})"))
        if s.notes:
            ac_layout.addWidget(make_row("📝", "Ghi chú", s.notes))

        self.detail_content_layout.addWidget(attr_card)

        btn_copy_single = QPushButton("📋 Sao chép thông tin môn này")
        btn_copy_single.setProperty("class", "ActionButton")
        btn_copy_single.clicked.connect(lambda: self._copy_single_course(s))
        self.detail_content_layout.addWidget(btn_copy_single)

        self.detail_content_layout.addStretch()

    def _copy_single_course(self, s: ClassSession) -> None:
        loc = resolve_room_location(s.room)
        txt = (
            f"[{s.badge_text}] {s.course_name}\n"
            f"• Thời gian: Tiết {s.start_period}-{s.end_period} ({s.time_range_str})\n"
            f"• Vị trí: {loc}\n"
            f"• Giảng viên: {s.lecturer or 'N/A'}\n"
            f"• Bậc: {'Thạc sĩ / Cao học' if s.is_master else 'Đại học'}"
        )
        QApplication.clipboard().setText(txt)
        self._show_info_dialog("rat", f"Đã sao chép thông tin môn: {s.course_name}!")

    def _render_details(self, a: ShiftAvailability) -> None:
        self._clear_detail_layout()
        self.detail_title.setText(f"📍 {a.day_name} — {a.shift_name}")
        self.detail_sub.setText(f"🕒 {a.time_range} (Tiết {a.start_period} ➔ {a.end_period})")

        color_info = availability_to_color(a.ratio)
        badge_box = QFrame()
        badge_box.setStyleSheet(f"background-color: {color_info['bg']}; border: 1px solid {color_info['border']}; border-radius: 10px; padding: 10px;")
        bb_layout = QVBoxLayout(badge_box)
        bb_layout.setContentsMargins(10, 8, 10, 8)

        lbl_status = QLabel(f"{color_info['badge']} • {a.free_count}/{a.total_active_members} bạn rảnh")
        lbl_status.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {color_info['text']};")
        bb_layout.addWidget(lbl_status)

        lbl_desc = QLabel(color_info["desc"])
        lbl_desc.setStyleSheet(f"font-size: 11px; color: {color_info['text']}; opacity: 0.85;")
        bb_layout.addWidget(lbl_desc)
        self.detail_content_layout.addWidget(badge_box)

        lbl_free_title = QLabel(f"🌿 Các bạn rảnh ({len(a.free_members)}):")
        lbl_free_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #166534; margin-top: 6px;")
        self.detail_content_layout.addWidget(lbl_free_title)

        if a.free_members:
            for name in a.free_members:
                row = QLabel(f"• {name}")
                row.setStyleSheet("font-size: 12px; color: #1e293b; padding-left: 8px;")
                self.detail_content_layout.addWidget(row)
        else:
            none_lbl = QLabel("• Không có bạn nào rảnh trong ca này.")
            none_lbl.setStyleSheet("font-size: 11px; color: #94a3b8; font-style: italic; padding-left: 8px;")
            self.detail_content_layout.addWidget(none_lbl)

        lbl_busy_title = QLabel(f"📚 Các bạn bận học ({len(a.busy_details)}):")
        lbl_busy_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #991b1b; margin-top: 8px;")
        self.detail_content_layout.addWidget(lbl_busy_title)

        if a.busy_details:
            for b in a.busy_details:
                card = QFrame()
                card.setStyleSheet("background-color: #fff1f2; border: 1px solid #fecdd3; border-radius: 8px; padding: 6px 8px;")
                c_layout = QVBoxLayout(card)
                c_layout.setContentsMargins(6, 4, 6, 4)
                c_layout.setSpacing(2)

                m_name = QLabel(f"<b>{b['member']}</b>")
                m_name.setStyleSheet("font-size: 11.5px; color: #9f1239;")
                c_layout.addWidget(m_name)

                c_info = QLabel(f"📖 {b['course']}")
                c_info.setStyleSheet("font-size: 11px; color: #475569;")
                c_info.setWordWrap(True)
                c_layout.addWidget(c_info)

                sub_info = QLabel(f"📍 {b['room']}  •  {b['periods']}")
                sub_info.setStyleSheet("font-size: 10px; color: #64748b;")
                c_layout.addWidget(sub_info)

                self.detail_content_layout.addWidget(card)
        else:
            none_busy = QLabel("• Tuyệt vời! Không ai bị kẹt lịch.")
            none_busy.setStyleSheet("font-size: 11px; color: #166534; font-style: italic; padding-left: 8px;")
            self.detail_content_layout.addWidget(none_busy)

        self.detail_content_layout.addStretch()

    def _toggle_golden_only(self, checked: bool) -> None:
        self.highlight_golden_only = checked
        self._render_grid()

    def _copy_action(self) -> None:
        try:
            if self.current_mode == "unified":
                member = self._get_selected_member()
                msg = self.compositor.generate_unified_clipboard_text(member, filter_level=self.filter_level)
                title = f"TKB Hợp Nhất ({member.name})"
            else:
                msg = self.compositor.generate_chat_message()
                title = "Lịch Trống Chung CLB"

            QApplication.clipboard().setText(msg)
            self._show_info_dialog(
                "rat — Đã sao chép",
                f"✨ Đã sao chép {title} vào bộ nhớ tạm!\nBạn có thể dán (Cmd+V) vào Zalo, Messenger, hoặc Apple Notes."
            )
        except Exception as e:
            logger.error(f"Error copying schedule: {e}", exc_info=True)

    def _export_ics_action(self) -> None:
        try:
            if self.current_mode == "unified":
                member = self._get_selected_member()
                filename = f"tkb_hop_nhat_{member.id}.ics"
                ics_content = self.compositor.generate_unified_ics(member, filter_level=self.filter_level)
                dialog_title = f"Lưu file TKB Hợp Nhất ({member.name})"
            else:
                filename = "club_free_slots.ics"
                ics_content = self.compositor.generate_ics_content(min_ratio=0.8)
                dialog_title = "Lưu file lịch trống CLB (.ics)"

            default_path = str(Path.home() / "Downloads" / filename)
            filepath, _ = QFileDialog.getSaveFileName(
                self,
                dialog_title,
                default_path,
                "iCalendar Files (*.ics)"
            )
            if not filepath:
                return

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(ics_content)

            if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
                reply = QMessageBox.question(
                    self,
                    "rat — Xuất Lịch Thành Công",
                    f"✅ Đã xuất file lịch thành công tại:\n{filepath}\n\nBạn có muốn mở ngay bằng Apple Calendar để đồng bộ không?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    subprocess.run(["open", filepath], check=False)
        except Exception as e:
            logger.error(f"Error exporting ICS file: {e}", exc_info=True)
            if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
                QMessageBox.critical(self, "Lỗi xuất file", f"Không thể xuất file: {e}")

    def keyPressEvent(self, event) -> None:
        key = event.key()
        modifiers = event.modifiers()
        is_cmd = bool(modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))

        if key == Qt.Key.Key_Escape:
            self.hide()
            return
        elif is_cmd and key == Qt.Key.Key_K:
            self.spotlight_search.setFocus()
            self.spotlight_search.selectAll()
            return
        elif is_cmd and key == Qt.Key.Key_T:
            new_v = "weekly" if self.view_mode == "today" else "today"
            self._set_view_mode(new_v)
            return
        elif is_cmd and key == Qt.Key.Key_W:
            new_v = "weekly" if self.view_mode == "widget" else "widget"
            self._set_view_mode(new_v)
            return
        elif is_cmd and key == Qt.Key.Key_1:
            self._set_mode("unified")
            return
        elif is_cmd and key == Qt.Key.Key_2:
            self._set_mode("group")
            return
        elif is_cmd and key == Qt.Key.Key_C:
            self._copy_action()
            return
        elif is_cmd and key == Qt.Key.Key_E:
            self._export_ics_action()
            return

        super().keyPressEvent(event)

    def shutdown(self) -> None:
        if hasattr(self, "live_timer") and self.live_timer.isActive():
            self.live_timer.stop()
        if hasattr(self, "claude_widget") and hasattr(self.claude_widget, "timer"):
            if self.claude_widget.timer.isActive():
                self.claude_widget.timer.stop()

    def closeEvent(self, event) -> None:
        app = QApplication.instance()
        if app and not getattr(app, "_is_quitting", False):
            event.ignore()
            self.hide()
            return
        self.shutdown()
        super().closeEvent(event)
