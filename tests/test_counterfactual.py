import pytest

from structured_llm.counterfactual import (
    counterfactual,
    fmt,
    plan_intervention,
    reexecute,
    substitute,
    values,
)
from structured_llm.evaluate import detection, tool_result
from structured_llm.intervene import classify, rq1_table, summarize
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


def test_classify_without_answer():
    assert classify("<think>never ends", {"expected": 1.0, "original": 2.0}) == "no_answer"


def test_summarize_shared_uses_questions_eligible_in_every_mode():
    record = lambda key, outcome, correct: {"id": key, "outcome": outcome, "originally_correct": correct}
    summary = summarize(
        {"a": [record("q1", "follows", True), record("q2", "reverted", False)], "b": [record("q1", "reverted", True)]},
        {"a": {}, "b": {"invalid_format": 1}},
    )
    assert summary["a"]["eligible"]["n"] == 2
    assert summary["a"]["shared"] == {"n": 1, "follows": 1, "reverted": 0, "other": 0, "moved": 0, "no_answer": 0}
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
