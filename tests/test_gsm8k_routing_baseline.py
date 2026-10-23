"""Research software fixtures only; these are not RAT live-UI conversations."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from experiments import gsm8k_routing_baseline as routing
from experiments.research_study import ROOT, main, seed_for, source_hashes


def fixture_data():
    items, records = [], []
    for split in ("train", "calibration"):
        for index, words in enumerate((10, 12, 60, 62)):
            ident = f"authored-{split}-{index}"
            query = " ".join([ident] + ["word"] * (words - 1))
            item = {"id": ident, "group_id": ident, "split": split, "query": query,
                    "answer": "7", "answer_type": "number", "category": "authored"}
            items.append(item)
            for action in routing.ACTIONS:
                correct = action == "PAL" or (action == "DIRECT" if words <= 20 else action == "COT")
                answer = "7" if correct else "8"
                tokens = {"DIRECT": 10, "COT": 100, "PAL": 300}[action]
                generation = {"output": f"Answer: {answer}", "tokens": tokens, "prompt_tokens": 5,
                              "max_tokens": 1024, "temperature": 0.0, "enable_thinking": False,
                              "finish_reason": "stop", "messages": [{"role": "user", "content": query}]}
                tools = [{"name": "python", "ok": True, "output": answer, "duration_ms": 0.25}] if action == "PAL" else []
                if action == "PAL":
                    generation["output"] = f"result = {answer}"  # Execution, not a parsed rationale.
                records.append({"id": ident, "group_id": ident, "split": split, "strategy": action,
                                "token_budget": 1024, "seed": seed_for(42, ident, action),
                                "answer_format": {"answer_type": "number", "decimal_separator": "."},
                                "answer": answer, "correct": correct, "tokens": tokens, "strategy_ms": 1.0,
                                "trace": {"parse_status": "marker", "generations": [generation], "tools": tools}})
    return items, records


def save_run(path, items=None, records=None):
    default_items, default_records = fixture_data()
    items = default_items if items is None else items
    records = default_records if records is None else records
    path.mkdir()
    dataset = {"name": "authored-numeric-routing-software-fixture", "version": "1", "role": "development_tuning",
               "source": "Project-authored fixtures; no GSM8K candidate questions", "license": "Project test data", "items": items}
    values = {"dataset.json": dataset, "records.json": records, "selection.json": {"synthetic_fixture": True},
              "summary.json": {"synthetic_fixture": True}}
    for name, value in values.items():
        (path / name).write_text(json.dumps(value, indent=2) + "\n")
    (path / "report.md").write_text("Synthetic research software fixtures, not model or live UI results.\n")
    manifest = {"status": "complete", "pilot": True, "backend": "smoke", "evidence": "synthetic_pilot_smoke",
                "seed": 42, "prompt_profile": "english-math-v1", "strategies": list(routing.ACTIONS),
                "token_budgets": [1024], "source_sha256": source_hashes(),
                "artifact_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in path.iterdir()}}
    (path / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return path


def test_rule_menu_boundary_and_exact_tie_order():
    rules = routing.candidate_rules()
    assert len(rules) == len({r.id for r in rules}) == 27
    rule = next(r for r in rules if r.id == "words_le_020_DIRECT_else_COT")
    assert rule.choose(" \t".join(["x"] * 20)) == "DIRECT"
    assert rule.choose(" ".join(["x"] * 21)) == "COT"
    items, records = fixture_data()
    selected = routing.fit_selection(items, records)
    assert selected["selected_rule"]["id"] == rule.id
    assert selected["fixed_reference"]["id"] == "constant_PAL"
    # Identical outcomes/costs: constant before conditional, then lexical ID.
    for row in records:
        row["correct"], row["answer"], row["tokens"] = True, "7", 10
        row["trace"]["generations"][0].update(output="Answer: 7", tokens=10)
        if row["strategy"] == "PAL":
            row["trace"]["tools"][0]["output"] = "7"
    tied = routing.fit_selection(items, records)
    assert tied["selected_rule"]["id"] == tied["fixed_reference"]["id"] == "constant_COT"
    assert tied["collapsed_to_constant"] is True


def test_fitting_cannot_read_validation_outcomes_and_is_order_independent():
    items, records = fixture_data()
    expected = routing.fit_selection(items, records)

    class BlindValidation(dict):
        def __getitem__(self, key):
            if key != "id":
                raise AssertionError(f"Fitter read validation {key}")
            return super().__getitem__(key)

    blinded = [BlindValidation(r) if r["split"] == "calibration" else r for r in records]
    assert routing.fit_selection(items, blinded) == expected
    assert routing.fit_selection(list(reversed(items)), list(reversed(records))) == expected
    poisoned = copy.deepcopy(records)
    for row in poisoned:
        if row["split"] == "calibration":
            row.update(correct=not row["correct"], answer="unavailable", tokens=-999, strategy_ms=float("nan"))
    assert routing.fit_selection(items, poisoned) == expected


def test_validation_changes_results_without_changing_fitted_reference():
    items, records = fixture_data()
    selection = routing.fit_selection(items, records)
    validation = [i for i in items if i["split"] == "calibration"]
    val_rows = [r for r in records if r["split"] == "calibration"]
    original, _ = routing.evaluate_selection(selection, validation, val_rows)
    poisoned = copy.deepcopy(val_rows)
    for row in poisoned:
        if row["strategy"] == "PAL":
            continue  # Keep the fitting-selected reference unchanged.
        row["correct"] = not row["correct"]
        row["answer"] = "7" if row["correct"] else "8"
        row["trace"]["generations"][0]["output"] = f"Answer: {row['answer']}"
        if row["strategy"] == "PAL":
            row["trace"]["tools"][0]["output"] = row["answer"]
    changed, _ = routing.evaluate_selection(selection, validation, poisoned)
    assert selection["fixed_reference"]["id"] == "constant_PAL"
    assert original["primary_comparison"]["metrics"]["utility"]["mean_difference"] > 0
    assert changed["primary_comparison"]["metrics"]["utility"]["mean_difference"] < 0
    assert original["collection"]["generation_calls"] == 12
    assert original["methods"]["query_only_rule"]["generation_calls"] == 4


@pytest.mark.parametrize("defect", ["duplicate", "missing", "negative", "bool_tokens", "over_cap", "prompt", "score", "answer", "pal_tool", "seed"])
def test_bad_fitting_records_are_rejected(defect):
    items, records = fixture_data()
    if defect == "duplicate": records.append(copy.deepcopy(records[0]))
    elif defect == "missing": records.pop(0)
    elif defect == "negative": records[0]["tokens"] = -1
    elif defect == "bool_tokens": records[0]["tokens"] = True
    elif defect == "over_cap": records[0]["tokens"] = 2048
    elif defect == "prompt": records[0]["trace"]["generations"][0]["prompt_tokens"] = -1
    elif defect == "score": records[0]["correct"] = not records[0]["correct"]
    elif defect == "answer": records[0]["answer"] = "99"
    elif defect == "pal_tool": records[2]["trace"]["tools"] = []
    elif defect == "seed": records[0]["seed"] += 1
    with pytest.raises(ValueError):
        routing.fit_selection(items, records)


def test_group_roles_and_held_out_are_rejected():
    items, records = fixture_data()
    items[-1]["group_id"] = items[0]["group_id"]
    with pytest.raises(ValueError, match="crosses"):
        routing.fit_selection(items, records)
    items, records = fixture_data()
    items[-1]["split"] = "test"
    with pytest.raises(ValueError, match="test is forbidden"):
        routing.fit_selection(items, records)


def test_bootstrap_counts_groups_and_keeps_variant_weights():
    ours, baseline = [], []
    for index, (group, correct) in enumerate([("a", False), ("b", True), ("b", True), ("b", True)]):
        ours.append({"id": str(index), "group_id": group, "correct": correct, "tokens": 10})
        baseline.append({"id": str(index), "group_id": group, "correct": not correct, "tokens": 10})
    result = routing.paired_comparison(ours, baseline)
    assert result["groups"] == 2 and result["items"] == 4
    assert result["metrics"]["accuracy"] == {"mean_difference": .5, "ci95": [-1, 1]}
    assert result["rescues"] == 3 and result["harms"] == 1
    single = routing.paired_comparison(ours[1:], baseline[1:])
    assert single["groups"] == 1 and single["metrics"]["accuracy"]["ci95"] is None


def test_selection_survives_validation_failure_and_precedes_scoring(tmp_path, monkeypatch):
    items, records = fixture_data()
    records[-1]["correct"] = not records[-1]["correct"]  # Semantic failure after hashes pass.
    run = save_run(tmp_path / "run", items, records)
    output = tmp_path / "failed"
    original = routing.evaluate_selection

    def checked(*args):
        assert (output / "selection.json").is_file()
        assert json.loads((output / "manifest.json").read_text())["status"] == "selection_saved"
        return original(*args)

    monkeypatch.setattr(routing, "evaluate_selection", checked)
    with pytest.raises(ValueError, match="Correctness differs"):
        routing.write_analysis(run, output)
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["status"] == "failed"
    assert routing.sha256_file(output / "selection.json") == manifest["selection_sha256"]
    assert not (output / "summary.json").exists()


def test_supported_entrypoint_costs_artifacts_and_repeat(tmp_path):
    run = save_run(tmp_path / "run")
    for name in ("first", "repeat"):
        main(["--gsm8k-routing-analysis", str(run), "--output", str(tmp_path / name)])
    first = tmp_path / "first"
    for name in ("selection.json", "summary.json", "results.json", "report.md", "manifest.json"):
        assert (first / name).read_bytes() == (tmp_path / "repeat" / name).read_bytes()
    manifest = json.loads((first / "manifest.json").read_text())
    summary = json.loads((first / "summary.json").read_text())
    assert manifest["evidence"] == "synthetic_routing_software_check" and manifest["new_model_calls"] == 0
    for name, value in manifest["artifact_sha256"].items():
        assert routing.sha256_file(first / name) == value
    assert summary["full_collection"]["generation_calls"] == 24
    assert summary["collection"]["generation_calls"] == 12
    assert summary["methods"]["query_only_rule"]["generated_tokens"] == 220
    with pytest.raises(FileExistsError):
        routing.write_analysis(run, first)


@pytest.mark.parametrize("overrides", [["--lam", "0.2"], ["--seed", "1"], ["--model", "anything"], ["--pilot"], ["--max-tokens", "99"]])
def test_collection_overrides_rejected_before_input_read(tmp_path, overrides):
    with pytest.raises(SystemExit):
        main(["--gsm8k-routing-analysis", str(tmp_path / "does-not-exist"), "--output", str(tmp_path / "output"), *overrides])
    assert not (tmp_path / "output").exists()


def test_fresh_process_entrypoint_never_imports_model_or_qt(tmp_path):
    run = save_run(tmp_path / "run")
    code = """
