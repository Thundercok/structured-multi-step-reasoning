"""Addendum study: outcome-blind full-prefix continuation (q=1.0) under standard CoT prompt.

This module evaluates full-prefix continuation on the 12 canonical questions from
the completed Qwen3.5-4B development pilot (audit/cot_restart_pilot_qwen35_20261009).
It verifies historical artifacts and journal chain read-only, never modifies or
resumes in the historical directory, and compares full-prefix continuation directly
with historical restart arms at budget 2048 under standardized token accounting.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import resource
import sys
import time
from typing import Any
from experiments.cot_restart_replay import (
    CAP_SWEEP_SEED_POLICY, backend_runtime_identity, decoding_config, derive_cap_sweep_seed, encode_prompt,
)

from experiments.cot_restart_pilot import (
    ALIGNED_DIRECT_COT_SUFFIX_TEXT,
    BASE_MODEL,
    DEV_POOL_PATH,
    DEV_POOL_SHA256,
    MODEL_FILE_HASHES,
    MODEL_REPOSITORY,
    MODEL_REVISION,
    QUANTIZATION,
    MockLLM,
    PilotJournal,
    atomic_save_json,
    encoded_json,
    execute_llm_call,
    file_sha256,
    gen_check,
    get_memory_telemetry,
    get_runtime_versions,
    parse_answer_details,
    reasoning_prefix,
    resolve_and_verify_local_snapshot,
    source_hashes,
    text_sha256,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HISTORICAL_DIR = ROOT / "audit" / "cot_restart_pilot_qwen35_20261009"

# Addendum budget and caps
ADDENDUM_BUDGET = 2048
MAX_ADDENDUM_CALLS = 12
MAX_ADDENDUM_COMPLETION_TOKENS = 24_576
MAX_ADDENDUM_DURATION_SECONDS = 8 * 3600  # 8 hours (480 minutes)
SAMPLING_TEMPERATURE = 0.6
SAMPLING_TOP_P = 0.95


def verify_historical_run(historical_dir: Path) -> dict[str, Any]:
    """Verify integrity of completed historical pilot run read-only."""
    historical_dir = Path(historical_dir).resolve()
    if not historical_dir.exists() or not historical_dir.is_dir():
        raise ValueError(f"Historical run directory does not exist: {historical_dir}")

    manifest_file = historical_dir / "manifest.json"
    if not manifest_file.exists():
        raise ValueError(f"Historical manifest missing: {manifest_file}")

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("status") != "complete":
        raise ValueError(
            f"Historical run status is '{manifest.get('status')}', expected 'complete'. "
            "Addendum can only be executed on complete historical runs."
        )

    required_files = ("calls.jsonl", "dataset.json", "base_traces.json", "summary.json")
    for fname in required_files:
        fpath = historical_dir / fname
        if not fpath.exists():
            raise ValueError(f"Historical run missing required file: {fpath}")

    # Verify recorded artifact hashes
    recorded_hashes = manifest.get("artifact_hashes", {})
    for fname, exp_hash in recorded_hashes.items():
        fpath = historical_dir / fname
        if not fpath.exists():
            raise ValueError(f"Historical artifact recorded in manifest missing on disk: {fpath}")
        act_hash = file_sha256(fpath)
        if act_hash != exp_hash:
            raise ValueError(
                f"Historical artifact hash mismatch for {fname}: "
                f"actual={act_hash}, expected={exp_hash}. Directory may have been tampered with."
            )

    # Verify journal chain
    calls_file = historical_dir / "calls.jsonl"
    head = "0" * 64
    seq = 0
    lines = calls_file.read_text(encoding="utf-8").splitlines(keepends=True)
    if not lines:
        raise ValueError(f"Historical journal {calls_file} is empty")

    for line in lines:
        if not line.endswith("\n"):
            raise ValueError(f"Torn tail in historical journal {calls_file}")
        entry = json.loads(line)
        body = {k: v for k, v in entry.items() if k != "sha256"}
        if entry.get("sha256") != text_sha256(encoded_json(body)):
            raise ValueError(f"Corrupt journal entry checksum at sequence {seq} in {calls_file}")
        if body.get("previous") != head or body.get("sequence") != seq:
            raise ValueError(
                f"Journal sequence or previous pointer mismatch at sequence {seq} in {calls_file}"
            )
        head = entry["sha256"]
        seq += 1

    expected_head = manifest.get("journal_head")
    if expected_head and head != expected_head:
        raise ValueError(
            f"Historical journal head mismatch: computed={head}, recorded in manifest={expected_head}"
        )

    return manifest


def build_addendum_run_identity(
    mock: bool, historical_manifest: dict, historical_dir: Path
) -> dict[str, Any]:
    """Build immutable identity fingerprint for Addendum mode."""
    return {
        "schema_version": 1,
        "study": "cot_restart_addendum_qwen35",
        "role": "exposed_development_addendum",
        "mock": mock,
        "model_repository": "mock" if mock else MODEL_REPOSITORY,
        "model_revision": "mock" if mock else MODEL_REVISION,
        "quantization": None if mock else QUANTIZATION,
        "dev_pool_sha256": DEV_POOL_SHA256,
        "settings_sha256": text_sha256(
            encoded_json({
                "historical_run_dir": str(historical_dir.resolve()),
                "historical_journal_head": historical_manifest.get("journal_head"),
                "budget": ADDENDUM_BUDGET,
                "arm": "full_prefix_continuation",
                "temp": SAMPLING_TEMPERATURE,
                "top_p": SAMPLING_TOP_P,
                "seed_policy": CAP_SWEEP_SEED_POLICY,
                "token_record_version": 1,
                "backend_runtime": backend_runtime_identity(mock=mock),
                "decoding_config": decoding_config(SAMPLING_TEMPERATURE, SAMPLING_TOP_P),
            })
        ),
        "source_sha256": source_hashes(),
    }


def run_cot_restart_addendum(
    historical_dir: Path = DEFAULT_HISTORICAL_DIR,
    output_dir: Path | None = None,
    mock: bool = False,
) -> dict[str, Any]:
    """Execute read-only full-prefix continuation addendum on historical pilot base traces."""
    historical_dir = Path(historical_dir).resolve()
    if output_dir is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        output_dir = ROOT / "audit" / f"cot_restart_addendum_qwen35_{stamp}"
    output_dir = Path(output_dir).resolve()

    # Preflight Check 1: Output directory must NEVER be the historical directory
    if output_dir == historical_dir:
        raise ValueError(
            f"Output directory cannot be identical to historical run directory: {historical_dir}. "
            "Addendum must strictly write to an isolated new directory without modifying history."
        )

    # Preflight Check 2: Verify historical run artifacts and journal chain read-only
    historical_manifest = verify_historical_run(historical_dir)

    # Load 12 canonical questions and base visible CoT traces
    dataset = json.loads((historical_dir / "dataset.json").read_text(encoding="utf-8"))
    items = dataset.get("items", [])
    if len(items) != 12:
        raise ValueError(f"Expected 12 canonical questions in historical dataset, got {len(items)}")

    base_traces = json.loads((historical_dir / "base_traces.json").read_text(encoding="utf-8"))
    for it in items:
        if it["id"] not in base_traces:
            raise ValueError(f"Question {it['id']} missing from historical base traces")

    historical_summary = json.loads((historical_dir / "summary.json").read_text(encoding="utf-8"))

    output_dir.mkdir(parents=True, exist_ok=True)
    expected_identity = build_addendum_run_identity(mock, historical_manifest, historical_dir)

    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {
            "schema_version": 1,
            "study": "cot_restart_addendum_qwen35",
            "role": "exposed_development_addendum",
            "identity": expected_identity,
            "historical_run_dir": str(historical_dir),
            "historical_journal_head": historical_manifest.get("journal_head"),
            "model_repository": "mock" if mock else MODEL_REPOSITORY,
            "model_revision": "mock" if mock else MODEL_REVISION,
            "base_model": BASE_MODEL,
            "quantization": None if mock else QUANTIZATION,
            "model_hashes": MODEL_FILE_HASHES if not mock else {},
            "dev_pool_sha256": DEV_POOL_SHA256,
            "source_hashes": source_hashes(),
            "python": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "status": "running",
            "mock": mock,
            "confirmatory": False,
            "publication_review_required": True,
            "safety_limits": {
                "max_calls": MAX_ADDENDUM_CALLS,
                "max_completion_tokens": MAX_ADDENDUM_COMPLETION_TOKENS,
                "max_duration_seconds": MAX_ADDENDUM_DURATION_SECONDS,
            },
        }

    journal = PilotJournal(output_dir, manifest, expected_identity=expected_identity)
    started_time = time.perf_counter()

    try:
        # Load backend (mock strictly never imports MLX)
        if mock:
            model = MockLLM()
            tokenizer = model.tokenizer
            manifest["local_model_path"] = "mock"
            manifest["runtime_versions"] = get_runtime_versions()
        else:
            snapshot_path = resolve_and_verify_local_snapshot()
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            from mlx_lm import load as mlx_load
            model, tokenizer = mlx_load(str(snapshot_path))
            manifest["local_model_path"] = str(snapshot_path)
            manifest["runtime_versions"] = get_runtime_versions()

        addendum_records = []
        for it in items:
            qid = it["id"]
            base = base_traces[qid]
            call_key = [qid, "full_prefix_continuation", str(ADDENDUM_BUDGET)]

            if journal.has("addendum_call", *call_key):
                res = journal.get("addendum_call", *call_key)
            else:
                # Check safety limits
                if journal.executed_model_calls >= MAX_ADDENDUM_CALLS:
                    raise RuntimeError(
                        f"Safety limit reached: executed calls {journal.executed_model_calls} >= {MAX_ADDENDUM_CALLS}"
                    )
                if journal.total_completion_tokens >= MAX_ADDENDUM_COMPLETION_TOKENS:
                    raise RuntimeError(
                        f"Safety limit reached: completion tokens {journal.total_completion_tokens} >= {MAX_ADDENDUM_COMPLETION_TOKENS}"
                    )
                if (time.perf_counter() - started_time) >= MAX_ADDENDUM_DURATION_SECONDS:
                    raise RuntimeError(
                        f"Safety limit reached: duration >= {MAX_ADDENDUM_DURATION_SECONDS}s"
                    )

                raw_trace = base["raw_output"]
                prefix_body, _, _ = reasoning_prefix(raw_trace)
                cot_suffix = ALIGNED_DIRECT_COT_SUFFIX_TEXT["COT"]

                msgs = [
                    {"role": "user", "content": it["query"] + cot_suffix},
                    {"role": "assistant", "content": prefix_body},
                ]
                prompt = tokenizer.apply_chat_template(
                    msgs,
                    tokenize=False,
                    add_generation_prompt=False,
                    enable_thinking=False,
                    continue_final_message=True,
                )

                p_tok = len(encode_prompt(tokenizer, prompt))
                comp_cap = ADDENDUM_BUDGET - p_tok

                if comp_cap <= 0:
                    res = {
                        "executed_call": False,
                        "skipped": True,
                        "skip_reason": "budget_infeasible",
                        "budget_infeasible": True,
                        "prompt": prompt,
                        "prompt_tokens_required": p_tok,
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
                else:
                    seed = derive_cap_sweep_seed(42, qid, "full_prefix_continuation")
                    journal.record_call_started("addendum_call", call_key, prompt, p_tok)
                    captured = {}
                    out_text, comp_tok, finish, dur_ms = execute_llm_call(
                        model,
                        tokenizer,
                        prompt,
                        max_tokens=comp_cap,
                        temp=SAMPLING_TEMPERATURE,
                        seed=seed,
                        is_mock=mock,
                        is_thinking=False,
                        capture=captured,
                    )
                    full_response = prefix_body + out_text
                    family = it["family"]
                    ans_type = "expression" if family == "g24" else "text" if family == "order" else "number"
                    parsed, status, wordy = parse_answer_details(full_response, answer_type=ans_type)
                    correct = bool(gen_check(it, parsed)) if parsed is not None else False

                    res = {
                        "executed_call": True,
                        "skipped": False,
                        "skip_reason": None,
                        "budget_infeasible": False,
                        "prompt": prompt,
                        "prompt_tokens_required": p_tok,
                        "incurred_prompt_tokens": p_tok,
                        "prompt_tokens": p_tok,
                        "completion_cap": comp_cap,
                        "raw_output": out_text,
                        "full_response": full_response,
                        "completion_tokens": comp_tok,
                        "total_tokens": p_tok + comp_tok,
                        "finish_reason": finish,
                        "parsed_answer": parsed,
                        "parse_status": status,
                        "wordy": wordy,
                        "correct": correct,
                        "duration_ms": round(dur_ms, 2),
                        "memory": get_memory_telemetry(mock=mock),
                        **captured,
                        "seed_policy": CAP_SWEEP_SEED_POLICY,
                    }
                journal.append("addendum_call", call_key, res)

            addendum_records.append({
                "question_id": qid,
                "family": it["family"],
                "arm": "full_prefix_continuation",
                "budget": ADDENDUM_BUDGET,
                "prefix_body_chars": len(prefix_body) if 'prefix_body' in locals() else len(reasoning_prefix(base["raw_output"])[0]),
                "base_correct": base["correct"],
                "base_finish_reason": base.get("finish_reason"),
                "base_parse_status": base.get("parse_status"),
                **res,
            })

        atomic_save_json(output_dir / "addendum_records.json", addendum_records)

        # Load historical records if present to compute accurate historical e2e token costs
        hist_records_file = historical_dir / "restart_records.json"
        historical_records = (
            json.loads(hist_records_file.read_text(encoding="utf-8"))
            if hist_records_file.exists()
            else None
        )

        # Compute summary and comparative statistics
        summary = generate_addendum_summary(
            items=items,
            base_traces=base_traces,
            addendum_records=addendum_records,
            journal=journal,
            historical_summary=historical_summary,
            historical_records=historical_records,
        )
        atomic_save_json(output_dir / "summary.json", summary)

        # Render report and Codex summary
        report_md = render_addendum_report(manifest, summary, addendum_records, base_traces)
        (output_dir / "report.md").write_text(report_md, encoding="utf-8")

        codex_report = render_addendum_result_for_codex(manifest, summary, output_dir)
        (output_dir / "RESULT_FOR_CODEX.md").write_text(codex_report, encoding="utf-8")

        journal.manifest["status"] = "complete"
        journal.manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
        journal.manifest["artifact_hashes"] = {
            p.name: file_sha256(p)
            for p in sorted(output_dir.iterdir())
            if p.is_file() and p.name != "manifest.json" and not p.name.startswith(".")
        }
        manifest.update(journal.manifest)
        journal.save_manifest()
        journal.close()

        return {
            "status": "complete",
            "summary": summary,
            "output_dir": str(output_dir),
            "manifest": manifest,
        }

    except Exception as e:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(e).__name__}: {str(e)}"
        if journal.in_flight_call is not None:
            manifest["in_flight_call"] = journal.in_flight_call
        manifest["total_attempted_calls"] = journal.total_attempted_calls
        manifest["failed_attempts"] = journal.failed_attempts
        manifest["executed_model_calls"] = journal.executed_model_calls
        manifest["total_completion_tokens"] = journal.total_completion_tokens
        manifest["total_incurred_prompt_tokens"] = journal.total_incurred_prompt_tokens
        manifest["total_incurred_tokens"] = journal.total_incurred_tokens
        manifest["cost_status"] = (
            "unknown_incurred"
            if (journal.failed_attempts > 0 or journal.cost_status == "unknown_incurred")
            else ("known_incurred" if journal.executed_model_calls > 0 else "zero_incurred")
        )
        journal.manifest.update(manifest)
        journal.save_manifest()
        journal.close()
        raise


def generate_addendum_summary(
    items: list[dict],
    base_traces: dict[str, dict],
    addendum_records: list[dict],
    journal: PilotJournal,
    historical_summary: dict,
    historical_records: list[dict] | None = None,
) -> dict[str, Any]:
    """Compute addendum metrics and direct comparison with historical arms at budget 2048."""
    n_questions = len(items)
    base_correct_count = sum(1 for b in base_traces.values() if b["correct"])
    base_wrong_count = n_questions - base_correct_count

    total = len(addendum_records)
    correct = sum(1 for r in addendum_records if r.get("correct", False))
    accuracy = correct / total if total else 0.0

    rescued = sum(1 for r in addendum_records if not r["base_correct"] and r.get("correct", False))
    harmed = sum(1 for r in addendum_records if r["base_correct"] and not r.get("correct", False))

    rescue_rate = (rescued / base_wrong_count) if base_wrong_count > 0 else 0.0
    harm_rate = (harmed / base_correct_count) if base_correct_count > 0 else 0.0

    truncations = sum(1 for r in addendum_records if r.get("finish_reason") == "length")
    infeasible = sum(1 for r in addendum_records if r.get("budget_infeasible", False))
    format_failures = sum(
        1 for r in addendum_records if r.get("parse_status") != "marker" and not r.get("budget_infeasible", False)
    )

    # Token accounting
    mean_prompt = sum(r.get("prompt_tokens", 0) for r in addendum_records) / total if total else 0.0
    mean_comp = sum(r.get("completion_tokens", 0) for r in addendum_records) / total if total else 0.0
    mean_total = sum(r.get("total_tokens", 0) for r in addendum_records) / total if total else 0.0

    # End-to-end policy path tokens
    e2e_totals = [
        base_traces[r["question_id"]]["total_tokens"] + r.get("total_tokens", 0)
        for r in addendum_records
    ]
    mean_e2e_total = sum(e2e_totals) / len(e2e_totals) if e2e_totals else 0.0

    # Historical regenerate reference at budget 2048
    mean_base_total = sum(b.get("total_tokens", 0) for b in base_traces.values()) / n_questions if n_questions else 0.0
    hist_cells = historical_summary.get("cells", {})
    hist_regen = hist_cells.get("regenerate_b2048", {})
    hist_regen_e2e = hist_regen.get("mean_e2e_total_tokens")
    if hist_regen_e2e is None:
        if historical_records:
            regen_rows = [r for r in historical_records if r.get("arm") == "regenerate" and r.get("budget") == ADDENDUM_BUDGET]
            if regen_rows:
                e2e_list = [base_traces[r["question_id"]]["total_tokens"] + r.get("total_tokens", 0) for r in regen_rows]
                hist_regen_e2e = sum(e2e_list) / len(e2e_list)
        if hist_regen_e2e is None:
            hist_regen_e2e = hist_regen.get("mean_total_tokens", 0.0) + mean_base_total

    savings_vs_regen = (
        ((hist_regen_e2e - mean_e2e_total) / hist_regen_e2e * 100.0)
        if hist_regen_e2e > 0.0
        else 0.0
    )

    full_prefix_cell = {
        "arm": "full_prefix_continuation",
        "budget": ADDENDUM_BUDGET,
        "items": total,
        "correct": correct,
        "accuracy": round(accuracy, 4),
        "initially_wrong_denominator": base_wrong_count,
        "rescued": rescued,
        "rescue_rate": round(rescue_rate, 4),
        "initially_correct_denominator": base_correct_count,
        "harmed": harmed,
        "harm_rate": round(harm_rate, 4),
        "truncations": truncations,
        "budget_infeasible": infeasible,
        "format_failures": format_failures,
        "mean_intervention_prompt_tokens": round(mean_prompt, 1),
        "mean_intervention_completion_tokens": round(mean_comp, 1),
        "mean_intervention_total_tokens": round(mean_total, 1),
        "mean_e2e_total_tokens": round(mean_e2e_total, 1),
        "path_savings_vs_regenerate_pct": round(savings_vs_regen, 1),
    }

    # Per-item observation tracking: observe single-draw outcomes under full-prefix continuation
    per_item_diagnostics = []
    for r in addendum_records:
        qid = r["question_id"]
        b = base_traces[qid]
        item_diag = {
            "question_id": qid,
            "family": r["family"],
            "base_correct": b["correct"],
            "base_finish_reason": b.get("finish_reason"),
            "base_parse_status": b.get("parse_status"),
            "full_prefix_continuation_correct": r.get("correct", False),
            "full_prefix_continuation_finish": r.get("finish_reason"),
            "full_prefix_continuation_parse": r.get("parse_status"),
        }
        per_item_diagnostics.append(item_diag)

    # Comparative view with historical arms at budget 2048
    comparative_arms_b2048 = {}
    for arm_name in ("regenerate", "restart_q025", "restart_q050", "restart_q075", "thinking_native"):
        c_key = f"{arm_name}_b2048"
        if c_key in hist_cells:
            c_dict = dict(hist_cells[c_key])
            if "mean_e2e_total_tokens" not in c_dict:
                if historical_records and arm_name != "thinking_native":
                    arm_rows = [r for r in historical_records if r.get("arm") == arm_name and r.get("budget") == ADDENDUM_BUDGET]
                    if arm_rows:
                        e2e_list = [base_traces[r["question_id"]]["total_tokens"] + r.get("total_tokens", 0) for r in arm_rows]
                        c_dict["mean_e2e_total_tokens"] = round(sum(e2e_list) / len(e2e_list), 1)
                    else:
                        c_dict["mean_e2e_total_tokens"] = round(c_dict.get("mean_total_tokens", 0.0) + mean_base_total, 1)
                elif arm_name == "thinking_native":
                    c_dict["mean_e2e_total_tokens"] = round(c_dict.get("mean_total_tokens", 0.0), 1)
                else:
                    c_dict["mean_e2e_total_tokens"] = round(c_dict.get("mean_total_tokens", 0.0) + mean_base_total, 1)
            if "path_savings_vs_regenerate_pct" not in c_dict:
                if arm_name == "thinking_native":
                    c_dict["path_savings_vs_regenerate_pct"] = 0.0
                elif hist_regen_e2e > 0:
                    c_dict["path_savings_vs_regenerate_pct"] = round(
                        (hist_regen_e2e - c_dict["mean_e2e_total_tokens"]) / hist_regen_e2e * 100.0, 1
                    )
                else:
                    c_dict["path_savings_vs_regenerate_pct"] = 0.0
            comparative_arms_b2048[c_key] = c_dict
    comparative_arms_b2048["full_prefix_continuation_b2048"] = full_prefix_cell

    return {
        "dataset_items": n_questions,
        "base_cot_accuracy": round(base_correct_count / n_questions, 4) if n_questions else 0.0,
        "base_initially_correct": base_correct_count,
        "base_initially_wrong": base_wrong_count,
        "collection_cost": {
            "journal_records": journal.count,
            "executed_model_calls": journal.executed_model_calls,
            "skipped_calls": journal.skipped_calls,
            "total_model_calls": journal.executed_model_calls,
            "total_completion_tokens": journal.total_completion_tokens,
            "total_incurred_prompt_tokens": journal.total_incurred_prompt_tokens,
            "total_incurred_tokens": journal.total_incurred_tokens,
        },
        "full_prefix_continuation": full_prefix_cell,
        "comparative_budget_2048": comparative_arms_b2048,
        "per_item_diagnostics": per_item_diagnostics,
    }


def render_addendum_report(
    manifest: dict,
    summary: dict,
    records: list[dict],
    base_traces: dict[str, dict],
) -> str:
    """Render comprehensive addendum audit report."""
    lines = [
        "# CoT Restart Addendum Report: Full-Prefix Continuation (Qwen3.5-4B)",
        "",
        "> [!IMPORTANT]",
        "> **Read-Only Addendum on Frozen Development Artifacts**: This addendum executes exclusively",
        "> `full_prefix_continuation` (q=1.0 uncut rationale prefill) across the 12 canonical questions from",
        "> the historical development pilot. It tests whether restart rescue is driven by completing truncated/unformatted",
        "> solutions versus revising faulty reasoning steps under the standard CoT prompt.",
        "",
        "## Run Metadata & Historical Link",
        f"- **Historical Run Directory**: `{manifest.get('historical_run_dir')}`",
        f"- **Historical Journal Head**: `{manifest.get('historical_journal_head')}`",
        f"- **Model**: `{manifest.get('model_repository')}` (revision `{manifest.get('model_revision')}`)",
        f"- **Platform**: `{manifest.get('platform')}` ({manifest.get('machine')})",
        f"- **Executed Calls**: {summary['collection_cost']['executed_model_calls']}",
        f"- **Completion Tokens**: {summary['collection_cost']['total_completion_tokens']}",
        "",
        "## Direct Comparison: Historical Arms vs. Full-Prefix Continuation (Budget 2048)",
        "",
        "| Arm / Policy | Budget | Accuracy | Rescue (den={}) | Harm (den={}) | Trunc | Call Total Tok | End-to-End Path Tok | Path Savings vs Regen |".format(
            summary["base_initially_wrong"], summary["base_initially_correct"]
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for arm_key, c in sorted(summary["comparative_budget_2048"].items()):
        acc_pct = f"{c['accuracy'] * 100:.1f}%"
        res_str = f"{c['rescued']}/{c['initially_wrong_denominator']} ({c['rescue_rate']*100:.1f}%)"
        harm_str = f"{c['harmed']}/{c['initially_correct_denominator']} ({c['harm_rate']*100:.1f}%)"
        call_tok = c.get("mean_intervention_total_tokens", c.get("mean_total_tokens", 0.0))
        e2e_tok = c.get("mean_e2e_total_tokens", 0.0)
        sav_pct = f"{c['path_savings_vs_regenerate_pct']:+.1f}%" if c['arm'] != 'thinking_native' else "N/A"
        lines.append(
            f"| `{c['arm']}` | {c['budget']} | {acc_pct} | {res_str} | {harm_str} | "
            f"{c['truncations']} | {call_tok:.0f} | {e2e_tok:.0f} | {sav_pct} |"
        )

    lines.extend([
        "",
        "## Per-Item Diagnostic Analysis (Observed Single-Draw Transitions)",
        "",
        "| Question ID | Family | Base Correct | Base Finish | Full-Prefix Correct | Full-Prefix Finish | Observed Transition (Single Draw) |",
        "| --- | --- | ---: | --- | ---: | --- | --- |",
    ])

    for diag in summary.get("per_item_diagnostics", []):
        qid = diag["question_id"]
        fam = diag["family"]
        base_c = "Yes" if diag["base_correct"] else "No"
        base_f = diag["base_finish_reason"] or "N/A"
        fp_c = "Yes" if diag["full_prefix_continuation_correct"] else "No"
        fp_f = diag["full_prefix_continuation_finish"] or "N/A"

        # Observed single-draw outcome transition (mechanism requires qualitative trace inspection)
        if not diag["base_correct"] and diag["full_prefix_continuation_correct"]:
            finding = "Observed transition: wrong -> correct"
        elif not diag["base_correct"] and not diag["full_prefix_continuation_correct"]:
            finding = "Observed transition: wrong -> wrong (unresolved)"
        elif diag["base_correct"] and not diag["full_prefix_continuation_correct"]:
            finding = "Observed transition: correct -> wrong (degraded)"
        else:
            finding = "Observed transition: correct -> correct (retained)"

        lines.append(
            f"| `{qid}` | {fam} | {base_c} | `{base_f}` | {fp_c} | `{fp_f}` | {finding} |"
        )

    lines.extend([
        "",
        "## Protocol Status & Methodological Notes",
        "- Single-draw exploratory observation on exposed development pool (q=1.0 prefix continuation).",
        "- Observed outcome transitions do NOT establish causal cognitive mechanisms on their own; whether an individual transition reflects formatting completion, continuing latent reasoning, or chance requires qualitative trace inspection across multiple draws.",
        "- Mechanism classification remains undetermined without verified multi-draw trace analysis.",
        "- Full confirmatory runs and multi-draw replication remain on hold pending review.",
    ])
    return "\n".join(lines) + "\n"


def render_addendum_result_for_codex(manifest: dict, summary: dict, output_dir: Path) -> str:
    """Render executive summary for Codex/review."""
    fp = summary["full_prefix_continuation"]
    lines = [
        "# Research Study Checkpoint: CoT Restart Addendum (Qwen3.5-4B)",
        "",
        "## Run Metadata",
        f"- **Execution Date**: {manifest.get('started_utc')}",
        f"- **Status**: `{manifest.get('status')}`",
        f"- **Artifact Directory**: `{output_dir.resolve()}`",
        f"- **Model**: `{manifest.get('model_repository')}` (revision `{str(manifest.get('model_revision'))[:10]}`)",
        f"- **Runtime**: macOS Apple Silicon 16 GB, MLX 4-bit affine",
        "",
        "## Comparative Arm Outcomes at Budget 2048",
        "",
        "| Arm | Budget | Accuracy | Rescued | Harmed | Trunc | Call Total Tok | End-to-End Path Tok | Path Savings vs Regen |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm_key, c in sorted(summary["comparative_budget_2048"].items()):
        sav_str = f"{c['path_savings_vs_regenerate_pct']:+.1f}%" if c['arm'] != 'thinking_native' else "N/A"
        call_tok = c.get("mean_intervention_total_tokens", c.get("mean_total_tokens", 0.0))
        lines.append(
            f"| `{c['arm']}` | {c['budget']} | {c['accuracy']*100:.1f}% | "
            f"{c['rescued']}/{c['initially_wrong_denominator']} | "
            f"{c['harmed']}/{c['initially_correct_denominator']} | "
            f"{c['truncations']} | {call_tok:.0f} | {c['mean_e2e_total_tokens']:.0f} | {sav_str} |"
        )

    lines.extend([
        "",
        "## Key Invariants Verified",
        "1. Historical run verified read-only: manifest artifact hashes and journal chain fully checked.",
        "2. Zero modification of historical directory: output strictly written to isolated addendum directory.",
        "3. Continuation performed under standard CoT prompt with continue_final_message=True.",
        "4. Cost accounting includes initial base CoT burden for true policy path comparison.",
        "5. Mechanism determination caveats: single-draw transitions reported strictly observationally; causal cognitive mechanism requires multi-draw qualitative trace analysis.",
    ])
    return "\n".join(lines) + "\n"
