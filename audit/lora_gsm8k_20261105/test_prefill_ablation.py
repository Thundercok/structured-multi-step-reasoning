"""Test whether prefilling "Step 1: Calculate the " fixes the 19 dev questions

Run: PYTHONPATH=. .venv/bin/python audit/lora_gsm8k_20261105/test_prefill_ablation.py
"""

import json
import time
from pathlib import Path
from mlx_lm import load, generate
from mlx_lm.sample_utils import make_sampler

from structured_llm.evaluate import model_path, chatml_prompt
from structured_llm.trace import check

DEV_FILE = Path("data/structured_gsm8k_v1/dev.jsonl")
ADAPTER = Path("adapters/gsm8k_cf_2000_s0")

# The 19 failing IDs identified in error_reading.md
FAILING_IDS = [
    "038474b6", "04163f5a", "04222269", "045a4b9c", "0490d526",
    "0535a2bf", "0556de23", "0557ecbe", "05846387", "059e1768",
    "05fb4a91", "069d0428", "04483c31", "0483a43e", "04d03ed7",
    "0533264e", "056e151c", "0587b07c", "05e8ecc8"
]

PREFILL = "<think>\nStep 1: Calculate the "


def main():
    items = [json.loads(line) for line in DEV_FILE.read_text().splitlines()]
    failing_items = [it for it in items if any(it["id"].startswith(fid) for fid in FAILING_IDS)]
    print(f"Loaded {len(failing_items)} target failing questions.")

    print(f"Loading model with adapter {ADAPTER}...")
    path = model_path()
    model, tokenizer = load(path, adapter_path=str(ADAPTER))
    sampler = make_sampler(temp=0.0)

    results = []
    recovered = 0

    for i, it in enumerate(failing_items, 1):
        prompt = chatml_prompt(it["question"]) + PREFILL
        start = time.perf_counter()
        continuation = generate(model, tokenizer, prompt=prompt, max_tokens=1024, sampler=sampler, verbose=False)
        output = PREFILL + continuation
        elapsed = time.perf_counter() - start

        score = check(output, it["question"], it["answer"])
        is_correct = bool(score["correct"])
        if is_correct:
            recovered += 1

        res = {
            "id": it["id"],
            "gold": it["answer"],
            "correct": is_correct,
            "format_valid": score["format_valid"],
            "seconds": round(elapsed, 2),
            "output": output
        }
        results.append(res)
        print(f"[{i}/{len(failing_items)}] {it['id']}: Correct={is_correct} (Gold: {it['answer']}, Found: {score.get('answer')})")

    out_file = Path("audit/lora_gsm8k_20261105/prefill_ablation_results.json")
    out_file.write_text(json.dumps({
        "total": len(failing_items),
        "recovered": recovered,
        "recovered_rate": round(recovered / len(failing_items), 4),
        "results": results
    }, indent=2) + "\n")

    print("\n" + "=" * 50)
    print(f"SUMMARY: Recovered {recovered}/{len(failing_items)} ({recovered / len(failing_items) * 100:.1f}%) questions")
    print(f"Results written to {out_file}")


if __name__ == "__main__":
    main()
