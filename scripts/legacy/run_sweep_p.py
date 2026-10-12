#!/usr/bin/env python3
"""Runner for Prompt P (DIRECT-v2 + COT on gen02_tune.json at tag harness-v1-run7).

Usage:
  python3 scripts/run_sweep_p.py
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
from qwen_mlx_backend import COT_SUFFIX

DATA_TUNE_PATH = ROOT / "data" / "gen02_tune.json"
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
    ap.add_argument("--model-id", default="mlx-community/Qwen3-8B-4bit")
    ap.add_argument("--snapshot-dir", default=DEFAULT_SNAPSHOT_DIR)
    ap.add_argument("--out-jsonl", default=str(ROOT / "audit" / "P_sweep_trace.jsonl"))
    ap.add_argument("--out-summary", default=str(ROOT / "audit" / "P_summary.txt"))
    args = ap.parse_args()

    # 1. Hard Asserts
    git_info = get_git_info()
    assert args.model_id == "mlx-community/Qwen3-8B-4bit", f"Model must be Qwen3-8B-4bit, got: {args.model_id}"
    assert not git_info["dirty"], f"Worktree must be clean (dirty=False), got dirty={git_info['dirty']}"

    snapshot_path = Path(args.snapshot_dir)
    assert snapshot_path.is_dir(), f"Snapshot dir not found: {snapshot_path}"
    safetensors_blobs = get_safetensors_blobs(snapshot_path)
    assert safetensors_blobs, f"No .safetensors found in {snapshot_path}"
    snapshot_hash = snapshot_path.name

    print("=== INITIALIZING MODEL FROM LOCAL SNAPSHOT ===")
    print(f"Snapshot path: {snapshot_path}")
    print(f"Snapshot hash: {snapshot_hash}")
    print(f"Safetensors blobs: {safetensors_blobs}")

    model, tokenizer = mlx_lm.load(str(snapshot_path))
    eos_ids = getattr(tokenizer, "eos_token_ids", None)
    if eos_ids is None:
        eid = tokenizer.eos_token_id
        eos_ids = [eid] if isinstance(eid, int) else list(eid)
    eos_ids_list = sorted(list(set(eos_ids)))

    # Load dataset
    with open(DATA_TUNE_PATH, "r", encoding="utf-8") as f:
        tune_data = json.load(f)
    items = tune_data["items"]
    assert len(items) == 100, f"Expected 100 items in gen02_tune.json, got {len(items)}"
    print(f"Loaded {len(items)} items from {DATA_TUNE_PATH}")

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

    # Arms configuration for Prompt P
    # DIRECT-v2: arith + order only (g24 skipped per prompt spec)
    # COT: all families (arith, order, g24), cap 1024
    arms_config = [
        {
            "name": "DIRECT-v2",
            "filter_fn": lambda it: it["family"] in ("arith", "order"),
            "suffix": "\nGive only the final answer directly without explanation.",
            "prefill": "Answer: ",
            "max_tokens": 24,
            "is_direct": True,
        },
        {
            "name": "COT",
            "filter_fn": lambda it: True,
            "suffix": COT_SUFFIX,
            "prefill": "",
            "max_tokens": 1024,
            "is_direct": False,
        },
    ]

    sampler = make_sampler(temp=0.0)
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
                max_tok = arm["max_tokens"]

                t0 = time.perf_counter()
                text, tok, f_reason = "", 0, None
                for r in mlx_lm.stream_generate(model, tokenizer, prompt_str, max_tokens=max_tok, sampler=sampler):
                    text += r.text
                    tok = r.generation_tokens
                    if getattr(r, "finish_reason", None) is not None:
                        f_reason = r.finish_reason

                    if not arm["is_direct"]:
                        # EOS-stop like run7
                        m_stop = re.search(r"(?:^|\n)Answer:[ \t]*\S[^\r\n]*\r?\n", text)
                        if m_stop:
                            text = text[:m_stop.end()]
                            f_reason = "stop_answer"
                            break

                wall_ms = (time.perf_counter() - t0) * 1000.0
                finish_reason = f_reason or "stop"
                repeat = check_repeated_lines(text)

                if arm["is_direct"]:
                    first_line = text.strip().splitlines()[0].strip() if text.strip() else ""
                    clean_first_line = first_line.replace("**", "").strip()
                    ans = extract_answer("Answer: " + clean_first_line)
                    status = "marker" if ans else "fail"
                    wordy = False
                else:
                    ans, status, wordy = parse_answer_details(text)

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
                    print(f"  [{idx}/{len(filtered_items)}] {it['id']} -> {ans!r} (gold: {it['answer']!r}, ok: {correct}, f: {finish_reason})")

    # 4. Generate Output Tables & Summary (P2)
    summary_lines = []
    summary_lines.append("=== RUN HEADER ===")
    summary_lines.append(f"branch: {git_info['branch']}")
    summary_lines.append(f"tag: {git_info['tag']}")
    summary_lines.append(f"commit: {git_info['commit']}")
    summary_lines.append(f"dirty: {git_info['dirty']}")
    summary_lines.append(f"model_id: {args.model_id}")
    summary_lines.append(f"snapshot_hash: {snapshot_hash}")
    summary_lines.append("")

    summary_lines.append("=== BẢNG FAMILY × LEVEL ===")
    header = "| family | level | n | DIRECT | COT | %length | %parsed rỗng | mean tokens |"
    sep    = "| --- | --- | --- | --- | --- | --- | --- | --- |"
    summary_lines.append(header)
    summary_lines.append(sep)

    levels_map = {
        "arith": [1, 2, 3, 4, 5],
        "order": [1, 2, 3, 4],
        "g24": [1, 2, 3, 4],
    }

    tot_n = 0
    tot_dir_corr, tot_dir_n = 0, 0
    tot_cot_corr = 0
    tot_len = 0
    tot_empty = 0
    tot_tokens = 0

    for fam in ("arith", "order", "g24"):
        for lvl in levels_map[fam]:
            fam_items = [it for it in items if it["family"] == fam and it["level"] == lvl]
            n = len(fam_items)
            if n == 0:
                continue

            # DIRECT
            dir_recs = [r for r in records if r["arm"] == "DIRECT-v2" and r["family"] == fam and r["level"] == lvl]
            if dir_recs:
                dir_acc = f"{sum(1 for r in dir_recs if r['correct']) / len(dir_recs):.1%}"
                tot_dir_corr += sum(1 for r in dir_recs if r['correct'])
                tot_dir_n += len(dir_recs)
            else:
                dir_acc = "n/a"

            # COT
            cot_recs = [r for r in records if r["arm"] == "COT" and r["family"] == fam and r["level"] == lvl]
            if cot_recs:
                cot_acc = f"{sum(1 for r in cot_recs if r['correct']) / len(cot_recs):.1%}"
                pct_len = f"{sum(1 for r in cot_recs if r['finish_reason'] == 'length') / len(cot_recs):.1%}"
                pct_empty = f"{sum(1 for r in cot_recs if not r.get('parsed')) / len(cot_recs):.1%}"
                mean_tok = f"{sum(r['completion_tokens'] for r in cot_recs) / len(cot_recs):.1f}"

                tot_n += len(cot_recs)
                tot_cot_corr += sum(1 for r in cot_recs if r['correct'])
                tot_len += sum(1 for r in cot_recs if r['finish_reason'] == 'length')
                tot_empty += sum(1 for r in cot_recs if not r.get('parsed'))
                tot_tokens += sum(r['completion_tokens'] for r in cot_recs)
            else:
                cot_acc, pct_len, pct_empty, mean_tok = "n/a", "n/a", "n/a", "n/a"

            row = f"| {fam} | {lvl} | {n} | {dir_acc} | {cot_acc} | {pct_len} | {pct_empty} | {mean_tok} |"
            summary_lines.append(row)

    # Total row
    dir_tot_str = f"{tot_dir_corr / tot_dir_n:.1%}" if tot_dir_n > 0 else "n/a"
    cot_tot_str = f"{tot_cot_corr / tot_n:.1%}" if tot_n > 0 else "n/a"
    pct_len_tot = f"{tot_len / tot_n:.1%}" if tot_n > 0 else "n/a"
    pct_empty_tot = f"{tot_empty / tot_n:.1%}" if tot_n > 0 else "n/a"
    mean_tok_tot = f"{tot_tokens / tot_n:.1f}" if tot_n > 0 else "n/a"
    summary_lines.append(f"| **Total** | - | **{tot_n}** | **{dir_tot_str}** | **{cot_tot_str}** | **{pct_len_tot}** | **{pct_empty_tot}** | **{mean_tok_tot}** |")
    summary_lines.append("")

    # 2 wrong items per family for COT
    summary_lines.append("=== 2 ITEM SAI MỖI FAMILY (COT T=0) ===")
    for fam in ("arith", "order", "g24"):
        fam_cot_wrong = [r for r in records if r["arm"] == "COT" and r["family"] == fam and not r["correct"]]
        summary_lines.append(f"\n--- Family: {fam} ({len(fam_cot_wrong)} wrong in COT) ---")
        for s_idx, r in enumerate(fam_cot_wrong[:2], 1):
            raw_tail = r["raw_output"][-300:].replace("\n", "\\n")
            summary_lines.append(f"Sample {s_idx}:")
            summary_lines.append(f"  id: {r['id']}")
            summary_lines.append(f"  raw_tail: {raw_tail}")
            summary_lines.append(f"  parsed: {r['parsed']!r}")
            summary_lines.append(f"  gold: {r['gold']!r}")

    summary_text = "\n".join(summary_lines)
    Path(args.out_summary).write_text(summary_text, encoding="utf-8")
    print("\n" + summary_text)


if __name__ == "__main__":
    main()
