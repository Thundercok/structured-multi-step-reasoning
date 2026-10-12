"""Migration/inspection regressions. Fixtures are synthetic, not OCR evidence."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from nesy_docai.service import inspect_invoice_file, parse_invoice_text, review_invoice_fields

ROOT = Path(__file__).resolve().parents[1]
RAW = {"subtotal": "100000", "tax": "10000", "total": "110000", "line_items": []}


def need_solver():
    pytest.importorskip("z3", reason="Install requirements-docai.txt for solver tests")


def test_package_does_not_load_optional_engines_or_rat():
    script = "import sys; import nesy_docai; assert 'z3' not in sys.modules; assert 'rat' not in sys.modules"
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_cli_help_does_not_load_z3():
    result = subprocess.run([sys.executable, "-m", "nesy_docai", "--help"], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0 and "fields-json" in result.stdout


@pytest.mark.parametrize("raw", [{}, {**RAW, "total": ""}, {**RAW, "tax": None},
                                  {**RAW, "tax": True}, {**RAW, "tax": "-10000"}, {**RAW, "tax": "10.50"}])
def test_missing_and_invalid_fields_never_become_zero_sat(raw):
    result = review_invoice_fields(raw)
    assert result["status"] == "INCOMPLETE"
    assert result["candidate_values"] is None and result["review_required"]
    assert result["raw_fields"] == raw


def test_valid_zero_tax_remains_zero():
    need_solver()
    raw = parse_invoice_text("Subtotal: 100000\nTax: 0\nTotal: 100000")
    assert raw["tax"] == "0"
    result = review_invoice_fields(raw)
    assert result["status"] == "SAT"
    assert result["candidate_values"]["tax"] == 0 and result["review_required"]


def test_sat_is_candidate_consistency_and_preserves_raw_noisy_digits():
    need_solver()
    raw = {**RAW, "tax": "1OOOO"}
    result = review_invoice_fields(raw)
    assert result["status"] == "SAT"
    assert result["candidate_values"]["tax"] == 10000
    assert result["raw_fields"] == raw
    assert result["review_required"] and result["candidate_selection"] == "uniqueness_not_checked"
    assert "confidence" not in result and "fraud_risk_score" not in result


def test_wrong_totals_and_wrong_line_products_fail():
    need_solver()
    assert review_invoice_fields({**RAW, "total": "210000"})["status"] == "UNSAT"
    raw = {**RAW, "line_items": [{"quantity": "2", "unit_price": "100000", "amount": "100000"}]}
    result = review_invoice_fields(raw)
    assert result["status"] == "UNSAT" and result["candidate_values"] is None


def test_text_parser_does_not_use_unlabelled_numbers_or_multiple_invoices():
    text = "MST 0312345678\nPO: 999999999\nSubtotal: 100000\nTax: 10000\nTotal: 110000\nTotal: 210000"
    raw = parse_invoice_text(text)
    assert raw["subtotal"] == "100000"
    assert raw["total"] == "" and raw["unresolved_labels"] == ["total"]
    assert review_invoice_fields(raw)["status"] == "INCOMPLETE"
    assert parse_invoice_text("99999999\n88888888\n77777777")["total"] == ""


def test_currency_and_incomplete_line_items_are_not_inferred():
    assert review_invoice_fields({**RAW, "currency": "USD"})["status"] == "UNSUPPORTED_CURRENCY"
    result = review_invoice_fields({**RAW, "line_items": [{"description": "Unknown row"}]})
    assert result["status"] == "INCOMPLETE"
    assert "line_items.0.amount" in result["missing_fields"]


def test_xml_no_signature_or_schema_approval_and_no_ledger(tmp_path, monkeypatch):
    need_solver()
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "example.xml"
    path.write_text("<Invoice><InvoiceNo>EXAMPLE</InvoiceNo><Subtotal>100000</Subtotal>"
                    "<TaxAmount>10000</TaxAmount><TotalAmount>110000</TotalAmount></Invoice>")
    result = inspect_invoice_file(path)
    assert result["source"]["engine"] == "xml_tag_parser"
    assert result["status"] == "SAT" and result["candidate_values"]["total"] == 110000
    assert result["review_required"] and "audit_status" not in result["raw_fields"]
    assert not (tmp_path / "invoice_registry.db").exists()
    assert result["source"]["sha256"]


@pytest.mark.parametrize("body, missing", [
    ("<Subtotal>100000</Subtotal><TotalAmount>110000</TotalAmount>", "tax"),
    ("<Subtotal>100000</Subtotal><TaxAmount>-10000</TaxAmount><TotalAmount>90000</TotalAmount>", "tax"),
    ("<Subtotal>100000</Subtotal><TaxAmount>10000</TaxAmount><TotalAmount>110000</TotalAmount><TotalAmount>210000</TotalAmount>", "total"),
])
def test_xml_missing_negative_and_ambiguous_totals_are_preserved(tmp_path, body, missing):
    path = tmp_path / "example.xml"
    path.write_text(f"<Invoice>{body}</Invoice>")
    result = inspect_invoice_file(path)
    assert result["status"] == "INCOMPLETE" and missing in result["missing_fields"]
    assert result["candidate_values"] is None


def test_xml_item_defaults_do_not_hide_missing_fields(tmp_path):
    path = tmp_path / "example.xml"
    path.write_text("<Invoice><Item><Description>Unknown</Description></Item>"
                    "<Subtotal>0</Subtotal><TaxAmount>0</TaxAmount><TotalAmount>0</TotalAmount></Invoice>")
    result = inspect_invoice_file(path)
    assert result["status"] == "INCOMPLETE"
    assert "line_items.0.quantity" in result["missing_fields"]


def test_native_ocr_tokens_are_preserved_and_no_boxes_are_invented(tmp_path, monkeypatch):
    need_solver()
    from nesy_docai.intake.vision_ocr import MacOSVisionEngine
    from nesy_docai.intake.tesseract_ocr import TesseractOCREngine
    tokens = [{"text": text, "bbox": [0, i * 30, 200, i * 30 + 20], "confidence": 0.8}
              for i, text in enumerate(["Subtotal: 100000", "Tax: 10000", "Total: 110000"])]
    monkeypatch.setattr("nesy_docai.service.platform.system", lambda: "Darwin")
    monkeypatch.setattr(MacOSVisionEngine, "run_ocr", lambda self, path: tokens)
    monkeypatch.setattr(TesseractOCREngine, "run_ocr", lambda *args: pytest.fail("Unexpected fallback"))
    path = tmp_path / "synthetic.png"
    path.write_bytes(b"fixture; OCR is mocked")
    result = inspect_invoice_file(path)
    assert result["status"] == "SAT" and result["review_required"]
    assert result["ocr_tokens"] == tokens
    assert "bboxes" not in result["raw_fields"]


def test_total_ocr_failure_is_explicit(tmp_path, monkeypatch):
    from nesy_docai.intake.tesseract_ocr import TesseractOCREngine
    monkeypatch.setattr("nesy_docai.service.platform.system", lambda: "Linux")
    monkeypatch.setattr(TesseractOCREngine, "run_ocr", lambda *args: {"full_text": "", "tokens": []})
    path = tmp_path / "unreadable.png"
    path.write_bytes(b"mock")
    result = inspect_invoice_file(path)
    assert result["status"] == "OCR_FAILED" and result["candidate_values"] is None


def test_cli_export_retains_failed_rows_and_refuses_overwrite(tmp_path):
    need_solver()
    from nesy_docai.cli import main
    fields = tmp_path / "fields.json"
    fields.write_text(json.dumps({**RAW, "total": "210000"}))
    output = tmp_path / "review.json"
    assert main([str(fields), "--fields-json", "-o", str(output)]) == 2
    records = json.loads(output.read_text())
    assert records[0]["status"] == "UNSAT" and records[0]["raw_fields"]["total"] == "210000"
    before = output.read_bytes()
    with pytest.raises(SystemExit):
        main([str(fields), "--fields-json", "-o", str(output)])
    assert output.read_bytes() == before


@pytest.mark.parametrize("output_format", ["csv", "xlsx"])
def test_cli_accounting_exports_are_review_candidates(tmp_path, output_format):
    need_solver()
    if output_format == "xlsx":
        pytest.importorskip("openpyxl")
    from nesy_docai.cli import main
    fields = tmp_path / "fields.json"
    fields.write_text(json.dumps(RAW))
    output = tmp_path / f"review.{output_format}"
    assert main([str(fields), "--fields-json", "-o", str(output), "-f", output_format]) == 0
    assert output.stat().st_size > 0

