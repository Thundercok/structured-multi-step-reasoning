"""
rat.ui.turn_notes_preview — Interactive Stage 1 UX Preview for Turn Notes.
Demonstrates:
1. Turn-level notes rendered as lightweight text lines on chat background (frame only when editing)
2. Preserving older revisions with legible text, replacement label, and forward links
3. Backward links from replacement notes to older revisions
4. Inline editing with draft preservation across compact toggle, keyboard shortcuts, and stale error warnings
5. Separate navigation link vs "Sửa bản mới" action (opens replacement note editor)
6. Predecessor forward link dynamically updates when successor is edited
7. Mascot 'Chuột' standing on the left with gentle, playful motion (respects reduce motion)
8. Clicking Chuột emotes and highlights latest active note with friendly natural phrasing
9. Real ChatComposer shell and authentic compact HUD sizing
10. Collapsible QA testing dock to keep primary review surface clean
"""
from __future__ import annotations

import copy
from typing import Dict, List, Optional

from PyQt6.QtCore import QEvent, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QKeySequence, QPainter, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from rat.ui.live_companion import LiveCompanion
from rat.ui.surface_layout import ChatComposer, motion_enabled
from rat.ui.turn_notes import InlineNoteRow, TurnNoteItem, TurnNotesPane
from rat.ui.work_context import WorkTracePane
from rat.engine.assistant_runtime import AgentStep


FIXTURE_TURNS = [
    {
        "turn_id": 1,
        "user_message": "Mình có 20 phút, chỉ ôn TCP.",
        "assistant_message": "Đã rõ! Mình sẽ tập trung vào cơ chế **bắt tay 3 bước** (3-way handshake) và **điều khiển luồng** (flow control) của TCP cho bạn trong 20 phút.",
        "trace_steps": [
            AgentStep(1, "Phân tích yêu cầu và ràng buộc thời gian", "analyze_intent", {}, {"time": "20m", "topic": "TCP"}),
            AgentStep(2, "Ghi nhận ràng buộc ôn tập", "record_work_note", {"text": "Có 20 phút · Chỉ ôn TCP."}, {"status": "committed"}),
        ],
        "notes": [
            TurnNoteItem(
                id="note-tcp-time",
                turn_id=1,
                text="Có 20 phút · Chỉ ôn TCP.",
                status="active",
                source="user_quote",
                quote="Mình có 20 phút, chỉ ôn TCP.",
                revision=1,
            )
        ],
    },
    {
        "turn_id": 2,
        "user_message": "Đổi thành 30 phút nhé.",
        "assistant_message": "Đã cập nhật thời gian học lên **30 phút**. Với thêm 10 phút này, chúng ta có thể đi tiếp sang cả phần **TCP Congestion Control** (Tahoe & Reno).",
        "trace_steps": [
            AgentStep(1, "Nhận diện thay đổi thời gian từ 20 sang 30 phút", "update_work_note", {}, {"before": "20 phút", "after": "30 phút"}),
            AgentStep(2, "Cập nhật ngữ cảnh ôn tập", "record_work_note", {"text": "20 → 30 phút (TCP)"}, {"status": "committed"}),
        ],
        "notes": [
            TurnNoteItem(
                id="note-tcp-time-v2",
                turn_id=2,
                text="Có 30 phút · Chỉ ôn TCP (Congestion Control).",
                status="active",
                source="user_edit",
                quote="Đổi thành 30 phút nhé.",
                revision=2,
                replaces_note_id="note-tcp-time",
                replaces_turn_id=1,
                replaces_text="Có 20 phút",
            )
        ],
    },
    {
        "turn_id": 3,
        "user_message": "Nếu kịp thì làm luôn bài tập trắc nghiệm cuối chương.",
        "assistant_message": "Bộ trắc nghiệm TCP có 15 câu, dự kiến cần thêm khoảng 15 phút nữa nếu làm kỹ. Bạn có muốn dời sang buổi sau để giữ đúng 30 phút không?",
        "trace_steps": [
            AgentStep(1, "Ước lượng thời gian làm 15 câu trắc nghiệm", "estimate_workload", {}, {"questions": 15, "minutes_needed": 15}),
        ],
        "notes": [
            TurnNoteItem(
                id="note-tcp-quiz-proposal",
                turn_id=3,
                text="Dời bài tập trắc nghiệm TCP sang chiều thứ 5.",
                status="proposed",
                source="model_proposal",
                confirmed=False,
                revision=1,
            )
        ],
    },
]


