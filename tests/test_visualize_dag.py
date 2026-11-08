"""Unit tests for MSRA DAG visualizer."""

from structured_llm.msra.types import (
    CapabilityTag,
    Decision,
    ReasoningNode,
    TraceValidationResult,
    VerificationStatus,
)
from tools.visualize_dag import render_ascii_dag, render_dot, render_mermaid


def test_render_ascii_dag():
    node1 = ReasoningNode(
        step_id=1,
        subgoal="Step 1",
        capability_tag=CapabilityTag.SYMBOLIC_CALC,
        decision=Decision.SOLVE_LOCAL,
        execution_result="4 * 5 = 20",
        output_var={"v1": "20"},
        verification_status=VerificationStatus.COMMIT,
    )
    res = TraceValidationResult(is_valid=True, errors=[], nodes=[node1])
    ascii_out = render_ascii_dag(res, final_answer="20")

    assert "Step 1 [LOCAL] [COMMIT]" in ascii_out
    assert "Subgoal:    Step 1" in ascii_out
    assert "Final Answer: 20" in ascii_out


def test_render_mermaid():
    node1 = ReasoningNode(
        step_id=1,
        subgoal="First step",
        capability_tag=CapabilityTag.SYMBOLIC_CALC,
        decision=Decision.SOLVE_LOCAL,
        output_var={"v1": "10"},
        verification_status=VerificationStatus.COMMIT,
    )
    node2 = ReasoningNode(
        step_id=2,
        subgoal="Second step",
        capability_tag=CapabilityTag.SYMBOLIC_CALC,
        decision=Decision.SOLVE_LOCAL,
        deps={"v1": "10"},
        output_var={"v2": "20"},
        verification_status=VerificationStatus.COMMIT,
    )
    res = TraceValidationResult(is_valid=True, errors=[], nodes=[node1, node2])
    mermaid_out = render_mermaid(res, final_answer="20")

    assert "graph TD" in mermaid_out
    assert "step_1 -->|v1| step_2" in mermaid_out
    assert "Final Answer: 20" in mermaid_out


def test_render_dot():
    node1 = ReasoningNode(
        step_id=1,
        subgoal="First",
        capability_tag=CapabilityTag.SYMBOLIC_CALC,
        decision=Decision.SOLVE_LOCAL,
        output_var={"v1": "10"},
        verification_status=VerificationStatus.COMMIT,
    )
    node2 = ReasoningNode(
        step_id=2,
        subgoal="Second",
        capability_tag=CapabilityTag.SYMBOLIC_CALC,
        decision=Decision.SOLVE_LOCAL,
        deps={"v1": "10"},
        output_var={"v2": "20"},
        verification_status=VerificationStatus.COMMIT,
    )
    res = TraceValidationResult(is_valid=True, errors=[], nodes=[node1, node2])
    dot_out = render_dot(res, final_answer="20")

    assert "digraph MSRA_DAG {" in dot_out
    assert 'step_1 -> step_2 [label="v1"];' in dot_out
