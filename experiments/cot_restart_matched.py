"""Prepare/review a bounded A/F/CONT development batch, then execute its plan.

Preparation uses a local tokenizer only. Real execution requires approval of
the exact prepared plan; synthetic execution never imports MLX or loads weights.
"""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path
import sys
import time
from datetime import datetime, timezone

from experiments.cot_restart_addendum import DEFAULT_HISTORICAL_DIR, verify_historical_run
from experiments.cot_restart_pilot import (
    ROOT, MODEL_REPOSITORY, MODEL_REVISION, MODEL_FILE_HASHES, QUANTIZATION,
    DEV_POOL_SHA256, ALIGNED_DIRECT_COT_SUFFIX_TEXT, MockLLM, PilotJournal,
    atomic_save_json, encoded_json, execute_llm_call, file_sha256,
    reasoning_prefix, resolve_and_verify_local_snapshot, source_hashes, text_sha256,
)
from experiments.cot_restart_replay import (
    CAP_SWEEP_SEED_POLICY, backend_runtime_identity, decoding_config,
    derive_cap_sweep_seed, encode_prompt,
)

ARMS = ("A", "F", "CONT")
POLICY_BUDGET = 2048
T_STAR = 2560
OFFSETS = (-8, 0, 8)
MAX_SECONDS = 8 * 3600
HISTORICAL_HEAD = "b8e0df5bdbaa7ce76ae27ef98f53f1ac486ead6c1406596453d5da56882e7dd0"
HISTORICAL_HASHES = {
    "dataset.json": "bc7c3ff389fa0fb217627cef44de2327c8c8df47c9b3b6c7db361ae1502fe109",
    "base_traces.json": "b84972d97af7f24eaa434012438b603fb87cc7ebc8f3ecb7bfb85b79b48202d5",
}


def verify_matched_history(directory: Path) -> dict:
    manifest = verify_historical_run(directory)
    if manifest["journal_head"] != HISTORICAL_HEAD or any(
        file_sha256(directory / name) != digest for name, digest in HISTORICAL_HASHES.items()
    ):
        raise ValueError("matched study accepts only the pinned 12-question exposed historical pilot")
    return manifest


def matched_source_hashes() -> dict:
    return {**source_hashes(), **{
        name: file_sha256(ROOT / name) for name in (
            "experiments/cot_restart_matched.py",
            "docs/cot_restart_matched_protocol_20261013.md",
        )
    }}


