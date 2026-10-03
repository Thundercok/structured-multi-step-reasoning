import copy
import io
import json

import numpy as np
import pytest

from experiments.research_study import (
    check_answer,
    collect_records,
    evaluate_records,
    fit_policies,
    main,
    paired_interval,
    smoke_dataset,
    validate_dataset,
)
from pipeline import MockDemoBackend


def collected_fixture():
    dataset = smoke_dataset()
    backend = MockDemoBackend()

    def set_seed(seed):
        backend.rng = np.random.default_rng(seed)

    records = collect_records(backend, dataset["items"], 42, set_seed, io.StringIO())
    return dataset, records


def test_rejects_cross_split_groups_and_duplicate_queries():
    dataset = smoke_dataset()
    validate_dataset(dataset)
    dataset["items"][-1]["group_id"] = dataset["items"][0]["group_id"]
    with pytest.raises(ValueError, match="crosses"):
        validate_dataset(dataset)
    dataset = smoke_dataset()
    dataset["items"][-1]["query"] = "  " + dataset["items"][0]["query"].upper()
    with pytest.raises(ValueError, match="Duplicate"):
        validate_dataset(dataset)


def test_answer_checker_rejects_substrings_negation_and_trailing_wrong_numbers():
    numeric = {"answer_type": "number", "answer": "7.44", "tolerance": 0.005}
    assert check_answer("7.440", numeric)
    assert not check_answer("3.14, but an earlier estimate was 7.44", numeric)
    assert not check_answer("NaN", numeric)
    assert not check_answer("7.46", numeric)
    text = {"answer_type": "text", "answer": "yes"}
    assert check_answer(" YES ", text)
    assert not check_answer("not yes", text)
    # Procedural families (arith, order, g24)
    arith_item = {"family": "arith", "answer": "52"}
    assert check_answer("52.0", arith_item)
    assert not check_answer("51", arith_item)
    order_item = {"family": "order", "answer": "Heidi"}
    assert check_answer("Heidi finished in 4th place", order_item)
    assert not check_answer("Bob", order_item)
    g24_item = {"family": "g24", "answer": "((10+(13+3))-2)", "meta": {"numbers": [10, 13, 2, 3]}}
    assert check_answer("10 + 13 + 3 - 2 = 24", g24_item)
    assert not check_answer("10 + 13 + 2 + 3", g24_item)


def test_generation_is_order_independent_and_test_labels_do_not_fit_policy():
    dataset, records = collected_fixture()
    backend = MockDemoBackend()

    def set_seed(seed):
        backend.rng = np.random.default_rng(seed)

    repeated = collect_records(backend, list(reversed(dataset["items"])), 42, set_seed, io.StringIO())
    for original, replayed in zip(records, repeated):
        assert original["embedding"] == replayed["embedding"]
        for strategy in original["attempts"]:
            for field in ("answer", "confidence", "tokens"):
                assert original["attempts"][strategy][field] == replayed["attempts"][strategy][field]
    poisoned = copy.deepcopy(records)
    for record in poisoned:
        if record["split"] == "test":
            for attempt in record["attempts"].values():
                attempt["correct"] = not attempt["correct"]
    original_policies = fit_policies(records, 0.02)
    poisoned_policies = fit_policies(poisoned, 0.02)
    assert original_policies[0].tau == poisoned_policies[0].tau
    before = evaluate_records(records, *original_policies)
    after = evaluate_records(poisoned, *poisoned_policies)
    assert [row["path"] for row in before] == [row["path"] for row in after]
    assert all(left["correct"] != right["correct"] for left, right in zip(before, after))


def test_all_methods_share_attempts_and_charge_every_executed_strategy():
    _, records = collected_fixture()
    policies = fit_policies(records, 0.02)
    results = evaluate_records(records, *policies)
    by_id = {record["id"]: record for record in records}
    for row in results:
        record = by_id[row["id"]]
        assert record["split"] == "test"
        assert row["tokens"] == sum(record["attempts"][strategy]["tokens"] for strategy in row["path"])
        assert row["answer"] == record["attempts"][row["path"][-1]]["answer"]


def test_paired_intervals_use_groups_and_validate_pairing():
    rows = [
        {"id": str(index), "group_id": "same", "method": method, "tokens": tokens}
        for index in range(4)
        for method, tokens in (("full_policy", 30), ("fixed_cot", 50))
    ]
    result = paired_interval(rows, "fixed_cot", "tokens", 42)
    assert result == {"mean_difference": -20, "ci95": None, "groups": 1}
    with pytest.raises(ValueError, match="identical"):
        paired_interval(rows[:-1], "fixed_cot", "tokens", 42)


def test_smoke_artifacts_replay_and_tamper_detection(tmp_path):
    original = tmp_path / "original"
    replay = tmp_path / "replay"
    main(["--backend", "smoke", "--output", str(original)])
    manifest = json.loads((original / "manifest.json").read_text())
    assert manifest["status"] == "complete"
    assert manifest["evidence"] == "synthetic_smoke"
    assert len(json.loads((original / "summary.json").read_text())["methods"]) == 9
    main(["--replay", str(original), "--output", str(replay)])
    assert (original / "results.json").read_bytes() == (replay / "results.json").read_bytes()
    assert (original / "summary.json").read_bytes() == (replay / "summary.json").read_bytes()
    with pytest.raises(FileExistsError):
        main(["--backend", "smoke", "--output", str(original)])
    (original / "records.json").write_text("[]")
    with pytest.raises(SystemExit):
        main(["--replay", str(original), "--output", str(tmp_path / "tampered")])


def test_failed_generation_keeps_failed_manifest(tmp_path, monkeypatch):
    def broken_run(*args):
        raise RuntimeError("backend unavailable")

    monkeypatch.setattr(MockDemoBackend, "run", broken_run)
    output = tmp_path / "failed"
    with pytest.raises(RuntimeError, match="backend unavailable"):
        main(["--backend", "smoke", "--output", str(output)])
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["status"] == "failed"
    assert not (output / "summary.json").exists()


def test_measured_mode_requires_reviewable_inputs_and_replay_rejects_overrides(tmp_path):
    with pytest.raises(SystemExit):
        main(["--backend", "mlx", "--output", str(tmp_path / "missing-inputs")])
    with pytest.raises(SystemExit):
        main(["--replay", str(tmp_path / "source"), "--lam", "0.5", "--output", str(tmp_path / "changed")])
    assert not (tmp_path / "missing-inputs").exists()
    assert not (tmp_path / "changed").exists()


def test_retired_simulator_cannot_overwrite_research_report():
    from experiments.benchmark_reasoning import run_benchmark

    with pytest.raises(RuntimeError, match="retired"):
        run_benchmark()
