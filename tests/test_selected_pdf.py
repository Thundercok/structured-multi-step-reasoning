"""Real authored PDFs, deterministic text search/citations; no model-quality claims."""
from pathlib import Path
import subprocess
import sys

import pytest
from pypdf import PdfWriter
from pypdf.constants import PageLabelStyle
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from rat.engine.selected_pdf import (
    SelectedPDFError, citation_text, read_selected_page, search_selected_pdf, select_pdf,
)


def write_pdf(path, texts, password=None):
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(612, 792)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream.set_data(f"BT /F1 12 Tf 40 750 Td ({escaped}) Tj ET".encode("latin-1"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    if texts:
        writer.set_page_label(0, len(texts) - 1, style=PageLabelStyle.DECIMAL, prefix="Book-", start=1)
    if password is not None:
        writer.encrypt(password)
    writer.write(path)
    return path


@pytest.fixture
def pdf(tmp_path):
    texts = ["Introduction"] * 30
    texts[0] = ""
    texts[1] = "Binary search halves a sorted array."
    texts[28] = "Thuat toan tim kiem. Binary search uses a loop."
    texts[29] = "Binary search uses log n comparisons. Binary search is fast."
    return write_pdf(tmp_path / "Tài liệu #1.pdf", texts), texts


def test_selected_unindexed_pdf_searches_and_reads_actual_late_page(pdf):
    path, texts = pdf
    selected = select_pdf(path)
    found = search_selected_pdf(selected, "binary search")
    assert selected.page_count == 30
    assert [x["page"] for x in found["items"]] == [30, 2, 29]
    assert found["searched_range"] == [1, 30]
    assert found["textless_pages"] == [1]
    read = read_selected_page(selected, 30)
    assert read["content"] == texts[29] and read["page_label"] == "Book-30"
    quoted = citation_text(selected, read, "log n comparisons")
    assert quoted.startswith("log n comparisons\n\n")
    assert "trang PDF 30" in quoted and "Book-30" in quoted and str(path) in quoted


def test_accent_matching_and_no_matches_are_not_claims_about_unsearched_pages(pdf):
    selected = select_pdf(pdf[0])
    assert [x["page"] for x in search_selected_pdf(selected, "THUẬT TOÁN")["items"]] == [29]
    result = search_selected_pdf(selected, "binary", max_pages=2)
    assert result["searched_range"] == [1, 2] and result["next_start_page"] == 3
    assert result["matched_pages"] == 1
    result = search_selected_pdf(selected, "notpresent", max_pages=2)
    assert result["items"] == [] and result["next_start_page"] == 3


@pytest.mark.parametrize("query", ["", "  ", "---", "___"])
def test_empty_or_punctuation_query_is_a_request_error(pdf, query):
    with pytest.raises(SelectedPDFError, match="empty_query"):
        search_selected_pdf(select_pdf(pdf[0]), query)


@pytest.mark.parametrize("page", [0, 31, True])
def test_invalid_page_never_returns_content(pdf, page):
    with pytest.raises(SelectedPDFError, match="invalid_page"):
        read_selected_page(select_pdf(pdf[0]), page)


def test_cancellation_and_changed_file_never_publish_new_content(pdf):
    selected = select_pdf(pdf[0])
    checks = []
    def cancel():
        checks.append(1)
        return len(checks) > 3
    with pytest.raises(InterruptedError):
        search_selected_pdf(selected, "binary", should_cancel=cancel)
    read = read_selected_page(selected, 30)
    pdf[0].write_bytes(pdf[0].read_bytes() + b"\n% changed\n")
    for action in (lambda: search_selected_pdf(selected, "binary"), lambda: read_selected_page(selected, 30), lambda: citation_text(selected, read)):
        with pytest.raises(SelectedPDFError, match="pdf_changed"):
            action()


def test_forged_citation_is_rejected_and_paragraph_selection_is_exact(pdf):
    selected = select_pdf(pdf[0])
    read = read_selected_page(selected, 30)
    with pytest.raises(SelectedPDFError, match="invalid_citation"):
        citation_text(selected, read, "The model invented this.")
    with pytest.raises(SelectedPDFError, match="invalid_citation"):
        citation_text(selected, {**read, "path": "/different.pdf"})
    assert citation_text(selected, read).startswith(read["citation"]["snippet"])


def test_expected_pdf_failures_are_distinct(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not PDF")
    empty = write_pdf(tmp_path / "empty.pdf", [])
    locked = write_pdf(tmp_path / "locked.pdf", ["Text"], password="fixture-password")
    for path, code in ((bad, "invalid_pdf"), (empty, "empty_pdf"), (locked, "encrypted_pdf"), (tmp_path / "missing.pdf", "file_not_found")):
        with pytest.raises(SelectedPDFError, match=code):
            select_pdf(path)
    blank = write_pdf(tmp_path / "blank.pdf", [""])
    selected = select_pdf(blank)
    assert search_selected_pdf(selected, "text")["textless_pages"] == [1]
    with pytest.raises(SelectedPDFError, match="no_text_page"):
        read_selected_page(selected, 1)


def test_scanned_pdf_is_not_mislabeled_as_corrupt_or_as_digital_text(tmp_path):
    from PIL import Image
    path = tmp_path / "image-only.pdf"
    Image.new("RGB", (80, 80), color="white").save(path, "PDF")
    selected = select_pdf(path)
    assert search_selected_pdf(selected, "text")["items"] == []
    with pytest.raises(SelectedPDFError, match="no_text_page"):
        read_selected_page(selected, 1)


def test_import_does_not_load_qt_indexer_or_models():
    code = "import sys; import rat.engine.selected_pdf; assert not any(x in sys.modules for x in ('PyQt6', 'rat.crawler.db', 'rat.engine.meta_reasoner', 'onnxruntime', 'numpy'))"
    run = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
