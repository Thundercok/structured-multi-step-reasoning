"""Regression checks use synthetic calls only and prohibit native imports."""

import copy
import hashlib
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

import scripts.pilot_order_certificate as pilot
from experiments.order_certificate_study import _selected_answer
from experiments.research_study import main


def fail_runtime(*args, **kwargs):
    raise AssertionError("Offline validation must never load a native runtime")


@pytest.fixture(autouse=True)
def block_native_runtime(monkeypatch):
    monkeypatch.setattr(pilot, "_load_runtime", fail_runtime)
    monkeypatch.setattr(pilot, "load", fail_runtime)


def collect(tmp_path, **kwargs):
    return pilot.run_pilot(num_items=1, seeds=[42], output_dir=tmp_path / "run",
                           mock=True, verbose=False, **kwargs)


def hashes(folder):
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in folder.iterdir() if path.is_file() and path.name != ".writer.lock"}


def test_mock_import_does_not_import_mlx():
    result = subprocess.run([sys.executable, "-c", "import sys; import scripts.pilot_order_certificate; assert not any(k == 'mlx' or k.startswith('mlx.') or k == 'mlx_lm' or k.startswith('mlx_lm.') for k in sys.modules)"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def stub_stream_runtime(monkeypatch, responses):
    events = []
    monkeypatch.setattr(pilot, "mx", SimpleNamespace(
        random=SimpleNamespace(seed=lambda seed: events.append(("seed", seed))),
        clear_cache=lambda: events.append(("clear", None))))
    monkeypatch.setattr(pilot, "make_sampler", lambda temp: temp)
    def stream(*args, **kwargs):
        for row in responses:
            events.append(("response", row))
            yield row
    monkeypatch.setattr(pilot, "stream_generate", stream)
    tokenizer = SimpleNamespace(apply_chat_template=lambda *args, **kwargs: "rendered fixture")
    return tokenizer, events


def test_stream_uses_final_backend_counts_and_finish_reason_not_chunk_count(monkeypatch):
    responses = [SimpleNamespace(text="Answer: Carol", prompt_tokens=123, generation_tokens=1,
                                 finish_reason=None),
                 SimpleNamespace(text="", prompt_tokens=123, generation_tokens=7, finish_reason="stop")]
    tokenizer, events = stub_stream_runtime(monkeypatch, responses)
    call = pilot.run_call(None, tokenizer, [{"role": "user", "content": "fixture"}],
                          max_tokens=7, temperature=0.7, enable_thinking=True, seed=42)
    assert call["completion_tokens"] == 7 and call["prompt_tokens"] == 123
    assert call["finish_reason"] == "stop" and call["output"] == "Answer: Carol"
    assert call["rendered_prompt"] == "rendered fixture"
    assert events[0] == ("seed", 42) and events[-1] == ("clear", None)
    assert sum(kind == "response" for kind, _ in events) == 2


@pytest.mark.parametrize("responses", [[], [SimpleNamespace(text="", finish_reason=None)],
                                      [SimpleNamespace(text="", prompt_tokens=1, generation_tokens=8,
                                                       finish_reason="length")]])
def test_missing_or_invalid_stream_telemetry_is_not_fabricated(monkeypatch, responses):
    tokenizer, events = stub_stream_runtime(monkeypatch, responses)
    with pytest.raises(RuntimeError, match="telemetry"):
        pilot.run_call(None, tokenizer, [], max_tokens=7, temperature=0,
                       enable_thinking=False, seed=42)
    assert events[-1] == ("clear", None)


def test_evidence_is_explicit_in_every_artifact(tmp_path):
    dataset, records, settings, report = collect(tmp_path)
    folder = tmp_path / "run"
    assert dataset["role"] == "development_tuning"
    assert dataset["evidence"] == report["evidence"] == "synthetic_smoke"
    assert all(row["evidence"] == "synthetic_smoke" for row in records)
    assert all(call["evidence"] == "synthetic_smoke" for row in records for call in row["generations"])
    manifest = json.loads((folder / "manifest.json").read_text())
    assert manifest["status"] == "complete" and manifest["model_calls"] is False
    assert manifest["confirmatory"] is False
    assert "synthetic_smoke" in (folder / "report.md").read_text()
    for name, expected in manifest["artifact_sha256"].items():
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == expected


@pytest.mark.parametrize("override", [{"mock": False}, {"thinking_max_tokens": 64}, {"seeds": [43]}, {"num_items": 2}])
def test_resume_rejects_changed_mode_profile_or_selection_before_writing(tmp_path, override):
    collect(tmp_path)
    before = hashes(tmp_path / "run")
    kwargs = dict(num_items=1, seeds=[42], output_dir=tmp_path / "run", mock=True, verbose=False)
    kwargs.update(override)
    with pytest.raises(ValueError, match="Resume"):
        pilot.run_pilot(**kwargs)
    assert hashes(tmp_path / "run") == before


def test_completed_resume_preserves_all_artifacts_without_calls(tmp_path, monkeypatch):
    first = collect(tmp_path)
    before = hashes(tmp_path / "run")
    monkeypatch.setattr(pilot, "collect_single_item", fail_runtime)
    second = collect(tmp_path)
    assert first[3] == second[3]
    assert hashes(tmp_path / "run") == before


@pytest.mark.parametrize("field,value", [("artifact_sha256", {}), ("journal_entries", 0),
                                         ("evidence", "measured_development_pilot")])
def test_completed_resume_rejects_invalid_manifest(tmp_path, field, value):
    collect(tmp_path)
    path = tmp_path / "run/manifest.json"
    manifest = json.loads(path.read_text())
    manifest[field] = value
    path.write_text(json.dumps(manifest))
    before = hashes(tmp_path / "run")
    with pytest.raises(ValueError, match="artifact|manifest|Manifest"):
        collect(tmp_path)
    assert hashes(tmp_path / "run") == before


def test_valid_fsynced_tail_is_recovered_when_manifest_lags(tmp_path):
    collect(tmp_path)
    path = tmp_path / "run/manifest.json"
    manifest = json.loads(path.read_text())
    entries = [json.loads(line) for line in (tmp_path / "run/calls.jsonl").read_text().splitlines()]
    manifest.update(status="interrupted", journal_head=entries[-2]["sha256"], journal_entries=len(entries) - 1)
    path.write_text(json.dumps(manifest))
    collect(tmp_path)
    assert json.loads(path.read_text())["journal_entries"] == len(entries)
    assert len((tmp_path / "run/calls.jsonl").read_text().splitlines()) == len(entries)


def test_second_writer_cannot_modify_locked_run(tmp_path):
    from experiments.order_pilot_checkpoint import PilotCheckpoint
    dataset, _, settings, _ = collect(tmp_path)
    folder = tmp_path / "run"
    identity = json.loads((folder / "manifest.json").read_text())["identity"]
    first = PilotCheckpoint(folder, identity, dataset, settings)
    try:
        before = hashes(folder)
        with pytest.raises(BlockingIOError):
            PilotCheckpoint(folder, identity, dataset, settings)
        assert hashes(folder) == before
    finally:
        first.close()


def test_interruption_preserves_each_finished_call_and_resumes_only_missing_calls(tmp_path, monkeypatch):
    original = pilot._mock_text
    def interrupt(item, arm, index):
        if arm == "candidate_selection" and index == 1:
            raise KeyboardInterrupt("synthetic interruption")
        return original(item, arm, index)
    monkeypatch.setattr(pilot, "_mock_text", interrupt)
    with pytest.raises(KeyboardInterrupt):
        collect(tmp_path)
    folder = tmp_path / "run"
    entries = [json.loads(line) for line in (folder / "calls.jsonl").read_text().splitlines()]
    assert sum(row["kind"] == "generation" for row in entries) == 3
    assert len(json.loads((folder / "records.json").read_text())) == 2
    assert json.loads((folder / "manifest.json").read_text())["status"] == "interrupted"
    calls = []
    def track(item, arm, index):
        calls.append((arm, index))
        return original(item, arm, index)
    monkeypatch.setattr(pilot, "_mock_text", track)
    collect(tmp_path)
    assert calls == [("candidate_selection", 1), ("candidate_selection", 2),
                     ("candidate_selection", 3), ("thinking_native", 0)]
    entries = [json.loads(line) for line in (folder / "calls.jsonl").read_text().splitlines()]
    assert sum(row["kind"] == "generation" for row in entries) == 7
    assert len(json.loads((folder / "records.json").read_text())) == 4


def test_execution_failure_does_not_lose_a_finished_pal_generation(tmp_path, monkeypatch):
    original = pilot.run_python_sandboxed
    monkeypatch.setattr(pilot, "run_python_sandboxed", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        collect(tmp_path)
    entries = [json.loads(line) for line in (tmp_path / "run/calls.jsonl").read_text().splitlines()]
    assert len(entries) == 1 and entries[0]["kind"] == "generation"
    monkeypatch.setattr(pilot, "run_python_sandboxed", original)
    original_text = pilot._mock_text
    calls = []
    def track(item, arm, index):
        calls.append(arm)
        return original_text(item, arm, index)
    monkeypatch.setattr(pilot, "_mock_text", track)
    collect(tmp_path)
    assert "pal_answer" not in calls


@pytest.mark.parametrize("corruption", ["tail", "checksum"])
def test_corrupt_journal_fails_closed_without_truncating(tmp_path, corruption):
    collect(tmp_path)
    path = tmp_path / "run/calls.jsonl"
    if corruption == "tail":
        path.write_text(path.read_text() + '{"unfinished":')
    else:
        lines = path.read_text().splitlines()
        entry = json.loads(lines[0])
        entry["value"]["output"] = "tampered"
        lines[0] = json.dumps(entry)
        path.write_text("\n".join(lines) + "\n")
    before = hashes(tmp_path / "run")
    with pytest.raises(ValueError, match="journal|Journal"):
        collect(tmp_path)
    assert hashes(tmp_path / "run") == before


def test_legacy_directory_and_invalid_requests_are_not_overwritten(tmp_path):
    folder = tmp_path / "run"
    folder.mkdir()
    (folder / "records.json").write_text("[]")
    with pytest.raises(ValueError, match="manifest"):
        collect(tmp_path)
    assert (folder / "records.json").read_text() == "[]"
    for count in (0, -1, 9):
        with pytest.raises(ValueError):
            pilot.run_pilot(num_items=count, output_dir=tmp_path / "new", mock=True)
    assert not (tmp_path / "new").exists()


@pytest.mark.parametrize("arm,index", [("candidate_selection", 0), ("candidate_selection", 3), ("thinking_native", 0), ("pal_certificate", 0)])
def test_selected_truncation_is_incorrect_even_if_answer_matches_gold(tmp_path, arm, index):
    dataset, records, settings, _ = collect(tmp_path)
    row = next(row for row in records if row["arm"] == arm)
    row["generations"][index]["finish_reason"] = "length"
    if row["execution"] is not None:
        row["execution"]["finish_reason"] = "length"
    row["answer"] = _selected_answer(row)[0]
    report = pilot.generate_pilot_report(dataset, records, settings)
    assert report["summary"]["fixed_" + arm]["accuracy"] == 0


def test_unselected_truncation_does_not_invalidate_selected_candidate(tmp_path):
    dataset, records, settings, _ = collect(tmp_path)
    row = next(row for row in records if row["arm"] == "candidate_selection")
    row["generations"][2]["finish_reason"] = "length"
    report = pilot.generate_pilot_report(dataset, records, settings)
    assert report["summary"]["fixed_candidate_selection"]["accuracy"] == 1


def test_correct_answer_invalid_witness_is_false_reject_and_fallback_harm(tmp_path):
    dataset, records, settings, _ = collect(tmp_path)
    records = copy.deepcopy(records)
    cert = next(row for row in records if row["arm"] == "pal_certificate")
    cert["execution"]["output"] = json.dumps({"order": [], "answer": cert["answer"]})
    candidate = next(row for row in records if row["arm"] == "candidate_selection")
    candidate["generations"][0]["output"] = "No final answer"
    candidate["generations"][-1]["messages"][0]["content"] = dataset["items"][0]["query"] + "\n" + pilot.PROMPTS["selector"] + "\n" + pilot.format_selector_candidates([call["output"] for call in candidate["generations"][:3]])
    candidate["answer"] = ""
    report = pilot.generate_pilot_report(dataset, records, settings)
    verified = report["summary"]["verified_certificate"]
    assert verified["gate_confusion_by_answer"]["false_reject"] == 1
    assert verified["gate_confusion_by_answer"]["true_reject"] == 0
    assert verified["harm_from_initial"] == 1
    assert report["summary"]["w_certificate"]["accuracy"] == 1
    assert verified["accuracy"] == 0
    stage_cost = sum(call["prompt_tokens"] + call["completion_tokens"] for call in cert["generations"])
    fallback_cost = sum(call["prompt_tokens"] + call["completion_tokens"] for call in candidate["generations"])
    assert verified["mean_tokens"] == stage_cost + fallback_cost
    assert verified["cost_identity"]["reconstructed_mean_tokens"] == verified["mean_tokens"]


def test_mixed_evidence_and_test_data_cannot_enter_pilot_report(tmp_path):
    dataset, records, settings, _ = collect(tmp_path)
    records[0]["evidence"] = "measured_development_pilot"
    with pytest.raises(ValueError, match="evidence"):
        pilot.generate_pilot_report(dataset, records, settings)
    dataset["items"][0]["split"] = "test"
    with pytest.raises(ValueError, match="development"):
        pilot.generate_pilot_report(dataset, records, settings)


def test_supported_entry_point_runs_mock_only_and_rejects_stray_overrides(tmp_path):
    main(["--order-certificate-pilot", "--order-pilot-mock", "--order-pilot-items", "1",
          "--seed", "42", "--output", str(tmp_path / "supported")])
    assert "synthetic_smoke" in (tmp_path / "supported/report.md").read_text()
    with pytest.raises(SystemExit):
        main(["--order-certificate-smoke", "--order-pilot-mock", "--output", str(tmp_path / "bad")])
    assert not (tmp_path / "bad").exists()