def build_plan(items: list[dict], bases: dict, tokenizer, *, q_star: float = .5) -> dict:
    """Budget from prompts/base counts only; correctness/gold never select caps."""
    if q_star not in (.25, .5, .75):
        raise ValueError("q_star must be one fixed interior menu point")
    requests, coverage = [], []
    for item in items:
        base = bases[item["id"]]
        body = reasoning_prefix(base["raw_output"])[0]
        menu = next(m for m in base["prefix_menu"] if m["q_requested"] == q_star)
        prefix = menu["prefix"]
        if not body.startswith(prefix) or menu["prefix_sha256"] != text_sha256(prefix):
            raise ValueError("historical F prefix does not match its base trace")
        per_item = []
        for arm, retained in (("A", ""), ("F", prefix), ("CONT", body)):
            messages = [{"role": "user", "content": item["query"] + ALIGNED_DIRECT_COT_SUFFIX_TEXT["COT"]}]
            if retained:
                messages.append({"role": "assistant", "content": retained})
            prompt = tokenizer.apply_chat_template(
                messages, tokenize=False, enable_thinking=False,
                continue_final_message=bool(retained), add_generation_prompt=not bool(retained),
            )
            prompt_ids = encode_prompt(tokenizer, prompt)
            per_item.append({
                "question_id": item["id"], "family": item["family"], "arm": arm,
                "prefix_text": retained, "prompt": prompt, "prompt_token_ids": prompt_ids,
                "prompt_tokens": len(prompt_ids), "seed": derive_cap_sweep_seed(42, item["id"], arm),
                "q_requested": {"A": 0.0, "F": q_star, "CONT": 1.0}[arm],
                "q_actual": menu["q_actual"] if arm == "F" else float(arm == "CONT"),
                "base_prompt_tokens": base["prompt_tokens"],
                "base_completion_tokens": base["completion_tokens"],
            })
        L = POLICY_BUDGET - per_item[2]["prompt_tokens"]
        if L < 8:
            raise ValueError("CONT prompt leaves insufficient room for M +/-8")
        for request in per_item:
            D = {str(w): T_STAR - base["completion_tokens"]
                 - w * (base["prompt_tokens"] + request["prompt_tokens"]) for w in (0, 1)}
            if min(D.values()) < 1:
                raise ValueError("T* does not leave a positive completion allowance in every arm")
            request.update({"M_cap": L, "D_caps": D,
                            "completion_cap": max(L + max(OFFSETS), *D.values())})
        requests.extend(per_item)
        coverage.append({
            "question_id": item["id"], "M_cap": L,
            "distinct_prompts": len({r["prompt"] for r in per_item}),
            "all_sensitivity_caps_available": True,
        })
    if len(items) != 12 or len({i["id"] for i in items}) != 12:
        raise ValueError("the matched plan requires all 12 unique historical questions")
    prompt_total = sum(r["prompt_tokens"] for r in requests)
    completion_total = sum(r["completion_cap"] for r in requests)
    minimal_w1 = max(r["base_completion_tokens"] + r["base_prompt_tokens"]
                     + r["prompt_tokens"] + 1 for r in requests)
    return {
        "schema_version": 1, "study": "cot_restart_matched_development",
        "status": "prepared_pending_budget_approval", "confirmatory": False,
        "stage_0_changed": False, "decision_states_enabled": False,
        "q_star": q_star, "q_star_selection": "user_fixed_menu_point; not fitted or optimal",
        "W": POLICY_BUDGET, "T_star": T_STAR,
        "T_star_rationale": "next 256-token grid point above the all-cell w=1 feasibility floor",
        "T_star_feasibility_floor_w1": minimal_w1,
        "M_offsets": list(OFFSETS), "D_prompt_weights": [0, 1],
        "seed_policy": CAP_SWEEP_SEED_POLICY, "base_seed": 42, "draws_per_cell": 1,
        "decoding_config": decoding_config(.6, .95),
        "base_cost_scope": "historical logged counts; EOS convention unverified",
        "collection_cost_excludes_historical_base_calls": True,
        "limits": {
            "max_attempted_calls": len(requests), "max_completion_tokens": completion_total,
            "max_prompt_tokens": prompt_total, "max_prompt_plus_completion_tokens": prompt_total + completion_total,
            "max_per_call_prompt_plus_completion_tokens": max(r["prompt_tokens"] + r["completion_cap"] for r in requests),
            "active_seconds_before_new_call_is_refused": MAX_SECONDS,
        },
        "coverage": coverage, "requests": requests,
    }


