"""Bounded UI image ingress. OCR/translation remain reasoning tools."""
from pathlib import Path
from dataclasses import replace
import hashlib
import sys

from PyQt6.QtCore import QByteArray, QBuffer, QIODevice, QUrl
from PyQt6.QtGui import QImage, QImageReader, QPixmap
from rat.kernel.input_context import ImageInput, MAX_IMAGE_BYTES, MAX_IMAGE_PIXELS

MAX_BYTES = MAX_IMAGE_BYTES
MAX_PIXELS = MAX_IMAGE_PIXELS
IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff'}


def encode_image(image, origin='clipboard_image'):
    if image.isNull() or image.width() * image.height() > MAX_PIXELS:
        raise ValueError('Ảnh trống hoặc quá lớn. Hãy chụp vùng chữ nhỏ hơn.')
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    saved = image.save(buffer, 'PNG')
    buffer.close()
    if not saved or data.size() > MAX_BYTES:
        raise ValueError('Ảnh vượt giới hạn 12 MB. Hãy chụp vùng chữ nhỏ hơn.')
    return ImageInput(bytes(data), origin)


def image_from_bytes(raw, origin='dropped_image'):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES:
        raise ValueError('Ảnh trống hoặc vượt giới hạn 12 MB. Hãy chụp vùng chữ nhỏ hơn.')
    data = QByteArray(raw)
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer)
    reader.setDecideFormatFromContent(True)
    reader.setAutoTransform(True)
    size = reader.size()
    if not size.isValid() or size.width() * size.height() > MAX_PIXELS:
        raise ValueError('Ảnh không hợp lệ hoặc quá lớn. Hãy chụp vùng chữ nhỏ hơn.')
    image = reader.read()
    buffer.close()
    return encode_image(image, origin)


def image_from_url(value, origin='dropped_file'):
    # A QVariantList from Qt can contain QUrl, not just its string form.
    url = QUrl(value) if isinstance(value, QUrl) else QUrl(str(value))
    if not url.isLocalFile() or url.host() not in ('', 'localhost'):
        if url.scheme() in ('http', 'https'):
            raise ValueError('Hãy thả dữ liệu ảnh hoặc file ảnh, không phải đường dẫn web.')
        raise ValueError('Chưa lấy được ảnh từ dữ liệu kéo thả. Hãy chờ ảnh lưu rồi thả lại file PNG.')
    path = Path(url.toLocalFile())
    if sys.platform == 'darwin' and str(path).startswith('/.file/id='):
        from Foundation import NSURL
        native = NSURL.URLWithString_(url.toString())
        resolved = native.filePathURL() if native is not None else None
        if resolved is None or not resolved.path():
            raise ValueError('macOS chưa chuyển xong file ảnh. Hãy chờ ảnh lưu rồi thả lại.')
        path = Path(str(resolved.path()))
    if path.suffix.lower() not in IMAGE_SUFFIXES:
        raise ValueError('Hãy thả ảnh PNG, JPG, WebP, BMP hoặc TIFF vào RAT.')
    try:
        if not path.is_file():
            raise ValueError('Chưa đọc được file ảnh. Hãy thả ảnh đã lưu từ Desktop hoặc Finder.')
        with path.open('rb') as source:
            raw = source.read(MAX_BYTES + 1)
    except OSError as exc:
        raise ValueError('Không đọc được ảnh. Hãy kiểm tra file và quyền truy cập.') from exc
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError('Ảnh trống hoặc vượt giới hạn 12 MB. Hãy chụp vùng chữ nhỏ hơn.')
    return replace(image_from_bytes(raw, origin), source_file_sha256=hashlib.sha256(raw).hexdigest()), path.name


ENCODED_IMAGE_TYPES = ('image/png', 'image/tiff', 'image/jpeg', 'image/webp', 'image/bmp',
    'public.png', 'public.tiff', 'public.jpeg')


def image_from_mime(mime, *, clipboard=False):
    """Snapshot a user-initiated drop/paste before its QMimeData expires."""
    urls = list(mime.urls()) if mime.hasUrls() else []
    if len(urls) > 1:
        raise ValueError('Hãy thả từng ảnh một để RAT dịch.')
    errors = []
    if urls:
        try:
            return image_from_url(urls[0], 'clipboard_file' if clipboard else 'dropped_file')
        except ValueError as exc:
            if str(exc).startswith('Hãy thả ảnh PNG'):
                raise  # Do not OCR a file icon as if it were the document image.
            errors.append(exc)
    origin = 'clipboard_image' if clipboard else 'dropped_image'
    if mime.hasImage():
        image = mime.imageData()
        if isinstance(image, QPixmap):
            image = image.toImage()
        if isinstance(image, QImage):
            return encode_image(image, origin), 'Ảnh vừa dán' if clipboard else 'Ảnh vừa thả'
    for kind in ENCODED_IMAGE_TYPES:
        if mime.hasFormat(kind):
            raw = bytes(mime.data(kind))
            if raw:
                try:
                    return image_from_bytes(raw, origin), 'Ảnh vừa dán' if clipboard else 'Ảnh vừa thả'
                except ValueError as exc:
                    errors.append(exc)
    if errors:
        raise errors[-1]
    raise ValueError('Chưa nhận được dữ liệu ảnh. Hãy chờ ảnh lưu rồi thả file PNG vào RAT.')
