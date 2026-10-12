"""Offline regression checks; fixtures do not establish model quality."""

import hashlib
import json
import sys

import numpy as np
import pytest
from sklearn.metrics import roc_auc_score

from scripts import agreement
from scripts.agreement import canonicalize_answer


def test_arith_canonicalizer_units_fixture():
    # Primary prereg fixture: '192' vs '192 slices'
    assert canonicalize_answer("192", "arith") == canonicalize_answer("192 slices", "arith")
    assert canonicalize_answer("192", "arith") == "192"
    assert canonicalize_answer("192 slices", "arith") == "192"


def test_arith_canonicalizer_commas():
    assert canonicalize_answer("2,760", "arith") == "2760"
    assert canonicalize_answer("2760", "arith") == "2760"
    assert canonicalize_answer("2,760", "arith") == canonicalize_answer("2760", "arith")


def test_order_canonicalizer_casing_and_punctuation():
    # Order fixture: 'Carol.' vs 'carol'
    assert canonicalize_answer("Carol.", "order") == canonicalize_answer("carol", "order")
    assert canonicalize_answer("Carol.", "order") == "carol"
    assert canonicalize_answer("**Answer**: Bob.", "order") == "bob"
    assert canonicalize_answer("Frank", "order") == "frank"


def test_g24_canonicalizer_validity():
    meta = {"numbers": [3, 8, 3, 8]}
    # Valid expression evaluated by check24
    assert canonicalize_answer("8/(3-8/3)", "g24", meta) == "__VALID_24__"
    # Invalid expression
    assert canonicalize_answer("3+8+3+8", "g24", meta) != "__VALID_24__"


def test_mean_repeat_auc_is_not_auc_of_mean_predictions():
    y = np.array([0, 0, 1, 1])
    predictions = np.array([[0, .9, .8, 1], [0, 0, .8, -10]])
    direct = np.mean([roc_auc_score(y, scores) for scores in predictions])
    assert agreement._mean_auc_kernel(predictions, y).mean() == pytest.approx(direct)
    assert direct != pytest.approx(roc_auc_score(y, predictions.mean(axis=0)))
    assert agreement._mean_auc_kernel(np.zeros((2, 4)), y).mean() == .5


def test_paired_bootstrap_matches_direct_repeat_auc_and_retains_group_variants():
    y = np.array([0, 0, 1, 1, 1, 0])
    groups = np.array(["a", "a", "b", "c", "c", "d"])
    base = np.array([[.1, .5, .3, .7, .7, .3], [.5, .5, .9, .7, .1, .5]])
    predictions = {"Baseline": base, "signal": base[:, ::-1]}
    observed, metadata = agreement.paired_oof_bootstrap(predictions, y, groups, n_bootstrap=40, seed=7)
    rng = np.random.default_rng(7)
    unique = sorted(set(groups))
    expected = []
    attempts = 0
    while len(expected) < 40:
        draw = rng.integers(0, len(unique), size=len(unique))
        indices = [index for group_index in draw for index in np.flatnonzero(groups == unique[group_index])]
        attempts += 1
        if len(set(y[indices])) != 2:
            continue
        model_aucs = {name: np.mean([roc_auc_score(y[indices], scores[indices]) for scores in preds])
                      for name, preds in predictions.items()}
        expected.append(model_aucs["signal"] - model_aucs["Baseline"])
    assert observed["signal"] == pytest.approx(expected)
    assert metadata["attempted_draws"] == attempts
    assert metadata["discarded_one_class_draws"] > 0
    assert metadata["refit"] is False


@pytest.fixture
def cv_design():
    y = np.repeat([0, 1, 0, 1, 0, 1], 2)
    groups = np.repeat(["a", "b", "c", "d", "e", "f"], 2)
    baseline = np.array([[i % 3, i] for i in range(len(y))], dtype=float)
    models = {"Baseline": baseline, "signal": np.column_stack([baseline, y])}
    return baseline, models, y, groups


def test_cv_saved_predictions_and_intervals_use_identical_statistic(cv_design):
    artifacts = {}
    results = agreement.run_cv_evaluation(*cv_design, n_splits=3, n_repeats=3, n_bootstrap=40, seed=9, artifacts=artifacts)
    _, _, y, groups = cv_design
    assignments = np.array(artifacts["fold_assignments"])
    for rep in assignments:
        assert set(rep) == {0, 1, 2}
        for group in set(groups):
            assert len(set(rep[groups == group])) == 1
    for name, predictions in artifacts["oof_predictions"].items():
        assert np.asarray(predictions).shape == (3, len(y))
        assert np.isfinite(predictions).all()
        direct = np.mean([roc_auc_score(y, scores) for scores in predictions])
        assert results[name]["mean_auroc"] == pytest.approx(direct)
        assert results[name]["preregistration_pass"] is False
    metric = results["signal"]
    assert metric["delta"] == pytest.approx(metric["mean_auroc"] - results["Baseline"]["mean_auroc"])
    low, high = np.quantile(artifacts["bootstrap_deltas"]["signal"], [.025, .975])
    assert (metric["ci_low"], metric["ci_high"]) == pytest.approx((low, high))
    assert metric["multiplicity_adjusted"] is False


