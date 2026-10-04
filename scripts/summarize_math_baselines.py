"""Audit a frozen English DIRECT/CoT/PAL development pilot, without model calls."""

import argparse
import itertools
import json
import math
from pathlib import Path

from experiments.research_pilot import sha256_file, verify_replay
from experiments.research_study import check_answer, write_json
from reasoning_strategies import extract_code
from research_scoring import parse_typed_answer


def summarize(dataset, records, manifest):
    if manifest.get("prompt_profile") != "english-math-v1" or set(manifest["strategies"]) != {"DIRECT", "COT", "PAL"}:
        raise ValueError("Expected the English fixed math strategies")
    from qwen_mlx_backend import MATH_EN_SUFFIXES
    from reasoning_env import ReasoningAction
    items = {item["id"]: item for item in dataset["items"]}
    for row in records:
        item = items[row["id"]]
        trace = row["trace"]
        if row["group_id"] != item["group_id"] or row["split"] != item["split"] or trace["prompt_profile"] != "english-math-v1":
            raise ValueError("Record identity/profile differs from frozen input")
        generations = trace["generations"]
        if len(generations) != 1:
            raise ValueError("This pilot declares exactly one generation per condition")
        generation = generations[0]
        suffix = MATH_EN_SUFFIXES[ReasoningAction[row["strategy"]]]
        if generation["messages"] != [{"role": "user", "content": item["query"] + suffix}]:
            raise ValueError("Prompt differs from the frozen label-free query and suffix")
        if generation["temperature"] != 0 or generation["enable_thinking"] is not False:
            raise ValueError("Decoder differs from the declared pilot")
        if row["tokens"] != generation["tokens"] or not 0 < row["tokens"] <= generation["max_tokens"] <= row["token_budget"]:
            raise ValueError("Token cost/cap differs from the raw generation")
        if not math.isfinite(row["strategy_ms"]) or row["strategy_ms"] < 0:
            raise ValueError("Strategy duration is invalid")
        text = generation["output"]
        if row["strategy"] == "PAL":
            if len(trace["tools"]) != 1:
                raise ValueError("PAL requires one recorded execution attempt")
            event = trace["tools"][0]
            if event["name"] != "python" or event["input"] != extract_code(text) or type(event["ok"]) is not bool:
                raise ValueError("Execution event differs from generated code")
            if not math.isfinite(event["duration_ms"]) or event["duration_ms"] < 0:
                raise ValueError("Execution duration is invalid")
            if event["ok"]:
                text = event["output"]
        elif trace["tools"]:
            raise ValueError("DIRECT and CoT must not execute tools")
        answer = parse_typed_answer(text, **row["answer_format"])[0]
        if row["answer"] != answer or type(row["correct"]) is not bool or row["correct"] != bool(check_answer(answer, item)):
            raise ValueError("Answer/score differs from raw output and frozen gold")
    metrics, pairs, bounds = [], [], []
    for cap in manifest["token_budgets"]:
        cells = {strategy: {row["id"]: row for row in records if row["strategy"] == strategy and row["token_budget"] == cap}
                 for strategy in ("DIRECT", "COT", "PAL")}
        for strategy, by_id in cells.items():
            rows = list(by_id.values())
            n = len(rows)
            metrics.append({"strategy": strategy, "cap_per_call": cap, "questions": n,
                "correct": sum(row["correct"] for row in rows),
                "mean_generated_tokens": sum(row["tokens"] for row in rows) / n,
                "mean_prompt_tokens": sum(row["trace"]["generations"][0]["prompt_tokens"] for row in rows) / n,
                "mean_strategy_ms": sum(row["strategy_ms"] for row in rows) / n,
                "mean_tool_ms": sum(sum(event.get("duration_ms", 0) for event in row["trace"]["tools"]) for row in rows) / n,
                "parse_failures": sum(row["trace"]["parse_status"] == "fail" for row in rows),
                "length_stops": sum(row["trace"]["generations"][0]["finish_reason"] == "length" for row in rows),
                "execution_successes": sum(row["trace"]["tools"][0]["ok"] for row in rows) if strategy == "PAL" else None})
        for before, after in itertools.combinations(cells, 2):
            paired = [(cells[before][key], cells[after][key]) for key in items]
            pairs.append({"comparison": f"{after} minus {before}", "cap_per_call": cap,
                "became_correct": sum(not a["correct"] and b["correct"] for a, b in paired),
                "became_incorrect": sum(a["correct"] and not b["correct"] for a, b in paired),
                "both_incorrect": sum(not a["correct"] and not b["correct"] for a, b in paired)})
        bounds.append({"cap_per_call": cap, "gold_informed_best_of_three_correct":
            sum(any(cells[strategy][key]["correct"] for strategy in cells) for key in items), "uses_gold_labels": True, "deployable": False})
    return {"metrics": metrics, "paired": pairs, "gold_informed_bounds": bounds,
        "descriptive_only": True, "controller_evaluated": False, "publication_ready": False,
        "failures": [{key: row[key] for key in ("id", "strategy", "answer", "confidence", "tokens")} for row in records if not row["correct"]]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    manifest = json.loads((args.run / "manifest.json").read_text())
    dataset, records, _ = verify_replay(args.run, manifest)
    result = summarize(dataset, records, manifest)
    args.output.mkdir(parents=True)
    write_json(args.output / "summary.json", result)
    write_json(args.output / "manifest.json", {"kind": "audited_fixed_math_development_baselines",
        "input_manifest_sha256": sha256_file(args.run / "manifest.json"),
        "source_sha256": sha256_file(Path(__file__)), "summary_sha256": sha256_file(args.output / "summary.json"),
        "records_rescored": len(records), "new_model_calls": 0, "human_review_status": "pending", "publication_ready": False})
    print(args.output / "summary.json")


if __name__ == "__main__":
    main()
