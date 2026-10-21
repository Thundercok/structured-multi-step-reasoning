"""Authored PDF/image fixtures and OCR doubles; no OCR quality measurements."""
import builtins
import subprocess
import sys
from types import SimpleNamespace as NS

import pytest
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from document_intake.pdf import PDFReadError, read_pdf
from document_intake.tesseract import TesseractOCREngine


def text_pdf(path, texts=("Short", "Second page"), password=None, algorithm=None):
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(100, 100)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                 NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({
            NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 5 50 Td ({text}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    writer.add_metadata({"/Title": "Fixture title"})
    if password is not None:
        if algorithm is None:
            writer.encrypt(password)
        else:
            writer.encrypt(password, algorithm=algorithm)
    writer.write(path)


@pytest.mark.parametrize("data", [b"", b"not a PDF", b"%PDF-1.7\ntruncated"])
def test_bad_pdf_has_stable_failure_and_rat_returns_empty(tmp_path, monkeypatch, data):
    from rat.crawler import extractors
    monkeypatch.setattr(extractors.platform, "system", lambda: "Linux")
    path = tmp_path / "bad.pdf"
    path.write_bytes(data)
    with pytest.raises(PDFReadError, match="invalid_pdf") as caught:
        read_pdf(path)
    assert caught.value.code == "invalid_pdf"
    assert extractors.extract_text_from_pdf(str(path)) == ""


def test_missing_input_and_missing_engine_are_distinct(tmp_path, monkeypatch):
    with pytest.raises(PDFReadError, match="file_not_found"):
        read_pdf(tmp_path / "missing.pdf")
    monkeypatch.setitem(sys.modules, "pypdf", None)
    with pytest.raises(PDFReadError, match="pdf_engine_unavailable"):
        read_pdf(tmp_path / "missing.pdf")


def test_missing_pdf_crypto_dependency_is_not_mislabeled_as_corruption(tmp_path, monkeypatch):
    import pypdf
    from pypdf.errors import DependencyError
    path = tmp_path / "encrypted.pdf"
    path.touch()
    def unavailable(*args, **kwargs):
        raise DependencyError("fixture: optional crypto is unavailable")
    monkeypatch.setattr(pypdf, "PdfReader", unavailable)
    with pytest.raises(PDFReadError, match="pdf_engine_unavailable"):
        read_pdf(path)


@pytest.mark.parametrize("algorithm", [None, "AES-256"])
def test_encrypted_pdf_requires_correct_password(tmp_path, monkeypatch, algorithm):
    from rat.crawler import extractors
    monkeypatch.setattr(extractors.platform, "system", lambda: "Linux")
    path = tmp_path / "locked.pdf"
    if algorithm is not None:
        pytest.importorskip("cryptography")
    text_pdf(path, password="fixture-password", algorithm=algorithm)
    for password in (None, "wrong-password"):
        with pytest.raises(PDFReadError, match="^encrypted_pdf$"):
            read_pdf(path, password=password)
    assert read_pdf(path, password="fixture-password")["full_text"] == "Short\nSecond page"
    assert extractors.extract_text_from_pdf(str(path)) == ""


def test_empty_password_pdf_is_readable(tmp_path):
    path = tmp_path / "empty-password.pdf"
    text_pdf(path, password="")
    assert read_pdf(path)["status"] == "ok"


def test_zero_pages_blank_pages_and_scanned_pdf_are_not_text(tmp_path, monkeypatch):
    from rat.crawler import extractors
    from document_intake import vision
    monkeypatch.setattr(extractors.platform, "system", lambda: "Linux")
    monkeypatch.setattr(vision, "recognize_tokens", lambda *_: pytest.fail("digital read invoked OCR"))
    zero = tmp_path / "zero-pages.pdf"
    text_pdf(zero, texts=())
    assert read_pdf(zero)["status"] == "empty"
    blank = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(100, 100)
    writer.add_metadata({"/Title": "Not body text"})
    writer.write(blank)
    scanned = tmp_path / "scanned.pdf"
    Image.new("RGB", (100, 100), color="white").save(scanned, "PDF")
    for path in (zero, blank, scanned):
        result = read_pdf(path)
        assert not result["full_text"].strip()
        assert result["status"] == ("empty" if path == zero else "no_text")
        assert extractors.extract_text_from_pdf(str(path)) == ""


@pytest.mark.parametrize("limit", [0, 1, 5, 6, 7, 16, 17, 100])
def test_character_limit_is_hard_and_includes_page_separators(tmp_path, limit):
    path = tmp_path / "digital.pdf"
    text_pdf(path)
    result = read_pdf(path, max_chars=limit)
    expected = "Short\nSecond page"
    assert result["full_text"] == expected[:limit]
    assert result["extraction_truncated"] == (limit < len(expected))
    assert result["full_text"] == "\n".join(p["text_content"] for p in result["pages"])


@pytest.mark.parametrize("limits", [{"max_pages": -1}, {"max_chars": True}, {"max_pages": 1.5}])
def test_invalid_limits_fail_before_open(limits):
    with pytest.raises(ValueError, match="nonnegative integer"):
        read_pdf("not-opened.pdf", **limits)


def native_pdf(monkeypatch, pages, *, attributes=None, locked=False):
    from document_intake import pdf
    doc = NS(documentAttributes=lambda: attributes or {}, pageCount=lambda: len(pages),
             pageAtIndex_=lambda i: pages[i], isLocked=lambda: locked,
             unlockWithPassword_=lambda _: False)
    cls = NS(alloc=lambda: NS(initWithURL_=lambda _: doc))
    monkeypatch.setitem(sys.modules, "objc", NS(loadBundle=lambda *a, **k: None, lookUpClass=lambda _: cls))
    monkeypatch.setitem(sys.modules, "Foundation", NS(NSURL=NS(fileURLWithPath_=lambda p: p), NSSize=lambda *a: a))
    monkeypatch.setattr(pdf.os.path, "exists", lambda _: True)
    return pdf


def test_short_native_digital_text_is_not_lost_or_sent_to_ocr(monkeypatch):
    page = NS(string=lambda: "42", thumbnailOfSize_forBox_=lambda *_: pytest.fail("unexpected OCR"))
    pdf = native_pdf(monkeypatch, [page])
    assert pdf.read_pdf_native("fixture.pdf") == "--- Page 1 ---\n42"
    assert pdf.read_pdf_native("fixture.pdf", max_chars=5) == "--- P"


def test_native_empty_metadata_and_locked_documents_return_no_content(monkeypatch):
    from document_intake import vision
    monkeypatch.setattr(vision, "recognize_tokens", lambda _: [])
    page = NS(string=lambda: "", thumbnailOfSize_forBox_=lambda *_: None)
    pdf = native_pdf(monkeypatch, [page], attributes={"Title": "Not body text"})
    assert pdf.read_pdf_native("fixture.pdf") == ""
    native_pdf(monkeypatch, [page], locked=True)
    assert pdf.read_pdf_native("fixture.pdf") is None


def test_native_zero_limit_does_not_render(monkeypatch):
    page = NS(string=lambda: pytest.fail("page accessed despite zero limit"))
    pdf = native_pdf(monkeypatch, [page])
    assert pdf.read_pdf_native("fixture.pdf", max_chars=0) == ""
    assert pdf.read_pdf_native("fixture.pdf", max_pages=0) == ""


@pytest.mark.parametrize("failure", [FileNotFoundError(), subprocess.TimeoutExpired("fixture", 2)])
def test_ocr_missing_engine_or_timeout_does_not_retry(tmp_path, monkeypatch, failure):
    from document_intake import tesseract
    path = tmp_path / "image.png"
    Image.new("RGB", (10, 10)).save(path)
    calls = []
    def run(*args, **kwargs):
        calls.append(args)
        raise failure
    monkeypatch.setattr(tesseract.subprocess, "run", run)
    assert TesseractOCREngine(timeout=2).run_ocr(str(path)) == {"full_text": "", "lines": [], "tokens": []}
    assert len(calls) == 1


def test_ocr_fallback_uses_remaining_budget(tmp_path, monkeypatch):
    from document_intake import tesseract
    path = tmp_path / "image.png"
    path.touch()
    clock = iter([10, 10.5])
    monkeypatch.setattr(tesseract.time, "monotonic", lambda: next(clock))
    calls = []
    def run(*args, **kwargs):
        calls.append(kwargs)
        return NS(returncode=1, stdout="") if len(calls) == 1 else NS(returncode=0, stdout="Fallback")
    monkeypatch.setattr(tesseract.subprocess, "run", run)
    assert TesseractOCREngine(timeout=2).run_ocr(str(path))["full_text"] == "Fallback"
    assert [call["timeout"] for call in calls] == [2, 1.5]


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), True])
def test_ocr_rejects_invalid_timeout(timeout):
    with pytest.raises(ValueError, match="positive and finite"):
        TesseractOCREngine(timeout=timeout)


