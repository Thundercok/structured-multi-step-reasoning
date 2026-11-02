"""Explicitly selected PDF operations, shared page readers, no index or model.

The selection is a transient reference granted by the user's file choice. Its
stat stamp detects ordinary replacement/modification; it is not a content hash
or a durable artifact revision.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from document_intake.pdf import PDFReadError, read_pdf
from rat.engine.book_pages import BookPageError, read_page, search_pages


class SelectedPDFError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class SelectedPDF:
    path: Path
    page_count: int
    stamp: tuple[int, int, int, int]


def _stamp(path):
    try:
        info = path.stat()
    except FileNotFoundError as exc:
        raise SelectedPDFError("file_not_found") from exc
    except OSError as exc:
        raise SelectedPDFError("file_unreadable") from exc
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def check_current(selection):
    if _stamp(selection.path) != selection.stamp:
        raise SelectedPDFError("pdf_changed")


def _cancel(callback):
    if callback and callback():
        raise InterruptedError("pdf_cancelled")


def select_pdf(path, *, should_cancel=None):
    _cancel(should_cancel)
    try:
        path = Path(path).expanduser().resolve(strict=True)
    except FileNotFoundError as exc:
        raise SelectedPDFError("file_not_found") from exc
    except (OSError, RuntimeError) as exc:
        raise SelectedPDFError("file_unreadable") from exc
    if path.suffix.casefold() != ".pdf" or not path.is_file():
        raise SelectedPDFError("not_pdf")
    before = _stamp(path)
    if before[2] > 64 * 1024 * 1024:
        raise SelectedPDFError("pdf_too_large")
    try:
        # Inspect metadata/page count without extracting body text or invoking OCR.
        data = read_pdf(path, max_pages=0, max_chars=0)
    except PDFReadError as exc:
        raise SelectedPDFError(exc.code) from exc
    _cancel(should_cancel)
    selection = SelectedPDF(path, data["total_pages"], before)
    check_current(selection)
    if not selection.page_count:
        raise SelectedPDFError("empty_pdf")
    return selection


def _run_page_operation(selection, operation, *, should_cancel=None):
    _cancel(should_cancel)
    check_current(selection)
    try:
        result = operation()
    except BookPageError as exc:
        raise SelectedPDFError(exc.code) from exc
    except ValueError as exc:
        if str(exc).startswith("cancelled:"):
            raise InterruptedError("pdf_cancelled") from exc
        raise SelectedPDFError("invalid_pdf") from exc
    except FileNotFoundError as exc:
        raise SelectedPDFError("file_not_found") from exc
    except Exception as exc:
        _cancel(should_cancel)
        raise SelectedPDFError("invalid_pdf") from exc
    _cancel(should_cancel)
    check_current(selection)
    return result


def search_selected_pdf(selection, query, *, start_page=1, max_pages=400, should_cancel=None):
    if not isinstance(query, str) or not re.search(r"[^\W_]", query):
        raise SelectedPDFError("empty_query")
    if type(start_page) is not int or not 1 <= start_page <= selection.page_count:
        raise SelectedPDFError("invalid_page")
    if type(max_pages) is not int or not 1 <= max_pages <= 400:
        raise SelectedPDFError("invalid_page_limit")
    result = _run_page_operation(selection, lambda: search_pages(
        selection.path, query.strip(), start_page=start_page, max_pages=max_pages,
        limit=5, context={"should_cancel": should_cancel}), should_cancel=should_cancel)
    result["notice"] = (
        "Trang tính từ 1 trong tệp PDF; nhãn PDF có thể khác số in trên sách. "
        "Tìm theo từ khóa, không phải trả lời AI. Trang không có văn bản có thể là trang trắng hoặc scan/ảnh; OCR chưa chạy."
    )
    return result


def read_selected_page(selection, page, *, should_cancel=None):
    if type(page) is not int or not 1 <= page <= selection.page_count:
        raise SelectedPDFError("invalid_page")
    return _run_page_operation(selection, lambda: read_page(
        selection.path, page, max_chars=8000,
        context={"should_cancel": should_cancel}), should_cancel=should_cancel)


def selected_source_text(content, selected_text):
    """Map a reading selection back to exact source bytes apart from whitespace.

    Words/punctuation must match. Only display whitespace may differ, and the
    returned quote always contains the original extracted spacing/newlines.
    """
    excerpt = selected_text.replace("\u2029", "\n")
    if excerpt and excerpt in content:
        return excerpt
    parts = excerpt.split()
    if parts:
        match = re.search(r'\s+'.join(re.escape(part) for part in parts), content)
        if match:
            return match.group()
    raise SelectedPDFError("invalid_citation")


def citation_text(selection, page_result, selected_text=""):
    check_current(selection)
    if (page_result.get("path") != str(selection.path)
            or page_result.get("page_numbering") != "pdf_1_based"):
        raise SelectedPDFError("invalid_citation")
    content = page_result.get("content", "")
    excerpt = selected_source_text(content, selected_text) if selected_text else page_result["citation"]["snippet"]
    if not excerpt or excerpt not in content:
        raise SelectedPDFError("invalid_citation")
    page = page_result["page"]
    label = page_result.get("page_label", str(page))
    suffix = f" · nhãn PDF: {label}" if label != str(page) else ""
    return f"{excerpt}\n\n— {selection.path.name}, trang PDF {page}{suffix}\n{selection.path}"
