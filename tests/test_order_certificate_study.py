import copy
import hashlib
import json
from collections import Counter

import pytest

from experiments.order_certificate_study import (
    SETTINGS, _smoke_records, evaluate, replay, run_smoke,
    smoke_dataset, summarize, validate_records, prepare_dataset, ROOT,
)
from experiments.research_study import main


def fixture():
    dataset = smoke_dataset()
    records = _smoke_records(dataset)
    validate_records(dataset, records, evidence="synthetic_smoke", settings=SETTINGS)
    return dataset, records


def test_two_certificate_gates_use_the_same_attempt_and_add_all_calls():
    dataset, records = fixture()
    rows = evaluate(dataset, records)
    indexed = {(row["id"], row["seed"], row["method"]): row for row in rows}
    attempts = {(row["id"], row["seed"], row["arm"]): row for row in records}
    for row in rows:
        if row["method"] not in ("w_certificate", "verified_certificate"):
            continue
        assert row["path"][0] == "pal_certificate"
        expected = sum(
            call["prompt_tokens"] + call["completion_tokens"]
            for arm in row["path"] for call in attempts[(row["id"], row["seed"], arm)]["generations"]
        )
        assert row["tokens"] == expected
        assert row["tokens"] == row["prompt_tokens"] + row["completion_tokens"]
        other = indexed[(row["id"], row["seed"], "fixed_pal_certificate")]
        if len(row["path"]) == 1:
            assert row["answer"] == other["answer"]
    summary = summarize(rows, evidence="synthetic_smoke")
    assert summary["decision"] == "synthetic_validation_only"
    for method in ("w_answer", "w_certificate", "verified_certificate"):
        metric = summary["methods"][method]
        assert metric["cost_identity"]["reconstructed_mean_tokens"] == pytest.approx(metric["mean_tokens"])
    assert summary["methods"]["symbolic_solver"]["mean_tokens"] == 0


def test_gold_cannot_change_gate_paths():
    dataset, records = fixture()
    original = evaluate(dataset, records)
    poisoned = copy.deepcopy(dataset)
    for item in poisoned["items"]:
        item["answer"] = "Nobody"
    changed = evaluate(poisoned, records)
    assert [row["path"] for row in original] == [row["path"] for row in changed]
    assert [row["verification_status"] for row in original] == [row["verification_status"] for row in changed]


@pytest.mark.parametrize("mutation", ["missing_selector", "missing_prompt", "wrong_seed", "wrong_answer", "wrong_cap", "duplicate"])
def test_incomplete_or_inconsistent_trace_is_rejected(mutation):
    dataset, records = fixture()
    row = next(row for row in records if row["arm"] == "candidate_selection")
    if mutation == "missing_selector":
        row["generations"].pop()
    elif mutation == "missing_prompt":
        row["generations"][-1]["messages"][0]["content"] = "Best?"
    elif mutation == "wrong_seed":
        row["generations"][0]["seed"] += 1
    elif mutation == "wrong_answer":
        row["answer"] = "Nobody"
    elif mutation == "wrong_cap":
        row["generations"][0]["max_tokens"] += 1
    else:
        records.append(copy.deepcopy(row))
    with pytest.raises(ValueError):
        validate_records(dataset, records, evidence="synthetic_smoke", settings=SETTINGS)


def test_unselected_length_stopped_candidate_does_not_invalidate_selected_answer():
    dataset, records = fixture()
    selected = next(row for row in records if row["arm"] == "candidate_selection" and row["split"] == "test")
    selected["generations"][2]["finish_reason"] = "length"
    validate_records(dataset, records, evidence="synthetic_smoke", settings=SETTINGS)
    outcome = next(row for row in evaluate(dataset, records) if row["id"] == selected["id"] and row["seed"] == selected["seed"] and row["method"] == "fixed_candidate_selection")
    assert outcome["correct"]
    # Contract v3: candidate 0 is length-stopped, candidate 2 was length-stopped,
    # candidate 1 is the sole admissible branch and is redirected to!
    selected["generations"][0]["finish_reason"] = "length"
    outcome = next(row for row in evaluate(dataset, records) if row["id"] == selected["id"] and row["seed"] == selected["seed"] and row["method"] == "fixed_candidate_selection")
    assert outcome["correct"]
    # If all candidates are length-stopped, it must fail.
    selected["generations"][1]["finish_reason"] = "length"
    outcome = next(row for row in evaluate(dataset, records) if row["id"] == selected["id"] and row["seed"] == selected["seed"] and row["method"] == "fixed_candidate_selection")
    assert not outcome["correct"]



