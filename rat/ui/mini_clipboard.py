"""Look input adapter only; never runs tools, OCR, translation or a model."""
import hashlib
import time

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QCursor, QGuiApplication


class LookClipboard(QObject):
    textReady = pyqtSignal(str, object)
    unavailable = pyqtSignal()
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.timer = QTimer(self)
        self.timer.setInterval(400)
        self.timer.timeout.connect(self.poll)
        self.pending = None
        self.last_digest = None
        self.board = None
        if QGuiApplication.platformName() == 'cocoa':
            from AppKit import NSPasteboard
            self.board = NSPasteboard.generalPasteboard()
        self.count = None

    def start(self):
        if self.timer.isActive():
            return
        if self.board is None:
            self.unavailable.emit()
            return
        try:
            self.count = int(self.board.changeCount())
            self.pending = None
            self.last_digest = None
            self.timer.start()
        except Exception:
            self.unavailable.emit()

    def stop(self):
        self.timer.stop()
        self.pending = None

    def ignore_own_write(self, text):
        self.pending = None
        self.last_digest = hashlib.sha256(text.encode()).digest()
        if self.board is not None:
            try:
                self.count = int(self.board.changeCount())
            except Exception:
                self.stop()
                self.unavailable.emit()

    def poll(self):
        try:
            count = int(self.board.changeCount())
            if count != self.count:
                self.count = count
                self.changed.emit()
                # Capture a position, not the selected text's unavailable bounds.
                self.pending = (count, time.monotonic(), QCursor.pos())
                return
            if self.pending is None or time.monotonic() - self.pending[1] < 0.25:
                return
            _, _, point = self.pending
            self.pending = None
            mime = QGuiApplication.clipboard().mimeData()
            if not mime or mime.hasUrls() or mime.hasImage() or not mime.hasText():
                return
            # Snapshot text once; retain only its digest after delivery.
            text = mime.text()
            if int(self.board.changeCount()) != count or not text.strip():
                return
            if len(text) > 8000:
                self.textReady.emit('', point)
                return
            digest = hashlib.sha256(text.encode()).digest()
            if digest != self.last_digest:
                self.last_digest = digest
                self.textReady.emit(text, point)
        except Exception:
            self.stop()
            self.unavailable.emit()
