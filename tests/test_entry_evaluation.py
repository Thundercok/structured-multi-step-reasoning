"""Authored software fixtures for offline development evaluation; zero model calls."""

import builtins
import hashlib
import json

import numpy as np
import pytest

from experiments import entry_evaluation as evaluation
from experiments.research_study import main, smoke_dataset, write_json
from reasoning.entry_predictor import EntryPredictor, EntryTrainingData


@pytest.fixture
def recorded_run(tmp_path):
    directory = tmp_path / "recorded"
    directory.mkdir()
    dataset = smoke_dataset()
    records, events = [], []
    strategies = sorted(evaluation.REQUIRED_STRATEGIES)
    for i, item in enumerate(dataset["items"]):
        # Two distinct questions share an original-problem group.
        item["group_id"] = f"{item['split']}-group-{(i % 24) // 2}"
        attempts = {}
        for k, strategy in enumerate(strategies):
            correct = (i + k) % 3 != 0
            attempts[strategy] = {"answer": "OK" if correct else "wrong", "correct": correct,
                                  "confidence": .8 if correct else .2, "tokens": 100 + k,
                                  "strategy_ms": 0.0, "seed": i * 10 + k}
            events.append({"id": item["id"], "strategy": strategy, **attempts[strategy]})
        records.append({"id": item["id"], "group_id": item["group_id"], "split": item["split"],
                        "embedding": [float(i % 3), float(i % 5), 1.0, 0.2],
                        "complexity": [1.0, float(i % 2), 0.0], "attempts": attempts})
    write_json(directory / "dataset.json", dataset)
    write_json(directory / "records.json", records)
    (directory / "attempts.jsonl").write_text("".join(json.dumps(row) + "\n" for row in events))
    manifest = {"schema_version": 1, "status": "complete", "backend": "smoke", "evidence": "synthetic_smoke",
                "lambda": .02, "seed": 42, "model": None, "model_revision_verified": False,
                "token_scope": "synthetic token units", "source_sha256": {"authored_fixture": "0" * 64},
                "artifact_sha256": {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                                    for name in ("dataset.json", "records.json", "attempts.jsonl")}}
    write_json(directory / "manifest.json", manifest)
    return directory


def rebind(directory, name, value):
    write_json(directory / name, value)
    manifest = json.loads((directory / "manifest.json").read_text())
    manifest["artifact_sha256"][name] = hashlib.sha256((directory / name).read_bytes()).hexdigest()
    write_json(directory / "manifest.json", manifest)


