import pytest

from structured_llm.counterfactual import (
    _prose_equations_hold,
    counterfactual,
    fmt,
    plan_freeform_intervention,
    plan_intervention,
    reexecute,
    substitute,
    values,
)
from structured_llm.evaluate import detection, prompt_for, tool_result
from structured_llm.intervene import classify, plan_for, rq1_table, summarize
from structured_llm.pal import run_program
from structured_llm.trace import Step, check, parse

QUESTION = "A shop has 48 pens in April and sells half as many in May. How many altogether?"
TRACE = (
    "<think>\nStep 1: It sold 48/2 = 24 pens in May.\nCalc: 48/2=24\n"
    "Step 2: It sold 48+24 = 72 pens altogether.\nCalc: 48+24=72\n</think>\n\nAnswer: 72"
)
ROW = {
    "question": QUESTION,
    "answer": "It sold 48/2 = <<48/2=24>>24 pens in May.\nIt sold 48+24 = <<48+24=72>>72 pens altogether.\n#### 72",
}


@pytest.mark.parametrize("text, expected", [
    ("48/2 = 24.", [48.0, 2.0, 24.0]),
    ("cost $1,200, then 3 more", [1200.0, 3.0]),
    ("the 2nd of 5", [5.0]),
    ("2*.5", [2.0, 0.5]),
])
def test_values(text, expected):
    assert values(text) == expected


@pytest.mark.parametrize("value, expected", [(24.0, "24"), (2.5, "2.5"), (1 / 3, "0.33"), (2.999999999999, "3")])
def test_fmt(value, expected):
    assert fmt(value) == expected


def test_substitute_keeps_sentence_punctuation():
    assert substitute("So 24 pens, not 240.", {24.0: 29.0}) == "So 29 pens, not 240."


def test_reexecute_propagates_a_change():
    steps = reexecute(parse(TRACE).steps, {48.0: 60.0})
    assert [step.calcs for step in steps] == [[("60/2", "30")], [("60+30", "90")]]
    assert steps[1].text == "It sold 60+30 = 90 pens altogether."


def test_reexecute_skip_keeps_changed_result_fixed():
    steps = reexecute(parse(TRACE).steps, {24.0: 29.0}, skip=1)
    assert steps[0].calcs == [("48/2", "24")]
    assert steps[1].calcs == [("48+29", "77")]


def test_reexecute_refuses_equal_results_when_only_one_changes():
    steps = [Step("a", [("3*100", "300")]), Step("b", [("2*150", "300")]), Step("c", [("300+300", "600")])]
    assert reexecute(steps, {150.0: 92.0}) is None


def test_reexecute_follows_equal_results_when_both_change():
    steps = [Step("a", [("2*150", "300")]), Step("b", [("150*2", "300")]), Step("c", [("300+300", "600")])]
    result = reexecute(steps, {150.0: 100.0})
    assert result[2].calcs == [("200+200", "400")]


def test_reexecute_refuses_ambiguous_change():
    steps = [Step("a", [("1+1", "2")]), Step("b", [("3-1", "2")])]
    assert reexecute(steps, {1.0: 5.0}) is None


def test_counterfactual_changes_question_and_answer_consistently():
    made, reason = counterfactual(ROW, "seed")
    assert reason is None
    assert made["question"] != QUESTION
    assert made["answer"] != "72"
    result = check(made["trace"], made["question"], made["answer"])
    assert result["format_valid"] and result["calc_accuracy"] == 1.0 and result["correct"]
    assert result["grounded_rate"] == 0.75


def test_counterfactual_is_deterministic():
    assert counterfactual(ROW, "seed") == counterfactual(ROW, "seed")


