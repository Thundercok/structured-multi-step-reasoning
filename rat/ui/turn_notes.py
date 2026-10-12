"""
rat.ui.turn_notes — Turn-level inline notes and revision linking.
Notes belong to specific conversation turns rather than an isolated pane.
Old revisions are preserved with forward links to newer revisions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QKeyEvent, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


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


BUTTON_STYLE = """
QPushButton {
    color: #796347;
    background: transparent;
    border: none;
    padding: 2px 7px;
    font-size: 11px;
    border-radius: 4px;
}
QPushButton:hover {
    background: #F0E6D8;
    color: #4D3C28;
}
QPushButton:focus {
    background: #EAE0D0;
    outline: none;
}
QPushButton:disabled {
    color: #BDB2A3;
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
    color: #8A5826;
    background: #F5ECE0;
    border: 1px solid #E2D3BE;
    border-radius: 4px;
    padding: 1px 6px;
    font-size: 11px;
    font-weight: 500;
}
QPushButton:hover {
    background: #EDDFC8;
    color: #6E431B;
    border-color: #D4BE9F;
}
QPushButton:focus {
    background: #E5D3B8;
    outline: none;
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
    - Active note with quick [Sửa] [Bỏ] controls
    - Old replaced note with intact snapshot and forward link to newer note
    - Replacement note with link back to predecessor
    - Model proposal with [Xác nhận] / [Sửa]
    - Tombstone with [Hoàn tác]
    - In-place editor with draft preservation and stale conflict warning
    """
    edit_saved = pyqtSignal(str, int, str)  # note_id, revision, new_text
    note_removed = pyqtSignal(str, int)     # note_id, revision
    note_restored = pyqtSignal(str)         # note_id
    note_confirmed = pyqtSignal(str)        # note_id
    navigate_requested = pyqtSignal(int, str)  # target_turn_id, target_note_id
    highlight_changed = pyqtSignal()

    def __init__(self, note: TurnNoteItem, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.note = note
        self.editing = False
        self._highlight_ratio = 0.0
        self._init_ui()
        self.refresh(note)

    def _init_ui(self) -> None:
        self.setObjectName("InlineNoteRow")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 6, 8, 6)
        self.layout.setSpacing(4)

        # Main row: Tag + Text + Inline Actions
        self.header_row = QWidget()
        h_layout = QHBoxLayout(self.header_row)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(6)

        self.tag_label = QLabel()
        self.tag_label.setStyleSheet("font-size: 11px; font-weight: 600; border: none; background: transparent;")
        h_layout.addWidget(self.tag_label, 0, Qt.AlignmentFlag.AlignTop)

        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
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

        h_layout.addWidget(self.actions_widget, 0, Qt.AlignmentFlag.AlignTop)
        self.layout.addWidget(self.header_row)

        # Sub-row for revision linking / metadata
        self.sub_row = QWidget()
        s_layout = QHBoxLayout(self.sub_row)
        s_layout.setContentsMargins(16, 0, 0, 0)
        s_layout.setSpacing(6)

        self.sub_info_label = QLabel()
        self.sub_info_label.setStyleSheet("color: #8C7B65; font-size: 11px; border: none; background: transparent;")
        s_layout.addWidget(self.sub_info_label, 0)

        self.btn_nav_link = QPushButton()
        self.btn_nav_link.setStyleSheet(LINK_BUTTON_STYLE)
        self.btn_nav_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nav_link.clicked.connect(self._on_nav_link_clicked)
        s_layout.addWidget(self.btn_nav_link, 0)

        s_layout.addStretch()
        self.layout.addWidget(self.sub_row)

        # Editor section (hidden by default)
        self.editor_section = QWidget()
        e_layout = QVBoxLayout(self.editor_section)
        e_layout.setContentsMargins(0, 4, 0, 0)
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

    def set_highlight_ratio(self, val: float) -> None:
        self._highlight_ratio = val
        self.update()

    highlight_ratio = pyqtProperty(float, get_highlight_ratio, set_highlight_ratio)

    def trigger_highlight(self) -> None:
        """Play a smooth amber glow to indicate this note is being referenced or selected by Chuột."""
        self.anim.stop()
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.start()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Base background: warm translucent paper tint
        bg_color = QColor("#F8F3EA")
        border_color = QColor("#E7DDD0")

        if self.note.status == "replaced":
            bg_color = QColor("#F6F2EA")
            border_color = QColor("#EADFD0")
        elif self.note.status == "proposed":
            bg_color = QColor("#FEF8EE")
            border_color = QColor("#F3DFB7")
        elif self.note.status == "removed":
            bg_color = QColor("#F5EFEB")
            border_color = QColor("#E2D8CD")

        if self._highlight_ratio > 0.001:
            # Blend with radiant amber glow
            glow = QColor("#FDE68A")
            alpha = int(self._highlight_ratio * 180)
            glow.setAlpha(alpha)
            bg_color = QColor(
                int(bg_color.red() * (1 - self._highlight_ratio) + 254 * self._highlight_ratio),
                int(bg_color.green() * (1 - self._highlight_ratio) + 243 * self._highlight_ratio),
                int(bg_color.blue() * (1 - self._highlight_ratio) + 199 * self._highlight_ratio),
            )
            border_color = QColor("#D97706")

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 7, 7)

        painter.fillPath(path, bg_color)
        pen = QPen(border_color, 1.2 if self._highlight_ratio > 0.1 else 1.0)
        if self.note.status == "proposed":
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
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
                self.btn_nav_link.setText(f"Xem bản cũ: {note.replaces_text or ''}")
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
            self.tag_label.setText("Bản cũ:")
            self.tag_label.setStyleSheet("color: #968673; font-size: 11px; font-weight: 600;")
            self.text_label.setStyleSheet("color: #756959; font-size: 12px; text-decoration: line-through;")
            self.sub_info_label.setText(f"Đã được thay thế ở lượt {note.replaced_by_turn_id or 'sau'} →")
            self.btn_nav_link.setText(f"Xem bản mới ({note.replaced_by_text or 'chi tiết'})")
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

        self.update()

    def _start_edit(self) -> None:
        if self.note.status == "replaced" and self.note.replaced_by_turn_id:
            # Sửa trên bản cũ dẫn tới bản mới đang dùng
            self.navigate_requested.emit(self.note.replaced_by_turn_id, self.note.replaced_by_note_id or "")
            return
        if not self.editing:
            self.editing = True
            self.editor.setPlainText(self.note.text)
        self.editor_section.show()
        self.actions_widget.hide()
        self.editor.setFocus()

    def _cancel_edit(self) -> None:
        self.editing = False
        self.editor_section.hide()
        self.actions_widget.show()
        self.error_label.hide()
        self.btn_edit.setFocus()

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
    Container for all notes recorded or referenced in a specific chat turn.
    Placed cleanly beneath the assistant's response text and above work trace.
    No internal scroll area — part of the main chat stream layout.
    """
    note_edit_saved = pyqtSignal(str, int, str)
    note_removed = pyqtSignal(str, int)
    note_restored = pyqtSignal(str)
    note_confirmed = pyqtSignal(str)
    navigate_requested = pyqtSignal(int, str)  # target_turn_id, target_note_id

    def __init__(self, turn_id: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.turn_id = turn_id
        self.rows: Dict[str, InlineNoteRow] = {}
        self.setObjectName("TurnNotesPane")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 4, 0, 4)
        self.layout.setSpacing(6)
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
                self.rows[note.id] = row
                self.layout.addWidget(row)

        self.setVisible(bool(self.rows))

    def highlight_note(self, note_id: str) -> None:
        if note_id in self.rows:
            self.rows[note_id].trigger_highlight()
