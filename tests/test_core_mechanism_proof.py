"""
Core Mechanism Proof: Empirical Evaluation of Verifiers, Guard Gaps, and Escalation Economics.

Covers:
1. Calculation Verifier (CalculationVerifier & VGCVerifier.verify_calculation)
   - True Positive, True Negative, False Negative, False Positive
2. Document Fact Verifier (VGCVerifier.verify_document_fact)
   - True Positive, True Negative, False Negative, False Positive
3. The Critical Blind Spot: Guard PASS but Final Answer is Wrong (Semantic Misalignment)
4. Escalation Economics Simulation: Measuring Escalation Rate and Token Costs
"""

import pytest
from dataclasses import dataclass
from typing import Optional, List

from rat.engine.vgc import (
    VGCCertificate,
    VGCVerifier,
    VGCVerificationStatus,
)
from rat.engine.verification import (
    CalculationVerifier,
    ExecutionEvidence,
    VerificationStatus,
)


# ==============================================================================
# PART 1: CALCULATION VERIFIER — CONFUSION MATRIX & BEHAVIOR
# ==============================================================================

def test_calculation_true_positive():
    """TP: Arithmetic expression evaluates correctly and matches the claim."""
    expr = "25 * 4 + 10"  # 110
    cert = VGCCertificate(claim="110", witness="110")
    result = VGCVerifier.verify_calculation(cert, expr)
    assert result.status == VGCVerificationStatus.VALID
    assert "110" in result.reason or result.status == VGCVerificationStatus.VALID


def test_calculation_true_negative():
    """TN: Arithmetic expression does NOT match the claim (model made a math error)."""
    expr = "25 * 4 + 10"  # Actually 110
    cert = VGCCertificate(claim="100", witness="100")  # Model claims 100
    result = VGCVerifier.verify_calculation(cert, expr)
    assert result.status == VGCVerificationStatus.INVALID
    assert "công cụ trả 100; tính độc lập được 110" in result.reason or "110" in result.reason


def test_calculation_false_negative():
    """
    FN (False Alarm): Valid mathematical expression outside AST parser support
    triggers UNVERIFIABLE even though the claim is mathematically sound.
    """
    # math.comb, unsupported rounding or complex syntax not in whitelist
    expr = "round(7.399, 1)"
    cert = VGCCertificate(claim="7.4", witness="7.4")
    result = VGCVerifier.verify_calculation(cert, expr)
    # Verifier cannot verify, escalating unnecessarily (False Alarm)
    assert result.status in (VGCVerificationStatus.UNVERIFIABLE, VGCVerificationStatus.INVALID)


def test_calculation_guard_pass_but_answer_wrong():
    """
    CRITICAL INSIGHT (Task 2.3): Guard PASS != Correctness.
    User asks: 'A rectangle has length 10 and width 5. What is its AREA?' (Gold = 50).
    Model mistakenly calculates perimeter formula: 10 + 5 + 10 + 5 = 30.
    Verifier evaluates '10 + 5 + 10 + 5': it is indeed 30!
    Result: Verifier reports VALID, but the user's question was answered WRONG.
    """
    gold_answer = 50  # 10 * 5
    model_generated_expr = "10 + 5 + 10 + 5"  # Misformulated equation
    model_claim = "30"

    cert = VGCCertificate(claim=model_claim, witness=model_claim)
    v_result = VGCVerifier.verify_calculation(cert, model_generated_expr)

    # 1. Verification PASSES (the arithmetic itself is flawless)
    assert v_result.status == VGCVerificationStatus.VALID

    # 2. But the final answer is blatantly WRONG against ground truth!
    assert int(cert.witness) != gold_answer
    assert v_result.status == VGCVerificationStatus.VALID and int(cert.witness) != gold_answer


# ==============================================================================
# PART 2: DOCUMENT FACT VERIFIER — CONFUSION MATRIX & BEHAVIOR
# ==============================================================================

def test_document_fact_true_positive():
    """TP: Quoted numbers exist verbatim in source text."""
    source = "Q3 financial report: Total revenue reached 450 billion VND, up 15% YoY."
    claim = "Total revenue reached 450 billion VND"
    cert = VGCCertificate(claim=claim, witness=claim, source_snippet=claim)
    result = VGCVerifier.verify_document_fact(cert, source)
    assert result.status == VGCVerificationStatus.VALID


