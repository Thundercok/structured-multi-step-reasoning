"""Shared PDF readers. PDFKit OCR is opt-in; digital reads never invoke OCR."""
import logging
import os
from pathlib import Path
logger = logging.getLogger(__name__)


def read_pdf(path, *, max_pages=None, max_chars=None):
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    pages, size = [], 0
    for i, page in enumerate(reader.pages):
        if max_pages is not None and i >= max_pages:
            break
        text = page.extract_text() or ""
        pages.append({"page_num": i + 1, "text_content": text})
        size += len(text)
        if max_chars is not None and size > max_chars:
            break
    meta = reader.metadata
    metadata = {key: getattr(meta, key, None) for key in ("title", "author", "subject")} if meta else {}
    return {"filepath": str(path), "total_pages": len(reader.pages), "pages": pages,
            "full_text": "\n".join(p["text_content"] for p in pages), "metadata": metadata,
            "extraction_truncated": len(pages) < len(reader.pages)}


def read_pdf_native(file_path: str, max_pages: int = 25, max_chars: int = 100_000) -> str | None:
    """Extract text and metadata from PDF using macOS native PDFKit + Apple Vision OCR for scanned pages."""
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

        texts = []
        # Metadata
        attr = pdf_doc.documentAttributes()
        if attr:
            title = attr.get("Title")
            author = attr.get("Author")
            subject = attr.get("Subject")
            if title:
                texts.append(f"Title: {title}")
            if author:
                texts.append(f"Author: {author}")
            if subject:
                texts.append(f"Subject: {subject}")

        page_count = min(pdf_doc.pageCount(), max_pages)

        for idx in range(page_count):
            page = pdf_doc.pageAtIndex_(idx)
            if not page:
                continue

            page_str = page.string()
            if page_str and len(page_str.strip()) >= 20:
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

            if sum(len(t) for t in texts) > max_chars:
                break

        return "\n\n".join(texts)
    except Exception as e:
        logger.debug(f"Native PDFKit extraction failed for {file_path}: {e}")
        return None


