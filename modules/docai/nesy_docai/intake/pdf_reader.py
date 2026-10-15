"""Compatibility facade over the shared digital PDF reader."""
from document_intake.pdf import read_pdf


class PDFReaderEngine:
    def process_pdf(self, pdf_filepath):
        try:
            result = read_pdf(pdf_filepath)
            return {key: result[key] for key in ("filepath", "total_pages", "pages", "full_text")}
        except Exception as exc:
            return {"error": str(exc), "pages": []}
