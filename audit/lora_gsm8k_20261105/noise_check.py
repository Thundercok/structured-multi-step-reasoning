"""Apply the checkpoint noise rule recorded in README.md before scoring.

Run from the repo root: PYTHONPATH=. .venv/bin/python audit/lora_gsm8k_20261105/noise_check.py
Written 2026-11-06 before the it2000 runs on valid finished. Rescores saved outputs with the
current checks, like compare.py.

Rule, per adapter: gap = correct(checkpoint) - correct(base_prefill) on the same 99 questions.
If the gap changes sign across checkpoints 1000/1500/2000, or max - min > 5, the dev gap is not yet
explained by data. Otherwise the gap is stable. Sign means negative, zero or positive.
Reported alongside, not used for the reading: format_valid, Wilson 95%, paired McNemar.
"""

import json
from pathlib import Path

from structured_llm.analyze import exact_mcnemar, wilson
from structured_llm.evaluate import read_jsonl, score

RUN = Path(__file__).parent
VALID = RUN / "valid"
ADAPTERS = ["gsm8k_plain_2000_s0", "gsm8k_cf_2000_s0"]
CHECKPOINTS = [1000, 1500, 2000]
N = 99
SPREAD_LIMIT = 5


def load(path, mode):
    rows = read_jsonl(path)
    for row in rows:
        row["check"] = score(mode, row["output"], row["question"], row["gold"])
    return {row["id"]: row for row in rows}


def sign(x):
    return (x > 0) - (x < 0)


def main():
    base = load(VALID / "base/base_prefill.jsonl", "base_prefill")
    assert len(base) == N, f"base_prefill has {len(base)} rows"
    base_correct = sum(bool(r["check"]["correct"]) for r in base.values())
    result = {"base_prefill": {"correct": base_correct, "correct_ci": wilson(base_correct, N),
                               "format_valid": sum(r["check"]["format_valid"] for r in base.values())}}
    for adapter in ADAPTERS:
        rows_by_it = {}
        for it in CHECKPOINTS:
            rows = load(VALID / f"{adapter}_it{it}/tuned.jsonl", "tuned")
            assert len(rows) == N and set(rows) == set(base), f"{adapter} it{it}: {len(rows)} rows"
            rows_by_it[it] = rows
        table = {}
        for it, rows in rows_by_it.items():
            correct = sum(bool(r["check"]["correct"]) for r in rows.values())
            valid = sum(r["check"]["format_valid"] for r in rows.values())
            only_this = sum(bool(rows[i]["check"]["correct"]) and not base[i]["check"]["correct"] for i in base)
            only_base = sum(bool(base[i]["check"]["correct"]) and not rows[i]["check"]["correct"] for i in base)
            table[it] = {
                "correct": correct, "correct_ci": wilson(correct, N),
                "gap": correct - base_correct,
                "format_valid": valid, "format_valid_ci": wilson(valid, N),
                "only_this_correct": only_this, "only_base_correct": only_base,
                "mcnemar_p": exact_mcnemar(only_this, only_base),
                "truncated": sum(r["truncated"] for r in rows.values()),
            }
        gaps = [table[it]["gap"] for it in CHECKPOINTS]
        sign_change = len({sign(g) for g in gaps}) > 1
        spread = max(gaps) - min(gaps)
        unexplained = sign_change or spread > SPREAD_LIMIT
        result[adapter] = {
            "checkpoints": table,
            "gaps": gaps, "sign_change": sign_change, "spread": spread,
            "reading": "dev gap not yet explained by data (checkpoint noise large enough)" if unexplained
            else "gap stable across checkpoints",
        }
    (RUN / "noise_check.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
