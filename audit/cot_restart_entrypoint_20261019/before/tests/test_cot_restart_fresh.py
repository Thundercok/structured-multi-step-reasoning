"""Fresh-base adapter acceptance using only authored synthetic fixtures."""

import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

import experiments.cot_restart_fresh as fresh
from experiments.cot_restart_pilot import MockLLM
from experiments.cot_restart_replay import replay_completion


def read_records(output):
    return json.loads((output / "records.json").read_text())


def test_frame_has_one_outcome_blind_representative_and_preserves_group_splits():
    dataset = fresh.synthetic_dataset()
    assert len(fresh.select_frame(dataset, "train")) == 3
    original = dataset["items"][1]
    variant = copy.deepcopy(original)
    variant["id"] = "aaa-first-order-variant"
    variant["meta"]["names"] = ["Cora", "Dara"]
    from scripts.gen_tasks import render_order
    variant["query"] = render_order(variant["meta"])
    variant["answer"] = "Cora"
    dataset["items"].append(variant)
    chosen = fresh.select_frame(dataset, "train")
    assert len(chosen) == 3 and variant["id"] in {r["id"] for r in chosen}
    variant["answer"] = "POISONED_GOLD"
    assert [r["id"] for r in fresh.select_frame(dataset, "train")] == [r["id"] for r in chosen]
    variant["split"] = "test"
    with pytest.raises(ValueError, match="crosses"):
        fresh.select_frame(dataset, "train")


def test_collects_original_base_and_all_arms_with_exact_tokens_and_costs(tmp_path):
    output = tmp_path / "mock"
    settings = fresh.MockSettings(64, 64, include_a=True)
    manifest = fresh.run_mock(fresh.synthetic_dataset(), output, settings)
    records = read_records(output)
    paths = json.loads((output / "paths.json").read_text())
    assert manifest["completed_mock_calls"] == manifest["attempted_mock_calls"] == 12
    assert manifest["real_model_calls"] == 0 and not manifest["confirmatory"]
    assert len(records) == len(paths) == 12 and manifest["original_groups"] == 3
    assert manifest["total_synthetic_collection_tokens"] == sum(r["total_tokens"] for r in records)
    by_key = {(r["question_id"], r["arm"]): r for r in records}
    assert len({r["seed"] for r in records}) == 12
    tokenizer = MockLLM.MockTokenizer()
    for record in records:
        assert record["completion_tokens"] == len(record["completion_token_ids"])
        assert record["prompt_tokens"] == len(record["prompt_token_ids"])
        replay = replay_completion(record, tokenizer, record["completion_cap"], prefix_text=record["prefix_text"])
        assert replay["full_response"] == record["full_response"]
        assert record["finish_reason"] == "stop" and record["includes_eos"]
        assert "Answer:" not in record["prefix_text"]
        assert record["temperature"] == (0 if record["arm"] == "O" else .6)
    for path in paths:
        calls = [by_key[path["question_id"], arm] for arm in path["path_call_arms"]]
        assert path["path_call_arms"] == (["O"] if path["arm"] == "O" else ["O", path["arm"]])
        assert path["path_total_tokens"] == sum(r["total_tokens"] for r in calls)
        assert path["path_prompt_tokens"] + path["path_completion_tokens_including_eos"] == path["path_total_tokens"]


def test_gold_does_not_change_generation_and_cap_does_not_change_seed(tmp_path):
    dataset = fresh.synthetic_dataset()
    fresh.run_mock(dataset, tmp_path / "original", fresh.MockSettings(64, 64))
    poisoned = copy.deepcopy(dataset)
    for item in poisoned["items"]:
        item["answer"] = "999" if item["family"] == "arith" else "POISONED_GOLD"
    fresh.run_mock(poisoned, tmp_path / "poisoned", fresh.MockSettings(64, 64))
    fresh.run_mock(dataset, tmp_path / "small", fresh.MockSettings(64, 8))
    old, altered, small = (read_records(tmp_path / name) for name in ("original", "poisoned", "small"))
    for left, right, cut in zip(old, altered, small):
        for field in ("prompt", "prompt_token_ids", "completion_token_ids", "seed", "prefix_text", "request_sha256"):
            assert left[field] == right[field], field
        assert left["seed"] == cut["seed"] and left["prompt_token_ids"] == cut["prompt_token_ids"]
        assert cut["completion_token_ids"] == left["completion_token_ids"][:cut["completion_cap"]]
        if cut["arm"] != "O":
            assert cut["finish_reason"] == "length" and not cut["includes_eos"]


def test_completed_resume_is_byte_identical_and_refuses_changed_settings(tmp_path):
    output = tmp_path / "mock"
    dataset, settings = fresh.synthetic_dataset(), fresh.MockSettings(64, 64)
    fresh.run_mock(dataset, output, settings)
    before = {p.name: p.read_bytes() for p in output.iterdir() if p.is_file()}
    fresh.run_mock(dataset, output, settings)
    assert before == {p.name: p.read_bytes() for p in output.iterdir() if p.is_file()}
    with pytest.raises(ValueError, match="identity mismatch"):
        fresh.run_mock(dataset, output, fresh.MockSettings(64, 63))
    assert before == {p.name: p.read_bytes() for p in output.iterdir() if p.is_file()}


