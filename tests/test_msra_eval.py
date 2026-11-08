"""Unit tests for MSRA evaluation harness."""

import pytest
from structured_llm.msra.evaluate_msra import (
    evaluate_records,
    score_trace,
    wilson_interval,
)
from structured_llm.msra.router import CapabilityRouter
from structured_llm.msra.stream_driver import MockGeneratorBackend, MSRAStepDriver


def test_wilson_interval():
    low, high = wilson_interval(50, 100)
    assert 40.0 <= low <= 41.0
    assert 59.0 <= high <= 61.0


def test_score_trace_valid_and_correct():
    trace_text = (
        '<step id="1" budget_remaining="2.00">\n'
        "  <subgoal>Compute answer</subgoal>\n"
        "  <deps>None</deps>\n"
        "  <capability>CAP:SYMBOLIC_CALC</capability>\n"
        "  <decision>SOLVE_LOCAL</decision>\n"
        "  <execution>5 * 10 = 50</execution>\n"
        '  <verification status="COMMIT">Exact</verification>\n'
        "  <output_var>v1 = 50</output_var>\n"
        "</step>\n\n"
        "<final_answer>50</final_answer>"
    )

    scored = score_trace(trace_text, "50")
    assert scored["xml_valid"] is True
    assert scored["dag_valid"] is True
    assert scored["correct"] is True
    assert scored["final_answer"] == "50"
    assert scored["num_steps"] == 1


def test_evaluate_records_mock_driver():
    records = [
        {
            "id": "test_1",
            "text": "<|im_start|>user\nWhat is 2+2?<|im_end|>\n<|im_start|>assistant\nAnswer: 4<|im_end|>",
            "gold": "4",
        }
    ]

    router = CapabilityRouter()
    backend = MockGeneratorBackend({
        '<step id="1"': (
            "  <subgoal>Add 2 and 2</subgoal>\n"
            "  <deps>None</deps>\n"
            "  <capability>CAP:SYMBOLIC_CALC</capability>\n"
            "  <decision>SOLVE_LOCAL</decision>\n"
            "  <execution>2+2 = 4</execution>\n"
            '  <verification status="COMMIT">Exact</verification>\n'
            "  <output_var>v1 = 4</output_var>\n"
            "</step>"
        ),
        "<step id=\"2\"": "<final_answer>4</final_answer>",
        "<final_answer>": "4</final_answer>",
    })

    driver = MSRAStepDriver(backend=backend, router=router)
    res = evaluate_records(records, driver)

    assert res["evaluated_problems"] == 1
    assert res["accuracy"] == 100.0
    assert res["xml_valid_rate"] == 100.0
    assert res["dag_valid_rate"] == 100.0


def test_evaluate_records_dev_jsonl_format():
    records = [
        {
            "id": "gsm8k_dev_1",
            "question": "What is 2+2?",
            "answer": "4",
        }
    ]

    router = CapabilityRouter()
    backend = MockGeneratorBackend({
        '<step id="1"': (
            "  <subgoal>Add 2 and 2</subgoal>\n"
            "  <deps>None</deps>\n"
            "  <capability>CAP:SYMBOLIC_CALC</capability>\n"
            "  <decision>SOLVE_LOCAL</decision>\n"
            "  <execution>2+2 = 4</execution>\n"
            '  <verification status="COMMIT">Exact</verification>\n'
            "  <output_var>v1 = 4</output_var>\n"
            "</step>"
        ),
        "<step id=\"2\"": "<final_answer>4</final_answer>",
        "<final_answer>": "4</final_answer>",
    })

    driver = MSRAStepDriver(backend=backend, router=router)
    res = evaluate_records(records, driver)

    assert res["evaluated_problems"] == 1
    assert res["accuracy"] == 100.0
    assert res["xml_valid_rate"] == 100.0
