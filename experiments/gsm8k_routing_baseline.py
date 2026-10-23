"""Offline query-only baseline for the existing GSM8K development protocol.

Fits the declared 27-rule menu on train only, durably saves selection, then
evaluates on calibration (development validation). Never invokes a model.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

from experiments.order_pilot_checkpoint import atomic_json, atomic_text
from experiments.research_pilot import sha256_file, verify_replay
from experiments.research_study import ROOT, check_answer, seed_for
from research_scoring import parse_typed_answer

ACTIONS = ("DIRECT", "COT", "PAL")
CUTOFFS = (20, 40, 60, 80)
RULE_VERSION = "gsm8k-query-words-v1"
LAMBDA = Fraction(1, 10)
PROTOCOL = ROOT / "docs/gsm8k_development_validation_protocol_20261004.md"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fingerprint(value):
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Rule:
    id: str
    short: str
    long: str
    cutoff: int | None = None

    def choose(self, query):
        require(isinstance(query, str) and bool(query.strip()), "Rule requires the original nonempty query")
        return self.short if self.cutoff is None or len(query.split()) <= self.cutoff else self.long


def candidate_rules():
    rules = [Rule(f"constant_{action}", action, action) for action in ACTIONS]
    rules += [Rule(f"words_le_{cutoff:03d}_{short}_else_{long}", short, long, cutoff)
              for cutoff in CUTOFFS for short in ACTIONS for long in ACTIONS if short != long]
    return sorted(rules, key=lambda rule: rule.id)


def frame(items):
    """Check identities using query/split metadata only, without inspecting gold."""
    by_id, groups, queries = {}, {}, set()
    for item in items:
        for key in ("id", "group_id", "query", "split"):
            require(isinstance(item.get(key), str) and bool(item[key].strip()), f"Missing {key}")
        require(item["split"] in ("train", "calibration"), "Only development train/calibration allowed; test is forbidden")
        require(item["id"] not in by_id, "Duplicate item ID")
        normalized = " ".join(item["query"].casefold().split())
        require(normalized not in queries, "Duplicate normalized query")
        require(groups.setdefault(item["group_id"], item["split"]) == item["split"], "Group crosses development roles")
        by_id[item["id"]] = item
        queries.add(normalized)
    require(bool(by_id), "Empty development frame")
    return by_id


def validate_records(items, records):
    """Audit the requested role only, including all three single-call arms."""
    by_id, arms = frame(items), {}
    for row in records:
        require(row["id"] in by_id and row["strategy"] in ACTIONS, "Unknown item or recipe")
        item = by_id[row["id"]]
        require(item.get("answer_type") == "number", "GSM8K routing expects numeric answers")
        require(row["group_id"] == item["group_id"] and row["split"] == item["split"], "Record group/role differs")
        key = (row["id"], row["strategy"])
        require(key not in arms, "Duplicate recipe record")
        require(type(row["token_budget"]) is int and row["token_budget"] == 1024, "Expected matched cap 1024")
        require(type(row["tokens"]) is int and 0 < row["tokens"] <= 1024, "Invalid generated-token count")
        require(type(row["strategy_ms"]) in (int, float) and math.isfinite(row["strategy_ms"]) and row["strategy_ms"] >= 0, "Invalid strategy duration")
        require(row["seed"] == seed_for(42, row["id"], row["strategy"]), "Unexpected recipe seed")
        expected_format = {"answer_type": "number", "decimal_separator": item.get("decimal_separator", ".")}
        require(row["answer_format"] == expected_format, "Answer-format metadata differs")
        trace = row["trace"]
        require(len(trace["generations"]) == 1, "This comparison requires one generation per recipe")
        generation = trace["generations"][0]
        require(type(generation["tokens"]) is int and generation["tokens"] == row["tokens"], "Generation/record cost differs")
        require(type(generation["max_tokens"]) is int and generation["max_tokens"] == 1024
                and generation["temperature"] == 0 and generation["enable_thinking"] is False, "Generation settings differ from protocol")
        require(type(generation["prompt_tokens"]) is int and generation["prompt_tokens"] >= 0, "Invalid prompt-token count")
        require(generation["finish_reason"] in ("stop", "length"), "Unexpected finish reason")
        tools = trace.get("tools", [])
        response = generation["output"]
        if row["strategy"] == "PAL":
            require(len(tools) == 1 and tools[0]["name"] == "python" and type(tools[0]["ok"]) is bool, "Missing PAL execution evidence")
            if tools[0]["ok"]:
                response = f"Answer: {tools[0]['output']}"
        else:
            require(not tools, "Unexpected tools on fixed language recipe")
        parsed = parse_typed_answer(response, **expected_format)[0]
        require(parsed == row["answer"], "Answer differs from public response/tool result")
        require(type(row["correct"]) is bool and row["correct"] == bool(check_answer(parsed, item)), "Correctness differs from frozen gold scoring")
        arms[key] = row
    require(set(arms) == {(ident, action) for ident in by_id for action in ACTIONS}, "Missing recipe or item")
    return arms


def selected_rows(rule, items, arms):
    result = []
    for item in sorted(items, key=lambda item: item["id"]):
        strategy = rule.choose(item["query"])
        record = arms[(item["id"], strategy)]
        result.append({"id": item["id"], "group_id": item["group_id"], "strategy": strategy,
                       **{key: record[key] for key in ("answer", "correct", "tokens", "strategy_ms", "trace")}})
    return result


def metrics(rows):
    n = len(rows)
    correct, tokens = sum(row["correct"] for row in rows), sum(row["tokens"] for row in rows)
    utility = Fraction(correct, n) - LAMBDA * Fraction(tokens, n * 1000)
    return {"items": n, "groups": len({r["group_id"] for r in rows}), "correct": correct,
            "accuracy": correct / n, "generated_tokens": tokens, "mean_generated_tokens": tokens / n,
            "mean_prompt_tokens": sum(r["trace"]["generations"][0]["prompt_tokens"] for r in rows) / n,
            "utility": float(utility), "utility_exact": str(utility), "generation_calls": n,
            "strategy_counts": {a: sum(r["strategy"] == a for r in rows) for a in ACTIONS},
            "parse_failures": sum(r["trace"].get("parse_status") == "fail" for r in rows),
            "length_stops": sum(r["trace"]["generations"][0]["finish_reason"] == "length" for r in rows),
            "pal_execution_failures": sum(any(t.get("ok") is False for t in r["trace"].get("tools", [])) for r in rows),
            "mean_replayed_strategy_ms": sum(r["strategy_ms"] for r in rows) / n}


def fit_selection(items, records):
    """Validation outcomes are not visited, validated or passed into the fitter."""
    frame(items)
    fit_items = sorted((i for i in items if i["split"] == "train"), key=lambda i: i["id"])
    require(bool(fit_items), "Missing fitting groups")
    ids = {i["id"] for i in fit_items}
    fit_records = [row for row in records if row["id"] in ids]
    arms = validate_records(fit_items, fit_records)
    rules = candidate_rules()
    scores = [{"rule": asdict(rule), **metrics(selected_rows(rule, fit_items, arms))} for rule in rules]

    def rank(score):
        return (-Fraction(score["utility_exact"]), -Fraction(score["correct"], score["items"]),
                Fraction(score["generated_tokens"], score["items"]), score["rule"]["cutoff"] is not None, score["rule"]["id"])

    selected = min(scores, key=rank)
    fixed = min((s for s in scores if s["rule"]["cutoff"] is None), key=rank)
    return {"rule_version": RULE_VERSION, "lambda": float(LAMBDA), "lambda_exact": str(LAMBDA),
            "feature": "len(original_query.split())", "cutoffs": list(CUTOFFS), "actions": list(ACTIONS),
            "selected_rule": selected["rule"], "fixed_reference": fixed["rule"],
            "collapsed_to_constant": selected["rule"]["cutoff"] is None,
            "fitting_ids": sorted(ids), "fitting_group_ids": sorted({i["group_id"] for i in fit_items}),
            "fitting_input_sha256": fingerprint({"items": fit_items, "records": sorted(fit_records, key=lambda r: (r["id"], r["strategy"]))}),
            "candidate_scores": scores}


def paired_comparison(ours, baseline):
    require(bool(ours), "Empty paired validation")
    require([(r["id"], r["group_id"]) for r in ours] == [(r["id"], r["group_id"]) for r in baseline], "Unpaired validation rows")
    groups = {}
    for a, b in zip(ours, baseline):
        accuracy = int(a["correct"]) - int(b["correct"])
        tokens = a["tokens"] - b["tokens"]
        groups.setdefault(a["group_id"], []).append((accuracy, tokens, accuracy - float(LAMBDA) * tokens / 1000))
    sums = np.array([np.sum(values, axis=0) for _, values in sorted(groups.items())])
    counts = np.array([len(values) for _, values in sorted(groups.items())])
    draws = []
    if len(groups) > 1:
        generator = np.random.default_rng(42)
        for _ in range(2000):
            indices = generator.integers(0, len(groups), len(groups))
            draws.append(sums[indices].sum(axis=0) / counts[indices].sum())
    return {"items": len(ours), "groups": len(groups),
            "rescues": sum(not b["correct"] and a["correct"] for a, b in zip(ours, baseline)),
            "harms": sum(b["correct"] and not a["correct"] for a, b in zip(ours, baseline)),
            "metrics": {name: {"mean_difference": float(value), "ci95": np.quantile(np.array(draws)[:, index], [.025, .975]).tolist() if draws else None}
                        for index, (name, value) in enumerate(zip(("accuracy", "generated_tokens", "utility"), sums.sum(axis=0) / counts.sum()))},
            "interval_scope": "descriptive group bootstrap; conditional on selected rules and observed generation seed; excludes fitting uncertainty",
            "bootstrap_seed": 42, "bootstrap_repetitions": 2000}


def evaluate_selection(selection, items, records):
    require(selection["rule_version"] == RULE_VERSION and selection["lambda_exact"] == str(LAMBDA), "Selection contract differs")
    items = sorted(items, key=lambda i: i["id"])
    by_id = frame(items)
    require(all(i["split"] == "calibration" for i in items), "Evaluation requires development validation only")
    require(not (set(by_id) & set(selection["fitting_ids"])), "Fitting ID leaked into validation")
    require(not ({i["group_id"] for i in items} & set(selection["fitting_group_ids"])), "Fitting group leaked into validation")
    arms = validate_records(items, records)
    canonical = {rule.id: rule for rule in candidate_rules()}
    chosen = []
    for key in ("selected_rule", "fixed_reference"):
        saved = selection[key]
        require(saved.get("id") in canonical and asdict(canonical[saved["id"]]) == saved, "Unknown or altered selected rule")
        chosen.append(canonical[saved["id"]])
    require(chosen[1].cutoff is None, "Reference must be a fitting-selected fixed strategy")
    rows = {"query_only_rule": selected_rows(chosen[0], items, arms), "selected_fixed_reference": selected_rows(chosen[1], items, arms)}
    rows.update({f"fixed_{a.lower()}": selected_rows(Rule(f"constant_{a}", a, a), items, arms) for a in ACTIONS})
    summary = {"development_only": True, "main_h1_evaluated": False, "lambda": float(LAMBDA),
               "collapsed_to_constant": selection["collapsed_to_constant"],
               "methods": {name: metrics(values) for name, values in rows.items()},
               "primary_comparison": paired_comparison(rows["query_only_rule"], rows["selected_fixed_reference"]),
               "collection": {"items": len(items), "groups": len({i["group_id"] for i in items}),
                              "generation_calls": len(records), "generated_tokens": sum(r["tokens"] for r in records),
                              "prompt_tokens": sum(r["trace"]["generations"][0]["prompt_tokens"] for r in records)}}
    public_rows = [{"method": name, **{key: row[key] for key in ("id", "group_id", "strategy", "answer", "correct", "tokens")}}
                   for name, values in rows.items() for row in values]
    return summary, public_rows


def render_report(summary, evidence):
    lines = ["# Query-only GSM8K development baseline", "", f"Evidence: **{evidence}**", "",
             "27 declared rules; fitting=train, development validation=calibration. Lambda=0.1 is specific to this development comparison.",
             "Selection and fixed reference were durably saved before validation scoring. No main H1 or held-out test evaluation.",
             "Synthetic inputs validate software only. Generated tokens exclude prompt/tool/full inference costs; replay timing is not online latency.",
             "Bootstrap intervals are descriptive, conditional on the selected rules and observed seed; human/publication review remains pending.", "",
             f"Selected rule collapsed to a constant: **{summary['collapsed_to_constant']}**.", "",
             "| Method | Correct/items | Groups | Mean generated tokens | Mean prompt tokens | Utility | PAL execution failures |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for method, row in summary["methods"].items():
        lines.append(f"| {method} | {row['correct']}/{row['items']} | {row['groups']} | {row['mean_generated_tokens']:.3f} | {row['mean_prompt_tokens']:.3f} | {row['utility']:.6f} | {row['pal_execution_failures']} |")
    lines += ["", "Primary contrast: query-only rule minus the fixed reference chosen on fitting.", ""]
    for metric, value in summary["primary_comparison"]["metrics"].items():
        lines.append(f"- {metric}: {value['mean_difference']:.6f}; descriptive 95% interval {value['ci95']}")
    lines += ["", "Collection costs include all three recipes; selected-path costs include exactly one. No winning comparator is chosen on validation.", ""]
    return "\n".join(lines)


def write_analysis(run, output):
    if output.exists():
        raise FileExistsError(output)
    manifest = json.loads((run / "manifest.json").read_text())
    require(manifest.get("evidence") in ("synthetic_pilot_smoke", "measured_development_pilot"), "Unknown input evidence")
    synthetic = manifest["evidence"] == "synthetic_pilot_smoke"
    require(manifest.get("backend") == ("smoke" if synthetic else "mlx"), "Backend/evidence mismatch")
    require(manifest.get("seed") == 42 and manifest.get("prompt_profile") == "english-math-v1", "Unexpected seed/profile")
    require(set(manifest.get("strategies", [])) == set(ACTIONS) and len(manifest["strategies"]) == 3, "Expected DIRECT/COT/PAL only")
    require(manifest.get("token_budgets") == [1024], "Expected single matched cap 1024")
    dataset, records, _ = verify_replay(run, manifest)
    items = dataset["items"]
    frame(items)
    if not synthetic:
        require(manifest.get("model_revision_verified") is True and manifest.get("model_repository") == "mlx-community/Qwen3-8B-4bit"
                and manifest.get("model_revision") == "545dc4251c05440727734bcd94334791f6ab0192", "Review model provenance for this development comparison")
        require(len(items) == len({i["group_id"] for i in items}) == 96 and Counter(i["split"] for i in items) == {"train": 48, "calibration": 48}, "Measured comparison requires its declared 48/48 frame")
        require(all(i.get("category") == "gsm8k" and i.get("source_provenance", {}).get("original_split") == "train"
                    and i["source_provenance"].get("revision") == "3101c7d5072418e28b9008a6636bde82a006892c" for i in items), "Expected pinned GSM8K source-train provenance")
    selection = fit_selection(items, records)
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "selection.json", selection)
    state = {"kind": "query_only_gsm8k_development_analysis", "status": "selection_saved", "new_model_calls": 0,
             "evidence": "synthetic_routing_software_check" if synthetic else "measured_development_saved_output_analysis",
             "input_run": str(run.resolve()), "collection_source_sha256": manifest["source_sha256"],
             "input_manifest_sha256": sha256_file(run / "manifest.json"), "input_artifact_sha256": manifest["artifact_sha256"],
             "analysis_source_sha256": sha256_file(Path(__file__)), "protocol_sha256": sha256_file(PROTOCOL),
             "atomic_writer_sha256": sha256_file(ROOT / "experiments/order_pilot_checkpoint.py"),
             "analysis_python": sys.version, "analysis_numpy": np.__version__,
             "cost_scope": "synthetic token units" if synthetic else "generated tokens summed over selected calls; prompt tokens separate; full inference costs excluded",
             "rule_version": RULE_VERSION, "selection_sha256": sha256_file(output / "selection.json"),
             "publication_ready": False, "human_review_status": "pending", "main_h1_evaluated": False}
    atomic_json(output / "manifest.json", state)
    try:
        val_items = [i for i in items if i["split"] == "calibration"]
        val_ids = {i["id"] for i in val_items}
        summary, rows = evaluate_selection(selection, val_items, [r for r in records if r["id"] in val_ids])
        summary["cost_scope"] = state["cost_scope"]
        summary["full_collection"] = {"generation_calls": len(records), "generated_tokens": sum(r["tokens"] for r in records),
                                      "prompt_tokens": sum(r["trace"]["generations"][0]["prompt_tokens"] for r in records)}
        atomic_json(output / "summary.json", summary)
        atomic_json(output / "results.json", rows)
        atomic_text(output / "report.md", render_report(summary, state["evidence"]))
        for name, expected in manifest["artifact_sha256"].items():
            require(sha256_file(run / name) == expected, "Input artifacts changed during analysis")
        require(sha256_file(output / "selection.json") == state["selection_sha256"], "Selection changed during validation")
        state.update(status="complete", artifact_sha256={name: sha256_file(output / name) for name in ("selection.json", "summary.json", "results.json", "report.md")})
        atomic_json(output / "manifest.json", state)
    except BaseException as error:
        state.update(status="failed", error=f"{type(error).__name__}: {error}")
        atomic_json(output / "manifest.json", state)
        raise
    return state
