"""Unit tests for MSRA Phase 2 architecture components."""

import pytest
from structured_llm.msra import (
    CapabilityRouter,
    CapabilityTag,
    Decision,
    EpistemicVerifier,
    MetacognitiveReasoningHarness,
    ReasoningNode,
    SymPySandbox,
    VerificationStatus,
)


def test_capability_router_dispatch_and_budget():
    router = CapabilityRouter()
    router.register_helper(
        CapabilityTag.SYMBOLIC_CALC,
        lambda query: f"Computed: {query}",
        cost=0.1,
        source_id="mock_calc",
    )

    # Within budget
    res, cost, src = router.dispatch(CapabilityTag.SYMBOLIC_CALC, "2+2", remaining_budget=0.5)
    assert res == "Computed: 2+2"
    assert cost == 0.1
    assert src == "mock_calc"

    # Exceeding budget
    res_exceeded, cost_exceeded, src_exceeded = router.dispatch(
        CapabilityTag.SYMBOLIC_CALC, "2+2", remaining_budget=0.05
    )
    assert "[SYSTEM_WARNING: BUDGET_EXCEEDED]" in res_exceeded
    assert cost_exceeded == 0.0
    assert src_exceeded == "budget_guard"


def test_sympy_sandbox_equation_solving():
    sandbox = SymPySandbox()
    out = sandbox.execute_query("Solve for x: 2*x + 10 = 24")
    assert "x = 7" in out


def test_sympy_sandbox_expression_evaluation():
    sandbox = SymPySandbox()
    out = sandbox.evaluate_expression(r"\frac{10}{2} + 5")
    assert out == "10"


def test_sympy_sandbox_boundary_consistency():
    sandbox = SymPySandbox()
    ok, msg = sandbox.check_boundary_consistency(
        candidate_value=0.5,
        constraints=["0 <= x <= 1", "x >= 0"],
        var_name="x",
    )
    assert ok is True
    assert "Satisfies all 2 boundary constraint(s)" in msg

    # Out of boundary
    ok_fail, msg_fail = sandbox.check_boundary_consistency(
        candidate_value=1.5,
        constraints=["0 <= x <= 1"],
        var_name="x",
    )
    assert ok_fail is False
    assert "Violated boundary constraint" in msg_fail


def test_epistemic_verifier_types_and_bounds():
    verifier = EpistemicVerifier()
    node = ReasoningNode(
        step_id=1,
        subgoal="Calculate probability",
        capability_tag=CapabilityTag.SYMBOLIC_CALC,
        decision=Decision.SOLVE_LOCAL,
    )

    # Valid probability
    status, _ = verifier.verify_step(node, candidate_result=0.75, expected_type="probability")
    assert status == VerificationStatus.COMMIT

    # Invalid probability
    status_fail, msg = verifier.verify_step(node, candidate_result=1.25, expected_type="probability")
    assert status_fail == VerificationStatus.REJECT
    assert "Probability must lie in [0, 1]" in msg

    # Integer requirement
    status_int_fail, _ = verifier.verify_step(node, candidate_result=3.14, expected_type="int")
    assert status_int_fail == VerificationStatus.REJECT


def test_harness_end_to_end():
    harness = MetacognitiveReasoningHarness()

    def mock_generator(problem, step_idx, budget, history):
        if step_idx == 1:
            return ReasoningNode(
                step_id=1,
                subgoal="Solve linear equation for x",
                capability_tag=CapabilityTag.SYMBOLIC_CALC,
                decision=Decision.ASK_HELP,
                query_payload="Solve for x: 4*x - 8 = 16",
            )
        else:
            prev_result = history[0].execution_result
            return ReasoningNode(
                step_id=2,
                subgoal="Finalize answer",
                capability_tag=CapabilityTag.DECOMPOSE,
                decision=Decision.SOLVE_LOCAL,
                execution_result="Final answer is 6",
                output_var={"final_answer": "6"},
            )

    res = harness.solve(
        problem="Find x such that 4*x - 8 = 16",
        max_steps=5,
        initial_budget=1.0,
        model_step_generator=mock_generator,
    )

    assert res["solved"] is True
    assert res["final_answer"] == "6"
    assert res["total_steps"] == 2
    assert res["total_cost"] == 0.1
    assert "x = 6" in res["nodes"][0].execution_result
