"""
Human-In-The-Loop (HITL) Accountant Review & Verification Workbench.
Allows accountants to review flagged/low-confidence invoices, make manual corrections,
re-run Z3 Presburger SMT constraint solving in real-time, and approve/reject invoice records.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from nesy_docai.solver.z3_engine import solve_invoice, SolverResult
from nesy_docai.fraud_checker import VietnameseTaxIDValidator
from nesy_docai.lattice.generator import CandidateLatticeGenerator

logger = logging.getLogger("nesy_docai.hitl_workbench")


@dataclass
class AccountantReviewItem:
    file_name: str
    invoice_id: str
    seller_tax_id: str
    seller_name: str
    invoice_date: str
    description_summary: str
    subtotal: Any
    tax: Any
    tax_rate: str
    total: Any
    audit_status: str
    confidence_score: float
    review_status: str = "PENDING_REVIEW"  # 'PENDING_REVIEW' | 'APPROVED' | 'REJECTED' | 'CORRECTED'
    accountant_notes: str = ""
    original_data: Dict[str, Any] = field(default_factory=dict)
    z3_certificate: Optional[Dict[str, Any]] = None


class AccountantHITLWorkbench:
    """
    Manager for Accountant Human-In-The-Loop Verification Workflow.
    """

    def __init__(self):
        self.items: List[AccountantReviewItem] = []
        self.mst_validator = VietnameseTaxIDValidator()
        self.lattice_gen = CandidateLatticeGenerator()

    def load_records(self, records: List[Dict[str, Any]]) -> List[AccountantReviewItem]:
        """
        Loads invoice audit records into review queue.
        Flags items needing accountant attention based on confidence, solver status, or fraud risk.
        """
        self.items.clear()

        for rec in records:
            status = rec.get("audit_status", "UNKNOWN")
            conf = float(rec.get("confidence_score", rec.get("confidence", 1.0)))
            risk_level = rec.get("fraud_risk_level", "LOW")

            # Determine initial review status
            if rec.get("is_xml") or status == "VERIFIED_SAT" and conf >= 0.9 and risk_level == "LOW":
                rev_status = "AUTO_APPROVED"
            else:
                rev_status = "PENDING_REVIEW"

            item = AccountantReviewItem(
                file_name=rec.get("file_name", rec.get("source_file", "unknown")),
                invoice_id=rec.get("invoice_id", ""),
                seller_tax_id=rec.get("seller_tax_id", ""),
                seller_name=rec.get("seller_name", ""),
                invoice_date=rec.get("invoice_date", ""),
                description_summary=rec.get("description_summary", ""),
                subtotal=rec.get("subtotal", 0),
                tax=rec.get("tax", 0),
                tax_rate=rec.get("tax_rate", "10%"),
                total=rec.get("total", 0),
                audit_status=status,
                confidence_score=conf,
                review_status=rev_status,
                original_data=rec,
                z3_certificate=rec.get("certificate")
            )
            self.items.append(item)

        logger.info(
            "Loaded %d invoice items into HITL workbench (%d auto-approved, %d pending review).",
            len(self.items),
            sum(1 for i in self.items if i.review_status == "AUTO_APPROVED"),
            sum(1 for i in self.items if i.review_status == "PENDING_REVIEW")
        )
        return self.items

    def apply_manual_correction(
        self,
        item_index: int,
        corrected_fields: Dict[str, Any],
        accountant_notes: str = ""
    ) -> AccountantReviewItem:
        """
        Applies manual field edits by accountant and re-evaluates Z3 SMT & MST validity in real-time.
        """
        if item_index < 0 or item_index >= len(self.items):
            raise IndexError(f"Review item index {item_index} out of range (total items: {len(self.items)})")

        item = self.items[item_index]

        # Apply updated fields
        if "seller_tax_id" in corrected_fields:
            item.seller_tax_id = str(corrected_fields["seller_tax_id"]).strip().replace("-", "")
        if "seller_name" in corrected_fields:
            item.seller_name = str(corrected_fields["seller_name"]).strip()
        if "description_summary" in corrected_fields:
            item.description_summary = str(corrected_fields["description_summary"]).strip()
        if "subtotal" in corrected_fields:
            item.subtotal = corrected_fields["subtotal"]
        if "tax" in corrected_fields:
            item.tax = corrected_fields["tax"]
        if "tax_rate" in corrected_fields:
            item.tax_rate = str(corrected_fields["tax_rate"]).strip()
        if "total" in corrected_fields:
            item.total = corrected_fields["total"]

        item.accountant_notes = accountant_notes

        # Re-run Z3 SMT Constraint Solver on corrected numerical values
        raw_edited = {
            "invoice_id": item.invoice_id,
            "seller_tax_id": item.seller_tax_id,
            "seller_name": item.seller_name,
            "subtotal": str(item.subtotal),
            "tax": str(item.tax),
            "total": str(item.total),
            "line_items": [{"description": item.description_summary, "quantity": "1", "amount": str(item.subtotal)}]
        }

        fields = self.lattice_gen.build_lattice_from_raw(raw_edited)
        solver_res: SolverResult = solve_invoice(fields)

        if solver_res.status == "SAT":
            item.audit_status = "VERIFIED_HUMAN_CORRECTED_SAT"
            item.review_status = "APPROVED"
            item.z3_certificate = solver_res.certificate
            logger.info("Human correction for item [%d] %s passed Z3 Presburger verification!", item_index, item.invoice_id)
        else:
            item.audit_status = f"FLAGGED_MANUAL_{solver_res.status}"
            item.review_status = "CORRECTED_UNSAT"
            item.z3_certificate = solver_res.certificate
            logger.warning("Human correction for item [%d] %s failed Z3 verification: %s", item_index, item.invoice_id, solver_res.status)

        return item

    def approve_item(self, item_index: int, notes: str = "") -> AccountantReviewItem:
        """Manually approve an invoice item."""
        if item_index < 0 or item_index >= len(self.items):
            raise IndexError("Index out of bounds")
        item = self.items[item_index]
        item.review_status = "APPROVED"
        if notes:
            item.accountant_notes = notes
        return item

    def reject_item(self, item_index: int, reason: str = "") -> AccountantReviewItem:
        """Reject an invoice item."""
        if item_index < 0 or item_index >= len(self.items):
            raise IndexError("Index out of bounds")
        item = self.items[item_index]
        item.review_status = "REJECTED"
        item.accountant_notes = reason
        return item

    def get_approved_records(self) -> List[Dict[str, Any]]:
        """Returns dictionary records for all approved / auto-approved invoices ready for export."""
        approved = []
        for item in self.items:
            if item.review_status in ["APPROVED", "AUTO_APPROVED"]:
                rec = dict(item.original_data)
                rec.update({
                    "file_name": item.file_name,
                    "invoice_id": item.invoice_id,
                    "seller_tax_id": item.seller_tax_id,
                    "seller_name": item.seller_name,
                    "invoice_date": item.invoice_date,
                    "description_summary": item.description_summary,
                    "subtotal": item.subtotal,
                    "tax": item.tax,
                    "tax_rate": item.tax_rate,
                    "total": item.total,
                    "audit_status": item.audit_status,
                    "accountant_notes": item.accountant_notes,
                    "certificate": item.z3_certificate
                })
                approved.append(rec)
        return approved
