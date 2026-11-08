"""Unit tests for MSRA counterfactual intervention engine."""

import pytest
from structured_llm.msra.intervene_msra import (
    classify_msra_outcome,
    find_eligible_intervention_step,
    plan_msra_intervention,
)
from structured_llm.msra.types import (
    CapabilityTag,
    Decision,
    ReasoningNode,
    VerificationStatus,
)


def test_find_eligible_intervention_step():
    node1 = ReasoningNode(
        step_id=1,
        subgoal="Step 1",
        capability_tag=CapabilityTag.SYMBOLIC_CALC,
        decision=Decision.SOLVE_LOCAL,
        output_var={"v1": "25"},
    )
    node2 = ReasoningNode(
        step_id=2,
        subgoal="Step 2",
        capability_tag=CapabilityTag.SYMBOLIC_CALC,
        decision=Decision.SOLVE_LOCAL,
        deps={"v1": "25"},
        output_var={"v2": "50"},
    )

    eligible = find_eligible_intervention_step([node1, node2])
    assert eligible is not None
    step_id, var_name, orig_val = eligible
    assert step_id == 1
    assert var_name == "v1"
    assert orig_val == 25.0


def test_plan_msra_intervention():
    trace_xml = (
        "<step id=\"1\" budget_remaining=\"2.00\">\n"
        "  <subgoal>Step 1</subgoal>\n"
        "  <deps>None</deps>\n"
        "  <capability>CAP:SYMBOLIC_CALC</capability>\n"
        "  <decision>SOLVE_LOCAL</decision>\n"
        "  <execution>50 / 2 = 25</execution>\n"
        "  <verification status=\"COMMIT\">Exact</verification>\n"
        "  <output_var>v1 = 25</output_var>\n"
        "</step>\n\n"
        "<step id=\"2\" budget_remaining=\"2.00\">\n"
        "  <subgoal>Step 2</subgoal>\n"
        "  <deps>v1 = 25</deps>\n"
        "  <capability>CAP:SYMBOLIC_CALC</capability>\n"
        "  <decision>SOLVE_LOCAL</decision>\n"
        "  <execution>25 + 10 = 35</execution>\n"
        "  <verification status=\"COMMIT\">Exact</verification>\n"
        "  <output_var>v2 = 35</output_var>\n"
        "</step>\n\n"
        "<final_answer>35</final_answer>"
    )

    plan, err = plan_msra_intervention(trace_xml, key=42)
    assert err is None
    assert plan is not None
    assert plan["step_id"] == 1
    assert plan["var_name"] == "v1"
    assert plan["original_value"] == 25.0
    assert plan["perturbed_value"] != 25.0
    assert plan["original_answer"] == 35.0
    assert f"<output_var>v1 = {int(plan['perturbed_value'])}</output_var>" in plan["prefix"]


def test_classify_msra_outcome():
    plan = {
        "original_answer": 35.0,
        "perturbed_value": 30.0,
    }

    # Case 1: Reverted to old answer
    res_rev = classify_msra_outcome("<final_answer>35</final_answer>", plan)
    assert res_rev == "reverted"

    # Case 2: Followed perturbation to new answer
    res_fol = classify_msra_outcome("<final_answer>40</final_answer>", plan)
    assert res_fol == "follows"

    # Case 3: Rejected by epistemic verifier!
    res_rej = classify_msra_outcome(
        '<step id="2">\n  <verification status="REJECT">Inconsistent with premise</verification>\n</step>',
        plan,
    )
    assert res_rej == "rejected_at_verification"


def test_run_msra_interventions():
    from structured_llm.msra.intervene_msra import run_msra_interventions
    from structured_llm.msra.stream_driver import MockGeneratorBackend

    trace_xml = (
        "<step id=\"1\" budget_remaining=\"2.00\">\n"
        "  <subgoal>Step 1</subgoal>\n"
        "  <deps>None</deps>\n"
        "  <capability>CAP:SYMBOLIC_CALC</capability>\n"
        "  <decision>SOLVE_LOCAL</decision>\n"
        "  <execution>50 / 2 = 25</execution>\n"
        "  <verification status=\"COMMIT\">Exact</verification>\n"
        "  <output_var>v1 = 25</output_var>\n"
        "</step>\n\n"
        "<step id=\"2\" budget_remaining=\"2.00\">\n"
        "  <subgoal>Step 2</subgoal>\n"
        "  <deps>v1 = 25</deps>\n"
        "  <capability>CAP:SYMBOLIC_CALC</capability>\n"
        "  <decision>SOLVE_LOCAL</decision>\n"
        "  <execution>25 + 10 = 35</execution>\n"
        "  <verification status=\"COMMIT\">Exact</verification>\n"
        "  <output_var>v2 = 35</output_var>\n"
        "</step>\n\n"
        "<final_answer>35</final_answer>"
    )

    records = [{"id": "item_1", "text": trace_xml}]
    backend = MockGeneratorBackend({"v1 =": "<final_answer>40</final_answer>"})

    summary = run_msra_interventions(records, backend)
    assert summary["eligible_count"] == 1
    assert summary["eligibility_rate"] == 1.0
    assert summary["outcomes"]["follows"] == 1
    assert summary["follows_rate"] == 100.0

