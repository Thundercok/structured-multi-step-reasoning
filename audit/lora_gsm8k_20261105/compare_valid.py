"""Checkpoint noise check on valid_eval.jsonl, read by the rule in README.md.

Run from the repo root: PYTHONPATH=. .venv/bin/python audit/lora_gsm8k_20261105/compare_valid.py
Rescores the saved outputs with the current checks.
"""

import json
from pathlib import Path

from structured_llm.analyze import exact_mcnemar, wilson
from structured_llm.evaluate import read_jsonl, score

RUN = Path(__file__).parent / "valid"
ADAPTERS = ("gsm8k_plain_2000_s0", "gsm8k_cf_2000_s0")
CHECKPOINTS = (1000, 1500, 2000)
MAX_RANGE = 5


def load(path, mode):
    rows = read_jsonl(path)
    for row in rows:
        row["check"] = score(mode, row["output"], row["question"], row["gold"])
    return {row["id"]: row for row in rows}


def sign(value):
    return (value > 0) - (value < 0)


def main():
    base = load(RUN / "base/base_prefill.jsonl", "base_prefill")
    ids = sorted(base)
    right = lambda rows, i: bool(rows[i]["check"]["correct"])
    base_correct = sum(right(base, i) for i in ids)
    table = {"base_prefill": {
        "correct": base_correct, "correct_ci": wilson(base_correct, len(ids)),
        "format_valid": sum(base[i]["check"]["format_valid"] for i in ids),
    }}
    for adapter in ADAPTERS:
        gaps = []
        for checkpoint in CHECKPOINTS:
            rows = load(RUN / f"{adapter}_it{checkpoint}/tuned.jsonl", "tuned")
            assert sorted(rows) == ids
            correct = sum(right(rows, i) for i in ids)
            valid = sum(rows[i]["check"]["format_valid"] for i in ids)
            only_tuned = sum(right(rows, i) and not right(base, i) for i in ids)
            only_base = sum(right(base, i) and not right(rows, i) for i in ids)
            gaps.append(correct - base_correct)
            table[f"{adapter}_it{checkpoint}"] = {
                "correct": correct, "correct_ci": wilson(correct, len(ids)),
                "format_valid": valid, "format_valid_ci": wilson(valid, len(ids)),
                "gap_vs_base_prefill": correct - base_correct,
                "only_tuned_correct": only_tuned, "only_base_correct": only_base,
                "mcnemar_p": exact_mcnemar(only_tuned, only_base),
                "truncated": sum(rows[i]["truncated"] for i in ids),
            }
        flips = len({sign(gap) for gap in gaps}) > 1
        spread = max(gaps) - min(gaps)
        table[f"{adapter}_rule"] = {
            "gaps": gaps, "sign_changes": flips, "range": spread,
            "reading": ("not explained by data: checkpoint noise is large enough" if flips or spread > MAX_RANGE
                        else "stable gap"),
        }
    (RUN / "comparison_valid.json").write_text(json.dumps(table, indent=2) + "\n")
    print(json.dumps(table, indent=2))


if __name__ == "__main__":
    main()