def test_cli_smoke_replay_hashes_and_non_overwrite(tmp_path):
    original, analysis = tmp_path / "smoke", tmp_path / "analysis"
    main(["--order-certificate-smoke", "--output", str(original)])
    main(["--order-certificate-analysis", str(original), "--output", str(analysis)])
    manifest = json.loads((original / "manifest.json").read_text())
    assert manifest["model_calls"] is False
    for name, expected in manifest["artifact_sha256"].items():
        assert hashlib.sha256((original / name).read_bytes()).hexdigest() == expected
    # Offline CPU timings vary on replay; quality, tokens and gate paths must not.
    before = json.loads((original / "results.json").read_text())
    after = json.loads((analysis / "results.json").read_text())
    for left, right in zip(before, after):
        for field in ("path", "answer", "correct", "tokens", "verification_status"):
            assert left[field] == right[field]
    with pytest.raises(FileExistsError):
        run_smoke(original)
    (original / "records.json").write_text("[]")
    with pytest.raises(ValueError, match="artifact changed"):
        replay(original, tmp_path / "tampered")


def test_certificate_answer_must_come_from_actual_execution_payload():
    dataset, records = fixture()
    row = next(row for row in records if row["arm"] == "pal_certificate" and row["execution"]["ok"])
    row["answer"] = "Nobody"
    with pytest.raises(ValueError, match="execution payload"):
        validate_records(dataset, records, evidence="synthetic_smoke", settings=SETTINGS)


def test_ci_containing_zero_does_not_establish_noninferiority():
    dataset, records = fixture()
    rows = evaluate(dataset, records)
    target = next(row["id"] for row in rows if row["split"] == "test")
    for row in rows:
        if row["method"] == "verified_certificate":
            row["correct"] = row["id"] != target
            row["tokens"] = 1  # A very cheap policy can still fail the accuracy gate.
    summary = summarize(rows, evidence="synthetic_smoke")
    comparison = summary["paired_verified_minus_candidate"]
    assert comparison["accuracy_delta_ci95"][0] < -0.02
    assert comparison["accuracy_delta_ci95"][1] == 0
    assert not summary["statistical_gate_pass"]


def test_single_group_and_degenerate_accuracy_intervals_cannot_pass():
    dataset, records = fixture()
    rows = evaluate(dataset, records)
    for row in rows:
        if row["method"] == "verified_certificate":
            row["tokens"] = 1
    summary = summarize(rows, evidence="synthetic_smoke")
    assert summary["paired_verified_minus_candidate"]["accuracy_bootstrap_degenerate"]
    assert not summary["statistical_gate_pass"]
    for row in rows:
        row["group_id"] = "one-original-group"
    summary = summarize(rows, evidence="synthetic_smoke")
    assert summary["paired_verified_minus_candidate"]["accuracy_delta_ci95"] is None
    assert summary["paired_verified_minus_candidate"]["token_ratio_ci95"] is None
    assert not summary["statistical_gate_pass"]


def test_preparation_preserves_prospective_content_without_solving(tmp_path, monkeypatch):
    path = ROOT / "data/order_confirmatory_gapB_100.json"
    original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    original = json.loads(path.read_text())
    def forbidden_solver(*args, **kwargs):
        raise AssertionError("Preparation must not solve prospective answers")
    monkeypatch.setattr("experiments.order_certificate_study.solve_order_query", forbidden_solver)
    output = tmp_path / "candidate"
    prepare_dataset(path, output)
    saved = json.loads((output / "dataset.json").read_text())
    assert Counter(row["split"] for row in saved["items"]) == {"train": 8, "calibration": 23, "test": 100}
    source = {row["id"]: row for row in original["items"]}
    for row in saved["items"]:
        if row["split"] == "test":
            for field in ("query", "answer", "meta", "level"):
                assert row[field] == source[row["id"]][field]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == original_hash
    assert saved["human_review_status"] == "pending"
    assert saved["publication_ready"] is False
    assert all(row["canonical_overlap"] == 0 for row in json.loads((output / "isolation.json").read_text()))
    assert json.loads((output / "plan.json").read_text())["measured_collection_enabled"] is False


def test_verified_gate_confusion_retains_all_generation_seeds():
    dataset, records = fixture()
    summary = summarize(evaluate(dataset, records), evidence="synthetic_smoke")
    verified = summary["methods"]["verified_certificate"]
    assert sum(verified["gate_confusion_by_answer"].values()) == verified["questions"] * 3
    assert summary["paired_verified_minus_w_certificate"]["baseline"] == "w_certificate"


def test_measured_backend_cannot_be_enabled_by_an_offline_mode(tmp_path):
    with pytest.raises(SystemExit):
        main(["--order-certificate-smoke", "--backend", "mlx", "--output", str(tmp_path / "forbidden")])
    assert not (tmp_path / "forbidden").exists()


def test_mock_pilot_execution_offline(tmp_path):
    from scripts.pilot_order_certificate import run_pilot
    out_dir = tmp_path / "mock_pilot"
    dataset, records, settings, summary = run_pilot(
        num_items=2,
        seeds=[42],
        output_dir=str(out_dir),
        thinking_max_tokens=1024,
        mock=True,
        verbose=False,
    )
    assert len(dataset["items"]) == 2
    assert len(records) == 8  # 2 items * 4 arms
    assert (out_dir / "records.json").exists()
    assert (out_dir / "records.jsonl").exists()
    assert (out_dir / "summary.json").exists()
    assert (out_dir / "report.md").exists()
    assert summary["summary"]["symbolic_solver"]["accuracy"] == 1.0

