"""Compatibility facade over shared Apple Vision OCR."""
from document_intake.vision import recognize_tokens


class MacOSVisionEngine:
    def run_ocr(self, image_path):
        return recognize_tokens(image_path)
