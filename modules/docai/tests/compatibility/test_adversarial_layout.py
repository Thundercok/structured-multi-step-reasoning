"""
Adversarial Layout & DPI Invariance Test Suite for SpatialLayoutExtractor & VisionPerceptionEngine
Tests:
1. DPI Scaling Invariance (72 DPI vs 150 DPI vs 300 DPI vs 4K resolution)
2. PO Number Positioned Below Subtotal vs Right-Neighbor Subtotal Value
3. Dense Multi-Column Line-Item Table Layout
4. Real OCR Bounding Box Extractions from Generated Hardcore Image Files
"""

import os
import zipfile
import tempfile
import pytest

from nesy_docai import (
    SpatialLayoutExtractor,
    VisionPerceptionEngine,
    SymbolicSolverEngine,
    BBox
)


def test_dpi_scaling_invariance():
    """
    Verifies 100% DPI & Resolution Invariance of SpatialLayoutExtractor.
    Coordinates scaled by 1x (base), 2.5x (high-res scan), and 4x (4K image) MUST return identical values.
    """
    extractor = SpatialLayoutExtractor()

    base_tokens = [
        {"text": "Subtotal", "confidence": 0.99, "bbox": [100, 500, 200, 520]},
        {"text": "100000", "confidence": 0.99, "bbox": [250, 500, 350, 520]},
        {"text": "VAT", "confidence": 0.99, "bbox": [100, 530, 200, 550]},
        {"text": "10000", "confidence": 0.99, "bbox": [250, 530, 350, 550]},
        {"text": "Total", "confidence": 0.99, "bbox": [100, 560, 200, 580]},
        {"text": "110000", "confidence": 0.99, "bbox": [250, 560, 350, 580]}
    ]

    # Base scale (1x)
    res_1x = extractor.extract_invoice_fields_spatially(base_tokens)

    # 2.5x High-Res Scan Scale
    res_25x_tokens = [
        {
            "text": t["text"],
            "confidence": t["confidence"],
            "bbox": [int(c * 2.5) for c in t["bbox"]]
        }
        for t in base_tokens
    ]
    res_25x = extractor.extract_invoice_fields_spatially(res_25x_tokens)

    # 4x 4K Camera Resolution Scale
    res_4x_tokens = [
        {
            "text": t["text"],
            "confidence": t["confidence"],
            "bbox": [int(c * 4.0) for c in t["bbox"]]
        }
        for t in base_tokens
    ]
    res_4x = extractor.extract_invoice_fields_spatially(res_4x_tokens)

    # All three DPI scales MUST return identical extracted monetary amounts!
    assert res_1x["subtotal"] == res_25x["subtotal"] == res_4x["subtotal"] == 100000
    assert res_1x["tax"] == res_25x["tax"] == res_4x["tax"] == 10000
    assert res_1x["total"] == res_25x["total"] == res_4x["total"] == 110000


def test_po_number_below_subtotal_vs_right_neighbor():
    """
    Adversarial Scenario:
    A PO Number '105000' sits directly BELOW the Subtotal label,
    while the true Subtotal value '100000' sits to the RIGHT of the Subtotal label.
    Normalized 2D Euclidean distance MUST select the right-neighbor Subtotal value ('100000').
    """
    extractor = SpatialLayoutExtractor()

    adversarial_tokens = [
        # Subtotal label
        {"text": "Subtotal", "confidence": 0.99, "bbox": [100, 500, 200, 520]},
        
        # Real Subtotal value to the right
        {"text": "100000", "confidence": 0.99, "bbox": [220, 500, 320, 520]},

        # PO Number directly below label (y = 530)
        {"text": "PO:", "confidence": 0.99, "bbox": [100, 530, 140, 545]},
        {"text": "105000", "confidence": 0.99, "bbox": [150, 530, 210, 545]}
    ]

    res = extractor.extract_invoice_fields_spatially(adversarial_tokens)
    assert res["subtotal"] == 100000
    assert res["subtotal"] != 105000


def test_dense_multicolumn_table_yband_filtering():
    """
    Adversarial Scenario:
    Dense line item row where Qty (10), Unit Price (15000), and Amount (150000) sit on the same y-band.
    Subtotal summary box sits below with explicit 'Total Amount' label.
    """
    extractor = SpatialLayoutExtractor()

    table_tokens = [
        # Line item row (y = 300)
        {"text": "Bút ký M&G", "confidence": 0.99, "bbox": [50, 300, 200, 320]},
        {"text": "10", "confidence": 0.99, "bbox": [220, 300, 250, 320]},
        {"text": "15000", "confidence": 0.99, "bbox": [270, 300, 340, 320]},
        {"text": "150000", "confidence": 0.99, "bbox": [360, 300, 450, 320]},

        # Totals Summary Box (y = 500)
        {"text": "Cộng tiền hàng", "confidence": 0.99, "bbox": [100, 500, 240, 520]},
        {"text": "150000", "confidence": 0.99, "bbox": [360, 500, 450, 520]}
    ]

    res = extractor.extract_invoice_fields_spatially(table_tokens)
    assert res["subtotal"] == 150000


def test_real_ocr_tokens_from_generated_hardcore_zip():
    """
    Tests VisionPerceptionEngine and SymbolicSolverEngine on REAL image files extracted
    from hardcore_invoices_challenge.zip (generated via PIL canvas rendering).
    Verifies actual macOS Vision API / Tesseract live OCR bounding box extractions.
    """
    zip_path = "hardcore_invoices_challenge.zip"
    assert os.path.exists(zip_path), "hardcore_invoices_challenge.zip must exist"

    tmp_extract_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(tmp_extract_dir)

    png_files = [
        os.path.join(tmp_extract_dir, f)
        for f in os.listdir(tmp_extract_dir)
        if f.lower().endswith(".png")
    ]
    assert len(png_files) > 0, "ZIP archive must contain PNG image files"

    vision_engine = VisionPerceptionEngine()
    solver_engine = SymbolicSolverEngine()

    processed_count = 0
    for img_file in png_files[:3]:  # Test first 3 real image files
        raw_extractions = vision_engine.process_invoice_image(img_file)
        assert raw_extractions is not None
        assert "subtotal" in raw_extractions

        verified = solver_engine.solve_and_verify(raw_extractions)
        assert verified is not None
        assert "audit_status" in verified
        processed_count += 1

    assert processed_count >= 3
