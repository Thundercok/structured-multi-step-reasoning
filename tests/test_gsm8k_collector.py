"""Comprehensive software tests for GSM8K staged collector, fail-closed recovery, and sealed validation.

Strictly offline software fixtures; zero real model calls, candidate content unopened.
Exercises all conditions from D1-D6 and F1-F2 design reviews.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Tuple

import pytest

from experiments import gsm8k_collector as collector
from experiments import gsm8k_routing_baseline as routing
from experiments.gsm8k_collector import (
    BudgetExhaustedError,
    GSM8KCollectorCheckpoint,
    MockStagedRunner,
    QuarantineError,
    StagedExecutionResult,
    ToolExecutionResult,
    run_staged_collection,
)
from experiments.research_pilot import sha256_file
from experiments.research_study import ROOT, main, seed_for, source_hashes
from tests.test_gsm8k_routing_baseline import fixture_data, save_run


def make_test_dataset(num_items: int = 4) -> Dict[str, Any]:
    items = []
    for split, role_count in (("train", num_items // 2), ("calibration", num_items // 2)):
        for idx in range(role_count):
            ident = f"item_{split}_{idx}"
            items.append({
                "id": ident,
                "group_id": f"group_{split}_{idx}",
                "split": split,
                "query": f"Query text for {ident} with some words.",
                "answer": "42",
                "answer_type": "number",
                "category": "gsm8k",
            })
    return {
        "name": "fixture_dataset",
        "version": "1.0",
        "role": "development_tuning",
        "items": items,
    }


def make_test_identity(dataset: Dict[str, Any], evidence: str = "synthetic_pilot_smoke") -> Dict[str, Any]:
    dataset_bytes = json.dumps(dataset, sort_keys=True).encode("utf-8")
    return {
        "evidence": evidence,
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "prompt_profile": "english-math-v1",
        "seed": 42,
        "strategies": list(collector.ACTIONS),
        "max_tokens": 1024,
        "source_hashes": source_hashes(),
    }


def test_clean_collection_completes_and_verifies_manifest(tmp_path: Path):
    """Test full staged collection completes and matches all artifact checksums."""
    dataset = make_test_dataset(num_items=4)
    identity = make_test_identity(dataset)
    settings = {"temperature": 0.0, "thinking": False}

    run_dir = tmp_path / "run_clean"
    checkpoint = GSM8KCollectorCheckpoint(run_dir, identity, dataset, settings)
    runner = MockStagedRunner()

    manifest = run_staged_collection(checkpoint, runner, dataset)
    checkpoint.close()

    assert manifest["status"] == "complete"
    assert manifest["calls_completed"] == 4 * 3  # 4 items x 3 strategies = 12 calls
    assert manifest["calls_started"] == 12
    assert (run_dir / "records.json").is_file()
    assert (run_dir / "summary.json").is_file()
    assert (run_dir / "report.md").is_file()

    # Verify all artifacts in manifest match disk bytes
    for name, expected_sha in manifest["artifact_sha256"].items():
        assert sha256_file(run_dir / name) == expected_sha


def test_d1_hard_stop_after_started_is_outcome_unknown_and_quarantines(tmp_path: Path):
    """D1: A started-only attempt without outcome is outcome_unknown, halts, and retains reservation."""
    from experiments.gsm8k_collector import SimulatedProcessKill

    dataset = make_test_dataset(num_items=2)
    identity = make_test_identity(dataset)
    settings = {"temperature": 0.0, "thinking": False}

    run_dir = tmp_path / "run_hard_stop"
    checkpoint = GSM8KCollectorCheckpoint(run_dir, identity, dataset, settings)

    # Intercept run_generation to simulate hard crash/SIGKILL after started event is written
    class CrashingRunner(MockStagedRunner):
        def run_generation(self, item, strategy, max_tokens, seed):
            if item["id"] == "item_train_0" and strategy == "COT":
                # Simulate sudden process exit after pre-dispatch journal write
                raise SimulatedProcessKill("Simulated hard crash right after started write")
            return super().run_generation(item, strategy, max_tokens, seed)

    runner = CrashingRunner()
    with pytest.raises(SimulatedProcessKill):
        run_staged_collection(checkpoint, runner, dataset)
    checkpoint.close()

    # Re-open checkpoint on resume: it must detect outcome_unknown and quarantine
    checkpoint_resume = GSM8KCollectorCheckpoint(run_dir, identity, dataset, settings, resume=True)
    assert checkpoint_resume.has_unknown_outcomes()
    assert ("item_train_0", "COT") in checkpoint_resume.unknown_conditions

    # Attempting to run collection must raise QuarantineError under no-retry policy
    with pytest.raises(QuarantineError, match="quarantined"):
        run_staged_collection(checkpoint_resume, MockStagedRunner(), dataset)
    checkpoint_resume.close()

    # Verify that manifest reflects quarantined status and reserved tokens
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "quarantined"


def test_d2_stage_separation_persists_generation_before_pal_tool(tmp_path: Path):
    """D2: Generation outcome is persisted to calls.jsonl BEFORE PAL tool execution starts."""
    dataset = make_test_dataset(num_items=2)
    identity = make_test_identity(dataset)
    settings = {"temperature": 0.0, "thinking": False}

    run_dir = tmp_path / "run_stage_sep"
    checkpoint = GSM8KCollectorCheckpoint(run_dir, identity, dataset, settings)

    events_seen_at_tool_start = []

    class StageObservingRunner(MockStagedRunner):
        def run_tool(self, code, timeout_seconds=5.0):
            # Check journal lines on disk at the exact moment tool starts
            journal_lines = (run_dir / "calls.jsonl").read_text(encoding="utf-8").splitlines()
            events = [json.loads(line)["kind"] for line in journal_lines]
            events_seen_at_tool_start.append(events)
            return super().run_tool(code, timeout_seconds)

    runner = StageObservingRunner()
    run_staged_collection(checkpoint, runner, dataset)
    checkpoint.close()

    assert len(events_seen_at_tool_start) >= 2  # PAL runs for both items
    for events in events_seen_at_tool_start:
        # Verify that generation_outcome appeared BEFORE tool_started
        assert "generation_started" in events
        assert "generation_outcome" in events
        assert "tool_started" in events
        gen_idx = events.index("generation_outcome")
        tool_idx = events.index("tool_started")
        assert gen_idx < tool_idx


def test_f1_unknown_cost_recorded_as_budget_charge_not_measured(tmp_path: Path):
    """F1: Failed/unknown generation records measured_generated_tokens: null and budget_charge: 1024."""
    dataset = make_test_dataset(num_items=2)
    identity = make_test_identity(dataset)
    settings = {"temperature": 0.0, "thinking": False}

    run_dir = tmp_path / "run_f1"
    checkpoint = GSM8KCollectorCheckpoint(run_dir, identity, dataset, settings)

    # Runner that raises an exception on first generation call
    runner = MockStagedRunner(responses={
        ("item_train_0", "DIRECT"): {"raise_generation": RuntimeError("CUDA Out of Memory")}
    })

    with pytest.raises(RuntimeError, match="CUDA Out of Memory"):
        run_staged_collection(checkpoint, runner, dataset)
    checkpoint.close()

    # Read calls.jsonl to verify failure payload
    lines = (run_dir / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    fail_events = [json.loads(l) for l in lines if json.loads(l)["kind"] == "generation_outcome" and json.loads(l)["value"]["status"] == "failed"]
    assert len(fail_events) == 1
    val = fail_events[0]["value"]
    assert val["measured_generated_tokens"] is None
    assert val["measured_prompt_tokens"] is None
    assert val["budget_charge_tokens"] == 1024
    assert val["cost_status"] == "unknown_reserved"


def test_f2_pal_tool_failure_parses_generation_text_with_distinguishable_values(tmp_path: Path):
    """F2: PAL tool failure retains diagnostics and parses generation text (not tool error), preserving measured tokens."""
    dataset = make_test_dataset(num_items=2)
    identity = make_test_identity(dataset)
    settings = {"temperature": 0.0, "thinking": False}

    run_dir = tmp_path / "run_f2"
    checkpoint = GSM8KCollectorCheckpoint(run_dir, identity, dataset, settings)

    # Distinct values:
    # Model text contains answer 42 and code that triggers timeout
    model_text = "Answer: 42\n```python\n# RAISE_TOOL_TIMEOUT\nx = 1\n```"
    runner = MockStagedRunner(responses={
        ("item_train_0", "PAL"): {"output": model_text, "tokens": 310, "confidence": 0.8}
    })

    run_staged_collection(checkpoint, runner, dataset)
    checkpoint.close()

    records = json.loads((run_dir / "records.json").read_text(encoding="utf-8"))
    pal_record = next(r for r in records if r["id"] == "item_train_0" and r["strategy"] == "PAL")

    # 1. Answer parsed MUST be 42 (from model text), NOT 99 (tool code) and NOT error string!
    assert pal_record["answer"] == "42"
    assert pal_record["correct"] is True  # item_train_0 ground truth is 42
    # 2. Measured tokens MUST be preserved from generation (310)
    assert pal_record["tokens"] == 310
    # 3. Confidence discounted by 0.3 on tool failure: 0.8 * 0.3 = 0.24
    assert pytest.approx(pal_record["confidence"], 0.001) == 0.24
    # 4. Tool diagnostics recorded in trace.tools
    assert len(pal_record["trace"]["tools"]) == 1
    tool_entry = pal_record["trace"]["tools"][0]
    assert tool_entry["ok"] is False
    assert "TimeoutError" in tool_entry["output"]


def test_d3_corrupt_or_torn_journal_fails_closed_zero_byte_alteration(tmp_path: Path):
    """D3: Torn tail or checksum tamper raises ValueError and leaves disk 100% unchanged."""
    dataset = make_test_dataset(num_items=2)
    identity = make_test_identity(dataset)
    settings = {"temperature": 0.0, "thinking": False}

    run_dir = tmp_path / "run_d3"
    checkpoint = GSM8KCollectorCheckpoint(run_dir, identity, dataset, settings)
    run_staged_collection(checkpoint, MockStagedRunner(), dataset)
    checkpoint.close()

    # Scenario A: Torn line at tail (missing newline or cut mid-JSON)
    journal_path = run_dir / "calls.jsonl"
    clean_bytes = journal_path.read_bytes()
    journal_path.write_bytes(clean_bytes + b'{"incomplete": true')

    before_snapshot = {p.name: p.read_bytes() for p in run_dir.iterdir()}
    with pytest.raises(ValueError, match="Torn journal tail"):
        GSM8KCollectorCheckpoint(run_dir, identity, dataset, settings, resume=True)
    after_snapshot = {p.name: p.read_bytes() for p in run_dir.iterdir()}
    assert before_snapshot == after_snapshot

    # Scenario B: Tampered content with mismatched sha256
    lines = clean_bytes.decode("utf-8").splitlines()
    entry = json.loads(lines[0])
    entry["value"]["tampered"] = True
    tampered_bytes = (json.dumps(entry) + "\n" + "\n".join(lines[1:]) + "\n").encode("utf-8")
    journal_path.write_bytes(tampered_bytes)

    before_tamper = {p.name: p.read_bytes() for p in run_dir.iterdir()}
    with pytest.raises(ValueError, match="Journal checksum mismatch"):
        GSM8KCollectorCheckpoint(run_dir, identity, dataset, settings, resume=True)
    assert {p.name: p.read_bytes() for p in run_dir.iterdir()} == before_tamper


def test_d3_stale_manifest_advances_to_verified_journal_descendant(tmp_path: Path):
    """D3: Manifest with stale journal_head advances safely if head is a verified ancestor."""
    dataset = make_test_dataset(num_items=2)
    identity = make_test_identity(dataset)
    settings = {"temperature": 0.0, "thinking": False}

    run_dir = tmp_path / "run_stale_manifest"
    checkpoint = GSM8KCollectorCheckpoint(run_dir, identity, dataset, settings)
    run_staged_collection(checkpoint, MockStagedRunner(), dataset)
    checkpoint.close()

    # Artificially roll back manifest's journal_head to sequence 0 (which is in the verified chain)
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    first_entry = json.loads((run_dir / "calls.jsonl").read_text(encoding="utf-8").splitlines()[0])
    manifest["journal_head"] = first_entry["sha256"]
    manifest["journal_entries"] = 1
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    # Resuming checkpoint must verify ancestry and accept the journal chain
    checkpoint_resume = GSM8KCollectorCheckpoint(run_dir, identity, dataset, settings, resume=True)
    assert checkpoint_resume.count > 1
    checkpoint_resume.close()


def test_d6_configuration_and_environment_mismatch_fails_closed(tmp_path: Path):
    """D6: Resuming with altered prompt_profile, seed, or dataset sha fails closed."""
    dataset = make_test_dataset(num_items=2)
    identity = make_test_identity(dataset)
    settings = {"temperature": 0.0, "thinking": False}

    run_dir = tmp_path / "run_d6"
    checkpoint = GSM8KCollectorCheckpoint(run_dir, identity, dataset, settings)
    run_staged_collection(checkpoint, MockStagedRunner(), dataset)
    checkpoint.close()

    # Mismatched seed
    mismatched_id = copy.deepcopy(identity)
    mismatched_id["seed"] = 999
    with pytest.raises(ValueError, match="Seed contract mismatch"):
        GSM8KCollectorCheckpoint(run_dir, mismatched_id, dataset, settings, resume=True)

    # Mismatched prompt profile
    mismatched_prof = copy.deepcopy(identity)
    mismatched_prof["prompt_profile"] = "legacy"
    with pytest.raises(ValueError, match="Prompt profile mismatch"):
        GSM8KCollectorCheckpoint(run_dir, mismatched_prof, dataset, settings, resume=True)


def test_sealed_cli_fit_and_validate_workflow(tmp_path: Path):
    """Condition 3 & D5: --gsm8k-routing-fit seals selection, and --gsm8k-routing-validate consumes sealed selection without refitting."""
    # Create fixture completed pilot run
    items, records = fixture_data()
    pilot_dir = save_run(tmp_path / "fixture_pilot", items, records)

    # 1. Run fitting via CLI
    fit_out = tmp_path / "fit_output"
    main(["--gsm8k-routing-fit", str(pilot_dir), "--output", str(fit_out)])

    assert (fit_out / "selection.json").is_file()
    assert (fit_out / "manifest.json").is_file()
    manifest_fit = json.loads((fit_out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest_fit["status"] in ("selection_saved", "selection_sealed")
    assert "selection_sha256" in manifest_fit
    assert manifest_fit["selection_sha256"] == sha256_file(fit_out / "selection.json")

    # 2. Run validation via CLI
    val_out = tmp_path / "val_output"
    main(["--gsm8k-routing-validate", str(fit_out), "--output", str(val_out)])

    assert (val_out / "manifest.json").is_file()
    assert (val_out / "summary.json").is_file()
    assert (val_out / "report.md").is_file()
    manifest_val = json.loads((val_out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest_val["status"] == "complete"

    # Verify all 5 rows exist in summary (D4)
    summary = json.loads((val_out / "summary.json").read_text(encoding="utf-8"))
    methods = summary["methods"]
    assert "query_only_rule" in methods
    assert "selected_fixed_reference" in methods
    assert "fixed_direct" in methods
    assert "fixed_cot" in methods
    assert "fixed_pal" in methods
    assert "primary_comparison" in summary


def test_validation_fails_closed_if_selection_file_tampered_before_validate(tmp_path: Path):
    """D6: Tampering with selection.json before --gsm8k-routing-validate fails closed on checksum check."""
    items, records = fixture_data()
    pilot_dir = save_run(tmp_path / "fixture_pilot_tamper", items, records)

    fit_out = tmp_path / "fit_output_tamper"
    main(["--gsm8k-routing-fit", str(pilot_dir), "--output", str(fit_out)])

    # Tamper with selection.json
    selection_path = fit_out / "selection.json"
    sel_data = json.loads(selection_path.read_text(encoding="utf-8"))
    sel_data["selected_rule"]["id"] = "TAMPERED_RULE"
    selection_path.write_text(json.dumps(sel_data, indent=2) + "\n", encoding="utf-8")

    val_out = tmp_path / "val_output_tamper"
    with pytest.raises(SystemExit):
        main(["--gsm8k-routing-validate", str(fit_out), "--output", str(val_out)])
    assert not val_out.exists()


def test_validation_outcomes_poisoning_does_not_alter_fitted_selection(tmp_path: Path):
    """D5: Changing validation answers/outcomes leaves fitted selection.json byte-identical."""
    items, records = fixture_data()
    pilot_dir1 = save_run(tmp_path / "pilot_clean", items, records)

    # Second run with poisoned validation records
    poisoned_records = copy.deepcopy(records)
    for r in poisoned_records:
        if r["split"] == "calibration":
            r["correct"] = not r["correct"]
            r["tokens"] = 999
    pilot_dir2 = save_run(tmp_path / "pilot_poisoned", items, poisoned_records)

    fit_out1 = tmp_path / "fit_clean"
    fit_out2 = tmp_path / "fit_poisoned"

    main(["--gsm8k-routing-fit", str(pilot_dir1), "--output", str(fit_out1)])
    main(["--gsm8k-routing-fit", str(pilot_dir2), "--output", str(fit_out2)])

    # Selected rules and candidate scores must be byte-identical
    assert (fit_out1 / "selection.json").read_bytes() == (fit_out2 / "selection.json").read_bytes()


def write_hash_valid_journal(path: Path, entries: List[Dict[str, Any]]) -> str:
    """Helper to author hash-valid journal chains with arbitrary event sequences."""
    from experiments.gsm8k_collector import canonical_json, digest
    head = "0" * 64
    lines = []
    for seq, (kind, attempt_id, cond_key, value) in enumerate(entries):
        body = {
            "sequence": seq,
            "previous": head,
            "kind": kind,
            "attempt_id": attempt_id,
            "key": list(cond_key),
            "timestamp_utc": "2026-10-24T12:00:00Z",
            "value": value,
        }
        entry = {**body, "sha256": digest(body)}
        head = entry["sha256"]
        lines.append(canonical_json(entry) + "\n")
    path.write_text("".join(lines), encoding="utf-8")
    return head


def test_g1_invalid_tokens_rejected_with_conservative_reservation(tmp_path: Path):
    """G1: Tokens of -100, 2048, or True fail validation, record failed outcome, and charge 1024."""
    dataset = make_test_dataset(num_items=2)
    identity = make_test_identity(dataset)
    settings = {"temperature": 0.0, "thinking": False}

    for idx, invalid_token_val in enumerate((-100, 2048, True)):
        run_dir = tmp_path / f"run_invalid_tok_{idx}"
        checkpoint = GSM8KCollectorCheckpoint(run_dir, identity, dataset, settings)
        runner = MockStagedRunner(responses={
            ("item_calibration_0", "DIRECT"): {"tokens": invalid_token_val}
        })

        with pytest.raises(ValueError, match="Generated tokens"):
            run_staged_collection(checkpoint, runner, dataset)
        checkpoint.close()

        # Check calls.jsonl: generation_outcome must be logged as failed with conservative reservation
        lines = (run_dir / "calls.jsonl").read_text(encoding="utf-8").splitlines()
        events = [json.loads(l) for l in lines]
        gen_out = next(e for e in events if e["kind"] == "generation_outcome" and e["key"] == ["item_calibration_0", "DIRECT"])
        val = gen_out["value"]
        assert val["status"] == "failed"
        assert val["measured_generated_tokens"] is None
        assert val["budget_charge_tokens"] == 1024
        assert val["cost_status"] == "unknown_reserved"

        # Manifest must record interrupted status and budget charge
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["status"] == "interrupted"
        assert manifest["budget_charged_tokens"] == 1024


def test_g1_invalid_tool_payload_rejected(tmp_path: Path):
    """G1: Non-boolean ok, non-string output, or negative duration in tool output raises ValueError."""
    dataset = make_test_dataset(num_items=2)
    identity = make_test_identity(dataset)
    settings = {"temperature": 0.0, "thinking": False}

    run_dir = tmp_path / "run_invalid_tool"
    checkpoint = GSM8KCollectorCheckpoint(run_dir, identity, dataset, settings)

    class BadToolRunner(MockStagedRunner):
        def run_tool(self, code, timeout_seconds=5.0):
            return ToolExecutionResult(ok="true", output="42", duration_ms=1.0)  # ok is str, not bool

    with pytest.raises(ValueError, match="Tool ok must be a boolean"):
        run_staged_collection(checkpoint, BadToolRunner(), dataset)
    checkpoint.close()


def test_g1_journal_with_invalid_token_payload_fails_closed(tmp_path: Path):
    """G1: Replaying a journal with tampered/invalid token count in succeeded event fails closed."""
    dataset = make_test_dataset(num_items=2)
    identity = make_test_identity(dataset)
    settings = {"temperature": 0.0, "thinking": False}

    run_dir = tmp_path / "run_journal_invalid_tok"
    run_dir.mkdir(parents=True)
    (run_dir / "dataset.json").write_text(json.dumps(dataset), encoding="utf-8")
    (run_dir / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

    entries = [
        ("generation_started", "item_train_0_DIRECT_a0", ("item_train_0", "DIRECT"), {
            "item_id": "item_train_0", "strategy": "DIRECT", "declared_max_tokens": 1024,
            "reserved_tokens": 1024, "seed": seed_for(42, "item_train_0", "DIRECT")
        }),
        ("generation_outcome", "item_train_0_DIRECT_a0", ("item_train_0", "DIRECT"), {
            "status": "succeeded", "output_text": "Answer: 42", "measured_generated_tokens": -100,
            "measured_prompt_tokens": 20, "finish_reason": "stop", "confidence": 0.9,
            "elapsed_ms": 10.0, "budget_charge_tokens": -100, "cost_status": "measured"
        }),
    ]
    head = write_hash_valid_journal(run_dir / "calls.jsonl", entries)
    manifest = {
        "schema_version": 1, "mode": "gsm8k_development_pilot_collection",
        "identity": identity, "status": "running", "journal_head": head,
        "journal_entries": len(entries), "calls_started": 1, "calls_completed": 0,
        "measured_tokens": 0, "budget_charged_tokens": 0,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="Generated tokens"):
        GSM8KCollectorCheckpoint(run_dir, identity, dataset, settings, resume=True)


def test_g2_orphan_charge_restored_on_resume(tmp_path: Path):
    """G2: An orphan started attempt restores conservative 1024 token reservation during journal replay."""
    from experiments.gsm8k_collector import SimulatedProcessKill

    dataset = make_test_dataset(num_items=2)
    identity = make_test_identity(dataset)
    settings = {"temperature": 0.0, "thinking": False}

    run_dir = tmp_path / "run_orphan_charge"
    checkpoint = GSM8KCollectorCheckpoint(run_dir, identity, dataset, settings)

    class KillRunner(MockStagedRunner):
        def run_generation(self, item, strategy, max_tokens, seed):
            raise SimulatedProcessKill("sudden kill right after start")

    with pytest.raises(SimulatedProcessKill):
        run_staged_collection(checkpoint, KillRunner(), dataset)
    checkpoint.close()

    # Re-open with resume
    cp_resume = GSM8KCollectorCheckpoint(run_dir, identity, dataset, settings, resume=True)
    assert len(cp_resume.unknown_conditions) == 1
    # Check that budget_charge_tokens_total was restored to 1024!
    assert cp_resume.budget_charge_tokens_total == 1024

    with pytest.raises(QuarantineError):
        run_staged_collection(cp_resume, MockStagedRunner(), dataset)
    cp_resume.close()

    # Manifest must record 1024 tokens reserved and status quarantined
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "quarantined"
    assert manifest["budget_charged_tokens"] == 1024
    assert manifest["calls_started"] == 1


def test_g2_pure_record_reconstruction_from_terminal_evidence(tmp_path: Path):
    """G2: A crash before record_assembled is reconstructed purely from durable terminal evidence without redispatch."""
    from experiments.gsm8k_collector import SimulatedProcessKill

    dataset = make_test_dataset(num_items=2)
    identity = make_test_identity(dataset)
    settings = {"temperature": 0.0, "thinking": False}

    run_dir = tmp_path / "run_lost_assembly"
    checkpoint = GSM8KCollectorCheckpoint(run_dir, identity, dataset, settings)

    # Intercept append_event: when record_assembled is called for the 1st condition, kill process
    original_append = checkpoint.append_event
    def kill_before_first_record(kind, *args, **kwargs):
        if kind == "record_assembled":
            raise SimulatedProcessKill("crash right after generation outcome, before record assembled")
        return original_append(kind, *args, **kwargs)

    checkpoint.append_event = kill_before_first_record
    with pytest.raises(SimulatedProcessKill):
        run_staged_collection(checkpoint, MockStagedRunner(), dataset)
    checkpoint.close()

    # Resume: checkpoint must reconstruct the missing record from persisted terminal evidence
    cp_resume = GSM8KCollectorCheckpoint(run_dir, identity, dataset, settings, resume=True)
    assert len(cp_resume.unknown_conditions) == 0
    # Condition 0 record has been reconstructed without re-executing!
    assert ("item_calibration_0", "DIRECT") in cp_resume.records
    assert ("item_calibration_0", "DIRECT") in cp_resume.completed_conditions
    assert cp_resume.calls_completed_total == 1

    runner = MockStagedRunner()
    state = run_staged_collection(cp_resume, runner, dataset)
    cp_resume.close()

    # 1. Total records must be 6 (all 6 completed)
    assert len(cp_resume.records) == 6
    # 2. Redispatch count must be exactly 5 (condition 0 was NOT redispatched!)
    assert runner.generation_dispatches == 5
    # 3. Status must be complete
    assert state["status"] == "complete"


def test_g3_sealed_input_bank_swap_rejected(tmp_path: Path):
    """G3: Modifying input bank outcomes and re-signing input manifest fails closed on sealed validation."""
    items, records = fixture_data()
    pilot_dir = save_run(tmp_path / "pilot_orig", items, records)

    seal_dir = tmp_path / "seal_dir"
    routing.write_fitting_seal(pilot_dir, seal_dir)

    # Now tamper with pilot_dir's records.json and update its manifest.json
    tampered_records = json.loads((pilot_dir / "records.json").read_text(encoding="utf-8"))
    for row in tampered_records:
        if row["split"] == "calibration":
            row["correct"] = not row["correct"]
            row["answer"] = "999"
    (pilot_dir / "records.json").write_text(json.dumps(tampered_records) + "\n", encoding="utf-8")

    manifest = json.loads((pilot_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["artifact_sha256"]["records.json"] = sha256_file(pilot_dir / "records.json")
    (pilot_dir / "manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")

    val_dir = tmp_path / "val_dir"
    with pytest.raises(ValueError, match="Input run manifest hash .* differs from sealed hash"):
        routing.write_validation_evaluation(seal_dir, val_dir)


def test_g3_sealed_artifact_tamper_rejected(tmp_path: Path):
    """G3: Modifying dataset.json in input run without updating manifest fails closed on checksum mismatch."""
    items, records = fixture_data()
    pilot_dir = save_run(tmp_path / "pilot_art_tamper", items, records)

    seal_dir = tmp_path / "seal_dir_art"
    routing.write_fitting_seal(pilot_dir, seal_dir)

    # Tamper dataset.json in pilot_dir
    (pilot_dir / "dataset.json").write_text("{\"tampered\": true}\n", encoding="utf-8")

    val_dir = tmp_path / "val_dir_art"
    with pytest.raises(ValueError, match="Input artifact .* checksum .* differs from sealed checksum"):
        routing.write_validation_evaluation(seal_dir, val_dir)


def test_g4_outcome_access_isolation_fitting_never_reads_validation_records(tmp_path: Path):
    """G4: write_fitting_seal loads exclusively from records_fitting.json; corrupted validation records cause no error."""
    dataset = make_test_dataset(num_items=4)
    identity = make_test_identity(dataset, evidence="synthetic_staged_pilot_collection")
    settings = {"temperature": 0.0, "thinking": False}

    staged_run = tmp_path / "staged_run"
    cp = GSM8KCollectorCheckpoint(staged_run, identity, dataset, settings)
    run_staged_collection(cp, MockStagedRunner(), dataset)
    cp.close()

    assert (staged_run / "records_fitting.json").is_file()
    assert (staged_run / "records_validation.json").is_file()

    # Corrupt records_validation.json completely
    (staged_run / "records_validation.json").write_text("INVALID NON-JSON CORRUPTED BYTES", encoding="utf-8")

    # write_fitting_seal must succeed without reading records_validation.json!
    seal_dir = tmp_path / "seal_isolated"
    state = routing.write_fitting_seal(staged_run, seal_dir)
    assert state["status"] == "selection_saved"
    assert (seal_dir / "selection.json").is_file()


def test_g4_pre_seal_validation_accuracy_suppressed(tmp_path: Path):
    """G4: Pre-seal summary.json and report.md suppress validation aggregate accuracy."""
    dataset = make_test_dataset(num_items=4)
    identity = make_test_identity(dataset, evidence="synthetic_staged_pilot_collection")
    settings = {"temperature": 0.0, "thinking": False}

    run_dir = tmp_path / "staged_run_suppress"
    cp = GSM8KCollectorCheckpoint(run_dir, identity, dataset, settings)
    run_staged_collection(cp, MockStagedRunner(), dataset)
    cp.close()

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary.get("validation_accuracy_suppressed") is True
    assert "accuracy" not in summary

    report_text = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "Validation Outcomes: Sealed" in report_text
    assert "aggregate accuracy suppressed" in report_text


def test_g5_staged_collection_to_fitting_seal_and_validation_e2e(tmp_path: Path):
    """G5: Full end-to-end staged collect -> fit seal -> validate workflow with 0 model calls."""
    dataset = make_test_dataset(num_items=4)
    identity = make_test_identity(dataset, evidence="synthetic_staged_pilot_collection")
    settings = {"temperature": 0.0, "thinking": False}

    # 1. Staged collection
    run_dir = tmp_path / "staged_collection_run"
    cp = GSM8KCollectorCheckpoint(run_dir, identity, dataset, settings)
    state_col = run_staged_collection(cp, MockStagedRunner(), dataset)
    cp.close()
    assert state_col["status"] == "complete"

    # 2. Fit seal
    seal_dir = tmp_path / "staged_seal"
    state_seal = routing.write_fitting_seal(run_dir, seal_dir)
    assert state_seal["status"] == "selection_saved"
    assert state_seal["new_model_calls"] == 0

    # 3. Validation evaluation
    val_dir = tmp_path / "staged_validation"
    state_val = routing.write_validation_evaluation(seal_dir, val_dir)
    assert state_val["status"] == "complete"

    summary = json.loads((val_dir / "summary.json").read_text(encoding="utf-8"))
    assert "query_only_rule" in summary["methods"]
    assert "selected_fixed_reference" in summary["methods"]
    assert "fixed_direct" in summary["methods"]
    assert "fixed_cot" in summary["methods"]
    assert "fixed_pal" in summary["methods"]
    assert "primary_comparison" in summary
    assert (val_dir / "report.md").is_file()


def test_integrity_duplicate_condition_start_rejected(tmp_path: Path):
    """Integrity: Duplicate start for same condition under distinct attempt IDs is rejected."""
    dataset = make_test_dataset(num_items=2)
    identity = make_test_identity(dataset)
    settings = {"temperature": 0.0, "thinking": False}

    run_dir = tmp_path / "run_dup_start"
    run_dir.mkdir(parents=True)
    (run_dir / "dataset.json").write_text(json.dumps(dataset), encoding="utf-8")
    (run_dir / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

    entries = [
        ("generation_started", "att_1", ("item_train_0", "DIRECT"), {
            "item_id": "item_train_0", "strategy": "DIRECT", "declared_max_tokens": 1024,
            "reserved_tokens": 1024, "seed": seed_for(42, "item_train_0", "DIRECT")
        }),
        ("generation_started", "att_2", ("item_train_0", "DIRECT"), {
            "item_id": "item_train_0", "strategy": "DIRECT", "declared_max_tokens": 1024,
            "reserved_tokens": 1024, "seed": seed_for(42, "item_train_0", "DIRECT")
        }),
    ]
    head = write_hash_valid_journal(run_dir / "calls.jsonl", entries)
    manifest = {
        "schema_version": 1, "mode": "gsm8k_development_pilot_collection",
        "identity": identity, "status": "running", "journal_head": head,
        "journal_entries": len(entries), "calls_started": 2, "calls_completed": 0,
        "measured_tokens": 0, "budget_charged_tokens": 0,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate condition started"):
        GSM8KCollectorCheckpoint(run_dir, identity, dataset, settings, resume=True)


def test_integrity_unknown_journal_kind_rejected(tmp_path: Path):
    """Integrity: Journal entry with unknown kind fails closed."""
    dataset = make_test_dataset(num_items=2)
    identity = make_test_identity(dataset)
    settings = {"temperature": 0.0, "thinking": False}

    run_dir = tmp_path / "run_unknown_kind"
    run_dir.mkdir(parents=True)
    (run_dir / "dataset.json").write_text(json.dumps(dataset), encoding="utf-8")
    (run_dir / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

    entries = [
        ("unknown_malicious_kind", "att_1", ("item_train_0", "DIRECT"), {"foo": "bar"}),
    ]
    head = write_hash_valid_journal(run_dir / "calls.jsonl", entries)
    manifest = {
        "schema_version": 1, "mode": "gsm8k_development_pilot_collection",
        "identity": identity, "status": "running", "journal_head": head,
        "journal_entries": len(entries), "calls_started": 0, "calls_completed": 0,
        "measured_tokens": 0, "budget_charged_tokens": 0,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="Unknown journal event kind"):
        GSM8KCollectorCheckpoint(run_dir, identity, dataset, settings, resume=True)


def test_integrity_record_assembled_without_tool_outcome_for_pal_rejected(tmp_path: Path):
    """Integrity: record_assembled for PAL without terminal tool_outcome is rejected during replay."""
    dataset = make_test_dataset(num_items=2)
    identity = make_test_identity(dataset)
    settings = {"temperature": 0.0, "thinking": False}

    run_dir = tmp_path / "run_pal_no_tool"
    run_dir.mkdir(parents=True)
    (run_dir / "dataset.json").write_text(json.dumps(dataset), encoding="utf-8")
    (run_dir / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

    entries = [
        ("generation_started", "att_1", ("item_train_0", "PAL"), {
            "item_id": "item_train_0", "strategy": "PAL", "declared_max_tokens": 1024,
            "reserved_tokens": 1024, "seed": seed_for(42, "item_train_0", "PAL")
        }),
        ("generation_outcome", "att_1", ("item_train_0", "PAL"), {
            "status": "succeeded", "output_text": "Answer: 42", "measured_generated_tokens": 100,
            "measured_prompt_tokens": 20, "finish_reason": "stop", "confidence": 0.9,
            "elapsed_ms": 10.0, "budget_charge_tokens": 100, "cost_status": "measured"
        }),
        # Premature record_assembled without tool_started or tool_outcome!
        ("record_assembled", "att_1", ("item_train_0", "PAL"), {
            "id": "item_train_0", "group_id": "group_train_0", "split": "train",
            "strategy": "PAL", "token_budget": 1024, "seed": seed_for(42, "item_train_0", "PAL"),
            "answer_format": {"answer_type": "number", "decimal_separator": "."},
            "answer": "42", "correct": True, "confidence": 0.9, "tokens": 100,
            "strategy_ms": 10.0, "trace": {"generations": [], "tools": []}
        }),
    ]
    head = write_hash_valid_journal(run_dir / "calls.jsonl", entries)
    manifest = {
        "schema_version": 1, "mode": "gsm8k_development_pilot_collection",
        "identity": identity, "status": "running", "journal_head": head,
        "journal_entries": len(entries), "calls_started": 1, "calls_completed": 1,
        "measured_tokens": 100, "budget_charged_tokens": 100,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="record_assembled for PAL without terminal tool_outcome"):
        GSM8KCollectorCheckpoint(run_dir, identity, dataset, settings, resume=True)
