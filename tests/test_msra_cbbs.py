"""Unit tests for Counterfactual Bottleneck Binary Search (CBBS) engine."""

import pytest
from structured_llm.msra.cbbs import CBBSController, classify_subgoal_capability
from structured_llm.msra.types import (
    CapabilityTag,
    Decision,
    ReasoningNode,
    VerificationStatus,
)


def test_classify_subgoal_capability():
    assert classify_subgoal_capability("Break problem into 3 parts") == CapabilityTag.DECOMPOSE
    assert classify_subgoal_capability("Solve the quadratic equation x^2 - 5x + 6 = 0") == CapabilityTag.SYMBOLIC_CALC
    assert classify_subgoal_capability("Verify that probability is between 0 and 1") == CapabilityTag.SANITY_CHECK
    assert classify_subgoal_capability("Apply Fermat's Little Theorem") == CapabilityTag.DOMAIN_FACT
    assert classify_subgoal_capability("Prove that sqrt(2) is irrational by contradiction") == CapabilityTag.DEEP_DEDUCTION


def test_cbbs_already_correct_zero_intervention():
    # If the initial trajectory already reaches gold answer, return None (zero help needed)
    nodes = [
        ReasoningNode(
            step_id=1,
            subgoal="Calculate 5 * 10",
            capability_tag=CapabilityTag.SYMBOLIC_CALC,
            decision=Decision.SOLVE_LOCAL,
            output_var={"ans": "50"},
        )
    ]

    cbbs = CBBSController(
        rollout_continuation=lambda p, pref: [],
        extract_answer=lambda tr: "50",
        is_correct=lambda cand, gold: cand == gold,
        helper_dispatch=lambda cap, q: ("50", 0.1),
    )

    bottleneck = cbbs.search_bottleneck("Problem", nodes, "50")
    assert bottleneck is None


def test_cbbs_finds_bottleneck_step():
    # Trajectory of 3 steps: step 1 (ok), step 2 (failed algebra), step 3 (wrong final answer)
    node1 = ReasoningNode(
        step_id=1,
        subgoal="Define variables",
        capability_tag=CapabilityTag.DECOMPOSE,
        decision=Decision.SOLVE_LOCAL,
        output_var={"x": "10"},
    )
    node2 = ReasoningNode(
        step_id=2,
        subgoal="Solve difficult polynomial 3*x^2 - 12 = 0",
        capability_tag=CapabilityTag.SYMBOLIC_CALC,
        decision=Decision.SOLVE_LOCAL,
        output_var={"y": "99"},  # Flawed local result! Correct is 2
    )
    node3 = ReasoningNode(
        step_id=3,
        subgoal="Compute final total x + y",
        capability_tag=CapabilityTag.SYMBOLIC_CALC,
        decision=Decision.SOLVE_LOCAL,
        output_var={"ans": "109"},  # Wrong! Should be 12
    )
    initial_traj = [node1, node2, node3]

    def mock_rollout(problem, prefix):
        # If prefix contains corrected step 2 where y = 2, step 3 computes 10 + 2 = 12
        last_step = prefix[-1]
        if last_step.step_id == 2 and "2" in last_step.execution_result:
            return [
                ReasoningNode(
                    step_id=3,
                    subgoal="Compute final total x + y",
                    capability_tag=CapabilityTag.SYMBOLIC_CALC,
                    decision=Decision.SOLVE_LOCAL,
                    output_var={"ans": "12"},
                )
            ]
        # Otherwise continues with flawed logic
        return [
            ReasoningNode(
                step_id=3,
                subgoal="Compute final total x + y",
                capability_tag=CapabilityTag.SYMBOLIC_CALC,
                decision=Decision.SOLVE_LOCAL,
                output_var={"ans": "109"},
            )
        ]

    def mock_extract(traj):
        if traj and "ans" in traj[-1].output_var:
            return traj[-1].output_var["ans"]
        return None

    def mock_helper(cap, query):
        if "polynomial" in query:
            return "2", 0.1
        return "0", 0.0

    cbbs = CBBSController(
        rollout_continuation=mock_rollout,
        extract_answer=mock_extract,
        is_correct=lambda cand, gold: cand == gold,
        helper_dispatch=mock_helper,
    )

    bottleneck = cbbs.search_bottleneck("Find x + y", initial_traj, "12")
    assert bottleneck == 2

    # Verify hybrid trace synthesis
    hybrid = cbbs.synthesize_hybrid_trace(initial_traj, bottleneck_step=2, helper_response="2")
    assert len(hybrid) == 3
    assert hybrid[0].decision == Decision.SOLVE_LOCAL
    assert hybrid[1].decision == Decision.ASK_HELP
    assert hybrid[1].execution_result == "2"
    assert hybrid[1].cost == 0.1
