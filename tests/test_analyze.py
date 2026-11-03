import json

import pytest

from structured_llm.analyze import analyze, compare, exact_mcnemar, wilson
from structured_llm.trace import check

CLEAN = "<think>\nStep 1: A.\nCalc: 1+1=2\n</think>\n\nAnswer: 2"
VACUOUS = "<think>\nStep 1: A.\nCalc: 2=2\n</think>\n\nAnswer: 2"


def test_wilson_interval_stays_in_range_and_handles_empty():
    assert wilson(0, 0) is None
    low, high = wilson(0, 20)
    assert low == 0.0 and 0.1 < high < 0.2
    low, high = wilson(20, 20)
    assert 0.8 < low < 0.9 and high == 1.0


@pytest.mark.parametrize("only_a, only_b, expected", [(0, 0, 1.0), (5, 5, 1.0), (6, 0, 0.0312), (10, 2, 0.0386)])
def test_exact_mcnemar(only_a, only_b, expected):
    assert exact_mcnemar(only_a, only_b) == expected


@pytest.mark.parametrize("expr, rate", [("2", 1.0), ("48/2", 0.0), ("(3)", 1.0), (".5*4", 0.0), ("-3", 1.0), ("3--2", 0.0)])
def test_vacuous_rate(expr, rate):
    text = f"<think>\nStep 1: A.\nCalc: {expr}=2\n</think>\n\nAnswer: 2"
    assert check(text, "Q", "2")["vacuous_rate"] == rate


def test_vacuous_rate_without_calcs():
    assert check("<think>x</think>\n\nAnswer: 2", "Q", "2")["vacuous_rate"] is None


def test_compare_uses_only_shared_questions():
    result = lambda correct: {"check": {"correct": correct}}
    mode = {"a": result(True), "b": result(False), "c": result(True)}
    base = {"a": result(False), "b": result(True)}
    assert compare(mode, base) == {"shared": 2, "only_this_correct": 1, "only_baseline_correct": 1, "mcnemar_p": 1.0}


def write_run(folder, mode, rows):
    lines = [json.dumps({"id": key, "question": "Q", "gold": gold, "output": output, "tokens": 10, "truncated": False})
             for key, output, gold in rows]
    (folder / f"{mode}.jsonl").write_text("\n".join(lines) + "\n")


def test_analyze_rescores_raw_outputs_and_skips_missing_modes(tmp_path):
    write_run(tmp_path, "tuned", [("a", CLEAN, "2"), ("b", VACUOUS, "9"), ("c", "<think>x</think>\n\nIt is 2.", "2")])
    write_run(tmp_path, "base_instructed", [("a", CLEAN, "9"), ("b", CLEAN, "2")])
    report = analyze(tmp_path, "base_instructed")
    assert set(report) == {"tuned", "base_instructed"}
    tuned = report["tuned"]
    assert tuned["n"] == 3 and tuned["correct"] == 2 and tuned["format_valid"] == 2
    assert tuned["caught_wrong"] == "0/1"
    assert tuned["false_alarm_right"] == "1/2"
    assert tuned["clean_with_vacuous_calc"] == 1
    assert tuned["vs_base_instructed"]["shared"] == 2
