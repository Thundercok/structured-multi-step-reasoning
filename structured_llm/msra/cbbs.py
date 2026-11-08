"""Counterfactual Bottleneck Binary Search (CBBS) Engine for MSRA.

Finds the minimal reasoning step t* in O(log K) where tool intervention
fixes a failed trajectory, synthesizing optimal hybrid SFT traces and
DPO contrastive pairs.
"""

import math
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from .types import (
    CapabilityTag,
    Decision,
    PreferencePair,
    ReasoningNode,
    VerificationStatus,
)


def classify_subgoal_capability(subgoal: str, payload: str = "") -> CapabilityTag:
    """Classify the capability tag required by a subgoal based on syntax and domain patterns."""
    text = (subgoal + " " + payload).lower()

    # Sanity check / boundary conditions
    if any(k in text for k in ["verify", "sanity check", "boundary", "check constraint", "non-negative", "domain check"]):
        return CapabilityTag.SANITY_CHECK

    # Symbolic calculation: equations, algebra, factorization, derivatives, roots
    if any(k in text for k in ["solve", "equation", "factor", "expand", "derivative", "integral", "root", "matrix", "simplify", "polynomial", "system of"]):
        return CapabilityTag.SYMBOLIC_CALC
    if any(sym in text for sym in ["=", "+", "-", "*", "/", "^", "\\sqrt", "\\frac"]) and any(c.isdigit() for c in text):
        return CapabilityTag.SYMBOLIC_CALC

    # Domain fact: lookup, theorem name, constants
    if any(k in text for k in ["theorem", "constant", "formula for", "definition of", "identity"]):
        return CapabilityTag.DOMAIN_FACT

    # Deep deduction: logic, proof, counterexample, induction
    if any(k in text for k in ["proof", "prove", "deduce", "contradiction", "induction", "counterexample"]):
        return CapabilityTag.DEEP_DEDUCTION

    # Default: local decomposition
    return CapabilityTag.DECOMPOSE


class CBBSController:
    """Counterfactual Bottleneck Binary Search (CBBS) runner.

    Given a multi-step trajectory and a problem with a gold answer, discovers the first
    critical step where local reasoning broke down and an external helper would rescue the proof.
    """

    def __init__(
        self,
        rollout_continuation: Callable[[str, List[ReasoningNode]], List[ReasoningNode]],
        extract_answer: Callable[[List[ReasoningNode]], Optional[str]],
        is_correct: Callable[[Optional[str], str], bool],
        helper_dispatch: Callable[[CapabilityTag, str], Tuple[str, float]],
    ):
        self.rollout_continuation = rollout_continuation
        self.extract_answer = extract_answer
        self.is_correct = is_correct
        self.helper_dispatch = helper_dispatch

    def search_bottleneck(
        self,
        problem: str,
        initial_trajectory: List[ReasoningNode],
        gold_answer: str,
        golden_contexts: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[int]:
        """Binary search O(log K) for the earliest step t* in [1, K] where helper intervention succeeds.

        If golden_contexts is provided (Golden-Context Guided CBBS), step m is evaluated with clean
        predecessor variable dependencies D_m to ensure search monotonicity.
        """
        k = len(initial_trajectory)
        if k == 0:
            return None

        # Check if already correct without help
        initial_ans = self.extract_answer(initial_trajectory)
        if self.is_correct(initial_ans, gold_answer):
            return None  # Solved locally, zero help needed

        low = 1
        high = k
        bottleneck_step: Optional[int] = None

        while low <= high:
            mid = (low + high) // 2
            target_node = initial_trajectory[mid - 1]

            # Construct isolated query payload for step mid
            cap = target_node.capability_tag or classify_subgoal_capability(target_node.subgoal, target_node.query_payload or "")
            query = target_node.query_payload or target_node.subgoal

            # Query helper
            helper_output, _ = self.helper_dispatch(cap, query)

            # Build hypothetical prefix up to step mid with helper intervention
            prefix_nodes: List[ReasoningNode] = []
            for idx in range(mid - 1):
                prefix_nodes.append(initial_trajectory[idx])

            # Use golden context if available to enforce clean state
            deps = target_node.deps
            if golden_contexts and (mid - 1) < len(golden_contexts):
                deps = golden_contexts[mid - 1]

            intervened_node = ReasoningNode(
                step_id=mid,
                subgoal=target_node.subgoal,
                capability_tag=cap,
                decision=Decision.ASK_HELP,
                deps=deps,
                query_payload=query,
                execution_result=helper_output,
                verification_status=VerificationStatus.COMMIT,
                critique="Intervention via Helper verified",
                output_var=target_node.output_var,
                helper_source="h_sym",
            )
            prefix_nodes.append(intervened_node)

            # Rollout remainder from mid + 1 to K
            resumed_nodes = self.rollout_continuation(problem, prefix_nodes)
            full_resumed = prefix_nodes + resumed_nodes
            resumed_ans = self.extract_answer(full_resumed)

            if self.is_correct(resumed_ans, gold_answer):
                # Success! Intervention at mid fixed the trajectory. Check if an earlier step also fixes it.
                bottleneck_step = mid
                high = mid - 1
            else:
                # Still failed; error may be earlier (bad deps) or later. Move search window forward.
                low = mid + 1

        return bottleneck_step

    def synthesize_hybrid_trace(
        self,
        base_trajectory: List[ReasoningNode],
        bottleneck_step: int,
        helper_response: str,
        helper_source: str = "h_sym",
    ) -> List[ReasoningNode]:
        """Construct a hybrid trace where steps < bottleneck are SOLVE_LOCAL and bottleneck is ASK_HELP."""
        hybrid_nodes: List[ReasoningNode] = []
        for node in base_trajectory:
            if node.step_id < bottleneck_step:
                # Kept as local execution
                hybrid_nodes.append(
                    ReasoningNode(
                        step_id=node.step_id,
                        subgoal=node.subgoal,
                        capability_tag=node.capability_tag or CapabilityTag.DECOMPOSE,
                        decision=Decision.SOLVE_LOCAL,
                        deps=node.deps,
                        execution_result=node.execution_result,
                        verification_status=VerificationStatus.COMMIT,
                        critique=node.critique or "Verified locally",
                        output_var=node.output_var,
                        cost=0.0,
                    )
                )
            elif node.step_id == bottleneck_step:
                # Intervened step: ASK_HELP
                cap = node.capability_tag or classify_subgoal_capability(node.subgoal, node.query_payload or "")
                hybrid_nodes.append(
                    ReasoningNode(
                        step_id=node.step_id,
                        subgoal=node.subgoal,
                        capability_tag=cap,
                        decision=Decision.ASK_HELP,
                        deps=node.deps,
                        query_payload=node.query_payload or node.subgoal,
                        execution_result=helper_response,
                        verification_status=VerificationStatus.COMMIT,
                        critique="Verified through external helper",
                        output_var=node.output_var,
                        helper_source=helper_source,
                        cost=0.1,
                    )
                )
            else:
                hybrid_nodes.append(node)

        return hybrid_nodes