def test_failed_attempt_is_fsynced_and_is_never_silently_retried(tmp_path):
    class FailingMock(MockLLM):
        def __init__(self):
            super().__init__()
            self.attempts = 0

        def stream_events(self, *args, **kwargs):
            self.attempts += 1
            if self.attempts == 2:
                raise RuntimeError("injected backend abort")
            return super().stream_events(*args, **kwargs)

    model, output = FailingMock(), tmp_path / "failed"
    dataset, settings = fresh.synthetic_dataset(), fresh.MockSettings(64, 64)
    with pytest.raises(RuntimeError, match="backend abort"):
        fresh.run_mock(dataset, output, settings, model=model)
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["attempted_mock_calls"] == 2 and manifest["completed_mock_calls"] == 1
    assert manifest["cost_status"] == "unknown_incurred"
    entries = [json.loads(line) for line in (output / "calls.jsonl").read_text().splitlines()]
    assert entries[-1]["kind"] == "call_started" and entries[-1]["value"]["reserved_completion_cap"] == 64
    before = (output / "calls.jsonl").read_bytes()
    with pytest.raises(ValueError, match="no automatic retry"):
        fresh.run_mock(dataset, output, settings, model=model)
    assert model.attempts == 2 and (output / "calls.jsonl").read_bytes() == before


def test_resume_between_calls_does_not_regenerate_base(tmp_path, monkeypatch):
    dataset, settings = fresh.synthetic_dataset(), fresh.MockSettings(64, 64)
    build = fresh.build_request

    def interrupt_before_start(*args, **kwargs):
        if args[3] == "F":
            raise KeyboardInterrupt("between calls")
        return build(*args, **kwargs)

    monkeypatch.setattr(fresh, "build_request", interrupt_before_start)
    with pytest.raises(KeyboardInterrupt):
        fresh.run_mock(dataset, tmp_path / "partial", settings)
    monkeypatch.setattr(fresh, "build_request", build)
    manifest = fresh.run_mock(dataset, tmp_path / "partial", settings)
    assert manifest["completed_mock_calls"] == manifest["attempted_mock_calls"] == 9
    assert len(read_records(tmp_path / "partial")) == 9
    assert "error" not in manifest


@pytest.mark.parametrize("filename", ["calls.jsonl", "records.json", "paths.json"])
def test_tampered_completed_artifacts_fail_without_modifying_journal(tmp_path, filename):
    output = tmp_path / "mock"
    dataset, settings = fresh.synthetic_dataset(), fresh.MockSettings(64, 64)
    fresh.run_mock(dataset, output, settings)
    with (output / filename).open("a") as handle:
        handle.write(" ")
    before = (output / "calls.jsonl").read_bytes()
    with pytest.raises(ValueError, match="Torn|changed"):
        fresh.run_mock(dataset, output, settings)
    assert (output / "calls.jsonl").read_bytes() == before


def test_real_data_and_non_mock_backend_are_rejected_before_output_creation(tmp_path):
    dataset, settings = fresh.synthetic_dataset(), fresh.MockSettings(64, 64)
    dataset["role"] = "main_study"
    with pytest.raises(ValueError, match="synthetic fixtures only"):
        fresh.run_mock(dataset, tmp_path / "real", settings)
    assert not (tmp_path / "real").exists()
    with pytest.raises(ValueError, match="offline MockLLM"):
        fresh.run_mock(fresh.synthetic_dataset(), tmp_path / "backend", settings, model=object())
    assert not (tmp_path / "backend").exists()


def test_smoke_runs_without_importing_model_or_gui_libraries(tmp_path):
    root = Path(__file__).resolve().parents[1]
    code = """
import builtins, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in ('mlx', 'mlx_lm', 'PySide6', 'PyQt6', 'PyQt5'):
        raise AssertionError('Forbidden software-smoke dependency: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from scripts.smoke_cot_restart_fresh import main
main(['--output', sys.argv[1]])
"""
    proc = subprocess.run([sys.executable, "-c", code, str(tmp_path / "headless")],
                          cwd=root, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["completed_mock_calls"] == 12 and result["real_model_calls"] == 0


def test_empty_prefix_is_retained_and_labeled_without_outcome_selection(tmp_path):
    output = tmp_path / "short"
    manifest = fresh.run_mock(fresh.synthetic_dataset(), output, fresh.MockSettings(1, 8))
    assert manifest["completed_mock_calls"] == 9
    f_records = [r for r in read_records(output) if r["arm"] == "F"]
    assert len(f_records) == 3 and all(r["prefix_collapsed_to_empty"] for r in f_records)
