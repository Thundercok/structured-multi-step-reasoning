"""Audit complete pilot records and describe paired strategy/budget outcomes."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from experiments.research_pilot import sha256_file, verify_replay
from experiments.research_study import check_answer, write_json
from research_scoring import parse_typed_answer


def validate_records(dataset, records):
    items = {item["id"]: item for item in dataset["items"]}
    for row in records:
        item = items[row["id"]]
        if row["group_id"] != item["group_id"] or row["split"] != item["split"]:
            raise ValueError("Pilot record group/split differs from its frozen dataset")
        generations = row["trace"]["generations"]
        if row["strategy"] not in ("DIRECT", "COT") or len(generations) != 1:
            raise ValueError("This paired analysis requires single-call DIRECT and COT records")
        generation = generations[0]
        if row["tokens"] != generation["tokens"] or not 0 < row["tokens"] <= generation["max_tokens"] <= row["token_budget"]:
            raise ValueError("Recorded token cost or cap differs from actual generation")
        if not math.isfinite(row["strategy_ms"]) or row["strategy_ms"] < 0:
            raise ValueError("Recorded strategy duration must be finite/nonnegative")
        parsed = parse_typed_answer(generation["output"], **row["answer_format"])[0]
        if parsed != row["answer"]:
            raise ValueError("Recorded answer differs from typed parsing of its raw output")
        if type(row["correct"]) is not bool or row["correct"] != bool(check_answer(parsed, item)):
            raise ValueError("Recorded correctness differs from rescoring against frozen gold")


def metrics(rows):
    n = len(rows)
    return {"items": n, "groups": len({row["group_id"] for row in rows}),
            "correct": sum(row["correct"] for row in rows),
            "accuracy": sum(row["correct"] for row in rows) / n,
            "mean_generated_tokens": sum(row["tokens"] for row in rows) / n,
            "mean_prompt_tokens": sum(row["trace"]["generations"][0]["prompt_tokens"] for row in rows) / n,
            "mean_strategy_ms": sum(row["strategy_ms"] for row in rows) / n,
            "parse_failures": sum(row["trace"].get("parse_status") == "fail" for row in rows),
            "length_stops": sum(row["trace"]["generations"][0]["finish_reason"] == "length" for row in rows)}


def paired(before, after):
    left, right = {row["id"]: row for row in before}, {row["id"]: row for row in after}
    if len(left) != len(before) or len(right) != len(after) or left.keys() != right.keys():
        raise ValueError("Paired conditions require identical, unique question IDs")
    pairs = [(left[key], right[key]) for key in sorted(left)]
    n = len(pairs)
    return {"items": n, "groups": len({a["group_id"] for a, _ in pairs}),
            "both_correct": sum(a["correct"] and b["correct"] for a, b in pairs),
            "became_correct": sum(not a["correct"] and b["correct"] for a, b in pairs),
            "became_incorrect": sum(a["correct"] and not b["correct"] for a, b in pairs),
            "both_incorrect": sum(not a["correct"] and not b["correct"] for a, b in pairs),
            "mean_accuracy_difference": sum(int(b["correct"]) - int(a["correct"]) for a, b in pairs) / n,
            "mean_generated_token_difference": sum(b["tokens"] - a["tokens"] for a, b in pairs) / n}


def summarize(records):
    budgets = sorted({row["token_budget"] for row in records})
    if len(budgets) != 2 or {row["strategy"] for row in records} != {"DIRECT", "COT"}:
        raise ValueError("Paired pilot requires two caps and both DIRECT/COT")
    families = sorted({row["family"] for row in records})
    aggregates, strategy_pairs, budget_pairs = [], [], []
    for family in [None, *families]:
        selected = [row for row in records if family is None or row["family"] == family]
        for budget in budgets:
            for strategy in ("DIRECT", "COT"):
                rows = [row for row in selected if row["token_budget"] == budget and row["strategy"] == strategy]
                aggregates.append({"family": family or "all", "cap_per_call": budget,
                                   "strategy": strategy, **metrics(rows)})
            left = [row for row in selected if row["token_budget"] == budget and row["strategy"] == "DIRECT"]
            right = [row for row in selected if row["token_budget"] == budget and row["strategy"] == "COT"]
            strategy_pairs.append({"family": family or "all", "cap_per_call": budget,
                                   "comparison": "COT minus DIRECT", **paired(left, right)})
        for strategy in ("DIRECT", "COT"):
            left = [row for row in selected if row["strategy"] == strategy and row["token_budget"] == budgets[0]]
            right = [row for row in selected if row["strategy"] == strategy and row["token_budget"] == budgets[1]]
            budget_pairs.append({"family": family or "all", "strategy": strategy,
                                 "comparison": f"cap {budgets[1]} minus cap {budgets[0]}", **paired(left, right)})
    return {"descriptive_only": True, "policy_fitted": False, "aggregates": aggregates,
            "paired_strategy_differences": strategy_pairs, "paired_cap_differences": budget_pairs,
            "failures": [{key: row[key] for key in ("id", "strategy", "token_budget", "answer", "confidence", "tokens")}
                         for row in records if not row["correct"]]}


def report(manifest, summary):
    lines = ["# Paired development pilot diagnostics", "", f"Evidence: **{manifest['evidence']}**", "",
        "Exposed development data, one generation seed, two fixed strategies and two per-call caps. Human/publication review remains pending.",
        "Synthetic inputs validate software only. Measured generated tokens exclude prefill/full inference cost; strategy duration excludes model loading and online controller scheduling.",
        "DIRECT uses a Vietnamese suffix and CoT an English suffix. Strategy differences include prompt-language effects; matched caps do not establish instruction-only causality.",
        "Questions/variants and groups are counted separately. No significance, superiority, calibrated difficulty or parameter freeze is inferred.", "",
        "| Family | Cap/call | Strategy | Correct/items | Groups | Mean generated tokens | Mean prompt tokens | Parse failures | Length stops |",
        "| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in summary["aggregates"]:
        lines.append(f"| {row['family']} | {row['cap_per_call']} | {row['strategy']} | {row['correct']}/{row['items']} | {row['groups']} | {row['mean_generated_tokens']:.1f} | {row['mean_prompt_tokens']:.1f} | {row['parse_failures']} | {row['length_stops']} |")
    lines.extend(["", "## Paired outcomes at the same cap", "",
        "Became correct/incorrect describe switching from DIRECT to CoT on the same question.", "",
        "| Family | Cap/call | Items | Both correct | Became correct | Became incorrect | Both incorrect | Mean token change |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for row in summary["paired_strategy_differences"]:
        lines.append(f"| {row['family']} | {row['cap_per_call']} | {row['items']} | {row['both_correct']} | {row['became_correct']} | {row['became_incorrect']} | {row['both_incorrect']} | {row['mean_generated_token_difference']:.1f} |")
    lines.extend(["", "## Increasing the cap within each strategy", "",
        "| Family | Strategy | Items | Became correct | Became incorrect | Mean token change |",
        "| --- | --- | ---: | ---: | ---: | ---: |"])
    for row in summary["paired_cap_differences"]:
        lines.append(f"| {row['family']} | {row['strategy']} | {row['items']} | {row['became_correct']} | {row['became_incorrect']} | {row['mean_generated_token_difference']:.1f} |")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError(args.output)
    manifest = json.loads((args.run / "manifest.json").read_text())
    dataset, records, _ = verify_replay(args.run, manifest)
    validate_records(dataset, records)
    summary = summarize(records)
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output / "summary.json", summary)
    (args.output / "report.md").write_text(report(manifest, summary), encoding="utf-8")
    write_json(args.output / "manifest.json", {
        "kind": "paired_development_pilot_analysis", "status": "complete",
        "recorded_utc": datetime.now(timezone.utc).isoformat(), "evidence": manifest["evidence"],
        "input_manifest_sha256": sha256_file(args.run / "manifest.json"),
        "collection_source_sha256": manifest["source_sha256"], "analysis_source_sha256": sha256_file(Path(__file__)),
        "recorded_answers_tokens_and_scores_reverified": len(records),
        "publication_ready": False, "model_calls": 0, "policy_fitted": False,
        "artifact_sha256": {name: sha256_file(args.output / name) for name in ("summary.json", "report.md")},
    })
    print(str(args.output / "report.md"))


if __name__ == "__main__":
    main()
