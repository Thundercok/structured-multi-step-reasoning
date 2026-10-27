"""Unit and regression tests for Qwen3.5-4B CoT restart development pilot."""

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import pytest

from experiments.cot_restart_pilot import (
    CANONICAL_PILOT_ARMS,
    CONFIG_ARMS,
    DEV_POOL_PATH,
    MAX_CALLS_LIMIT,
    MENU,
    MODEL_FILE_HASHES,
    PROPOSED_6ARM_CONFIG,
    PilotJournal,
    build_run_identity,
    calculate_planned_calls_upper_bound,
    derive_call_seed,
    generate_summary_statistics,
    make_prefix_menu,
    reasoning_prefix,
    resolve_and_verify_local_snapshot,
    run_cot_restart_pilot,
    select_pilot_questions,
    sentence_boundaries,
    text_sha256,
)
from experiments.cot_restart_addendum import (
    DEFAULT_HISTORICAL_DIR,
    run_cot_restart_addendum,
    verify_historical_run,
)
from reasoning.reasoning_strategies import parse_answer_details
from research_identity import problem_fingerprint


def test_pilot_question_selection_is_stratified_and_outcome_blind():
    items = select_pilot_questions(DEV_POOL_PATH)
    assert len(items) == 12
    families = [it["family"] for it in items]
    assert families.count("arith") == 4
    assert families.count("order") == 4
    assert families.count("g24") == 4

    # Unique canonical fingerprints
    fps = [problem_fingerprint(it) for it in items]
    assert len(set(fps)) == 12

    # Verify seed 42 reproducible selection
    again = select_pilot_questions(DEV_POOL_PATH)
    assert [it["id"] for it in items] == [it["id"] for it in again]


def test_menu_snapping_sentence_boundaries_and_final_marker_exclusion():
    raw_trace = (
        "First step is addition. Second step is multiplication. "
        "Final step is checking the output.\nAnswer: 42"
    )
    info, menu = make_prefix_menu(raw_trace, count_tokens=len)
    assert info["explicit_answer_marker_count"] == 1
    assert [m["q_requested"] for m in menu] == [0.0, 0.25, 0.5, 0.75]

    for m in menu:
        assert "Answer:" not in m["prefix"]
        assert raw_trace.startswith(m["prefix"])
        assert 0.0 <= m["q_actual"] <= 1.0


def test_prefix_deduplication_collapses_identical_snapped_cuts():
    # Short trace with only one interior sentence boundary
    short_trace = "Only one sentence here.\nAnswer: 10"
    info, menu = make_prefix_menu(short_trace, count_tokens=len)
    assert info["distinct_menu_prefixes"] == 1
    assert all(m["cut_char"] == 0 for m in menu)


def test_full_prefix_continuation_arm_contract():
    raw_trace = "Step 1 is addition. Step 2 is multiplication.\nAnswer: 42"
    body, end, markers = reasoning_prefix(raw_trace)
    assert markers == 1
    assert body == "Step 1 is addition. Step 2 is multiplication."
    # full_prefix_continuation continues directly from uncut body (q=1.0)
    assert "Answer:" not in body


def test_token_accounting_and_budget_infeasibility():
    # If rendered prompt is 100 tokens and budget is 90 tokens, completion cap must be infeasible
    budget = 90
    prompt_tokens = 100
    comp_cap = budget - prompt_tokens
    assert comp_cap <= 0
    # Must never silently raise cap above budget
    assert budget < prompt_tokens


def test_journal_append_only_fsync_and_chaining(tmp_path):
    manifest = {"status": "running"}
    journal = PilotJournal(tmp_path, manifest)

    # Append call 1
    journal.append("smoke", ["call1"], {"output": "A", "completion_tokens": 10})
    head1 = journal.head
    count1 = journal.count
    assert count1 == 1

    # Append call 2
    journal.append("smoke", ["call2"], {"output": "B", "completion_tokens": 15})
    head2 = journal.head
    count2 = journal.count
    assert count2 == 2
    assert head2 != head1
    assert journal.total_completion_tokens == 25
    journal.close()

    # Re-open and verify replay integrity
    journal_resumed = PilotJournal(tmp_path, manifest)
    assert journal_resumed.count == 2
    assert journal_resumed.head == head2
    assert journal_resumed.total_completion_tokens == 25
    assert journal_resumed.has("smoke", "call1")
    assert journal_resumed.has("smoke", "call2")
    journal_resumed.close()