def test_cv_identical_models_have_zero_delta_and_are_deterministic(cv_design):
    baseline, _, y, groups = cv_design
    design = (baseline, {"Baseline": baseline, "same": baseline.copy()}, y, groups)
    outputs = []
    for _ in range(2):
        artifacts = {}
        outputs.append((agreement.run_cv_evaluation(*design, n_splits=3, n_repeats=2, n_bootstrap=24, artifacts=artifacts), artifacts))
    assert outputs[0] == outputs[1]
    result = outputs[0][0]["same"]
    assert result["delta"] == result["ci_low"] == result["ci_high"] == 0
    assert result["passed"] is False


def test_cv_single_class_training_fold_uses_constant_prediction():
    baseline = np.arange(4, dtype=float).reshape(-1, 1)
    artifacts = {}
    agreement.run_cv_evaluation(baseline, {"Baseline": baseline, "same": baseline},
                                np.array([0, 0, 1, 1]), np.array(["a", "a", "b", "b"]),
                                n_splits=2, n_repeats=2, n_bootstrap=10, artifacts=artifacts)
    assert artifacts["constant_training_folds"] == 4
    assert set(np.asarray(artifacts["oof_predictions"]["Baseline"]).ravel()) == {0., 1.}


@pytest.mark.parametrize("change", ["single_class", "two_dimensional", "few_groups", "nan_features", "wrong_baseline", "zero_repeats", "zero_bootstrap"])
def test_cv_rejects_invalid_design(cv_design, change):
    baseline, models, y, groups = cv_design
    settings = {"n_splits": 3, "n_repeats": 2, "n_bootstrap": 10}
    if change == "single_class":
        y = np.ones_like(y)
    elif change == "two_dimensional":
        y = y[:, None]
    elif change == "few_groups":
        groups = np.repeat("a", len(y))
    elif change == "nan_features":
        models["signal"][0, 0] = np.nan
    elif change == "wrong_baseline":
        models["Baseline"] = baseline + 1
    elif change == "zero_repeats":
        settings["n_repeats"] = 0
    elif change == "zero_bootstrap":
        settings["n_bootstrap"] = 0
    with pytest.raises(ValueError):
        agreement.run_cv_evaluation(baseline, models, y, groups, **settings)


@pytest.mark.parametrize("y,groups,predictions,count", [
    ([0, 0], ["a", "b"], [[0, 0]], 10),
    ([0, 1], ["a", "a"], [[0, 1]], 10),
    ([0, 1], ["a"], [[0, 1]], 10),
    ([0, 1], ["a", "b"], [[0, float("nan")]], 10),
    ([0, 1], ["a", "b"], [[0, 1]], 0),
])
def test_bootstrap_rejects_invalid_inputs(y, groups, predictions, count):
    with pytest.raises(ValueError):
        agreement.paired_oof_bootstrap({"Baseline": predictions}, y, groups, n_bootstrap=count)


def test_precision_zero_agreements_is_none_and_g24_denominator_is_seventeen():
    precision, wrong = agreement.evaluate_precision_and_failures()
    g24_pair = precision["g24"]["agree(PAL-v2,COT)"]
    assert (g24_pair["n_corr"], g24_pair["n_agreed"], g24_pair["p_corr"]) == (0, 0, None)
    g24_plurality = precision["g24"]["plurality_agree>=2"]
    assert (g24_plurality["n_corr"], g24_plurality["n_agreed"]) == (16, 17)
    assert g24_plurality["p_corr"] == pytest.approx(16 / 17)
    assert any(row["id"] == "order_0010_en_orig" and row["accepted"] == "alice" and row["gold"] == "grace" for row in wrong)


@pytest.mark.parametrize("error", ["duplicate_id", "duplicate_arm", "duplicate_pal", "missing_arm", "wrong_gold", "bad_tokens"])
def test_load_dataset_rejects_corrupt_join(tmp_path, monkeypatch, error):
    item = {"id": "a", "group_id": "ga", "family": "order", "level": 1, "answer": "Bob"}
    common = {"id": "a", "group_id": "ga", "family": "order", "level": 1,
              "gold": "Bob", "prompt_tokens": 3, "completion_tokens": 4}
    rows = [{**common, "arm": arm} for arm in ("COT", "TOT", "SC")]
    pals = [{**common, "arm": "PAL-v2"}]
    items = [item]
    if error == "duplicate_id":
        items.append(item)
    elif error == "duplicate_arm":
        rows.append(rows[0])
    elif error == "duplicate_pal":
        pals.append(pals[0])
    elif error == "missing_arm":
        rows.pop()
    elif error == "wrong_gold":
        rows[0]["gold"] = "Carol"
    elif error == "bad_tokens":
        rows[0]["prompt_tokens"] = -1
    for name, value, jsonl in (("RUN11_TRACE", rows, True), ("PALV2_TRACE", pals, True), ("TUNE_PATH", {"items": items}, False)):
        path = tmp_path / name
        path.write_text("".join(json.dumps(row) + "\n" for row in value) if jsonl else json.dumps(value))
        monkeypatch.setattr(agreement, name, path)
    with pytest.raises(ValueError):
        agreement.load_dataset()


