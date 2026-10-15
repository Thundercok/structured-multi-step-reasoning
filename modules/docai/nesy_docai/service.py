"""Headless invoice inspection, with raw evidence and bounded consistency checks.

This supported facade deliberately avoids the upstream auto-approval, fraud
score, synthetic boxes, and persistent duplicate ledger. A satisfying Z3 model
is a candidate interpretation, never proof that OCR or the invoice is correct.
"""
from __future__ import annotations

import copy
import hashlib
import platform
import re
import threading
from pathlib import Path
from typing import Any

from nesy_docai.lattice.generator import CandidateLatticeGenerator

AMOUNT_KEYS = ("subtotal", "tax", "total")
DOCUMENT_EXTENSIONS = {".xml", ".pdf", ".png", ".jpg", ".jpeg"}
_DIGITS = r"0-9OoIl|SsBZzGQ"
_AMOUNT = re.compile(rf"(?:[{_DIGITS}]+|[{_DIGITS}]{{1,3}}(?:[., ][{_DIGITS}]{{3}})+)")
_LABELS = {
    "subtotal": r"cộng tiền hàng|tiền hàng|subtotal|net amount",
    "tax": r"tiền thuế(?: gtgt)?|thuế gtgt|tax amount|vat|tax",
    "total": r"tổng cộng(?: thanh toán)?|tổng tiền(?: thanh toán)?|grand total|amount due|total",
}
_SOLVER_LOCK = threading.Lock()


