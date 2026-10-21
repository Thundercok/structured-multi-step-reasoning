"""Shared PDF readers. PDFKit OCR is opt-in; digital reads never invoke OCR."""
import logging
import os
from pathlib import Path
logger = logging.getLogger(__name__)


class PDFReadError(ValueError):
    """Expected intake failure with a stable code; never contains passwords."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _validate_limits(max_pages, max_chars):
    for name, value in (("max_pages", max_pages), ("max_chars", max_chars)):
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError(f"{name} must be a nonnegative integer or None")


def read_pdf(path, *, max_pages=None, max_chars=None, password=None):
    """Read digital text only, with hard limits and explicit input failures.

    ``status`` distinguishes zero-page documents (empty), pages without digital
    text (no_text), and extracted text (ok). Blank and scanned pages both have
    no_text status: absence of digital text does not establish that OCR is needed.
    ``max_chars`` includes the newlines between returned pages, not metadata.
    """
    _validate_limits(max_pages, max_chars)
    try:
        from pypdf import PdfReader
        from pypdf.errors import DependencyError
    except ImportError as exc:
        raise PDFReadError("pdf_engine_unavailable") from exc
    try:
        with open(path, "rb") as stream:
            reader = PdfReader(stream)
            if reader.is_encrypted and not reader.decrypt(password or ""):
                raise PDFReadError("encrypted_pdf")
            total_pages = len(reader.pages)
            pages, size, truncated = [], 0, False
            for i in range(total_pages):
                if ((max_pages is not None and i >= max_pages)
                        or (max_chars is not None and size >= max_chars)):
                    truncated = True
                    break
                text = reader.pages[i].extract_text() or ""
                separator_size = int(bool(pages))
                if max_chars is not None:
                    remaining = max_chars - size - separator_size
                    if remaining < 0:
                        truncated = True
                        break
                    if len(text) > remaining:
                        text = text[:remaining]
                        truncated = True
                pages.append({"page_num": i + 1, "text_content": text})
                size += separator_size + len(text)
                if truncated:
                    break
            meta = reader.metadata
            metadata = {key: getattr(meta, key, None) for key in ("title", "author", "subject")} if meta else {}
            full_text = "\n".join(p["text_content"] for p in pages)
            return {"filepath": str(path), "total_pages": total_pages, "pages": pages,
                    "full_text": full_text, "metadata": metadata,
                    "extraction_truncated": truncated,
                    "status": "empty" if not total_pages else "ok" if full_text.strip() else "no_text"}
    except PDFReadError:
        raise
    except DependencyError as exc:
        raise PDFReadError("pdf_engine_unavailable") from exc
    except FileNotFoundError as exc:
        raise PDFReadError("file_not_found") from exc
    except OSError as exc:
        raise PDFReadError("file_unreadable") from exc
    except Exception as exc:
        raise PDFReadError("invalid_pdf") from exc


def read_pdf_native(file_path: str, max_pages: int = 25, max_chars: int = 100_000) -> str | None:
    """Extract text and metadata from PDF using macOS native PDFKit + Apple Vision OCR for scanned pages."""
    _validate_limits(max_pages, max_chars)
    if max_pages == 0 or max_chars == 0:
        return ""
    try:
        import objc
        from Foundation import NSURL, NSSize

        framework_path = "/System/Library/Frameworks/PDFKit.framework"
        if not os.path.exists(framework_path):
            return None

        objc.loadBundle("PDFKit", globals(), bundle_path=framework_path)
        PDFDocument = objc.lookUpClass("PDFDocument")
        if not PDFDocument:
            return None

        file_url = NSURL.fileURLWithPath_(str(Path(file_path).resolve()))
        pdf_doc = PDFDocument.alloc().initWithURL_(file_url)
        if not pdf_doc:
            return None
        if hasattr(pdf_doc, "isLocked") and pdf_doc.isLocked():
            if not pdf_doc.unlockWithPassword_(""):
                return None

        texts, metadata = [], []
        # Metadata
        attr = pdf_doc.documentAttributes()
        if attr:
            title = attr.get("Title")
            author = attr.get("Author")
            subject = attr.get("Subject")
            if title:
                metadata.append(f"Title: {title}")
            if author:
                metadata.append(f"Author: {author}")
            if subject:
                metadata.append(f"Subject: {subject}")

        page_count = pdf_doc.pageCount() if max_pages is None else min(pdf_doc.pageCount(), max_pages)

        for idx in range(page_count):
            page = pdf_doc.pageAtIndex_(idx)
            if not page:
                continue

            page_str = page.string()
            if page_str and page_str.strip():
                texts.append(f"--- Page {idx + 1} ---\n{page_str.strip()}")
            else:
                # Scanned / Image page: render high-res thumbnail & run Apple Vision OCR
                try:
                    ns_image = page.thumbnailOfSize_forBox_(NSSize(2000, 2600), 0)
                    if ns_image:
                        tiff_data = ns_image.TIFFRepresentation()
                        if tiff_data:
                            from .vision import recognize_tokens
                            tokens = recognize_tokens(bytes(tiff_data))
                            if tokens:
                                texts.append(f"--- Page {idx + 1} (Scanned OCR) ---\n" + "\n".join(t["text"] for t in tokens))
                except Exception as e:
                    logger.debug(f"Failed to OCR scanned PDF page {idx+1} in {file_path}: {e}")

            if max_chars is not None and sum(len(t) for t in metadata + texts) >= max_chars:
                break

        # Metadata alone must not mask empty content or prevent digital fallback.
        return "\n\n".join(metadata + texts)[:max_chars] if texts else ""
    except Exception as e:
        logger.debug(f"Native PDFKit extraction failed for {file_path}: {e}")
        return None


