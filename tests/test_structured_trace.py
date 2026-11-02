import pytest

from structured_llm import gsm8k
from structured_llm.trace import Step, calc_is_correct, check, evaluate_expr, loose_answer, parse, render

QUESTION = "Natalia sold clips to 48 of her friends in April, and half as many in May. How many altogether?"
NATALIA = {
    "question": QUESTION,
    "answer": "Natalia sold 48/2 = <<48/2=24>>24 clips in May.\n"
              "Natalia sold 48+24 = <<48+24=72>>72 clips altogether.\n#### 72",
}
TRACE = (
    "<think>\nStep 1: Natalia sold 48/2 = 24 clips in May.\nCalc: 48/2=24\n"
    "Step 2: Natalia sold 48+24 = 72 clips altogether.\nCalc: 48+24=72\n</think>\n\nAnswer: 72"
)


def test_render_parse_round_trip():
    steps = [Step("First.", [("1+1", "2")]), Step("No calculation here.")]
    trace = parse(render(steps, "2"))
    assert trace.errors == []
    assert trace.answer == "2"
    assert [step.text for step in trace.steps] == ["First.", "No calculation here."]
    assert trace.steps[0].calcs == [("1+1", "2")]


@pytest.mark.parametrize("text, error", [
    (TRACE.removeprefix("<think>\n"), "missing_think_open"),
    (TRACE.replace("</think>", ""), "missing_think_close"),
    (TRACE.replace("Step 2", "Step 3"), "step_number"),
    (TRACE.replace("Calc: 48/2=24", "So that is 24."), "line_outside_grammar"),
    ("<think>\n</think>\n\nAnswer: 1", "no_steps"),
    (TRACE.replace("Answer: 72", "It is 72."), "answer_line"),
])
def test_parse_reports_each_error(text, error):
    assert error in parse(text).errors


@pytest.mark.parametrize("expr, value", [
    ("2+3*4", 14.0), ("(2+3)*4", 20.0), ("-3+5", 2.0), (".5*4", 2.0), ("7/2", 3.5),
])
def test_evaluate_expr(expr, value):
    assert evaluate_expr(expr) == value


@pytest.mark.parametrize("expr", ["1/0", "2**8", "abs(1)", "x+1", "__import__('os')", "1+", "05+1"])
def test_evaluate_expr_rejects(expr):
    assert evaluate_expr(expr) is None


@pytest.mark.parametrize("expr, stated, expected", [
    ("48/2", "24", True), ("2/3", ".67", True), ("2/3", ".66", False),
    ("10/3", "3", False), ("100/3", "33.33", True), ("1+1", "3", False), ("1+1", "2.", True),
    ("1+1", "1.2.3", False), ("x", "1", False),
])
def test_calc_is_correct(expr, stated, expected):
    assert calc_is_correct(expr, stated) is expected


@pytest.mark.parametrize("text, expected", [
    ("<think>x</think>\n\nAnswer: 72", 72.0),
    ("<think>x</think>The total is $1,250.50 today", 1250.5),
    ("<think>x</think>Maybe 3 then \\boxed{18}", 18.0),
    ("<think>x</think>\n\nAnswer: -5", -5.0),
    ("<think>x</think>so 8-3 gives 5-2", 2.0),
    ("<think>12 here</think>no number after", None),
    ("<think>never closed 12", None),
])
def test_loose_answer(text, expected):
    assert loose_answer(text) == expected


def test_check_scores_a_clean_trace():
    result = check(TRACE, QUESTION, "72")
    assert result["format_valid"] is True
    assert result["calc_accuracy"] == 1.0
    assert result["answer_from_last_calc"] is True
    assert result["correct"] is True
    # 2 is implied by "half", so three of the four operands are grounded.
    assert result["grounded_rate"] == 0.75


def test_check_separates_structure_from_correctness():
    free_form = check("<think>half of 48 is 24, plus 48</think>\n\nThe answer is 72.", QUESTION, "72")
    assert free_form["format_valid"] is False
    assert free_form["correct"] is True
    wrong = check(TRACE.replace("Answer: 72", "Answer: 70"), QUESTION, "72")
    assert wrong["format_valid"] is True
    assert wrong["correct"] is False
    assert wrong["answer_from_last_calc"] is False


def test_check_flags_a_wrong_calculation():
    assert check(TRACE.replace("48+24=72", "48+24=70"), QUESTION, "72")["calc_accuracy"] == 0.5


def test_check_with_no_calcs_has_no_rates():
    result = check("<think>\nStep 1: Just reason.\n</think>\n\nAnswer: 5", "Q", "5")
    assert result["calc_accuracy"] is None
    assert result["grounded_rate"] is None


def test_convert_natalia():
    trace, reason = gsm8k.convert(NATALIA)
    assert reason is None
    assert trace == TRACE


@pytest.mark.parametrize("answer, reason", [
    ("She sold some clips.\n#### 72", "no_annotations"),
    ("Total is <<48+24=70>>70.\n#### 70", "wrong_or_unparsable_annotation"),
    ("<<48+24=72>>\n#### 72", "calc_without_prose"),
])
def test_convert_rejects(answer, reason):
    assert gsm8k.convert({"question": "Q", "answer": answer}) == (None, reason)


def test_gold_answer_strips_comma_and_dollar():
    assert gsm8k.gold_answer("Step.\n#### $1,250") == "1250"


def test_prompt_ends_where_the_trace_starts():
    row = gsm8k.training_row(NATALIA, TRACE)
    assert row["text"].startswith("<|im_start|>user\nNatalia")
    assert row["text"].endswith("<|im_start|>assistant\n" + TRACE + "<|im_end|>")


def test_rank_ignores_case_and_spacing():
    assert gsm8k.rank_key("A  b") == gsm8k.rank_key("a b")
