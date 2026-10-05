#!/usr/bin/env python3
"""Unified sweep runner for reasoning strategies (Prompt R1).

Usage:
  python3 scripts/run_sweep.py --dataset data/gen02_tune.json --arms DIRECT-v2,COT,SC,TOT,REACT,PAL --out audit/sweep_trace.jsonl
  python3 scripts/run_sweep.py --dataset data/gen02_tune.json --arms DIRECT-v2,COT --stub --max-items 2 --out audit/stub_trace.jsonl
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

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.gen_tasks import check as gen_check
from reasoning_strategies import parse_answer_details, extract_answer, majority_vote

COT_SUFFIX = "\nWrite concise steps in plain text without markdown or LaTeX. End with exactly one line 'Answer: ' followed only by the final answer."

DEFAULT_SNAPSHOT_DIR = os.path.expanduser(
    "~/.cache/huggingface/hub/models--mlx-community--Qwen3-8B-4bit/snapshots/545dc4251c05440727734bcd94334791f6ab0192"
)


def get_git_info(cwd: Path = ROOT):
    def _run(cmd):
        try:
            return subprocess.check_output(cmd, cwd=str(cwd), stderr=subprocess.DEVNULL).decode().strip()
        except Exception:
            return "unknown"

    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    commit = _run(["git", "rev-parse", "--short", "HEAD"])
    tag = _run(["git", "describe", "--tags", "--exact-match", "HEAD"])

    status_raw = _run(["git", "status", "--porcelain", "-uall"])
    dirty = False
    if status_raw and status_raw != "unknown":
        for line in status_raw.splitlines():
            line = line.strip()
            if not line:
                continue
            path_part = line[2:].strip().strip('"')
            if "->" in path_part:
                path_part = path_part.split("->")[-1].strip().strip('"')
            path_clean = path_part.lstrip("/")
            if path_clean == "audit" or path_clean.startswith("audit/"):
                continue
            if path_clean == "data/MANIFEST.json":
                continue
            dirty = True
            break

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


class StubRunner:
    """Mock runner for offline testing without GPU/model loading."""

    def __init__(self, model_id: str = "mlx-community/Qwen3-8B-4bit"):
        self.model_id = model_id
        self.eos_ids = [151645]

    def run_arm(self, arm_name: str, item: dict) -> dict:
        gold = item["answer"]
        sc_candidates = None
        sc_vote_share = None
        tot_candidates = None
        tot_eval_scores = None

        # Simulate realistic outputs per arm
        if arm_name == "DIRECT-v2":
            raw = f"{gold}"
            parsed = gold
            tok = 12
            f_reason = "stop"
            mean_lp, min_lp = -0.15, -0.45
        elif arm_name == "COT":
            raw = f"Step 1: solve.\nAnswer: {gold}"
            parsed = gold
            tok = 120
            f_reason = "stop"
            mean_lp, min_lp = -0.25, -0.85
        elif arm_name == "SC":
            raw = f"Sample majority.\nAnswer: {gold}"
            parsed = gold
            tok = 500
            f_reason = "stop"
            mean_lp, min_lp = -0.30, -1.10
            sc_candidates = [gold] * 5
            sc_vote_share = 1.0
        elif arm_name == "TOT":
            raw = f"Tree search Best: 0.\nAnswer: {gold}"
            parsed = gold
            tok = 350
            f_reason = "stop"
            mean_lp, min_lp = -0.28, -0.95
            tot_candidates = [gold] * 3
            tot_eval_scores = [1.0, 0.0, 0.0]
        elif arm_name == "REACT":
            raw = f"Thought: solve Action: finish[{gold}]"
            parsed = gold
            tok = 80
            f_reason = "stop"
            mean_lp, min_lp = -0.20, -0.60
        elif arm_name == "PAL":
            raw = f"```python\nresult = {gold!r}\n```\nAnswer: {gold}"
            parsed = gold
            tok = 90
            f_reason = "stop"
            mean_lp, min_lp = -0.22, -0.70
        else:
            raise ValueError(f"Unknown arm: {arm_name}")

        correct = bool(gen_check(item, parsed))
        return {
            "raw_output": raw,
            "parsed": parsed,
            "correct": correct,
            "parse_status": "marker" if parsed else "fail",
            "prompt_tokens": len(item["query"].split()) + 20,
            "completion_tokens": tok,
            "n_tokens": tok,
            "mean_logprob": mean_lp,
            "min_logprob": min_lp,
            "sc_candidates": sc_candidates,
            "sc_vote_share": sc_vote_share,
            "tot_candidates": tot_candidates,
            "tot_eval_scores": tot_eval_scores,
            "finish_reason": f_reason,
            "wall_ms": 150.0,
            "repeat": False,
            "wordy": False,
        }


class MLXRunner:
    """Real MLX backend execution on Apple Silicon."""

    def __init__(self, model_id: str, snapshot_path: Path):
        import mlx_lm
        from mlx_lm.sample_utils import make_sampler

        print(f"Loading MLX model from {snapshot_path}...")
        self.model, self.tokenizer = mlx_lm.load(str(snapshot_path))
        self.mlx_lm = mlx_lm
        self.make_sampler = make_sampler

        eos_ids = getattr(self.tokenizer, "eos_token_ids", None)
        if eos_ids is None:
            eid = self.tokenizer.eos_token_id
            eos_ids = [eid] if isinstance(eid, int) else list(eid)
        self.eos_ids = sorted(list(set(eos_ids)))

    def _generate_stream(self, prompt: str, max_tokens: int, sampler, check_stop_answer: bool = True):
        text, tok, f_reason = "", 0, None
        logps = []
        for r in self.mlx_lm.stream_generate(self.model, self.tokenizer, prompt, max_tokens=max_tokens, sampler=sampler):
            text += r.text
            tok = r.generation_tokens
            if getattr(r, "finish_reason", None) is not None:
                f_reason = r.finish_reason

            if getattr(r, "logprobs", None) is not None and getattr(r, "token", None) is not None:
                try:
                    lp_arr = np.asarray(r.logprobs, dtype=np.float32)
                    if len(lp_arr) > r.token:
                        logps.append(float(lp_arr[r.token]))
                except Exception:
                    pass

            if check_stop_answer:
                m_stop = re.search(r"(?:^|\n)Answer:[ \t]*\S[^\r\n]*\r?\n", text)
                if m_stop:
                    text = text[:m_stop.end()]
                    f_reason = "stop_answer"
                    break

        mean_lp = float(np.mean(logps)) if logps else None
        min_lp = float(np.min(logps)) if logps else None
        return text, tok, f_reason or "stop", mean_lp, min_lp

    def run_arm(self, arm_name: str, item: dict) -> dict:
        query = item["query"]
        t0 = time.perf_counter()
        sc_candidates = None
        sc_vote_share = None
        tot_candidates = None
        tot_eval_scores = None

        if arm_name == "DIRECT-v2":
            user_content = query + "\nGive only the final answer directly without explanation."
            msgs = [{"role": "user", "content": user_content}]
            prompt = self.tokenizer.apply_chat_template(msgs, tokenize=False, enable_thinking=False, add_generation_prompt=True)
            prompt += "Answer: "
            p_tok = len(self.tokenizer.encode(prompt))
            sampler = self.make_sampler(temp=0.0)

            text, tok, f_reason, mean_lp, min_lp = self._generate_stream(prompt, max_tokens=24, sampler=sampler, check_stop_answer=False)
            first_line = text.strip().splitlines()[0].strip() if text.strip() else ""
            clean_first_line = first_line.replace("**", "").strip()
            parsed = extract_answer("Answer: " + clean_first_line)
            status = "marker" if parsed else "fail"
            wordy = False

        elif arm_name == "COT":
            user_content = query + COT_SUFFIX
            msgs = [{"role": "user", "content": user_content}]
            prompt = self.tokenizer.apply_chat_template(msgs, tokenize=False, enable_thinking=False, add_generation_prompt=True)
            p_tok = len(self.tokenizer.encode(prompt))
            sampler = self.make_sampler(temp=0.0)

            text, tok, f_reason, mean_lp, min_lp = self._generate_stream(prompt, max_tokens=1024, sampler=sampler, check_stop_answer=True)
            parsed, status, wordy = parse_answer_details(text)

        elif arm_name == "SC":
            user_content = query + COT_SUFFIX
            msgs = [{"role": "user", "content": user_content}]
            prompt = self.tokenizer.apply_chat_template(msgs, tokenize=False, enable_thinking=False, add_generation_prompt=True)
            p_tok = len(self.tokenizer.encode(prompt))
            sampler = self.make_sampler(temp=0.7, top_p=0.8, top_k=20)

            candidates, all_texts, total_tok = [], [], 0
            all_m_lps, all_min_lps = [], []
            f_reason = "stop"
            for _ in range(5):
                t_branch, tok_branch, fr_branch, m_lp, min_l = self._generate_stream(prompt, max_tokens=1024, sampler=sampler, check_stop_answer=True)
                ans_b, _, _ = parse_answer_details(t_branch)
                candidates.append(ans_b)
                all_texts.append(t_branch)
                total_tok += tok_branch
                if m_lp is not None:
                    all_m_lps.append(m_lp)
                if min_l is not None:
                    all_min_lps.append(min_l)
                if fr_branch == "length":
                    f_reason = "length"

            parsed, max_votes = majority_vote(candidates)
            vote_share = float(max_votes / len(candidates)) if candidates else 0.0
            text = "\n---\n".join(all_texts)
            tok = total_tok
            status = "majority" if parsed else "fail"
            wordy = False
            sc_candidates = candidates
            sc_vote_share = round(vote_share, 4)
            mean_lp = float(np.mean(all_m_lps)) if all_m_lps else None
            min_lp = min(all_min_lps) if all_min_lps else None

        elif arm_name == "TOT":
            user_content = query + COT_SUFFIX
            msgs = [{"role": "user", "content": user_content}]
            prompt = self.tokenizer.apply_chat_template(msgs, tokenize=False, enable_thinking=False, add_generation_prompt=True)
            p_tok = len(self.tokenizer.encode(prompt))

            # 3 candidate branches
            sampler_branch = self.make_sampler(temp=0.8)
            candidates, all_texts, total_tok = [], [], 0
            candidate_answers = []
            for _ in range(3):
                t_branch, tok_branch, _, _, _ = self._generate_stream(prompt, max_tokens=1024, sampler=sampler_branch, check_stop_answer=True)
                candidates.append(t_branch)
                total_tok += tok_branch
                ans_b, _, _ = parse_answer_details(t_branch)
                candidate_answers.append(ans_b)

            # Selector prompt
            listing = "\n\n".join(f"[{i}] {c}" for i, c in enumerate(candidates))
            eval_prompt = (
                f"Câu hỏi: {query}\n\nCác lời giải ứng viên:\n{listing}\n\n"
                f"Chọn lời giải đúng nhất. Chỉ trả về một trong các dòng: Best: 0, Best: 1, Best: 2."
            )
            eval_msgs = [{"role": "user", "content": eval_prompt}]
            eval_p_str = self.tokenizer.apply_chat_template(eval_msgs, tokenize=False, enable_thinking=False, add_generation_prompt=True)
            sampler_eval = self.make_sampler(temp=0.0)
            eval_text, eval_tok, _, eval_m_lp, eval_min_lp = self._generate_stream(eval_p_str, max_tokens=64, sampler=sampler_eval, check_stop_answer=False)
            total_tok += eval_tok

            import re as re_mod
            m_best = re_mod.search(r"\bBest\s*:\s*\[?([0-2])\]?", eval_text, re_mod.IGNORECASE)
            idx = int(m_best.group(1)) if m_best else 0
            best_sol = candidates[idx]
            parsed, status, wordy = parse_answer_details(best_sol)
            text = best_sol + f"\n[Selection: Best: {idx}]"
            tok = total_tok
            f_reason = "stop"
            mean_lp = eval_m_lp
            min_lp = eval_min_lp
            tot_candidates = candidate_answers
            tot_eval_scores = [1.0 if i == idx else 0.0 for i in range(len(candidates))]

        elif arm_name == "REACT":
            from qwen_mlx_backend import REACT_SYSTEM, REACT_EXAMPLE, parse_action, safe_calculate
            msgs = [{"role": "system", "content": REACT_SYSTEM}, *REACT_EXAMPLE, {"role": "user", "content": query}]
            total_tok = 0
            p_tok = len(self.tokenizer.encode(query))
            sampler = self.make_sampler(temp=0.0)
            text = ""
            parsed = ""
            f_reason = "stop"
            step_m_lps, step_min_lps = [], []

            for _ in range(4):
                prompt_r = self.tokenizer.apply_chat_template(msgs, tokenize=False, enable_thinking=False, add_generation_prompt=True)
                t_step, tok_step, _, s_m_lp, s_min_lp = self._generate_stream(prompt_r, max_tokens=200, sampler=sampler, check_stop_answer=False)
                total_tok += tok_step
                text += t_step + "\n"
                if s_m_lp is not None:
                    step_m_lps.append(s_m_lp)
                if s_min_lp is not None:
                    step_min_lps.append(s_min_lp)
                msgs.append({"role": "assistant", "content": t_step})
                act_info = parse_action(t_step)
                if act_info is None:
                    break
                act, arg = act_info
                if act == "finish":
                    parsed = extract_answer(f"Answer: {arg}") or arg
                    break
                if act == "calculate":
                    obs = safe_calculate(arg)
                    msgs.append({"role": "user", "content": f"Observation: {obs}"})
                else:
                    break

            if not parsed:
                parsed = extract_answer(text)
            tok = total_tok
            status = "react" if parsed else "fail"
            wordy = False
            mean_lp = float(np.mean(step_m_lps)) if step_m_lps else None
            min_lp = min(step_min_lps) if step_min_lps else None

        elif arm_name == "PAL":
            from qwen_mlx_backend import PAL_SUFFIX, extract_code, run_python_sandboxed
            user_content = query + PAL_SUFFIX
            msgs = [{"role": "user", "content": user_content}]
            prompt = self.tokenizer.apply_chat_template(msgs, tokenize=False, enable_thinking=False, add_generation_prompt=True)
            p_tok = len(self.tokenizer.encode(prompt))
            sampler = self.make_sampler(temp=0.0)

            text, tok, f_reason, mean_lp, min_lp = self._generate_stream(prompt, max_tokens=512, sampler=sampler, check_stop_answer=False)
            code = extract_code(text)
            ok, res = run_python_sandboxed(code)
            parsed = extract_answer(res) if ok else extract_answer(text)
            status = "pal" if ok else "pal_fail"
            wordy = False

        else:
            raise ValueError(f"Unknown arm: {arm_name}")

        wall_ms = (time.perf_counter() - t0) * 1000.0
        if f_reason == "length":
            correct = False
            status = "truncated"
        else:
            correct = bool(gen_check(item, parsed))

        return {
            "raw_output": text,
            "parsed": parsed,
            "correct": correct,
            "parse_status": status,
            "prompt_tokens": p_tok,
            "completion_tokens": tok,
            "n_tokens": tok,
            "mean_logprob": round(mean_lp, 4) if mean_lp is not None else None,
            "min_logprob": round(min_lp, 4) if min_lp is not None else None,
            "sc_candidates": sc_candidates,
            "sc_vote_share": sc_vote_share,
            "tot_candidates": tot_candidates,
            "tot_eval_scores": tot_eval_scores,
            "finish_reason": f_reason,
            "wall_ms": round(wall_ms, 2),
            "repeat": check_repeated_lines(text),
            "wordy": wordy,
        }



def main():
    ap = argparse.ArgumentParser(description="Unified reasoning sweep runner")
    ap.add_argument("--dataset", default="data/gen02_tune.json", help="Path to input dataset JSON")
    ap.add_argument("--arms", default="DIRECT-v2,COT,SC,TOT,REACT,PAL", help="Comma-separated arms")
    ap.add_argument("--out", default="audit/sweep_trace.jsonl", help="Path to output jsonl")
    ap.add_argument("--out-summary", default=None, help="Path to output summary txt")
    ap.add_argument("--max-items", type=int, default=None, help="Max items per arm (for smoke testing)")
    ap.add_argument("--item-ids", default=None, help="Comma-separated item IDs to filter")
    ap.add_argument("--model-id", default="mlx-community/Qwen3-8B-4bit")
    ap.add_argument("--snapshot-dir", default=DEFAULT_SNAPSHOT_DIR)
    ap.add_argument("--stub", action="store_true", help="Run with mock runner for offline verification")
    args = ap.parse_args()

    git_info = get_git_info()
    if not args.stub:
        assert args.model_id == "mlx-community/Qwen3-8B-4bit", f"Invalid model_id: {args.model_id}"
        assert not git_info["dirty"], f"Repository must be clean (dirty=False), got {git_info['dirty']}"
        snapshot_path = Path(args.snapshot_dir)
        assert snapshot_path.is_dir(), f"Snapshot dir not found: {snapshot_path}"
        safetensors_blobs = get_safetensors_blobs(snapshot_path)
        assert safetensors_blobs, f"No safetensors found in {snapshot_path}"
        snapshot_hash = snapshot_path.name
        runner = MLXRunner(args.model_id, snapshot_path)
    else:
        snapshot_path = Path(args.snapshot_dir)
        snapshot_hash = "stub-snapshot-545dc425"
        safetensors_blobs = {"model.safetensors": "stub-blob-f2d296"}
        runner = StubRunner(args.model_id)

    # Load dataset
    ds_path = Path(args.dataset)
    if not ds_path.is_absolute():
        ds_path = ROOT / ds_path
    with open(ds_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    items = data["items"]
    if args.item_ids:
        selected_ids = {x.strip() for x in args.item_ids.split(",") if x.strip()}
        items = [it for it in items if it["id"] in selected_ids]
    if args.max_items is not None:
        items = items[: args.max_items]

    selected_arms = [a.strip() for a in args.arms.split(",") if a.strip()]

    # Read existing records for resume support
    done_keys = set()
    records = []
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    os.makedirs(out_path.parent, exist_ok=True)

    if out_path.exists():
        with open(out_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    records.append(r)
                    done_keys.add((r.get("arm"), r.get("id")))
                except Exception:
                    pass
        print(f"Resuming: found {len(records)} existing records in {out_path}")

    with open(out_path, "a", encoding="utf-8") as jf:
        for arm_name in selected_arms:
            arm_items = [
                it for it in items
                if not (arm_name == "DIRECT-v2" and it["family"] not in ("arith", "order"))
            ]
            print(f"\n=== Executing Arm: {arm_name} ({len(arm_items)} items) ===")
            for idx, it in enumerate(arm_items, 1):
                key = (arm_name, it["id"])
                if key in done_keys:
                    continue

                res = runner.run_arm(arm_name, it)
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
                    "eos_token_ids": runner.eos_ids,
                    "enable_thinking": False,
                    "gold": it["answer"],
                    "branch": git_info["branch"],
                    "tag": git_info["tag"],
                    "commit": git_info["commit"],
                    "dirty": git_info["dirty"],
                    **res,
                }
                records.append(rec)
                done_keys.add(key)
                jf.write(json.dumps(rec, ensure_ascii=False) + "\n")
                jf.flush()
                print(f"  [{idx}/{len(items)}] {it['id']} -> parsed: {res['parsed']!r} (ok={res['correct']}, tok={res['completion_tokens']})")

    print(f"\nDone. Total records in {out_path}: {len(records)}")


if __name__ == "__main__":
    main()
