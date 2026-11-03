import pytest

from structured_llm.math_check import (
    CONDITIONAL,
    FALSE,
    TRUE,
    boxed_answer,
    check_text,
    compare,
    equations,
    is_covered,
    is_trivial,
    parse,
    to_expression,
)


def verdict(left, right):
    return compare(parse(to_expression(left)), parse(to_expression(right)))


@pytest.mark.parametrize("left, right, expected", [
    ("2+3", "5", TRUE),
    ("2+3", "6", FALSE),
    ("\\frac{1}{2}+\\frac{1}{3}", "\\frac{5}{6}", TRUE),
    ("\\dfrac{3}{4}", "0.75", TRUE),
    ("3\\cdot 4", "12", TRUE),
    ("2 \\times 3", "7", FALSE),
    ("\\sqrt{16}", "4", TRUE),
    ("\\sqrt{2}\\sqrt{2}", "2", TRUE),
    ("2^{10}", "1024", TRUE),
    ("1,000+1", "1001", TRUE),
    ("\\left(1+2\\right)^2", "9", TRUE),
    ("\\sin 30^\\circ", "\\frac{1}{2}", TRUE),
    ("(x+1)^2", "x^2+2x+1", TRUE),
    ("(x+1)^2", "x^2+1", CONDITIONAL),
    ("2x+3", "7", CONDITIONAL),
    ("x y", "y x", TRUE),
    ("2(3+1)", "8", TRUE),
    ("\\frac12+\\frac12", "1", TRUE),
    ("\\frac1{4}", "\\frac{1}{4}", TRUE),
    ("\\frac{3}2", "1.5", TRUE),
    ("-2 + 2", "0,", TRUE),
    ("1\\,000+1", "1001", TRUE),
])
def test_compare(left, right, expected):
    assert verdict(left, right) == expected


@pytest.mark.parametrize("latex", [
    "\\text{area}", "a_1", "5!", "|x|", "\\sum_{k=1}^n k", "x \\le 2", "1,2,3", "\\binom{5}{2}", "AB",
    "\\mathbf{v}", "1 + \\dots + n", "\\frac{1}{2", "\\unknown{3}", "__import__('os')", "open('x')", "area",
    "x.__class__", "2^3^4", "lambda", "\\sqrt[3]{8}", "3\\frac{2}{3}", "6 \\cdot 8\\frac{1}{3}",
])
def test_to_expression_rejects(latex):
    assert to_expression(latex) is None


def test_parse_ignores_none():
    assert parse(None) is None


def test_equations_reads_inline_display_and_chains():
    text = "We get $1+1=2$ and \\[2+2=4=1+3.\\] Then $$a=b$$."
    assert list(equations(text)) == [("1+1", "2"), ("2+2", "4"), ("4", "1+3."), ("a", "b")]


def test_equations_continues_aligned_lines():
    text = "\\begin{align*}\nx &= 1+1 \\\\\n&= 2 \\\\\ny &= 3\n\\end{align*}"
    assert list(equations(text)) == [("x", "1+1"), ("1+1", "2"), ("y", "3")]


@pytest.mark.parametrize("left, right, trivial", [
    ("x", "5", True), ("5", "5", True), ("1+1", "2", False), ("x", "\\frac{1}{2}", False), ("2(3)", "6", False),
])
def test_is_trivial(left, right, trivial):
    assert is_trivial(left, right) is trivial


def test_boxed_answer_takes_the_last_and_handles_nesting():
    assert boxed_answer("$\\boxed{1}$ then $\\boxed{\\frac{1}{2}}$") == "\\frac{1}{2}"
    assert boxed_answer("no answer") is None


def test_covered_when_checked_equations_reach_the_answer():
    result = check_text("First $2+3=5$. Then $5\\cdot 2=\\boxed{10}$.")
    assert result["counts"][TRUE] == 2
    assert result["reaches_answer"] is True
    assert is_covered(result)


def test_not_covered_without_enough_checks_or_answer_link():
    assert not is_covered(check_text("So $1+1=\\boxed{2}$."))
    assert not is_covered(check_text("We have $1+1=2$ and $2+2=4$, so the answer is $\\boxed{9}$."))


def test_check_text_records_false_equations():
    result = check_text("Here $2+2=5$ and $\\boxed{5}$.")
    assert result["counts"][FALSE] == 1
    assert result["false_examples"] == ["2+2 = 5"]
