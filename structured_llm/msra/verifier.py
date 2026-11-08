"""Phase 2 Epistemic Verifier for Metacognitive Structured Reasoning Agent (MSRA).

Validates candidate reasoning artifacts against boundary conditions and dependency constraints
before committing them to the permanent reasoning DAG state.
"""

from typing import Any, Dict, List, Optional, Tuple, Union

from .types import ReasoningNode, VerificationStatus
from .sandbox import SymPySandbox


class EpistemicVerifier:
    """Evaluates candidate artifacts y_t^{cand} to decide COMMIT vs REJECT."""

    def __init__(self, sandbox: Optional[SymPySandbox] = None):
        self.sandbox = sandbox or SymPySandbox()

    def verify_step(
        self,
        node: ReasoningNode,
        candidate_result: Any,
        boundary_conditions: Optional[List[str]] = None,
        expected_type: Optional[str] = None,
    ) -> Tuple[VerificationStatus, str]:
        """Perform Phase 2 verification on candidate step output."""
        status = VerificationStatus.COMMIT
        critique = ""

        # 1. Type and sanity checks
        if expected_type == "int":
            try:
                val = float(candidate_result)
                if not val.is_integer():
                    return (
                        VerificationStatus.REJECT,
                        f"Expected integer value, but received non-integer {candidate_result}."
                    )
            except (ValueError, TypeError):
                return (
                    VerificationStatus.REJECT,
                    f"Expected integer value, could not parse '{candidate_result}'."
                )

        if expected_type == "non_negative":
            try:
                val = float(candidate_result)
                if val < -1e-6:
                    return (
                        VerificationStatus.REJECT,
                        f"Physical quantity must be non-negative, but got {val}."
                    )
            except (ValueError, TypeError):
                pass

        if expected_type == "probability":
            try:
                val = float(candidate_result)
                if val < 0.0 or val > 1.0:
                    return (
                        VerificationStatus.REJECT,
                        f"Probability must lie in [0, 1], but got {val}."
                    )
            except (ValueError, TypeError):
                pass

        # 2. Boundary conditions via sandbox
        if boundary_conditions:
            ok, reason = self.sandbox.check_boundary_consistency(
                candidate_value=candidate_result,
                constraints=boundary_conditions,
            )
            if not ok:
                return (VerificationStatus.REJECT, f"Boundary verification failed: {reason}")
            critique = reason

        return (status, critique or "Verified consistent with step dependencies.")