def prepare_plan(output: Path, historical: Path = DEFAULT_HISTORICAL_DIR, *, q_star: float = .5,
                 tokenizer=None) -> dict:
    output, historical = Path(output).resolve(), Path(historical).resolve()
    if output.exists() or output.is_relative_to(historical):
        raise ValueError("use a new plan directory outside historical artifacts")
    hist_manifest = verify_matched_history(historical)
    synthetic = tokenizer is not None
    snapshot = Path.home() / ".cache/huggingface/hub/models--mlx-community--Qwen3.5-4B-MLX-4bit/snapshots" / MODEL_REVISION
    if tokenizer is None:
        for name in ("tokenizer.json", "tokenizer_config.json"):
            if file_sha256(snapshot / name) != MODEL_FILE_HASHES[name]:
                raise ValueError(f"pinned tokenizer hash mismatch: {name}")
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(str(snapshot), local_files_only=True, trust_remote_code=False)
    items = json.loads((historical / "dataset.json").read_text())["items"]
    bases = json.loads((historical / "base_traces.json").read_text())
    plan = build_plan(items, bases, tokenizer, q_star=q_star)
    plan.update({
        "evidence": "synthetic_preparation" if synthetic else "tokenizer_only_development_preparation",
        "historical_dir": str(historical), "historical_journal_head": hist_manifest["journal_head"],
        "historical_dataset_sha256": file_sha256(historical / "dataset.json"),
        "model_repository": MODEL_REPOSITORY, "model_revision": MODEL_REVISION,
        "model_file_hashes": MODEL_FILE_HASHES, "local_model_path": str(snapshot),
        "backend_runtime": backend_runtime_identity(mock=synthetic),
        "python": sys.version, "platform": platform.platform(),
        "source_sha256": matched_source_hashes(),
    })
    plan["plan_sha256"] = text_sha256(encoded_json(plan))
    output.mkdir(parents=True, exist_ok=False)
    atomic_save_json(output / "plan.json", plan)
    limits = plan["limits"]
    lines = ["# Proposed A/F/CONT development batch", "",
             "Prepared with a tokenizer only; real generation remains pending explicit budget approval.", "",
             f"- Same 12 exposed-development questions; F fixed by the user at q={q_star:.2f}.",
             f"- {limits['max_attempted_calls']} attempted calls, one fresh draw per item/arm; no new base calls.",
             f"- Completion ceiling: {limits['max_completion_tokens']:,} sampled tokens including EOS.",
             f"- Second-prompt tokens: {limits['max_prompt_tokens']:,}; total ceiling: {limits['max_prompt_plus_completion_tokens']:,}.",
             f"- Largest per-call prompt+completion allowance: {limits['max_per_call_prompt_plus_completion_tokens']:,} tokens.",
             "- Refuse new calls after 8 hours of active collection; failed attempts consume the 36-call allowance.",
             f"- M uses W={POLICY_BUDGET}, per-item L_i and offsets -8/0/+8; every required cap is collected.",
             f"- D uses proposed T*={T_STAR} for w=0 and w=1. The w=1 feasibility floor is {plan['T_star_feasibility_floor_w1']}.",
             "", "A flat 2,056-token collection limit cannot cover all w=1 deployment cells at a common T.",
             "Instead, each call collects only the maximum completion required by M+8, D(w=0) and D(w=1).",
             "This changes the collection allowance, while primary M remains at W=2,048.", "",
             "Legacy base counts remain a labeled cost component with unverified EOS convention.",
             "D is conditional on those logged counts, not a fully audited inference-cost measurement.",
             "No lambda/practical threshold or GO/NO-GO decision is fitted or enabled in this 12-item diagnostic.",
             "No learned locator, held-out claim, deployment efficiency claim or Stage 0 change.", "",
             "| Item | Arm | Prompt | Collected cap | M | D w=0 | D w=1 |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for r in plan["requests"]:
        lines.append(f"| {r['question_id']} | {r['arm']} | {r['prompt_tokens']} | {r['completion_cap']} | "
                     f"{r['M_cap']} | {r['D_caps']['0']} | {r['D_caps']['1']} |")
    (output / "report.md").write_text("\n".join(lines) + "\n")
    return plan


def read_plan(directory: Path) -> dict:
    plan = json.loads((Path(directory) / "plan.json").read_text())
    checksum = plan.pop("plan_sha256")
    if text_sha256(encoded_json(plan)) != checksum:
        raise ValueError("prepared plan checksum mismatch")
    plan["plan_sha256"] = checksum
    if plan["source_sha256"] != matched_source_hashes():
        raise ValueError("sources changed since preparation; prepare a new reviewed plan")
    if plan["backend_runtime"] != backend_runtime_identity(mock=plan["evidence"] == "synthetic_preparation"):
        raise ValueError("runtime changed since preparation")
    if plan["python"] != sys.version or plan["platform"] != platform.platform():
        raise ValueError("Python/platform changed since preparation")
    manifest = verify_matched_history(Path(plan["historical_dir"]))
    if manifest["journal_head"] != plan["historical_journal_head"]:
        raise ValueError("historical journal changed since preparation")
    if file_sha256(Path(plan["historical_dir"]) / "dataset.json") != plan["historical_dataset_sha256"]:
        raise ValueError("historical dataset changed since preparation")
    return plan


def run_plan(directory: Path, output: Path, *, mock: bool = False, approved: bool = False) -> dict:
    """Run exactly the reviewed requests; failures remain journaled, never replaced."""
    plan = read_plan(directory)
    if not mock and (not approved or plan["evidence"] == "synthetic_preparation"):
        raise ValueError("real generation requires explicit approval of a real-tokenizer plan")
    output = Path(output).resolve()
    historical = Path(plan["historical_dir"])
    if output.is_relative_to(historical) or output.is_relative_to(Path(directory).resolve()):
        raise ValueError("collection must use a separate directory outside history and the prepared plan")
    identity = {
        "schema_version": 1, "study": plan["study"], "role": "exposed_development_matched",
        "mock": mock, "model_repository": "mock" if mock else MODEL_REPOSITORY,
        "model_revision": "mock" if mock else MODEL_REVISION,
        "quantization": None if mock else QUANTIZATION, "dev_pool_sha256": DEV_POOL_SHA256,
        "settings_sha256": text_sha256(encoded_json({"plan": plan["plan_sha256"], "mock": mock})),
        "source_sha256": plan["source_sha256"],
    }
    manifest = {"identity": identity, "study": plan["study"], "status": "running", "mock": mock,
                "confirmatory": False, "evidence": "synthetic_mock" if mock else "exposed_development",
                "plan_sha256": plan["plan_sha256"], "limits": plan["limits"], "active_seconds": 0,
                "source_sha256": plan["source_sha256"],
                "started_utc": datetime.now(timezone.utc).isoformat()}
    journal = PilotJournal(output, manifest, expected_identity=identity)
    started, previous_seconds = time.monotonic(), manifest.get("active_seconds", 0)
    try:
        if mock:
            model = MockLLM()
            tokenizer = model.tokenizer
        else:
            snapshot = resolve_and_verify_local_snapshot(plan["local_model_path"])
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            from mlx_lm import load
            model, tokenizer = load(str(snapshot))
        records = []
        requests_by_key = {(r["question_id"], r["arm"]): r for r in plan["requests"]}
        attempts = [v for k, v in journal.cache.items()
                    if k[0] == "call_started" and v["target_kind"] == "matched_call"]
        reserved_completion = sum(requests_by_key[tuple(v["target_key"])]["completion_cap"] for v in attempts)
        reserved_prompt = sum(requests_by_key[tuple(v["target_key"])]["prompt_tokens"] for v in attempts)
        for request in plan["requests"]:
            key = [request["question_id"], request["arm"]]
            if journal.has("matched_call", *key):
                records.append(journal.get("matched_call", *key))
                continue
            if journal.total_attempted_calls >= plan["limits"]["max_attempted_calls"]:
                raise RuntimeError("attempted-call ceiling reached; failure retries need a new reviewed budget")
            if (reserved_completion + request["completion_cap"] > plan["limits"]["max_completion_tokens"]
                    or reserved_prompt + request["prompt_tokens"] > plan["limits"]["max_prompt_tokens"]):
                raise RuntimeError("reserved token ceiling reached; failed calls retain their full allowance")
            if previous_seconds + time.monotonic() - started >= MAX_SECONDS:
                raise RuntimeError("active duration ceiling reached before the next call")
            if not mock and encode_prompt(tokenizer, request["prompt"]) != request["prompt_token_ids"]:
                raise ValueError("backend prompt IDs differ from prepared prompt IDs")
            prompt_tokens = len(encode_prompt(tokenizer, request["prompt"]))
            journal.record_call_started("matched_call", key, request["prompt"], prompt_tokens)
            reserved_completion += request["completion_cap"]
            reserved_prompt += request["prompt_tokens"]
            captured = {}
            _, _, _, duration = execute_llm_call(
                model, tokenizer, request["prompt"], request["completion_cap"], .6, request["seed"],
                is_mock=mock, capture=captured,
            )
            record = {**request, **captured, "seed_policy": CAP_SWEEP_SEED_POLICY,
                      "duration_ms": duration, "evidence": manifest["evidence"]}
            record["total_tokens"] = record["prompt_tokens"] + record["completion_tokens"]
            journal.append("matched_call", key, record)
            records.append(record)
        atomic_save_json(output / "records.json", records)
        manifest.update({"status": "complete", "executed_model_calls": journal.executed_model_calls,
                         "finished_utc": datetime.now(timezone.utc).isoformat(),
                         "active_seconds": previous_seconds + time.monotonic() - started,
                         "total_completion_tokens": journal.total_completion_tokens,
                         "total_incurred_tokens": journal.total_incurred_tokens})
        manifest["artifact_hashes"] = {name: file_sha256(output / name)
                                       for name in ("records.json", "calls.jsonl")}
        journal.save_manifest()
        return manifest
    except Exception as error:
        manifest.update({"status": "failed", "error": str(error),
                         "active_seconds": previous_seconds + time.monotonic() - started})
        journal.save_manifest()
        raise
    finally:
        journal.close()
