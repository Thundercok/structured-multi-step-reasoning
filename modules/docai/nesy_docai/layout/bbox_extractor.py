"""
2D Bounding-Box Spatial Layout Extractor (DPI-Invariant & Relative Line-Height Scaled)
Anchors Key-Value invoice fields by relative 2D geometry (relative to median token line-height h_line),
eliminating DPI coupling, absolute pixel thresholds, and 1D string blocklists.
"""

import math
import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple


@dataclass
class BBox:
    x_min: int
    y_min: int
    x_max: int
    y_max: int

    @property
    def x_center(self) -> float:
        return (self.x_min + self.x_max) / 2.0

    @property
    def y_center(self) -> float:
        return (self.y_min + self.y_max) / 2.0

    @property
    def width(self) -> int:
        return self.x_max - self.x_min

    @property
    def height(self) -> int:
        return self.y_max - self.y_min


@dataclass
class OCRToken:
    text: str
    confidence: float = 1.0
    bbox: Optional[BBox] = None


class SpatialLayoutExtractor:
    """
    DPI-Invariant 2D Spatial Layout Parser for Document AI.
    All distance thresholds are dynamically normalized relative to the median token line height (h_line).
    """

    def parse_bbox(self, raw_bbox: Any) -> Optional[BBox]:
        if not raw_bbox or not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) < 4:
            return None
        return BBox(
            x_min=int(raw_bbox[0]),
            y_min=int(raw_bbox[1]),
            x_max=int(raw_bbox[2]),
            y_max=int(raw_bbox[3])
        )

    def tokens_from_raw(self, raw_tokens: List[Dict[str, Any]]) -> List[OCRToken]:
        tokens = []
        for t in raw_tokens:
            text = str(t.get("text", "")).strip()
            if not text:
                continue
            conf = float(t.get("confidence", 1.0))
            bbox = self.parse_bbox(t.get("bbox"))
            tokens.append(OCRToken(text=text, confidence=conf, bbox=bbox))
        return tokens

    def compute_median_line_height(self, tokens: List[OCRToken]) -> float:
        """
        Computes the median token line-height (h_line) across all valid bounding boxes on the page.
        Enables 100% resolution & DPI invariance across 72 DPI, 300 DPI, 4K scans.
        """
        heights = [t.bbox.height for t in tokens if t.bbox and t.bbox.height > 0]
        if not heights:
            return 20.0
        sorted_h = sorted(heights)
        n = len(sorted_h)
        if n % 2 == 1:
            return float(sorted_h[n // 2])
        return (sorted_h[n // 2 - 1] + sorted_h[n // 2]) / 2.0

    def find_kv_spatial_pair(
        self,
        tokens: List[OCRToken],
        keyword_regexes: List[str]
    ) -> Optional[Tuple[OCRToken, OCRToken, int]]:
        """
        DPI-Invariant Spatial Search:
        Locates the keyword token, computes dynamic h_line relative thresholds,
        and finds the closest candidate numeric token in 2D space.
        """
        if not tokens:
            return None

        h_line = self.compute_median_line_height(tokens)

        # Dynamic DPI-Invariant Relative Thresholds (scaled by h_line)
        max_y_same_line = 1.5 * h_line
        max_x_right_dist = 25.0 * h_line
        below_x_center_tolerance = 5.0 * h_line
        below_y_max_dist = 3.0 * h_line
        x_min_slack = 0.5 * h_line
        y_min_slack = 0.25 * h_line

        # Step 1: Find Keyword Token(s)
        keyword_matches = []
        for t in tokens:
            for pattern in keyword_regexes:
                if re.search(pattern, t.text, re.IGNORECASE):
                    keyword_matches.append(t)
                    break

        if not keyword_matches:
            return None

        # Sort candidate keywords by y-position (top to bottom)
        keyword_matches.sort(key=lambda tok: tok.bbox.y_center if tok.bbox else 0)

        for key_tok in keyword_matches:
            if not key_tok.bbox:
                continue

            # Step 2: Search for Numeric Candidate Tokens in Relative 2D Proximity
            candidates = []
            for t in tokens:
                if t == key_tok or not t.bbox:
                    continue

                # Clean numeric value
                num_str = re.sub(r'[^\d]', '', t.text)
                if not num_str:
                    continue

                val = int(num_str)

                # Geometry Check 1: Right-Neighbor Relationship
                # Same horizontal line (y_center within max_y_same_line) AND number is to the right
                is_right = (
                    abs(t.bbox.y_center - key_tok.bbox.y_center) <= max_y_same_line
                    and t.bbox.x_min >= (key_tok.bbox.x_min - x_min_slack)
                    and (t.bbox.x_min - key_tok.bbox.x_max) <= max_x_right_dist
                )

                # Geometry Check 2: Below-Neighbor Relationship
                # Number is directly below keyword (x_center alignment within tolerance) AND y_min below keyword
                is_below = (
                    abs(t.bbox.x_center - key_tok.bbox.x_center) <= below_x_center_tolerance
                    and t.bbox.y_min >= (key_tok.bbox.y_max - y_min_slack)
                    and (t.bbox.y_min - key_tok.bbox.y_max) <= below_y_max_dist
                )

                if is_right or is_below:
                    # Calculate Normalized 2D Euclidean Distance (in units of h_line)
                    dx = (t.bbox.x_min - key_tok.bbox.x_max) / h_line
                    dy = abs(t.bbox.y_center - key_tok.bbox.y_center) / h_line
                    norm_dist = math.sqrt(max(0, dx)**2 + dy**2)
                    candidates.append((norm_dist, t, val))

            if candidates:
                # Pick token with smallest normalized 2D spatial distance to keyword
                candidates.sort(key=lambda item: item[0])
                best_dist, best_tok, best_val = candidates[0]
                return (key_tok, best_tok, best_val)

        return None

    def extract_invoice_fields_spatially(
        self,
        raw_tokens: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Full DPI-invariant 2D spatial layout extraction for Subtotal, Tax, Total.
        """
        tokens = self.tokens_from_raw(raw_tokens)
        if not tokens:
            return {}

        subtotal_keys = [r'cộng\s*tiền\s*hàng', r'tiền\s*hàng', r'\bsubtotal\b', r'net\s*amount']
        tax_keys = [r'tiền\s*thuế', r'thuế\s*gtgt', r'\bvat\b', r'\btax\b', r'tax\s*amount']
        total_keys = [r'tổng\s*cộng', r'tổng\s*tiền', r'\btotal\b', r'amount\s*due', r'grand\s*total']

        subtotal_res = self.find_kv_spatial_pair(tokens, subtotal_keys)
        tax_res = self.find_kv_spatial_pair(tokens, tax_keys)
        total_res = self.find_kv_spatial_pair(tokens, total_keys)

        extracted = {}

        if subtotal_res:
            extracted["subtotal"] = subtotal_res[2]
            extracted["subtotal_bbox"] = subtotal_res[1].bbox

        if tax_res:
            extracted["tax"] = tax_res[2]
            extracted["tax_bbox"] = tax_res[1].bbox

        if total_res:
            extracted["total"] = total_res[2]
            extracted["total_bbox"] = total_res[1].bbox

        return extracted