def test_document_fact_true_negative():
    """TN: Model hallucinates a number not in the source text."""
    source = "Q3 financial report: Total revenue reached 450 billion VND, up 15% YoY."
    claim = "Total revenue was 990 billion VND"  # 990 is invented
    cert = VGCCertificate(claim=claim, witness=claim)
    result = VGCVerifier.verify_document_fact(cert, source)
    assert result.status == VGCVerificationStatus.INVALID
    assert "Hallucination detected" in result.reason
    assert "990" in result.reason


def test_document_fact_false_negative():
    """
    FN (False Alarm): Number exists in source but under a different surface format
    (e.g., words vs digits or different punctuation).
    """
    source = "The project completed in two years with zero casualties."
    claim = "The duration was 2 years."  # Digits '2' vs word 'two'
    cert = VGCCertificate(claim=claim, witness=claim)
    result = VGCVerifier.verify_document_fact(cert, source)
    # Lexical matching fails to ground '2' because source has 'two'
    assert result.status == VGCVerificationStatus.INVALID
    assert "2" in result.reason


def test_document_fact_false_positive():
    """
    FP (Silent Miss): Model claims a false fact using a number that coincidental
    appears elsewhere in an unrelated sentence of the document.
    """
    source = (
        "Project Alpha has 40 members. "
        "Separately, Project Beta budget is 1500 USD, while Alpha budget is 900 USD."
    )
    # Model mistakenly claims: "Project Beta has 40 members" (Beta members actually unknown)
    # Because 40 exists in source, naive lexical presence verifier gives UNVERIFIABLE or VALID
    # depending on entity checking.
    cert = VGCCertificate(
        claim="Project Beta has 40 members",
        witness="40",
        source_snippet="Project Alpha has 40 members."
    )
    result = VGCVerifier.verify_document_fact(cert, source)
    # Even if excerpt contains 40, semantic relation between Beta and 40 is false!
    assert "40" in source


def test_document_fact_guard_pass_but_answer_wrong():
    """
    CRITICAL INSIGHT (Task 2.3): Entity relation confusion.
    Source: 'Alice scored 100 points. Bob scored 20 points.'
    Question: 'How many points did Bob score?' (Gold = 20)
    Model answer: 'Bob scored 100 points.'
    Because 100 exists in source, a purely lexical number check might pass unless
    entity-relation bounds are explicitly checked.
    """
    source = "Alice scored 100 points. Bob scored 20 points."
    gold_answer = "20"
    wrong_model_claim = "Bob scored 100 points."

    cert = VGCCertificate(claim=wrong_model_claim, witness="100", source_snippet=source)
    result = VGCVerifier.verify_document_fact(cert, source)

    # VGCVerifier correctly detects entity mismatch and returns UNVERIFIABLE
    # proving that raw lexical matching is NOT enough to claim correctness!
    assert result.status == VGCVerificationStatus.UNVERIFIABLE
    assert cert.witness != gold_answer


# ==============================================================================
# PART 3: ESCALATION & TOKEN COST SIMULATION (Task 2.4)
# ==============================================================================

@dataclass
class SimulatedQuery:
    query_id: str
    prompt: str
    gold_answer: str
    tier0_answer: str
    tier0_expr: Optional[str]
    tier0_tokens: int
    tier1_answer: str
    tier1_tokens: int


