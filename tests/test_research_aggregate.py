import copy
import hashlib
import json
import math
import shutil

import pytest

from experiments import research_aggregate as aggregate
from experiments.research_study import main, write_json


@pytest.fixture(scope="module")
def smoke_runs(tmp_path_factory):
    root = tmp_path_factory.mktemp("seed-runs")
    runs = []
    for seed in (11, 22, 33):
        output = root / str(seed)
        main(["--backend", "smoke", "--seed", str(seed), "--output", str(output)])
        runs.append(output)
    return runs


def copied_run(smoke_runs, tmp_path):
    return shutil.copytree(smoke_runs[1], tmp_path / "modified")


def edit_artifact(directory, name, data):
    write_json(directory / name, data)
    manifest = json.loads((directory / "manifest.json").read_text())
    manifest["artifact_sha256"][name] = hashlib.sha256((directory / name).read_bytes()).hexdigest()
    write_json(directory / "manifest.json", manifest)


def test_cli_aggregate_preserves_evidence_counts_and_input_hashes(smoke_runs, tmp_path):
    output = tmp_path / "aggregate"
    main(["--aggregate", *map(str, smoke_runs), "--output", str(output)])
    manifest = json.loads((output / "manifest.json").read_text())
    summary = json.loads((output / "summary.json").read_text())
    assert manifest["status"] == "complete"
    assert manifest["kind"] == "multi_seed_aggregate"
    assert manifest["evidence"] == "synthetic_smoke"
    assert manifest["publication_review_required"] is True
    assert "scripts/gen_tasks.py" in manifest["source_sha256"]
    assert summary["generation_seeds"] == [11, 22, 33]
    assert summary["test_queries"] == summary["test_groups"] == 24
    assert all(metrics["n"] == 24 for metrics in summary["methods"].values())
    assert len(summary["per_seed"]) == 3
    for source, recorded in zip(smoke_runs, manifest["inputs"]):
        assert recorded["manifest_sha256"] == hashlib.sha256((source / "manifest.json").read_bytes()).hexdigest()
    for name, expected in manifest["artifact_sha256"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == expected
    report = (output / "report.md").read_text()
    assert "do not increase" in report
    assert "not measured online" in report
    assert "synthetic token units" in report
    with pytest.raises(SystemExit):
        main(["--aggregate", *map(str, smoke_runs), "--output", str(output)])


def test_seed_average_precedes_group_bootstrap(monkeypatch, smoke_runs):
    template = aggregate.load_run(smoke_runs[0])
    dataset = copy.deepcopy(template["dataset"])
    dataset["items"] = [item for item in dataset["items"] if item["split"] != "test"]
    for identifier, group in (("a1", "a"), ("a2", "a"), ("b", "b")):
        dataset["items"].append({
            "id": identifier, "group_id": group, "split": "test", "query": identifier,
            "answer": "OK", "answer_type": "text",
        })
    runs = []
    for seed in (0, 1):
        run = copy.deepcopy(template)
        run["manifest"]["seed"] = seed
        run["dataset"] = dataset
        rows = []
        for index, (identifier, group) in enumerate((("a1", "a"), ("a2", "a"), ("b", "b"))):
            for method in sorted(aggregate.METHODS):
                # Seeds disagree on each question; their paired mean is always 0.5.
                correct = bool((index < 2) != bool(seed)) if method == "full_policy" else False
                rows.append({
                    "id": identifier, "group_id": group, "method": method,
                    "correct": correct, "tokens": 20 if method == "full_policy" else 50,
                    "strategy_ms_sum": 0, "embedding_ms": 0, "escalated": False,
                })
        run["results"] = rows
        run["indexed"] = {(row["id"], row["method"]): row for row in rows}
        runs.append(run)
    monkeypatch.setattr(aggregate, "load_run", lambda path: runs[int(str(path))])
    _, summary = aggregate.aggregate_runs(["0", "1"])
    assert summary["test_queries"] == 3
    assert summary["test_groups"] == 2
    assert summary["methods"]["full_policy"]["n"] == 3
    assert summary["methods"]["full_policy"]["accuracy"] == 0.5
    assert summary["methods"]["full_policy"]["seed_variability"]["accuracy"]["sample_sd"] == pytest.approx(math.sqrt(1 / 18))
    comparison = summary["paired_full_minus_baseline"]["one_shot_router"]
    assert comparison["correct"]["ci95"] == [0.5, 0.5]
    assert comparison["tokens"]["ci95"] == [-30, -30]
    assert comparison["utility"]["mean_difference"] == pytest.approx(0.5006)


def test_duplicate_seeds_including_replay_copies_are_rejected(smoke_runs, tmp_path):
    with pytest.raises(ValueError, match="at least two"):
        aggregate.aggregate_runs(smoke_runs[:1])
    with pytest.raises(ValueError, match="directories must be distinct"):
        aggregate.aggregate_runs([smoke_runs[0], smoke_runs[0]])
    replay = tmp_path / "replay"
    main(["--replay", str(smoke_runs[0]), "--output", str(replay)])
    with pytest.raises(ValueError, match="Duplicate generation seed"):
        aggregate.aggregate_runs([smoke_runs[0], replay])


@pytest.mark.parametrize("field,value", [
    ("lambda", 0.5), ("model", "different-checkpoint"),
    ("token_scope", "full inference tokens"), ("source_sha256", {"different.py": "0" * 64}),
    ("packages", {"numpy": "different"}), ("platform", "different-hardware"),
])
def test_incompatible_settings_are_rejected(smoke_runs, tmp_path, field, value):
    modified = copied_run(smoke_runs, tmp_path)
    manifest = json.loads((modified / "manifest.json").read_text())
    manifest[field] = value
    write_json(modified / "manifest.json", manifest)
    with pytest.raises(ValueError, match=field):
        aggregate.aggregate_runs([smoke_runs[0], modified])


def test_different_frozen_dataset_is_rejected(smoke_runs, tmp_path):
    modified = copied_run(smoke_runs, tmp_path)
    dataset = json.loads((modified / "dataset.json").read_text())
    dataset["version"] = "different"
    edit_artifact(modified, "dataset.json", dataset)
    with pytest.raises(ValueError, match="frozen dataset differs"):
        aggregate.aggregate_runs([smoke_runs[0], modified])


@pytest.mark.parametrize("name", ["results.json", "records.json", "report.md"])
def test_changed_input_bytes_are_rejected(smoke_runs, tmp_path, name):
    modified = copied_run(smoke_runs, tmp_path)
    with (modified / name).open("a") as stream:
        stream.write(" ")
    with pytest.raises(ValueError, match="artifact changed"):
        aggregate.aggregate_runs([smoke_runs[0], modified])


@pytest.mark.parametrize("change,match", [
    ("duplicate", "Duplicate result"), ("missing", "identical complete"),
    ("group", "group differs"), ("train", "only frozen test IDs"),
    ("tokens", "positive integer"), ("nan", "finite"),
    ("path", "Invalid strategy path"), ("cost", "token cost disagrees"),
    ("answer", "answer/correctness disagrees"),
])
def test_invalid_or_unpaired_results_cannot_enter_summary(smoke_runs, tmp_path, change, match):
    modified = copied_run(smoke_runs, tmp_path)
    rows = json.loads((modified / "results.json").read_text())
    row = next(row for row in rows if row["method"] == "fixed_cot")
    if change == "duplicate":
        rows.append(copy.deepcopy(row))
    elif change == "missing":
        rows.remove(row)
    elif change == "group":
        row["group_id"] = "wrong"
    elif change == "train":
        row["id"] = "pal_train_0"
    elif change == "tokens":
        row["tokens"] = True
    elif change == "nan":
        row["strategy_ms_sum"] = float("inf")
    elif change == "path":
        row["path"] = ["PAL"]
    elif change == "cost":
        row["tokens"] += 1
    elif change == "answer":
        row["answer"] = "changed"
    if change == "nan":
        # Allow a malformed external artifact so the reader, not the writer, rejects it.
        (modified / "results.json").write_text(json.dumps(rows))
        manifest = json.loads((modified / "manifest.json").read_text())
        manifest["artifact_sha256"]["results.json"] = hashlib.sha256((modified / "results.json").read_bytes()).hexdigest()
        write_json(modified / "manifest.json", manifest)
    else:
        edit_artifact(modified, "results.json", rows)
    with pytest.raises(ValueError, match=match):
        aggregate.aggregate_runs([smoke_runs[0], modified])


def test_failed_run_and_setting_overrides_fail_before_output_creation(smoke_runs, tmp_path):
    modified = copied_run(smoke_runs, tmp_path)
    manifest = json.loads((modified / "manifest.json").read_text())
    manifest["status"] = "failed"
    write_json(modified / "manifest.json", manifest)
    output = tmp_path / "invalid"
    with pytest.raises(SystemExit):
        main(["--aggregate", str(smoke_runs[0]), str(modified), "--output", str(output)])
    assert not output.exists()
    with pytest.raises(SystemExit):
        main(["--aggregate", *map(str, smoke_runs), "--lam", "0.7", "--output", str(output)])
    assert not output.exists()


@pytest.mark.parametrize("change,match", [
    ("evidence", "backend and evidence"), ("missing_hash", "required artifact hashes"),
    ("raw_hash", "raw attempts artifact hash"), ("outside_file", "within the run directory"),
])
def test_evidence_and_artifact_manifest_are_required(smoke_runs, tmp_path, change, match):
    modified = copied_run(smoke_runs, tmp_path)
    manifest = json.loads((modified / "manifest.json").read_text())
    if change == "evidence":
        manifest["evidence"] = "measured_strategy_replay"
    elif change == "missing_hash":
        del manifest["artifact_sha256"]["results.json"]
    elif change == "raw_hash":
        del manifest["artifact_sha256"]["attempts.jsonl"]
    else:
        manifest["artifact_sha256"]["../outside.json"] = "0" * 64
    write_json(modified / "manifest.json", manifest)
    with pytest.raises(ValueError, match=match):
        aggregate.aggregate_runs([smoke_runs[0], modified])