def test_cli_retains_provenance_excludes_test_and_refuses_overwrite(recorded_run, tmp_path):
    output = tmp_path / "evaluation"
    arguments = ["--entry-evaluation", str(recorded_run), "--entry-configs", "old", "--entry-folds", "2",
                 "--entry-repeats", "2", "--entry-bootstrap", "10", "--output", str(output)]
    main(arguments)
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["evidence"] == "synthetic_development_cv"
    assert manifest["real_model_calls"] == 0 and manifest["stage_0_changed"] is False
    assert manifest["excluded_test_items"] == 24 and manifest["configuration_selected"] is None
    assert manifest["input_manifest_sha256"] == hashlib.sha256((recorded_run / "manifest.json").read_bytes()).hexdigest()
    predictions = json.loads((output / "predictions.json").read_text())
    assert {row["split"] for row in predictions} == {"train"}
    for fold in json.loads((output / "folds.json").read_text()):
        assert not set(fold["train_groups"]) & set(fold["evaluation_groups"])
    for name, digest in manifest["artifact_sha256"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest
    with pytest.raises(SystemExit):
        main(arguments)


def test_base_rates_use_outer_training_only_and_repeat_metrics_match(recorded_run):
    loaded = evaluation.load_recorded_run(recorded_run)
    result = evaluation.evaluate_development(loaded["development"], .02, configs=["old"], folds=2, repeats=2, bootstrap=5)
    targets = {row["id"]: row for row in result["targets"]}
    for fold in result["folds"]:
        expected = np.mean([targets[identifier]["route_accuracy"] for identifier in fold["train_ids"]], axis=0)
        selected = [row for row in result["predictions"] if row["method"] == "training_base_rate"
                    and row["repeat"] == fold["repeat"] and row["fold"] == fold["fold"]]
        assert selected
        for row in selected:
            np.testing.assert_allclose(row["predicted_accuracy"], expected)
    for method, repeats in result["summary"]["per_repeat"].items():
        for metric in evaluation.METRICS:
            assert result["summary"]["methods"][method][metric]["mean"] == pytest.approx(np.mean([row[metric] for row in repeats]))


def test_test_payload_cannot_affect_fit_or_predictions(recorded_run):
    before = evaluation.load_recorded_run(recorded_run)
    records = json.loads((recorded_run / "records.json").read_text())
    for record in records:
        if record["split"] == "test":
            record["embedding"] = None
            record["attempts"] = {"POISONED_TEST": {"correct": "must not be evaluated"}}
    rebind(recorded_run, "records.json", records)
    after = evaluation.load_recorded_run(recorded_run)
    assert before["development"] == after["development"]


def test_tampered_bytes_and_raw_record_disagreement_are_rejected(recorded_run):
    path = recorded_run / "records.json"
    original = path.read_bytes()
    path.write_bytes(original + b" ")
    with pytest.raises(ValueError, match="changed"):
        evaluation.load_recorded_run(recorded_run)
    path.write_bytes(original)
    records = json.loads(original)
    records[0]["attempts"]["COT"]["tokens"] += 1
    rebind(recorded_run, "records.json", records)
    with pytest.raises(ValueError, match="Raw development attempts"):
        evaluation.load_recorded_run(recorded_run)


@pytest.mark.parametrize("mutation,error", [("nonfinite", "finite"), ("split", "split"), ("missing", "five"), ("scoring", "scoring")])
def test_invalid_development_records_fail_before_output(recorded_run, tmp_path, mutation, error):
    records = json.loads((recorded_run / "records.json").read_text())
    if mutation == "nonfinite":
        records[0]["embedding"] = ["nan"]
    elif mutation == "split":
        records[0]["split"] = "test"
    elif mutation == "missing":
        records[0]["attempts"].pop("PAL")
    else:
        records[0]["attempts"]["COT"]["correct"] = not records[0]["attempts"]["COT"]["correct"]
    rebind(recorded_run, "records.json", records)
    output = tmp_path / "forbidden"
    with pytest.raises(ValueError, match=error):
        evaluation.write_evaluation(recorded_run, output, configs=["old"], folds=2, repeats=1, bootstrap=5)
    assert not output.exists()


def test_output_inside_input_and_unrelated_cli_overrides_are_rejected(recorded_run, tmp_path):
    with pytest.raises(ValueError, match="separate"):
        evaluation.write_evaluation(recorded_run, recorded_run / "child")
    with pytest.raises(SystemExit):
        main(["--entry-evaluation", str(recorded_run), "--lam", "1", "--output", str(tmp_path / "forbidden")])
    with pytest.raises(SystemExit):
        main(["--backend", "smoke", "--entry-folds", "2", "--output", str(tmp_path / "forbidden")])


def test_inner_group_cv_keeps_groups_and_scores_single_class_validation(monkeypatch):
    import reasoning.entry_predictor as module
    monkeypatch.setattr(module, "_C_GRID", [0.01])
    monkeypatch.setattr(module, "_ALPHA_GRID", [1000.0])
    rng = np.random.default_rng(42)
    groups = np.repeat(["a", "b", "c", "d"], 2)
    y = np.tile(np.array([0, 0, 1, 1, 0, 0, 1, 1])[:, None], (1, 3))
    data = EntryTrainingData(rng.normal(size=(8, 6)), rng.normal(size=(8, 3)), y, rng.uniform(size=(8, 3)))
    predictor = EntryPredictor(cv_folds=4).fit(data, groups=groups)
    for tr, te in predictor.perf[0].cv:
        assert not set(groups[tr]) & set(groups[te])
    assert np.isfinite(predictor.score(data.embed[0], data.complexity[0])).all()


def test_impossible_class_isolated_group_cv_uses_fixed_regularization():
    rng = np.random.default_rng(42)
    data = EntryTrainingData(rng.normal(size=(4, 6)), rng.normal(size=(4, 3)),
                             np.tile([[0], [0], [1], [1]], (1, 3)), np.ones((4, 3)))
    predictor = EntryPredictor().fit(data, groups=["a", "a", "b", "b"])
    assert not hasattr(predictor.perf[0], "best_estimator_")
    assert np.isfinite(predictor.score(data.embed[0], data.complexity[0])).all()


def test_group_interval_counts_original_groups_once():
    result = evaluation.group_interval([1., 1., 0.], ["a", "a", "b"], 42, 20)
    assert result["groups"] == 2 and result["mean"] == pytest.approx(2 / 3)
    assert "refitting" in result["scope"]


def test_offline_evaluation_does_not_import_model_or_gui(recorded_run, tmp_path, monkeypatch):
    original_import = builtins.__import__
    def guarded(name, *args, **kwargs):
        if name.split(".")[0] in {"mlx", "mlx_lm", "PyQt6", "rat", "qwen_mlx_backend"}:
            pytest.fail(f"Offline evaluator attempted forbidden import: {name}")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", guarded)
    evaluation.write_evaluation(recorded_run, tmp_path / "offline", configs=["old"], folds=2, repeats=1, bootstrap=5)


@pytest.mark.parametrize("options", [{"folds": 1}, {"folds": 100}, {"repeats": 0}, {"bootstrap": 0}, {"configs": ["old", "old"]}])
def test_invalid_settings_create_no_output(recorded_run, tmp_path, options):
    output = tmp_path / "invalid"
    settings = {"configs": ["old"], "folds": 2, "repeats": 1, "bootstrap": 5, **options}
    with pytest.raises(ValueError):
        evaluation.write_evaluation(recorded_run, output, **settings)
    assert not output.exists()
