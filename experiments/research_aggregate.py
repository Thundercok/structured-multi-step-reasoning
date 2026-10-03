"""Aggregate compatible research runs without treating seeds as new questions."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from experiments.research_study import (
    ROOT, STRATEGY_LABELS, summarize, summarize_methods, validate_dataset, write_json,
)
from reasoning_env import LADDER, STRATEGIES


METHODS = {f"fixed_{strategy.name.lower()}" for strategy in STRATEGIES} | {
    "ladder_only", "one_shot_router", "entry_without_escalation", "full_policy",
}
COMPATIBILITY_FIELDS = (
    "schema_version", "backend", "evidence", "token_scope", "model",
    "model_revision_verified", "lambda", "source_sha256", "strategy_labels",
    "python", "packages", "platform",
)
REQUIRED_ARTIFACTS = {
    "dataset.json", "records.json", "policy.json", "results.json", "summary.json", "report.md",
}
MEAN_FIELDS = ("correct", "tokens", "strategy_ms_sum", "embedding_ms", "escalated")


def _finite_number(value, minimum=0):
    return (
        isinstance(value, (int, float)) and not isinstance(value, bool)
        and math.isfinite(value) and value >= minimum
    )


def validate_results(dataset, results):
    """Require exactly one valid test outcome per query and method."""
    if not isinstance(dataset, dict):
        raise ValueError("Frozen dataset must be an object")
    items = validate_dataset(dataset)
    test = {item["id"]: item for item in items if item["split"] == "test"}
    if not isinstance(results, list) or not results:
        raise ValueError("Results must be a nonempty list")
    indexed = {}
    ladder = [strategy.name for strategy in LADDER]
    for row in results:
        if not isinstance(row, dict):
            raise ValueError("Every result must be an object")
        identifier, method = row.get("id"), row.get("method")
        if not isinstance(identifier, str) or identifier not in test:
            raise ValueError("Results may contain only frozen test IDs")
        if not isinstance(method, str) or method not in METHODS:
            raise ValueError("Unknown or missing result method")
        key = (identifier, method)
        if key in indexed:
            raise ValueError(f"Duplicate result for {identifier}/{method}")
        if row.get("group_id") != test[identifier]["group_id"]:
            raise ValueError(f"Result group differs from dataset: {identifier}")
        if not isinstance(row.get("answer"), str) or type(row.get("correct")) is not bool:
            raise ValueError("Results require a string answer and boolean correctness")
        if type(row.get("tokens")) is not int or row["tokens"] <= 0:
            raise ValueError("Result token cost must be a positive integer")
        if not all(_finite_number(row.get(field)) for field in ("strategy_ms_sum", "embedding_ms")):
            raise ValueError("Result timings must be finite and nonnegative")
        path = row.get("path")
        if not isinstance(path, list) or not path or not all(isinstance(step, str) for step in path):
            raise ValueError("Results require a nonempty strategy path")
        if method.startswith("fixed_"):
            valid_path = path == [method.removeprefix("fixed_").upper()]
        elif method in ("one_shot_router", "entry_without_escalation"):
            valid_path = path in (["COT"], ["REACT"], ["PAL"])
        else:
            valid_path = path == ladder[:len(path)]
            if method == "full_policy":
                valid_path = valid_path or path in (["REACT"], ["PAL"])
        if not valid_path:
            raise ValueError(f"Invalid strategy path for {method}")
        if type(row.get("escalated")) is not bool or row["escalated"] != (len(path) > 1):
            raise ValueError("Escalation flag disagrees with strategy path")
        indexed[key] = row
    expected = {(identifier, method) for identifier in test for method in METHODS}
    if indexed.keys() != expected:
        raise ValueError("Every method requires the identical complete test query set")
    for identifier in test:
        if indexed[identifier, "full_policy"]["path"][0] != indexed[identifier, "entry_without_escalation"]["path"][0]:
            raise ValueError("Entry ablation must share the full policy's initial strategy")
    return indexed


def load_run(directory):
    """Verify saved bytes before using outcomes; do not trust summary tables."""
    directory = Path(directory).resolve()
    manifest_bytes = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if not isinstance(manifest, dict) or manifest.get("status") != "complete":
        raise ValueError(f"Only complete collection/replay runs can be aggregated: {directory}")
    if manifest.get("pilot"):
        raise ValueError("Development pilot diagnostics cannot be aggregated as held-out study results")
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise ValueError("Unsupported input manifest schema")
    for field in COMPATIBILITY_FIELDS:
        if field not in manifest:
            raise ValueError(f"Input manifest lacks {field}")
    if type(manifest.get("seed")) is not int or not _finite_number(manifest["lambda"]):
        raise ValueError("Input seed must be an integer and lambda finite/nonnegative")
    evidence = {"smoke": "synthetic_smoke", "mlx": "measured_strategy_replay"}
    if not isinstance(manifest["backend"], str) or manifest["backend"] not in evidence or manifest["evidence"] != evidence[manifest["backend"]]:
        raise ValueError("Input backend and evidence label disagree")
    if manifest["backend"] == "mlx" and (not isinstance(manifest["model"], str) or not manifest["model"].strip()):
        raise ValueError("Measured inputs require recorded model metadata")
    if type(manifest["model_revision_verified"]) is not bool:
        raise ValueError("Input model verification flag must be boolean")
    if not isinstance(manifest["token_scope"], str) or not manifest["token_scope"].strip():
        raise ValueError("Input requires an explicit token scope")
    sources = manifest["source_sha256"]
    valid_sources = isinstance(sources, dict) and bool(sources) and all(
        isinstance(name, str) and isinstance(digest, str) and len(digest) == 64
        and all(char in "0123456789abcdef" for char in digest)
        for name, digest in sources.items()
    )
    if manifest["strategy_labels"] != STRATEGY_LABELS or not valid_sources:
        raise ValueError("Input requires the supported strategies and frozen source hashes")
    hashes = manifest.get("artifact_sha256")
    if not isinstance(hashes, dict) or not REQUIRED_ARTIFACTS <= hashes.keys():
        raise ValueError("Input manifest lacks required artifact hashes")
    if "replayed_from" not in manifest and "attempts.jsonl" not in hashes:
        raise ValueError("Collection inputs require the raw attempts artifact hash")
    artifacts = {}
    for name, expected in hashes.items():
        if not isinstance(name, str) or Path(name).name != name or name in (".", "..", "manifest.json"):
            raise ValueError("Artifact hashes must refer to files within the run directory")
        data = (directory / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"Input artifact changed: {directory / name}")
        if name in ("dataset.json", "records.json", "results.json"):
            artifacts[name] = json.loads(data)
    indexed = validate_results(artifacts["dataset.json"], artifacts["results.json"])
    validate_record_outcomes(artifacts["dataset.json"], artifacts["records.json"], indexed)
    return {
        "directory": str(directory), "manifest": manifest,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "dataset": artifacts["dataset.json"], "results": artifacts["results.json"],
        "indexed": indexed,
    }


def validate_record_outcomes(dataset, records, indexed):
    """Check reported answers and cumulative costs against the recorded attempts."""
    items = {item["id"]: item for item in dataset["items"]}
    if not isinstance(records, list) or len(records) != len(items):
        raise ValueError("Records require complete dataset coverage")
    by_id = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            raise ValueError("Each record requires an item ID")
        identifier = record["id"]
        if identifier not in items or identifier in by_id:
            raise ValueError("Records contain duplicate or unknown IDs")
        if any(record.get(field) != items[identifier][field] for field in ("group_id", "split")):
            raise ValueError("Record split/group disagrees with dataset")
        attempts = record.get("attempts")
        if not isinstance(attempts, dict) or attempts.keys() != {strategy.name for strategy in STRATEGIES}:
            raise ValueError("Records require every fixed strategy attempt")
        if not _finite_number(record.get("embedding_ms")):
            raise ValueError("Record embedding time must be finite/nonnegative")
        for attempt in attempts.values():
            if not isinstance(attempt, dict) or not isinstance(attempt.get("answer"), str) or type(attempt.get("correct")) is not bool:
                raise ValueError("Recorded attempts require answers and boolean correctness")
            if type(attempt.get("tokens")) is not int or attempt["tokens"] <= 0:
                raise ValueError("Recorded token counts must be positive integers")
            if not _finite_number(attempt.get("strategy_ms")):
                raise ValueError("Recorded strategy time must be finite/nonnegative")
        by_id[identifier] = record
    for (identifier, method), row in indexed.items():
        record = by_id[identifier]
        attempts = [record["attempts"][step] for step in row["path"]]
        if any(row[field] != attempts[-1][field] for field in ("answer", "correct")):
            raise ValueError("Result answer/correctness disagrees with recorded final attempt")
        if row["tokens"] != sum(attempt["tokens"] for attempt in attempts):
            raise ValueError("Result token cost disagrees with recorded strategy path")
        if not math.isclose(row["strategy_ms_sum"], sum(attempt["strategy_ms"] for attempt in attempts)):
            raise ValueError("Result strategy time disagrees with recorded path")
        expected_embedding = record["embedding_ms"] if method in ("one_shot_router", "entry_without_escalation", "full_policy") else 0
        if not math.isclose(row["embedding_ms"], expected_embedding):
            raise ValueError("Result embedding time disagrees with recorded overhead")


def aggregate_runs(directories, bootstrap_seed=42):
    if len(directories) < 2:
        raise ValueError("Aggregation requires at least two distinct generation seeds")
    if len({Path(path).resolve() for path in directories}) != len(directories):
        raise ValueError("Input run directories must be distinct")
    runs = sorted((load_run(path) for path in directories), key=lambda run: run["manifest"]["seed"])
    reference = runs[0]["manifest"]
    seeds = [run["manifest"]["seed"] for run in runs]
    if len(set(seeds)) != len(seeds):
        raise ValueError("Duplicate generation seed; replay copies are not independent runs")
    for run in runs[1:]:
        for field in COMPATIBILITY_FIELDS:
            if run["manifest"][field] != reference[field]:
                raise ValueError(f"Incompatible runs: {field} differs")
        if run["manifest"]["artifact_sha256"]["dataset.json"] != reference["artifact_sha256"]["dataset.json"]:
            raise ValueError("Incompatible runs: frozen dataset differs")
    # Each question still contributes once: average its outcomes over observed seeds.
    averaged = []
    for key in sorted(runs[0]["indexed"]):
        rows = [run["indexed"][key] for run in runs]
        averaged.append({
            "id": key[0], "method": key[1], "group_id": rows[0]["group_id"],
            **{field: float(np.mean([row[field] for row in rows])) for field in MEAN_FIELDS},
        })
    summary = summarize(averaged, reference["lambda"], bootstrap_seed)
    per_seed = [
        {"seed": run["manifest"]["seed"], "methods": summarize_methods(run["results"], reference["lambda"])}
        for run in runs
    ]
    for method, metrics in summary["methods"].items():
        metrics["seed_variability"] = {}
        for metric in ("accuracy", "mean_tokens", "utility", "escalation_rate"):
            values = [row["methods"][method][metric] for row in per_seed]
            metrics["seed_variability"][metric] = {
                "sample_sd": float(np.std(values, ddof=1)), "min": min(values), "max": max(values),
            }
    test_items = [item for item in runs[0]["dataset"]["items"] if item["split"] == "test"]
    summary.update(
        generation_seeds=seeds, seed_count=len(seeds), per_seed=per_seed,
        test_queries=len(test_items), test_groups=len({item["group_id"] for item in test_items}),
        bootstrap={
            "seed": bootstrap_seed, "repetitions": 2000, "unit": "original problem group",
            "seed_handling": "Average each query over the observed generation seeds before group resampling",
            "conditioning": "Frozen fitted policies and observed seed set; excludes policy-fitting and seed-population uncertainty",
        },
    )
    return runs, summary


def render_report(manifest, summary):
    lines = [
        "# Reasoning research aggregate", "", f"Evidence: **{manifest['evidence']}**", "",
        f"Generation seeds: {summary['generation_seeds']}. Unique test questions: {summary['test_queries']}; original problem groups: {summary['test_groups']}.",
        "Seeds are repeated generations of the same questions; they do not increase the number of independent questions.",
        "Synthetic smoke runs validate software only. This aggregate requires review before supporting manuscript claims.", "",
        "| Method | Test N | Mean accuracy | Accuracy SD across seeds | Mean tokens | Mean utility | Mean escalation |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for method, metrics in summary["methods"].items():
        sd = metrics["seed_variability"]["accuracy"]["sample_sd"]
        lines.append(f"| {method} | {metrics['n']} | {metrics['accuracy']:.3f} | {sd:.3f} | {metrics['mean_tokens']:.1f} | {metrics['utility']:.3f} | {metrics['escalation_rate']:.3f} |")
    lines.extend([
        "", "Differences are full policy minus baseline. Accuracy differences use the 0–1 scale; negative token differences mean fewer tokens.",
        "Paired percentile 95% intervals first average seeds per query, then resample original problem groups (2,000 draws).",
        "Intervals are conditional on the frozen fitted policies and the observed seed set. They exclude fitting uncertainty and generalization to new seeds.",
        "Sample SD across seeds is descriptive. One problem group yields no interval.", "",
        "| Baseline | Metric | Mean difference | Paired 95% interval |",
        "| --- | --- | ---: | --- |",
    ])
    for baseline, comparisons in summary["paired_full_minus_baseline"].items():
        for metric, comparison in comparisons.items():
            lines.append(f"| {baseline} | {metric} | {comparison['mean_difference']:.4f} | {comparison['ci95']} |")
    lines.extend([
        "", "## Per-seed outcomes", "",
        "| Seed | Method | Test N | Accuracy | Mean tokens | Utility | Escalation |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    for run in summary["per_seed"]:
        for method, metrics in run["methods"].items():
            lines.append(f"| {run['seed']} | {method} | {metrics['n']} | {metrics['accuracy']:.3f} | {metrics['mean_tokens']:.1f} | {metrics['utility']:.3f} | {metrics['escalation_rate']:.3f} |")
    lines.extend([
        "", f"Token scope: {manifest['token_scope']}. Utility penalty lambda: {manifest['lambda']}.",
        "Strategy time sums are replay estimates, not measured online policy latency. Prompt tokens, router overhead and model loading remain outside the generated-token comparison.",
        "Matching model paths and manifest metadata do not verify checkpoint identity or dataset review. Consult original raw artifacts and model provenance.",
        "Choose generation seeds and comparisons before viewing test results; this tool cannot establish preregistration or authorize the Stage 0 campaign.",
        "", "## Input artifacts", "",
    ])
    for run in manifest["inputs"]:
        lines.append(f"- Seed {run['seed']}: `{run['directory']}`; manifest SHA-256 `{run['manifest_sha256']}`.")
    return "\n".join(lines) + "\n"


def write_aggregate(directories, output):
    runs, summary = aggregate_runs(directories)
    reference = runs[0]["manifest"]
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "schema_version": 1, "kind": "multi_seed_aggregate", "status": "running",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        **{field: reference[field] for field in COMPATIBILITY_FIELDS if field != "schema_version"},
        "generation_seeds": summary["generation_seeds"], "publication_review_required": True,
        "analysis_source_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in ("experiments/research_aggregate.py", "experiments/research_study.py")
        },
        "inputs": [
            {"directory": run["directory"], "seed": run["manifest"]["seed"],
             "manifest_sha256": run["manifest_sha256"], "artifact_sha256": run["manifest"]["artifact_sha256"]}
            for run in runs
        ],
    }
    write_json(output / "manifest.json", manifest)
    try:
        write_json(output / "summary.json", summary)
        (output / "report.md").write_text(render_report(manifest, summary), encoding="utf-8")
        manifest["artifact_sha256"] = {
            name: hashlib.sha256((output / name).read_bytes()).hexdigest()
            for name in ("summary.json", "report.md")
        }
        manifest.update(status="complete", finished_utc=datetime.now(timezone.utc).isoformat())
        write_json(output / "manifest.json", manifest)
    except BaseException as error:
        manifest.update(status="failed", error=f"{type(error).__name__}: {error}")
        write_json(output / "manifest.json", manifest)
        raise
    print(f"{manifest['evidence']} aggregate: {output / 'report.md'}")
