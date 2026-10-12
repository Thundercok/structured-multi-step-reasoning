import copy
import hashlib
import json

import pytest

from experiments import research_pilot as pilot
from experiments import research_study as study
from experiments.research_aggregate import load_run


def read(directory, name):
    return json.loads((directory / name).read_text())


def test_pilot_is_development_only_never_fits_policy_and_replays_exactly(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("A development pilot must never fit or evaluate a controller")
    monkeypatch.setattr(study, "fit_policies", forbidden)
    monkeypatch.setattr(study, "evaluate_records", forbidden)
    original, replay = tmp_path / "original", tmp_path / "replay"
    study.main(["--backend", "smoke", "--pilot", "--output", str(original)])
    manifest = read(original, "manifest.json")
    assert manifest["status"] == "complete"
    assert manifest["evidence"] == "synthetic_pilot_smoke"
    assert manifest["policy_fitted"] is False
    assert not (original / "policy.json").exists()
    assert not (original / "results.json").exists()
    records = read(original, "records.json")
    items = read(original, "dataset.json")["items"]
    assert {row["split"] for row in records} == {"train", "calibration"}
    assert {(row["id"], row["strategy"], row["token_budget"]) for row in records} == {
        (item["id"], strategy, budget) for item in items
        for strategy in ("DIRECT", "COT") for budget in (96, 1024)
    }
    for name, digest in manifest["artifact_sha256"].items():
        assert hashlib.sha256((original / name).read_bytes()).hexdigest() == digest
    monkeypatch.setattr(pilot.PilotSmokeBackend, "run", forbidden)
    study.main(["--replay", str(original), "--output", str(replay)])
    for name in ("dataset.json", "records.json", "selection.json", "summary.json", "report.md"):
        assert (original / name).read_bytes() == (replay / name).read_bytes()
    assert not (replay / "attempts.jsonl").exists()
    with pytest.raises(ValueError, match="pilot diagnostics"):
        load_run(original)
    with pytest.raises(FileExistsError):
        study.main(["--backend", "smoke", "--pilot", "--output", str(original)])


def test_group_sampling_is_label_and_order_independent_and_preserves_variants():
    dataset = pilot.synthetic_dataset()
    alternatives = copy.deepcopy(dataset["items"])
    for item in alternatives:
        item["id"] += "_alternative"
        item["group_id"] += "_alternative"
        item["query"] += "_alternative"
    dataset["items"].extend(alternatives)
    selected, selection = pilot.select_groups(dataset, 42, 1)
    poisoned = copy.deepcopy(dataset)
    poisoned["items"].reverse()
    for item in poisoned["items"]:
        item["answer"] = "poisoned"
    repeated, second = pilot.select_groups(poisoned, 42, 1)
    assert selection == second
    assert [item["id"] for item in selected["items"]] == [item["id"] for item in repeated["items"]]
    groups = set(selection["selected_group_ids"])
    assert {item["id"] for item in selected["items"]} == {item["id"] for item in dataset["items"] if item["group_id"] in groups}
    assert all(sum(item["group_id"] == group for item in selected["items"]) == 2 for group in groups)
    assert len(selection["strata"]) == 24
    assert len(selected["items"]) * 2 == len(dataset["items"])


@pytest.mark.parametrize("dataset", [study.smoke_dataset(), {**study.smoke_dataset(), "role": "development_tuning"}])
def test_held_out_inputs_are_rejected_before_model_loading(tmp_path, dataset, capsys, monkeypatch):
    path = tmp_path / "input.json"
    study.write_json(path, dataset)
    def forbidden(*args):
        pytest.fail("Model validation/loading must not run for a held-out input")
    monkeypatch.setattr(pilot, "local_model_metadata", forbidden)
    with pytest.raises(SystemExit):
        study.main(["--backend", "mlx", "--pilot", "--dataset", str(path), "--model", "unused", "--output", str(tmp_path / "run")])
    error = capsys.readouterr().err
    assert "development tuning" in error or "held-out test split" in error
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize("options", [
    ["--token-budgets", "0"], ["--token-budgets", "96", "96"],
    ["--groups-per-stratum", "0"], ["--strategies", "DIRECT", "DIRECT"],
    ["--strategies", "STOP"], ["--lam", "0.02"],
    ["--max-tokens", "96", "--token-budgets", "1024"],
])
def test_invalid_pilot_conditions_create_no_run(tmp_path, options):
    output = tmp_path / "invalid"
    with pytest.raises(SystemExit):
        study.main(["--backend", "smoke", "--pilot", *options, "--output", str(output)])
    assert not output.exists()


def test_budget_and_subset_flags_cannot_change_held_out_study(tmp_path):
    with pytest.raises(SystemExit):
        study.main(["--backend", "smoke", "--strategies", "DIRECT", "--output", str(tmp_path / "bad")])
    assert not (tmp_path / "bad").exists()


def test_all_strategy_calls_are_counted_and_small_caps_reach_react(tmp_path):
    output = tmp_path / "all"
    study.main(["--backend", "smoke", "--pilot", "--strategies", *[action.name for action in pilot.PILOT_STRATEGIES], "--token-budgets", "48", "512", "--output", str(output)])
    records = read(output, "records.json")
    assert {row["strategy"] for row in records} == {action.name for action in pilot.PILOT_STRATEGIES}
    for row in records:
        generations = row["trace"]["generations"]
        assert row["tokens"] == sum(g["tokens"] for g in generations)
        assert all(g["tokens"] <= g["max_tokens"] <= row["token_budget"] for g in generations)
        if row["strategy"] == "REACT":
            assert generations[0]["max_tokens"] == min(200, row["token_budget"])
        if row["strategy"] == "SELF_CONSISTENCY":
            assert len(generations) == 5
    assert any(row["tokens"] > row["token_budget"] for row in records)


def test_partial_failure_preserves_flushed_attempts(tmp_path, monkeypatch):
    run = pilot.PilotSmokeBackend.run
    calls = 0
    def fail_third(self, *args):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError("interrupted fixture")
        return run(self, *args)
    monkeypatch.setattr(pilot.PilotSmokeBackend, "run", fail_third)
    output = tmp_path / "failed"
    with pytest.raises(RuntimeError, match="interrupted"):
        study.main(["--backend", "smoke", "--pilot", "--output", str(output)])
    assert read(output, "manifest.json")["status"] == "failed"
    assert len([json.loads(line) for line in (output / "attempts.jsonl").read_text().splitlines()]) == 2
    assert not (output / "summary.json").exists()
    with pytest.raises(SystemExit):
        study.main(["--replay", str(output), "--output", str(tmp_path / "failed-replay")])


def test_pilot_replay_rejects_tampering_and_overrides(tmp_path):
    output = tmp_path / "source"
    study.main(["--backend", "smoke", "--pilot", "--output", str(output)])
    with pytest.raises(SystemExit):
        study.main(["--replay", str(output), "--max-tokens", "32", "--output", str(tmp_path / "changed")])
    (output / "records.json").write_text("[]")
    with pytest.raises(SystemExit):
        study.main(["--replay", str(output), "--output", str(tmp_path / "tampered")])
    assert not (tmp_path / "tampered").exists()


def test_prompt_profile_is_frozen_in_pilot_and_replay_rejects_override(tmp_path):
    original, replay = tmp_path / "english", tmp_path / "replay"
    study.main(["--backend", "smoke", "--pilot", "--strategies", "DIRECT", "COT", "PAL",
                "--prompt-profile", "english-math-v1", "--max-tokens", "1024", "--output", str(original)])
    assert read(original, "manifest.json")["prompt_profile"] == "english-math-v1"
    study.main(["--replay", str(original), "--output", str(replay)])
    assert read(replay, "manifest.json")["prompt_profile"] == "english-math-v1"
    with pytest.raises(SystemExit):
        study.main(["--replay", str(original), "--prompt-profile", "legacy", "--output", str(tmp_path / "override")])
    with pytest.raises(SystemExit):
        study.main(["--backend", "smoke", "--prompt-profile", "english-math-v1", "--output", str(tmp_path / "heldout")])


def test_aligned_direct_cot_profile_is_frozen_and_rejects_other_strategies(tmp_path):
    output = tmp_path / "aligned"
    study.main([
        "--backend", "smoke", "--pilot", "--strategies", "DIRECT", "COT",
        "--prompt-profile", "aligned-direct-cot-v1", "--max-tokens", "512",
        "--output", str(output),
    ])
    manifest = read(output, "manifest.json")
    assert manifest["prompt_profile"] == "aligned-direct-cot-v1"
    assert manifest["strategies"] == ["DIRECT", "COT"]
    assert manifest["token_budgets"] == [512]

    invalid = tmp_path / "aligned-with-pal"
    with pytest.raises(SystemExit):
        study.main([
            "--backend", "smoke", "--pilot", "--strategies", "DIRECT", "COT", "PAL",
            "--prompt-profile", "aligned-direct-cot-v1", "--output", str(invalid),
        ])
    assert not invalid.exists()


def test_local_model_content_is_hashed_and_repository_ids_rejected(tmp_path):
    with pytest.raises(ValueError, match="local model directory"):
        pilot.local_model_metadata("mlx-community/missing-model")
    (tmp_path / "config.json").write_text('{"fixture": true}')
    (tmp_path / "model.safetensors").write_bytes(b"artificial weights, never loaded")
    model, hashes = pilot.local_model_metadata(str(tmp_path))
    assert model == str(tmp_path.resolve())
    assert hashes["model.safetensors"] == hashlib.sha256((tmp_path / "model.safetensors").read_bytes()).hexdigest()
