"""Shared layout primitives for RAT's compact and full conversation surface."""
from __future__ import annotations

import os

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QPlainTextEdit, QPushButton,
    QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)


def motion_enabled() -> bool:
    env = os.getenv("RAT_REDUCE_MOTION", "").lower()
    if env in ("1", "true", "yes"):
        return False
    if env in ("0", "false", "no"):
        return True
    app = QApplication.instance()
    if app is not None:
        prop = app.property("ratReduceMotion")
        if prop is not None:
            return not bool(prop)
    try:
        from AppKit import NSWorkspace
        return not NSWorkspace.sharedWorkspace().accessibilityDisplayShouldReduceMotion()
    except (ImportError, AttributeError):
        return True


class ChatComposer(QPlainTextEdit):
    """One persistent editor, with a small line-edit compatibility API."""
    returnPressed = pyqtSignal()
    height_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTabChangesFocus(True)
        self.document().setDocumentMargin(3)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._in_ime_composition = False
        self.textChanged.connect(self._fit_height)
        self.setFixedHeight(34)

    def is_composing(self) -> bool:
        return bool(getattr(self, "_in_ime_composition", False))

    def inputMethodEvent(self, event):
        self._in_ime_composition = bool(event.preeditString())
        super().inputMethodEvent(event)
        if not event.preeditString():
            self._in_ime_composition = False

    def text(self):
        return self.toPlainText()

    def setText(self, text):
        self.setPlainText(text)

    def setCursorPosition(self, position):
        cursor = self.textCursor()
        cursor.setPosition(min(position, len(self.text())))
        self.setTextCursor(cursor)

    def cursorPosition(self):
        return self.textCursor().position()

    def setSelection(self, start, length):
        cursor = self.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cursor)

    def hasSelectedText(self):
        return self.textCursor().hasSelection()

    def selectedText(self):
        return self.textCursor().selectedText().replace("\u2029", "\n")

    def selectionStart(self):
        return self.textCursor().selectionStart()

    def _fit_height(self):
        # Count wrapped visual lines without changing the editor or caret.
        lines = sum(max(1, block.layout().lineCount()) for block in self._blocks())
        target = min(112, max(34, lines * self.fontMetrics().lineSpacing() + 10))
        if target != self.height():
            self.setFixedHeight(target)
            self.height_changed.emit()

    def _blocks(self):
        block = self.document().begin()
        while block.isValid():
            yield block
            block = block.next()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_height()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.returnPressed.emit()
            event.accept()
        else:
            super().keyPressEvent(event)


class CurrentPageStack(QStackedWidget):
    """Hidden legacy pages cannot impose their minimum size on the chat box."""
    def add_lazy_page(self, factory):
        if not hasattr(self, '_page_factories'):
            self._page_factories = {}
        placeholder = QWidget(self)
        index = self.addWidget(placeholder)
        self._page_factories[index] = factory
        return placeholder

    def ensure_page(self, index):
        factory = getattr(self, '_page_factories', {}).get(index)
        if factory is not None:
            page = factory()  # Leave the factory available if construction fails.
            old = self.widget(index)
            self.removeWidget(old)
            self.insertWidget(index, page)
            del self._page_factories[index]
            old.deleteLater()
        return self.widget(index)

    def setCurrentIndex(self, index):
        self.ensure_page(index)
        super().setCurrentIndex(index)

    def minimumSizeHint(self):
        page = self.currentWidget()
        return page.minimumSizeHint() if page else QSize(0, 0)

    def sizeHint(self):
        page = self.currentWidget()
        return page.sizeHint() if page else QSize(0, 0)


class ResponsiveFields(QWidget):
    """Keep live field widgets while reflowing between one and two columns."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self.columns = 0
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(10)

    def add_field(self, widget):
        self.rows.append(widget)
        self._reflow()

    def _reflow(self):
        columns = 2 if self.width() >= 520 and len(self.rows) > 1 else 1
        if columns == self.columns and self.grid.count() == len(self.rows):
            return
        self.columns = columns
        while self.grid.count():
            self.grid.takeAt(0)  # Reparenting or recreation would lose editor state.
        for index, row in enumerate(self.rows):
            self.grid.addWidget(row, index // columns, index % columns)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, int(columns == 2))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow()


class Disclosure(QWidget):
    """A keyboard-accessible inline detail region with optional height motion."""
    changed = pyqtSignal()

    def __init__(self, title, body, parent=None):
        super().__init__(parent)
        self.title, self.body = title, body
        self.opened = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        self.button = QPushButton("▸ " + title)
        self.button.setCheckable(True)
        self.button.setAccessibleName(title)
        self.button.setStyleSheet("QPushButton { background: transparent; border: none; color: #766548; font-size: 12px; text-align: left; padding: 5px 0; } QPushButton:hover { color: #302B24; }")
        self.button.toggled.connect(self.set_open)
        layout.addWidget(self.button)
        layout.addWidget(body)
        body.hide()
        self.animation = QPropertyAnimation(body, b"maximumHeight", self)
        self.animation.setDuration(170)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.finished.connect(self._finished)

    def set_open(self, opened, animate=True):
        self.opened = bool(opened)
        focus = QApplication.focusWidget()
        if not self.opened and focus is not None and (focus is self.body or self.body.isAncestorOf(focus)):
            self.button.setFocus(Qt.FocusReason.OtherFocusReason)
        blocked = self.button.blockSignals(True)
        self.button.setChecked(self.opened)
        self.button.blockSignals(blocked)
        self.button.setText(("▾ " if self.opened else "▸ ") + self.title)
        self.animation.stop()
        current = self.body.height() if not self.body.isHidden() else 0
        target = max(1, self.body.sizeHint().height()) if self.opened else 0
        if animate and motion_enabled() and self.isVisible():
            self.body.setMaximumHeight(current)
            self.body.show()
            self.animation.setStartValue(current)
            self.animation.setEndValue(target)
            self.animation.start()
        else:
            self._finished()
        self.changed.emit()

    def _finished(self):
        self.body.setVisible(self.opened)
        self.body.setMaximumHeight(16777215 if self.opened else 0)

