"""Metacognitive Reasoning Harness for MSRA (Phase 2).

Orchestrates the 2-phase factored MDP loop:
1. Propose Subgoal & Capability Tag -> Phase 1 Gate (SOLVE_LOCAL vs ASK_HELP)
2. Execute Local or Dispatch to Router -> Phase 2 Verification Gate (COMMIT vs REJECT)
3. Update Reasoning DAG & Budget
"""

import re
from typing import Any, Callable, Dict, List, Optional

from .types import CapabilityTag, Decision, ReasoningNode, VerificationStatus
from .router import CapabilityRouter
from .sandbox import SymPySandbox
from .verifier import EpistemicVerifier


class MetacognitiveReasoningHarness:
    """Execution engine for structured DAG reasoning with help-seeking capabilities."""

    def __init__(
        self,
        router: Optional[CapabilityRouter] = None,
        verifier: Optional[EpistemicVerifier] = None,
        base_model_generate: Optional[Callable[[str, List[str]], str]] = None,
    ):
        self.router = router or CapabilityRouter()
        self.verifier = verifier or EpistemicVerifier()
        self.generate_fn = base_model_generate

        # Auto-register SymPySandbox if router does not have handlers
        if not self.router.has_helper(CapabilityTag.SYMBOLIC_CALC):
            sandbox = SymPySandbox()
            self.router.register_helper(
                CapabilityTag.SYMBOLIC_CALC,
                sandbox.execute_query,
                cost=0.1,
                source_id="h_sym",
            )
            self.router.register_helper(
                CapabilityTag.SANITY_CHECK,
                sandbox.execute_query,
                cost=0.05,
                source_id="h_sym_sanity",
            )

    def solve(
        self,
        problem: str,
        max_steps: int = 8,
        initial_budget: float = 2.0,
        model_step_generator: Optional[Callable[[str, int, float, List[ReasoningNode]], ReasoningNode]] = None,
    ) -> Dict[str, Any]:
        """Execute the multi-step metacognitive reasoning process on a problem.

        Supports custom step generator function (for testing or model integration).
        """
        dag_nodes: List[ReasoningNode] = []
        total_cost = 0.0
        budget_remaining = initial_budget
        solved = False
        final_answer = None

        for step_idx in range(1, max_steps + 1):
            if budget_remaining <= 0.0 and all(n.decision == Decision.ASK_HELP for n in dag_nodes[-2:]):
                break

            # 1. Propose node via model or generator
            if model_step_generator:
                node = model_step_generator(problem, step_idx, budget_remaining, dag_nodes)
            else:
                # Default rule-based decomposition
                node = self._default_propose_node(problem, step_idx, budget_remaining, dag_nodes)

            # 2. Phase 1 Gate: SOLVE_LOCAL vs ASK_HELP
            if node.decision == Decision.ASK_HELP:
                # Dispatch query payload to Router
                query = node.query_payload or node.subgoal
                res_str, step_cost, source = self.router.dispatch(
                    node.capability_tag,
                    query,
                    budget_remaining,
                )
                node.execution_result = res_str
                node.cost = step_cost
                node.helper_source = source
                total_cost += step_cost
                budget_remaining = max(0.0, initial_budget - total_cost)
            else:
                node.cost = 0.0
                node.helper_source = "local_model"

            # 3. Phase 2 Gate: Epistemic Verification
            status, critique = self.verifier.verify_step(
                node,
                candidate_result=node.execution_result,
            )
            node.verification_status = status
            node.critique = critique

            dag_nodes.append(node)

            # Check if problem is resolved
            if "final_answer" in node.output_var:
                solved = True
                final_answer = node.output_var["final_answer"]
                break

        return {
            "problem": problem,
            "solved": solved,
            "final_answer": final_answer,
            "nodes": dag_nodes,
            "total_steps": len(dag_nodes),
            "total_cost": round(total_cost, 4),
            "budget_remaining": round(budget_remaining, 4),
        }

    def _default_propose_node(
        self,
        problem: str,
        step_idx: int,
        budget: float,
        history: List[ReasoningNode],
    ) -> ReasoningNode:
        """Fallback rule-based node generator."""
        return ReasoningNode(
            step_id=step_idx,
            subgoal=f"Step {step_idx} analysis for problem: {problem[:40]}",
            capability_tag=CapabilityTag.SYMBOLIC_CALC,
            decision=Decision.ASK_HELP if budget >= 0.1 else Decision.SOLVE_LOCAL,
            query_payload=problem,
        )