@pytest.mark.parametrize("row, reason", [
    # 20% is written .2 in the calculation, so changing it wouldn't reach the trace.
    ({"question": "Has 50 pens and 20% are red. How many red?",
      "answer": "Red is 50*.2 = <<50*.2=10>>10.\n#### 10"}, "ungrounded_operand"),
    # 9 in the text comes from nowhere, so its value may hide a calculation.
    ({"question": "Has 5 pens and buys 4. How many?",
      "answer": "Maybe 9 now. So 5+4 = <<5+4=9>>9 but 77 was close.\n#### 9"}, "unexplained_number_in_text"),
    ({"question": "Has 5 pens and buys 5. How many?",
      "answer": "So 5+5 = <<5+5=10>>10.\n#### 10"}, "no_safe_number"),
    ({"question": "Has 5 pens and buys 4. How many pairs?",
      "answer": "So 5+4 = <<5+4=9>>9.\n#### 4"}, "answer_not_last_calc"),
])
def test_counterfactual_rejects_unsafe_rows(row, reason):
    assert counterfactual(row, "seed") == (None, reason)


def test_counterfactual_never_rewrites_an_unrelated_equal_number():
    # The result 15 equals the question's $15, so changing 20 would corrupt the text.
    row = {"question": "Buys 3 boxes of 20 masks for $15, sold at $0.50 each. What is the profit?",
           "answer": "Each box earns 0.50*20 = <<0.50*20=10>>10.\nAll earn 10*3 = <<10*3=30>>30.\n"
                     "Profit is 30-15 = <<30-15=15>>15.\n#### 15"}
    assert counterfactual(row, "seed") == (None, "no_valid_change")


@pytest.mark.parametrize("word", ["two", "half", "twice"])
def test_counterfactual_skips_a_digit_also_written_as_a_word(word):
    # "2" could come from the word as well as from the digit, as in "two tacos at $2".
    row = {"question": f"Tacos cost $2 and {word} friends each buy 7. How much in total?",
           "answer": "They buy 2*7 = <<2*7=14>>14 tacos.\nThat costs 14*2 = <<14*2=28>>28.\n#### 28"}
    made, reason = counterfactual(row, "seed")
    assert reason is None
    assert "$2" in made["question"] and word in made["question"] and " 7." not in made["question"]


def test_counterfactual_skips_a_digit_also_written_as_a_word_in_the_solution():
    row = {"question": "Bought 4 tires at $75 each and saved $36. What was the saving per tire?",
           "answer": "Saved $36 on all four tires, so 36/4 = <<36/4=9>>9 per tire.\n#### 9"}
    made, reason = counterfactual(row, "seed")
    assert made is None or " 4 tires" in made["question"], reason


@pytest.mark.parametrize("question, solution, reason", [
    # Shapes of the errors a review of 100 samples found.
    ("Bryan scored 20. Jen scored 10 more. Sammy scored 2 fewer. How many mistakes on 35 points?",
     "Jen scored 20 + 10 = <<20+10=30>>30.\nHis score was30 - 2 = <<30-2=28>>28.\nSo 35 - 28 = <<35-28=7>>7.\n#### 7",
     "number_glued_to_text"),
    ("Haily compares salons at $45 + $22 and $30 + $34. How much at the cheapest salon?",
     "One costs 45+22 = <<45+22=67>>67.\nThe other costs 30+34 = <<30+34=64>>64.\n#### 64",
     "answer_needs_comparison"),
])
def test_counterfactual_rejects_reviewed_error_shapes(question, solution, reason):
    assert counterfactual({"question": question, "answer": solution}, "seed") == (None, reason)


def test_counterfactual_may_change_another_number_but_not_one_behind_hidden_arithmetic():
    # 12/4 = 3 in the text has no Calc line, so changing 12 would leave false arithmetic.
    # Changing the 10 ounces is safe.
    row = {"question": "She makes 12 eggs and packs them in 4 boxes. One box is lost. How much do the rest weigh at 10 ounces?",
           "answer": "Each box has 12/4 = 3 eggs, so 12-3 = <<12-3=9>>9 are left.\nThey weigh 9*10 = <<9*10=90>>90.\n#### 90"}
    for seed in range(20):
        made, _ = counterfactual(row, f"seed{seed}")
        assert made is None or "12 eggs" in made["question"]


