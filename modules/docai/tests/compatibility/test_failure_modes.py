"""
Comprehensive Failure Mode Test Suite for NeSy-DocAI:
1. Mixed Tax Brackets (Decree 15/2022/NĐ-CP: 0%, 5%, 8%, 10% line items)
2. Pre-Tax and Post-Tax Trade Discounts
3. EUR Inverted Locale Parsing (1.000.000,00)
4. Word-Level Confidence Ranking Calibration
5. Human-Readable UNSAT Diagnostic Certificates
6. 2D Bounding-Box Spatial Anchoring (Plausible PO Number vs Subtotal/Tax/Total)
"""

import pytest
from nesy_docai import (
    SymbolicSolverEngine,
    solve_invoice,
    SpatialLayoutExtractor,
    BBox
)
from nesy_docai.lattice.generator import (
    CandidateLatticeGenerator,
    RawToken,
    DocCondition,
    Locale,
    generate_lattice
)


def test_mixed_tax_brackets_decree_15():
    """
    Tests Vietnamese Decree 15/2022/NĐ-CP mixed tax rates:
    - Item 1: Non-taxable / 0% VAT (50,000 VND) -> tax 0
    - Item 2: 8% VAT (100,000 VND) -> tax 8,000
    - Item 3: 10% VAT (200,000 VND) -> tax 20,000
    Total Subtotal = 350,000; Total Tax = 28,000; Total = 378,000 VND.
    Must return VERIFIED_SAT (NOT FLAGGED_UNSAT)!
    """
    solver = SymbolicSolverEngine()
    raw_mixed = {
        "invoice_id": "DECREE-15-MIXED",
        "seller_tax_id": "0312345678",
        "seller_name": "CÔNG TY THIẾT BỊ & NÔNG SẢN",
        "line_items": [
            {"item_id": 1, "description": "Nông sản (0% VAT)", "quantity": "1", "unit_price": "50000", "amount": "50000"},
            {"item_id": 2, "description": "Hàng giảm thuế (8% VAT)", "quantity": "1", "unit_price": "100000", "amount": "100000"},
            {"item_id": 3, "description": "Hàng tiêu chuẩn (10% VAT)", "quantity": "1", "unit_price": "200000", "amount": "200000"}
        ],
        "subtotal": "350000",
        "tax": "28000",
        "total": "378000"
    }

    result = solver.solve_and_verify(raw_mixed)
    assert result["audit_status"] == "VERIFIED_SAT"
    assert result["subtotal"] == 350000
    assert result["tax"] == 28000
    assert result["total"] == 378000


def test_pre_and_post_tax_discounts():
    """
    Tests trade discounts: Subtotal = 100,000, Discount = 10,000.
    Pre-tax discount: Taxable = 90,000 (10% VAT = 9,000); Total = 99,000.
    """
    solver = SymbolicSolverEngine()
    raw_discount = {
        "invoice_id": "DISCOUNT-001",
        "seller_tax_id": "0312345678",
        "seller_name": "CÔNG TY BÁN LẺ",
        "line_items": [
            {"item_id": 1, "description": "Hàng hóa A", "quantity": "1", "unit_price": "100000", "amount": "100000"}
        ],
        "discount": "10000",
        "subtotal": "100000",
        "tax": "9000",
        "total": "99000"
    }

    result = solver.solve_and_verify(raw_discount)
    assert result["audit_status"] == "VERIFIED_SAT"
    assert result["subtotal"] == 100000
    assert result["tax"] == 9000
    assert result["total"] == 99000


def test_eur_inverted_locale_parsing():
    """
    Tests European decimal locale: '1.000.000,00' -> 100000000 minor units (cents).
    """
    token = RawToken(text="1.000.000,00", word_confidence=0.95, engine="tesseract")
    candidates = generate_lattice(token, condition=DocCondition.CLEAN, locale=Locale.EUR)
    assert len(candidates) > 0
    assert candidates[0].parsed_value == 100000000


def test_word_level_confidence_ranking_calibration():
    """
    User Check #3 Test Case:
    A word Vision API scores 0.80 confidence but is actually correct.
    Verifies that the exact original parsed value (15000) is TOP-RANKED.
    """
    token = RawToken(text="15000", char_confidences=[0.80] * 5, engine="vision_api")
    result = generate_lattice(token, DocCondition.CLEAN, Locale.VND)
    
    parsed_values = [c.parsed_value for c in result]
    assert 15000 in parsed_values
    assert result[0].parsed_value == 15000  # Must be top-ranked!


def test_human_readable_unsat_explanation():
    """
    Verifies that non-technical accounting users receive plain-language explanations
    on UNSAT invoices rather than raw Z3 model dumps.
    """
    solver = SymbolicSolverEngine()
    raw_fraud = {
        "invoice_id": "HD-FRAUD-002",
        "seller_tax_id": "0312345678",
        "seller_name": "CÔNG TY GIẢ MẠO",
        "line_items": [
            {"item_id": 1, "description": "Mặt hàng A", "quantity": "1", "unit_price": "1000000", "amount": "1000000"}
        ],
        "subtotal": "1000000",
        "tax": "100000",
        "total": "2000000"  # Invalid total!
    }

    result = solver.solve_and_verify(raw_fraud)
    assert result["audit_status"] == "FLAGGED_UNSAT"
    
    proof = result["proof_certificate"]
    assert proof is not None
    assert "constraints_verified" in proof
    explanation = proof["constraints_verified"][0]
    assert "Accounting Equation Violation" in explanation or "differs from Total" in explanation


def test_plausible_magnitude_po_number_spatial_anchoring():
    """
    Tests 2D Bounding-Box Layout Anchoring vs Plausible-Magnitude Anomaly:
    A PO Number '105000' (plausible 5% difference from Subtotal '100000') sits at top of invoice.
    Verifies that 2D spatial layout extraction anchors Subtotal to '100000' and Tax to '10000'
    by 2D geometric proximity, ignoring the distant '105000' PO number.
    """
    extractor = SpatialLayoutExtractor()
    raw_tokens = [
        # Top of invoice: PO Number
        {"text": "PO:", "confidence": 0.99, "bbox": [50, 50, 100, 70]},
        {"text": "105000", "confidence": 0.99, "bbox": [110, 50, 200, 70]},

        # Bottom of invoice: Summary Totals Box
        {"text": "Subtotal", "confidence": 0.99, "bbox": [100, 500, 200, 520]},
        {"text": "100000", "confidence": 0.99, "bbox": [250, 500, 350, 520]},  # Right of Subtotal

        {"text": "Tax", "confidence": 0.99, "bbox": [100, 530, 200, 550]},
        {"text": "10000", "confidence": 0.99, "bbox": [250, 530, 350, 550]},   # Right of Tax

        {"text": "Total", "confidence": 0.99, "bbox": [100, 560, 200, 580]},
        {"text": "110000", "confidence": 0.99, "bbox": [250, 560, 350, 580]}   # Right of Total
    ]

    spatial_res = extractor.extract_invoice_fields_spatially(raw_tokens)

    assert spatial_res["subtotal"] == 100000
    assert spatial_res["tax"] == 10000
    assert spatial_res["total"] == 110000
    # PO number 105000 MUST NOT be mis-anchored as Subtotal or Tax!
    assert spatial_res["subtotal"] != 105000
    assert spatial_res["tax"] != 105000
