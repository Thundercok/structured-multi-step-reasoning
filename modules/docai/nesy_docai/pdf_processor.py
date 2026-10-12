"""
PDF Document Processor Module for Multi-Page Invoices
"""

import io
from typing import List, Dict, Any
from PIL import Image, ImageDraw
import pypdf


class PDFDocumentProcessor:
    def extract_pdf_metadata_and_text(self, pdf_filepath: str) -> Dict[str, Any]:
        """
        Parses multi-page PDF invoices and extracts text streams per page.
        """
        reader = pypdf.PdfReader(pdf_filepath)
        num_pages = len(reader.pages)
        pages_text = []

        for idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            pages_text.append({
                "page_num": idx + 1,
                "text_length": len(text),
                "text_content": text[:500]  # Snippet
            })

        return {
            "filepath": pdf_filepath,
            "total_pages": num_pages,
            "pages": pages_text
        }

    def render_dummy_pdf_page_image(self, page_num: int = 1, width: int = 600, height: int = 800) -> Image.Image:
        """
        Generates a synthetic high-resolution image representation of an invoice page for Vision processing.
        """
        img = Image.new("RGB", (width, height), color="#FFFFFF")
        draw = ImageDraw.Draw(img)

        # Draw mock invoice layout lines
        draw.rectangle([20, 20, width - 20, height - 20], outline="#CCCCCC", width=2)
        draw.text((40, 40), "HOÁ ĐƠN GIÁ TRỊ GIA TĂNG (VAT INVOICE)", fill="#1F4E78")
        draw.text((40, 70), f"Mẫu số: 01GTKT0/001 - Ký hiệu: AA/26E - Page {page_num}", fill="#555555")

        # Mock table grid
        draw.rectangle([40, 200, width - 40, 400], outline="#000000", width=1)
        draw.line([40, 240, width - 40, 240], fill="#000000", width=1)

        return img