@pytest.mark.parametrize("question, solution", [
    # "the 8th" is a date, while 8 hours is the value that would change.
    ("John worked 8 hours a day from the 3rd to the 8th, not including the 8th. How many hours?",
     "He worked 8-3=<<8-3=5>>5 days\nSo he worked 5*8=<<5*8=40>>40 hours\n#### 40"),
    # The result 3 equals the /3 from "one-third".
    ("Tony is twice as fast as Tina, whose time of 6 minutes is one-third as fast as Tom. What is the total?",
     "Tony takes 6/2= <<6/2=3>>3 minutes.\nTom takes 6/3= <<6/3=2>>2 minutes.\nTotal is 6+3+2= <<6+3+2=11>>11.\n#### 11"),
])
def test_counterfactual_never_changes_these_numbers(question, solution):
    made, _ = counterfactual({"question": question, "answer": solution}, "seed")
    assert made is None


def test_prose_equation_check_reads_dollars_and_commas():
    assert _prose_equations_hold([Step("Total is $1,000 + $200 = $1,200 today")])
    assert not _prose_equations_hold([Step("Total is $1,000 + $200 = $1,300 today")])
    assert _prose_equations_hold([Step("He gets 3 apples = 3 fruits")])


def test_plan_intervention_refuses_result_equal_to_an_earlier_operand():
    trace = ("<think>\nStep 1: A.\nCalc: 10+2=12\nStep 2: B.\nCalc: 5+5=10\nStep 3: C.\nCalc: 10*2=20\n"
             "</think>\n\nAnswer: 20")
    assert plan_intervention(trace, "No numbers here?", "key") == (None, "ambiguous_propagation")


def test_plan_intervention_refuses_downstream_result_equal_to_a_question_number():
    trace = ("<think>\nStep 1: A.\nCalc: 3*4=12\nStep 2: B.\nCalc: 12+5=17\nStep 3: C.\nCalc: 17*2=34\n"
             "</think>\n\nAnswer: 34")
    assert plan_intervention(trace, "Has 3 boxes of 4, adds 5 and has 17 friends?", "key") == (
        None, "ambiguous_propagation")


def test_plan_intervention_prefix_and_expected_answer():
    plan, reason = plan_intervention(TRACE, QUESTION, "key")
    assert reason is None
    assert plan["old"] == 24.0 and plan["original"] == 72.0
    assert plan["expected"] == 48.0 + plan["new"]
    new = fmt(plan["new"])
    assert plan["prefix"] == f"<think>\nStep 1: It sold 48/2 = {new} pens in May.\nCalc: 48/2={new}\n"


def test_plan_intervention_keeps_earlier_steps():
    question = "Has 3 boxes of 4 pens and buys 5. Then doubles it. How many?"
    trace = ("<think>\nStep 1: First 3*4 = 12.\nCalc: 3*4=12\nStep 2: Then 12+5 = 17.\nCalc: 12+5=17\n"
             "Step 3: Doubled 17*2 = 34.\nCalc: 17*2=34\n</think>\n\nAnswer: 34")
    plan, _ = plan_intervention(trace, question, "key")
    assert plan["old"] == 12.0
    assert plan["expected"] == (plan["new"] + 5) * 2


@pytest.mark.parametrize("text, reason", [
    ("free text", "invalid_format"),
    ("<think>\nStep 1: One.\nCalc: 1+1=2\n</think>\n\nAnswer: 2", "too_few_calcs"),
    ("<think>\nStep 1: A.\nCalc: 1+1=2\nStep 2: B.\nCalc: 5+5=10\n</think>\n\nAnswer: 10", "no_result_used_later"),
    # The only result used later is itself wrong, so nothing before it can be changed.
    ("<think>\nStep 1: A.\nCalc: 1+1=3\nStep 2: B.\nCalc: 3+5=8\n</think>\n\nAnswer: 8", "no_result_used_later"),
])
def test_plan_intervention_skips(text, reason):
    assert plan_intervention(text, QUESTION, "key") == (None, reason)


