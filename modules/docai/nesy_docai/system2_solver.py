"""
System 2: Symbolic Reasoning Engine (Z3 SMT Presburger & LIA Constraint Solver)
Bridge interface routing to modular solver/z3_engine.py & lattice/generator.py
"""

from typing import Dict, Any
from nesy_docai.lattice.generator import CandidateLatticeGenerator
from nesy_docai.solver.z3_engine import solve_invoice
from nesy_docai.system1_vision import VisionPerceptionEngine


class SymbolicSolverEngine:
    def __init__(self, vision_engine: VisionPerceptionEngine = None, timeout_ms: int = 1000):
        self.vision_engine = vision_engine or VisionPerceptionEngine()
        self.lattice_gen = CandidateLatticeGenerator()
        self.timeout_ms = timeout_ms

    def solve_and_verify(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes Z3 SMT Linear Integer Arithmetic (LIA) Presburger constraint solving.
        - Enforces per-invoice isolated Solver() instantiation.
        - Uses Python-side product candidate filtering (NIA -> LIA conversion).
        - Multiplies tax constraints by 100 to eliminate integer division.
        """
        fields = self.lattice_gen.build_lattice_from_raw(raw_data)
        res = solve_invoice(fields, timeout_ms=self.timeout_ms)

        if res.status == "SAT" and res.values:
            line_items = raw_data.get("line_items", [])
            corrected_items = []
            line_amounts = res.values.get("line_amounts", [])

            for i, item in enumerate(line_items):
                amt = line_amounts[i] if i < len(line_amounts) else 0
                qty = int(item.get("quantity", 1)) if str(item.get("quantity", "1")).isdigit() else 1
                price = amt // qty if qty > 0 else 0

                corrected_items.append({
                    "item_id": item.get("item_id", i + 1),
                    "description": item.get("description", f"Item {i+1}"),
                    "quantity": qty,
                    "unit_price": price,
                    "amount": amt,
                    "bbox": item.get("bbox")
                })

            subtotal_val = res.values.get("subtotal", 0)
            tax_val = res.values.get("tax", 0)
            total_val = res.values.get("total", 0)
            calc_tax_rate = res.values.get("tax_rate", "0%")

            desc_summary = ", ".join([it["description"] for it in corrected_items if it.get("description")])

            proof_certificate = {
                "smt_status": "SAT",
                "decidability_domain": "LIA_Presburger_Bounded",
                "proof_formula": "Subtotal = Sum(LineAmounts) AND Total = Subtotal + Tax",
                "certificate_model": res.certificate,
                "constraints_verified": [
                    f"Line items verified: {len(corrected_items)}",
                    f"Subtotal = {subtotal_val}",
                    f"Tax = {tax_val} (Tax Rate: {calc_tax_rate})",
                    f"Total = {total_val}"
                ]
            }

            return {
                "audit_status": "VERIFIED_SAT",
                "currency": raw_data.get("currency", "VND"),
                "invoice_id": raw_data.get("invoice_id"),
                "invoice_date": raw_data.get("invoice_date"),
                "seller_tax_id": raw_data.get("seller_tax_id"),
                "vendor_tax_code": raw_data.get("seller_tax_id"),
                "seller_name": raw_data.get("seller_name"),
                "description_summary": desc_summary,
                "line_items": corrected_items,
                "subtotal": subtotal_val,
                "tax_rate": calc_tax_rate,
                "tax": tax_val,
                "tax_amount": tax_val,
                "total": total_val,
                "bboxes": raw_data.get("bboxes"),
                "proof_certificate": proof_certificate
            }

        return {
            "audit_status": f"FLAGGED_{res.status}",
            "currency": raw_data.get("currency", "VND"),
            "invoice_id": raw_data.get("invoice_id"),
            "invoice_date": raw_data.get("invoice_date"),
            "seller_tax_id": raw_data.get("seller_tax_id"),
            "vendor_tax_code": raw_data.get("seller_tax_id"),
            "seller_name": raw_data.get("seller_name"),
            "line_items": raw_data.get("line_items", []),
            "subtotal": raw_data.get("subtotal"),
            "tax": raw_data.get("tax"),
            "total": raw_data.get("total"),
            "proof_certificate": {
                "smt_status": res.status,
                "decidability_domain": "LIA_Presburger_Bounded",
                "proof_formula": "Subtotal = Sum(LineAmounts) AND Total = Subtotal + Tax",
                "certificate_model": None,
                "constraints_verified": [res.human_explanation or "FLAGGED_UNSAT: Accounting equality constraints violated."]
            }
        }