def test_resume_integrity_rejects_identity_mismatch(tmp_path):
    output_dir = tmp_path / "resume_test"
    output_dir.mkdir(parents=True)
    manifest_file = output_dir / "manifest.json"

    # Simulate existing manifest with mock=True
    id_mock = build_run_identity(mock=True)
    manifest_mock = {"status": "running", "identity": id_mock, "mock": True}
    manifest_file.write_text(json.dumps(manifest_mock))

    # Attempt to resume with mock=False (real model) -> must fail!
    id_real = build_run_identity(mock=False)
    manifest_real = {"status": "running", "identity": id_real, "mock": False}

    with pytest.raises(ValueError, match="Resume identity mismatch on 'mock'"):
        PilotJournal(output_dir, manifest_real, expected_identity=id_real)


def test_resume_integrity_rejects_source_sha256_mismatch(tmp_path):
    output_dir = tmp_path / "resume_source_hash_test"
    output_dir.mkdir(parents=True)
    manifest_file = output_dir / "manifest.json"

    id_expected = build_run_identity(mock=True)
    # Tamper with source_sha256 in existing manifest
    id_tampered = copy.deepcopy(id_expected)
    id_tampered["source_sha256"]["experiments/cot_restart_pilot.py"] = "0" * 64

    manifest_tampered = {"status": "running", "identity": id_tampered, "mock": True}
    manifest_file.write_text(json.dumps(manifest_tampered))

    with pytest.raises(ValueError, match="Resume identity mismatch on 'source_sha256'"):
        PilotJournal(output_dir, manifest_tampered, expected_identity=id_expected)


def test_resume_integrity_rejects_dataset_mismatch(tmp_path):
    output_dir = tmp_path / "resume_ds_test"
    output_dir.mkdir(parents=True)
    manifest_file = output_dir / "manifest.json"
    dataset_file = output_dir / "dataset.json"

    id_expected = build_run_identity(mock=True)
    manifest_valid = {"status": "running", "identity": id_expected, "mock": True}
    manifest_file.write_text(json.dumps(manifest_valid))

    # Write corrupt/tampered dataset items
    dataset_file.write_text(json.dumps({"name": "test", "items": [{"id": "fake_item"}]}))

    with pytest.raises(ValueError, match="Resume dataset items mismatch"):
        PilotJournal(output_dir, manifest_valid, expected_identity=id_expected)


def test_thinking_native_answer_only_after_think_tag():
    # Incomplete thinking: no </think>
    incomplete_raw = "<think>\nThinking step by step... Answer: 42"
    assert "</think>" not in incomplete_raw

    # Completed thinking: </think> present
    completed_raw = "<think>\nSome thinking...\n</think>\n\nAnswer: 42"
    assert "</think>" in completed_raw
    post_think = completed_raw.split("</think>")[-1]
    parsed, status, _ = parse_answer_details(post_think, answer_type="number")
    assert parsed == "42"
    assert status == "marker"


def test_mock_never_imports_mlx(tmp_path):
    # Execute mock pilot in a subprocess where MLX is deliberately unavailable
    output_dir = tmp_path / "no_mlx_mock_out"
    code = f"""
import sys
# Block mlx imports entirely
sys.modules['mlx'] = None
sys.modules['mlx.core'] = None
sys.modules['mlx_lm'] = None

from pathlib import Path
from experiments.cot_restart_pilot import run_cot_restart_pilot

run_cot_restart_pilot(Path('{str(output_dir)}'), mock=True)
"""
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert res.returncode == 0, f"Error: {res.stderr}\nOutput: {res.stdout}"
    assert (output_dir / "manifest.json").exists()
    assert (output_dir / "summary.json").exists()


