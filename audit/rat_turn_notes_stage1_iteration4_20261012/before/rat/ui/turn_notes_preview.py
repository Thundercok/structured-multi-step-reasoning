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

from PyQt6.QtCore import QEvent, QRect, QSize, Qt, QTimer, QEasingCurve, QPropertyAnimation, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QKeySequence, QPainter, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QGridLayout,
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
        "assistant_message": "Ok, **20 phút · chỉ TCP**. Handshake + flow control trước. Chưa cần cứu cả Internet.",
        "trace_steps": [
            AgentStep(1, "", "update_task_state", {}, {"task_state": {"goal": "Ôn TCP trong 20 phút", "remaining": ["Handshake rồi flow control"]}}),
            AgentStep(2, "", "record_work_note", {}, {"note": {"text": "Có 20 phút · Chỉ ôn TCP.", "confirmed": True}}),
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
        "assistant_message": "Chốt **30 phút**. Thêm congestion control vào kèo. Não cũng cần điều khiển tắc nghẽn mà.",
        "trace_steps": [
            AgentStep(1, "", "update_task_state", {}, {"task_state": {"goal": "Ôn TCP trong 30 phút", "remaining": ["Thêm congestion control"]}}),
            AgentStep(2, "", "record_work_note", {}, {"note": {"text": "Có 30 phút · Chỉ ôn TCP.", "confirmed": True}}),
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
        "assistant_message": "15 câu trắc nghiệm cần thêm khoảng **15 phút**. Để chiều thứ 5 nhé? Deadline không có quyền ăn cả buổi của bạn.",
        "trace_steps": [
            AgentStep(1, "", "calculate", {"expression": "15 * 1"}, {"expression": "15 * 1", "result": "15"}),
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
        layout.setContentsMargins(0, 4, 0, 12)
        layout.setSpacing(9)

        # 1. User Message Row (PlainText)
        user_row = QHBoxLayout()
        user_row.setContentsMargins(0, 0, 0, 0)
        user_label = QLabel(turn_data["user_message"])
        self.user_label = user_label
        user_label.setTextFormat(Qt.TextFormat.PlainText)
        user_label.setWordWrap(True)
        user_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        user_label.setStyleSheet("color: #8C7B65; font-size: 12px; font-weight: 500; padding: 1px 0;")
        user_label.setMaximumWidth(390)
        user_label.setFixedWidth(min(340, user_label.fontMetrics().horizontalAdvance(user_label.text()) + 24))
        user_label.setStyleSheet("color: #70695D; background: #F0EDE6; border: none; border-radius: 9px; padding: 5px 10px; font-size: 12px;")
        user_row.addStretch()
        user_row.addWidget(user_label, 0)
        layout.addLayout(user_row)

        # 2. Assistant Response Bubble (Render Markdown)
        self.reply_label = QLabel()
        self.reply_label.setTextFormat(Qt.TextFormat.MarkdownText)
        self.reply_label.setText(turn_data["assistant_message"])
        self.reply_label.setWordWrap(True)
        self.reply_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.reply_label.setStyleSheet("color: #302D26; font-size: 14px; padding: 2px 0;")
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
        self.work_trace.caption.setText("Dự định và thao tác trong kịch bản mẫu này.")
        self.work_trace.preview.hide()
        self.work_trace.button.setStyleSheet("QPushButton { color: #908675; background: transparent; border: none; font-size: 11px; text-align: left; padding: 3px 0; } QPushButton:hover, QPushButton:focus { color: #43583F; }")
        layout.addWidget(self.work_trace)

    def set_notes(self, notes: List[TurnNoteItem]) -> None:
        self.notes_pane.set_notes(notes)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = min(340, max(160, int(self.width() * .84)), self.user_label.fontMetrics().horizontalAdvance(self.user_label.text()) + 24)
        self.user_label.setFixedWidth(width)
        self.user_label.ensurePolished()
        text_height = self.user_label.fontMetrics().boundingRect(QRect(0, 0, max(1, width - 20), 4000), Qt.TextFlag.TextWordWrap, self.user_label.text()).height()
        self.user_label.setFixedHeight(text_height + 12)


class TurnNotesPreviewWindow(QMainWindow):
    """
    Interactive Stage 1 UX testbed for evaluating Turn-level notes.
    Pure fixture data — completely decoupled from live AI models.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.is_expanded = True
        self._mode_width = 820
        self.turns_data = copy.deepcopy(FIXTURE_TURNS)
        self.turn_widgets: Dict[int, TurnWidget] = {}
        self._revealed_compact_turn: Optional[int] = None
        self._init_window()
        self._init_ui()
        self._populate_turns()

    def _init_window(self) -> None:
        self.setWindowTitle("RAT · Bản xem Giao diện Ghi chép theo Lượt (Fixture)")
        self.setMinimumSize(620, 280)
        self.resize(820, 620)
        self.setStyleSheet("""
            QMainWindow {
                background: #ECE9E1;
            }
            QLabel {
                font-family: "Helvetica Neue";
            }
        """)

        # ⌘L shortcut for switching Compact / Full mode
        shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        shortcut.activated.connect(self.toggle_expanded)
        shortcut_meta = QShortcut(QKeySequence("Meta+L"), self)
        shortcut_meta.activated.connect(self.toggle_expanded)

    def _init_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)
        self.main_layout.setContentsMargins(16, 14, 16, 14)
        self.main_layout.setSpacing(12)
        header = QHBoxLayout()
        title = QLabel("chuột.")
        title.setStyleSheet('color: #403D32; font-family: Georgia; font-size: 22px; font-weight: bold;')
        header.addWidget(title)
        subtitle = QLabel("đồng phạm chạy deadline")
        subtitle.setStyleSheet('color: #918575; font-size: 11px;')
        header.addWidget(subtitle)
        header.addStretch()
        self.preview_badge = QLabel("Bản xem · dữ liệu mẫu")
        self.preview_badge.setStyleSheet('color: #807B6C; font-size: 10px;')
        self.preview_badge.setToolTip('Preview offline với dữ liệu mẫu, chưa nối model hoặc ghi chú thật.')
        header.addWidget(self.preview_badge)
        quiet = 'QPushButton { color: #706959; background: transparent; border: none; border-radius: 6px; padding: 6px 8px; font-size: 11px; } QPushButton:hover, QPushButton:focus { background: #E2DFD5; color: #3E4D37; }'
        self.btn_toggle_qa = QPushButton("Thử")
        self.btn_toggle_qa.setStyleSheet(quiet)
        self.btn_toggle_qa.setToolTip('Mở các tình huống kiểm thử UI')
        self.btn_toggle_qa.clicked.connect(self._toggle_qa_dock)
        header.addWidget(self.btn_toggle_qa)
        self.btn_mode_toggle = QPushButton("Thu gọn ↙")
        self.btn_mode_toggle.setToolTip('Đổi compact/full · ⌘L')
        self.btn_mode_toggle.setStyleSheet(quiet)
        self.btn_mode_toggle.clicked.connect(self.toggle_expanded)
        header.addWidget(self.btn_mode_toggle)
        self.main_layout.addLayout(header)

        work = QHBoxLayout()
        work.setSpacing(16)
        self.left_stage = QWidget()
        self.left_stage.setFixedWidth(164)
        left = QVBoxLayout(self.left_stage)
        left.setContentsMargins(0, 10, 0, 0)
        left.setSpacing(5)
        self.companion = LiveCompanion(self, self.left_stage)
        self.companion.clicked.disconnect()
        self.companion.clicked.connect(self._on_companion_clicked)
        left.addWidget(self.companion, 0, Qt.AlignmentFlag.AlignHCenter)
        self.companion_caption = QLabel("Não cá vàng?\nCó Chuột giữ hộ.")
        self.companion_caption.setTextFormat(Qt.TextFormat.PlainText)
        self.companion_caption.setWordWrap(True)
        self.companion_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.companion_caption.setFixedWidth(150)
        self.companion_caption.setStyleSheet('color: #817461; font-size: 12px; padding: 7px;')
        left.addWidget(self.companion_caption, 0, Qt.AlignmentFlag.AlignHCenter)
        tip = QLabel("chạm một cái là hiểu ♡")
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tip.setStyleSheet('color: #A89B87; font-size: 10px;')
        left.addWidget(tip)
        left.addStretch()
        work.addWidget(self.left_stage)
        self.container = QFrame()
        self.container.setObjectName("SpotlightContainer")
        self.container.setStyleSheet('QFrame#SpotlightContainer { background: #FCFAF6; border: 1px solid #DBD5C9; border-radius: 18px; }')
        shadow = QGraphicsDropShadowEffect(self.container)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(54, 46, 32, 22))
        self.container.setGraphicsEffect(shadow)
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(20, 16, 20, 14)
        self.container_layout.setSpacing(10)
        self.compact_nav_banner = QFrame()
        nav = QHBoxLayout(self.compact_nav_banner)
        nav.setContentsMargins(0, 0, 0, 0)
        self.cnb_label = QLabel("Đang xem lượt cũ")
        self.cnb_label.setStyleSheet('color: #877F6B; font-size: 11px;')
        nav.addWidget(self.cnb_label, 1)
        self.btn_return = QPushButton("Về hiện tại ↗")
        self.btn_return.setStyleSheet(quiet)
        self.btn_return.clicked.connect(self._return_to_latest_compact_turn)
        nav.addWidget(self.btn_return)
        self.compact_nav_banner.hide()
        self.container_layout.addWidget(self.compact_nav_banner)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet('QScrollArea { background: transparent; border: none; } QScrollBar:vertical { width: 4px; background: transparent; } QScrollBar::handle:vertical { background: #D8D1C4; border-radius: 2px; min-height: 20px; } QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }')
        self.chat_content = QWidget()
        self.chat_content.setStyleSheet('background: transparent;')
        self.chat_layout = QVBoxLayout(self.chat_content)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_layout.setSpacing(14)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.chat_content)
        self.container_layout.addWidget(self.scroll_area, 1)
        self.composer_container = QFrame()
        self.composer_container.setObjectName('PreviewComposer')
        self.composer_container.setStyleSheet('QFrame#PreviewComposer { background: #F0EDE6; border: 1px solid #DED9CD; border-radius: 12px; }')
        compose = QHBoxLayout(self.composer_container)
        compose.setContentsMargins(9, 5, 7, 5)
        self.chat_composer = ChatComposer(self.composer_container)
        self.chat_composer.setPlaceholderText("Quăng việc cho Chuột…")
        self.chat_composer.setStyleSheet('QPlainTextEdit { color: #3A352B; font-size: 13px; border: none; background: transparent; selection-background-color: #DFE3D1; }')
        compose.addWidget(self.chat_composer, 1)
        self.btn_send = QPushButton("↑")
        self.btn_send.setAccessibleName('Gửi tin nhắn trong bản xem')
        self.btn_send.setFixedSize(30, 30)
        self.btn_send.setStyleSheet('QPushButton { background: #58654A; color: white; border: none; border-radius: 10px; font-size: 20px; } QPushButton:hover, QPushButton:focus { background: #3F4C34; }')
        self.btn_send.clicked.connect(self._preview_send)
        self.chat_composer.returnPressed.connect(self._preview_send)
        compose.addWidget(self.btn_send)
        self.container_layout.addWidget(self.composer_container)
        self.composer_hint = QLabel()
        self.composer_hint.setTextFormat(Qt.TextFormat.PlainText)
        self.composer_hint.setWordWrap(True)
        self.composer_hint.setStyleSheet('color: #928570; font-size: 11px; padding: 0 2px;')
        self.composer_hint.hide()
        self.container_layout.addWidget(self.composer_hint)
        work.addWidget(self.container, 1)
        self.main_layout.addLayout(work, 1)

        self.dock = QFrame()
        self.dock.setStyleSheet('QFrame { background: #E4E0D6; border: none; border-radius: 9px; }')
        grid = QGridLayout(self.dock)
        grid.setContentsMargins(10, 9, 10, 9)
        tests = [('Chạm Chuột', self._on_companion_clicked), ('Bản cũ ↔ mới', self._toggle_test_navigation),
                 ('Sửa note', self._trigger_edit_turn2), ('Xung đột', self._trigger_stale_warning),
                 ('Duyệt đề xuất', self._confirm_turn3_proposal), ('Bỏ ↔ hoàn tác', self._toggle_remove_undo)]
        for index, (label, callback) in enumerate(tests):
            button = QPushButton(label)
            button.setStyleSheet(quiet)
            button.clicked.connect(callback)
            grid.addWidget(button, index // 3, index % 3)
        reset = QPushButton('Đặt lại dữ liệu mẫu')
        reset.setStyleSheet(quiet)
        reset.clicked.connect(self.reset_fixtures)
        grid.addWidget(reset, 2, 0, 1, 3)
        self.dock.hide()
        self.main_layout.addWidget(self.dock)
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.timeout.connect(self._fit_surface)
        self.chat_composer.height_changed.connect(self._queue_fit)
        self._resize_motion = QPropertyAnimation(self, b'geometry', self)
        self._resize_motion.setDuration(160)
        self._resize_motion.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._resize_motion.finished.connect(self._after_resize)

    def _preview_send(self):
        self._show_hint('Bản xem chưa gửi tin nhắn thật. Bản nháp vẫn ở đây.')
        self.chat_composer.setFocus()

    def _show_hint(self, text):
        self.composer_hint.setText(text)
        self.composer_hint.show()
        self._queue_fit()

    def _queue_fit(self):
        if hasattr(self, '_fit_timer'):
            self._fit_timer.start(0)

    def _fit_surface(self):
        if self._resize_motion.state() == QPropertyAnimation.State.Running:
            return
        self.main_layout.activate()
        self.container_layout.activate()
        self.chat_layout.activate()
        if self.is_expanded:
            self._resize_surface(QSize(820, 620))
            return
        visible = [turn for turn in self.turn_widgets.values() if not turn.isHidden()]
        width = max(260, self._mode_width - 252)
        height = sum(turn.layout().heightForWidth(width) if turn.layout().hasHeightForWidth() else turn.sizeHint().height() for turn in visible)
        height = max(170, min(330, height))
        chrome = self.height() - self.scroll_area.viewport().height()
        self._resize_surface(QSize(self._mode_width, max(300, height + chrome)))

    def _resize_surface(self, size):
        target = QRect(self.x(), self.y(), size.width(), size.height())
        if target.size() == self.size():
            return
        self._resize_motion.stop()
        if motion_enabled() and self.isVisible():
            self._resize_motion.setStartValue(self.geometry())
            self._resize_motion.setEndValue(target)
            self._resize_motion.start()
        else:
            self.setGeometry(target)

    def _after_resize(self):
        focus = QApplication.focusWidget()
        if focus is not None and self.chat_content.isAncestorOf(focus):
            self.scroll_area.ensureWidgetVisible(focus, 8, 12)
        elif getattr(self, '_navigation_target', None) is not None:
            self.scroll_area.ensureWidgetVisible(self._navigation_target, 8, 12)
        self._navigation_target = None
        self._queue_fit()

    def _toggle_qa_dock(self) -> None:
        self.dock.setVisible(not self.dock.isVisible())
        self.btn_toggle_qa.setText("Đóng thử" if self.dock.isVisible() else "Thử")
        self._queue_fit()

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
            turn_w.notes_pane.changed.connect(self._queue_fit)
            turn_w.work_trace.changed.connect(self._queue_fit)

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
        self._queue_fit()

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
            self._mode_width = 680
        else:
            self._revealed_compact_turn = None
            self._mode_width = 820

        self.btn_mode_toggle.setText("Thu gọn ↙" if self.is_expanded else "Mở rộng ↗")
        self._apply_mode_visibility()
        self._queue_fit()

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
        row = target_widget.notes_pane.rows.get(target_note_id)
        self._navigation_target = row
        self.scroll_area.ensureWidgetVisible(row or target_widget, 8, 12)
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
            self._queue_fit()
            QTimer.singleShot(0, lambda: self.scroll_area.ensureWidgetVisible(row.editor, 8, 12))
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
            self._show_hint(f"Ghi chép đang dùng: “{snippet}”. Não cá vàng đã có đồng phạm.")
        else:
            self._show_hint("Chưa có gì để giữ hộ. Quăng cho Chuột một điều đi.")

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
        self._show_hint("Sửa rồi. Bản cũ vẫn còn, Chuột không chơi trò xóa dấu vết.")

    def _on_note_removed(self, note_id: str, revision: int) -> None:
        for turn_data in self.turns_data:
            for note in turn_data["notes"]:
                if note.id == note_id:
                    note.status = "removed"
                    self.turn_widgets[note.turn_id].set_notes(turn_data["notes"])
                    self.companion.react("waiting")
                    self._show_hint("Đã bỏ. Đổi ý thì bấm Hoàn tác — chưa bay màu đâu.")
                    return

    def _on_note_restored(self, note_id: str) -> None:
        for turn_data in self.turns_data:
            for note in turn_data["notes"]:
                if note.id == note_id:
                    note.status = "active"
                    note.revision += 1
                    self.turn_widgets[note.turn_id].set_notes(turn_data["notes"])
                    self.companion.react("happy")
                    self._show_hint("Ghi chú hồi sinh. Mèo chưa kịp ăn.")
                    return

    def _on_note_confirmed(self, note_id: str) -> None:
        for turn_data in self.turns_data:
            for note in turn_data["notes"]:
                if note.id == note_id:
                    note.status = "active"
                    note.confirmed = True
                    self.turn_widgets[note.turn_id].set_notes(turn_data["notes"])
                    self.companion.react("done")
                    self._show_hint("Ghi lại rồi. Chuột giữ hộ, cậu lo phần học.")
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
        self._show_hint("Đã đặt lại dữ liệu mẫu ban đầu.")