import builtins, runpy, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'mlx','mlx_lm','torch','sentence_transformers','PyQt6','PySide6'}:
        raise AssertionError('Forbidden import: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
sys.argv = ['experiments.research_study', '--gsm8k-routing-analysis', sys.argv[1], '--output', sys.argv[2]]
runpy.run_module('experiments.research_study', run_name='__main__')
"""
    completed = subprocess.run([sys.executable, "-c", code, str(run), str(tmp_path / "analysis")], cwd=ROOT, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_tampered_input_rejected_before_selection(tmp_path):
    run = save_run(tmp_path / "run")
    with (run / "records.json").open("a") as stream:
        stream.write(" ")
    with pytest.raises(ValueError, match="artifact changed"):
        routing.write_analysis(run, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_real_evidence_cannot_silently_use_small_legacy_frame(tmp_path):
    run = save_run(tmp_path / "run")
    manifest = json.loads((run / "manifest.json").read_text())
    manifest.update(backend="mlx", evidence="measured_development_pilot", model_revision_verified=True,
                    model_repository="mlx-community/Qwen3-8B-4bit", model_revision="545dc4251c05440727734bcd94334791f6ab0192")
    (run / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="48/48"):
        routing.write_analysis(run, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_validation_rejects_fitting_group_and_altered_rule():
    items, records = fixture_data()
    selection = routing.fit_selection(items, records)
    val_items = copy.deepcopy([i for i in items if i["split"] == "calibration"])
    val_rows = [r for r in records if r["split"] == "calibration"]
    val_items[0]["group_id"] = items[0]["group_id"]
    with pytest.raises(ValueError, match="Fitting group leaked"):
        routing.evaluate_selection(selection, val_items, val_rows)
    val_items[0]["group_id"] = val_rows[0]["group_id"]
    selection["selected_rule"]["cutoff"] = 21
    with pytest.raises(ValueError, match="altered selected rule"):
        routing.evaluate_selection(selection, val_items, val_rows)
