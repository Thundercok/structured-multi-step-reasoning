"""
End-to-End Pipeline Orchestrator for NeSy-DocAI with 4-Layer Anti-Fraud Defense Shield
Connects Intake Readers -> Candidate Lattice Generator -> Pure Presburger Z3 Solver -> Fraud Risk Scorer -> Output Exporters

Production-hardened: No mock data injection, proper error handling, structured logging.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Literal, Optional

from nesy_docai.intake.pdf_reader import PDFReaderEngine
from nesy_docai.intake.vision_ocr import MacOSVisionEngine
from nesy_docai.intake.tesseract_ocr import TesseractOCREngine
from nesy_docai.intake.qwen_ocr import QwenVLEngine
from nesy_docai.intake.xml_reader import EInvoiceXMLReaderEngine

from nesy_docai.lattice.generator import CandidateLatticeGenerator, InvoiceFields
from nesy_docai.solver.z3_engine import solve_invoice, SolverResult
from nesy_docai.fraud_checker import FraudRiskScorer, FraudAuditResult
from nesy_docai.exporter import AuditExcelExporter

logger = logging.getLogger("nesy_docai.pipeline")


class OCRExtractionError(Exception):
    """Raised when all OCR engines fail to extract text from a document."""
    pass


@dataclass
class ProcessingResult:
    """Structured result from processing a single invoice file."""
    file_path: str
    status: Literal["SUCCESS", "OCR_FAILED", "SOLVER_UNSAT", "PARTIAL", "ERROR", "XML_DIRECT"]
    data: Optional[Dict[str, Any]] = None
    errors: List[str] = field(default_factory=list)
    confidence: float = 0.0


class NeSyInvoicePipeline:
    def __init__(self):
        self.pdf_reader = PDFReaderEngine()
        self.mac_vision = MacOSVisionEngine()
        self.tesseract = TesseractOCREngine()
        self.qwen_vlm = QwenVLEngine()
        self.xml_reader = EInvoiceXMLReaderEngine()
        self.lattice_gen = CandidateLatticeGenerator()
        self.fraud_scorer = FraudRiskScorer()
        self.exporter = AuditExcelExporter()

    def extract_raw_fields_from_file(self, filepath: str) -> Dict[str, Any]:
        """
        Multi-Engine Intake Router: Extracts text tokens & candidate strings from file.
        Supports XML e-invoices (Thông tư 78), PDF digital text, macOS Vision, and Tesseract OCR.
        Raises OCRExtractionError if all engines fail — never injects mock/fake data.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Invoice file not found: {filepath}")

        filename = os.path.basename(filepath)
        ext = os.path.splitext(filename)[1].lower()
        invoice_id = f"INV-{abs(hash(filename)) % 100000:05d}"

        # 0. XML e-Invoice Direct Fast Path (Zero OCR Error)
        if ext == ".xml" or self.xml_reader.is_xml_file(filepath):
            try:
                xml_data = self.xml_reader.process_xml(filepath)
                logger.info("XML e-invoice parsing successful for %s", filename)
                return xml_data
            except Exception as e:
                logger.warning("XML e-invoice parsing failed for %s: %s", filename, e)

        # 1. PDF Digital Text Fast Path
        if ext == ".pdf":
            try:
                pdf_res = self.pdf_reader.process_pdf(filepath)
                text = pdf_res.get("full_text", "")
                if text and text.strip():
                    logger.info("PDF text extraction successful for %s", filename)
                    parsed = self._extract_schema_from_text(text)
                    parsed["invoice_id"] = invoice_id
                    return parsed
            except Exception as e:
                logger.warning("PDF reader failed for %s: %s", filename, e)

        # 2. macOS Native Vision API
        try:
            mac_tokens = self.mac_vision.run_ocr(filepath)
            if mac_tokens:
                full_text = "\n".join([t["text"] for t in mac_tokens if "text" in t])
                if full_text.strip():
                    logger.info("macOS Vision OCR successful for %s (%d tokens)", filename, len(mac_tokens))
                    parsed = self._extract_schema_from_text(full_text)
                    parsed["invoice_id"] = invoice_id
                    return parsed
        except Exception as e:
            logger.warning("macOS Vision OCR failed for %s: %s", filename, e)

        # 3. Tesseract OCR Fallback
        try:
            tess_res = self.tesseract.run_ocr(filepath)
            if tess_res.get("full_text") and tess_res["full_text"].strip():
                logger.info("Tesseract OCR successful for %s", filename)
                parsed = self._extract_schema_from_text(tess_res["full_text"])
                parsed["invoice_id"] = invoice_id
                return parsed
        except Exception as e:
            logger.warning("Tesseract OCR failed for %s: %s", filename, e)

        # All engines failed — raise error instead of injecting mock data
        logger.error("All OCR engines failed for %s. No data extracted.", filename)
        raise OCRExtractionError(
            f"All OCR engines (PDF reader, macOS Vision, Tesseract) failed to extract "
            f"readable text from: {filepath}"
        )

    def _extract_schema_from_text(self, text: str) -> Dict[str, Any]:
        """Extract structured invoice fields from raw OCR text using regex heuristics."""
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        subtotal_val = None
        tax_val = None
        total_val = None
        seller_tax_id = None
        seller_name = None
        invoice_date = None
        line_items = []

        # Extract seller tax ID (MST)
        tax_match = re.search(r'(MST|Mã số thuế|Tax Code)[:\s]*([0-9\-]{10,14})', text, re.IGNORECASE)
        if tax_match:
            seller_tax_id = tax_match.group(2).replace("-", "")

        # Extract invoice date
        date_match = re.search(r'(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})', text)
        if date_match:
            invoice_date = date_match.group(1)

        # Extract seller name (first non-empty line that looks like a company name)
        for line in lines:
            if any(kw in line.upper() for kw in ["CÔNG TY", "CTY", "COMPANY", "CO.", "CORP"]):
                seller_name = line.strip()
                break

        # Extract monetary amounts using keyword-anchored line scanning
        for line in lines:
            line_clean_nums = []
            for n in re.findall(r'\b\d+[\d\.,\s]*\b', line):
                num_digits = re.sub(r'[^\d]', '', n)
                if num_digits and 4 <= len(num_digits) < 15:
                    val = int(num_digits)
                    if val > 0:
                        line_clean_nums.append(val)

            line_lower = line.lower()
            if any(k in line_lower for k in ["cộng tiền hàng", "tiền hàng", "subtotal", "net amount"]):
                if line_clean_nums:
                    subtotal_val = line_clean_nums[-1]
            elif any(k in line_lower for k in ["tiền thuế", "thuế gtgt", "vat", "tax amount"]):
                if line_clean_nums:
                    tax_val = line_clean_nums[-1]
            elif any(k in line_lower for k in ["tổng cộng", "tổng tiền", "total", "amount due", "grand total"]):
                if line_clean_nums:
                    total_val = line_clean_nums[-1]

        # Fallback: use sorted numbers if keyword anchoring didn't find all fields
        if subtotal_val is None or total_val is None:
            numbers = re.findall(r'\b\d+[\d\.,\s]*\b', text)
            clean_nums = []
            for n in numbers:
                num_str = re.sub(r'[^\d]', '', n)
                if num_str and 4 <= len(num_str) < 15:
                    clean_nums.append(int(num_str))

            if len(clean_nums) >= 3:
                if total_val is None:
                    total_val = max(clean_nums)
                if subtotal_val is None:
                    subtotal_val = sorted(clean_nums)[-2] if len(clean_nums) > 1 else total_val
                if tax_val is None:
                    tax_val = total_val - subtotal_val if total_val > subtotal_val else None

        # Extract line items from text (basic: look for lines with quantity × price patterns)
        item_pattern = re.compile(r'(.+?)\s+(\d+)\s*[xX×]\s*([\d\.,]+)\s*=?\s*([\d\.,]+)?')
        for line in lines:
            m = item_pattern.match(line)
            if m:
                line_items.append({
                    "description": m.group(1).strip(),
                    "quantity": m.group(2),
                    "unit_price": re.sub(r'[^\d]', '', m.group(3)),
                    "amount": re.sub(r'[^\d]', '', m.group(4)) if m.group(4) else "",
                })

        # If no structured line items found, use description lines between header and totals
        if not line_items:
            for line in lines[1:]:
                line_lower = line.lower()
                if any(k in line_lower for k in ["cộng", "tổng", "subtotal", "total", "thuế", "mst", "tax"]):
                    break
                if len(line) > 3 and not line.isdigit():
                    line_items.append({"description": line, "quantity": "1", "unit_price": "", "amount": ""})

        return {
            "invoice_id": "INV-DETECTED",
            "invoice_date": invoice_date or "",
            "seller_tax_id": seller_tax_id or "",
            "seller_name": seller_name or "",
            "line_items": line_items,
            "subtotal": str(subtotal_val) if subtotal_val else "",
            "tax": str(tax_val) if tax_val else "",
            "total": str(total_val) if total_val else "",
        }

    def process_file(self, filepath: str) -> Dict[str, Any]:
        """
        Processes a single file: Intake (XML/PDF/OCR) -> Candidate Lattice -> Z3 Solver -> 4-Layer Fraud Audit.
        Returns a result dict. Raises OCRExtractionError on total OCR failure.
        """
        logger.info("Processing file: %s", os.path.basename(filepath))

        raw_data = self.extract_raw_fields_from_file(filepath)

        # XML direct fast-path
        if raw_data.get("is_xml"):
            output_record = dict(raw_data)
            output_record["file_name"] = os.path.basename(filepath)
            output_record["certificate"] = {
                "smt_status": "XML_EXACT",
                "proof_formula": "100% Exact XML e-Invoice Schema Data (NĐ 123 / TT 78)",
                "constraints_verified": ["XML schema exactness"]
            }
            fraud_audit: FraudAuditResult = self.fraud_scorer.audit_invoice_record(output_record, file_name=os.path.basename(filepath))
            output_record.update({
                "fraud_risk_score": fraud_audit.risk_score,
                "fraud_risk_level": fraud_audit.risk_level,
                "duplicate_flag": fraud_audit.duplicate_flag,
                "mst_valid": fraud_audit.mst_valid,
                "fraud_alerts": fraud_audit.fraud_alerts,
                "fingerprint_hash": fraud_audit.fingerprint_hash
            })
            return output_record

        fields = self.lattice_gen.build_lattice_from_raw(raw_data)

        # FRESH Solver() called internally by solve_invoice
        result: SolverResult = solve_invoice(fields)

        # Build description summary from line items
        descriptions = [
            item.get("description", "").strip()
            for item in raw_data.get("line_items", [])
            if item.get("description", "").strip()
        ]
        description_summary = "; ".join(descriptions)

        output_record = {
            "file_name": os.path.basename(filepath),
            "invoice_id": raw_data.get("invoice_id"),
            "invoice_date": raw_data.get("invoice_date"),
            "seller_tax_id": raw_data.get("seller_tax_id"),
            "seller_name": raw_data.get("seller_name"),
            "description_summary": description_summary,
            "audit_status": "VERIFIED_SAT" if result.status == "SAT" else f"FLAGGED_{result.status}",
            "certificate": result.certificate
        }

        if result.status == "SAT" and result.values:
            output_record.update({
                "subtotal": result.values.get("subtotal"),
                "tax": result.values.get("tax"),
                "tax_rate": result.values.get("tax_rate"),
                "total": result.values.get("total"),
                "line_amounts": result.values.get("line_amounts")
            })
            logger.info("Z3 solver: SAT — invoice %s verified", raw_data.get("invoice_id"))
        else:
            output_record.update({
                "subtotal": raw_data.get("subtotal"),
                "tax": raw_data.get("tax"),
                "tax_rate": "N/A",
                "total": raw_data.get("total")
            })
            logger.warning("Z3 solver: %s — invoice %s flagged", result.status, raw_data.get("invoice_id"))

        # Run 4-Layer Anti-Fraud Audit Engine
        fraud_audit: FraudAuditResult = self.fraud_scorer.audit_invoice_record(output_record, file_name=os.path.basename(filepath))
        output_record.update({
            "fraud_risk_score": fraud_audit.risk_score,
            "fraud_risk_level": fraud_audit.risk_level,
            "duplicate_flag": fraud_audit.duplicate_flag,
            "mst_valid": fraud_audit.mst_valid,
            "fraud_alerts": fraud_audit.fraud_alerts,
            "fingerprint_hash": fraud_audit.fingerprint_hash
        })

        return output_record

    def process_file_safe(self, filepath: str) -> ProcessingResult:
        """
        Safe wrapper around process_file that catches exceptions and returns ProcessingResult.
        Used by batch processor to isolate per-file errors.
        """
        try:
            record = self.process_file(filepath)
            status = "XML_DIRECT" if record.get("is_xml") else ("SUCCESS" if record.get("audit_status") == "VERIFIED_SAT" else "SOLVER_UNSAT")
            return ProcessingResult(
                file_path=filepath,
                status=status,
                data=record,
                confidence=1.0 if (record.get("is_xml") or status == "SUCCESS") else 0.5
            )
        except OCRExtractionError as e:
            logger.error("OCR failed for %s: %s", filepath, e)
            return ProcessingResult(
                file_path=filepath,
                status="OCR_FAILED",
                errors=[str(e)],
                confidence=0.0
            )
        except Exception as e:
            logger.error("Unexpected error processing %s: %s", filepath, e, exc_info=True)
            return ProcessingResult(
                file_path=filepath,
                status="ERROR",
                errors=[str(e)],
                confidence=0.0
            )

    def process_folder(self, folder_path: str) -> List[Dict[str, Any]]:
        """
        Processes an entire directory of invoices with per-file independent solver execution & fraud auditing.
        Skips files that fail OCR instead of crashing the entire batch.
        """
        results = []
        path = Path(folder_path)
        if not path.exists():
            logger.error("Folder not found: %s", folder_path)
            return []

        valid_exts = {".png", ".jpg", ".jpeg", ".pdf", ".xml"}
        files = sorted([p for p in path.iterdir() if p.suffix.lower() in valid_exts])
        logger.info("Found %d invoice files in %s", len(files), folder_path)

        for idx, file_path in enumerate(files, 1):
            result = self.process_file_safe(str(file_path))
            if result.data:
                results.append(result.data)
            else:
                logger.warning("[%d/%d] Skipped %s: %s", idx, len(files), file_path.name,
                               "; ".join(result.errors))

            if idx % 10 == 0 or idx == len(files):
                logger.info("Progress: %d/%d files processed", idx, len(files))

        logger.info("Batch complete: %d/%d files successful", len(results), len(files))
        return results
