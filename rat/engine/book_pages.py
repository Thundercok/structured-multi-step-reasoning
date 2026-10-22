"""On-demand PDF page text, independent of Qt, indexing and model inference."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import re
import unicodedata


class BookPageError(ValueError):
    """Expected page-read failure with a stable, non-sensitive code."""

    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def normalized(text: str) -> str:
    text = unicodedata.normalize("NFD", text.casefold())
    return "".join(c for c in text if unicodedata.category(c) != "Mn").replace("đ", "d")


@contextmanager
def open_pdf(path: Path):
    from pypdf import PdfReader

    with path.open("rb") as stream:
        reader = PdfReader(stream)
        if reader.is_encrypted and not reader.decrypt(""):
            raise BookPageError("encrypted_pdf", "PDF có mật khẩu; cần bản đã mở khóa để đọc nội dung.")
        yield reader


def check_cancel(context):
    callback = context.get("should_cancel")
    if callable(callback) and callback():
        raise ValueError("cancelled:execution_cancelled")


def page_metadata(path, reader, page, label):
    return {"path": str(path), "filename": path.name, "page": page,
            "page_label": label, "page_count": len(reader.pages),
            "page_numbering": "pdf_1_based", "extraction": "pdf_text"}


def search_pages(path, query, *, start_page=1, max_pages=400, limit=5, context=None):
    context = context or {}
    query_words = re.findall(r"[^\W_]+", normalized(query))
    terms = list(dict.fromkeys(query_words))
    if not terms:
        raise ValueError("Hãy nhập từ hoặc cụm từ cần tìm trong sách.")
    with open_pdf(path) as reader:
        count = len(reader.pages)
        if not 1 <= start_page <= count:
            raise BookPageError("invalid_page", f"Trang bắt đầu phải nằm trong khoảng 1–{count}.")
        end = min(count, start_page + max_pages - 1)
        labels = reader.page_labels
        matches, textless, failures = [], [], []
        for index in range(start_page - 1, end):
            check_cancel(context)
            try:
                text = reader.pages[index].extract_text() or ""
            except Exception as exc:
                failures.append({"page": index + 1, "error": str(exc)[:200]})
                continue
            words = [(normalized(m.group()), m.start(), m.end())
                     for m in re.finditer(r"[^\W_]+", unicodedata.normalize("NFC", text))]
            if not words:
                textless.append(index + 1)
                continue
            present = {word for word, _, _ in words}
            if not set(terms) <= present:
                continue
            # Offsets and snippets refer to this exact extracted text, never model prose.
            text = unicodedata.normalize("NFC", text)
            anchor = next(start for word, start, _ in words if word in terms)
            left, right = max(0, anchor - 100), min(len(text), anchor + 500)
            snippet = text[left:right]
            phrase = (" " + " ".join(query_words) + " ") in (" " + " ".join(word for word, _, _ in words) + " ")
            occurrences = sum(word in terms for word, _, _ in words)
            matches.append({**page_metadata(path, reader, index + 1, labels[index]),
                            "snippet": snippet, "snippet_start": left,
                            "matched_terms": terms, "phrase_match": phrase,
                            "occurrences": occurrences})
        matches.sort(key=lambda item: (not item["phrase_match"], -item["occurrences"], item["page"]))
        return {"title": f"Trang sách · {path.name} · {query}",
                "query": query, "path": str(path), "filename": path.name,
                "items": matches[:limit], "matched_pages": len(matches),
                "results_truncated": len(matches) > limit, "page_count": count,
                "searched_range": [start_page, end], "pages_examined": end - start_page + 1,
                "next_start_page": end + 1 if end < count else None,
                "textless_pages": textless, "unreadable_pages": failures,
                "search_mode": "all_query_words_accent_insensitive",
                "notice": "Số trang tính từ 1 trong tệp PDF. Nhãn trang do PDF khai báo, có thể khác số in trên sách. "
                          "Các trang không có văn bản trích xuất cần OCR để tìm nội dung."}


def read_page(path, page, *, max_chars=8000, context=None):
    check_cancel(context or {})
    with open_pdf(path) as reader:
        count = len(reader.pages)
        if not 1 <= page <= count:
            raise BookPageError("invalid_page", f"Trang phải nằm trong khoảng 1–{count}.")
        text = (reader.pages[page - 1].extract_text() or "").strip()
        check_cancel(context or {})
        if not text:
            raise BookPageError("no_text_page", "Trang này không có văn bản trích xuất; có thể là trang trắng hoặc scan/ảnh. OCR chưa chạy.")
        content = text[:max_chars]
        metadata = page_metadata(path, reader, page, reader.page_labels[page - 1])
        return {**metadata, "title": f"{path.name} · Trang PDF {page}",
                "found": True, "content": content,
                "total_chars": len(text), "truncated": len(text) > max_chars,
                "citation": {**metadata, "snippet": content[:500]},
                "notice": "Văn bản trích xuất từ trang PDF; nhãn PDF không xác nhận số trang in trên sách."}
