#!/usr/bin/env python3
"""Runner for Gate G (G2 model verification + G3 sweep on gen_tune.json).

Usage:
  python3 scripts/run_sweep_g.py --model-id mlx-community/Qwen3-8B-4bit
"""

import argparse
import json
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mlx_lm
from mlx_lm.sample_utils import make_sampler
from scripts.gen_tasks import check as gen_check
from qwen_mlx_backend import QwenMLXBackend, COT_SUFFIX, DIRECT_SUFFIX
from reasoning_strategies import parse_answer_details

DATA_TUNE_PATH = ROOT / "data" / "gen_tune.json"


def get_git_info():
    def _run(cmd):
        try:
            return subprocess.check_output(cmd, cwd=str(ROOT), stderr=subprocess.DEVNULL).decode().strip()
        except Exception:
            return "unknown"

    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    commit = _run(["git", "rev-parse", "--short", "HEAD"])
    tag = _run(["git", "describe", "--tags", "--exact-match", "HEAD"])
    dirty = bool(_run(["git", "status", "--porcelain"]))
    return {"branch": branch, "tag": tag, "commit": commit, "dirty": dirty}


def get_snapshot_hash(model_id: str) -> str:
    hub = Path(os.path.expanduser("~/.cache/huggingface/hub"))
    folder_name = "models--" + model_id.replace("/", "--")
    snapshots = hub / folder_name / "snapshots"
    if snapshots.exists():
        dirs = [d.name for d in snapshots.iterdir() if d.is_dir()]
        if dirs:
            return sorted(dirs)[-1]
    return "unknown"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-id", required=True, help="HF model identifier")
    ap.add_argument("--out-jsonl", default=str(ROOT / "audit" / "G_sweep_trace.jsonl"))
    ap.add_argument("--out-summary", default=str(ROOT / "audit" / "G_summary.txt"))
    args = ap.parse_args()

    # 1. Assert exact model id
    assert args.model_id == "mlx-community/Qwen3-8B-4bit", (
        f"Model must be 'mlx-community/Qwen3-8B-4bit', got: {args.model_id}"
    )

    print(f"=== INITIALIZING MODEL {args.model_id} ===")
    snapshot_hash = get_snapshot_hash(args.model_id)
    print(f"Model snapshot hash: {snapshot_hash}")

    # Load model and tokenizer
    model, tokenizer = mlx_lm.load(args.model_id)
    eos_ids = getattr(tokenizer, "eos_token_ids", None)
    if eos_ids is None:
        eid = tokenizer.eos_token_id
        eos_ids = [eid] if isinstance(eid, int) else list(eid)
    eos_ids_list = sorted(list(set(eos_ids)))
    print(f"tokenizer.eos_token: {tokenizer.eos_token}")
    print(f"tokenizer.eos_token_ids: {eos_ids_list}")

    git_info = get_git_info()

    # 2. G2: 1 Generation Sample (enable_thinking=False)
    print("\n=== G2: 1 GENERATION SAMPLE (enable_thinking=False) ===")
    sample_msgs = [{"role": "user", "content": "Nếu 3 quả táo giá 45000 đồng, 7 quả táo giá bao nhiêu?" + DIRECT_SUFFIX}]
    sample_prompt = tokenizer.apply_chat_template(sample_msgs, enable_thinking=False, add_generation_prompt=True)
    decoded_prompt = tokenizer.decode(sample_prompt) if isinstance(sample_prompt, list) else sample_prompt
    last_80_chars = decoded_prompt[-80:].replace("\n", "\\n")
    print(f"Last 80 chars of decoded templated prompt: {last_80_chars}")

    sampler = make_sampler(temp=0.0)
    raw_sample = ""
    finish_reason = None
    sample_tok = 0
    for r in mlx_lm.stream_generate(model, tokenizer, sample_prompt, max_tokens=96, sampler=sampler):
        raw_sample += r.text
        sample_tok = r.generation_tokens
        if getattr(r, "finish_reason", None) is not None:
            finish_reason = r.finish_reason

    print(f"Raw output: {raw_sample!r}")
    print(f"finish_reason: {finish_reason}")
    assert finish_reason == "stop", f"Expected finish_reason == 'stop', got: {finish_reason}"
    has_think = "<think>" in raw_sample or "</think>" in raw_sample
    print(f"Has '<think>' in output: {has_think}")
    assert not has_think, "Found <think> in generation output!"

    # 3. G3: Sweep on data/gen_tune.json (94 items) across DIRECT and COT
    print("\n=== G3: SWEEP ON DATA/GEN_TUNE.JSON (94 ITEMS × 2 ARMS) ===")
    with open(DATA_TUNE_PATH, "r", encoding="utf-8") as f:
        tune_data = json.load(f)
    items = tune_data["items"]
    print(f"Loaded {len(items)} items from {DATA_TUNE_PATH}")
    assert len(items) == 94, f"Expected 94 items in gen_tune.json, got: {len(items)}"

    arms = [
        ("DIRECT", DIRECT_SUFFIX, 96),
        ("COT", COT_SUFFIX, 1024),
    ]

    records = []
    os.makedirs(os.path.dirname(args.out_jsonl) or ".", exist_ok=True)
    with open(args.out_jsonl, "w", encoding="utf-8") as jf:
        for arm_name, suffix, max_tok in arms:
            print(f"\n--- Arm: {arm_name} (max_tokens={max_tok}) ---")
            for idx, it in enumerate(items, 1):
                msgs = [{"role": "user", "content": it["query"] + suffix}]
                prompt = tokenizer.apply_chat_template(msgs, enable_thinking=False, add_generation_prompt=True)
                p_tok = len(prompt) if isinstance(prompt, list) else len(tokenizer.encode(prompt))

                t0 = time.perf_counter()
                text, tok, f_reason = "", 0, None
                for r in mlx_lm.stream_generate(model, tokenizer, prompt, max_tokens=max_tok, sampler=sampler):
                    text += r.text
                    tok = r.generation_tokens
                    if getattr(r, "finish_reason", None) is not None:
                        f_reason = r.finish_reason
                wall_ms = (time.perf_counter() - t0) * 1000.0

                answer_type = "expression" if it["family"] == "g24" else "text" if it["family"] == "order" else "number"
                ans, status, wordy = parse_answer_details(text, answer_type=answer_type)
                correct = bool(gen_check(it, ans))

                rec = {
                    "id": it["id"],
                    "group_id": it["group_id"],
                    "family": it["family"],
                    "level": it["level"],
                    "arm": arm_name,
                    "model_id": args.model_id,
                    "snapshot_hash": snapshot_hash,
                    "eos_token_ids": eos_ids_list,
                    "enable_thinking": False,
                    "raw_output": text,
                    "finish_reason": f_reason or "stop",
                    "prompt_tokens": p_tok,
                    "completion_tokens": tok,
                    "wall_ms": round(wall_ms, 2),
                    "parsed": ans,
                    "gold": it["answer"],
                    "correct": correct,
                    "parse_status": status,
                    "wordy": wordy,
                    "branch": git_info["branch"],
                    "tag": git_info["tag"],
                    "commit": git_info["commit"],
                    "dirty": git_info["dirty"],
                }
                records.append(rec)
                jf.write(json.dumps(rec, ensure_ascii=False) + "\n")
                jf.flush()
                if idx % 10 == 0 or idx == len(items):
                    print(f"  [{idx}/{len(items)}] {it['id']} -> {ans!r} (gold: {it['answer']!r}, ok: {correct})")

    # 4. Generate Output Table & Summary
    summary_lines = []
    # RUN HEADER
    summary_lines.append("=== RUN HEADER ===")
    summary_lines.append(f"branch: {git_info['branch']}")
    summary_lines.append(f"tag: {git_info['tag']}")
    summary_lines.append(f"commit: {git_info['commit']}")
    summary_lines.append(f"dirty: {git_info['dirty']}")
    summary_lines.append(f"model_id: {args.model_id}")
    summary_lines.append(f"snapshot_hash: {snapshot_hash}")
    summary_lines.append(f"eos_ids: {eos_ids_list}")
    summary_lines.append("")

    # TABLE: family × level -> n | DIRECT acc | COT acc | %max_tokens | %fallback | %wordy | mean completion_tokens
    summary_lines.append("=== TUNE SWEEP RESULTS TABLE ===")
    header = "| family | level | n | DIRECT acc | COT acc | %max_tokens | %fallback | %wordy | mean completion_tokens |"
    sep    = "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"
    summary_lines.append(header)
    summary_lines.append(sep)

    families = ["arith", "order", "g24"]
    for fam in families:
        for lvl in range(1, 5):
            dir_recs = [r for r in records if r["arm"] == "DIRECT" and r["family"] == fam and r["level"] == lvl]
            cot_recs = [r for r in records if r["arm"] == "COT" and r["family"] == fam and r["level"] == lvl]
            n = len(cot_recs)
            if n == 0:
                continue
            dir_ok = sum(1 for r in dir_recs if r["correct"])
            cot_ok = sum(1 for r in cot_recs if r["correct"])
            dir_acc = f"{dir_ok / len(dir_recs):.1%}" if dir_recs else "0.0%"
            cot_acc = f"{cot_ok / n:.1%}"
            all_recs = dir_recs + cot_recs
            pct_max = f"{sum(1 for r in all_recs if r['finish_reason'] == 'length') / len(all_recs):.1%}"
            pct_fallback = f"{sum(1 for r in all_recs if r['parse_status'] == 'fallback') / len(all_recs):.1%}"
            pct_wordy = f"{sum(1 for r in all_recs if r['wordy']) / len(all_recs):.1%}"
            mean_tok = f"{sum(r['completion_tokens'] for r in all_recs) / len(all_recs):.1f}"

            row = f"| {fam} | {lvl} | {n} | {dir_acc} | {cot_acc} | {pct_max} | {pct_fallback} | {pct_wordy} | {mean_tok} |"
            summary_lines.append(row)

    # 2 wrong items per family for COT
    summary_lines.append("\n=== 2 WRONG ITEMS PER FAMILY (COT) ===")
    for fam in families:
        fam_cot_wrong = [r for r in records if r["arm"] == "COT" and r["family"] == fam and not r["correct"]]
        summary_lines.append(f"\n--- Family: {fam} ({len(fam_cot_wrong)} wrong in COT) ---")
        sample_wrong = fam_cot_wrong[:2]
        for s_idx, r in enumerate(sample_wrong, 1):
            raw_tail = r["raw_output"][-300:].replace("\n", "\\n")
            summary_lines.append(f"  Wrong Sample {s_idx}:")
            summary_lines.append(f"    id: {r['id']}")
            summary_lines.append(f"    raw_tail: {raw_tail}")
            summary_lines.append(f"    parsed: {r['parsed']!r}")
            summary_lines.append(f"    gold: {r['gold']!r}")
            summary_lines.append(f"    parse_status: {r['parse_status']}")
            summary_lines.append(f"    wordy: {r['wordy']}")

    summary_text = "\n".join(summary_lines)
    Path(args.out_summary).write_text(summary_text, encoding="utf-8")
    print("\n" + summary_text)


if __name__ == "__main__":
    main()
