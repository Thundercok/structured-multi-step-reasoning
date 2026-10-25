"""
rat.ui.turn_notes — Turn-level inline notes and revision linking.
Notes belong to specific conversation turns rather than an isolated pane.
Rendered as lightweight, borderless text lines on the chat background;
the editor frame appears only when actively editing.
Old revisions remain legible with replacement labels and forward links.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from PyQt6.QtCore import QEvent, QEasingCurve, QPropertyAnimation, QRectF, Qt, QTimer, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QKeyEvent, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from rat.ui import surface_layout


@dataclass
class TurnNoteItem:
    """Represents a discrete note belonging to a conversation turn."""
    id: str
    turn_id: int
    text: str
    status: str = "active"  # "active", "replaced", "proposed", "removed"
    source: str = "user_note"  # "user_note", "user_edit", "quote", "model_proposal"
    quote: Optional[str] = None
    confirmed: bool = True
    revision: int = 1
    # Provenance links between revisions
    replaced_by_note_id: Optional[str] = None
    replaced_by_turn_id: Optional[int] = None
    replaced_by_text: Optional[str] = None
    replaces_note_id: Optional[str] = None
    replaces_turn_id: Optional[int] = None
    replaces_text: Optional[str] = None
    error_message: Optional[str] = None

    @staticmethod
    def _parse_turn_int(val: object) -> Optional[int]:
        if val is None or val == "":
            return None
        if isinstance(val, int):
            return val
        s = str(val).strip()
        if s.startswith("turn-"):
            s = s[5:]
        try:
            return int(s)
        except ValueError:
            return 1

    @classmethod
    def from_dict(cls, data: dict) -> "TurnNoteItem":
        tid = cls._parse_turn_int(data.get("turn_id") or data.get("owner_turn_id")) or 1
        return cls(
            id=str(data["id"]),
            turn_id=tid,
            text=str(data.get("text", "")),
            status=str(data.get("status", "active")),
            source=str(data.get("source", "user_note")),
            quote=data.get("quote"),
            confirmed=bool(data.get("confirmed", True)),
            revision=int(data.get("revision", 1)),
            replaced_by_note_id=data.get("replaced_by_note_id"),
            replaced_by_turn_id=cls._parse_turn_int(data.get("replaced_by_turn_id")),
            replaced_by_text=data.get("replaced_by_text"),
            replaces_note_id=data.get("replaces_note_id"),
            replaces_turn_id=cls._parse_turn_int(data.get("replaces_turn_id")),
            replaces_text=data.get("replaces_text"),
            error_message=data.get("error_message"),
        )


BUTTON_STYLE = """
QPushButton {
    color: #856E52;
    background: transparent;
    border: none;
    padding: 2px 6px;
    font-size: 11px;
    border-radius: 4px;
}
QPushButton:hover {
    background: #EFE6D8;
    color: #4D3C28;
}
QPushButton:focus {
    background: #EAE0D0;
    outline: none;
}
QPushButton:disabled {
    color: #C2B6A6;
}
"""

PRIMARY_BUTTON_STYLE = """
QPushButton {
    color: #FFFFFF;
    background: #8C6A43;
    border: none;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 500;
    border-radius: 5px;
}
QPushButton:hover {
    background: #755532;
}
QPushButton:focus {
    background: #644728;
    outline: none;
}
QPushButton:disabled {
    background: #D9CEBF;
    color: #F5EFEB;
}
"""

LINK_BUTTON_STYLE = """
QPushButton {
    color: #79766C;
    background: transparent;
    border: none;
    border-radius: 4px;
    padding: 2px 0;
    font-size: 11px;
    text-align: left;
}
QPushButton:hover {
    color: #3F5142;
}
QPushButton:focus {
    background: #ECEDE5;
}
"""


class NoteEditor(QPlainTextEdit):
    """Custom editor with keyboard shortcuts (Escape: cancel, Ctrl/Cmd+Enter: apply)."""
    apply_requested = pyqtSignal()
    cancel_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setTabChangesFocus(True)
        self.setFixedHeight(62)
        self.setStyleSheet("""
            QPlainTextEdit {
                color: #362E24;
                background: #FFFFFF;
                border: 1.5px solid #C8B79F;
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 12px;
                selection-background-color: #EADBC8;
            }
            QPlainTextEdit:focus {
                border-color: #8C6A43;
            }
        """)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_requested.emit()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
                self.apply_requested.emit()
                event.accept()
                return
        super().keyPressEvent(event)


class InlineNoteRow(QFrame):
    """
    Renders one note item inside a turn:
    - Default state: subtle, borderless text line seamlessly on chat background
    - Old replaced note: legible text (not struck-through), labeled as replaced, linking to new version
    - Replacement note: labeled with predecessor link
    - Proposal: gentle dashed guide with confirm/edit actions
    - Tombstone: removed notice with undo button
    - Editing state: frame container appears only while editor is active
    """
    edit_saved = pyqtSignal(str, int, str)             # note_id, revision, new_text
    note_removed = pyqtSignal(str, int)                # note_id, revision
    note_restored = pyqtSignal(str)                    # note_id
    note_confirmed = pyqtSignal(str)                   # note_id
    navigate_requested = pyqtSignal(int, str)          # target_turn_id, target_note_id
    edit_replacement_requested = pyqtSignal(int, str)  # target_turn_id, target_note_id
    highlight_changed = pyqtSignal()
    layout_changed = pyqtSignal()

    def __init__(self, note: TurnNoteItem, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.note = note
        self.editing = False
        self.details_open = False
        self._highlight_ratio = 0.0
        self._static_timer: Optional[QTimer] = None
        self._init_ui()
        self.refresh(note)

    def _init_ui(self) -> None:
        self.setObjectName("InlineNoteRow")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 3, 0, 1)
        self.layout.setSpacing(2)

        # Main row: Tag + Text + Inline Actions
        self.header_row = QWidget()
        h_layout = QHBoxLayout(self.header_row)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(6)

        self.tag_label = QLabel()
        self.tag_label.setStyleSheet("font-size: 11px; font-weight: 600; border: none; background: transparent;")
        h_layout.addWidget(self.tag_label, 0, Qt.AlignmentFlag.AlignTop)

        self.text_label = QLabel()
        self.text_label.setTextFormat(Qt.TextFormat.PlainText)
        self.text_label.setWordWrap(True)
        self.text_label.setMinimumWidth(0)
        self.text_label.installEventFilter(self)
        self.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.text_label.setStyleSheet("color: #383025; font-size: 12px; border: none; background: transparent;")
        h_layout.addWidget(self.text_label, 1, Qt.AlignmentFlag.AlignTop)

        # Quick action controls
        self.actions_widget = QWidget()
        a_layout = QHBoxLayout(self.actions_widget)
        a_layout.setContentsMargins(0, 0, 0, 0)
        a_layout.setSpacing(4)

        self.btn_confirm = QPushButton("Xác nhận")
        self.btn_confirm.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self.btn_confirm.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_confirm.clicked.connect(self._on_confirm_clicked)
        self.btn_confirm.setText("Ghi lại")
        self.btn_confirm.setAccessibleName("Xác nhận ghi chú được đề xuất")
        self.btn_confirm.setStyleSheet(PRIMARY_BUTTON_STYLE.replace('#8C6A43', '#59644F').replace('#755532', '#44503C'))
        a_layout.addWidget(self.btn_confirm)

        self.btn_edit = QPushButton("Sửa")
        self.btn_edit.setStyleSheet(BUTTON_STYLE)
        self.btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_edit.clicked.connect(self._start_edit)
        a_layout.addWidget(self.btn_edit)

        self.btn_remove = QPushButton("Bỏ")
        self.btn_remove.setStyleSheet(BUTTON_STYLE)
        self.btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_remove.setToolTip("Bỏ ghi chú này khỏi ngữ cảnh active")
        self.btn_remove.clicked.connect(self._on_remove_clicked)
        a_layout.addWidget(self.btn_remove)

        self.btn_undo = QPushButton("Hoàn tác")
        self.btn_undo.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self.btn_undo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_undo.clicked.connect(self._on_undo_clicked)
        a_layout.addWidget(self.btn_undo)

        self.btn_details = QPushButton("⋯")
        self.btn_details.setStyleSheet(BUTTON_STYLE)
        self.btn_details.setCheckable(True)
        self.btn_details.setAccessibleName("Nguồn và lịch sử ghi chú")
        self.btn_details.setToolTip("Nguồn và lịch sử ghi chú")
        self.btn_details.toggled.connect(self._toggle_details)
        a_layout.addWidget(self.btn_details)

        h_layout.addWidget(self.actions_widget, 0, Qt.AlignmentFlag.AlignTop)
        self.layout.addWidget(self.header_row)

        # Sub-row for revision linking / metadata
        self.sub_row = QWidget()
        s_layout = QHBoxLayout(self.sub_row)
        s_layout.setContentsMargins(0, 0, 0, 0)
        s_layout.setSpacing(6)

        self.sub_info_label = QLabel()
        self.sub_info_label.setTextFormat(Qt.TextFormat.PlainText)
        self.sub_info_label.setStyleSheet("color: #8C7B65; font-size: 11px; border: none; background: transparent;")
        self.sub_info_label.setWordWrap(True)

        self.btn_nav_link = QPushButton()
        self.btn_nav_link.setStyleSheet(LINK_BUTTON_STYLE)
        self.btn_nav_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nav_link.clicked.connect(self._on_nav_link_clicked)
        s_layout.addWidget(self.btn_nav_link, 0)

        s_layout.addStretch()
        self.layout.addWidget(self.sub_row)
        self.layout.addWidget(self.sub_info_label)

        # Editor section (hidden by default; frame appears only when editing)
        self.editor_section = QWidget()
        self.editor_section.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        e_layout = QVBoxLayout(self.editor_section)
        e_layout.setContentsMargins(0, 4, 0, 2)
        e_layout.setSpacing(4)

        self.editor = NoteEditor()
        self.editor.apply_requested.connect(self._save_edit)
        self.editor.cancel_requested.connect(self._cancel_edit)
        e_layout.addWidget(self.editor)

        # Inline error warning if conflict occurs
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #B91C1C; font-size: 11px; font-weight: 500; padding: 2px 0;")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        e_layout.addWidget(self.error_label)

        ctrl_row = QHBoxLayout()
        ctrl_row.setContentsMargins(0, 0, 0, 0)
        ctrl_row.setSpacing(6)

        hint_label = QLabel("Enter: xuống dòng · ⌘⏎: Áp dụng · Esc: Hủy")
        hint_label.setStyleSheet("color: #A3937F; font-size: 10px;")
        ctrl_row.addWidget(hint_label)
        ctrl_row.addStretch()

        self.btn_apply = QPushButton("Áp dụng")
        self.btn_apply.setStyleSheet(PRIMARY_BUTTON_STYLE)
        self.btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply.clicked.connect(self._save_edit)
        ctrl_row.addWidget(self.btn_apply)

        self.btn_cancel = QPushButton("Hủy")
        self.btn_cancel.setStyleSheet(BUTTON_STYLE)
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.clicked.connect(self._cancel_edit)
        ctrl_row.addWidget(self.btn_cancel)

        e_layout.addLayout(ctrl_row)
        self.editor_section.hide()
        self.layout.addWidget(self.editor_section)

        # Highlight animation
        self.anim = QPropertyAnimation(self, b"highlight_ratio")
        self.anim.setDuration(1200)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def get_highlight_ratio(self) -> float:
        return self._highlight_ratio

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_note_text()

    def eventFilter(self, watched, event):
        if watched is getattr(self, 'text_label', None) and event.type() == QEvent.Type.Resize:
            self._fit_note_text()
        return super().eventFilter(watched, event)

    def _fit_note_text(self):
        if hasattr(self, 'text_label') and self.text_label.width() > 0:
            rect = self.text_label.fontMetrics().boundingRect(
                QRectF(0, 0, self.text_label.width(), 5000).toRect(),
                Qt.TextFlag.TextWordWrap, self.text_label.text())
            if self.text_label.height() != rect.height() + 2:
                self.text_label.setFixedHeight(rect.height() + 2)
                self.layout_changed.emit()

    def set_highlight_ratio(self, val: float) -> None:
        self._highlight_ratio = val
        self.update()

    highlight_ratio = pyqtProperty(float, get_highlight_ratio, set_highlight_ratio)

    def is_highlighted(self) -> bool:
        """True if currently undergoing animated highlight or active static cue."""
        return self._highlight_ratio > 0.05 or self.anim.state() == QPropertyAnimation.State.Running

    def _clear_static_highlight(self) -> None:
        self._highlight_ratio = 0.0
        self.update()

    def trigger_highlight(self) -> None:
        """Indicate this note is being referenced or selected by Chuột."""
        self.anim.stop()
        if not surface_layout.motion_enabled():
            # Static indicator without running animation; auto-clears statically
            self._highlight_ratio = 0.8
            self.update()
            if self._static_timer is None:
                self._static_timer = QTimer(self)
                self._static_timer.setSingleShot(True)
                self._static_timer.timeout.connect(self._clear_static_highlight)
            self._static_timer.start(1200)
            return

        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.start()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 6, 6)

        # Normal note is a light, borderless line on chat background.
        # Only render box when actively editing or highlighted.
        if self.editing:
            painter.fillPath(path, QColor("#FAF5ED"))
            painter.setPen(QPen(QColor("#E2D5C3"), 1.0))
            painter.drawPath(path)
        elif self._highlight_ratio > 0.001:
            glow = QColor("#FDE68A")
            glow.setAlpha(int(self._highlight_ratio * 160))
            painter.fillPath(path, glow)
            border_col = QColor("#D97706")
            border_col.setAlpha(int(self._highlight_ratio * 220))
            painter.setPen(QPen(border_col, 1.2))
            painter.drawPath(path)

        painter.end()
        super().paintEvent(event)

    def refresh(self, note: TurnNoteItem) -> None:
        self.note = note
        if not self.editing:
            self.text_label.setText(note.text)

        # Style by note status
        if note.status == "active":
            if note.replaces_note_id:
                self.tag_label.setText("Đã đổi:")
                self.tag_label.setStyleSheet("color: #2563EB; font-size: 11px; font-weight: 600;")
                self.sub_info_label.setText(f"Thay thế bản ở lượt {note.replaces_turn_id} ·")
                disp_old = note.replaces_text or ""
                if len(disp_old) > 36:
                    disp_old = disp_old[:36] + "…"
                self.btn_nav_link.setText(f"Xem bản cũ: {disp_old}")
                self.btn_nav_link.show()
                self.sub_row.show()
            else:
                self.tag_label.setText("Ghi lại:")
                self.tag_label.setStyleSheet("color: #7A5B36; font-size: 11px; font-weight: 600;")
                self.btn_nav_link.hide()
                if note.quote:
                    self.sub_info_label.setText(f"Trích lời bạn: “{note.quote}”")
                    self.sub_row.show()
                else:
                    self.sub_row.hide()

            self.text_label.setStyleSheet("color: #332B21; font-size: 12px;")
            self.btn_confirm.hide()
            self.btn_edit.show()
            self.btn_edit.setText("Sửa")
            self.btn_remove.show()
            self.btn_undo.hide()

        elif note.status == "replaced":
            # Old version remains legible (no strikethrough), with replaced label & forward link
            self.tag_label.setText("Đã thay thế:")
            self.tag_label.setStyleSheet("color: #8C7B65; font-size: 11px; font-weight: 500;")
            self.text_label.setStyleSheet("color: #5C5245; font-size: 12px;")
            self.sub_info_label.setText(f"Đã được thay thế ở lượt {note.replaced_by_turn_id or 'sau'} →")
            disp_new = note.replaced_by_text or "chi tiết"
            if len(disp_new) > 36:
                disp_new = disp_new[:36] + "…"
            self.btn_nav_link.setText(f"Xem bản mới ({disp_new})")
            self.btn_nav_link.show()
            self.sub_row.show()

            self.btn_confirm.hide()
            self.btn_edit.show()
            self.btn_edit.setText("Sửa bản mới")
            self.btn_remove.hide()
            self.btn_undo.hide()

        elif note.status == "proposed":
            self.tag_label.setText("Đề xuất:")
            self.tag_label.setStyleSheet("color: #B45309; font-size: 11px; font-weight: 600;")
            self.text_label.setStyleSheet("color: #403425; font-size: 12px; font-style: italic;")
            self.sub_info_label.setText("Gợi ý từ ngữ cảnh · Bạn có muốn ghi lại không?")
            self.btn_nav_link.hide()
            self.sub_row.show()

            self.btn_confirm.show()
            self.btn_edit.show()
            self.btn_edit.setText("Sửa")
            self.btn_remove.show()
            self.btn_remove.setText("Bỏ qua")
            self.btn_undo.hide()

        elif note.status == "removed":
            self.tag_label.setText("Đã bỏ:")
            self.tag_label.setStyleSheet("color: #A3937F; font-size: 11px; font-weight: 600;")
            self.text_label.setText(f"Không còn giữ trong ghi chép: “{note.text}”")
            self.text_label.setStyleSheet("color: #9C8E7C; font-size: 12px; font-style: italic;")
            self.sub_row.hide()

            self.btn_confirm.hide()
            self.btn_edit.hide()
            self.btn_remove.hide()
            self.btn_undo.show()

        if note.error_message:
            self.error_label.setText(note.error_message)
            self.error_label.show()
        else:
            self.error_label.hide()
        self.tag_label.setStyleSheet("color: #897D6A; font-size: 11px; border: none; background: transparent;")
        if note.status == 'proposed':
            self.tag_label.setStyleSheet("color: #9B703D; font-size: 11px; border: none; background: transparent;")
        elif note.status == 'active':
            self.tag_label.setStyleSheet("color: #627058; font-size: 11px; border: none; background: transparent;")
        self.text_label.setStyleSheet("color: #70685B; font-size: 12px; border: none; background: transparent;")
        self.btn_nav_link.setToolTip(note.replaced_by_text or note.replaces_text or '')
        self.sub_info_label.setVisible(self.details_open)
        self.sub_row.setVisible(not self.btn_nav_link.isHidden() and (note.status == 'replaced' or self.details_open))
        self._fit_note_text()
        self.layout_changed.emit()
        self.update()

    def _toggle_details(self, opened):
        self.details_open = bool(opened)
        self.sub_info_label.setVisible(self.details_open)
        self.sub_row.setVisible(not self.btn_nav_link.isHidden() and (self.note.status == 'replaced' or self.details_open))
        self.layout_changed.emit()

    def _start_edit(self) -> None:
        if self.note.status == "replaced" and self.note.replaced_by_turn_id:
            # Sửa bản mới: điều hướng VÀ mở editor tại bản đang dùng
            self.edit_replacement_requested.emit(self.note.replaced_by_turn_id, self.note.replaced_by_note_id or "")
            return
        if not self.editing:
            self.editing = True
            self.editor.setPlainText(self.note.text)
        self.editor_section.show()
        self.actions_widget.hide()
        self.editor.setFocus()
        self.layout_changed.emit()
        self.update()

    def _cancel_edit(self) -> None:
        self.editing = False
        self.editor_section.hide()
        self.actions_widget.show()
        self.error_label.hide()
        self.btn_edit.setFocus()
        self.layout_changed.emit()
        self.update()

    def _save_edit(self) -> None:
        new_text = self.editor.toPlainText().strip()
        if not new_text:
            self.error_label.setText("Nội dung ghi chú không được để trống.")
            self.error_label.show()
            return
        self.edit_saved.emit(self.note.id, self.note.revision, new_text)

    def _on_remove_clicked(self) -> None:
        self.note_removed.emit(self.note.id, self.note.revision)

    def _on_undo_clicked(self) -> None:
        self.note_restored.emit(self.note.id)

    def _on_confirm_clicked(self) -> None:
        self.note_confirmed.emit(self.note.id)

    def _on_nav_link_clicked(self) -> None:
        if self.note.status == "replaced" and self.note.replaced_by_turn_id:
            self.navigate_requested.emit(self.note.replaced_by_turn_id, self.note.replaced_by_note_id or "")
        elif self.note.replaces_turn_id:
            self.navigate_requested.emit(self.note.replaces_turn_id, self.note.replaces_note_id or "")


class TurnNotesPane(QWidget):
    """
    Container for notes belonging to a specific chat turn.
    Placed cleanly beneath the assistant's response text and above work trace.
    No internal scroll area — part of the main chat stream layout.
    """
    note_edit_saved = pyqtSignal(str, int, str)
    note_removed = pyqtSignal(str, int)
    note_restored = pyqtSignal(str)
    note_confirmed = pyqtSignal(str)
    navigate_requested = pyqtSignal(int, str)
    edit_replacement_requested = pyqtSignal(int, str)
    changed = pyqtSignal()

    def __init__(self, turn_id: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.turn_id = turn_id
        self.rows: Dict[str, InlineNoteRow] = {}
        self.setObjectName("TurnNotesPane")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 1, 0, 1)
        self.layout.setSpacing(4)
        self.hide()

    def set_notes(self, notes: List[TurnNoteItem]) -> None:
        """Update the notes displayed in this turn."""
        current_ids = {n.id for n in notes}
        for nid in list(self.rows.keys()):
            if nid not in current_ids:
                row = self.rows.pop(nid)
                self.layout.removeWidget(row)
                row.deleteLater()

        for note in notes:
            if note.id in self.rows:
                self.rows[note.id].refresh(note)
            else:
                row = InlineNoteRow(note, self)
                row.edit_saved.connect(self.note_edit_saved.emit)
                row.note_removed.connect(self.note_removed.emit)
                row.note_restored.connect(self.note_restored.emit)
                row.note_confirmed.connect(self.note_confirmed.emit)
                row.navigate_requested.connect(self.navigate_requested.emit)
                row.edit_replacement_requested.connect(self.edit_replacement_requested.emit)
                row.layout_changed.connect(self.changed.emit)
                self.rows[note.id] = row
                self.layout.addWidget(row)

        self.setVisible(bool(self.rows))
        self.changed.emit()

    def highlight_note(self, note_id: str) -> None:
        if note_id in self.rows:
            self.rows[note_id].trigger_highlight()
