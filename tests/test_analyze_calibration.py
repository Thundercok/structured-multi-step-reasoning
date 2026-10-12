import json
from pathlib import Path
import numpy as np
import pytest
from sklearn.metrics import roc_auc_score

from scripts.analyze_calibration import (
    extract_answer_first_lp,
    _mean_auc_kernel,
    paired_oof_bootstrap,
    run_cv_evaluation_family,
    evaluate_prereg_gate,
    run_analysis,
)


def test_extract_answer_first_lp():
    # Case 1: Pre-existing field
    r1 = {"answer_first_lp": -0.42}
    assert extract_answer_first_lp(r1) == -0.42

    # Case 2: Regex Answer: with mock token logprobs and no tokenizer (fallback to last token)
    r2 = {
        "raw_output": "Step 1: compute 2+2=4.\nAnswer: 4",
        "token_logprobs": [-0.1, -0.2, -0.3, -0.05],
    }
    assert extract_answer_first_lp(r2) == -0.05

    # Case 3: Regex #### format
    r3 = {
        "raw_output": "Reasoning...\n#### 42",
        "token_logprobs": [-0.5, -0.25],
    }
    assert extract_answer_first_lp(r3) == -0.25

    # Case 4: No logprobs
    r4 = {"raw_output": "Answer: 10", "token_logprobs": []}
    assert extract_answer_first_lp(r4) == 0.0

    # Case 5: With mock tokenizer
    class MockTok:
        def encode(self, text):
            # 1 token per 5 chars
            return list(range(len(text) // 5))

    r5 = {
        "raw_output": "1234567890Answer: 99",
        "token_logprobs": [-1.0, -2.0, -3.0, -4.0],
    }
    # prefix is "1234567890Answer: " (len 18) -> encode gives 3 tokens -> index 3 -> -4.0
    assert extract_answer_first_lp(r5, tok=MockTok()) == -4.0


def test_mean_auc_kernel():
    y = np.array([1, 0, 1, 0])
    # 2 repetitions x 4 items
    preds = np.array([
        [0.8, 0.2, 0.7, 0.3],
        [0.9, 0.1, 0.6, 0.4],
    ])
    kernel = _mean_auc_kernel(preds, y)
    # y=1 has 2 items, y=0 has 2 items -> 2x2 kernel matrix
    assert kernel.shape == (2, 2)
    # Check that predictions rank positive above negative in all pairs
    assert np.all(kernel == 1.0)


def test_paired_oof_bootstrap_properties():
    y = np.array([1, 0, 1, 0, 1, 0])
    groups = np.array(["g1", "g2", "g3", "g4", "g5", "g6"])
    oof_predictions = {
        "Baseline": np.array([
            [0.6, 0.4, 0.7, 0.3, 0.8, 0.2],
            [0.5, 0.3, 0.6, 0.4, 0.7, 0.1],
        ]),
        "+ signal": np.array([
            [0.9, 0.1, 0.8, 0.2, 0.9, 0.1],
            [0.85, 0.15, 0.8, 0.2, 0.95, 0.05],
        ]),
    }
    diffs, meta = paired_oof_bootstrap(oof_predictions, y, groups, n_bootstrap=100, seed=42)
    assert "+ signal" in diffs
    assert "Baseline" not in diffs
    assert len(diffs["+ signal"]) == 100
    assert meta["accepted_draws"] == 100
    # Signal is strictly better than baseline -> differences should be >= 0
    assert np.mean(diffs["+ signal"]) >= 0


def test_run_cv_evaluation_family():
    # Construct synthetic 10-item family dataset
    recs = []
    for i in range(10):
        recs.append({
            "group_id": f"grp_{i}",
            "family": "arith",
            "level": float(i % 3 + 1),
            "completion_tokens": float(50 + i * 10),
            "mean_logprob": -0.1 * (i % 5),
            "min_logprob": -0.5 * (i % 5),
            "answer_first_lp": 0.0,
            "correct": bool(i < 7),  # 7 pos, 3 neg
        })
    res = run_cv_evaluation_family("arith", recs, n_splits=3, n_repeats=5, n_bootstrap=50, seed=42)
    assert res["n"] == 10
    assert res["n_pos"] == 7
    assert res["n_neg"] == 3
    assert "Baseline" in res["models"]
    assert "+ mean_logprob" in res["models"]
    assert "+ min_logprob" in res["models"]
    assert "+ answer_first_lp" in res["models"]
    assert 0.0 <= res["baseline_mean_auroc"] <= 1.0


def test_evaluate_prereg_gate():
    # Case 1: Signal fails dual-family gate (passes arith, fails order)
    family_results_fail = {
        "arith": {
            "models": {
                "+ mean_logprob": {"passed": False, "delta": 0.02, "ci_low": -0.01, "ci_high": 0.05},
                "+ min_logprob": {"passed": True, "delta": 0.07, "ci_low": 0.01, "ci_high": 0.15},
                "+ answer_first_lp": {"passed": False, "delta": 0.0, "ci_low": 0.0, "ci_high": 0.0},
            }
        },
        "order": {
            "models": {
                "+ mean_logprob": {"passed": False, "delta": -0.01, "ci_low": -0.05, "ci_high": 0.05},
                "+ min_logprob": {"passed": False, "delta": 0.04, "ci_low": -0.02, "ci_high": 0.12},
                "+ answer_first_lp": {"passed": False, "delta": 0.0, "ci_low": 0.0, "ci_high": 0.0},
            }
        },
    }
    gate = evaluate_prereg_gate(family_results_fail)
    assert gate["passed"] is False
    assert gate["gate_verdict"] == "GATE FAIL"
    assert "verifier- or agreement-based escalation" in gate["prescribed_action"]
    assert gate["signals"]["+ min_logprob"]["signal_passed_dual_family"] is False

    # Case 2: Signal passes dual-family gate (passes both arith and order)
    family_results_pass = {
        "arith": {
            "models": {
                "+ mean_logprob": {"passed": False, "delta": 0.02, "ci_low": -0.01, "ci_high": 0.05},
                "+ min_logprob": {"passed": True, "delta": 0.07, "ci_low": 0.01, "ci_high": 0.15},
                "+ answer_first_lp": {"passed": False, "delta": 0.0, "ci_low": 0.0, "ci_high": 0.0},
            }
        },
        "order": {
            "models": {
                "+ mean_logprob": {"passed": False, "delta": -0.01, "ci_low": -0.05, "ci_high": 0.05},
                "+ min_logprob": {"passed": True, "delta": 0.06, "ci_low": 0.01, "ci_high": 0.12},
                "+ answer_first_lp": {"passed": False, "delta": 0.0, "ci_low": 0.0, "ci_high": 0.0},
            }
        },
    }
    gate_p = evaluate_prereg_gate(family_results_pass)
    assert gate_p["passed"] is True
    assert gate_p["gate_verdict"] == "GATE PASS"
    assert gate_p["signals"]["+ min_logprob"]["signal_passed_dual_family"] is True


def test_run_analysis_end_to_end(tmp_path):
    # Create small synthetic JSONL trace
    records = []
    # 20 COT items (10 arith, 10 order)
    for i in range(20):
        fam = "arith" if i < 10 else "order"
        records.append({
            "id": f"item_{i}",
            "group_id": f"grp_{i}",
            "family": fam,
            "arm": "COT",
            "level": 2,
            "completion_tokens": 100,
            "mean_logprob": -0.2,
            "min_logprob": -0.8,
            "raw_output": f"Answer: {i}",
            "token_logprobs": [-0.1, -0.2, -0.05],
            "correct": (i % 3 != 0),
            "finish_reason": "stop",
        })
    # Add some SC items for paired SC vs COT
    for i in range(20):
        fam = "arith" if i < 10 else "order"
        records.append({
            "id": f"item_{i}",
            "group_id": f"grp_{i}",
            "family": fam,
            "arm": "SC",
            "level": 2,
            "correct": True,
        })

    trace_file = tmp_path / "mock_trace.jsonl"
    with open(trace_file, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    out_prefix = str(tmp_path / "report_")
    run_analysis(trace_file, out_prefix, run_tokens=False)

    assert (tmp_path / "report_0_snapshot_info.txt").exists()
    assert (tmp_path / "report_1_cot_auroc.txt").exists()
    assert (tmp_path / "report_2_cot_logistic_cv.txt").exists()
    assert (tmp_path / "report_3_retokenize_check.txt").exists()
    assert (tmp_path / "report_4_paired_sc_cot.txt").exists()
    assert Path("audit/confidence_signal_gate_report.json").exists()

    x2_text = (tmp_path / "report_2_cot_logistic_cv.txt").read_text()
    assert "Finished-only COT: Repeated 5-fold CV x20" in x2_text
    assert "Gate Decision Rule Evaluation" in x2_text
    assert "Final Verdict: GATE FAIL" in x2_text
