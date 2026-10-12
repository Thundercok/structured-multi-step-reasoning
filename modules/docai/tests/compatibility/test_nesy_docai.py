"""
Unit Tests for nesy-docai Framework
"""

import os
import pytest
from nesy_docai import (
    VisionPerceptionEngine,
    SymbolicSolverEngine,
    TaxMasterDataVerifier,
    AuditExcelExporter
)


def test_candidate_generator():
    vision = VisionPerceptionEngine()
    candidates = vision.generate_number_candidates("1O000")
    assert 10000 in candidates

    tax_candidates = vision.generate_number_candidates("95OO")
    assert 9500 in tax_candidates


def test_z3_symbolic_solver():
    vision = VisionPerceptionEngine()
    solver = SymbolicSolverEngine(vision_engine=vision)

    raw_noisy_data = {
        "invoice_id": "TEST-001",
        "invoice_date": "2026-08-07",
        "seller_tax_id": "0312345678",
        "seller_name": "TEST COMPANY",
        "line_items": [
            {
                "item_id": 1,
                "description": "Item A",
                "quantity": "2",
                "unit_price": "1O000",  # Noisy 'O'
                "amount": "20000",
                "bbox": [10, 10, 50, 50]
            },
            {
                "item_id": 2,
                "description": "Item B",
                "quantity": "5",
                "unit_price": "15000",
                "amount": "75000",
                "bbox": [10, 60, 50, 100]
            }
        ],
        "subtotal": "95000",
        "tax": "95OO",  # Noisy 'OO'
        "total": "104500"
    }

    result = solver.solve_and_verify(raw_noisy_data)

    assert result["audit_status"] == "VERIFIED_SAT"
    assert result["subtotal"] == 95000
    assert result["tax"] == 9500
    assert result["total"] == 104500
    assert result["line_items"][0]["unit_price"] == 10000
    assert result["line_items"][0]["amount"] == 20000


def test_tax_verifier():
    verifier = TaxMasterDataVerifier()
    res = verifier.verify_tax_id("0312345678")
    assert res["verified"] is True
    assert res["status"] == "ACTIVE_OPERATING"


def test_excel_exporter(tmp_path):
    # Use inline mock data instead of calling process_invoice_image with non-existent file
    raw_data = {
        "invoice_id": "HD-TEST-001",
        "invoice_date": "2026-08-09",
        "seller_tax_id": "0312345678",
        "seller_name": "CÔNG TY TEST",
        "line_items": [
            {"item_id": 1, "description": "Test item", "quantity": "2", "unit_price": "10000", "amount": "20000"}
        ],
        "subtotal": "95000",
        "tax": "9500",
        "total": "104500"
    }
    vision = VisionPerceptionEngine()
    solver = SymbolicSolverEngine(vision_engine=vision)
    verified = solver.solve_and_verify(raw_data)

    exporter = AuditExcelExporter()
    out_file = str(tmp_path / "test_report.xlsx")
    saved_path = exporter.export_to_excel([verified], output_filepath=out_file)

    assert os.path.exists(saved_path)