def _valid_amount(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return False
    return bool(_AMOUNT.fullmatch(str(value).strip()))


def parse_invoice_text(text: str) -> dict[str, Any]:
    """Extract only explicitly labelled totals; preserve missing fields.

Repeated labels, multiple totals, decimals, and unlabelled large numbers are
left unresolved. This prototype does not reconstruct line items from prose.
"""
    raw = {key: "" for key in AMOUNT_KEYS}
    raw.update(currency="VND", line_items=[], seller_name="", invoice_id="")
    matches = {key: [] for key in AMOUNT_KEYS}
    for line in text.splitlines():
        line = line.strip()
        for key, labels in _LABELS.items():
            match = re.fullmatch(
                rf"(?:{labels})\s*[:=]?\s*(.*?)\s*(?:VND|đ|₫)?", line, re.IGNORECASE
            )
            if match:
                amount = match.group(1).strip()
                # Keep invalid readings visible instead of guessing a value.
                matches[key].append(amount)
                break
        if not raw["seller_name"] and re.search(r"công ty|company|\bcty\b", line, re.IGNORECASE):
            raw["seller_name"] = line
    for key, values in matches.items():
        if len(values) == 1:
            raw[key] = values[0]
    raw["unresolved_labels"] = [key for key, values in matches.items() if len(values) > 1]
    return raw


def review_invoice_fields(raw_fields: dict[str, Any], *, timeout_ms: int = 1000) -> dict[str, Any]:
    """Check candidate arithmetic while retaining the exact input fields."""
    if not isinstance(raw_fields, dict):
        raise ValueError("Invoice fields must be a JSON object.")
    if not isinstance(timeout_ms, int) or isinstance(timeout_ms, bool) or not 1 <= timeout_ms <= 10000:
        raise ValueError("timeout_ms must be an integer between 1 and 10000.")
    result = {
        "status": "INCOMPLETE",
        "raw_fields": copy.deepcopy(raw_fields),
        "candidate_values": None,
        "solver_model": None,
        "review_required": True,
        "evidence_scope": "development_document_inspection",
        "consistency_scope": "candidate_arithmetic_under_fixed_prototype_rules",
        "candidate_selection": "uniqueness_not_checked",
        "tax_brackets": [0, 5, 8, 10],
        "rounding_tolerance_vnd": 2,
        "notices": [
            "Đối chiếu các trường với hóa đơn gốc trước khi sử dụng.",
            "Kết quả Z3 chỉ kiểm tra tính nhất quán của các giá trị ứng viên.",
        ],
    }
    currency = raw_fields.get("currency", "VND")
    if not isinstance(currency, str) or currency.upper() != "VND":
        result.update(status="UNSUPPORTED_CURRENCY", missing_fields=[])
        return result
    missing = [key for key in AMOUNT_KEYS if not _valid_amount(raw_fields.get(key))]
    items = raw_fields.get("line_items", [])
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise ValueError("line_items must be a list of objects.")
    for i, item in enumerate(items):
        missing.extend(f"line_items.{i}.{key}" for key in ("quantity", "unit_price", "amount")
                       if not _valid_amount(item.get(key)))
    if "discount" in raw_fields and not _valid_amount(raw_fields["discount"]):
        missing.append("discount")
    result["missing_fields"] = missing
    if missing:
        return result

    from nesy_docai.solver.z3_engine import solve_invoice

    generator = CandidateLatticeGenerator()
    fields = generator.build_lattice_from_raw(raw_fields)
    # The compatibility lattice falls back to supplied amounts when products
    # disagree. Reject that fallback for the supported inspection operation.
    for i, item in enumerate(items):
        q = generator.generate_number_candidates(item["quantity"])
        p = generator.generate_number_candidates(item["unit_price"])
        a = generator.generate_number_candidates(item["amount"])
        valid = sorted({quantity * price for quantity in q for price in p} & set(a))
        if not valid:
            result.update(status="UNSAT")
            result["notices"].append(f"Dòng {i + 1}: các giá trị ứng viên không khớp số lượng × đơn giá.")
            return result
        fields.line_items[i]["a_cands"] = valid
    # The compatibility solver uses Z3's shared default context.
    with _SOLVER_LOCK:
        solved = solve_invoice(fields, timeout_ms=timeout_ms)
    result.update(status=solved.status, candidate_values=solved.values, solver_model=solved.certificate)
    if not items:
        result["notices"].append("Chưa trích xuất được các dòng hàng; chỉ kiểm tra các tổng tiền.")
    return result


def _ocr_text(tokens: list[dict[str, Any]]) -> str:
    """Group supplied OCR boxes into rows without inventing coordinates."""
    rows = []
    for token in sorted(tokens, key=lambda t: (t["bbox"][1], t["bbox"][0])):
        box = token["bbox"]
        middle = (box[1] + box[3]) / 2
        height = max(box[3] - box[1], 1)
        row = next((r for r in rows if abs(r["middle"] - middle) <= min(r["height"], height) / 2), None)
        if row is None:
            row = {"middle": middle, "height": height, "tokens": []}
            rows.append(row)
        row["tokens"].append(token)
    return "\n".join(" ".join(t["text"] for t in sorted(r["tokens"], key=lambda t: t["bbox"][0]))
                     for r in sorted(rows, key=lambda r: r["middle"]))


def inspect_invoice_file(file_path: str | Path, *, timeout_ms: int = 1000, max_pages: int = 25) -> dict[str, Any]:
    """Read one local document and return candidates requiring human review.

    XML signatures/provider schemas are not validated. PDF text is capped
    at max_pages and reports truncation. No model or network service is called.
    """
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Invoice file not found: {path}")
    if path.suffix.lower() not in DOCUMENT_EXTENSIONS:
        raise ValueError("Supported invoice files: XML, PDF, PNG, JPG, JPEG.")
    if not isinstance(max_pages, int) or isinstance(max_pages, bool) or not 1 <= max_pages <= 100:
        raise ValueError("max_pages must be an integer between 1 and 100.")
    if path.stat().st_size > 25 * 1024 * 1024:
        raise ValueError("Invoice inspection is limited to 25 MiB per file.")
    source = {"path": str(path), "filename": path.name,
              "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "extraction_truncated": False}
    text, tokens = "", []
    if path.suffix.lower() == ".xml":
        from nesy_docai.intake.xml_reader import EInvoiceXMLReaderEngine

        parsed = EInvoiceXMLReaderEngine().process_xml(str(path), preserve_raw_fields=True)
        # Exclude the legacy VERIFIED_XML_DIRECT and confidence/approval fields.
        raw = {key: value for key, value in parsed.items() if key in {
            *AMOUNT_KEYS, "currency", "discount", "invoice_id", "invoice_date",
            "seller_name", "seller_tax_id", "seller_address", "line_items",
        }}
        source["engine"] = "xml_tag_parser"
    else:
        if path.suffix.lower() == ".pdf":
            from document_intake.pdf import read_pdf

            extracted = read_pdf(path, max_pages=max_pages)
            source["extraction_truncated"] = extracted["extraction_truncated"]
            source["engine"] = "pypdf_text"
            text = extracted["full_text"]
        else:
            from nesy_docai.intake.vision_ocr import MacOSVisionEngine
            from nesy_docai.intake.tesseract_ocr import TesseractOCREngine

            tokens = MacOSVisionEngine().run_ocr(str(path)) if platform.system() == "Darwin" else []
            source["engine"] = "macos_vision"
            if tokens:
                text = _ocr_text(tokens)
            if not text.strip():
                extracted = TesseractOCREngine().run_ocr(str(path))
                tokens = extracted.get("tokens", [])
                text = _ocr_text(tokens) if tokens else extracted.get("full_text", "")
                source["engine"] = "tesseract"
        raw = parse_invoice_text(text)
    result = review_invoice_fields(raw, timeout_ms=timeout_ms)
    result.update(source=source, source_text=text, ocr_tokens=tokens)
    if path.suffix.lower() != ".xml" and not text.strip():
        result["status"] = "OCR_FAILED"
    if source["extraction_truncated"]:
        result["notices"].append(f"Chỉ đọc {max_pages} trang đầu của PDF.")
    return result
