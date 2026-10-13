"""A shared notebook and public work trace inside the conversation surface."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)
from rat.engine.work_trace import summarize_step
from rat.ui.surface_layout import Disclosure


BUTTON = 'QPushButton { color: #796347; background: transparent; border: none; padding: 4px 6px; font-size: 11px; } QPushButton:hover, QPushButton:focus { background: #F2EADD; border-radius: 5px; } QPushButton:disabled { color: #B6ADA0; }'


class NoteRow(QWidget):
    saved = pyqtSignal(str, int, str)
    removed = pyqtSignal(str, int)

    def __init__(self, note, parent=None):
        super().__init__(parent)
        self.note = note
        self.editing = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 5)
        layout.setSpacing(3)
        self.text = QLabel()
        self.text.setTextFormat(Qt.TextFormat.PlainText)
        self.text.setWordWrap(True)
        self.text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.text.setStyleSheet('color: #433B30; font-size: 12px; border: none;')
        layout.addWidget(self.text)
        self.source = QLabel()
        self.source.setStyleSheet('color: #958570; font-size: 10px; border: none;')
        layout.addWidget(self.source)
        self.editor = QPlainTextEdit()
        self.editor.setObjectName('note-edit-' + note['id'])
        self.editor.setAccessibleName('Nội dung ghi chú')
        self.editor.setTabChangesFocus(True)
        self.editor.setFixedHeight(66)
        self.editor.setStyleSheet('QPlainTextEdit { color: #433B30; background: #F7F2E9; border: 1px solid #E5DACA; border-radius: 6px; padding: 4px; font-size: 12px; }')
        self.editor.hide()
        layout.addWidget(self.editor)
        controls = QHBoxLayout()
        self.edit = QPushButton('Sửa')
        self.apply = QPushButton('Áp dụng')
        self.cancel = QPushButton('Hủy')
        self.delete = QPushButton('Xóa khỏi ghi chép')
        for button in (self.edit, self.apply, self.cancel, self.delete):
            button.setStyleSheet(BUTTON)
            controls.addWidget(button)
        controls.addStretch()
        layout.addLayout(controls)
        self.edit.clicked.connect(self._edit)
        self.cancel.clicked.connect(self._cancel)
        self.apply.clicked.connect(self._save)
        self.delete.clicked.connect(lambda: self.removed.emit(self.note['id'], self.note['revision']))
        self.apply.hide()
        self.cancel.hide()
        self.refresh(note)

    def refresh(self, note):
        if not self.editing:
            self.note = note
        self.text.setText(note['text'])
        label = 'Bạn đã nhập' if note['source'].startswith('control:') else 'Bạn sửa / xác nhận' if note['source'] == 'user_edit' else 'Bạn ghi' if note['source'] == 'user_note' else 'Trích lời bạn' if note['confirmed'] else 'Đề xuất từ ngữ cảnh · cần xác nhận'
        self.source.setText(label)
        self.source.setToolTip(note.get('quote', '') or note['text'])
        self.edit.setText('Sửa' if note['confirmed'] else 'Xem và xác nhận')

    def _edit(self):
        self.editing = True
        self.editor.setPlainText(self.note['text'])
        self.editor.show()
        self.apply.show()
        self.cancel.show()
        self.edit.hide()
        self.editor.setFocus()

    def _cancel(self):
        self.editing = False
        self.editor.hide()
        self.apply.hide()
        self.cancel.hide()
        self.edit.show()
        self.edit.setFocus()

    def _save(self):
        self.saved.emit(self.note['id'], self.note['revision'], self.editor.toPlainText())

    def set_busy(self, busy):
        for button in (self.edit, self.apply, self.delete):
            button.setEnabled(not busy)


class NotebookPane(Disclosure):
    changed_notes = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, notebook, parent=None):
        self.notebook = notebook
        self.rows = {}
        self.busy = False
        body = QScrollArea()
        body.setWidgetResizable(True)
        body.setFrameShape(QScrollArea.Shape.NoFrame)
        body.setMaximumHeight(190)
        body.setStyleSheet('QScrollArea { background: transparent; border: none; }')
        content = QWidget()
        content.setStyleSheet('background: transparent;')
        layout = QVBoxLayout(content)
        layout.setContentsMargins(2, 2, 5, 4)
        layout.setSpacing(6)
        hint = QLabel('Những điều giữ cho cuộc trò chuyện này. Bạn có thể sửa hoặc xóa.')
        hint.setWordWrap(True)
        hint.setStyleSheet('color: #958570; font-size: 11px;')
        layout.addWidget(hint)
        self.note_layout = QVBoxLayout()
        self.note_layout.setSpacing(5)
        layout.addLayout(self.note_layout)
        add = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText('Ghi thêm một điều…')
        self.input.setAccessibleName('Ghi thêm cho Chuột')
        self.input.setStyleSheet('QLineEdit { color: #433B30; background: #F7F2E9; border: 1px solid #E5DACA; border-radius: 6px; padding: 6px; }')
        self.add = QPushButton('Ghi lại')
        self.add.setStyleSheet(BUTTON)
        add.addWidget(self.input, 1)
        add.addWidget(self.add)
        layout.addLayout(add)
        body.setWidget(content)
        super().__init__('Ghi chép', body, parent)
        self.add.clicked.connect(self._add)
        self.input.returnPressed.connect(self._add)
        self.refresh()

    def _add(self):
        if self.busy:
            return
        try:
            self.notebook.add_user_note(self.input.text())
        except ValueError as exc:
            self.error.emit(str(exc))
            return
        self.input.clear()
        self.refresh()
        self.changed_notes.emit()

    def _save(self, note_id, revision, text):
        if self.busy:
            return
        try:
            self.notebook.user_edit(note_id, revision, text)
        except ValueError as exc:
            self.error.emit(str(exc))
            return
        self.rows[note_id]._cancel()
        self.refresh()
        self.changed_notes.emit()

    def _remove(self, note_id, revision):
        if self.busy:
            return
        try:
            self.notebook.remove(note_id, revision)
        except ValueError as exc:
            self.error.emit(str(exc))
            return
        self.refresh()
        self.changed_notes.emit()

    def refresh(self):
        notes = self.notebook.snapshot()
        ids = {note['id'] for note in notes}
        for note_id in set(self.rows) - ids:
            row = self.rows[note_id]
            if row.editing:
                row.source.setText('Ghi chú vừa đổi · bản nháp của bạn vẫn được giữ')
                continue
            self.rows.pop(note_id)
            self.note_layout.removeWidget(row)
            row.hide()
            row.deleteLater()
        for note in notes:
            row = self.rows.get(note['id'])
            if row is None:
                row = NoteRow(note)
                row.saved.connect(self._save)
                row.removed.connect(self._remove)
                row.cancel.clicked.connect(self.refresh)
                self.rows[note['id']] = row
                self.note_layout.addWidget(row)
            row.refresh(note)
            row.set_busy(self.busy)
        self.title = 'Ghi chép' + (f' · {len(notes)} điều' if notes else '')
        self.button.setText(('▾ ' if self.opened else '▸ ') + self.title)
        self.setVisible(bool(notes) or self.opened)
        self.changed.emit()

    def set_open(self, opened, animate=True):
        super().set_open(opened, animate)
        self.setVisible(bool(self.rows) or self.opened)

    def set_busy(self, busy):
        self.busy = bool(busy)
        self.add.setEnabled(not busy)
        for row in self.rows.values():
            row.set_busy(busy)


class WorkTracePane(Disclosure):
    def __init__(self, parent=None):
        body = QWidget()
        self.flow = QVBoxLayout(body)
        self.flow.setContentsMargins(3, 2, 2, 4)
        self.flow.setSpacing(7)
        self.caption = QLabel('Các bước thực hiện, dự định và dữ kiện Chuột dùng cho yêu cầu này.')
        self.caption.setWordWrap(True)
        self.caption.setStyleSheet('color: #978974; font-size: 11px;')
        self.flow.addWidget(self.caption)
        self.entries = {}
        self.status = ''
        super().__init__('Cách Chuột làm', body, parent)
        self.button.setToolTip('Luồng suy luận và thao tác: dự định, công cụ đã chạy và dữ kiện nhận được.')
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        self.preview.setTextFormat(Qt.TextFormat.PlainText)
        self.preview.setStyleSheet('color: #9B886A; font-size: 11px; border: none; padding: 0 3px 3px;')
        self.layout().insertWidget(1, self.preview)
        self.preview.hide()
        self.hide()

    def set_status(self, status):
        self.status = status
        self._title()
        self.show()

    def _title(self):
        detail = f'{len(self.entries)} bước' if self.entries else self.status
        self.title = 'Cách Chuột làm' + (' · ' + detail if detail else '')
        self.button.setText(('▾ ' if self.opened else '▸ ') + self.title)
        self.changed.emit()

    def add_step(self, step):
        entry = summarize_step(step)
        if entry.number in self.entries:
            return
        label = QLabel()
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        suffix = {'proposed': ' · dự định', 'error': ' · chưa xong', 'waiting': ' · cần thêm dữ kiện', 'stopped': ' · đã dừng', 'unchecked': ' · chưa kiểm chứng'}.get(entry.status, '')
        label.setText(f'{entry.number}. {entry.title}{suffix}' + ('\n' + entry.detail if entry.detail else ''))
        label.setStyleSheet('color: #806B50; font-size: 12px; border: none; padding: 2px 0;')
        self.flow.addWidget(label)
        self.entries[entry.number] = entry
        self.preview.setText(' → '.join(item.title for item in list(self.entries.values())[-3:]))
        self.preview.show()
        self._title()
        self.show()

    def finish(self, response):
        for step in response.steps:
            self.add_step(step)
        self.set_status('Đã dừng' if response.error == 'cancelled' else 'Chưa hoàn tất' if response.error else 'Cần thêm dữ kiện' if response.pending_input_request else 'Đã trả lời')
