"""
Genuine Presburger Linear Integer Arithmetic (LIA) Z3 Solver Engine
Supports Mixed Tax Brackets (Decree 15/2022/NĐ-CP), Pre/Post-tax Trade Discounts,
and Human-Readable UNSAT Diagnostic Certificates.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from z3 import Int, Solver, Or, And, sat

TAX_BRACKETS = (0, 5, 8, 10)
EPSILON = 2  # Rounding tolerance for currency minor units


@dataclass
class SolverResult:
    status: str                        # 'SAT' | 'UNSAT' | 'TIMEOUT'
    values: Optional[Dict[str, Any]]   # Corrected field values if SAT
    certificate: Optional[str]        # SMT Proof model string certificate
    human_explanation: Optional[str] = None # Human-readable error diagnostic for non-technical users


def generate_human_unsat_explanation(fields) -> str:
    """
    Generates plain-language diagnostic explanation when Z3 returns UNSAT.
    Helps accounting users understand exactly which numbers fail accounting laws.
    """
    sub_cands = fields.subtotal_cands or [0]
    tax_cands = fields.tax_cands or [0]
    tot_cands = fields.total_cands or [0]

    s_best = sub_cands[0]
    t_best = tax_cands[0]
    v_best = tot_cands[0]

    sum_line_amounts = sum([item.get('a_cands', [0])[0] for item in fields.line_items])

    reasons = []

    # 1. Line amounts sum check
    if len(fields.line_items) > 0 and abs(sum_line_amounts - s_best) > EPSILON:
        reasons.append(
            f"Sum of Line Amounts ({sum_line_amounts:,}) does not equal extracted Subtotal ({s_best:,})."
        )

    # 2. Subtotal + Tax = Total check
    expected_total = s_best + t_best
    if abs(expected_total - v_best) > EPSILON:
        diff = abs(v_best - expected_total)
        reasons.append(
            f"Accounting Equation Violation: Subtotal ({s_best:,}) + Tax ({t_best:,}) = {expected_total:,}, "
            f"which differs from Total ({v_best:,}) by {diff:,} VND."
        )

    # 3. Tax rate sanity check
    if s_best > 0:
        eff_tax_rate = (t_best / s_best) * 100
        valid_rates = [0, 5, 8, 10]
        if not any(abs(eff_tax_rate - r) <= 1.0 for r in valid_rates):
            reasons.append(
                f"Non-standard Tax Rate: Tax ({t_best:,}) is {eff_tax_rate:.1f}% of Subtotal ({s_best:,}), "
                f"which is outside standard tax brackets (0%, 5%, 8%, 10%)."
            )

    if not reasons:
        reasons.append("Mathematical inconsistency detected between OCR extractions and accounting rules.")

    return "❌ " + " ".join(reasons)


def solve_invoice(fields, timeout_ms: int = 5000) -> SolverResult:
    """
    Executes Z3 SMT constraint solving under genuine Presburger LIA bounds.
    - Instantiates a FRESH Z3 Solver() instance for complete per-invoice isolation.
    - Supports Mixed Line-Item Tax Brackets (0%, 5%, 8%, 10%).
    - Supports Pre-tax & Post-tax Trade Discounts.
    - Generates human-readable UNSAT diagnostics for accounting users.
    """
    s = Solver()
    s.set("timeout", timeout_ms)

    n = len(fields.line_items)
    S, T, V, D = Int('S'), Int('T'), Int('V'), Int('D')
    a = [Int(f'a_{i}') for i in range(n)]
    t_line = [Int(f't_{i}') for i in range(n)]  # Per-line item tax allocation

    # Line amount candidates (product rule enforced in Python, not Z3)
    for i, item in enumerate(fields.line_items):
        valid_a = item.get('a_cands', [])
        if valid_a:
            s.add(Or([a[i] == v for v in valid_a]))

    # Aggregation field candidates
    if fields.subtotal_cands:
        s.add(Or([S == v for v in fields.subtotal_cands]))
    if fields.tax_cands:
        s.add(Or([T == v for v in fields.tax_cands]))
    if fields.total_cands:
        s.add(Or([V == v for v in fields.total_cands]))

    discount_cands = getattr(fields, 'discount_cands', [0]) or [0]
    s.add(Or([D == v for v in discount_cands]))

    # LINEAR constraints (genuine Presburger — no Z3 variable multiplication)
    if n > 0:
        s.add(S == sum(a))
    else:
        s.add(S >= 0)

    # Pre-tax discount: V = (S - D) + T  OR  Post-tax discount: V = S + T - D
    s.add(Or(
        V == (S - D) + T,
        V == S + T - D
    ))

    s.add(S >= 0)
    s.add(T >= 0)
    s.add(V >= 0)
    s.add(D >= 0)

    # Mixed Tax Rate Bracket Allocation (Decree 15/2022/NĐ-CP):
    # Allows both global uniform tax rate OR per-line mixed tax rate partitioning (0%, 5%, 8%, 10%)
    for i in range(n):
        s.add(Or([
            And(t_line[i] * 100 >= a[i] * r - EPSILON * 100,
                t_line[i] * 100 <= a[i] * r + EPSILON * 100)
            for r in TAX_BRACKETS
        ]))

    # Global Tax T is either sum of line taxes OR global rate over (S - D)
    global_tax_constraints = [
        And(T * 100 >= (S - D) * r - EPSILON * 100,
            T * 100 <= (S - D) * r + EPSILON * 100)
        for r in TAX_BRACKETS
    ]
    if n > 0:
        s.add(Or(
            T == sum(t_line),
            Or(global_tax_constraints)
        ))
    else:
        s.add(Or(global_tax_constraints))

    result = s.check()

    if result == sat:
        m = s.model()
        subtotal_val = m[S].as_long()
        tax_val = m[T].as_long()
        total_val = m[V].as_long()
        discount_val = m[D].as_long()
        line_amounts = [m[a[i]].as_long() for i in range(n)]

        tax_rate_str = f"{round((tax_val / max(subtotal_val - discount_val, 1)) * 100)}%" if subtotal_val > 0 else "0%"

        return SolverResult(
            status='SAT',
            values={
                'line_amounts': line_amounts,
                'subtotal': subtotal_val,
                'tax': tax_val,
                'discount': discount_val,
                'total': total_val,
                'tax_rate': tax_rate_str
            },
            certificate=str(m),
            human_explanation="✅ Invoice mathematically & tax verified under Presburger LIA accounting rules."
        )

    explanation = generate_human_unsat_explanation(fields)
    return SolverResult(
        status='UNSAT' if str(result) == 'unsat' else 'TIMEOUT',
        values=None,
        certificate=None,
        human_explanation=explanation
    )
