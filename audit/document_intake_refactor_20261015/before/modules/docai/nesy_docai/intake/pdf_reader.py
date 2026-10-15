"""
PyPDF Digital Document Intake Engine
"""

import os
from typing import Dict, Any, List
import pypdf


class PDFReaderEngine:
    def process_pdf(self, pdf_filepath: str) -> Dict[str, Any]:
        """
        Parses digital PDF invoice files and extracts page text streams.
        """
        if not os.path.exists(pdf_filepath):
            return {"error": f"File not found: {pdf_filepath}", "pages": []}

        try:
            reader = pypdf.PdfReader(pdf_filepath)
            num_pages = len(reader.pages)
            pages_text = []

            for idx, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                pages_text.append({
                    "page_num": idx + 1,
                    "text_content": text
                })

            full_text = "\n".join([p["text_content"] for p in pages_text])

            return {
                "filepath": pdf_filepath,
                "total_pages": num_pages,
                "pages": pages_text,
                "full_text": full_text
            }
        except Exception as ex:
            return {"error": str(ex), "pages": []}