class TurnWidget(QFrame):
    """Visual card for one conversation turn containing user prompt, assistant reply, turn notes, and trace."""
    navigate_turn_requested = pyqtSignal(int, str)
    edit_replacement_requested = pyqtSignal(int, str)

    def __init__(self, turn_data: dict, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.turn_id = turn_data["turn_id"]
        self.turn_data = turn_data
        self.setObjectName(f"TurnWidget_{self.turn_id}")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setStyleSheet("""
            QFrame[objectName^="TurnWidget"] {
                background: transparent;
                border: none;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 8)
        layout.setSpacing(5)

        # 1. User Message Row (PlainText)
        user_row = QHBoxLayout()
        user_row.setContentsMargins(0, 0, 0, 0)
        user_label = QLabel(f"Bạn: {turn_data['user_message']}")
        user_label.setTextFormat(Qt.TextFormat.PlainText)
        user_label.setWordWrap(True)
        user_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        user_label.setStyleSheet("color: #8C7B65; font-size: 12px; font-weight: 500; padding: 1px 0;")
        user_row.addWidget(user_label, 1)
        layout.addLayout(user_row)

        # 2. Assistant Response Bubble (Render Markdown)
        self.reply_label = QLabel()
        self.reply_label.setTextFormat(Qt.TextFormat.MarkdownText)
        self.reply_label.setText(turn_data["assistant_message"])
        self.reply_label.setWordWrap(True)
        self.reply_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.reply_label.setStyleSheet("color: #2F2920; font-size: 13px; line-height: 1.4; padding: 1px 0;")
        layout.addWidget(self.reply_label)

        # 3. Inline Turn Notes Pane (Lightweight line on chat surface)
        self.notes_pane = TurnNotesPane(self.turn_id, self)
        self.notes_pane.navigate_requested.connect(self.navigate_turn_requested.emit)
        self.notes_pane.edit_replacement_requested.connect(self.edit_replacement_requested.emit)
        layout.addWidget(self.notes_pane)

        # 4. Work Trace Pane ("Cách Chuột làm")
        self.work_trace = WorkTracePane(self)
        for step in turn_data.get("trace_steps", []):
            self.work_trace.add_step(step)
        self.work_trace.set_status("Đã hoàn tất")
        layout.addWidget(self.work_trace)

    def set_notes(self, notes: List[TurnNoteItem]) -> None:
        self.notes_pane.set_notes(notes)


class TurnNotesPreviewWindow(QMainWindow):
    """
    Interactive Stage 1 UX testbed for evaluating Turn-level notes.
    Pure fixture data — completely decoupled from live AI models.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.is_expanded = True
        self.turns_data = copy.deepcopy(FIXTURE_TURNS)
        self.turn_widgets: Dict[int, TurnWidget] = {}
        self._revealed_compact_turn: Optional[int] = None
        self._init_window()
        self._init_ui()
        self._populate_turns()

    def _init_window(self) -> None:
        self.setWindowTitle("RAT · Bản xem Giao diện Ghi chép theo Lượt (Fixture)")
        self.setMinimumSize(660, 360)
        self.resize(740, 600)
        self.setStyleSheet("""
            QMainWindow {
                background: #F3ECE1;
            }
            QLabel {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            }
        """)

        # ⌘L shortcut for switching Compact / Full mode
        shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        shortcut.activated.connect(self.toggle_expanded)
        shortcut_meta = QShortcut(QKeySequence("Meta+L"), self)
        shortcut_meta.activated.connect(self.toggle_expanded)

    def _init_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_vbox = QVBoxLayout(central_widget)
        main_vbox.setContentsMargins(12, 10, 12, 10)
        main_vbox.setSpacing(8)

        # -------------------------------------------------------------
        # Header Disclaimer Banner
        # -------------------------------------------------------------
        banner = QFrame()
        banner.setObjectName("BannerFrame")
        banner.setStyleSheet("""
            QFrame#BannerFrame {
                background: #FFF7ED;
                border: 1px solid #FED7AA;
                border-radius: 8px;
                padding: 4px 8px;
            }
        """)
        b_layout = QHBoxLayout(banner)
        b_layout.setContentsMargins(4, 2, 4, 2)
        b_layout.setSpacing(6)

        disclaimer_icon = QLabel("⚠️")
        disclaimer_icon.setStyleSheet("font-size: 13px; background: transparent; border: none;")
        b_layout.addWidget(disclaimer_icon, 0)

        disclaimer_text = QLabel(
            "<b>Bản xem giao diện Giai đoạn 1 (Dữ liệu mẫu / Fixture)</b> · "
            "Ghi chú là dòng nhẹ liền với phản hồi. Bản cũ giữ nguyên & dẫn tới bản mới. "
            "Chưa nối live model AI."
        )
        disclaimer_text.setWordWrap(True)
        disclaimer_text.setStyleSheet("color: #9A3412; font-size: 11px; background: transparent; border: none;")
        b_layout.addWidget(disclaimer_text, 1)

        self.btn_toggle_qa = QPushButton("🛠 Công cụ thử nghiệm")
        self.btn_toggle_qa.setStyleSheet("""
            QPushButton {
                background: #FFFFFF;
                color: #8C6A43;
                border: 1px solid #E2D3BE;
                border-radius: 5px;
                padding: 3px 8px;
                font-size: 11px;
            }
            QPushButton:hover { background: #FAF5ED; }
        """)
        self.btn_toggle_qa.clicked.connect(self._toggle_qa_dock)
        b_layout.addWidget(self.btn_toggle_qa, 0)

        self.btn_mode_toggle = QPushButton("Đầy đủ (⌘L)")
        self.btn_mode_toggle.setStyleSheet("""
            QPushButton {
                background: #FFFFFF;
                color: #7A5B36;
                border: 1px solid #E2D3BE;
                border-radius: 5px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover { background: #FAF5ED; }
        """)
        self.btn_mode_toggle.clicked.connect(self.toggle_expanded)
        b_layout.addWidget(self.btn_mode_toggle, 0)

        main_vbox.addWidget(banner, 0)

        # -------------------------------------------------------------
        # Main Work Area: Chuột (Left) + Chat Container (Center)
        # -------------------------------------------------------------
        work_hbox = QHBoxLayout()
        work_hbox.setContentsMargins(0, 0, 0, 0)
        work_hbox.setSpacing(10)

        # LEFT: Chuột (LiveCompanion)
        left_stage = QWidget()
        left_stage.setFixedWidth(148)
        left_layout = QVBoxLayout(left_stage)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.companion = LiveCompanion(self, left_stage)
        self.companion.clicked.disconnect()  # Disconnect old notebook pane behavior
        self.companion.clicked.connect(self._on_companion_clicked)
        left_layout.addWidget(self.companion, 0, Qt.AlignmentFlag.AlignHCenter)

        companion_hint = QLabel("Chạm Chuột để emote<br>& xem ghi chép")
        companion_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        companion_hint.setStyleSheet("color: #A3937F; font-size: 11px; background: transparent; border: none;")
        left_layout.addWidget(companion_hint, 0, Qt.AlignmentFlag.AlignHCenter)

        work_hbox.addWidget(left_stage, 0)

        # CENTER: Chat Container (Warm Paper Card with authentic RAT styling)
        self.container = QFrame()
        self.container.setObjectName("SpotlightContainer")
        self.container.setStyleSheet("""
            QFrame#SpotlightContainer {
                background: #FFFDFA;
                border: 1px solid #DDD7CD;
                border-radius: 14px;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self.container)
        shadow.setBlurRadius(14)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(42, 34, 25, 20))
        self.container.setGraphicsEffect(shadow)

        c_layout = QVBoxLayout(self.container)
        c_layout.setContentsMargins(12, 10, 12, 10)
        c_layout.setSpacing(6)

        # Reveal banner for compact mode navigation
        self.compact_nav_banner = QFrame()
        self.compact_nav_banner.setStyleSheet("""
            QFrame {
                background: #FAF3E8;
                border: 1px solid #E5D5C1;
                border-radius: 6px;
                padding: 3px 6px;
            }
        """)
        cnb_layout = QHBoxLayout(self.compact_nav_banner)
        cnb_layout.setContentsMargins(2, 1, 2, 1)
        cnb_layout.setSpacing(6)
        self.cnb_label = QLabel("Đang xem chi tiết lượt cũ")
        self.cnb_label.setStyleSheet("color: #7A5B36; font-size: 11px; font-weight: 500;")
        cnb_layout.addWidget(self.cnb_label, 1)

        btn_return = QPushButton("← Quay về lượt hiện tại")
        btn_return.setStyleSheet("""
            QPushButton {
                color: #FFFFFF;
                background: #8C6A43;
                border: none;
                border-radius: 4px;
                padding: 2px 7px;
                font-size: 11px;
            }
            QPushButton:hover { background: #755532; }
        """)
        btn_return.clicked.connect(self._return_to_latest_compact_turn)
        cnb_layout.addWidget(btn_return, 0)
        self.compact_nav_banner.hide()
        c_layout.addWidget(self.compact_nav_banner, 0)

        # Chat scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:horizontal {
                height: 0px;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 5px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 0, 0, 0.14);
                min-height: 20px;
                border-radius: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(0, 0, 0, 0.25);
            }
        """)

        self.chat_content = QWidget()
        self.chat_content.setStyleSheet("background: transparent;")
        self.chat_layout = QVBoxLayout(self.chat_content)
        self.chat_layout.setContentsMargins(2, 2, 2, 2)
        self.chat_layout.setSpacing(10)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.chat_content)
        c_layout.addWidget(self.scroll_area, 1)

        # Authentic Chat Composer Shell
        self.composer_container = QFrame()
        self.composer_container.setStyleSheet("""
            QFrame {
                background: #F8F4ED;
                border: 1px solid #E6DED2;
                border-radius: 8px;
                padding: 2px 4px;
            }
        """)
        comp_layout = QHBoxLayout(self.composer_container)
        comp_layout.setContentsMargins(4, 2, 4, 2)
        comp_layout.setSpacing(6)

        self.chat_composer = ChatComposer(self.composer_container)
        self.chat_composer.setPlaceholderText("Hỏi một điều, tìm một tệp, hoặc dặn Chuột…")
        self.chat_composer.setStyleSheet("""
            QPlainTextEdit {
                color: #302B24;
                font-size: 12px;
                background: transparent;
                border: none;
            }
        """)
        comp_layout.addWidget(self.chat_composer, 1)

        self.btn_send = QPushButton("Gửi")
        self.btn_send.setStyleSheet("""
            QPushButton {
                background: #8C6A43;
                color: #FFFFFF;
                border: none;
                border-radius: 5px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover { background: #755532; }
        """)
        comp_layout.addWidget(self.btn_send, 0)
        c_layout.addWidget(self.composer_container, 0)

        # Subtle hint line
        self.composer_hint = QLabel("💡 <i>Nhấn vào link 'Xem bản mới/cũ' hoặc 'Sửa' để thử nghiệm ghi chép theo lượt.</i>")
        self.composer_hint.setStyleSheet("color: #948572; font-size: 11px; border: none; background: transparent; padding: 1px 4px;")
        c_layout.addWidget(self.composer_hint, 0)

        work_hbox.addWidget(self.container, 1)
        main_vbox.addLayout(work_hbox, 1)

        # -------------------------------------------------------------
        # QA Testing Dock (Collapsible to keep primary UX clean)
        # -------------------------------------------------------------
        self.dock = QFrame()
        self.dock.setObjectName("TestingDock")
        self.dock.setStyleSheet("""
            QFrame#TestingDock {
                background: #EBE3D7;
                border: 1px solid #DCD0C0;
                border-radius: 8px;
                padding: 4px 8px;
            }
            QPushButton {
                background: #FFFFFF;
                color: #5C4A33;
                border: 1px solid #D1C2AF;
                border-radius: 5px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #FAF6EF;
                border-color: #BCA993;
            }
        """)
        d_layout = QHBoxLayout(self.dock)
        d_layout.setContentsMargins(2, 2, 2, 2)
        d_layout.setSpacing(6)

        d_label = QLabel("<b>Thử nghiệm:</b>")
        d_label.setStyleSheet("color: #5C4A33; font-size: 11px;")
        d_layout.addWidget(d_label, 0)

        btn_test_pet = QPushButton("1. Chạm Chuột")
        btn_test_pet.clicked.connect(self._on_companion_clicked)
        d_layout.addWidget(btn_test_pet)

        btn_test_nav = QPushButton("2. Nhảy Lượt 1 ⇄ 2")
        btn_test_nav.clicked.connect(self._toggle_test_navigation)
        d_layout.addWidget(btn_test_nav)

        btn_test_edit = QPushButton("3. Sửa tại chỗ")
        btn_test_edit.clicked.connect(self._trigger_edit_turn2)
        d_layout.addWidget(btn_test_edit)

        btn_test_stale = QPushButton("4. Thử lỗi Stale")
        btn_test_stale.clicked.connect(self._trigger_stale_warning)
        d_layout.addWidget(btn_test_stale)

        btn_test_confirm = QPushButton("5. Duyệt đề xuất")
        btn_test_confirm.clicked.connect(self._confirm_turn3_proposal)
        d_layout.addWidget(btn_test_confirm)

        btn_test_undo = QPushButton("6. Bỏ / Hoàn tác")
        btn_test_undo.clicked.connect(self._toggle_remove_undo)
        d_layout.addWidget(btn_test_undo)

        btn_reset = QPushButton("Đặt lại mẫu")
        btn_reset.setStyleSheet("background: #F3EAE0; color: #8A4B20; font-weight: 600;")
        btn_reset.clicked.connect(self.reset_fixtures)
        d_layout.addWidget(btn_reset)

        main_vbox.addWidget(self.dock, 0)

    def _toggle_qa_dock(self) -> None:
        self.dock.setVisible(not self.dock.isVisible())
        self.btn_toggle_qa.setText("🛠 Đóng công cụ" if self.dock.isVisible() else "🛠 Công cụ thử nghiệm")

    def _populate_turns(self) -> None:
        """Create TurnWidgets and initialize note events."""
        t1_note = self.turns_data[0]["notes"][0]
        t2_note = self.turns_data[1]["notes"][0]

        t1_note.status = "replaced"
        t1_note.replaced_by_note_id = t2_note.id
        t1_note.replaced_by_turn_id = 2
        t1_note.replaced_by_text = "Có 30 phút · Chỉ ôn TCP (Congestion Control)."

        for data in self.turns_data:
            turn_w = TurnWidget(data, self.chat_content)
            turn_w.navigate_turn_requested.connect(self.navigate_to_turn_note)
            turn_w.edit_replacement_requested.connect(self.open_editor_on_note)
            turn_w.notes_pane.note_edit_saved.connect(self._on_note_edit_saved)
            turn_w.notes_pane.note_removed.connect(self._on_note_removed)
            turn_w.notes_pane.note_restored.connect(self._on_note_restored)
            turn_w.notes_pane.note_confirmed.connect(self._on_note_confirmed)
            turn_w.set_notes(data["notes"])
            self.turn_widgets[data["turn_id"]] = turn_w
            self.chat_layout.addWidget(turn_w)

        self._apply_mode_visibility()

    def _apply_mode_visibility(self) -> None:
        """In Compact mode, show only the active turn or the specifically revealed turn."""
        latest_turn_id = max(self.turn_widgets.keys()) if self.turn_widgets else 1
        for tid, widget in self.turn_widgets.items():
            if self.is_expanded:
                widget.show()
            else:
                if self._revealed_compact_turn is not None:
                    widget.setVisible(tid == self._revealed_compact_turn)
                else:
                    widget.setVisible(tid == latest_turn_id)

        if not self.is_expanded and self._revealed_compact_turn not in (None, latest_turn_id):
            self.cnb_label.setText(f"Đang xem chi tiết lượt cũ (Lượt {self._revealed_compact_turn})")
            self.compact_nav_banner.show()
        else:
            self.compact_nav_banner.hide()

    def toggle_expanded(self) -> None:
        """Toggle between Compact HUD and Full Mode; preserves active editor, focus and selection."""
        # Check if an editor is currently open anywhere
        active_edit_turn = None
        active_editor = None
        for tid, tw in self.turn_widgets.items():
            for row in tw.notes_pane.rows.values():
                if row.editing:
                    active_edit_turn = tid
                    active_editor = row.editor
                    break
            if active_edit_turn is not None:
                break

        self.is_expanded = not self.is_expanded

        if not self.is_expanded:
            # Entering compact mode: if editing a turn, keep that turn revealed!
            if active_edit_turn is not None:
                self._revealed_compact_turn = active_edit_turn
            else:
                self._revealed_compact_turn = None
            self.resize(680, 410)
        else:
            self._revealed_compact_turn = None
            self.resize(740, 600)

        self.btn_mode_toggle.setText("Đầy đủ (⌘L)" if self.is_expanded else "Thu gọn HUD (⌘L)")
        self._apply_mode_visibility()

        # Restore focus to editor if it was active
        if active_editor is not None:
            active_editor.setFocus()

    def _return_to_latest_compact_turn(self) -> None:
        self._revealed_compact_turn = None
        self._apply_mode_visibility()

    def navigate_to_turn_note(self, target_turn_id: int, target_note_id: str) -> None:
        """Jump to a referenced note across turns and trigger glow highlight."""
        if target_turn_id not in self.turn_widgets:
            return

        if not self.is_expanded:
            self._revealed_compact_turn = target_turn_id
            self._apply_mode_visibility()

        target_widget = self.turn_widgets[target_turn_id]
        self.scroll_area.ensureWidgetVisible(target_widget)
        target_widget.notes_pane.highlight_note(target_note_id)

    def open_editor_on_note(self, target_turn_id: int, target_note_id: str) -> None:
        """Navigate to note and immediately open its editor (used by 'Sửa bản mới')."""
        if target_turn_id not in self.turn_widgets:
            return

        if not self.is_expanded:
            self._revealed_compact_turn = target_turn_id
            self._apply_mode_visibility()

        target_widget = self.turn_widgets[target_turn_id]
        self.scroll_area.ensureWidgetVisible(target_widget)
        if target_note_id in target_widget.notes_pane.rows:
            row = target_widget.notes_pane.rows[target_note_id]
            row._start_edit()
            row.editor.setFocus()
            target_widget.notes_pane.highlight_note(target_note_id)

    def _on_companion_clicked(self) -> None:
        """Clicking Chuột emotes and highlights the latest active note using natural language."""
        self.companion.react("happy")
        latest_active_note = None
        for turn_data in reversed(self.turns_data):
            for note in turn_data["notes"]:
                if note.status == "active":
                    latest_active_note = note
                    break
            if latest_active_note:
                break

        if latest_active_note:
            self.navigate_to_turn_note(latest_active_note.turn_id, latest_active_note.id)
            snippet = latest_active_note.text[:35] + ("…" if len(latest_active_note.text) > 35 else "")
            self.composer_hint.setText(f"🐭 Chuột: <i>'Ghi chép đang dùng: “{snippet}”'</i>")
        else:
            self.composer_hint.setText("🐭 Chuột: <i>'Hiện chưa có ghi chép nào đang mở.'</i>")

    def _toggle_test_navigation(self) -> None:
        """Test jumping from Turn 1 to Turn 2 or vice versa."""
        t2_note_id = "note-tcp-time-v2"
        t1_note_id = "note-tcp-time"
        if self._revealed_compact_turn == 1:
            self.navigate_to_turn_note(2, t2_note_id)
        else:
            self.navigate_to_turn_note(1, t1_note_id)

    def _trigger_edit_turn2(self) -> None:
        target_w = self.turn_widgets.get(2)
        if target_w and "note-tcp-time-v2" in target_w.notes_pane.rows:
            if not self.is_expanded:
                self._revealed_compact_turn = 2
                self._apply_mode_visibility()
            target_w.notes_pane.rows["note-tcp-time-v2"]._start_edit()

    def _trigger_stale_warning(self) -> None:
        """Simulate a revision conflict where backend revision changed while user was typing."""
        target_w = self.turn_widgets.get(2)
        if target_w and "note-tcp-time-v2" in target_w.notes_pane.rows:
            row = target_w.notes_pane.rows["note-tcp-time-v2"]
            if not row.editing:
                row._start_edit()
            row.error_label.setText("⚠️ Lỗi xung đột: Ghi chú đã đổi ở nơi khác. Bản nháp của bạn được giữ nguyên.")
            row.error_label.show()

    def _confirm_turn3_proposal(self) -> None:
        """Confirm proposed note in Turn 3 into an active note."""
        self._on_note_confirmed("note-tcp-quiz-proposal")

    def _toggle_remove_undo(self) -> None:
        target_w = self.turn_widgets.get(2)
        if target_w and "note-tcp-time-v2" in target_w.notes_pane.rows:
            note = target_w.notes_pane.rows["note-tcp-time-v2"].note
            if note.status == "active":
                self._on_note_removed(note.id, note.revision)
            else:
                self._on_note_restored(note.id)

    def _on_note_edit_saved(self, note_id: str, revision: int, new_text: str) -> None:
        """Save edited note AND dynamically update forward link on any predecessor notes."""
        saved_turn_id = None
        for turn_data in self.turns_data:
            for note in turn_data["notes"]:
                if note.id == note_id:
                    note.text = new_text
                    note.revision += 1
                    note.error_message = None
                    saved_turn_id = note.turn_id
                    break

        if saved_turn_id is not None:
            self.turn_widgets[saved_turn_id].notes_pane.rows[note_id]._cancel_edit()
            self.turn_widgets[saved_turn_id].set_notes(self.turns_data[saved_turn_id - 1]["notes"])

        # Dynamically update forward link text on predecessor notes pointing to this note
        for turn_data in self.turns_data:
            updated_pred = False
            for p_note in turn_data["notes"]:
                if p_note.replaced_by_note_id == note_id:
                    p_note.replaced_by_text = new_text
                    updated_pred = True
            if updated_pred:
                self.turn_widgets[turn_data["turn_id"]].set_notes(turn_data["notes"])

        self.companion.react("noting")
        self.composer_hint.setText(f"✓ Đã lưu thay đổi cho ghi chú: '{new_text}'")

    def _on_note_removed(self, note_id: str, revision: int) -> None:
        for turn_data in self.turns_data:
            for note in turn_data["notes"]:
                if note.id == note_id:
                    note.status = "removed"
                    self.turn_widgets[note.turn_id].set_notes(turn_data["notes"])
                    self.companion.react("waiting")
                    self.composer_hint.setText("Đã bỏ ghi chú. Bạn có thể nhấn 'Hoàn tác' để khôi phục.")
                    return

    def _on_note_restored(self, note_id: str) -> None:
        for turn_data in self.turns_data:
            for note in turn_data["notes"]:
                if note.id == note_id:
                    note.status = "active"
                    note.revision += 1
                    self.turn_widgets[note.turn_id].set_notes(turn_data["notes"])
                    self.companion.react("happy")
                    self.composer_hint.setText("Đã hoàn tác khôi phục ghi chú.")
                    return

    def _on_note_confirmed(self, note_id: str) -> None:
        for turn_data in self.turns_data:
            for note in turn_data["notes"]:
                if note.id == note_id:
                    note.status = "active"
                    note.confirmed = True
                    self.turn_widgets[note.turn_id].set_notes(turn_data["notes"])
                    self.companion.react("done")
                    self.composer_hint.setText("✓ Đã xác nhận đề xuất thành ghi chú chính thức.")
                    return

    def reset_fixtures(self) -> None:
        self.turns_data = copy.deepcopy(FIXTURE_TURNS)
        t1_note = self.turns_data[0]["notes"][0]
        t2_note = self.turns_data[1]["notes"][0]
        t1_note.status = "replaced"
        t1_note.replaced_by_note_id = t2_note.id
        t1_note.replaced_by_turn_id = 2
        t1_note.replaced_by_text = "Có 30 phút · Chỉ ôn TCP (Congestion Control)."
        for turn_data in self.turns_data:
            if turn_data["turn_id"] in self.turn_widgets:
                self.turn_widgets[turn_data["turn_id"]].set_notes(turn_data["notes"])
        self._revealed_compact_turn = None
        self._apply_mode_visibility()
        self.companion.react("greet")
        self.composer_hint.setText("Đã đặt lại dữ liệu mẫu ban đầu.")
