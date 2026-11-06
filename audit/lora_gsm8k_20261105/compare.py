"""Table for this run: rates with Wilson 95% intervals, and paired exact McNemar against base_prefill.

Run from the repo root: PYTHONPATH=. .venv/bin/python audit/lora_gsm8k_20261105/compare.py
Rescores the saved outputs with the current checks, like structured_llm.analyze.
"""

import collections
import json
from pathlib import Path

from structured_llm.analyze import exact_mcnemar, wilson
from structured_llm.evaluate import read_jsonl, score

RUN = Path(__file__).parent
SOURCES = {
    "tuned (plain)": RUN / "eval_plain/tuned.jsonl",
    "tuned_cf": RUN / "eval_cf/tuned.jsonl",
    "base_prefill": RUN / "eval_base/base_prefill.jsonl",
    "base_instructed": RUN / "eval_base/base_instructed.jsonl",
    "base_showcalc": RUN / "eval_base/base_showcalc.jsonl",
}
MODE = {"base_prefill": "base_prefill", "base_instructed": "base_instructed", "base_showcalc": "base_showcalc"}


def load(name):
    rows = read_jsonl(SOURCES[name])
    for row in rows:
        row["check"] = score(MODE.get(name, "tuned"), row["output"], row["question"], row["gold"])
    return {row["id"]: row for row in rows}


def main():
    runs = {name: load(name) for name in SOURCES}
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
            "correct": correct, "correct_ci": wilson(correct, n),
            "format_valid": valid, "format_valid_ci": wilson(valid, n),
            "vs_base_prefill": {"only_this_correct": only_this, "only_base_correct": only_base,
                                "mcnemar_p": None if name == "base_prefill" else exact_mcnemar(only_this, only_base)},
            "mean_tokens": round(sum(rows[i]["tokens"] for i in ids) / n, 1),
            "truncated": sum(rows[i]["truncated"] for i in ids),
            "format_errors": dict(errors.most_common()),
        }
    plain, cf = runs["tuned (plain)"], runs["tuned_cf"]
    table["tuned (plain) vs tuned_cf"] = {
        "only_plain_correct": sum(bool(plain[i]["check"]["correct"]) and not cf[i]["check"]["correct"] for i in ids),
        "only_cf_correct": sum(bool(cf[i]["check"]["correct"]) and not plain[i]["check"]["correct"] for i in ids),
        "only_plain_valid": sum(plain[i]["check"]["format_valid"] and not cf[i]["check"]["format_valid"] for i in ids),
        "only_cf_valid": sum(cf[i]["check"]["format_valid"] and not plain[i]["check"]["format_valid"] for i in ids),
    }
    pair = table["tuned (plain) vs tuned_cf"]
    pair["correct_mcnemar_p"] = exact_mcnemar(pair["only_plain_correct"], pair["only_cf_correct"])
    pair["format_mcnemar_p"] = exact_mcnemar(pair["only_plain_valid"], pair["only_cf_valid"])
    (RUN / "comparison.json").write_text(json.dumps(table, indent=2) + "\n")
    print(json.dumps(table, indent=2))


if __name__ == "__main__":
    main()
