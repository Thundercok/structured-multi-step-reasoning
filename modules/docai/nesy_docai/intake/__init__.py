"""
Multi-Engine Document Intake Module (PDF, macOS Vision, Tesseract, Qwen VLM, e-Invoice XML)
"""

from .pdf_reader import PDFReaderEngine
from .tesseract_ocr import TesseractOCREngine
from .vision_ocr import MacOSVisionEngine
from .qwen_ocr import QwenVLEngine
from .xml_reader import EInvoiceXMLReaderEngine

__all__ = [
    "PDFReaderEngine",
    "TesseractOCREngine",
    "MacOSVisionEngine",
    "QwenVLEngine",
    "EInvoiceXMLReaderEngine",
]
