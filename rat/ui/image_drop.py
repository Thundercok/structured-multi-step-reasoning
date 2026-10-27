"""Native Qt drag ingress; UI normalization only, business work stays in tools."""
import logging
import json
from pathlib import Path
import tempfile
import time
from uuid import uuid4
from PyQt6.QtCore import QObject, QEvent, Qt, QUrl

from rat.ui.image_input import ENCODED_IMAGE_TYPES, image_from_mime, image_from_url
from rat.ui.macos_image_promise import MacImagePromises, drag_file_promises, register_file_promises

logger = logging.getLogger(__name__)


class ImageDropFilter(QObject):
    def __init__(self, view, controller, diagnostic_file=None):
        super().__init__(view)
        self.view, self.controller = view, controller
        self.promises = MacImagePromises(self)
        self.diagnostic_file = Path(diagnostic_file) if diagnostic_file else None
        self.receipt = {}
        view.installEventFilter(self)

    def eventFilter(self, watched, event):
        try:
            return self._image_event(event)
        except Exception as exc:
            # Exceptions escaping a PyQt event filter can abort the GUI process.
            logger.warning('image_drop_adapter_failed kind=%s', type(exc).__name__)
            if event.type() == QEvent.Type.Drop:
                self._diagnostic('adapter_error', error_class=type(exc).__name__)
            self.controller.setDropActive(False)
            if event.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove, QEvent.Type.Drop):
                event.ignore()
                if event.type() == QEvent.Type.Drop:
                    self.controller.image_input_error('Chưa nhận được ảnh. Hãy chờ ảnh lưu rồi thả lại file PNG.')
                return True
            return False

    def _image_event(self, event):
        kind = event.type()
        if kind == QEvent.Type.Show:
            register_file_promises(self.view)
            return False
        if kind == QEvent.Type.DragLeave:
            self.controller.setDropActive(False)
            return True
        if kind not in (QEvent.Type.DragEnter, QEvent.Type.DragMove, QEvent.Type.Drop):
            return False
        root = self.view.rootObject()
        if root is None or not root.property('imageDropEnabled') or not event.possibleActions() & Qt.DropAction.CopyAction:
            self.controller.setDropActive(False)
            event.ignore()
            return True
        mime = event.mimeData()
        if kind != QEvent.Type.Drop:
            accepted = (mime.hasUrls() or mime.hasImage() or any(mime.hasFormat(f) for f in ENCODED_IMAGE_TYPES)
                or (kind == QEvent.Type.DragEnter and bool(drag_file_promises()))
                or bool(self.controller.snapshot['dropActive']))
            self.controller.setDropActive(bool(accepted))
            if accepted:
                event.setDropAction(Qt.DropAction.CopyAction)
                event.accept()
            else:
                event.ignore()
            return True
        self.controller.setDropActive(False)
        self.receipt = {'drop_id':uuid4().hex, 'app_version':self.view.title(), 'received_at':time.time()}
        instruction = root.property('draftText') or ''
        self._diagnostic('received', has_image=bool(mime.hasImage()), url_count=len(mime.urls()),
            encoded_image_formats=[f for f in ENCODED_IMAGE_TYPES if mime.hasFormat(f)])
        logger.info('image_drop_received has_image=%s url_count=%s encoded_image=%s',
            mime.hasImage(), len(mime.urls()), any(mime.hasFormat(f) for f in ENCODED_IMAGE_TYPES))
        # A promise is the actual pending screenshot. An image representation
        # on the same pasteboard may only be its drag icon; prefer the promise.
        receivers = drag_file_promises()
        try:
            if receivers:
                raise ValueError('image_file_promise_pending')
            image, label = image_from_mime(mime)
        except ValueError as exc:
            logger.info('image_drop_fallback promise_count=%s', len(receivers))
            if not receivers:
                self._diagnostic('rejected', reason='no_readable_image_or_promise', promise_count=0)
                self.controller.image_input_error(str(exc))
                event.ignore()
                return True
            token = self.controller.beginImageReceive()
            if token is None:
                event.ignore()
                return True
            try:
                event.setDropAction(Qt.DropAction.CopyAction)
                event.accept()
                self._diagnostic('awaiting_file', promise_count=len(receivers))
                self.controller.engagementRequested.emit()  # explicit drop only; never a late promise callback
                self.promises.receive(receivers,
                    lambda path: self._promised_image(token, path, instruction),
                    lambda message: self._promise_error(token, message))
            except Exception as error:
                self._diagnostic('promise_start_failed', error_class=type(error).__name__)
                message = str(error) if isinstance(error, ValueError) else 'Chưa nhận được ảnh thu nhỏ. Hãy chờ ảnh lưu rồi thả lại.'
                self.controller.finishImageReceive(token, error=message)
                event.ignore()
                return True
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            return True
        if self.controller.acceptDroppedImage(image, label, instruction):
            self._diagnostic('accepted_ingress', route=image.origin, byte_count=len(image.content))
            self.controller.engagementRequested.emit()
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()
        return True

    def _promised_image(self, token, path, instruction):
        if not self.controller.isImageReceiveCurrent(token):
            return
        try:
            image, label = image_from_url(QUrl.fromLocalFile(str(path)), origin='dropped_image')
            self._diagnostic('accepted_ingress', route='file_promise', byte_count=len(image.content))
            self.controller.finishImageReceive(token, image=image, label=label, instruction=instruction)
        except ValueError as exc:
            self._diagnostic('promise_image_invalid', error_class=type(exc).__name__)
            self.controller.finishImageReceive(token, error=str(exc))

    def _promise_error(self, token, message):
        if self.controller.isImageReceiveCurrent(token):
            self._diagnostic('promise_failed')
            self.controller.finishImageReceive(token, error=message)

    def _diagnostic(self, stage, **values):
        # One bounded, local receipt. Never include URLs, paths, text or bytes.
        self.receipt.update(stage=stage, **values)
        if self.diagnostic_file is None:
            return
        temporary = None
        try:
            self.diagnostic_file.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', dir=self.diagnostic_file.parent,
                    prefix='.image-drop-', delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(self.receipt, stream, ensure_ascii=False)
            temporary.replace(self.diagnostic_file)
        except OSError:
            logger.debug('image_drop_diagnostic_unavailable')
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def close(self):
        self.promises.close()