def test_ocr_skips_malformed_tsv_and_impossible_boxes():
    header = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
    rows = ["5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t90\tValid"]
    for confidence in ("nan", "inf", "101", "-1", "nonsense"):
        rows.append(f"5\t1\t1\t1\t1\t1\t0\t0\t10\t10\t{confidence}\tInvalid")
    rows += ["5\t1\t1\t1\t1\t1\t-1\t0\t10\t10\t90\tNegative",
             "5\t1\t1\t1\t1\t1\t0\t0\t0\t10\t90\tZero", "broken"]
    tokens = TesseractOCREngine()._parse_tsv_output(header + "\n".join(rows))
    assert [token["text"] for token in tokens] == ["Valid"]


def test_vision_false_error_tuple_is_failure(tmp_path, monkeypatch):
    from document_intake import vision
    path = tmp_path / "image.png"
    Image.new("RGB", (10, 10)).save(path)
    request = NS(setRecognitionLevel_=lambda _: None, setUsesLanguageCorrection_=lambda _: None,
                 setRecognitionLanguages_=lambda _: None, results=lambda: pytest.fail("failed OCR results consumed"))
    req_cls = NS(alloc=lambda: NS(init=lambda: request))
    handler = NS(performRequests_error_=lambda *_: (False, "fixture error"))
    handler_cls = NS(alloc=lambda: NS(initWithURL_options_=lambda *_: handler))
    monkeypatch.setattr(vision.platform, "system", lambda: "Darwin")
    monkeypatch.setitem(sys.modules, "objc", NS(loadBundle=lambda *a, **k: None,
                        lookUpClass=lambda n: req_cls if n == "VNRecognizeTextRequest" else handler_cls))
    monkeypatch.setitem(sys.modules, "Foundation", NS(NSURL=NS(fileURLWithPath_=lambda p: p)))
    assert vision.recognize_tokens(path) == []


