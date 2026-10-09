"""Headless, paired evaluation of routing and stopping on frozen strategy outputs."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

import numpy as np

from entry_predictor import EntryPredictor, EntryTrainingData
from optimal_stopping import CalibrationData, OptimalStoppingPolicy
from reasoning_env import LADDER, ReasoningAction as A, STRATEGIES, complexity_features
from research_identity import FAMILIES, IDENTITY_VERSION, canonical_problem_id, problem_fingerprint


ROOT = Path(__file__).resolve().parents[1]
SPLITS = ("train", "calibration", "test")
STRATEGY_LABELS = {
    "COT": "CoT",
    "SELF_CONSISTENCY": "Self-consistency",
    "TOT": "Candidate selection (legacy TOT identifier)",
    "REACT": "ReAct calculator",
    "PAL": "PAL",
    "DIRECT": "Direct",
}


def normalized_text(value):
    return " ".join(str(value).casefold().split())


def check_answer(answer, item):
    if "family" in item or "checker" in item:
        from scripts.gen_tasks import check as gen_check
        return bool(gen_check(item, str(answer) if answer is not None else ""))
    if item["answer_type"] == "text":
        labels = [item["answer"], *item.get("answer_aliases", [])]
        return normalized_text(answer) in {normalized_text(label) for label in labels}
    try:
        if item.get("decimal_separator") == ",":
            from research_scoring import numeric_literal
            predicted = numeric_literal(answer, ",")
            if predicted is None:
                return False
        else:
            predicted = Decimal(str(answer).strip())
        expected = Decimal(str(item["answer"]).strip())
        tolerance = Decimal(str(item.get("tolerance", 0)))
        return predicted.is_finite() and abs(predicted - expected) <= tolerance
    except InvalidOperation:
        return False


def validate_dataset(dataset, *, require_all_splits=True, pilot=False):
    for field in ("name", "version", "source", "license"):
        if not isinstance(dataset.get(field), str) or not dataset[field].strip():
            raise ValueError(f"Dataset requires nonempty {field}")
    items = dataset.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("Dataset requires a nonempty items list")
    identifiers, queries, group_splits, observed_splits = set(), set(), {}, set()
    problem_groups = {}
    if dataset.get("identity_version") not in (None, IDENTITY_VERSION):
        raise ValueError("Unknown procedural identity_version")
    tuning = dataset.get("role") == "development_tuning"
    if pilot:
        if not tuning:
            raise ValueError("Pilot mode requires a development tuning dataset (role='development_tuning')")
    elif tuning and require_all_splits:
        raise ValueError("Development tuning pools cannot be used as a held-out study dataset")
    for item in items:
        for field in ("id", "group_id", "split", "query", "answer", "answer_type"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError(f"Each item requires nonempty string {field}")
        if item["split"] not in SPLITS or item["answer_type"] not in ("number", "text"):
            raise ValueError("Unknown split or answer_type")
        query = normalized_text(item["query"])
        if item["id"] in identifiers or query in queries:
            raise ValueError("Duplicate item ID or normalized query")
        identifiers.add(item["id"])
        queries.add(query)
        existing_split = group_splits.setdefault(item["group_id"], item["split"])
        if existing_split != item["split"]:
            raise ValueError(f"Group {item['group_id']} crosses dataset splits")
        observed_splits.add(item["split"])
        if pilot and item["split"] == "test":
            raise ValueError("Pilot mode cannot contain a held-out test split; main-study test questions must remain untouched")
        if tuning and item["split"] == "test":
            raise ValueError("An exposed tuning pool cannot contain a held-out test split")
        if "family" in item or "checker" in item:
            family = item.get("family")
            if family not in FAMILIES or item.get("checker", family) != family:
                raise ValueError("Unknown or inconsistent procedural checker")
            expected_type = "number" if family == "arith" else "text"
            if item["answer_type"] != expected_type:
                raise ValueError("Procedural answer_type does not match family")
            fingerprint = problem_fingerprint(item)
            group_and_split = (item["group_id"], item["split"])
            if problem_groups.setdefault(fingerprint, group_and_split) != group_and_split:
                raise ValueError("Canonical procedural problem crosses groups or splits")
            problem_id = canonical_problem_id(item)
            if "problem_id" in item and item["problem_id"] != problem_id:
                raise ValueError("Incorrect canonical problem_id")
            if dataset.get("identity_version") == IDENTITY_VERSION and (item.get("problem_id") != problem_id or item["group_id"] != problem_id):
                raise ValueError("Canonical releases require problem_id and group_id to match identity")
            from scripts import gen_tasks
            rendered = getattr(gen_tasks, f"render_{family}")(item["meta"])
            if rendered != item["query"]:
                raise ValueError("Procedural query differs from its declared metadata/template")
        if item.get("decimal_separator", ".") not in (".", ","):
            raise ValueError("Unknown decimal_separator")
        if "answer_aliases" in item:
            aliases = item["answer_aliases"]
            if item["answer_type"] != "text" or not isinstance(aliases, list) or not aliases or not all(isinstance(alias, str) and alias.strip() for alias in aliases):
                raise ValueError("answer_aliases require a nonempty list of text answers")
            normalized = [normalized_text(item["answer"]), *map(normalized_text, aliases)]
            if len(normalized) != len(set(normalized)):
                raise ValueError("Duplicate normalized answer aliases")
        if item["answer_type"] == "number":
            try:
                gold = Decimal(item["answer"])
                tolerance = Decimal(str(item.get("tolerance", 0)))
            except InvalidOperation as error:
                raise ValueError("Invalid numeric answer or tolerance") from error
            if not gold.is_finite() or not tolerance.is_finite() or tolerance < 0:
                raise ValueError("Numeric answers and tolerances must be finite; tolerance >= 0")
    if pilot:
        if observed_splits != {"train", "calibration"}:
            raise ValueError("Pilot mode requires both train and calibration splits")
    elif require_all_splits and observed_splits != set(SPLITS):
        raise ValueError("Separate train, calibration and test splits are required")
    return items


def smoke_dataset(*, pilot=False):
    items = []
    splits = ("train", "calibration") if pilot else SPLITS
    for split in splits:
        for category in ("pal", "react", "plain"):
            for index in range(8):
                identifier = f"{category}_{split}_{index}"
                items.append({
                    "id": identifier, "group_id": identifier, "split": split,
                    "query": identifier, "answer": "OK", "answer_type": "text",
                })
    return {
        "name": "synthetic-controller-smoke-pilot" if pilot else "synthetic-controller-smoke",
        "version": "1",
        "role": "development_tuning" if pilot else "main_study",
        "source": "Generated category markers; no real reasoning questions",
        "license": "Project-authored test fixture", "items": items,
    }


def seed_for(seed, identifier, action):
    digest = hashlib.sha256(f"{seed}:{identifier}:{action}".encode()).digest()
    return int.from_bytes(digest[:4], "big")


def collect_records(backend, items, seed, set_seed, event_file, strategies=None):
    strategies = strategies or STRATEGIES
    records = []
    for item in sorted(items, key=lambda entry: entry["id"]):
        answer_format = {
            "answer_type": "expression" if item.get("family") == "g24" else "text" if item.get("family") == "order" else item["answer_type"],
            "decimal_separator": item.get("decimal_separator", "."),
        }
        configure = getattr(backend, "configure_answer_format", None)
        if configure is not None:
            configure(**answer_format)
        set_seed(seed_for(seed, item["id"], "embed"))
        started = time.perf_counter()
        embedding = np.asarray(backend.embed(item["query"]), dtype=float)
        embedding_ms = (time.perf_counter() - started) * 1000
        if embedding.ndim != 1 or not embedding.size or not np.isfinite(embedding).all():
            raise ValueError("Backend returned an invalid embedding")
        embedding = embedding / max(float(np.linalg.norm(embedding)), 1e-12)
        record = {
            "id": item["id"], "group_id": item["group_id"], "split": item["split"],
            "embedding": embedding.tolist(), "embedding_ms": embedding_ms,
            "complexity": complexity_features(item["query"]).tolist(), "attempts": {},
            "answer_format": answer_format,
        }
        order = np.random.default_rng(seed_for(seed, item["id"], "order")).permutation(len(strategies))
        for strategy_index in order:
            strategy = strategies[strategy_index]
            action_seed = seed_for(seed, item["id"], strategy.name)
            set_seed(action_seed)
            started = time.perf_counter()
            answer, confidence, tokens = backend.run(strategy, item["query"])
            elapsed_ms = (time.perf_counter() - started) * 1000
            if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                raise ValueError("Backend confidence must be finite and in [0, 1]")
            if isinstance(tokens, bool) or not isinstance(tokens, (int, np.integer)) or tokens <= 0:
                raise ValueError("Backend must report a positive integer token count")
            attempt = {
                "answer": str(answer), "confidence": float(confidence), "tokens": int(tokens),
                "correct": bool(check_answer(answer, item)), "strategy_ms": elapsed_ms,
                "seed": action_seed,
            }
            trace = getattr(backend, "last_trace", None)
            if trace is not None:
                attempt["trace"] = trace
            record["attempts"][strategy.name] = attempt
            event_file.write(json.dumps({"id": item["id"], "strategy": strategy.name, **attempt}, ensure_ascii=False) + "\n")
            event_file.flush()
        records.append(record)
    return records


def calibration_data(records):
    return CalibrationData(
        conf=np.array([[record["attempts"][strategy.name]["confidence"] for record in records] for strategy in LADDER]),
        correct=np.array([[float(record["attempts"][strategy.name]["correct"]) for record in records] for strategy in LADDER]),
        cost=np.array([[record["attempts"][strategy.name]["tokens"] / 1000 for record in records] for strategy in LADDER]),
    )


def ladder_path(record, policy):
    path = []
    for rung, strategy in enumerate(LADDER):
        path.append(strategy.name)
        if rung == len(LADDER) - 1 or not policy.should_escalate(rung, record["attempts"][strategy.name]["confidence"]):
            break
    return path


def entry_training_data(records, policy, use_ladder):
    accuracy, cost = [], []
    for record in records:
        paths = [ladder_path(record, policy) if use_ladder else ["COT"], ["REACT"], ["PAL"]]
        accuracy.append([float(record["attempts"][path[-1]]["correct"]) for path in paths])
        cost.append([sum(record["attempts"][strategy]["tokens"] for strategy in path) / 1000 for path in paths])
    return EntryTrainingData(
        embed=np.array([record["embedding"] for record in records]),
        complexity=np.array([record["complexity"] for record in records]),
        accuracy=np.array(accuracy), cost=np.array(cost),
    )


def fit_policies(records, lam):
    calibration = [record for record in records if record["split"] == "calibration"]
    train = [record for record in records if record["split"] == "train"]
    policy = OptimalStoppingPolicy(lam).fit(calibration_data(calibration))
    full = EntryPredictor(lam).fit(entry_training_data(train, policy, use_ladder=True))
    one_shot = EntryPredictor(lam).fit(entry_training_data(train, policy, use_ladder=False))
    return policy, full, one_shot


def evaluate_records(records, policy, full, one_shot):
    results = []
    for record in records:
        if record["split"] != "test":
            continue
        embedding, complexity = np.array(record["embedding"]), np.array(record["complexity"])
        full_choice = int(full.choose(embedding, complexity))
        single_choice = int(one_shot.choose(embedding, complexity))
        entry_names = ("COT", "REACT", "PAL")
        paths = {f"fixed_{strategy.name.lower()}": [strategy.name] for strategy in STRATEGIES}
        paths.update({
            "ladder_only": ladder_path(record, policy),
            "one_shot_router": [entry_names[single_choice]],
            "entry_without_escalation": [entry_names[full_choice]],
            "full_policy": ladder_path(record, policy) if full_choice == 0 else [entry_names[full_choice]],
        })
        for method, path in paths.items():
            final = record["attempts"][path[-1]]
            results.append({
                "id": record["id"], "group_id": record["group_id"], "method": method,
                "path": path, "answer": final["answer"], "correct": final["correct"],
                "tokens": sum(record["attempts"][strategy]["tokens"] for strategy in path),
                "strategy_ms_sum": sum(record["attempts"][strategy]["strategy_ms"] for strategy in path),
                "embedding_ms": record["embedding_ms"] if method in ("one_shot_router", "entry_without_escalation", "full_policy") else 0,
                "escalated": len(path) > 1,
            })
    return results


def paired_interval(results, baseline, metric, seed, repetitions=2000):
    ours = {row["id"]: row for row in results if row["method"] == "full_policy"}
    reference = {row["id"]: row for row in results if row["method"] == baseline}
    if not ours or ours.keys() != reference.keys():
        raise ValueError("Paired comparison requires identical nonempty query sets")
    groups = {}
    for identifier, row in ours.items():
        groups.setdefault(row["group_id"], []).append(float(row[metric]) - float(reference[identifier][metric]))
    sums = np.array([sum(values) for values in groups.values()])
    counts = np.array([len(values) for values in groups.values()])
    mean = float(sums.sum() / counts.sum())
    if len(groups) < 2:
        return {"mean_difference": mean, "ci95": None, "groups": len(groups)}
    generator = np.random.default_rng(seed)
    draws = []
    for _ in range(repetitions):
        indices = generator.integers(0, len(groups), size=len(groups))
        draws.append(float(sums[indices].sum() / counts[indices].sum()))
    return {"mean_difference": mean, "ci95": np.quantile(draws, [0.025, 0.975]).tolist(), "groups": len(groups)}


def summarize_methods(results, lam):
    methods = {}
    for method in sorted({row["method"] for row in results}):
        rows = [row for row in results if row["method"] == method]
        accuracy = float(np.mean([row["correct"] for row in rows]))
        tokens = float(np.mean([row["tokens"] for row in rows]))
        methods[method] = {
            "n": len(rows), "accuracy": accuracy, "mean_tokens": tokens,
            "utility": accuracy - lam * tokens / 1000,
            "escalation_rate": float(np.mean([row["escalated"] for row in rows])),
            "mean_strategy_ms_sum": float(np.mean([row["strategy_ms_sum"] for row in rows])),
            "mean_embedding_ms": float(np.mean([row["embedding_ms"] for row in rows])),
        }
    return methods


def summarize(results, lam, seed):
    results = [{**row, "utility": float(row["correct"]) - lam * row["tokens"] / 1000} for row in results]
    comparisons = {
        baseline: {metric: paired_interval(results, baseline, metric, seed) for metric in ("correct", "tokens", "utility")}
        for baseline in ("one_shot_router", "fixed_self_consistency", "entry_without_escalation")
    }
    return {"methods": summarize_methods(results, lam), "paired_full_minus_baseline": comparisons}


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def git_value(*arguments):
    result = subprocess.run(["git", *arguments], cwd=ROOT, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def source_hashes():
    names = (
        "experiments/research_study.py", "optimal_stopping.py", "entry_predictor.py",
        "reasoning_env.py", "reasoning_strategies.py", "pipeline.py", "qwen_mlx_backend.py",
        "scripts/gen_tasks.py",
        "research_scoring.py",
        "research_identity.py",
        "research_prompt_profiles.py",
        "experiments/research_pilot.py",
    )
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}


def render_report(manifest, summary):
    lines = [
        "# Reasoning research run", "", f"Evidence: **{manifest['evidence']}**", "",
        "These are paired replay estimates from frozen strategy outputs. They do not measure online end-to-end latency.",
        "Synthetic runs only validate the experiment software; they provide no evidence of model quality.", "",
        "| Method | Test N | Accuracy | Mean tokens | Utility | Escalation |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for method, metrics in summary["methods"].items():
        lines.append(f"| {method} | {metrics['n']} | {metrics['accuracy']:.3f} | {metrics['mean_tokens']:.1f} | {metrics['utility']:.3f} | {metrics['escalation_rate']:.3f} |")
    lines.extend([
        "", "Differences below are full policy minus baseline. Accuracy is on the 0–1 scale; negative token differences mean fewer tokens.",
        "Intervals resample problem groups and are conditional on this fitted policy and generation seed.", "",
        "| Baseline | Metric | Mean difference | Paired 95% interval |",
        "| --- | --- | ---: | --- |",
    ])
    for baseline, comparisons in summary["paired_full_minus_baseline"].items():
        for metric, comparison in comparisons.items():
            lines.append(f"| {baseline} | {metric} | {comparison['mean_difference']:.4f} | {comparison['ci95']} |")
    lines.extend([
        "", f"Token scope: {manifest['token_scope']}. All invoked strategy costs are added.",
        "Strategy timings and embedding overhead are logged separately. Router execution, model loading, and live scheduling are not included in replay latency sums.",
        "The legacy TOT identifier denotes candidate generation and selection in the MLX adapter, not a full tree search.",
        "The one-shot router is an internal baseline, not a reproduction of Route-to-Reason.",
        "Publication needs reviewed data/answers, pinned model provenance, multiple generation seeds, prior-art comparisons, and a separate online timing run.",
    ])
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--backend", choices=("smoke", "mlx"))
    mode.add_argument("--replay", type=Path, help="Recompute a completed run without model calls or changing its settings")
    mode.add_argument("--aggregate", type=Path, nargs="+", metavar="RUN", help="Aggregate compatible completed runs with distinct generation seeds")
    mode.add_argument(
        "--direct-cot-analysis", type=Path, metavar="PILOT_RUN",
        help="Development-only replay of a fixed DIRECT-to-CoT policy; never calls a model",
    )
    mode.add_argument(
        "--run11-think-on-demand-replay", type=Path, metavar="TRACE",
        help="Post-hoc development replay on the exact hashed Run 11 trace; never calls a model",
    )
    mode.add_argument("--order-certificate-smoke", action="store_true", help="Offline synthetic validation of certificate gates and complete per-call cost")
    mode.add_argument("--order-certificate-prepare", type=Path, metavar="CANDIDATE", help="Adapt the frozen ordering candidate and audit label-free group isolation")
    mode.add_argument("--order-certificate-analysis", type=Path, metavar="RUN", help="Validate and replay frozen ordering certificate artifacts")
    mode.add_argument("--order-certificate-pilot", action="store_true", help="Call-checkpointed ordering diagnostics on exposed train only; never confirmatory")
    mode.add_argument("--cot-restart-pilot", action="store_true", help="Run or resume the Qwen3.5-4B CoT restart development pilot on exposed questions")
    mode.add_argument("--agreement-analysis", action="store_true", help="Offline exploratory reanalysis of pinned Run 11/PAL-v2 development outputs; never calls a model")
    parser.add_argument("--order-pilot-mock", action="store_true", help="Synthetic ordering pilot; never import or load MLX")
    parser.add_argument("--order-pilot-items", type=int, help="Exposed ordering train questions (default 2)")
    parser.add_argument("--order-pilot-thinking-tokens", type=int, help="Development-only native-thinking cap override")
    parser.add_argument("--cot-restart-mock", action="store_true", help="Synthetic mock pilot; never import or load MLX")
    parser.add_argument("--cot-restart-smoke-only", action="store_true", help="Run only the 4-call smoke verification")
    parser.add_argument("--pilot", action="store_true", help="Fixed-strategy diagnostics on exposed development only")
    parser.add_argument("--strategies", nargs="+", choices=("DIRECT", "COT", "SELF_CONSISTENCY", "TOT", "REACT", "PAL"), help="Pilot strategies (default DIRECT COT)")
    budget = parser.add_mutually_exclusive_group()
    budget.add_argument("--max-tokens", type=int, help="Pilot single per-call token cap")
    budget.add_argument("--token-budgets", nargs="+", type=int, help="Matched pilot per-call caps (default 96 1024)")
    parser.add_argument("--groups-per-stratum", type=int, help="Pilot groups per split/family/level (default 1)")
    parser.add_argument("--model-provenance", type=Path, help="Pilot upstream model-content verification JSON")
    parser.add_argument("--direct-cot-budget", type=int, help="Matched per-call budget to replay from a DIRECT/CoT pilot")
    parser.add_argument(
        "--prompt-profile", choices=("legacy", "english-math-v1", "aligned-direct-cot-v1"),
        help="Pilot prompt profile; replay retains the recorded profile",
    )
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--model", help="Local pinned MLX model directory or model repository")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--lam", type=float)
    parser.add_argument("--output", type=Path, required=True, help="New run directory; only the ordering development pilot supports exact compatible resume")
    args = parser.parse_args(argv)
    pilot_settings = (args.strategies, args.max_tokens, args.token_budgets, args.groups_per_stratum, args.model_provenance, args.prompt_profile)
    if args.order_certificate_pilot:
        if args.backend is not None or args.pilot or any(value is not None for value in (args.dataset, args.model, args.lam, args.direct_cot_budget, *pilot_settings)):
            parser.error("Ordering pilot selects exposed train only; generic collection overrides are not allowed")
        from scripts.pilot_order_certificate import run_pilot
        try:
            run_pilot(num_items=2 if args.order_pilot_items is None else args.order_pilot_items,
                      seeds=[42 if args.seed is None else args.seed], output_dir=args.output,
                      thinking_max_tokens=args.order_pilot_thinking_tokens, mock=args.order_pilot_mock)
        except (ValueError, OSError, RuntimeError) as error:
            parser.error(str(error))
        print(f"order_certificate_development_pilot: {args.output / 'report.md'}")
        return
    if args.order_pilot_mock or args.order_pilot_items is not None or args.order_pilot_thinking_tokens is not None:
        parser.error("Ordering pilot overrides require --order-certificate-pilot")
    if args.cot_restart_pilot:
        if args.backend is not None or args.pilot or any(value is not None for value in (args.dataset, args.model, args.seed, args.lam, args.direct_cot_budget, *pilot_settings)):
            parser.error("CoT restart pilot uses pinned exposed questions and settings; overrides are not allowed")
        from experiments.cot_restart_pilot import run_cot_restart_pilot
        try:
            run_cot_restart_pilot(output_dir=args.output, mock=args.cot_restart_mock, smoke_only=args.cot_restart_smoke_only)
        except (ValueError, OSError, RuntimeError) as error:
            parser.error(str(error))
        print(f"cot_restart_development_pilot: {args.output / 'report.md'}")
        return
    if args.cot_restart_mock or args.cot_restart_smoke_only:
        parser.error("CoT restart overrides require --cot-restart-pilot")
    if args.agreement_analysis:
        if args.pilot or any(value is not None for value in (args.dataset, args.model, args.seed, args.lam, args.direct_cot_budget, *pilot_settings)):
            parser.error("Agreement analysis uses pinned exposed development artifacts and fixed settings; overrides are not allowed")
        from scripts.agreement import write_analysis
        try:
            write_analysis(args.output)
        except (ValueError, OSError) as error:
            parser.error(str(error))
        print(f"agreement_exploratory_reanalysis: {args.output / 'report.md'}")
        return
    if args.order_certificate_smoke or args.order_certificate_prepare or args.order_certificate_analysis:
        if args.backend is not None or args.pilot or any(value is not None for value in (args.dataset, args.model, args.seed, args.lam, args.direct_cot_budget, *pilot_settings)):
            parser.error("Ordering certificate modes use frozen settings; collection overrides are not allowed")
        from experiments.order_certificate_study import prepare_dataset, replay, run_smoke

        try:
            if args.order_certificate_prepare:
                prepare_dataset(args.order_certificate_prepare, args.output)
            elif args.order_certificate_analysis:
                replay(args.order_certificate_analysis, args.output)
            else:
                run_smoke(args.output)
        except (ValueError, OSError) as error:
            parser.error(str(error))
        print(f"order_certificate_offline: {args.output / 'report.md'}")
        return
    if args.run11_think_on_demand_replay:
        forbidden = (
            args.model, args.seed, args.direct_cot_budget,
            *pilot_settings,
        )
        if args.pilot or any(value is not None for value in forbidden):
            parser.error("Run 11 replay uses frozen artifacts; collection overrides are not allowed")
        args.lam = 0.02 if args.lam is None else args.lam
        if not math.isfinite(args.lam) or args.lam < 0:
            parser.error("--lam must be finite and nonnegative")
        dataset = args.dataset or ROOT / "data" / "gen02_tune.json"
        from experiments.think_on_demand_replay import write_analysis

        try:
            write_analysis(args.run11_think_on_demand_replay, dataset, args.output, args.lam)
        except (ValueError, OSError) as error:
            parser.error(str(error))
        print(f"run11_think_on_demand_posthoc_replay: {args.output / 'report.md'}")
        return
    if args.direct_cot_analysis:
        forbidden = (
            args.dataset, args.model, args.seed,
            *pilot_settings,
        )
        if args.pilot or any(value is not None for value in forbidden):
            parser.error("DIRECT/CoT analysis replays frozen pilot artifacts; collection overrides are not allowed")
        args.lam = 0.02 if args.lam is None else args.lam
        if not math.isfinite(args.lam) or args.lam < 0:
            parser.error("--lam must be finite and nonnegative")
        if args.direct_cot_budget is not None and args.direct_cot_budget <= 0:
            parser.error("--direct-cot-budget must be positive")
        from experiments.direct_cot_analysis import write_analysis

        try:
            write_analysis(args.direct_cot_analysis, args.output, args.lam, args.direct_cot_budget)
        except (ValueError, OSError) as error:
            parser.error(str(error))
        print(f"direct_cot_development_analysis: {args.output / 'report.md'}")
        return
    if args.direct_cot_budget is not None:
        parser.error("--direct-cot-budget requires --direct-cot-analysis")
    if (args.aggregate or args.replay) and (args.pilot or any(value is not None for value in pilot_settings)):
        parser.error("Replay and aggregation use frozen settings; pilot overrides are not allowed")
    if args.replay and any(value is not None for value in (args.dataset, args.model, args.seed, args.lam)):
        parser.error("Replay uses the original dataset, model, seed and lambda; overrides are not allowed")
    if args.pilot:
        from experiments.research_pilot import run
        try:
            run(args, parser)
        except ValueError as error:
            parser.error(str(error))
        return
    if any(value is not None for value in pilot_settings):
        parser.error("Strategy, sampling and budget options require --pilot")
    if args.replay:
        if any(value is not None for value in (args.dataset, args.model, args.seed, args.lam)):
            parser.error("Replay uses frozen settings; overrides are not allowed")
        replay_manifest = json.loads((args.replay / "manifest.json").read_text())
        if replay_manifest.get("pilot"):
            from experiments.research_pilot import run
            try:
                run(args, parser, replay_manifest=replay_manifest)
            except ValueError as error:
                parser.error(str(error))
            return
    if args.aggregate:
        if any(value is not None for value in (args.dataset, args.model, args.seed, args.lam)):
            parser.error("Aggregation uses the frozen input settings; overrides are not allowed")
        from experiments.research_aggregate import write_aggregate

        try:
            write_aggregate(args.aggregate, args.output)
        except (ValueError, OSError) as error:
            parser.error(str(error))
        return
    if args.replay and any(value is not None for value in (args.dataset, args.model, args.seed, args.lam)):
        parser.error("Replay uses the original dataset, model, seed and lambda; overrides are not allowed")
    args.seed = 42 if args.seed is None else args.seed
    args.lam = 0.02 if args.lam is None else args.lam
    if not math.isfinite(args.lam) or args.lam < 0:
        parser.error("--lam must be finite and nonnegative")
    if args.replay:
        source = args.replay
        manifest = json.loads((source / "manifest.json").read_text())
        if manifest["status"] != "complete":
            parser.error("Only complete runs can be replayed")
        if source_hashes() != manifest["source_sha256"]:
            parser.error("Replay requires the original implementation; source hashes differ")
        dataset = json.loads((source / "dataset.json").read_text())
        records = json.loads((source / "records.json").read_text())
        for name in ("dataset.json", "records.json"):
            if hashlib.sha256((source / name).read_bytes()).hexdigest() != manifest["artifact_sha256"][name]:
                parser.error(f"Replay artifact changed: {name}")
        args.seed, args.lam = manifest["seed"], manifest["lambda"]
        manifest = {**manifest, "replayed_from": str(source.resolve())}
    else:
        if args.backend == "mlx" and (args.dataset is None or args.model is None):
            parser.error("MLX requires --dataset and --model; there is no synthetic fallback")
        if args.backend == "smoke" and (args.dataset is not None or args.model is not None):
            parser.error("Smoke runs use only the bundled synthetic fixture")
        dataset = smoke_dataset() if args.backend == "smoke" else json.loads(args.dataset.read_text())
        packages = {}
        for name in ("numpy", "scikit-learn", "gymnasium", "mlx", "mlx-lm"):
            try:
                packages[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                packages[name] = None
        manifest = {
            "schema_version": 1, "seed": args.seed, "lambda": args.lam,
            "backend": args.backend, "model": args.model,
            "evidence": "synthetic_smoke" if args.backend == "smoke" else "measured_strategy_replay",
            "token_scope": "synthetic token units" if args.backend == "smoke" else "generated tokens only; input tokens not counted",
            "git_sha": git_value("rev-parse", "HEAD"), "git_status": git_value("status", "--porcelain"),
            "source_sha256": source_hashes(), "python": sys.version,
            "platform": platform.platform(), "packages": packages,
            "strategy_labels": STRATEGY_LABELS, "model_revision_verified": False,
        }
    items = validate_dataset(dataset)
    args.output.mkdir(parents=True, exist_ok=False)
    manifest.update(status="running", started_utc=datetime.now(timezone.utc).isoformat())
    write_json(args.output / "manifest.json", manifest)
    write_json(args.output / "dataset.json", dataset)
    try:
        if not args.replay:
            started = time.perf_counter()
            if args.backend == "smoke":
                from pipeline import MockDemoBackend

                backend = MockDemoBackend(seed=args.seed)

                def set_seed(seed):
                    backend.rng = np.random.default_rng(seed)
            else:
                import mlx.core as mx
                from qwen_mlx_backend import QwenMLXBackend

                backend = QwenMLXBackend(repo=args.model)
                set_seed = mx.random.seed
            manifest["backend_load_ms"] = (time.perf_counter() - started) * 1000
            with (args.output / "attempts.jsonl").open("w", encoding="utf-8") as event_file:
                records = collect_records(backend, items, args.seed, set_seed, event_file)
        write_json(args.output / "records.json", records)
        policy, full, one_shot = fit_policies(records, args.lam)
        results = evaluate_records(records, policy, full, one_shot)
        summary = summarize(results, args.lam, args.seed)
        write_json(args.output / "policy.json", {"tau": policy.tau, "mean_cost": policy.mean_cost, "lambda": args.lam})
        write_json(args.output / "results.json", results)
        write_json(args.output / "summary.json", summary)
        (args.output / "report.md").write_text(render_report(manifest, summary), encoding="utf-8")
        manifest["artifact_sha256"] = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(args.output.iterdir()) if path.is_file() and path.name != "manifest.json"
        }
        manifest.update(status="complete", finished_utc=datetime.now(timezone.utc).isoformat())
        write_json(args.output / "manifest.json", manifest)
    except BaseException as error:
        manifest.update(status="failed", error=f"{type(error).__name__}: {error}")
        write_json(args.output / "manifest.json", manifest)
        raise
    print(f"{manifest['evidence']}: {args.output / 'report.md'}")


if __name__ == "__main__":
    main()