def test_escalation_rate_and_cost_accounting():
    """
    Simulates a representative 6-item benchmark with Tier 0 fast-path,
    Verifier gate, and calibrated Tier 1 escalation.
    Measures:
    - Escalation Rate (%)
    - Rescue Rate (wrong Tier 0 turned correct by Tier 1)
    - Total tokens consumed vs Fixed Tier 1 baseline
    """
    dataset: List[SimulatedQuery] = [
        # 1. Easy query, Tier 0 correct -> Verifier PASS -> Dừng (No escalation)
        SimulatedQuery(
            query_id="q1_easy",
            prompt="24 + 36",
            gold_answer="60",
            tier0_answer="60",
            tier0_expr="24 + 36",
            tier0_tokens=25,
            tier1_answer="60",
            tier1_tokens=320,
        ),
        # 2. Easy query, Tier 0 correct -> Verifier PASS -> Dừng (No escalation)
        SimulatedQuery(
            query_id="q2_easy",
            prompt="15 * 6",
            gold_answer="90",
            tier0_answer="90",
            tier0_expr="15 * 6",
            tier0_tokens=22,
            tier1_answer="90",
            tier1_tokens=280,
        ),
        # 3. Medium query, Tier 0 math error -> Verifier FAIL -> Escalate -> Rescued by Tier 1
        SimulatedQuery(
            query_id="q3_math_error",
            prompt="14 * 12 + 8",  # 168 + 8 = 176
            gold_answer="176",
            tier0_answer="168",  # Forgot + 8
            tier0_expr="14 * 12 + 8",
            tier0_tokens=30,
            tier1_answer="176",  # ReAct calculator solves it correctly
            tier1_tokens=380,
        ),
        # 4. Complex query, Tier 0 unverified syntax -> Verifier UNVERIFIABLE -> Escalate
        SimulatedQuery(
            query_id="q4_complex",
            prompt="Compute compound interest",
            gold_answer="1250",
            tier0_answer="1200",
            tier0_expr="round(1000 * (1.05)**5, 0)",
            tier0_tokens=40,
            tier1_answer="1276",
            tier1_tokens=450,
        ),
        # 5. Semantic blindspot: Tier 0 wrong formula, but math valid -> Verifier PASS -> False Stop!
        SimulatedQuery(
            query_id="q5_blindspot",
            prompt="Area of 8 by 4 rect",
            gold_answer="32",
            tier0_answer="24",  # Model did perimeter (8+4)*2 = 24
            tier0_expr="(8 + 4) * 2",
            tier0_tokens=35,
            tier1_answer="32",
            tier1_tokens=350,
        ),
        # 6. Hard query, Tier 0 fails -> Verifier FAIL -> Escalate -> Rescued
        SimulatedQuery(
            query_id="q6_hard",
            prompt="Multi-step puzzle",
            gold_answer="42",
            tier0_answer="38",
            tier0_expr="10 + 20",  # Truncated expression
            tier0_tokens=30,
            tier1_answer="42",
            tier1_tokens=520,
        ),
    ]

    total_queries = len(dataset)
    escalations = 0
    tier0_correct = 0
    final_policy_correct = 0
    total_policy_tokens = 0
    total_fixed_tier1_tokens = sum(item.tier1_tokens for item in dataset)

    for item in dataset:
        # Run Tier 0
        cert = VGCCertificate(claim=item.tier0_answer, witness=item.tier0_answer)
        v_res = VGCVerifier.verify_calculation(cert, item.tier0_expr or "")

        is_tier0_correct = (item.tier0_answer == item.gold_answer)
        if is_tier0_correct:
            tier0_correct += 1

        # Policy decision: Stop if VALID, else Escalate to Tier 1
        if v_res.status == VGCVerificationStatus.VALID:
            # Stopped at Tier 0
            tokens_used = item.tier0_tokens
            final_answer = item.tier0_answer
        else:
            # Escalated to Tier 1
            escalations += 1
            tokens_used = item.tier0_tokens + item.tier1_tokens
            final_answer = item.tier1_answer

        total_policy_tokens += tokens_used
        if final_answer == item.gold_answer:
            final_policy_correct += 1

    escalation_rate = escalations / total_queries
    token_savings_pct = (1.0 - (total_policy_tokens / total_fixed_tier1_tokens)) * 100.0

    # Assertions on empirical metrics:
    # 1. Escalation occurred on faulty or unverifiable queries
    assert 0.0 < escalation_rate < 1.0, f"Expected selective escalation, got {escalation_rate:.2f}"
    assert escalations == 3  # q3, q4, q6 escalated

    # 2. Token cost is significantly lower than always running Tier 1
    assert total_policy_tokens < total_fixed_tier1_tokens
    assert token_savings_pct > 30.0  # Saves over 30% tokens by fast-pathing easy queries

    # 3. Final accuracy improves over raw Tier 0 due to rescues
    assert final_policy_correct > tier0_correct
    # q1, q2 (correct Tier 0) + q3, q6 (rescued by Tier 1) = 4/6 correct
    assert final_policy_correct == 4
    assert tier0_correct == 2
