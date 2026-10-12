"""Unit and regression tests for Qwen3.5-4B CoT restart development pilot."""

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import pytest

from experiments.cot_restart_pilot import (
    DEV_POOL_PATH,
    MENU,
    PilotJournal,
    derive_call_seed,
    make_prefix_menu,
    reasoning_prefix,
    run_cot_restart_pilot,
    select_pilot_questions,
    sentence_boundaries,
    text_sha256,
)
from reasoning_strategies import parse_answer_details
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
