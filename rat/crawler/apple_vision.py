"""
rat.crawler.apple_vision — Native macOS Apple Vision Framework integration.
Zero-dependency, high-speed on-device OCR and Image Scene/Object Classification.
"""

from __future__ import annotations

import logging
import os
import platform
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rat.crawler.vision_taxonomy import expand_taxonomy_labels

logger = logging.getLogger("rat.apple_vision")

_VISION_LOADED = False
_VISION_LOCK = threading.Lock()

# Global objective-c class handles
VNClassifyImageRequest = None
VNImageRequestHandler = None
NSURL = None


def _init_apple_vision() -> bool:
    """Initialize and load Apple Vision Framework dynamically via PyObjC."""
    global _VISION_LOADED, VNClassifyImageRequest, VNImageRequestHandler, NSURL

    if _VISION_LOADED:
        return True

    if platform.system() != "Darwin":
        logger.debug("Apple Vision is only available on macOS Darwin.")
        return False

    with _VISION_LOCK:
        if _VISION_LOADED:
            return True
        try:
            import objc
            from Foundation import NSBundle, NSURL as _NSURL

            framework_path = "/System/Library/Frameworks/Vision.framework"
            if not os.path.exists(framework_path):
                logger.warning(f"Vision framework not found at {framework_path}")
                return False

            vision_bundle = NSBundle.bundleWithPath_(framework_path)
            objc.loadBundle("Vision", globals(), bundle_path=framework_path)

            VNClassifyImageRequest = objc.lookUpClass("VNClassifyImageRequest")
            VNImageRequestHandler = objc.lookUpClass("VNImageRequestHandler")
            NSURL = _NSURL

            _VISION_LOADED = True
            logger.info("Native Apple Vision Framework initialized successfully.")
            return True
        except Exception as e:
            logger.warning(f"Failed to load Apple Vision framework: {e}")
            return False


class AppleVisionEngine:
    """Native macOS Apple Vision engine for OCR and Image Recognition."""

    def __init__(self) -> None:
        self.available = _init_apple_vision()

    def recognize_text(self, image_path: str) -> str:
        return self._recognize_text(image_path)

    def recognize_text_from_bytes(self, image_bytes: bytes) -> str:
        return self._recognize_text(image_bytes)

    def _recognize_text(self, source) -> str:
        if not self.available:
            return ""
        from document_intake.vision import recognize_tokens
        return "\n".join(token["text"] for token in recognize_tokens(source))

    def classify_image(
        self,
        image_path: str,
        min_confidence: float = 0.08,
        max_labels: int = 12
    ) -> List[Tuple[str, float]]:
        """
        Classify scene, objects, and concepts in an image using VNClassifyImageRequest.
        Returns a list of (label_identifier, confidence_score).
        """
        if not self.available or not os.path.exists(image_path):
            return []

        try:
            file_url = NSURL.fileURLWithPath_(str(Path(image_path).resolve()))
            request = VNClassifyImageRequest.alloc().init()
            handler = VNImageRequestHandler.alloc().initWithURL_options_(file_url, {})
            success = handler.performRequests_error_([request], None)

            if not success:
                return []

            results = request.results()
            if not results:
                return []

            scored_labels: List[Tuple[str, float]] = []
            for observation in results:
                conf = float(observation.confidence())
                if conf >= min_confidence:
                    identifier = str(observation.identifier())
                    scored_labels.append((identifier, conf))

            # Sort by confidence descending
            scored_labels.sort(key=lambda x: x[1], reverse=True)
            return scored_labels[:max_labels]
        except Exception as e:
            logger.debug(f"Apple Vision classification failed on {image_path}: {e}")
            return []

    def analyze_image(self, image_path: str) -> Dict[str, Any]:
        """
        Deep multimodal image analysis combining OCR, Scene/Object Classification, and Taxonomy Expansion.
        """
        path_obj = Path(image_path)
        if not path_obj.exists():
            return {
                "ocr_text": "",
                "visual_tags": [],
                "vietnamese_tags": [],
                "english_tags": [],
                "combined_text": "",
                "is_screenshot": False,
            }

        # 1. Classify image visual contents
        classified = self.classify_image(image_path, min_confidence=0.08)
        raw_identifiers = [item[0] for item in classified]

        # 2. Expand taxonomy to Vietnamese and English terms
        en_tags, vi_tags = expand_taxonomy_labels(raw_identifiers)

        # 3. Detect if image is screenshot or screen capture
        name_lower = path_obj.name.lower()
        is_screenshot = any(s in name_lower for s in ["screenshot", "screen shot", "cap_man_hinh", "capture"]) or any("screenshot" in t for t in en_tags)
        if is_screenshot:
            if "ảnh chụp màn hình" not in vi_tags:
                vi_tags.append("ảnh chụp màn hình")
            if "screenshot" not in en_tags:
                en_tags.append("screenshot")

        # 4. Extract OCR text
        ocr_text = self.recognize_text(image_path)

        # 5. Build rich searchable textual document representation
        lines = []
        lines.append(f"Image File: {path_obj.name}")

        if vi_tags or en_tags:
            tags_display_vi = ", ".join(vi_tags[:15])
            tags_display_en = ", ".join(en_tags[:15])
            lines.append(f"Visual Concepts (VI): {tags_display_vi}")
            lines.append(f"Visual Concepts (EN): {tags_display_en}")

        if ocr_text.strip():
            lines.append("--- Detected Text (OCR) ---")
            lines.append(ocr_text.strip())

        combined_text = "\n".join(lines)

        return {
            "ocr_text": ocr_text,
            "raw_labels": raw_identifiers,
            "vietnamese_tags": vi_tags,
            "english_tags": en_tags,
            "visual_tags": vi_tags[:8],
            "combined_text": combined_text,
            "is_screenshot": is_screenshot,
        }


# Global singleton instance
apple_vision = AppleVisionEngine()
