"""Unit tests for H5 Llama-3.1 strict filtering, Holm reading rules, and analysis pipeline."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MOD_PATH = Path(__file__).resolve().parents[1] / "audit" / "llama31_trace_source_20261127" / "hf_runner.py"
spec = importlib.util.spec_from_file_location("hf_runner", MOD_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_strict_trace_clean_rejects_calcless_and_decoupled_steps():
    q = "Natalia sold 48 clips in April and half as many in May. How many altogether?"
    good = (
        "<think>\n"
        "Step 1: May clips: 48/2 = 24.\n"
        "Calc: 48/2=24\n"
        "Step 2: Total: 48+24 = 72.\n"
        "Calc: 48+24=72\n"
        "</think>\n\nAnswer: 72"
    )
    assert mod.is_strict_trace_clean(good, q, "72") == (True, None)

    # Decoupled final step (the 8/229 confound in H3/H4)
    decoupled_last = (
        "<think>\n"
        "Step 1: May clips: 48/2 = 24.\n"
        "Calc: 48/2=24\n"
        "Step 2: Total is 48+24 = 72.\n"
        "</think>\n\nAnswer: 72"
    )
    ok, reason = mod.is_strict_trace_clean(decoupled_last, q, "72")
    assert not ok
    assert reason == "answer_not_from_last_calc"

    # Intermediate step without Calc (the 28/229 confound in H3/H4)
    calcless_mid = (
        "<think>\n"
        "Step 1: First note Natalia sold 48 clips in April.\n"
        "Step 2: May clips: 48/2 = 24.\n"
        "Calc: 48/2=24\n"
        "Step 3: Total: 48+24 = 72.\n"
        "Calc: 48+24=72\n"
        "</think>\n\nAnswer: 72"
    )
    ok2, reason2 = mod.is_strict_trace_clean(calcless_mid, q, "72")
    assert not ok2
    assert reason2 == "step_without_calc"


def test_strip_stop_tokens_trims_eot_and_trailing_pads():
    class DummyTok:
        eos_token = "<|eot_id|>"

    raw = "<think>\nStep 1: 2+2=4\nCalc: 2+2=4\n</think>\n\nAnswer: 4<|eot_id|><|end_of_text|><|end_of_text|>"
    assert mod.strip_stop_tokens(raw, DummyTok()) == "<think>\nStep 1: 2+2=4\nCalc: 2+2=4\n</think>\n\nAnswer: 4"


def test_holm_reading_rules():
    assert mod.holm_reading_two_seeds(
        {"p": 0.01, "only_x": 20, "only_y": 4},
        {"p": 0.03, "only_x": 18, "only_y": 5},
    ) == "replicated_both_seeds"

    assert mod.holm_reading_two_seeds(
        {"p": 0.01, "only_x": 20, "only_y": 4},
        {"p": 0.12, "only_x": 14, "only_y": 7},
    ) == "supported_one_seed_holm"

    assert mod.holm_reading_two_seeds(
        {"p": 0.03, "only_x": 16, "only_y": 6},
        {"p": 0.04, "only_x": 15, "only_y": 6},
    ) == "not_distinguishable"

    assert mod.holm_reading_two_seeds(
        {"p": 0.005, "only_x": 3, "only_y": 19},
        {"p": 0.20, "only_x": 10, "only_y": 8},
    ) == "opposite_direction"


def test_end_to_end_analyze_synthetic_run(tmp_path: Path):
    qids = [f"q{i:03d}" for i in range(30)]
    for tag in ("self_s0", "human_s0", "self_s1", "human_s1"):
        is_self = tag.startswith("self")
        d = tmp_path / f"eval_{tag}"
        d.mkdir(parents=True)
        ev_rows, iv_rows = [], []
        for idx, qid in enumerate(qids):
            ev_rows.append({
                "id": qid, "question": "Q", "gold": "72", "output": "",
                "tokens": 40, "truncated": False,
                "check": {"format_valid": True, "correct": True},
            })
            # Make self follow on items 0..24, human derail after using edit on items 0..14
            if is_self or idx >= 15:
                cont = "Step 2: 48+30=78\nCalc: 48+30=78\n</think>\n\nAnswer: 78"
                outc = "follows"
            else:
                cont = "Step 2: 48+30=78\nCalc: 48+30=78\nStep 3: 78+10=88\nCalc: 78+10=88\n</think>\n\nAnswer: 88"
                outc = "other"
            iv_rows.append({
                "id": qid, "prefix": "<think>\nStep 1: ...\nCalc: 48/2=30\n",
                "old": 24.0, "new": 30.0, "expected": 78.0, "original": 72.0,
                "flags": [], "continuation": cont, "outcome": outc,
                "tokens": 20, "originally_correct": True,
            })
        mod.write_jsonl(d / "tuned.jsonl", ev_rows)
        mod.write_jsonl(d / "tuned_interventions.jsonl", iv_rows)

    res = mod.analyze_h5_run(tmp_path)
    assert res["H5_reading"] == "replicated_both_seeds"
    assert res["H5b_mechanism_B1"]["derail_holm_reading"] == "replicated_both_seeds"
    assert res["H5b_mechanism_B1"]["derail_diff_exceeds_bypass_both_seeds"] is True
    assert (tmp_path / "results.json").exists()
