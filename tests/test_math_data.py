import pytest

from structured_llm.evaluate import score
from structured_llm.math_check import final_answer, same_answer
from structured_llm.math_data import as_item, rank_key, select

COVERED = "First $2+3=5$. Then $5\\cdot 2=\\boxed{10}$."


def row(key, level="Level 4", solution=COVERED):
    return {"id": key, "subject": "algebra", "level": level, "problem": f"Problem {key}?", "solution": solution}


def test_select_keeps_only_hard_covered_rows_in_rank_order():
    rows = [row("a"), row("b"), row("easy", level="Level 2"), row("prose", solution="It is $\\boxed{10}$.")]
    kept = select(rows)
    assert {item["id"] for item in kept} == {"a", "b"}
    assert [item["id"] for item in kept] == sorted(["a", "b"], key=lambda key: rank_key(f"Problem {key}?"))


def test_as_item_takes_the_boxed_answer():
    item = as_item(row("a"))
    assert item["answer"] == "10" and item["answer_format"] == "latex" and item["question"] == "Problem a?"


def test_rank_key_ignores_case_and_spacing():
    assert rank_key("A  b") == rank_key("a b")


@pytest.mark.parametrize("text, expected", [
    ("<think>x</think>\nSo $\\boxed{\\frac{1}{2}}$.", "\\frac{1}{2}"),
    ("<think>x</think>\n\nAnswer: 72", "72"),
    ("<think>x</think>\n\nAnswer: $\\frac{3}{4}$", "\\frac{3}{4}"),
    ("<think>x</think>\n\n**Answer: 5**", "5"),
    ("<think>x</think>\nThe total is $12$ apples.", "12"),
    ("<think>x</think>\nThe total is 1,250 today", "1,250"),
    ("<think>x</think>\n\nAnswer: Saturday", "Saturday"),
    ("Thinking is off. Answer: 9", "9"),
    ("<think>never closed 12", None),
    ("<think>no close\nAnswer: 12\n\nQuestion: and 9?", "12"),
    ("<think>x</think>   ", None),
])
def test_final_answer(text, expected):
    assert final_answer(text) == expected


@pytest.mark.parametrize("found, gold, expected", [
    ("\\frac{1}{2}", "\\dfrac{1}{2}", True),
    ("0.5", "\\frac{1}{2}", True),
    ("1,250", "1250", True),
    ("2\\sqrt{3}", "\\sqrt{12}", True),
    ("x^2+2x+1", "(x+1)^2", True),
    ("3", "4", False),
    ("\\text{Saturday}", "\\text{ Saturday }", True),
    ("(1,2)", "(1, 2)", True),
    ("(1,2)", "(2,1)", False),
    (None, "1", False),
])
def test_same_answer(found, gold, expected):
    assert same_answer(found, gold) is expected


def test_score_uses_latex_answers_only_when_asked():
    output = "<think>\nStep 1: A.\nCalc: 1+1=2\n</think>\n\nAnswer: $\\frac{1}{2}$"
    result = score("tuned", output, "Q", "\\dfrac{1}{2}", "latex")
    assert result["correct"] is True and result["answered"] is True
    assert score("tuned", "<think>x</think>\n\nAnswer: 7", "Q", "7")["correct"] is True


def test_score_reads_program_results_for_latex_answers():
    program = "```python\nresult = 1/2\n```"
    assert score("base_pal", program, "Q", "\\frac{1}{2}", "latex")["correct"] is True


def test_truncated_thinking_is_unanswered():
    result = score("base_native", "<think>still going 12", "Q", "12", "latex")
    assert result["answered"] is False and result["correct"] is False
