"""One bounded, memory-only thumbnail for explicit image input; never persisted."""
import threading
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage
from PyQt6.QtQuick import QQuickImageProvider


class ImagePreviewProvider(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._lock = threading.RLock()
        self._image, self._id, self._content = QImage(), '', b''

    def set_input(self, source):
        image = QImage.fromData(source.content)
        thumbnail = image.scaled(640, 360, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
        with self._lock:
            self._image, self._id, self._content = thumbnail, source.input_id, source.content
        return 'image://mini-input/' + source.input_id

    def clear(self):
        with self._lock:
            self._image, self._id, self._content = QImage(), '', b''

    def requestImage(self, image_id, requestedSize):
        with self._lock:
            image = QImage(self._image) if image_id == self._id else QImage()
            content = self._content if image_id == self._id+'/full' else None
        if content:
            image = QImage.fromData(content).scaled(1600,2400,Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
        return image, image.size()
