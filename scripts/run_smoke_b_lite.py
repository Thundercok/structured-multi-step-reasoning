import json
import os
import random
import sys
import time
from decimal import Decimal, InvalidOperation

from experiments.research_study import check_answer
from qwen_mlx_backend import QwenMLXBackend
from reasoning_env import ReasoningAction as A

REPO = "mlx-community/Qwen2.5-0.5B-Instruct-4bit"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_PATH = os.path.join(ROOT, "data", "nckh_reasoning_dataset_draft.json")
JSONL_PATH = os.path.join(ROOT, "audit", "B_smoke_trace.jsonl")

ARMS = [
    ("DIRECT", A.DIRECT),
    ("COT", A.COT),
    ("SC", A.SELF_CONSISTENCY),
    ("TOT", A.TOT),
    ("REACT", A.REACT),
    ("PAL", A.PAL),
]

def main():
    print(f"=== INITIALIZING MODEL {REPO} ===")
    backend = QwenMLXBackend(repo=REPO, max_tokens=512)
    print("Model initialized successfully on Apple Silicon.")

    # 1. Load dataset & pick 3 groups with seed=0
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    train_items = [it for it in dataset["items"] if it.get("split") == "train"]
    dev_group_ids = sorted(list(set(it["group_id"] for it in train_items)))
    rng = random.Random(0)
    selected_groups = sorted(rng.sample(dev_group_ids, 3))
    print(f"\nSelected 3 groups (seed=0): {selected_groups}")

    smoke_items = [it for it in train_items if it["group_id"] in selected_groups]
    smoke_items.sort(key=lambda x: (x["group_id"], x["id"]))
    print(f"Total smoke items: {len(smoke_items)} items across 3 groups (3 variants each).")
    for it in smoke_items:
        print(f"  [{it['group_id']}] {it['id']} (type: {it['answer_type']}, gold: {it['answer']})")

    # 2. Run smoke benchmark across 6 arms
    os.makedirs(os.path.join(ROOT, "audit"), exist_ok=True)
    records = []

    print("\n=== RUNNING SMOKE INFERENCE (6 ARMS × 9 ITEMS = 54 EVALUATIONS) ===")
    with open(JSONL_PATH, "w", encoding="utf-8") as jf:
        for arm_name, action in ARMS:
            print(f"\n--- Arm: {arm_name} ---")
            for idx, item in enumerate(smoke_items, 1):
                t0 = time.perf_counter()
                ans, conf, tok = backend.run(action, item["query"])
                wall_ms = (time.perf_counter() - t0) * 1000.0

                generations = backend.last_trace.get("generations", [])
                n_calls = len(generations)
                raw_output = "\n---\n".join(g["output"] for g in generations)
                final_gen = generations[-1] if generations else {}
                finish_reason = final_gen.get("finish_reason") or "stop"
                prompt_tokens = sum(g.get("prompt_tokens", 0) for g in generations)
                completion_tokens = tok

                parsed = ans
                gold = item["answer"]
                correct = check_answer(parsed, item)

                rec = {
                    "id": item["id"],
                    "group_id": item["group_id"],
                    "arm": arm_name,
                    "raw_output": raw_output,
                    "finish_reason": finish_reason,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "n_calls": n_calls,
                    "wall_ms": round(wall_ms, 2),
                    "parsed": parsed,
                    "gold": gold,
                    "correct": bool(correct),
                }
                records.append(rec)
                jf.write(json.dumps(rec, ensure_ascii=False) + "\n")
                jf.flush()
                print(f"  [{idx}/9] {item['id']} -> parsed: {parsed!r} | gold: {gold!r} | correct: {correct} ({wall_ms:.1f}ms, {tok} tok, calls: {n_calls})")

    print(f"\nSaved {len(records)} trace records to {JSONL_PATH}")

    # 3. Step 5: Summary Table
    print("\n" + "=" * 80)
    print("=== SMOKE BENCHMARK RESULTS TABLE ===")
    print("=" * 80)

    table_header = "| arm | acc strict | #parse fail | % max_tokens | tokens | wall_ms |"
    table_sep    = "| --- | --- | --- | --- | --- | --- |"
    print(table_header)
    print(table_sep)

    arm_records_map = {}
    for arm_name, _ in ARMS:
        arm_recs = [r for r in records if r["arm"] == arm_name]
        arm_records_map[arm_name] = arm_recs
        n = len(arm_recs)
        n_correct = sum(1 for r in arm_recs if r["correct"])
        acc_strict = f"{n_correct / n:.1%}" if n > 0 else "0.0%"
        parse_fail = sum(1 for r in arm_recs if not r["parsed"] or not str(r["parsed"]).strip())
        max_tokens_count = sum(1 for r in arm_recs if r["finish_reason"] == "length")
        pct_max_tokens = f"{max_tokens_count / n:.1%}" if n > 0 else "0.0%"
        mean_tokens = f"{sum(r['completion_tokens'] for r in arm_recs) / n:.1f}" if n > 0 else "0.0"
        mean_wall_ms = f"{sum(r['wall_ms'] for r in arm_recs) / n:.1f}" if n > 0 else "0.0"

        print(f"| {arm_name} | {acc_strict} ({n_correct}/{n}) | {parse_fail} | {pct_max_tokens} | {mean_tokens} | {mean_wall_ms} |")

    # 4. Under Table: 3 Random Items per Arm
    print("\n" + "=" * 80)
    print("=== 3 RAW SAMPLES PER ARM (RANDOM SEED = 0) ===")
    print("=" * 80)

    for arm_name, _ in ARMS:
        arm_recs = arm_records_map[arm_name]
        arm_sample = random.Random(0).sample(arm_recs, min(3, len(arm_recs)))
        print(f"\n--- Arm: {arm_name} (3 samples) ---")
        for s_idx, r in enumerate(arm_sample, 1):
            raw_tail = r["raw_output"][-300:].replace("\n", "\\n")
            print(f"  Sample {s_idx}:")
            print(f"    id: {r['id']}")
            print(f"    raw_tail (last 300 chars): {raw_tail}")
            print(f"    parsed: {r['parsed']!r}")
            print(f"    gold: {r['gold']!r}")
            print(f"    correct: {r['correct']}")

if __name__ == "__main__":
    main()
