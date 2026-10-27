"""Receive native drag file promises only after an explicit accepted drop."""
from pathlib import Path
import logging
import sys
import tempfile
from uuid import uuid4

from PyQt6.QtCore import QObject, QTimer, Qt, pyqtSignal, pyqtSlot

logger = logging.getLogger(__name__)


def register_file_promises(view):
    """Extend the app's Qt NSView drag types; keep Qt's existing registrations."""
    if sys.platform != 'darwin':
        return False
    from PyQt6.QtGui import QGuiApplication
    application = QGuiApplication.instance()
    if application is None or application.platformName() != 'cocoa':
        # Offscreen/minimal platforms can return a non-NSView window id.
        # Passing that id to objc_object is unsafe, even inside try/except.
        return False
    try:
        import ctypes
        import objc
        from AppKit import NSFilePromiseReceiver
        # On Cocoa, QWindow.winId() is the NSView pointer. This only configures
        # our own app window; it never monitors or manipulates another app.
        native = objc.objc_object(c_void_p=ctypes.c_void_p(int(view.winId())))
        types = list(native.registeredDraggedTypes() or [])
        types = list(dict.fromkeys(types + list(NSFilePromiseReceiver.readableDraggedTypes())))
        native.registerForDraggedTypes_(types)
        logger.info('image_promise_types_registered count=%s', len(types))
        return True
    except Exception as exc:
        logger.warning('image_promise_registration_failed kind=%s', type(exc).__name__)
        return False


def drag_file_promises():
    if sys.platform != 'darwin':
        return []
    try:
        from AppKit import NSPasteboard, NSPasteboardNameDrag, NSFilePromiseReceiver
        board = NSPasteboard.pasteboardWithName_(NSPasteboardNameDrag)
        return list(board.readObjectsForClasses_options_([NSFilePromiseReceiver], {}) or [])
    except Exception:
        return []


class MacImagePromises(QObject):
    completed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pending = {}
        self.closed = False
        self.completed.connect(self._completed, Qt.ConnectionType.QueuedConnection)

    def receive(self, receivers, ready, failed):
        if len(receivers) != 1 or len(receivers[0].fileNames() or []) != 1:
            raise ValueError('Hãy thả từng ảnh một để RAT dịch.')
        from Foundation import NSURL, NSOperationQueue
        key = uuid4().hex
        temporary = tempfile.TemporaryDirectory(prefix='rat-mini-drop-')
        queue = NSOperationQueue.alloc().init()
        queue.setMaxConcurrentOperationCount_(1)
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._finish(key, error='macOS chưa chuyển xong ảnh. Hãy chờ ảnh lưu rồi thả lại.'))

        def reader(file_url, error):
            # Called off the GUI thread; emit only metadata, never touch Qt UI.
            if self.closed:
                return
            path = str(file_url.path()) if file_url is not None and error is None else None
            try:
                self.completed.emit((key, path, error is not None))
            except RuntimeError:
                pass  # Window/Qt object already destroyed during application exit.

        self.pending[key] = dict(temporary=temporary, queue=queue, timer=timer,
            ready=ready, failed=failed, receiver=receivers[0], reader=reader)

        def start():
            if self.closed or key not in self.pending:
                return
            try:
                receivers[0].receivePromisedFilesAtDestination_options_operationQueue_reader_(
                    NSURL.fileURLWithPath_(temporary.name), {}, queue, reader)
            except Exception as exc:
                logger.warning('image_promise_start_failed kind=%s', type(exc).__name__)
                self._finish(key, error='macOS chưa chuyển được ảnh. Hãy chờ ảnh lưu rồi thả lại.')
                raise ValueError('macOS chưa chuyển được ảnh. Hãy chờ ảnh lưu rồi thả lại.') from exc

        timer.start(30000)
        # The native request must be registered during the accepted drop.
        # The operation queue receives the file asynchronously; this does not
        # wait for the provider to write it on the GUI thread.
        start()

    @pyqtSlot(object)
    def _completed(self, result):
        key, path, error = result
        if self.closed or key not in self.pending:
            return
        if error or not path:
            self._finish(key, error='macOS chưa chuyển được ảnh. Hãy thả lại ảnh đã lưu.')
            return
        row = self.pending[key]
        try:
            resolved = Path(path).resolve(strict=True)
            if not resolved.is_relative_to(Path(row['temporary'].name).resolve()):
                raise ValueError('Ảnh nhận được không nằm trong thư mục chuyển ảnh của RAT.')
            self._finish(key, path=resolved)
        except (OSError, ValueError):
            self._finish(key, error='Chưa đọc được ảnh macOS vừa chuyển. Hãy thả lại ảnh đã lưu.')

    def _finish(self, key, path=None, error=None):
        row = self.pending.pop(key, None)
        if row is None:
            return
        row['timer'].stop()
        row['timer'].deleteLater()
        try:
            if not self.closed:
                if error:
                    row['failed'](error)
                else:
                    row['ready'](path)
        except Exception as exc:
            logger.warning('image_promise_callback_failed kind=%s', type(exc).__name__)
            if not self.closed:
                row['failed']('Chưa nhận được ảnh. Hãy thả lại file ảnh đã lưu.')
        finally:
            row['queue'].cancelAllOperations()
            row['temporary'].cleanup()

    def close(self):
        self.closed = True
        for key in list(self.pending):
            self._finish(key)
