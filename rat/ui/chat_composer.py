"""A small, plain-text composer that grows without turning quick chat into a form."""

from __future__ import annotations

import math

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QInputMethodEvent, QKeyEvent, QTextCursor, QTextOption
from PyQt6.QtWidgets import QFrame, QPlainTextEdit


class ChatComposer(QPlainTextEdit):
    submit_requested = pyqtSignal()
    height_changed = pyqtSignal(int)
    MAX_VISIBLE_LINES = 4
    MIN_HEIGHT = 36

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._preedit_active = False
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setTabChangesFocus(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.document().setDocumentMargin(0)
        self.setViewportMargins(0, 7, 0, 7)
        self.setFixedHeight(self.MIN_HEIGHT)
        self.setAccessibleName("Câu hỏi cho Chuột")
        self.setAccessibleDescription("Enter gửi câu hỏi; Shift+Enter xuống dòng.")
        self.setToolTip("Enter gửi · Shift+Enter xuống dòng")
        self.textChanged.connect(self._update_height)

    # Keep the existing omnibar's text-editing call sites and shortcuts readable.
    def text(self) -> str:
        return self.toPlainText()

    def setText(self, text: str) -> None:
        self.setPlainText(text)

    def hasSelectedText(self) -> bool:
        return self.textCursor().hasSelection()

    def setCursorPosition(self, position: int) -> None:
        text = self.toPlainText()
        cursor = self.textCursor()
        if position >= len(text):
            cursor.movePosition(QTextCursor.MoveOperation.End)
        else:
            # Qt positions are UTF-16 offsets, not Python Unicode character counts.
            offset = len(text[:max(0, position)].encode("utf-16-le")) // 2
            cursor.setPosition(offset)
        self.setTextCursor(cursor)

    @property
    def is_composing(self) -> bool:
        return self._preedit_active

    def inputMethodEvent(self, event: QInputMethodEvent) -> None:
        self._preedit_active = bool(event.preeditString())
        super().inputMethodEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._preedit_active:
                # Enter may accept a Vietnamese/CJK composition; never send it yet.
                event.accept()
                return
            if not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.submit_requested.emit()
                event.accept()
                return
        super().keyPressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_height()

    def _update_height(self) -> None:
        self.document().documentLayout().documentSize()
        lines = 0
        block = self.document().begin()
        while block.isValid() and lines < self.MAX_VISIBLE_LINES:
            lines += max(1, block.layout().lineCount())
            block = block.next()
        visible_lines = min(max(1, lines), self.MAX_VISIBLE_LINES)
        target = max(self.MIN_HEIGHT, math.ceil(self.fontMetrics().lineSpacing() * visible_lines + 16))
        if self.height() != target:
            self.setFixedHeight(target)
            self.height_changed.emit(target)
