"""Unit tests for RAT image drop & clipboard ingress (Roadmap step 2.4)."""
from pathlib import Path
import pytest
from PyQt6.QtCore import QMimeData, QUrl
from PyQt6.QtGui import QGuiApplication, QImage

from rat.kernel.input_context import ImageInput
from rat.ui.image_input import (
    encode_image,
    image_from_bytes,
    image_from_mime,
    image_from_url,
    parse_pasted_mime_content,
)
from rat.ui.image_preview import ImagePreviewProvider
from rat.ui.quick_pdf_controller import QuickPDFController


@pytest.fixture(scope="session")
def qapp():
    return QGuiApplication.instance() or QGuiApplication([])


def test_encode_and_read_image(tmp_path, qapp):
    img = QImage(64, 64, QImage.Format.Format_RGB32)
    img.fill(0xFF0000)
    img_input = encode_image(img, origin="dropped_image")
    assert isinstance(img_input, ImageInput)
    assert img_input.origin == "dropped_image"
    assert len(img_input.content) > 0
    assert img_input.content_sha256

    # From bytes
    from_b = image_from_bytes(img_input.content, origin="clipboard_image")
    assert from_b.origin == "clipboard_image"
    assert from_b.content_sha256 == img_input.content_sha256

    # From URL / file
    file_path = tmp_path / "test_sample.png"
    assert img.save(str(file_path), "PNG")
    from_url, name = image_from_url(QUrl.fromLocalFile(str(file_path)))
    assert name == "test_sample.png"
    assert from_url.origin == "dropped_file"
    assert from_url.source_file_sha256


def test_image_from_mime(tmp_path, qapp):
    img = QImage(32, 32, QImage.Format.Format_RGB32)
    img.fill(0x00FF00)
    mime = QMimeData()
    mime.setImageData(img)

    inp, label = image_from_mime(mime, clipboard=True)
    assert inp.origin == "clipboard_image"
    assert label == "Ảnh vừa dán"

    parsed = parse_pasted_mime_content(mime)
    assert parsed["kind"] == "image"
    assert parsed["image"].origin == "clipboard_image"


def test_image_preview_provider(qapp):
    img = QImage(40, 40, QImage.Format.Format_RGB32)
    img.fill(0x0000FF)
    inp = encode_image(img)

    provider = ImagePreviewProvider()
    url = provider.set_input(inp)
    assert url.startswith("image://input-preview/img-")

    retrieved, size = provider.requestImage(inp.input_id, None)
    assert not retrieved.isNull()
    assert size.width() > 0


def test_controller_image_drop_handling(tmp_path, monkeypatch, qapp):
    controller = QuickPDFController()
    assert not controller.snapshot["dropActive"]

    controller.setDropActive(True)
    assert controller.snapshot["dropActive"]

    controller.setDropActive(False)
    assert not controller.snapshot["dropActive"]

    # Test acceptDroppedImageUrl
    img = QImage(30, 30, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFF)
    path = tmp_path / "diagram.png"
    img.save(str(path), "PNG")

    captured_jobs = []

    def fake_capture_text(mode, image_input=None, **kwargs):
        captured_jobs.append((mode, image_input))
        return {"text": "Hello world from image OCR"}

    monkeypatch.setattr("rat.engine.snippet_translation.capture_text", fake_capture_text)

    # Mock translate
    translated_texts = []
    fake_translator = type("FakeTranslator", (), {
        "translate": lambda self, text, source="auto", target="vi": {
            "text": "Xin chào thế giới từ ảnh",
            "source_lang": "en",
            "engine": "offline",
        }
    })()
    monkeypatch.setattr(controller, "_get_translator", lambda: fake_translator)

    accepted = controller.acceptDroppedImageUrl(str(path))
    assert accepted

    # Check that worker started
    import time
    for _ in range(20):
        if captured_jobs:
            break
        time.sleep(0.05)

    assert len(captured_jobs) == 1
    mode, img_inp = captured_jobs[0]
    assert mode == "image"
    assert isinstance(img_inp, ImageInput)

    controller.close()
