#!/usr/bin/env python3
"""Runner for Prompt K (DIRECT-v2 + COT on gen_tune.json).

Usage:
  python3 scripts/run_sweep_k.py --model-id mlx-community/Qwen3-8B-4bit
"""

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mlx_lm
from mlx_lm.sample_utils import make_sampler
from scripts.gen_tasks import check as gen_check
from reasoning_strategies import parse_answer_details, extract_answer

DATA_TUNE_PATH = ROOT / "data" / "gen_tune.json"
DEFAULT_SNAPSHOT_DIR = os.path.expanduser(
    "~/.cache/huggingface/hub/models--mlx-community--Qwen3-8B-4bit/snapshots/545dc4251c05440727734bcd94334791f6ab0192"
)


def get_git_info():
    def _run(cmd):
        try:
            return subprocess.check_output(cmd, cwd=str(ROOT), stderr=subprocess.DEVNULL).decode().strip()
        except Exception:
            return "unknown"

    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    commit = _run(["git", "rev-parse", "--short", "HEAD"])
    tag = _run(["git", "describe", "--tags", "--exact-match", "HEAD"])
    dirty = bool(_run(["git", "status", "--porcelain", "-uno"]))
    return {"branch": branch, "tag": tag, "commit": commit, "dirty": dirty}


def get_safetensors_blobs(snapshot_dir: Path) -> dict:
    blobs = {}
    for p in snapshot_dir.glob("*.safetensors"):
        real = os.path.realpath(p)
        blobs[p.name] = os.path.basename(real)
    return blobs