def test_writer_refuses_existing_directory_before_analysis(tmp_path, monkeypatch):
    sentinel = tmp_path / "keep.txt"
    sentinel.write_text("original")
    def forbidden():
        pytest.fail("must reject existing output before reading/analysing")
    monkeypatch.setattr(agreement, "load_dataset", forbidden)
    with pytest.raises(ValueError, match="new output"):
        agreement.write_analysis(tmp_path)
    assert sentinel.read_text() == "original"


def test_writer_rejects_unpinned_input_before_creating_output(tmp_path, monkeypatch):
    wrong_input = tmp_path / "wrong.json"
    wrong_input.write_text("{}")
    monkeypatch.setattr(agreement, "PINNED_INPUTS", {wrong_input: "0" * 64})
    output = tmp_path / "new"
    with pytest.raises(ValueError, match="hash mismatch"):
        agreement.write_analysis(output)
    assert not output.exists()


def test_legacy_script_requires_new_explicit_output():
    with pytest.raises(SystemExit) as error:
        agreement.main([])
    assert error.value.code == 2


@pytest.mark.parametrize("override", ["--model", "--dataset", "--seed", "--lam", "--order-pilot-thinking-tokens"])
def test_supported_cli_rejects_collection_overrides(tmp_path, override):
    from experiments.research_study import main
    value = "1" if override in {"--seed", "--lam", "--order-pilot-thinking-tokens"} else "unused"
    with pytest.raises(SystemExit) as error:
        main(["--agreement-analysis", "--output", str(tmp_path / "unused"), override, value])
    assert error.value.code == 2
    assert not (tmp_path / "unused").exists()


def test_supported_cli_is_offline_and_forwards_only_new_output(tmp_path, monkeypatch):
    from experiments.research_study import main
    output = tmp_path / "new"
    called = []
    monkeypatch.setattr(agreement, "write_analysis", lambda path: called.append(path))
    before = {name for name in sys.modules if name.startswith("mlx")}
    main(["--agreement-analysis", "--output", str(output)])
    assert called == [output]
    assert before == {name for name in sys.modules if name.startswith("mlx")}


def test_complete_writer_retains_history_and_saves_recomputable_results(tmp_path):
    historical = [agreement.ROOT / "prereg/decision_rule_agree.md",
                  *agreement.AUDIT_DIR.glob("AJ_*.txt")]
    before_hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in historical}
    before_mlx = {name for name in sys.modules if name.startswith("mlx")}
    output = tmp_path / "reanalysis"
    summary = agreement.write_analysis(output)
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["status"] == "complete"
    assert manifest["new_model_calls"] == 0
    assert manifest["confirmatory"] is False
    assert manifest["preregistration_pass"] is False
    assert manifest["publication_review_required"] is True
    assert manifest["n_items"] == manifest["n_groups"] == 100
    assert summary["preregistration_pass"] is False
    for name, expected in manifest["artifacts_sha256"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == expected
    for name, expected in manifest["source_sha256"].items():
        assert hashlib.sha256((agreement.ROOT / name).read_bytes()).hexdigest() == expected
    assert {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in historical} == before_hashes
    assert {name for name in sys.modules if name.startswith("mlx")} == before_mlx
    cv = json.loads((output / "cv.json").read_text())
    for family in ("order", "pooled"):
        assert len(cv[family]["fold_assignments"]) == 20
        for name, predictions in cv[family]["oof_predictions"].items():
            scores = [roc_auc_score(cv[family]["target"], row) for row in predictions]
            metric = summary["gate"][family]["models"][name]
            assert np.mean(scores) == pytest.approx(metric["mean_auroc"])
            if name != "Baseline":
                assert len(cv[family]["bootstrap_deltas"][name]) == 2000
                bounds = np.quantile(cv[family]["bootstrap_deltas"][name], [.025, .975])
                assert (metric["ci_low"], metric["ci_high"]) == pytest.approx(bounds)
    replay = summary["replay"]["order"]
    assert replay["W"]["corr"] == 23
    assert replay["G1"]["corr"] == replay["G2"]["corr"] == 22
    assert replay["W"]["mean_tok"] == pytest.approx(915.9677419354839)
    assert replay["G1"]["mean_tok"] > replay["W"]["mean_tok"]
    assert summary["gate"]["arith"]["models"]["Baseline"]["mean_auroc"] is None
    report = (output / "report.md").read_text()
    assert "0/0 | N/A (no agreements)" in report
    assert "16/17 | 94.1%" in report
    assert "LEGACY token proxy" in report
    assert "NOT causal diagnosis" in report
    assert "PASS" not in report