def test_vision_bad_image_and_non_mac_are_empty(tmp_path, monkeypatch):
    from document_intake import vision
    path = tmp_path / "broken.png"
    path.write_bytes(b"not an image")
    monkeypatch.setattr(vision.platform, "system", lambda: "Linux")
    assert vision.recognize_tokens(path) == []
    assert vision.recognize_tokens(b"") == []


def test_corrupt_image_is_rejected_before_native_ocr_import(tmp_path, monkeypatch):
    from document_intake import vision
    path = tmp_path / "broken.png"
    path.write_bytes(b"not an image")
    monkeypatch.setattr(vision.platform, "system", lambda: "Darwin")
    original = builtins.__import__
    def import_module(name, *args, **kwargs):
        if name in ("objc", "Foundation"):
            pytest.fail("corrupt image reached native OCR initialization")
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", import_module)
    assert vision.recognize_tokens(path) == []


def test_ocr_errors_do_not_become_document_text(tmp_path, monkeypatch):
    from document_intake import tesseract
    path = tmp_path / "bad.png"
    path.write_bytes(b"corrupt image")
    calls = []
    def run(*args, **kwargs):
        calls.append(args)
        return NS(returncode=1, stdout="engine/language-data failure")
    monkeypatch.setattr(tesseract.subprocess, "run", run)
    assert TesseractOCREngine().run_ocr(str(path)) == {"full_text": "", "lines": [], "tokens": []}
    assert len(calls) == 2


def test_rat_pdf_output_limit_includes_metadata_and_markers(tmp_path, monkeypatch):
    from rat.crawler import extractors
    path = tmp_path / "digital.pdf"
    text_pdf(path)
    monkeypatch.setattr(extractors.platform, "system", lambda: "Linux")
    monkeypatch.setattr(extractors, "MAX_CHARS_PER_DOC", 10)
    assert len(extractors.extract_text_from_pdf(str(path))) == 10
