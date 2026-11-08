"""Unit tests for MSRA XML trace parser, DAG validator, and serializer."""

import pytest
from structured_llm.msra.trace_parser import (
    compute_helper_spans,
    extract_final_answer,
    format_node_to_xml,
    format_trace_to_xml,
    parse_step,
    parse_trace,
    parse_var_dict,
)
from structured_llm.msra.types import (
    CapabilityTag,
    Decision,
    ReasoningNode,
    VerificationStatus,
)


def test_parse_var_dict():
    assert parse_var_dict("None") == {}
    assert parse_var_dict("") == {}
    d1 = parse_var_dict("x = 42, y = 3.14")
    assert d1 == {"x": "42", "y": "3.14"}
    d2 = parse_var_dict("a: 10\nb: 20")
    assert d2 == {"a": "10", "b": "20"}


def test_parse_valid_single_step():
    content = """
    <subgoal>Calculate total price</subgoal>
    <deps>None</deps>
    <capability>CAP:SYMBOLIC_CALC</capability>
    <decision>SOLVE_LOCAL</decision>
    <execution>10 * 5 = 50</execution>
    <verification status="COMMIT">Verified exact product</verification>
    <output_var>total = 50</output_var>
    """
    node, errors = parse_step("1", content, "2.0")
    assert not errors
    assert node is not None
    assert node.step_id == 1
    assert node.subgoal == "Calculate total price"
    assert node.capability_tag == CapabilityTag.SYMBOLIC_CALC
    assert node.decision == Decision.SOLVE_LOCAL
    assert node.execution_result == "10 * 5 = 50"
    assert node.verification_status == VerificationStatus.COMMIT
    assert node.output_var == {"total": "50"}


def test_parse_valid_multi_step_dag():
    trace_text = """
    <step id="1" budget_remaining="2.00">
      <subgoal>Find unit cost</subgoal>
      <deps>None</deps>
      <capability>CAP:SYMBOLIC_CALC</capability>
      <decision>SOLVE_LOCAL</decision>
      <execution>100 / 4 = 25</execution>
      <verification status="COMMIT">Exact divisor</verification>
      <output_var>unit_cost = 25</output_var>
    </step>

    <step id="2" budget_remaining="2.00">
      <subgoal>Find total with tax</subgoal>
      <deps>unit_cost = 25</deps>
      <capability>CAP:SYMBOLIC_CALC</capability>
      <decision>ASK_HELP</decision>
      <query_payload>Evaluate 25 * 1.1</query_payload>
      <helper_response source="h_sym">27.5</helper_response>
      <verification status="COMMIT">Verified via SymPy</verification>
      <output_var>final_total = 27.5</output_var>
    </step>

    <final_answer>27.5</final_answer>
    """
    result = parse_trace(trace_text)
    assert result.is_valid
    assert len(result.errors) == 0
    assert len(result.nodes) == 2
    assert extract_final_answer(trace_text) == "27.5"


def test_parse_broken_dag_missing_dependency():
    trace_text = """
    <step id="1">
      <subgoal>Find unit cost</subgoal>
      <deps>None</deps>
      <capability>CAP:DECOMPOSE</capability>
      <decision>SOLVE_LOCAL</decision>
      <execution>Calculated</execution>
      <verification status="COMMIT">Done</verification>
      <output_var>x = 10</output_var>
    </step>

    <step id="2">
      <subgoal>Calculate something else</subgoal>
      <deps>unproduced_var = 50</deps>
      <capability>CAP:SYMBOLIC_CALC</capability>
      <decision>SOLVE_LOCAL</decision>
      <execution>Calculated</execution>
      <verification status="COMMIT">Done</verification>
      <output_var>y = 20</output_var>
    </step>
    """
    result = parse_trace(trace_text)
    assert not result.is_valid
    assert any("unproduced_var" in err for err in result.errors)


def test_parse_missing_query_payload_for_help():
    trace_text = """
    <step id="1">
      <subgoal>Ask help without payload</subgoal>
      <deps>None</deps>
      <capability>CAP:SYMBOLIC_CALC</capability>
      <decision>ASK_HELP</decision>
      <verification status="COMMIT">Done</verification>
      <output_var>res = 5</output_var>
    </step>
    """
    result = parse_trace(trace_text)
    assert not result.is_valid
    assert any("query_payload" in err for err in result.errors)


def test_serialization_and_helper_spans():
    node1 = ReasoningNode(
        step_id=1,
        subgoal="First step",
        capability_tag=CapabilityTag.DECOMPOSE,
        decision=Decision.SOLVE_LOCAL,
        execution_result="Let x = 10",
        verification_status=VerificationStatus.COMMIT,
        critique="Valid",
        output_var={"x": "10"},
    )
    node2 = ReasoningNode(
        step_id=2,
        subgoal="Solve equation",
        capability_tag=CapabilityTag.SYMBOLIC_CALC,
        decision=Decision.ASK_HELP,
        deps={"x": "10"},
        query_payload="Solve x + y = 30",
        execution_result="y = 20",
        verification_status=VerificationStatus.COMMIT,
        critique="Root checked",
        output_var={"y": "20"},
        helper_source="h_sym",
        cost=0.1,
    )

    xml_text = format_trace_to_xml([node1, node2], final_answer="20", initial_budget=2.0)
    parsed = parse_trace(xml_text)
    assert parsed.is_valid
    assert len(parsed.nodes) == 2
    assert extract_final_answer(xml_text) == "20"

    spans = compute_helper_spans(xml_text)
    assert len(spans) == 1
    start, end = spans[0]
    matched = xml_text[start:end]
    assert '<helper_response source="h_sym">y = 20</helper_response>' in matched
