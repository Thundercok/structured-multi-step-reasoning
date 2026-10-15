"""
Tesseract 5.5.2 Native CLI OCR Engine with TSV Bounding Box Support
"""

import logging
import os
import subprocess
from typing import Dict, Any, List

logger = logging.getLogger("nesy_docai.intake.tesseract")


class TesseractOCREngine:
    def __init__(self, tesseract_cmd: str = "/opt/homebrew/bin/tesseract"):
        self.tesseract_cmd = tesseract_cmd if os.path.exists(tesseract_cmd) else "tesseract"

    def run_ocr(self, image_path: str) -> Dict[str, Any]:
        """
        Runs Tesseract OCR on an image.
        Returns full text, individual lines, and tokens with bounding boxes.
        """
        if not os.path.exists(image_path):
            logger.warning("Image file not found: %s", image_path)
            return {"full_text": "", "lines": [], "tokens": []}

        tokens = []
        full_text = ""

        # 1. Try TSV mode for bounding boxes
        try:
            cmd_tsv = [self.tesseract_cmd, image_path, "stdout", "-l", "vie+eng", "--oem", "1", "tsv"]
            res_tsv = subprocess.run(cmd_tsv, capture_output=True, text=True, timeout=15)
            if res_tsv.returncode == 0 and res_tsv.stdout.strip():
                tokens = self._parse_tsv_output(res_tsv.stdout)
                full_text = " ".join([t["text"] for t in tokens if t.get("text", "").strip()])
                logger.info("Tesseract TSV mode: extracted %d tokens from %s", len(tokens), os.path.basename(image_path))
        except Exception as e:
            logger.warning("Tesseract TSV mode failed for %s: %s", image_path, e)

        # 2. Fallback to plain text mode if TSV didn't work
        if not full_text:
            try:
                cmd_text = [self.tesseract_cmd, image_path, "stdout", "-l", "vie+eng", "--oem", "1"]
                res_text = subprocess.run(cmd_text, capture_output=True, text=True, timeout=10)
                full_text = res_text.stdout if res_text.returncode == 0 else ""
                logger.info("Tesseract text mode: extracted %d chars from %s", len(full_text), os.path.basename(image_path))
            except Exception as e:
                logger.warning("Tesseract text mode also failed for %s: %s", image_path, e)
                return {"full_text": "", "lines": [], "tokens": []}

        lines = [line.strip() for line in full_text.splitlines() if line.strip()]

        return {
            "full_text": full_text,
            "lines": lines,
            "tokens": tokens
        }

    def _parse_tsv_output(self, tsv_text: str) -> List[Dict[str, Any]]:
        """
        Parse Tesseract TSV output into token dicts with bounding boxes.
        TSV columns: level, page_num, block_num, par_num, line_num, word_num,
                     left, top, width, height, conf, text
        """
        tokens = []
        lines = tsv_text.strip().split("\n")
        if len(lines) < 2:  # Need at least header + 1 data line
            return tokens

        # Skip header line
        for line in lines[1:]:
            parts = line.split("\t")
            if len(parts) < 12:
                continue

            try:
                conf = float(parts[10])
                text = parts[11].strip()

                # Skip empty text or low-confidence noise (conf < 0 means no text)
                if not text or conf < 0:
                    continue

                left = int(parts[6])
                top = int(parts[7])
                width = int(parts[8])
                height = int(parts[9])

                tokens.append({
                    "text": text,
                    "confidence": conf / 100.0,  # Normalize to 0.0-1.0
                    "bbox": [left, top, left + width, top + height],
                    "level": int(parts[0]),
                    "line_num": int(parts[4]),
                    "word_num": int(parts[5]),
                })
            except (ValueError, IndexError):
                continue

        return tokens