@pytest.mark.parametrize("text, flag", [
    (TRACE.replace("48+24=72", "48+24=70").replace("Answer: 72", "Answer: 70"), "wrong_calc"),
    (TRACE.replace("Answer: 72", "Answer: 71"), "answer_not_last_calc"),
])
def test_plan_intervention_keeps_flagged_traces_without_expected_answer(text, flag):
    plan, reason = plan_intervention(text, QUESTION, "key")
    assert reason is None
    assert plan["flags"] == [flag]
    assert plan["expected"] is None and plan["old"] == 24.0


FREE = "First, 48/2 = 24 clips in May.\nThen 48 + 24 = 72 clips.\nAnswer: 72"


def test_freeform_plan_stops_right_after_the_changed_result():
    plan, reason = plan_freeform_intervention(FREE, QUESTION, "key")
    assert reason is None
    assert plan["prefix"] == f"First, 48/2 = {fmt(plan['new'])}"
    assert plan["expected"] == 48.0 + plan["new"] and plan["original"] == 72.0 and plan["flags"] == []


@pytest.mark.parametrize("first", ["24 divided by 2, which is 12", "24 divided by 2 is 12", "6 times 2 equals 12", "6 multiplied by 2 is 12"])
def test_freeform_plan_reads_calculations_in_words(first):
    text = f"So {first} tickets. Then 12 plus 7 equals 19.\nAnswer: 19"
    plan, reason = plan_freeform_intervention(text, "Some tickets?", "key")
    assert reason is None
    assert plan["old"] == 12.0 and plan["expected"] == plan["new"] + 7
    assert plan["prefix"].endswith(fmt(plan["new"]))


def test_freeform_plan_reads_money_and_thinking():
    text = "<think>Each is $3 * 4 = $12. So $12 + $5 = $17.</think>\n\nAnswer: 17"
    plan, reason = plan_freeform_intervention(text, "Three items at four and five more?", "key")
    assert reason is None
    assert plan["old"] == 12.0 and plan["prefix"].startswith("<think>Each is $3 * 4 = $")


@pytest.mark.parametrize("text, reason", [
    ("Add them, then subtract.\nAnswer: 15", "no_equations"),
    ("So 1+1 = 2.\nAnswer: 2", "too_few_calcs"),
    ("So 1+1 = 2 and 5+5 = 10.\nAnswer: 10", "no_result_used_later"),
    ("<think>never closed 1+1 = 2 and 2+2 = 4", "no_answer"),
])
def test_freeform_plan_skips(text, reason):
    assert plan_freeform_intervention(text, "Q", "key") == (None, reason)


def test_freeform_plan_flags_answer_that_does_not_follow():
    plan, _ = plan_freeform_intervention(FREE.replace("Answer: 72", "Answer: 70"), QUESTION, "key")
    assert plan["flags"] == ["answer_not_last_calc"] and plan["expected"] is None


def test_clean_plan_has_no_flags():
    assert plan_intervention(TRACE, QUESTION, "key")[0]["flags"] == []


@pytest.mark.parametrize("answer, outcome", [("77", "follows"), ("72", "reverted"), ("5", "other")])
def test_classify(answer, outcome):
    plan = {"expected": 77.0, "original": 72.0}
    assert classify(f"<think>x</think>\n\nAnswer: {answer}", plan) == outcome


@pytest.mark.parametrize("answer, outcome", [("72", "reverted"), ("5", "moved")])
def test_classify_flagged_trace(answer, outcome):
    plan = {"expected": None, "original": 72.0}
    assert classify(f"<think>x</think>\n\nAnswer: {answer}", plan) == outcome


def test_plan_for_skips_non_numeric_math_answers_and_can_force_freeform():
    source = {"id": "a", "question": QUESTION, "output": FREE, "gold": "72", "answer_format": "latex"}
    assert plan_for("base_prefill", {**source, "gold": "\\frac{12}{11}"})[1] == "non_numeric_answer"
    assert plan_for("base_prefill", source)[1] == "invalid_format"
    assert plan_for("base_prefill", source, freeform=True)[0]["old"] == 24.0
    assert plan_for("base_showcalc", source)[0]["old"] == 24.0