def check_repeated_lines(text: str, min_count: int = 3) -> bool:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return False
    counts = Counter(lines)
    return any(c >= min_count for c in counts.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-id", default="mlx-community/Qwen3-8B-4bit", help="HF model identifier")
    ap.add_argument("--snapshot-dir", default=DEFAULT_SNAPSHOT_DIR, help="Local snapshot directory")
    ap.add_argument("--out-jsonl", default=str(ROOT / "audit" / "K_sweep_trace.jsonl"))
    ap.add_argument("--out-summary", default=str(ROOT / "audit" / "K_summary.txt"))
    ap.add_argument("--enable-thinking", action="store_true", default=False)
    args = ap.parse_args()

    # 1. Hard Asserts
    git_info = get_git_info()
    assert args.model_id == "mlx-community/Qwen3-8B-4bit", (
        f"Model must be 'mlx-community/Qwen3-8B-4bit', got: {args.model_id}"
    )
    assert not args.enable_thinking, f"enable_thinking must be False, got: {args.enable_thinking}"
    assert not git_info["dirty"], f"Repository must be clean (dirty=False), got dirty={git_info['dirty']}"

    snapshot_path = Path(args.snapshot_dir)
    assert snapshot_path.is_dir(), f"Snapshot dir not found: {snapshot_path}"
    safetensors_blobs = get_safetensors_blobs(snapshot_path)
    assert safetensors_blobs, f"No .safetensors found in {snapshot_path}"
    snapshot_hash = snapshot_path.name

    print(f"=== INITIALIZING MODEL FROM LOCAL SNAPSHOT ===")
    print(f"Snapshot path: {snapshot_path}")
    print(f"Snapshot hash: {snapshot_hash}")
    print(f"Safetensors blobs: {safetensors_blobs}")

    # Load from local snapshot
    model, tokenizer = mlx_lm.load(str(snapshot_path))
    eos_ids = getattr(tokenizer, "eos_token_ids", None)
    if eos_ids is None:
        eid = tokenizer.eos_token_id
        eos_ids = [eid] if isinstance(eid, int) else list(eid)
    eos_ids_list = sorted(list(set(eos_ids)))
    print(f"tokenizer.eos_token: {tokenizer.eos_token}")
    print(f"tokenizer.eos_token_ids: {eos_ids_list}")

    # Load dataset
    with open(DATA_TUNE_PATH, "r", encoding="utf-8") as f:
        tune_data = json.load(f)
    items = tune_data["items"]
    print(f"Loaded {len(items)} items from {DATA_TUNE_PATH}")
    assert len(items) == 94, f"Expected 94 items, got {len(items)}"

    # Resume support
    records = []
    done_keys = set()
    if os.path.exists(args.out_jsonl):
        with open(args.out_jsonl, "r", encoding="utf-8") as rf:
            for line in rf:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    records.append(r)
                    done_keys.add((r.get("arm"), r.get("id")))
                except Exception:
                    pass
        print(f"Resuming: found {len(records)} existing records in {args.out_jsonl}")

    # Arm definitions
    # 1. DIRECT-v2: prefill 'Answer:', max_tokens 24 (g24: 32), parse first line
    # 2. COT: T=0, cap 1024, English suffix
    # 3. g24-COT-sample: g24 only, T=0.7/top_p=0.8/top_k=20, cap 1024
    arms_config = [
        {
            "name": "DIRECT-v2",
            "filter_fn": lambda it: True,
            "suffix": "\nGive only the final answer directly without explanation.",
            "prefill": "Answer: ",
            "max_tokens_fn": lambda it: 32 if it["family"] == "g24" else 24,
            "sampler": make_sampler(temp=0.0),
            "is_direct_v2": True,
        },
        {
            "name": "COT",
            "filter_fn": lambda it: True,
            "suffix": "\nThink step by step and output your final answer on the last line starting with 'Answer: '.",
            "prefill": "",
            "max_tokens_fn": lambda it: 1024,
            "sampler": make_sampler(temp=0.0),
            "is_direct_v2": False,
        },
        {
            "name": "g24-COT-sample",
            "filter_fn": lambda it: it["family"] == "g24",
            "suffix": "\nThink step by step and output your final answer on the last line starting with 'Answer: '.",
            "prefill": "",
            "max_tokens_fn": lambda it: 1024,
            "sampler": make_sampler(temp=0.7, top_p=0.8, top_k=20),
            "is_direct_v2": False,
        },
    ]

    os.makedirs(os.path.dirname(args.out_jsonl) or ".", exist_ok=True)
    with open(args.out_jsonl, "a", encoding="utf-8") as jf:
        for arm in arms_config:
            arm_name = arm["name"]
            filtered_items = [it for it in items if arm["filter_fn"](it)]
            print(f"\n--- Arm: {arm_name} ({len(filtered_items)} items) ---")

            for idx, it in enumerate(filtered_items, 1):
                if (arm_name, it["id"]) in done_keys:
                    continue

                user_content = it["query"] + arm["suffix"]
                msgs = [{"role": "user", "content": user_content}]
                prompt_str = tokenizer.apply_chat_template(
                    msgs,
                    tokenize=False,
                    enable_thinking=False,
                    add_generation_prompt=True,
                )
                if arm["prefill"]:
                    prompt_str += arm["prefill"]

                p_tok = len(tokenizer.encode(prompt_str))
                max_tok = arm["max_tokens_fn"](it)

                t0 = time.perf_counter()
                text, tok, f_reason = "", 0, None
                for r in mlx_lm.stream_generate(model, tokenizer, prompt_str, max_tokens=max_tok, sampler=arm["sampler"]):
                    text += r.text
                    tok = r.generation_tokens
                    if getattr(r, "finish_reason", None) is not None:
                        f_reason = r.finish_reason
                wall_ms = (time.perf_counter() - t0) * 1000.0

                finish_reason = f_reason or "stop"
                repeat = check_repeated_lines(text)

                if arm["is_direct_v2"]:
                    # Parse first line directly
                    full_text = "Answer: " + text
                    first_line = text.strip().splitlines()[0].strip() if text.strip() else ""
                    clean_first_line = first_line.replace("**", "").strip()
                    ans = extract_answer("Answer: " + clean_first_line)
                    status = "marker" if ans else "fail"
                    wordy = False
                else:
                    ans, status, wordy = parse_answer_details(text)

                # K1 rule: finish_reason=length => correct=False, parse_status=truncated
                if finish_reason == "length":
                    correct = False
                    status = "truncated"
                else:
                    correct = bool(gen_check(it, ans))

                rec = {
                    "id": it["id"],
                    "group_id": it["group_id"],
                    "family": it["family"],
                    "level": it["level"],
                    "arm": arm_name,
                    "model_id": args.model_id,
                    "snapshot_dir": str(snapshot_path),
                    "snapshot_hash": snapshot_hash,
                    "safetensors_blobs": safetensors_blobs,
                    "eos_token_ids": eos_ids_list,
                    "enable_thinking": False,
                    "raw_output": text,
                    "finish_reason": finish_reason,
                    "prompt_tokens": p_tok,
                    "completion_tokens": tok,
                    "wall_ms": round(wall_ms, 2),
                    "parsed": ans,
                    "gold": it["answer"],
                    "correct": correct,
                    "parse_status": status,
                    "wordy": wordy,
                    "repeat": repeat,
                    "branch": git_info["branch"],
                    "tag": git_info["tag"],
                    "commit": git_info["commit"],
                    "dirty": git_info["dirty"],
                }
                records.append(rec)
                done_keys.add((arm_name, it["id"]))
                jf.write(json.dumps(rec, ensure_ascii=False) + "\n")
                jf.flush()

                if idx % 10 == 0 or idx == len(filtered_items):
                    print(f"  [{idx}/{len(filtered_items)}] {it['id']} -> {ans!r} (gold: {it['answer']!r}, ok: {correct}, f: {finish_reason}, rep: {repeat})")

    # 4. Generate Output Tables & Summary (K3)
    summary_lines = []
    summary_lines.append("=== RUN HEADER ===")
    summary_lines.append(f"branch: {git_info['branch']}")
    summary_lines.append(f"tag: {git_info['tag']}")
    summary_lines.append(f"commit: {git_info['commit']}")
    summary_lines.append(f"dirty: {git_info['dirty']}")
    summary_lines.append(f"model_id: {args.model_id}")
    summary_lines.append(f"snapshot_hash: {snapshot_hash}")
    summary_lines.append(f"safetensors_blobs: {safetensors_blobs}")
    summary_lines.append(f"eos_ids: {eos_ids_list}")
    summary_lines.append("")

    families = ["arith", "order", "g24"]
    for arm in arms_config:
        arm_name = arm["name"]
        summary_lines.append(f"=== PER-ARM RESULTS: {arm_name} ===")
        header = "| family | level | n | acc | %length | %repeat | mean tokens |"
        sep    = "| --- | --- | --- | --- | --- | --- | --- |"
        summary_lines.append(header)
        summary_lines.append(sep)

        for fam in families:
            for lvl in range(1, 5):
                arm_recs = [r for r in records if r["arm"] == arm_name and r["family"] == fam and r["level"] == lvl]
                n = len(arm_recs)
                if n == 0:
                    continue
                acc = f"{sum(1 for r in arm_recs if r['correct']) / n:.1%}"
                pct_len = f"{sum(1 for r in arm_recs if r['finish_reason'] == 'length') / n:.1%}"
                pct_rep = f"{sum(1 for r in arm_recs if r.get('repeat', False)) / n:.1%}"
                mean_tok = f"{sum(r['completion_tokens'] for r in arm_recs) / n:.1f}"
                row = f"| {fam} | {lvl} | {n} | {acc} | {pct_len} | {pct_rep} | {mean_tok} |"
                summary_lines.append(row)
        summary_lines.append("")

    # 2 wrong items per family for COT arms
    summary_lines.append("=== 2 WRONG ITEMS PER FAMILY (COT T=0) ===")
    for fam in families:
        fam_cot_wrong = [r for r in records if r["arm"] == "COT" and r["family"] == fam and not r["correct"]]
        summary_lines.append(f"\n--- Family: {fam} ({len(fam_cot_wrong)} wrong in COT) ---")
        for s_idx, r in enumerate(fam_cot_wrong[:2], 1):
            raw_tail = r["raw_output"][-300:].replace("\n", "\\n")
            summary_lines.append(f"  Wrong Sample {s_idx}:")
            summary_lines.append(f"    id: {r['id']}")
            summary_lines.append(f"    raw_tail: {raw_tail}")
            summary_lines.append(f"    parsed: {r['parsed']!r}")
            summary_lines.append(f"    gold: {r['gold']!r}")
            summary_lines.append(f"    parse_status: {r['parse_status']}")
            summary_lines.append(f"    repeat: {r.get('repeat', False)}")

    summary_text = "\n".join(summary_lines)
    Path(args.out_summary).write_text(summary_text, encoding="utf-8")
    print("\n" + summary_text)


if __name__ == "__main__":
    main()