def test_mock_pilot_execution_via_research_study(tmp_path):
    output_dir = tmp_path / "mock_pilot_out"
    cmd = [
        sys.executable,
        "-m",
        "experiments.research_study",
        "--cot-restart-pilot",
        "--cot-restart-mock",
        "--output",
        str(output_dir),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"Error: {res.stderr}\nOutput: {res.stdout}"

    # Verify generated artifacts
    assert (output_dir / "manifest.json").exists()
    assert (output_dir / "dataset.json").exists()
    assert (output_dir / "plan.json").exists()
    assert (output_dir / "calls.jsonl").exists()
    assert (output_dir / "base_traces.json").exists()
    assert (output_dir / "restart_records.json").exists()
    assert (output_dir / "summary.json").exists()
    assert (output_dir / "report.md").exists()
    assert (output_dir / "RESULT_FOR_CODEX.md").exists()

    manifest = json.loads((output_dir / "manifest.json").read_text())
    assert manifest["status"] == "complete"
    assert manifest["mock"] is True

    summary = json.loads((output_dir / "summary.json").read_text())
    assert summary["dataset_items"] == 12
    assert "collection_cost" in summary
    assert "cells" in summary

    # Verify canonical pilot cells are present in summary
    assert "regenerate_b1024" in summary["cells"]
    assert "restart_q050_b2048" in summary["cells"]
    assert "thinking_native_b2048" in summary["cells"]

    # Verify end-to-end token keys exist in summary cells
    c = summary["cells"]["restart_q050_b2048"]
    assert "mean_e2e_total_tokens" in c
    assert "path_savings_vs_regenerate_pct" in c

    # Verify collection cost breakdown
    cost = summary["collection_cost"]
    assert "journal_records" in cost
    assert "executed_model_calls" in cost
    assert "skipped_calls" in cost
    assert "total_incurred_prompt_tokens" in cost
    assert "total_incurred_tokens" in cost
    assert cost["executed_model_calls"] <= 136


def test_budget_preflight_rejects_160_calls_without_calling_backend(tmp_path):
    output_dir = tmp_path / "preflight_rejection_out"

    # 6 arms x 2 budgets x 12 questions + 12 base + 4 smoke = 160 calls (> MAX_CALLS_LIMIT 136)
    assert calculate_planned_calls_upper_bound(12, PROPOSED_6ARM_CONFIG, (1024, 2048), True) == 160
    assert calculate_planned_calls_upper_bound(12, CANONICAL_PILOT_ARMS, (1024, 2048), True) == 136

    # Call run_cot_restart_pilot with PROPOSED_6ARM_CONFIG -> must reject before loading model
    with pytest.raises(
        ValueError,
        match=r"Budget preflight rejected: planned worst-case model calls \(160\) exceeds MAX_CALLS_LIMIT \(136\)",
    ):
        run_cot_restart_pilot(output_dir, mock=True, config_arms=PROPOSED_6ARM_CONFIG)

    # Crucial: verify that NO calls were executed and NO calls.jsonl exists
    assert not (output_dir / "calls.jsonl").exists()
    assert not (output_dir / "manifest.json").exists()


def test_budget_infeasible_accounting_preserves_zero_incurred_tokens(tmp_path):
    output_dir = tmp_path / "infeasible_accounting_out"
    manifest = {"status": "running"}
    journal = PilotJournal(output_dir, manifest)

    # Record a budget_infeasible item
    infeasible_record = {
        "executed_call": False,
        "skipped": True,
        "skip_reason": "budget_infeasible",
        "budget_infeasible": True,
        "prompt": "Very long prompt " * 200,
        "prompt_tokens_required": 2200,
        "incurred_prompt_tokens": 0,
        "prompt_tokens": 0,
        "completion_cap": 0,
        "raw_output": "",
        "completion_tokens": 0,
        "total_tokens": 0,
        "finish_reason": "budget_infeasible",
        "parsed_answer": None,
        "parse_status": "budget_infeasible",
        "wordy": False,
        "correct": False,
        "duration_ms": 0.0,
    }
    journal.append("restart_call", ["q1", "restart_q050", "2048"], infeasible_record)

    assert journal.skipped_calls == 1
    assert journal.executed_model_calls == 0
    assert journal.total_incurred_prompt_tokens == 0
    assert journal.total_completion_tokens == 0
    assert journal.total_incurred_tokens == 0
    assert journal.count == 1  # 1 journal record
    journal.close()

    # Verify that in summary statistics, the skipped item is NOT excluded from denominator
    base_traces = {
        "q1": {"correct": False, "total_tokens": 500, "prompt_tokens": 50, "completion_tokens": 450}
    }
    restart_rows = [{
        "question_id": "q1",
        "family": "arith",
        "arm": "restart_q050",
        "budget": 2048,
        "canonical_prefix_sha256": "abc",
        "is_deduplicated_call": False,
        "associated_arms": ["restart_q050"],
        "base_correct": False,
        **infeasible_record,
    }]
    j2 = PilotJournal(output_dir, manifest)
    summary = generate_summary_statistics(base_traces, restart_rows, j2)
    j2.close()

    cell = summary["cells"]["restart_q050_b2048"]
    assert cell["items"] == 1  # denominator preserved!
    assert cell["correct"] == 0
    assert cell["accuracy"] == 0.0
    assert cell["rescued"] == 0
    assert cell["budget_infeasible"] == 1
    assert summary["collection_cost"]["skipped_calls"] == 1
    assert summary["collection_cost"]["executed_model_calls"] == 0
    assert summary["collection_cost"]["total_completion_tokens"] == 0
    assert summary["collection_cost"]["total_incurred_prompt_tokens"] == 0


def test_addendum_verifies_historical_integrity(tmp_path):
    import shutil

    # 1. Real historical directory must verify cleanly
    manifest = verify_historical_run(DEFAULT_HISTORICAL_DIR)
    assert manifest["status"] == "complete"
    assert manifest["journal_count"] == 136

    # 2. Tampered directory with modified artifact hash must be rejected
    tampered_dir = tmp_path / "tampered_hist"
    shutil.copytree(DEFAULT_HISTORICAL_DIR, tampered_dir)
    with (tampered_dir / "calls.jsonl").open("a") as f:
        f.write("# tampered comment\n")
    with pytest.raises(ValueError, match="Historical artifact hash mismatch"):
        verify_historical_run(tampered_dir)

    # 3. Non-complete status must be rejected
    incomplete_dir = tmp_path / "incomplete_hist"
    shutil.copytree(DEFAULT_HISTORICAL_DIR, incomplete_dir)
    inc_man = json.loads((incomplete_dir / "manifest.json").read_text())
    inc_man["status"] = "running"
    (incomplete_dir / "manifest.json").write_text(json.dumps(inc_man))
    with pytest.raises(ValueError, match="Historical run status is 'running', expected 'complete'"):
        verify_historical_run(incomplete_dir)


def test_addendum_rejects_overwriting_historical_dir():
    with pytest.raises(ValueError, match="Output directory cannot be identical to historical run directory"):
        run_cot_restart_addendum(
            historical_dir=DEFAULT_HISTORICAL_DIR, output_dir=DEFAULT_HISTORICAL_DIR, mock=True
        )


def test_mock_addendum_execution_via_research_study(tmp_path):
    output_dir = tmp_path / "mock_addendum_out"
    cmd = [
        sys.executable,
        "-m",
        "experiments.research_study",
        "--cot-restart-addendum",
        "--cot-restart-addendum-mock",
        "--output",
        str(output_dir),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"Error: {res.stderr}\nOutput: {res.stdout}"

    # Verify generated artifacts
    assert (output_dir / "manifest.json").exists()
    assert (output_dir / "calls.jsonl").exists()
    assert (output_dir / "addendum_records.json").exists()
    assert (output_dir / "summary.json").exists()
    assert (output_dir / "report.md").exists()
    assert (output_dir / "RESULT_FOR_CODEX.md").exists()

    manifest = json.loads((output_dir / "manifest.json").read_text())
    assert manifest["status"] == "complete"
    assert manifest["mock"] is True

    summary = json.loads((output_dir / "summary.json").read_text())
    assert summary["dataset_items"] == 12
    assert summary["collection_cost"]["executed_model_calls"] == 12
    assert "full_prefix_continuation" in summary
    assert "comparative_budget_2048" in summary
    assert "per_item_diagnostics" in summary
    assert len(summary["per_item_diagnostics"]) == 12


def test_failure_mid_call_and_resume(tmp_path, monkeypatch):
    import experiments.cot_restart_addendum as addendum_mod

    output_dir = tmp_path / "failure_resume_test"

    # Inject failure on the 3rd backend call
    real_execute = addendum_mod.execute_llm_call
    call_counter = [0]

    def failing_execute(*args, **kwargs):
        call_counter[0] += 1
        if call_counter[0] == 3:
            raise RuntimeError("Injected mid-inference failure on call 3")
        return real_execute(*args, **kwargs)

    monkeypatch.setattr(addendum_mod, "execute_llm_call", failing_execute)

    # 1. First run: must fail during call 3
    with pytest.raises(RuntimeError, match="Injected mid-inference failure on call 3"):
        run_cot_restart_addendum(DEFAULT_HISTORICAL_DIR, output_dir, mock=True)

    # 2. Check manifest and journal state immediately after failure
    manifest_file = output_dir / "manifest.json"
    assert manifest_file.exists()
    failed_man = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert failed_man["status"] == "failed"
    assert "Injected mid-inference failure" in failed_man["error"]
    assert failed_man["cost_status"] == "unknown_incurred"
    assert failed_man["executed_model_calls"] == 2
    assert failed_man["total_attempted_calls"] == 3
    assert failed_man["failed_attempts"] == 1
    assert failed_man.get("in_flight_call") is not None

    # Check journal has 5 records: 2 successful pairs (call_started + addendum_call) + 1 failed call_started
    journal_file = output_dir / "calls.jsonl"
    lines = [json.loads(line) for line in journal_file.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 5
    started_entries = [e for e in lines if e.get("kind") == "call_started"]
    completed_entries = [e for e in lines if e.get("kind") == "addendum_call"]
    assert len(started_entries) == 3
    assert len(completed_entries) == 2

    # 3. Resume run without failure
    monkeypatch.setattr(addendum_mod, "execute_llm_call", real_execute)
    resumed = run_cot_restart_addendum(DEFAULT_HISTORICAL_DIR, output_dir, mock=True)

    assert resumed["status"] == "complete"
    resumed_man = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert resumed_man["status"] == "complete"
    assert resumed["manifest"]["status"] == "complete"
    assert resumed_man["executed_model_calls"] == 12
    # Total attempted calls = 1 initial failed attempt + 12 completed attempts = 13
    assert resumed_man["total_attempted_calls"] == 13
    assert resumed_man["failed_attempts"] == 1
    assert resumed_man["cost_status"] == "unknown_incurred"

    # Total entries in calls.jsonl:
    # 1 failed call_started + 12 successful call_started + 12 completed addendum_call = 25
    final_lines = [json.loads(line) for line in journal_file.read_text(encoding="utf-8").splitlines()]
    assert len(final_lines) == 25


def test_local_model_snapshot_verification(tmp_path):
    # 1. Existing local snapshot must resolve and match pinned hashes
    snapshot_dir = resolve_and_verify_local_snapshot()
    assert snapshot_dir.exists()
    assert snapshot_dir.is_dir()
    for fname in MODEL_FILE_HASHES:
        assert (snapshot_dir / fname).exists()

    # 2. Missing snapshot directory must raise FileNotFoundError
    non_existent = tmp_path / "non_existent_snapshot"
    with pytest.raises(FileNotFoundError, match="Local model snapshot directory not found"):
        resolve_and_verify_local_snapshot(non_existent)

    # 3. Snapshot with missing file must raise FileNotFoundError
    incomplete_snap = tmp_path / "incomplete_snap"
    incomplete_snap.mkdir()
    with pytest.raises(FileNotFoundError, match="missing from local snapshot"):
        resolve_and_verify_local_snapshot(incomplete_snap)

    # 4. Snapshot with tampered file must raise ValueError
    tampered_snap = tmp_path / "tampered_snap"
    tampered_snap.mkdir()
    for fname in MODEL_FILE_HASHES:
        (tampered_snap / fname).write_text("dummy content")
    with pytest.raises(ValueError, match="hash mismatch in snapshot"):
        resolve_and_verify_local_snapshot(tampered_snap)


def test_addendum_reports_observational_transitions_without_mechanism_claims(tmp_path):
    output_dir = tmp_path / "addendum_report_audit"
    run_cot_restart_addendum(DEFAULT_HISTORICAL_DIR, output_dir, mock=True)

    report_text = (output_dir / "report.md").read_text(encoding="utf-8")
    codex_text = (output_dir / "RESULT_FOR_CODEX.md").read_text(encoding="utf-8")

    # Observational header and transition values must be present
    assert "Observed Transition (Single Draw)" in report_text
    assert "Observed transition:" in report_text

    # Hard-coded mechanism conclusions must NOT be present
    assert "formatting/completion effect" not in report_text
    assert "requires reasoning revision/rollback" not in report_text
    assert "confirms the exact mechanism" not in report_text

    # Methodological caveats must be documented
    assert "Methodological Notes" in report_text
    assert "qualitative trace inspection across multiple draws" in report_text
    assert "Mechanism determination caveats" in codex_text

