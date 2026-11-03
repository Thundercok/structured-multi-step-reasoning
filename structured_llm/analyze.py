"""Summarize a run from its raw outputs, rescoring them with the current checks.

Run: python -m structured_llm.analyze audit/run --baseline base_instructed

Pairs modes on the same questions. Counts are for reading, not for claims: a small run gives
wide intervals, and a threshold chosen after seeing these numbers is not a test of anything.
"""

import argparse
import json
from math import comb, sqrt
from pathlib import Path

from .evaluate import MODES, is_flagged, read_jsonl, score


def wilson(hits, total, z=1.96):
    """95% Wilson interval, or None when there is nothing to measure."""
    if not total:
        return None
    rate = hits / total
    denominator = 1 + z * z / total
    centre = (rate + z * z / (2 * total)) / denominator
    margin = z * sqrt(rate * (1 - rate) / total + z * z / (4 * total * total)) / denominator
    return round(max(0.0, centre - margin), 3), round(min(1.0, centre + margin), 3)


def exact_mcnemar(only_a, only_b):
    """Two-sided exact p-value from the discordant pairs."""
    total = only_a + only_b
    if not total:
        return 1.0
    tail = sum(comb(total, k) for k in range(min(only_a, only_b) + 1)) / 2**total
    return round(min(1.0, 2 * tail), 4)


def load_mode(run_dir, mode):
    records = {}
    for record in read_jsonl(Path(run_dir) / f"{mode}.jsonl"):
        record["check"] = score(mode, record["output"], record["question"], record["gold"],
                                record.get("answer_format", "number"))
        records[record["id"]] = record
    return records


def describe(records):
    rows = list(records.values())
    wrong = [row for row in rows if not row["check"]["correct"]]
    right = [row for row in rows if row["check"]["correct"]]
    caught, false_alarms = (sum(is_flagged(row["check"]) for row in group) for group in (wrong, right))
    # "Clean but vacuous" outputs pass every check while possibly checking nothing.
    vacuous = sum(not is_flagged(row["check"]) and (row["check"]["vacuous_rate"] or 0) > 0 for row in rows)
    return {
        "n": len(rows),
        "correct": len(right),
        "correct_ci": wilson(len(right), len(rows)),
        "format_valid": sum(row["check"]["format_valid"] for row in rows),
        "format_valid_ci": wilson(sum(row["check"]["format_valid"] for row in rows), len(rows)),
        "mean_tokens": round(sum(row["tokens"] for row in rows) / max(len(rows), 1), 1),
        "truncated": sum(row["truncated"] for row in rows),
        "caught_wrong": f"{caught}/{len(wrong)}",
        "caught_wrong_ci": wilson(caught, len(wrong)),
        "false_alarm_right": f"{false_alarms}/{len(right)}",
        "false_alarm_ci": wilson(false_alarms, len(right)),
        "clean_with_vacuous_calc": vacuous,
    }


def compare(records, baseline):
    """Accuracy of a mode against a baseline, on the questions both have answered."""
    shared = records.keys() & baseline.keys()
    only_mode = sum(records[key]["check"]["correct"] and not baseline[key]["check"]["correct"] for key in shared)
    only_base = sum(baseline[key]["check"]["correct"] and not records[key]["check"]["correct"] for key in shared)
    return {"shared": len(shared), "only_this_correct": only_mode, "only_baseline_correct": only_base,
            "mcnemar_p": exact_mcnemar(only_mode, only_base)}


def analyze(run_dir, baseline_mode):
    modes = {mode: load_mode(run_dir, mode) for mode in MODES}
    modes = {mode: records for mode, records in modes.items() if records}
    report = {mode: describe(records) for mode, records in modes.items()}
    if baseline_mode in modes:
        for mode, records in modes.items():
            if mode != baseline_mode:
                report[mode][f"vs_{baseline_mode}"] = compare(records, modes[baseline_mode])
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run")
    parser.add_argument("--baseline", default="base_instructed")
    args = parser.parse_args()
    print(json.dumps(analyze(args.run, args.baseline), indent=2))
