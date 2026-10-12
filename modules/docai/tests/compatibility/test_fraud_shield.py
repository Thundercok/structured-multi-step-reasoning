"""
Test Suite for 4-Layer Anti-Fraud Defense Shield
"""

import os
import pytest
from nesy_docai import (
    DuplicateInvoiceRegistry,
    VietnameseTaxIDValidator,
    FraudRiskScorer,
    NeSyInvoicePipeline
)


def test_duplicate_invoice_prevention(tmp_path):
    """
    Layer 1: Verifies SHA-256 fingerprint anti-double claiming registry.
    """
    reg_path = os.path.join(tmp_path, "test_registry.db")
    registry = DuplicateInvoiceRegistry(db_path=reg_path)

    # First submission
    is_dup1, hash1 = registry.check_and_register("0312345678", "INV-1001", "2026-08-09", 104500, "file1.png")
    assert is_dup1 is False
    assert len(hash1) == 64

    # Second submission (identical fingerprint)
    is_dup2, hash2 = registry.check_and_register("0312345678", "INV-1001", "2026-08-09", 104500, "file2.png")
    assert is_dup2 is True
    assert hash1 == hash2


def test_vietnamese_tax_id_modulo_31():
    """
    Layer 2: Verifies Modulo-31 MST checksum algorithm & format validation.
    """
    validator = VietnameseTaxIDValidator()

    # Valid test enterprise codes
    valid, msg = validator.validate_mst("0312345678")
    assert valid is True

    # Bad format (wrong length)
    valid_bad_fmt, msg_bad_fmt = validator.validate_mst("12345")
    assert valid_bad_fmt is False
    assert "10 or 13 digits" in msg_bad_fmt

    # Bad check digit
    valid_bad_chk, msg_bad_chk = validator.validate_mst("0312345679")
    assert valid_bad_chk is False
    assert "Invalid MST Modulo-31 check digit" in msg_bad_chk


def test_composite_fraud_risk_scorer():
    """
    Layer 4: Verifies composite risk score calculation (0 - 100).
    """
    # Use a fresh in-memory SQLite registry so test doesn't conflict with other tests
    import tempfile
    tmp_db = os.path.join(tempfile.mkdtemp(), "fraud_test.db")
    scorer = FraudRiskScorer()
    scorer.registry = DuplicateInvoiceRegistry(db_path=tmp_db)

    clean_record = {
        "invoice_id": "INV-SAFE-001",
        "seller_tax_id": "0312345678",
        "seller_name": "CÔNG TY BÁN LẺ THÔNG MINH",
        "invoice_date": "2026-08-09",
        "subtotal": 100000,
        "tax": 10000,
        "total": 110000,
        "audit_status": "VERIFIED_SAT"
    }

    res_clean = scorer.audit_invoice_record(clean_record, file_name="safe.png")
    assert res_clean.risk_score <= 20
    assert res_clean.risk_level == "LOW"
    assert res_clean.duplicate_flag is False

    # Second submission of identical record -> triggers duplicate claim!
    res_dup = scorer.audit_invoice_record(clean_record, file_name="duplicate.png")
    assert res_dup.duplicate_flag is True
    assert res_dup.risk_score >= 50
    assert res_dup.risk_level in ("MEDIUM", "HIGH")

    # Fraudulent record (Invalid MST + Math Fraud)
    fraud_record = {
        "invoice_id": "INV-FRAUD-999",
        "seller_tax_id": "0312345679",  # Invalid check digit!
        "seller_name": "N/A",
        "invoice_date": "2026-08-09",
        "subtotal": 1000000,
        "tax": 100000,
        "total": 9999999,               # Math tampering!
        "audit_status": "FLAGGED_UNSAT"
    }

    res_fraud = scorer.audit_invoice_record(fraud_record, file_name="fraud.png")
    assert res_fraud.risk_score >= 60
    assert res_fraud.risk_level == "HIGH"
    assert res_fraud.mst_valid is False
    assert len(res_fraud.fraud_alerts) >= 3
