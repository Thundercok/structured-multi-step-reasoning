"""Unit tests for compare_math.py anatomy and RQ2 Gate evaluation."""

import pytest
from audit.lora_math_20261107.compare_math import (
    analyze_math_tuned_anatomy,
    compute_breakdowns,
    evaluate_rq2_gate,
)


def test_analyze_math_tuned_anatomy_synthetic():
    recs = {
        "rec1": {
            "id": "rec1",
            "truncated": False,
            "output": "<think>\nStep 1: Test\nCalc: 1+1=2\n</think>\n\nAnswer: 2",
            "check": {"correct": True, "format_valid": True, "errors": []},
        },
        "rec2": {
            "id": "rec2",
            "truncated": False,
            "output": "<think>\nStep 1: Test\nCalc: x+y=z\n</think>\n\nAnswer: 2",
            "check": {"correct": True, "format_valid": False, "errors": ["line_outside_grammar"]},
        },
        "rec3": {
            "id": "rec3",
            "truncated": True,
            "output": "Line A\nLine B\n" + "Repeated Line\n" * 6,
            "check": {"correct": False, "format_valid": False, "errors": ["missing_think_close"]},
        },
        "rec4": {
            "id": "rec4",
            "truncated": True,
            "output": "Unique line 1\nUnique line 2\nUnique line 3\n",
            "check": {"correct": False, "format_valid": False, "errors": ["missing_think_close"]},
        },
    }

    res = analyze_math_tuned_anatomy(recs)
    assert res["non_truncated"]["n"] == 2
    assert res["non_truncated"]["correct"] == 2
    assert res["non_truncated"]["format_valid"] == 1
    assert res["non_truncated"]["invalid_format_n"] == 1
    assert res["non_truncated"]["invalid_format_but_correct"] == 1
    assert res["non_truncated"]["error_counts"]["line_outside_grammar"] == 1

    assert res["truncated"]["n"] == 2
    assert res["truncated"]["repetition_loop_n"] == 1
    assert res["truncated"]["long_derivation_n"] == 1


def test_evaluate_rq2_gate_official_branches():
    # Branch 1: < 30 eligible -> unmeasurable
    int_small = {
        "tuned": {
            "eligible": {
                "n": 25,
                "follows": 20,
                "follows_rounded": 2,
                "reverted": 2,
                "other": 1,
                "moved": 0,
            }
        }
    }
    gate1 = evaluate_rq2_gate(int_data=int_small)
    assert "unmeasurable" in gate1["status"]

    # Branch 2: >= 30 eligible, not_followed >= 5 and >= 5% -> active
    int_active = {
        "tuned": {
            "eligible": {
                "n": 50,
                "follows": 40,
                "follows_rounded": 2,
                "reverted": 4,
                "other": 4,  # not_followed = 8 / 50 = 16% >= 5%
                "moved": 0,
            }
        }
    }
    gate2 = evaluate_rq2_gate(int_data=int_active)
    assert "active" in gate2["status"]
    assert gate2["official_evaluation"]["not_followed"] == 8

    # Branch 3: >= 30 eligible, not_followed < 5 -> inactive
    int_inactive = {
        "tuned": {
            "eligible": {
                "n": 50,
                "follows": 45,
                "follows_rounded": 3,
                "reverted": 1,
                "other": 1,  # not_followed = 2 < 5
                "moved": 0,
            }
        }
    }
    gate3 = evaluate_rq2_gate(int_data=int_inactive)
    assert "inactive" in gate3["status"]


def test_compute_breakdowns_synthetic():
    loaded = {
        "math_lora_tuned": {
            "q1": {"id": "q1", "truncated": False, "check": {"correct": True, "format_valid": True}},
            "q2": {"id": "q2", "truncated": True, "check": {"correct": False, "format_valid": False}},
        },
        "base_prefill": {
            "q1": {"id": "q1", "check": {"correct": True}},
            "q2": {"id": "q2", "check": {"correct": True}},
        },
    }
    dev_meta = {
        "q1": {"level": "Level 3", "subject": "algebra"},
        "q2": {"level": "Level 5", "subject": "geometry"},
    }
    res = compute_breakdowns(loaded, dev_meta)
    assert "by_level" in res and "by_subject" in res
    assert res["by_level"]["Level 3"]["n"] == 1
    assert res["by_level"]["Level 3"]["lora_correct"] == 1
    assert res["by_level"]["Level 3"]["lora_non_trunc_correct"] == 1
    assert res["by_level"]["Level 5"]["n"] == 1
    assert res["by_level"]["Level 5"]["lora_truncated"] == 1
    assert res["by_subject"]["algebra"]["n"] == 1
    assert res["by_subject"]["geometry"]["lora_truncated"] == 1
