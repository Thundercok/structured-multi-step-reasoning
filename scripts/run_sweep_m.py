#!/usr/bin/env python3
"""Runner for Prompt M3 (COT on gen_tune.json at tag harness-v1-run5).

Usage:
  python3 scripts/run_sweep_m.py --model-id mlx-community/Qwen3-8B-4bit
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
from reasoning_strategies import parse_answer_details
from qwen_mlx_backend import COT_SUFFIX

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
    ap.add_argument("--out-jsonl", default=str(ROOT / "audit" / "M_sweep_trace.jsonl"))
    ap.add_argument("--out-summary", default=str(ROOT / "audit" / "M_summary.txt"))
    ap.add_argument("--k-rescored", default=str(ROOT / "audit" / "K_rescored.jsonl"))
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

    print("=== INITIALIZING MODEL FROM LOCAL SNAPSHOT ===")
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
    done_ids = set()
    if os.path.exists(args.out_jsonl):
        with open(args.out_jsonl, "r", encoding="utf-8") as rf:
            for line in rf:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    records.append(r)
                    done_ids.add(r.get("id"))
                except Exception:
                    pass
        print(f"Resuming: found {len(records)} existing records in {args.out_jsonl}")

    sampler = make_sampler(temp=0.0)
    max_tokens = 1024

    os.makedirs(os.path.dirname(args.out_jsonl) or ".", exist_ok=True)
    with open(args.out_jsonl, "a", encoding="utf-8") as jf:
        print(f"\n--- Arm: COT (T=0, cap 1024) ({len(items)} items) ---")
        for idx, it in enumerate(items, 1):
            if it["id"] in done_ids:
                continue

            user_content = it["query"] + COT_SUFFIX
            msgs = [{"role": "user", "content": user_content}]
            prompt_str = tokenizer.apply_chat_template(
                msgs,
                tokenize=False,
                enable_thinking=False,
                add_generation_prompt=True,
            )

            p_tok = len(tokenizer.encode(prompt_str))
            t0 = time.perf_counter()
            text, tok, f_reason = "", 0, None
            for r in mlx_lm.stream_generate(model, tokenizer, prompt_str, max_tokens=max_tokens, sampler=sampler):
                text += r.text
                tok = r.generation_tokens
                if getattr(r, "finish_reason", None) is not None:
                    f_reason = r.finish_reason
                # Early stop at end of first line starting with Answer:
                m_stop = re.search(r"(?:^|\n)Answer:[^\r\n]*\r?\n", text)
                if m_stop:
                    text = text[:m_stop.end()]
                    f_reason = "stop_answer"
                    break

            wall_ms = (time.perf_counter() - t0) * 1000.0
            finish_reason = f_reason or "stop"
            repeat = check_repeated_lines(text)

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
                "arm": "COT",
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
            done_ids.add(it["id"])
            jf.write(json.dumps(rec, ensure_ascii=False) + "\n")
            jf.flush()

            if idx % 10 == 0 or idx == len(items):
                print(f"  [{idx}/{len(items)}] {it['id']} -> {ans!r} (gold: {it['answer']!r}, ok: {correct}, f: {finish_reason}, rep: {repeat})")

    # Load K-rescored records for comparison
    k_records = []
    if os.path.exists(args.k_rescored):
        with open(args.k_rescored, "r", encoding="utf-8") as kf:
            for line in kf:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    if r.get("arm") == "COT":
                        k_records.append(r)

    # Summary table
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
    summary_lines.append("=== COMPARISON TABLE: COT on gen_tune (M vs K-rescored) ===")
    header = "| family | level | n | K-rescored acc | M acc | %length | mean tokens |"
    sep    = "| --- | --- | --- | --- | --- | --- | --- |"
    summary_lines.append(header)
    summary_lines.append(sep)

    for fam in families:
        for lvl in range(1, 5):
            m_recs = [r for r in records if r["family"] == fam and r["level"] == lvl]
            k_recs = [r for r in k_records if r["family"] == fam and r["level"] == lvl]
            n = len(m_recs)
            if n == 0:
                continue
            m_acc = f"{sum(1 for r in m_recs if r['correct']) / n:.1%}"
            k_acc = f"{sum(1 for r in k_recs if r['correct']) / len(k_recs):.1%}" if k_recs else "n/a"
            pct_len = f"{sum(1 for r in m_recs if r['finish_reason'] == 'length') / n:.1%}"
            mean_tok = f"{sum(r['completion_tokens'] for r in m_recs) / n:.1f}"
            row = f"| {fam} | {lvl} | {n} | {k_acc} | {m_acc} | {pct_len} | {mean_tok} |"
            summary_lines.append(row)
    summary_lines.append("")

    # Overall summary row
    tot_n = len(records)
    tot_m_acc = f"{sum(1 for r in records if r['correct']) / tot_n:.1%}" if tot_n else "0%"
    tot_k_acc = f"{sum(1 for r in k_records if r['correct']) / len(k_records):.1%}" if k_records else "n/a"
    tot_len = f"{sum(1 for r in records if r['finish_reason'] == 'length') / tot_n:.1%}" if tot_n else "0%"
    tot_mean_tok = f"{sum(r['completion_tokens'] for r in records) / tot_n:.1f}" if tot_n else "0.0"
    summary_lines.append(f"**Total**: n={tot_n} | K-rescored acc={tot_k_acc} | M acc={tot_m_acc} | %length={tot_len} | mean tokens={tot_mean_tok}")

    summary_text = "\n".join(summary_lines)
    Path(args.out_summary).write_text(summary_text, encoding="utf-8")
    print("\n" + summary_text)


if __name__ == "__main__":
    main()
