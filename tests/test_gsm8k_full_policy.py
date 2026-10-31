"""Tests for Full Adaptive Policy Evaluation (Entry Routing + Optimal Stopping)."""
from fractions import Fraction
import json
from pathlib import Path
import pytest

from experiments import gsm8k_full_policy_evaluation as full_pol
from experiments import gsm8k_routing_baseline as routing
from experiments.research_study import seed_for


def synthetic_full_fixture():
    items, records = [], []
    for split in ("train", "calibration"):
        for index, words in enumerate((15, 30, 65, 85)):
            ident = f"syn-{split}-{index}"
            query = " ".join([ident] + ["word"] * (words - 1))
            item = {
                "id": ident,
                "group_id": ident,
                "split": split,
                "query": query,
                "answer": "42",
                "answer_type": "number",
                "category": "synthetic",
            }
            items.append(item)
            for action in routing.ACTIONS:
                # PAL is always correct; DIRECT is correct only if short; COT is correct only if very short
                correct = action == "PAL" or (action == "DIRECT" and words <= 50)
                answer = "42" if correct else "99"
                conf = 0.98 if correct else 0.85
                tokens = {"DIRECT": 20, "COT": 80, "PAL": 150}[action]
                generation = {
                    "output": f"Answer: {answer}",
                    "tokens": tokens,
                    "prompt_tokens": 10,
                    "max_tokens": 1024,
                    "temperature": 0.0,
                    "enable_thinking": False,
                    "finish_reason": "stop",
                    "messages": [{"role": "user", "content": query}],
                }
                tools = [{"name": "python", "ok": True, "output": answer, "duration_ms": 0.5}] if action == "PAL" else []
                if action == "PAL":
                    generation["output"] = f"result = {answer}"
                records.append({
                    "id": ident,
                    "group_id": ident,
                    "split": split,
                    "strategy": action,
                    "token_budget": 1024,
                    "seed": seed_for(42, ident, action),
                    "answer_format": {"answer_type": "number", "decimal_separator": "."},
                    "answer": answer,
                    "correct": correct,
                    "confidence": conf,
                    "tokens": tokens,
                    "strategy_ms": 1.0,
                    "trace": {"parse_status": "marker", "generations": [generation], "tools": tools},
                })
    return items, records


def test_fit_full_policy_finds_valid_thresholds():
    items, records = synthetic_full_fixture()
    train_items = [i for i in items if i["split"] == "train"]
    train_records = [r for r in records if r["split"] == "train"]

    fit = full_pol.fit_full_policy(train_items, train_records, lam=Fraction(1, 10))
    assert fit["policy_version"] == full_pol.POLICY_VERSION
    assert "entry_rule" in fit
    assert "thresholds_all" in fit
    assert "thresholds_subset" in fit
    assert isinstance(fit["thresholds_all"]["tau_0"], float)
    assert isinstance(fit["thresholds_all"]["tau_1"], float)


def test_evaluate_full_policy_rejects_train_leakage():
    items, records = synthetic_full_fixture()
    fit = full_pol.fit_full_policy([i for i in items if i["split"] == "train"],
                                   [r for r in records if r["split"] == "train"])

    val_items = [dict(i) for i in items if i["split"] == "calibration"]
    # Change first val item id to match a train id
    leaked_id = fit["fitting_ids"][0]
    val_items[0]["id"] = leaked_id

    val_records = [dict(r) for r in records if r["split"] == "calibration"]
    for r in val_records:
        if r["group_id"] == val_items[0]["group_id"]:
            r["id"] = leaked_id

    with pytest.raises(ValueError, match="Train item ID leaked into calibration validation"):
        full_pol.evaluate_full_policy_selection(fit, val_items, val_records)


def test_evaluate_full_policy_computes_h1_comparison():
    items, records = synthetic_full_fixture()
    fit = full_pol.fit_full_policy([i for i in items if i["split"] == "train"],
                                   [r for r in records if r["split"] == "train"])

    val_items = [i for i in items if i["split"] == "calibration"]
    val_records = [r for r in records if r["split"] == "calibration"]

    summary, results = full_pol.evaluate_full_policy_selection(fit, val_items, val_records)

    assert "full_policy_3rung_vs_one_shot_router" in summary["comparisons"]
    comp = summary["comparisons"]["full_policy_3rung_vs_one_shot_router"]
    assert "rescues" in comp
    assert "harms" in comp
    assert "metrics" in comp
    assert "utility" in comp["metrics"]
    assert len(results) > 0


def test_write_full_policy_run_end_to_end(tmp_path: Path):
    items, records = synthetic_full_fixture()
    run_dir = tmp_path / "mock_run"
    run_dir.mkdir()
    dataset = {
        "name": "synthetic-test",
        "version": "1",
        "role": "development_tuning",
        "source": "synthetic",
        "items": items,
    }
    with open(run_dir / "dataset.json", "w") as f:
        json.dump(dataset, f)
    with open(run_dir / "records.json", "w") as f:
        json.dump(records, f)
    manifest = {
        "status": "complete",
        "evidence": "synthetic_staged_pilot_collection",
        "artifact_sha256": {
            "dataset.json": full_pol.sha256_file(run_dir / "dataset.json"),
            "records.json": full_pol.sha256_file(run_dir / "records.json"),
        },
    }
    with open(run_dir / "manifest.json", "w") as f:
        json.dump(manifest, f)

    out_dir = tmp_path / "output_eval"
    state = full_pol.write_full_policy_run(run_dir, out_dir)

    assert state["status"] == "complete"
    assert (out_dir / "policy_fit.json").is_file()
    assert (out_dir / "summary.json").is_file()
    assert (out_dir / "results.json").is_file()
    assert (out_dir / "report.md").is_file()
    assert (out_dir / "manifest.json").is_file()
