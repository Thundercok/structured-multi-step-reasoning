"""Table for the enriched GSM8K training run:
Rates with Wilson 95% intervals, and paired exact McNemar against base_prefill and old cf adapter.

Run from the repo root:
PYTHONPATH=. .venv/bin/python audit/lora_gsm8k_enriched_20261107/compare.py
"""

import collections
import json
from pathlib import Path

from structured_llm.analyze import exact_mcnemar, wilson
from structured_llm.evaluate import read_jsonl, score

DIR = Path(__file__).parent
OLD_DIR = Path("audit/lora_gsm8k_20261105")

SOURCES = {
    "enriched_plain": DIR / "eval_plain/tuned.jsonl",
    "enriched_plain_tool": DIR / "eval_plain/tuned_tool.jsonl",
    "enriched_cf": DIR / "eval_cf/tuned.jsonl",
    "enriched_cf_tool": DIR / "eval_cf/tuned_tool.jsonl",
    "old_plain": OLD_DIR / "eval_plain/tuned.jsonl",
    "old_cf": OLD_DIR / "eval_cf/tuned.jsonl",
    "base_prefill": OLD_DIR / "eval_base/base_prefill.jsonl",
}

MODE = {
    "base_prefill": "base_prefill",
    "enriched_plain": "tuned",
    "enriched_plain_tool": "tuned_tool",
    "enriched_cf": "tuned",
    "enriched_cf_tool": "tuned_tool",
    "old_plain": "tuned",
    "old_cf": "tuned",
}


def load(name):
    path = SOURCES[name]
    if not path.exists():
        return None
    rows = read_jsonl(path)
    for row in rows:
        row["check"] = score(MODE.get(name, "tuned"), row["output"], row["question"], row["gold"])
    return {row["id"]: row for row in rows}


def main():
    runs = {}
    for name in SOURCES:
        data = load(name)
        if data:
            runs[name] = data

    if "base_prefill" not in runs:
        print("base_prefill not found, exiting.")
        return

    ids = set.intersection(*(set(rows) for rows in runs.values()))
    base = runs["base_prefill"]
    table = {}

    for name, rows in runs.items():
        n = len(ids)
        correct = sum(bool(rows[i]["check"]["correct"]) for i in ids)
        valid = sum(rows[i]["check"]["format_valid"] for i in ids)
        only_this = sum(bool(rows[i]["check"]["correct"]) and not base[i]["check"]["correct"] for i in ids)
        only_base = sum(bool(base[i]["check"]["correct"]) and not rows[i]["check"]["correct"] for i in ids)
        errors = collections.Counter(e for i in ids for e in rows[i]["check"]["errors"])
        table[name] = {
            "n": n,
            "correct": correct,
            "correct_ci": wilson(correct, n),
            "format_valid": valid,
            "format_valid_ci": wilson(valid, n),
            "vs_base_prefill": {
                "only_this_correct": only_this,
                "only_base_correct": only_base,
                "mcnemar_p": None if name == "base_prefill" else exact_mcnemar(only_this, only_base),
            },
            "mean_tokens": round(sum(rows[i]["tokens"] for i in ids) / n, 1),
            "truncated": sum(rows[i]["truncated"] for i in ids),
            "format_errors": dict(errors.most_common()),
        }

    if "enriched_cf" in runs and "old_cf" in runs:
        new_cf, old_cf = runs["enriched_cf"], runs["old_cf"]
        table["enriched_cf vs old_cf"] = {
            "only_new_correct": sum(bool(new_cf[i]["check"]["correct"]) and not old_cf[i]["check"]["correct"] for i in ids),
            "only_old_correct": sum(bool(old_cf[i]["check"]["correct"]) and not new_cf[i]["check"]["correct"] for i in ids),
            "only_new_valid": sum(new_cf[i]["check"]["format_valid"] and not old_cf[i]["check"]["format_valid"] for i in ids),
            "only_old_valid": sum(old_cf[i]["check"]["format_valid"] and not new_cf[i]["check"]["format_valid"] for i in ids),
        }

    out_file = DIR / "comparison.json"
    out_file.write_text(json.dumps(table, indent=2) + "\n")
    print(f"Summary written to {out_file}")
    print(json.dumps(table, indent=2))


if __name__ == "__main__":
    main()
