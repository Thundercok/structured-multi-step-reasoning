"""Exploratory group-isolated development CV on frozen research outputs.

No collection, backend construction, test-outcome evaluation, or default selection.
Invoked through ``python -m experiments.research_study --entry-evaluation RUN``.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import platform
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge

from experiments.research_study import (
    ROOT, calibration_data, check_answer, entry_training_data, git_value,
    validate_dataset, write_json,
)
from reasoning.entry_predictor import EntryPredictor, EntryTrainingData, _ConstantClassifier
from reasoning.optimal_stopping import OptimalStoppingPolicy


ROUTES = ("LADDER", "REACT", "PAL")
CONFIGURATIONS = {"old": None, "scaler_only": None, "pca16": 16, "pca32": 32, "pca64": 64}
DEFAULT_CONFIGS = ("old", "scaler_only", "pca32")
REQUIRED_STRATEGIES = {"COT", "SELF_CONSISTENCY", "TOT", "REACT", "PAL"}
METRICS = ("accuracy", "cost_k_tokens", "utility", "log_loss")
INTERVAL_SCOPE = (
    "Exploratory group bootstrap of repeat-averaged OOF outcomes, conditional on "
    "the recorded generation draw, calibration policy and fitted CV models. "
    "Shared training-fold dependence and refitting/selection uncertainty are not covered."
)


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _hash_string(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _number(value, minimum=0):
    return type(value) in (int, float) and math.isfinite(value) and value >= minimum


def load_recorded_run(directory):
    """Verify original manifest-bound bytes; validate development scoring only.

    Stored test rows are parsed for coverage/split identity but their features,
    attempts and labels never enter evaluation. Source drift is retained in
    provenance, not repaired by changing historical manifest hashes.
    """
    directory = Path(directory).resolve()
    manifest_bytes = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if not isinstance(manifest, dict) or manifest.get("status") != "complete" or manifest.get("schema_version") != 1:
        raise ValueError("Entry evaluation requires a complete schema-1 research run")
    if manifest.get("pilot") or "replayed_from" in manifest:
        raise ValueError("Use an original research collection with separate train/calibration/test, not a pilot or replay copy")
    evidence = {"smoke": "synthetic_smoke", "mlx": "measured_strategy_replay"}
    backend = manifest.get("backend")
    if not isinstance(backend, str) or backend not in evidence or manifest.get("evidence") != evidence[backend]:
        raise ValueError("Input backend/evidence labels are inconsistent")
    if not _number(manifest.get("lambda")) or type(manifest.get("seed")) is not int:
        raise ValueError("Input requires finite nonnegative lambda and an integer generation seed")
    token_scope = "synthetic token units" if backend == "smoke" else "generated tokens only; input tokens not counted"
    if manifest.get("token_scope") != token_scope:
        raise ValueError("Input token scope disagrees with the supported research collector")
    if backend == "mlx" and (not isinstance(manifest.get("model"), str) or not manifest["model"].strip()):
        raise ValueError("Measured input requires model identity")
    if type(manifest.get("model_revision_verified")) is not bool:
        raise ValueError("Input requires an explicit model revision verification flag")
    sources = manifest.get("source_sha256")
    if not isinstance(sources, dict) or not sources or not all(isinstance(k, str) and _hash_string(v) for k, v in sources.items()):
        raise ValueError("Input requires frozen source fingerprints")
    hashes = manifest.get("artifact_sha256")
    if not isinstance(hashes, dict) or not {"dataset.json", "records.json", "attempts.jsonl"} <= hashes.keys():
        raise ValueError("Input requires dataset, records and raw-attempt hashes")
    payloads = {}
    for name, expected in hashes.items():
        if not isinstance(name, str) or Path(name).name != name or name in (".", "..", "manifest.json") or not _hash_string(expected):
            raise ValueError("Invalid manifest artifact path or SHA256")
        target = directory / name
        if target.is_symlink() or target.resolve().parent != directory:
            raise ValueError("Artifacts must remain inside the run directory without symlinks")
        raw = target.read_bytes()
        if _digest(raw) != expected:
            raise ValueError(f"Input artifact changed: {name}")
        if name in ("dataset.json", "records.json"):
            payloads[name] = json.loads(raw)
        elif name == "attempts.jsonl":
            payloads[name] = raw
    items = {item["id"]: item for item in validate_dataset(payloads["dataset.json"])}
    records = payloads["records.json"]
    if not isinstance(records, list) or len(records) != len(items):
        raise ValueError("Records must cover the complete frozen dataset")
    seen, dimensions, development, expected_attempts = set(), None, [], {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            raise ValueError("Each record requires an item ID")
        identifier = record["id"]
        if identifier not in items or identifier in seen:
            raise ValueError("Duplicate or unknown recorded item ID")
        seen.add(identifier)
        item = items[identifier]
        if any(record.get(field) != item[field] for field in ("split", "group_id")):
            raise ValueError("Record group/split disagrees with frozen dataset")
        if record["split"] == "test":
            continue
        vectors = [np.asarray(record.get(field), dtype=float) for field in ("embedding", "complexity")]
        if any(vector.ndim != 1 or not vector.size or not np.isfinite(vector).all() for vector in vectors):
            raise ValueError("Development features must be finite nonempty vectors")
        shape = tuple(vector.shape for vector in vectors)
        if dimensions is not None and dimensions != shape:
            raise ValueError("Development feature dimensions disagree")
        dimensions = shape
        attempts = record.get("attempts")
        if not isinstance(attempts, dict) or not REQUIRED_STRATEGIES <= attempts.keys():
            raise ValueError("Development records require all five reasoning strategies")
        for strategy in REQUIRED_STRATEGIES:
            attempt = attempts[strategy]
            if not isinstance(attempt, dict) or type(attempt.get("correct")) is not bool or not isinstance(attempt.get("answer"), str):
                raise ValueError("Attempts require string answers and boolean correctness")
            if not _number(attempt.get("confidence")) or attempt["confidence"] > 1:
                raise ValueError("Confidence must be finite and in [0, 1]")
            if type(attempt.get("tokens")) is not int or attempt["tokens"] <= 0:
                raise ValueError("Token counts must be positive integers")
            if attempt["correct"] != check_answer(attempt["answer"], item):
                raise ValueError("Recorded development scoring differs from current checker; review historical semantics")
            expected_attempts[identifier, strategy] = attempt
        development.append(record)
    raw = payloads["attempts.jsonl"]
    if not raw.endswith(b"\n"):
        raise ValueError("Raw attempts must end with a complete JSONL line")
    observed = set()
    for line in raw.splitlines():
        event = json.loads(line)
        if not isinstance(event, dict) or not isinstance(event.get("id"), str) or event["id"] not in items:
            raise ValueError("Raw attempt has an unknown item ID")
        if items[event["id"]]["split"] == "test":
            continue
        strategy = event.get("strategy")
        if not isinstance(strategy, str):
            raise ValueError("Raw attempt requires a strategy name")
        if strategy not in REQUIRED_STRATEGIES:
            continue
        key = event["id"], strategy
        content = {name: value for name, value in event.items() if name not in ("id", "strategy")}
        if key in observed or content != expected_attempts.get(key):
            raise ValueError("Raw development attempts disagree with records or contain duplicates")
        observed.add(key)
    if observed != expected_attempts.keys():
        raise ValueError("Raw development attempts are incomplete")
    return {
        "directory": str(directory), "manifest": manifest,
        "manifest_sha256": _digest(manifest_bytes),
        "development": sorted(development, key=lambda row: row["id"]),
        "excluded_test_items": sum(item["split"] == "test" for item in items.values()),
    }


def outer_splits(groups, folds, seed):
    """Shuffle original groups, keeping every member in one evaluation fold."""
    groups = np.asarray(groups)
    unique = np.unique(groups)
    if type(folds) is not int or not 2 <= folds <= len(unique):
        raise ValueError("Outer folds must be between 2 and the number of train groups")
    shuffled = np.random.default_rng(seed).permutation(unique)
    for index in range(folds):
        mask = np.isin(groups, shuffled[index::folds])
        yield np.flatnonzero(~mask), np.flatnonzero(mask)


def _subset(data, indices):
    return EntryTrainingData(data.embed[indices], data.complexity[indices], data.accuracy[indices], data.cost[indices])


def predict_heads(config, training, embeddings, complexity, groups, lam, seed):
    """Share the production predictor; retain a clearly named historical baseline."""
    X = np.concatenate([training.embed, training.complexity], axis=1)
    heldout = np.concatenate([embeddings, complexity], axis=1)
    if config == "old":
        perf, cost = [], []
        for k in range(3):
            y = training.accuracy[:, k]
            perf.append(_ConstantClassifier(y[0]) if len(np.unique(y)) < 2 else LogisticRegression(max_iter=2000).fit(X, y))
            cost.append(Ridge(alpha=1.0).fit(X, training.cost[:, k]))
    else:
        predictor = EntryPredictor(lam, n_components=CONFIGURATIONS[config], seed=seed).fit(training, groups=groups)
        perf, cost = predictor.perf, predictor.cost
    probabilities = np.column_stack([model.predict_proba(heldout)[:, 1] for model in perf])
    costs = np.column_stack([model.predict(heldout) for model in cost])
    if not np.isfinite(probabilities).all() or not np.isfinite(costs).all():
        raise ValueError("Predictor returned nonfinite outputs")
    if np.any((probabilities < 0) | (probabilities > 1)):
        raise ValueError("Predicted probabilities must be in [0, 1]")
    # Preserve the shared predictor's cost/selection rule, including unclipped Ridge predictions.
    return probabilities, costs


def outcome_rows(method, rep, fold, records, data, indices, probabilities, costs, choices, lam):
    rows = []
    for local, index in enumerate(indices):
        choice = int(choices[local])
        accuracy, cost = float(data.accuracy[index, choice]), float(data.cost[index, choice])
        probability = np.clip(probabilities[local], 1e-6, 1 - 1e-6)
        labels = data.accuracy[index]
        rows.append({
            "id": records[index]["id"], "group_id": records[index]["group_id"],
            "split": "train", "repeat": rep, "fold": fold, "method": method,
            "choice": ROUTES[choice], "predicted_accuracy": probabilities[local].tolist(),
            "predicted_cost_k_tokens": costs[local].tolist(),
            "accuracy": accuracy, "cost_k_tokens": cost, "utility": accuracy - lam * cost,
            "log_loss": float(-np.mean(labels * np.log(probability) + (1 - labels) * np.log(1 - probability))),
        })
    return rows


def group_interval(values, groups, seed, repetitions):
    """Descriptive conditional intervals, not a CV significance test."""
    unique = sorted(set(groups))
    values, groups = np.asarray(values, dtype=float), np.asarray(groups)
    mean = float(values.mean())
    if len(unique) < 2:
        return {"mean": mean, "ci95": None, "groups": len(unique), "scope": INTERVAL_SCOPE}
    sums = np.array([values[groups == group].sum() for group in unique])
    counts = np.array([np.sum(groups == group) for group in unique])
    rng, draws = np.random.default_rng(seed), []
    for _ in range(repetitions):
        sampled = rng.integers(0, len(unique), len(unique))
        draws.append(float(sums[sampled].sum() / counts[sampled].sum()))
    return {"mean": mean, "ci95": np.quantile(draws, [.025, .975]).tolist(), "groups": len(unique), "scope": INTERVAL_SCOPE}


def summarize_oof(rows, records, repeats, seed, bootstrap):
    """Average outcomes, not probabilities, over repeats before group resampling."""
    identifiers = [record["id"] for record in records]
    groups = [record["group_id"] for record in records]
    methods, averages, per_repeat = {}, {}, {}
    for method in sorted({row["method"] for row in rows}):
        selected = [row for row in rows if row["method"] == method]
        indexed = {(row["repeat"], row["id"]): row for row in selected}
        if len(indexed) != len(selected) or set(indexed) != {(rep, identifier) for rep in range(repeats) for identifier in identifiers}:
            raise ValueError("OOF predictions must cover each item exactly once per method/repeat")
        arrays = {metric: np.array([[indexed[rep, identifier][metric] for identifier in identifiers] for rep in range(repeats)]) for metric in METRICS}
        averages[method] = {metric: values.mean(axis=0) for metric, values in arrays.items()}
        methods[method] = {metric: group_interval(values, groups, seed, bootstrap) for metric, values in averages[method].items()}
        methods[method]["route_mix"] = {route: sum(row["choice"] == route for row in selected) / len(selected) for route in ROUTES}
        per_repeat[method] = [{"repeat": rep, **{metric: float(values[rep].mean()) for metric, values in arrays.items()},
                               "route_mix": {route: sum(indexed[rep, identifier]["choice"] == route for identifier in identifiers) / len(identifiers) for route in ROUTES}} for rep in range(repeats)]
    comparisons = {}
    for method in methods:
        if method.startswith("fixed_") or method == "training_base_rate":
            continue
        comparisons[method] = {}
        for reference in ("training_base_rate", "fixed_LADDER", "fixed_REACT", "fixed_PAL", "old"):
            if reference == method or reference not in methods:
                continue
            comparisons[method][reference] = {metric: group_interval(averages[method][metric] - averages[reference][metric], groups, seed, bootstrap) for metric in METRICS}
    return {"methods": methods, "per_repeat": per_repeat, "paired_differences": comparisons,
            "interval_scope": INTERVAL_SCOPE, "configuration_selected": None}


def evaluate_development(development, lam, *, configs=DEFAULT_CONFIGS, folds=5, repeats=2, seed=42, bootstrap=2000):
    if not _number(lam) or type(seed) is not int or type(repeats) is not int or repeats < 1 or type(bootstrap) is not int or bootstrap < 1:
        raise ValueError("Invalid lambda, seed, repeats or bootstrap repetitions")
    configs = tuple(configs)
    if not configs or len(set(configs)) != len(configs) or any(config not in CONFIGURATIONS for config in configs):
        raise ValueError("Configurations must be unique supported names")
    if any(record["split"] not in ("train", "calibration") for record in development):
        raise ValueError("Development evaluation must not receive test records")
    train = sorted((record for record in development if record["split"] == "train"), key=lambda row: row["id"])
    calibration = sorted((record for record in development if record["split"] == "calibration"), key=lambda row: row["id"])
    groups = np.array([record["group_id"] for record in train])
    if not train or not calibration or set(groups) & {row["group_id"] for row in calibration}:
        raise ValueError("Train and calibration must be nonempty with disjoint groups")
    # Validate fold settings before any fitting.
    list(outer_splits(groups, folds, seed))
    policy = OptimalStoppingPolicy(lam).fit(calibration_data(calibration))
    data = entry_training_data(train, policy, use_ladder=True)
    rows, assignments = [], []
    for rep in range(repeats):
        for fold, (tr, te) in enumerate(outer_splits(groups, folds, seed + rep)):
            training = _subset(data, tr)
            assignments.append({"repeat": rep, "fold": fold,
                                "train_ids": [train[i]["id"] for i in tr], "evaluation_ids": [train[i]["id"] for i in te],
                                "train_groups": sorted(set(groups[tr])), "evaluation_groups": sorted(set(groups[te]))})
            base_prob = np.broadcast_to(training.accuracy.mean(axis=0), (len(te), 3))
            base_cost = np.broadcast_to(training.cost.mean(axis=0), (len(te), 3))
            heads = {"training_base_rate": (base_prob, base_cost)}
            for config in configs:
                heads[config] = predict_heads(config, training, data.embed[te], data.complexity[te], groups[tr], lam, seed + rep)
            for method, (prob, cost) in heads.items():
                choices = np.argmax(prob - lam * cost, axis=1)
                rows.extend(outcome_rows(method, rep, fold, train, data, te, prob, cost, choices, lam))
            for k, route in enumerate(ROUTES):
                # Fixed routes use the training-only base-rate probabilities for log-loss.
                rows.extend(outcome_rows("fixed_" + route, rep, fold, train, data, te, base_prob, base_cost, np.full(len(te), k), lam))
    summary = summarize_oof(rows, train, repeats, seed, bootstrap)
    realized = data.accuracy - lam * data.cost
    summary["hindsight_only"] = {
        "best_fixed_utility": float(realized.mean(axis=0).max()),
        "oracle_utility": float(realized.max(axis=1).mean()),
        "scope": "Peeks at development outcomes; descriptive references only, never selected as deployable baselines or used for CIs.",
    }
    targets = [{"id": record["id"], "group_id": record["group_id"], "split": "train",
                "route_accuracy": data.accuracy[i].tolist(), "route_cost_k_tokens": data.cost[i].tolist()} for i, record in enumerate(train)]
    return {"summary": summary, "predictions": rows, "folds": assignments, "targets": targets,
            "calibration": {"ids": [row["id"] for row in calibration], "tau": policy.tau, "lambda": lam}}


def render_report(manifest, result):
    lines = ["# Entry predictor — exploratory development evaluation", "",
             f"Evidence: **{manifest['evidence']}**", f"Input token scope: {manifest['input_token_scope']}", "",
             "Calibration fits stopping only. Group-isolated outer CV scores train only; held-out test outcomes are excluded.",
             "No model calls, no configuration selection, no Stage 0 change. Synthetic inputs provide no model-quality evidence.", "",
             "| Method | Accuracy | Mean cost (k units) | Utility | Mean per-repeat log-loss |",
             "| --- | ---: | ---: | ---: | ---: |"]
    for name, metrics in result["summary"]["methods"].items():
        lines.append(f"| {name} | {metrics['accuracy']['mean']:.4f} | {metrics['cost_k_tokens']['mean']:.4f} | {metrics['utility']['mean']:.4f} | {metrics['log_loss']['mean']:.4f} |")
    lines.extend(["", INTERVAL_SCOPE, "", "Intervals and paired differences for accuracy, cost, utility and log-loss are in summary.json; no significance labels are assigned.",
                  "Fixed routes' log-loss uses the same training-only base-rate probabilities. Hindsight fixed/oracle values are descriptive only.",
                  "Costs sum generated-token counts along the selected route and divide by 1000; smoke counts are synthetic units. Prompt/full inference costs and online latency are not measured.",
                  "Negative Ridge cost predictions remain unclipped to match the shared predictor; realized route costs come from frozen attempts.",
                  "Input manifests retain their original source hashes. Current evaluator sources are fingerprinted separately; this is a new retrospective development analysis, not a historical-source verification pass."])
    return "\n".join(lines) + "\n"


def write_evaluation(directory, output, **options):
    directory, output = Path(directory).resolve(), Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError("Entry evaluation requires a new output directory")
    output = output.resolve()
    if output.is_relative_to(directory) or directory.is_relative_to(output):
        raise ValueError("Output must be separate from the recorded input directory")
    loaded = load_recorded_run(directory)
    original = loaded["manifest"]
    result = evaluate_development(loaded["development"], original["lambda"], **options)
    source_names = ("experiments/entry_evaluation.py", "experiments/research_study.py", "reasoning/entry_predictor.py",
                    "reasoning/optimal_stopping.py", "reasoning/reasoning_env.py", "reasoning/reasoning_strategies.py",
                    "research_identity.py", "research_scoring.py", "scripts/gen_tasks.py")
    manifest = {
        "schema_version": 1, "status": "complete", "analysis": "entry_development_group_cv",
        "evidence": "synthetic_development_cv" if original["backend"] == "smoke" else "exploratory_recorded_development_cv",
        "confirmatory": False, "stage_0_changed": False, "real_model_calls": 0, "configuration_selected": None,
        "input_directory": loaded["directory"], "input_manifest_sha256": loaded["manifest_sha256"],
        "input_manifest": original, "input_token_scope": original["token_scope"],
        "excluded_test_items": loaded["excluded_test_items"],
        "evaluated_split": "train", "stopping_fit_split": "calibration", "inner_cv_group_isolated": True,
        "inner_cv_fallback": "Use fixed strong regularization without CV when group-isolated tuning is impossible; never split a group to enable tuning",
        "estimand": "Query-weighted mean of repeat-averaged OOF outcomes; original groups are bootstrap units",
        "settings": {"configs": list(DEFAULT_CONFIGS), "folds": 5, "repeats": 2, "seed": 42, "bootstrap": 2000, **options, "lambda": original["lambda"]},
        "python": sys.version, "platform": platform.platform(),
        "packages": {name: importlib.metadata.version(name) for name in ("numpy", "scikit-learn")},
        "git_sha": git_value("rev-parse", "HEAD"), "git_status": git_value("status", "--porcelain"),
        "source_sha256": {name: _digest((ROOT / name).read_bytes()) for name in source_names},
        "interval_scope": INTERVAL_SCOPE,
    }
    # Finish computation before creating any output. Never overwrite input/old analyses.
    output.mkdir(parents=True, exist_ok=False)
    for name in ("summary", "predictions", "folds", "targets", "calibration"):
        write_json(output / f"{name}.json", result[name])
    (output / "report.md").write_text(render_report(manifest, result), encoding="utf-8")
    manifest["artifact_sha256"] = {path.name: _digest(path.read_bytes()) for path in sorted(output.iterdir())}
    write_json(output / "manifest.json", manifest)
    return manifest
