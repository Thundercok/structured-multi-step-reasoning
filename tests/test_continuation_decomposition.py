"""Unit tests for post-hoc continuation decomposition (bypass vs. derailment)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import pytest

MOD_PATH = Path(__file__).resolve().parents[1] / "audit" / "trace_dose_20261120" / "decompose_continuations.py"
spec = importlib.util.spec_from_file_location("decompose_continuations", MOD_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_rejects_expected_none():
    with pytest.raises(ValueError):
        mod.classify_b1_record({"outcome": "moved", "new": 30.0, "expected": None, "continuation": ""})


def test_follows_and_reverted_buckets():
    r_fol = mod.classify_b1_record({
        "outcome": "follows", "new": 30.0, "expected": 78.0,
        "continuation": "Step 2: 48+30=78\nCalc: 48+30=78\n</think>\n\nAnswer: 78",
    })
    assert r_fol["bucket"] == "follows_exact"
    assert r_fol["used_new"] is True

    r_rev = mod.classify_b1_record({
        "outcome": "reverted", "new": 30.0, "expected": 78.0,
        "continuation": "Step 2: 48+24=72\nCalc: 48+24=72\n</think>\n\nAnswer: 72",
    })
    assert r_rev["bucket"] == "bypass_or_revert"
    assert r_rev["submode"] == "reverted_pure_bypass"


def test_derailment_submodes():
    # 1. Hit expected midway then over-stepped
    r_over = mod.classify_b1_record({
        "outcome": "other", "new": 20.0, "expected": 800.0,
        "continuation": "Step 2: 20*40=800\nCalc: 20*40=800\nStep 3: 800*40=32000\nCalc: 800*40=32000\n</think>\n\nAnswer: 32000",
    })
    assert r_over["bucket"] == "derailed_after_using_new"
    assert r_over["submode"] == "hit_expected_overstepped"

    # 2. Used new, committed arithmetic slip
    r_arith = mod.classify_b1_record({
        "outcome": "other", "new": 21.0, "expected": 51.0,
        "continuation": "Step 2: 21+2=23\nCalc: 21+2=23\nStep 3: 23+28=41\nCalc: 23+28=41\n</think>\n\nAnswer: 41",
    })
    assert r_arith["bucket"] == "derailed_after_using_new"
    assert r_arith["submode"] == "bad_arith"

    # 3. Never used new -> pure bypass
    r_byp = mod.classify_b1_record({
        "outcome": "other", "new": 21.0, "expected": 51.0,
        "continuation": "Step 2: 18+2=20\nCalc: 18+2=20\n</think>\n\nAnswer: 20",
    })
    assert r_byp["bucket"] == "bypass_or_revert"
    assert r_byp["submode"] == "other_pure_bypass"