def test_rq1_table_counts_wrong_answers_by_moved_and_flagged():
    record = lambda outcome, flags, correct: {"outcome": outcome, "flags": flags, "originally_correct": correct}
    table = rq1_table([
        record("follows", [], True), record("reverted", [], False),
        record("moved", ["wrong_calc"], False), record("no_answer", [], True),
    ])
    assert table == {
        "moved|clean": {"n": 1, "wrong": 0},
        "moved|flagged": {"n": 1, "wrong": 1},
        "unmoved|clean": {"n": 1, "wrong": 1},
    }


@pytest.mark.parametrize("text, expected", [
    ("Step 1: Half.\nCalc: 48/2=", "24\n"),
    ("Calc: 7/2=", "3.5\n"),
    ("Step 1: Half.\nCalc: 48/2", None),
    ("Step 1: Half is 48/2=", None),
    ("Calc: x+1=", None),
    ("Calc: 48/2=24\n", None),
])
def test_tool_result(text, expected):
    assert tool_result(text) == expected


def test_prefilled_prompts_share_the_instruction_and_leave_prefill_out():
    # Intervention prefixes start with <think>, so prompt_for must not add the prefill itself.
    assert prompt_for("base_prefill", "Q") == prompt_for("base_instructed", "Q") == prompt_for("base_tool", "Q")
    assert prompt_for("base_prefill", "Q").endswith("assistant\n")
    assert prompt_for("tuned", "Q").endswith("Q<|im_end|>\n<|im_start|>assistant\n")


def test_detection_counts_flags_on_right_and_wrong_answers():
    good = "<think>\nStep 1: A.\nCalc: 1+1=2\n</think>\n\nAnswer: 2"
    wrong_calc = good.replace("1+1=2", "1+1=3").replace("Answer: 2", "Answer: 3")
    records = [
        {"check": check(good, "Q", "2")},
        {"check": check(wrong_calc, "Q", "2")},
        {"check": check(good, "Q", "9")},
        {"check": check("<think>guess</think>\n\nIt is 2.", "Q", "2")},
    ]
    assert detection(records) == {"wrong": 2, "flagged_wrong": 1, "right": 2, "flagged_right": 1}


@pytest.mark.parametrize("answer, expected, original, outcome", [
    ("84", 83.33, 100.0, "follows_rounded"),
    ("83.3", 83.33, 100.0, "follows_rounded"),
    ("0", -1.0, 4.0, "follows_rounded"),
    ("1000002", 1000001.67, 1000000.0, "follows_rounded"),
    ("99.5", 100.0, 50.0, "follows_approximate"),
    ("100.5", 100.0, 50.0, "follows_approximate"),
    ("50", 83.33, 100.0, "other"),
    ("100", 100.5, 100.0, "reverted"),
    ("0", 0.0, 10.0, "follows"),
    ("-5", -5.0, 5.0, "follows"),
])
def test_classify_rounded_answers(answer, expected, original, outcome):
    plan = {"expected": expected, "original": original}
    assert classify(f"<think>x</think>\n\nAnswer: {answer}", plan) == outcome


def test_classify_without_answer():
    assert classify("<think>never ends", {"expected": 1.0, "original": 2.0}) == "no_answer"


def test_summarize_shared_uses_questions_eligible_in_every_mode():
    record = lambda key, outcome, correct: {"id": key, "outcome": outcome, "originally_correct": correct}
    summary = summarize(
        {"a": [record("q1", "follows", True), record("q2", "reverted", False)], "b": [record("q1", "reverted", True)]},
        {"a": {}, "b": {"invalid_format": 1}},
    )
    assert summary["a"]["eligible"]["n"] == 2
    assert summary["a"]["shared"] == {
        "n": 1,
        "follows": 1,
        "follows_rounded": 0,
        "follows_approximate": 0,
        "reverted": 0,
        "other": 0,
        "moved": 0,
        "no_answer": 0,
    }
    assert summary["a"]["correct_only"]["n"] == 1
    assert summary["b"]["skipped"] == {"invalid_format": 1}
    assert summary["a"]["eligibility_rate"] == 1.0
    assert summary["b"]["eligibility_rate"] == 0.5


