"""Unit tests for MSRA SimPO / DPO contrastive preference synthesizer."""

import pytest
from structured_llm.msra.preference import PreferenceSynthesizer
from structured_llm.msra.types import CapabilityTag


def test_anti_laziness_pair():
    pair = PreferenceSynthesizer.create_anti_laziness_pair(
        prefix_context="<problem>Alice has 5 apples and buys 3 more.</problem>\n\n",
        step_id=1,
        subgoal="Calculate total apples",
        deps={},
        correct_local_exec="5 + 3 = 8",
        critique="Elementary arithmetic verified",
        output_var={"total": "8"},
        unnecessary_query="Evaluate 5 + 3",
        budget_remaining=2.0,
    )

    assert pair.category == "anti_laziness"
    assert pair.step_id == 1
    assert "SOLVE_LOCAL" in pair.chosen
    assert "ASK_HELP" in pair.rejected
    assert "<query_payload>Evaluate 5 + 3</query_payload>" in pair.rejected
    assert "<subgoal>Calculate total apples</subgoal>" in pair.prompt


def test_anti_conservatism_pair():
    pair = PreferenceSynthesizer.create_anti_conservatism_pair(
        prefix_context="<problem>Solve polynomial.</problem>\n\n",
        step_id=2,
        subgoal="Find roots of 9x^4 - 6x^3 + 2x - 1 = 0",
        capability=CapabilityTag.SYMBOLIC_CALC,
        deps={"alpha": "30"},
        query_payload="Solve 9*x^4 - 6*x^3 + 2*x - 1 = 0 in [0, 1]",
        failed_local_exec="x = 1/2 (hallucinated estimate)",
        budget_remaining=1.9,
    )

    assert pair.category == "anti_conservatism"
    assert pair.step_id == 2
    assert "ASK_HELP" in pair.chosen
    assert "<query_payload>Solve 9*x^4" in pair.chosen
    assert "SOLVE_LOCAL" in pair.rejected
    assert "hallucinated estimate" in pair.rejected


def test_adversarial_verification_pair():
    pair = PreferenceSynthesizer.create_adversarial_verification_pair(
        prefix_context="<problem>Probability problem.</problem>\n\n",
        step_id=3,
        subgoal="Check probability bounds",
        flawed_execution_or_helper="P(A) = 1.45",
        valid_critique_of_flaw="Violates axiom: probability cannot exceed 1.0",
        blind_commit_critique="Looks fine, proceeding",
        budget_remaining=1.5,
    )

    assert pair.category == "adversarial_verification"
    assert pair.step_id == 3
    assert 'status="REJECT"' in pair.chosen
    assert "Violates axiom" in pair.chosen
    assert 'status="COMMIT"' in pair.rejected
    assert "Looks fine" in pair.rejected
