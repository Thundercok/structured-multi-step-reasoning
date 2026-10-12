"""
Visual Bounding Box Annotator Module (Pixel-Level Provenance Renderer)
"""

from typing import Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont


class BoundingBoxVisualizer:
    def __init__(self, font_size: int = 14):
        self.font_size = font_size
        try:
            self.font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            self.font = ImageFont.load_default()

    def annotate_invoice(
        self,
        image_input: Image.Image,
        verified_record: Dict[str, Any],
        box_color: str = "#28A745",
        text_color: str = "#FFFFFF"
    ) -> Image.Image:
        """
        Draws 2D bounding box rectangles and status labels over the target invoice image.
        """
        annotated_img = image_input.copy().convert("RGB")
        draw = ImageDraw.Draw(annotated_img)

        audit_status = verified_record.get("audit_status", "UNKNOWN")
        main_color = "#28A745" if audit_status == "VERIFIED_SAT" else "#DC3545"

        # 1. Draw Line Items Bounding Boxes
        for item in verified_record.get("line_items", []):
            bbox = item.get("bbox")
            if bbox and len(bbox) == 4:
                x0, y0, x1, y1 = bbox
                draw.rectangle([x0, y0, x1, y1], outline=main_color, width=3)
                label = f"Item {item.get('item_id')}: {item.get('amount'):,} VND"
                draw.rectangle([x0, max(0, y0 - 20), x0 + 160, y0], fill=main_color)
                draw.text((x0 + 4, max(0, y0 - 18)), label, fill=text_color, font=self.font)

        # 2. Draw Totals Bounding Boxes
        bboxes = verified_record.get("bboxes", {})
        total_bbox = bboxes.get("total")
        if total_bbox and len(total_bbox) == 4:
            x0, y0, x1, y1 = total_bbox
            draw.rectangle([x0, y0, x1, y1], outline="#007BFF", width=3)
            draw.rectangle([x0, max(0, y0 - 20), x0 + 140, y0], fill="#007BFF")
            draw.text((x0 + 4, max(0, y0 - 18)), f"Total: {verified_record.get('total'):,} VND", fill=text_color, font=self.font)

        # 3. Draw Watermark Audit Stamp Badge
        w, h = annotated_img.size
        stamp_text = f" VERIFIED_SAT (Z3 Presburger SMT) " if audit_status == "VERIFIED_SAT" else " FLAGGED_UNSAT "
        draw.rectangle([w - 320, 20, w - 20, 60], fill=main_color)
        draw.text((w - 310, 30), stamp_text, fill="#FFFFFF", font=self.font)

        return annotated_img
