import pytest

from structured_llm.math_convert import clean_prose, convert_math_solution


def test_clean_prose():
    assert clean_prose("First step $2+3=5$. Then $\\boxed{5}$.") == "First step $2+3=5$. Then ."


def test_convert_math_solution_simple():
    row = {
        "id": "test_1",
        "problem": "Compute $2+3$ and then multiply by $2$.",
        "solution": "First compute $2+3=5$.\n\nThen $5\\cdot 2 = \\boxed{10}$.",
    }
    trace, err = convert_math_solution(row)
    assert err is None
    assert "<think>" in trace
    assert "Calc: 2+3=5" in trace
    assert "Calc: 5\\cdot 2=10" in trace
    assert "Answer: 10" in trace


def test_convert_math_solution_no_boxed():
    row = {
        "id": "test_no_boxed",
        "problem": "Compute something.",
        "solution": "We know $2+2=4$ but no box.",
    }
    trace, err = convert_math_solution(row)
    assert trace is None
    assert err == "no_boxed_answer"