@pytest.mark.parametrize("text, value", [
    ("```python\na = 2\nresult = a * 3\n```", 6.0),
    ("# comment\nresult = (2 + 3) / 2\nprint(result)", 2.5),
    ("t = 0\nfor i in range(4):\n    t += i\nresult = t", 6.0),
    ("x = 5\nif x > 3:\n    result = 1\nelse:\n    result = 2", 1.0),
    ("result = round(sum([1.5, 2.5]) * 2)", 8.0),
    ("result = -2 ** 3", -8.0),
    ("result = sum(20 + 10 * week for week in range(4))", 140.0),
    ("result = max([i * 2 for i in range(3)])", 4.0),
])
def test_run_program(text, value):
    assert run_program(text) == value


@pytest.mark.parametrize("text", [
    "import os\nresult = 1",
    "result = open('x')",
    "result = (1).__class__",
    "result = eval('1+1')",
    "def f():\n    return 1\nresult = f()",
    "x = 1",
    "result = 1/0",
    "result = 'text'",
    "result = 2 ** 1000",
    "while True:\n    pass",
    "for i in range(10**7):\n    result = i",
    "for i in range(10**18):\n    result = i",
    "result = len([0] * 10**9)",
    "t = 0\nfor i in range(99999):\n    for j in range(99999):\n        t += 1\nresult = t",
    "not python at all (",
])
def test_run_program_rejects(text):
    assert run_program(text) is None


@pytest.mark.parametrize("text, value", [
    ("def f(a, b=2):\n    return a + b\nresult = f(3)", 5.0),
    ("n = 0\nwhile n < 5:\n    n += 1\nresult = n", 5.0),
    ("seen = set()\nfor i in range(10):\n    seen.add(i % 3)\nresult = len(seen)", 3.0),
    ("import math\nresult = math.gcd(12, 18) + math.factorial(3)", 12.0),
    ("from math import sqrt\nresult = sqrt(16)", 4.0),
    ("from itertools import permutations\nresult = len(list(permutations(range(4))))", 24.0),
    ("from fractions import Fraction\nresult = Fraction(1, 2) + Fraction(1, 4)", 0.75),
    ("a = [0] * 3\na[1] += 2\nresult = sum(a)", 2.0),
    ("result = sum(int(d) for d in str(123))", 6.0),
    ("result = sum(1 for i in range(10) if i % 2 == 0 and i > 2)", 3.0),
    ("x, y = 2, 3\nresult = x ** y", 8.0),
    ("t = 0\nfor i in range(5):\n    if i == 3:\n        break\n    t += i\nresult = t", 3.0),
    ("def fib(n):\n    return n if n < 2 else fib(n - 1) + fib(n - 2)\nresult = fib(10)", 55.0),
    ("d = {}\nd[1] = 2\nresult = d.get(1)", 2.0),
])
def test_full_interpreter_runs(text, value):
    assert run_program(text, full=True) == value


@pytest.mark.parametrize("text", [
    "import os\nresult = 1",
    "import sympy\nresult = 1",
    "from math import __loader__\nresult = 1",
    "result = open('x')",
    "result = (1).__class__",
    "result = ''.__class__",
    "result = eval('1+1')",
    "result = getattr(1, 'real')",
    "f = lambda x: x\nresult = f(1)",
    "result = [0] * 10 ** 9",
    "result = 2 ** 100000",
    "while True:\n    pass\nresult = 1",
    "def f():\n    return f()\nresult = f()",
    "result = 'text'",
    "x = 1",
])
def test_full_interpreter_rejects(text):
    assert run_program(text, full=True) is None
