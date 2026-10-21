"""Replicate seed identity without drift or real inference."""

import copy
import json

import pytest

from experiments.cot_restart_matched import prepare_plan, read_plan, run_plan
from experiments.cot_restart_pilot import MockLLM, atomic_save_json, encoded_json, text_sha256
from experiments.cot_restart_replay import derive_cap_sweep_seed
from scripts.prepare_cot_restart_replication import (
    build_replication_plan, prepare_replication, validate_replication_plan,
)


def parent_plan(tmp_path):
    return prepare_plan(tmp_path / "parent", tokenizer=MockLLM.MockTokenizer())


def rehash(plan):
    plan["plan_sha256"] = text_sha256(encoded_json({k: v for k, v in plan.items() if k != "plan_sha256"}))


def test_new_draw_preserves_frozen_fields_and_uses_budget_independent_seeds(tmp_path):
    parent = parent_plan(tmp_path)
    replica = build_replication_plan(parent)
    validate_replication_plan(parent, replica)
    assert replica["limits"] == parent["limits"]
    assert replica["source_sha256"] == parent["source_sha256"]
    assert replica["plan_sha256"] != parent["plan_sha256"]
    for old, new in zip(parent["requests"], replica["requests"]):
        assert new["seed"] == derive_cap_sweep_seed(42, new["question_id"], new["arm"], 1)
        assert {k: v for k, v in new.items() if k not in ("seed", "call_index")} == {
            k: v for k, v in old.items() if k != "seed"}
    assert len({r["seed"] for r in parent["requests"] + replica["requests"]}) == 72


@pytest.mark.parametrize("index", [0, -1, True, 1.5])
def test_repeated_or_invalid_draw_identity_is_rejected(tmp_path, index):
    with pytest.raises(ValueError, match="new increasing integer"):
        build_replication_plan(parent_plan(tmp_path), draw_index=index)


@pytest.mark.parametrize("field,value", [("completion_cap", 99999), ("prompt", "drift")])
def test_recomputed_checksum_cannot_hide_non_seed_drift(tmp_path, field, value):
    parent = parent_plan(tmp_path)
    replica = build_replication_plan(parent)
    replica["requests"][0][field] = value
    rehash(replica)
    with pytest.raises(ValueError, match="frozen fields"):
        validate_replication_plan(parent, replica)


def test_parent_seed_and_checksum_must_match_namespace(tmp_path):
    parent = parent_plan(tmp_path)
    bad = copy.deepcopy(parent)
    bad["requests"][0]["seed"] += 1
    with pytest.raises(ValueError, match="checksum"):
        build_replication_plan(bad)
    rehash(bad)
    with pytest.raises(ValueError, match="seed does not match"):
        build_replication_plan(bad)


def test_existing_runner_accepts_replica_and_resumes_without_extra_draws(tmp_path):
    parent = parent_plan(tmp_path)
    replica = build_replication_plan(parent)
    prepared, output = tmp_path / "replica", tmp_path / "mock"
    prepared.mkdir()
    atomic_save_json(prepared / "plan.json", replica)
    assert read_plan(prepared)["plan_sha256"] == replica["plan_sha256"]
    result = run_plan(prepared, output, mock=True)
    records = json.loads((output / "records.json").read_text())
    assert result["status"] == "complete" and result["executed_model_calls"] == 36
    assert {r["call_index"] for r in records} == {1}
    assert {(r["question_id"], r["arm"], r["seed"]) for r in records} == {
        (r["question_id"], r["arm"], r["seed"]) for r in replica["requests"]}
    resumed = run_plan(prepared, output, mock=True)
    assert resumed["journal_head"] == result["journal_head"]
    assert resumed["executed_model_calls"] == 36
    with pytest.raises(ValueError, match="explicit approval"):
        run_plan(prepared, tmp_path / "forbidden")
    assert not (tmp_path / "forbidden").exists()


def test_synthetic_parent_cannot_prepare_real_replication(tmp_path):
    parent_plan(tmp_path)
    with pytest.raises(ValueError, match="real parent plan"):
        prepare_replication(tmp_path / "parent", tmp_path / "missing_run", tmp_path / "forbidden")
    assert not (tmp_path / "forbidden").exists()
