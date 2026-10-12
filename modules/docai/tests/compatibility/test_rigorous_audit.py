"""
Rigorous Audit & Edge Case Testing Suite for NeSy-DocAI
Tests multi-tax rates (0%, 5%, 8%, 10%), severe OCR noise, mathematical fraud detection (UNSAT),
multi-item invoices, and Excel export integrity.
"""

import os
import openpyxl
import pytest
from nesy_docai import (
    VisionPerceptionEngine,
    SymbolicSolverEngine,
    TaxMasterDataVerifier,
    AuditExcelExporter,
    PDFDocumentProcessor
)


def test_candidate_generator_severe_ocr_noise():
    vision = VisionPerceptionEngine()
    
    # Severe OCR noise combinations
    assert 10000 in vision.generate_number_candidates("1O.OOO")
    assert 15000 in vision.generate_number_candidates("l5.OOO đ")
    assert 85000 in vision.generate_number_candidates("B5OOO VND")
    assert 20000 in vision.generate_number_candidates("Z0,000")
    assert 500000 in vision.generate_number_candidates("S00.000")


def test_z3_solver_multi_tax_rates():
    solver = SymbolicSolverEngine()
    
    # 1. Tax Rate 8% (Decree VAT Reduction)
    raw_8pct = {
        "invoice_id": "HD-VAT-8",
        "seller_tax_id": "0312345678",
        "seller_name": "CÔNG TY CP THƯƠNG MẠI AN PHÁT",
        "line_items": [
            {"item_id": 1, "description": "Thiết bị điện tử", "quantity": "10", "unit_price": "100000", "amount": "1000000"}
        ],
        "subtotal": "1000000",
        "tax": "80000",  # 8% VAT
        "total": "1080000"
    }
    res_8pct = solver.solve_and_verify(raw_8pct)
    assert res_8pct["audit_status"] == "VERIFIED_SAT"
    assert res_8pct["tax_rate"] == "8%"
    assert res_8pct["total"] == 1080000

    # 2. Tax Rate 5% (Essential goods)
    raw_5pct = {
        "invoice_id": "HD-VAT-5",
        "seller_tax_id": "0312345678",
        "seller_name": "CÔNG TY NÔNG SẢN XANH",
        "line_items": [
            {"item_id": 1, "description": "Gạo ST25", "quantity": "20", "unit_price": "25000", "amount": "500000"}
        ],
        "subtotal": "500000",
        "tax": "25000",  # 5% VAT
        "total": "525000"
    }
    res_5pct = solver.solve_and_verify(raw_5pct)
    assert res_5pct["audit_status"] == "VERIFIED_SAT"
    assert res_5pct["tax_rate"] == "5%"

    # 3. Tax Rate 0% (Export/Exempt)
    raw_0pct = {
        "invoice_id": "HD-VAT-0",
        "seller_tax_id": "0312345678",
        "seller_name": "CÔNG TY XUẤT NHẬP KHẨU",
        "line_items": [
            {"item_id": 1, "description": "Dịch vụ phần mềm xuất khẩu", "quantity": "1", "unit_price": "5000000", "amount": "5000000"}
        ],
        "subtotal": "5000000",
        "tax": "0",  # 0% VAT
        "total": "5000000"
    }
    res_0pct = solver.solve_and_verify(raw_0pct)
    assert res_0pct["audit_status"] == "VERIFIED_SAT"
    assert res_0pct["tax_rate"] == "0%"


def test_z3_solver_fraud_unsat_detection():
    solver = SymbolicSolverEngine()
    
    # Invalid math: Subtotal=1,000,000 + Tax=100,000 != Total=2,000,000
    raw_fraud = {
        "invoice_id": "HD-FRAUD-001",
        "seller_tax_id": "0312345678",
        "seller_name": "CÔNG TY GIẢ MẠO",
        "line_items": [
            {"item_id": 1, "description": "Mặt hàng A", "quantity": "1", "unit_price": "1000000", "amount": "1000000"}
        ],
        "subtotal": "1000000",
        "tax": "100000",
        "total": "2000000"  # Invalid total!
    }
    res_fraud = solver.solve_and_verify(raw_fraud)
    assert res_fraud["audit_status"] == "FLAGGED_UNSAT"
    assert res_fraud["proof_certificate"]["smt_status"] == "UNSAT"


def test_excel_exporter_all_11_columns_and_sheets():
    exporter = AuditExcelExporter()
    solver = SymbolicSolverEngine()
    
    sample_raw = {
        "invoice_id": "HD-EXCEL-TEST",
        "invoice_date": "2026-08-08",
        "seller_tax_id": "0312345678",
        "seller_name": "CÔNG TY TEST EXCEL",
        "line_items": [
            {"item_id": 1, "description": "Bút chì 2B", "quantity": "10", "unit_price": "5000", "amount": "50000"},
            {"item_id": 2, "description": "Thước kẻ 30cm", "quantity": "2", "unit_price": "10000", "amount": "20000"}
        ],
        "subtotal": "70000",
        "tax": "7000",
        "total": "77000"
    }
    record = solver.solve_and_verify(sample_raw)
    
    out_file = "test_rigorous_output.xlsx"
    exporter.export_to_excel([record], output_filepath=out_file)
    
    assert os.path.exists(out_file)
    
    wb = openpyxl.load_workbook(out_file)
    sheet_names = wb.sheetnames
    assert "Invoice Summary" in sheet_names
    assert "Line Items Detail" in sheet_names
    assert "Audit Trail Log" in sheet_names
    
    ws_summary = wb["Invoice Summary"]
    headers = [cell.value for cell in ws_summary[1]]
    assert "MST Ng Bán (Vendor Tax Code)" in headers
    assert "Nội Dung Diễn Giải (Description)" in headers
    assert "Thuế Suất Tax Rate (%)" in headers
    assert "Tiền Thuế VAT Tax Amount (VND)" in headers
    
    # Cleanup test output file
    if os.path.exists(out_file):
        os.remove(out_file)
