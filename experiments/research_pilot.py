"""Development diagnostics; no held-out evaluation or controller fitting."""

from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import json
import math
import platform
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from experiments.research_study import (
    ROOT, STRATEGY_LABELS, check_answer, git_value, seed_for, smoke_dataset,
    source_hashes, validate_dataset, write_json,
)
from reasoning_env import ReasoningAction as A


PILOT_STRATEGIES = (A.DIRECT, A.COT, A.SELF_CONSISTENCY, A.TOT, A.REACT, A.PAL)


def select_groups(dataset, seed, groups_per_stratum):
    """Rank whole groups by ID and seed, without consulting answers/outcomes."""
    items = validate_dataset(dataset, pilot=True)
    groups = defaultdict(list)
    for item in items:
        groups[item["group_id"]].append(item)
    strata = defaultdict(list)
    for group, variants in groups.items():
        keys = {(item["split"], str(item.get("family", item.get("category", "unspecified"))),
                 str(item.get("level", "unspecified"))) for item in variants}
        if len(keys) != 1:
            raise ValueError("Pilot group variants must share split, family/category and level")
        strata[next(iter(keys))].append(group)
    selected, counts = set(), []
    for key, candidates in sorted(strata.items()):
        ranked = sorted(candidates, key=lambda group: (
            hashlib.sha256(f"{seed}:pilot-selection:{group}".encode()).hexdigest(), group,
        ))
        chosen = ranked[:groups_per_stratum]
        selected.update(chosen)
        counts.append({"split": key[0], "family": key[1], "level": key[2],
                       "available_groups": len(candidates), "selected_groups": len(chosen)})
    result = copy.deepcopy(dataset)
    result["items"] = sorted((copy.deepcopy(item) for item in items if item["group_id"] in selected), key=lambda item: item["id"])
    return result, {"seed": seed, "groups_per_stratum": groups_per_stratum,
                    "strata": counts, "selected_group_ids": sorted(selected)}


def synthetic_dataset():
    dataset = smoke_dataset(pilot=True)
    for item in dataset["items"]:
        category, split, index = item["id"].split("_")
        item.update(category=category, level=int(index) // 2 + 1,
                    group_id=f"{category}_{split}_group_{int(index) // 2}")
    return dataset


class PilotSmokeBackend:
    """Artificial traces and token units for exercising the pilot artifact contract."""

    def configure_answer_format(self, **metadata):
        self.answer_format = metadata

    def run(self, strategy, query):
        ok = self.rng.random() < 0.5
        confidence = float(self.rng.uniform(0.1, 0.9))
        required = 120 if strategy == A.DIRECT else 300
        calls = 5 if strategy == A.SELF_CONSISTENCY else 4 if strategy == A.TOT else 1
        cap = min(200, self.max_tokens) if strategy == A.REACT else self.max_tokens
        count = min(required, cap)
        truncated = required > cap
        answer = "OK" if ok and not truncated else "wrong"
        self.last_trace = {
            "synthetic": True, "strategy": strategy.name, "parse_status": "fail" if truncated else "marker",
            "answer_format": self.answer_format, "tools": [],
            "generations": [{"output": f"Answer: {answer}", "tokens": count,
                "prompt_tokens": 1, "messages": [{"role": "user", "content": query}],
                "max_tokens": cap, "temperature": 0.0, "enable_thinking": False,
                "finish_reason": "length" if truncated else "stop"} for _ in range(calls)],
        }
        return answer, confidence, count * calls


def collect(backend, dataset, strategies, budgets, seed, set_seed, event_file):
    records = []
    for item in dataset["items"]:
        metadata = {"answer_type": "expression" if item.get("family") == "g24" else item["answer_type"],
                    "decimal_separator": item.get("decimal_separator", ".")}
        backend.configure_answer_format(**metadata)
        conditions = [(strategy, budget) for strategy in strategies for budget in budgets]
        order = np.random.default_rng(seed_for(seed, item["id"], "pilot-order")).permutation(len(conditions))
        for index in order:
            strategy, budget = conditions[index]
            action_seed = seed_for(seed, item["id"], strategy.name)
            set_seed(action_seed)
            backend.max_tokens = budget
            started = time.perf_counter()
            answer, confidence, tokens = backend.run(strategy, item["query"])
            elapsed_ms = (time.perf_counter() - started) * 1000
            if not math.isfinite(confidence) or not 0 <= confidence <= 1:
                raise ValueError("Backend confidence must be finite and in [0, 1]")
            if isinstance(tokens, bool) or not isinstance(tokens, (int, np.integer)) or tokens <= 0:
                raise ValueError("Backend must report a positive integer token count")
            trace = copy.deepcopy(backend.last_trace)
            generations = trace.get("generations", [])
            if not generations or sum(row["tokens"] for row in generations) != tokens:
                raise ValueError("Pilot generated-token cost must match all generation calls")
            if any(not 0 < row["tokens"] <= row["max_tokens"] <= budget for row in generations):
                raise ValueError("Pilot generation exceeds its declared per-call budget")
            record = {
                "id": item["id"], "group_id": item["group_id"], "split": item["split"],
                "family": str(item.get("family", item.get("category", "unspecified"))),
                "level": str(item.get("level", "unspecified")), "strategy": strategy.name,
                "token_budget": budget, "seed": action_seed, "answer_format": metadata,
                "answer": str(answer), "correct": bool(check_answer(answer, item)),
                "confidence": float(confidence), "tokens": int(tokens), "strategy_ms": elapsed_ms,
                "trace": trace,
            }
            records.append(record)
            event_file.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
            event_file.flush()
    return records


def summarize(records):
    cells = defaultdict(list)
    for record in records:
        cells[(record["split"], record["family"], record["level"], record["strategy"], record["token_budget"])].append(record)
    rows = []
    for key, attempts in sorted(cells.items()):
        n = len(attempts)
        rows.append({
            "split": key[0], "family": key[1], "level": key[2], "strategy": key[3], "token_budget": key[4],
            "items": n, "groups": len({row["group_id"] for row in attempts}),
            "correct": sum(row["correct"] for row in attempts),
            "accuracy": sum(row["correct"] for row in attempts) / n,
            "mean_generated_tokens": sum(row["tokens"] for row in attempts) / n,
            "mean_prompt_tokens": sum(sum(g["prompt_tokens"] for g in row["trace"]["generations"]) for row in attempts) / n,
            "mean_strategy_ms": sum(row["strategy_ms"] for row in attempts) / n,
            "parse_failures": sum(row["trace"].get("parse_status") == "fail" for row in attempts),
            "attempts_with_length_stop": sum(any(g["finish_reason"] == "length" for g in row["trace"]["generations"]) for row in attempts),
            "high_confidence_errors_at_0_8": sum(not row["correct"] and row["confidence"] >= 0.8 for row in attempts),
        })
    return {"development_only": True, "descriptive_only": True, "policy_fitted": False, "cells": rows}


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def local_model_metadata(model):
    path = Path(model).expanduser().resolve()
    weights = sorted(path.glob("*.safetensors"))
    if not path.is_dir() or not (path / "config.json").is_file() or not weights:
        raise ValueError("Pilot MLX requires a local model directory with config.json and safetensors weights; repository IDs are rejected")
    files = sorted(set(weights + list(path.glob("*.json")) + list(path.glob("*.model"))))
    return str(path), {file.name: sha256_file(file) for file in files}


def render_report(manifest, summary):
    lines = ["# Development-only research pilot", "", f"Evidence: **{manifest['evidence']}**", "",
        "Fixed-strategy diagnostics on exposed development groups. No held-out evaluation or policy fitting.",
        "Synthetic smoke traces validate software only; they provide no model-quality evidence.",
        "Budgets cap each generation call; multi-call strategies can consume more total tokens. ReAct also retains its 200-token per-turn ceiling.",
        "Timings are measured strategy-call duration (Python only for smoke), not online controller latency. Prompt counts are separate from generated-token costs.",
        "Cells count questions and original groups separately. Variants and budget repetitions are not independent problems. No confidence intervals or superiority claims are inferred.", "",
        "| Split | Family | Level | Strategy | Cap/call | Items/groups | Accuracy | Mean generated tokens | Parse failures | Length stops |",
        "| --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: |"]
    for row in summary["cells"]:
        lines.append(f"| {row['split']} | {row['family']} | {row['level']} | {row['strategy']} | {row['token_budget']} | {row['items']}/{row['groups']} | {row['accuracy']:.3f} | {row['mean_generated_tokens']:.1f} | {row['parse_failures']} | {row['attempts_with_length_stop']} |")
    lines.extend(["", f"Token scope: {manifest['token_scope']}.",
        "Human/source review and pilot configuration review remain pending. Parameters are not frozen. Stage 0 is unchanged.", ""])
    return "\n".join(lines)


def verify_replay(directory, manifest):
    if manifest.get("status") != "complete" or manifest.get("pilot") is not True:
        raise ValueError("Only complete development pilot runs can be replayed here")
    if source_hashes() != manifest.get("source_sha256"):
        raise ValueError("Replay requires the original implementation; source hashes differ")
    hashes = manifest.get("artifact_sha256", {})
    if not {"dataset.json", "records.json", "selection.json", "summary.json", "report.md"} <= hashes.keys():
        raise ValueError("Pilot replay requires complete artifact hashes")
    for name, digest in hashes.items():
        if Path(name).name != name or sha256_file(directory / name) != digest:
            raise ValueError(f"Replay artifact changed: {name}")
    dataset = json.loads((directory / "dataset.json").read_text())
    items = validate_dataset(dataset, pilot=True)
    records = json.loads((directory / "records.json").read_text())
    expected = {(item["id"], strategy, budget) for item in items for strategy in manifest["strategies"] for budget in manifest["token_budgets"]}
    actual = [(row["id"], row["strategy"], row["token_budget"]) for row in records]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("Pilot records must contain every selected item/strategy/budget exactly once")
    return dataset, records, json.loads((directory / "selection.json").read_text())


def run(args, parser, replay_manifest=None):
    if replay_manifest is not None:
        dataset, records, selection = verify_replay(args.replay, replay_manifest)
        manifest = {**replay_manifest, "replayed_from": str(args.replay.resolve())}
    else:
        if args.lam is not None:
            parser.error("Pilot collects both development splits without policy utility or fitting; --lam is inapplicable")
        strategies = tuple(A[name] for name in (args.strategies or ["DIRECT", "COT"]))
        budgets = args.token_budgets or ([args.max_tokens] if args.max_tokens is not None else [96, 1024])
        count = args.groups_per_stratum if args.groups_per_stratum is not None else 1
        if len(strategies) != len(set(strategies)) or any(strategy not in PILOT_STRATEGIES for strategy in strategies):
            parser.error("Pilot requires distinct supported reasoning strategies")
        if len(budgets) != len(set(budgets)) or any(budget <= 0 for budget in budgets) or count <= 0:
            parser.error("Token budgets and groups per stratum must be positive; budgets must be distinct")
        if args.backend == "smoke" and (args.dataset is not None or args.model is not None):
            parser.error("Smoke runs use only the bundled synthetic fixture")
        if args.backend == "mlx" and (args.dataset is None or args.model is None):
            parser.error("Pilot MLX requires --dataset and --model")
        seed = 42 if args.seed is None else args.seed
        original = synthetic_dataset() if args.backend == "smoke" else json.loads(args.dataset.read_text())
        dataset, selection = select_groups(original, seed, count)
        model, model_hashes = local_model_metadata(args.model) if args.backend == "mlx" else (None, {})
        packages = {}
        for name in ("numpy", "scikit-learn", "gymnasium", "mlx", "mlx-lm"):
            try:
                packages[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                packages[name] = None
        manifest = {
            "schema_version": 1, "pilot": True, "mode": "development_pilot", "backend": args.backend,
            "seed": seed, "model": model, "model_content_sha256": model_hashes,
            "model_revision_verified": False, "publication_ready": False, "policy_fitted": False,
            "evidence": "synthetic_pilot_smoke" if args.backend == "smoke" else "measured_development_pilot",
            "token_scope": "synthetic token units" if args.backend == "smoke" else "generated tokens summed over all calls; prompt tokens recorded separately",
            "strategies": [strategy.name for strategy in strategies], "strategy_labels": STRATEGY_LABELS,
            "token_budgets": budgets, "budget_scope": "per generation call; ReAct min(cap, 200)",
            "input_dataset_sha256": sha256_file(args.dataset) if args.dataset else None,
            "source_sha256": source_hashes(), "git_sha": git_value("rev-parse", "HEAD"),
            "git_status": git_value("status", "--porcelain"), "python": sys.version,
            "platform": platform.platform(), "packages": packages,
            "stage0_decision_sha256": sha256_file(ROOT / "docs/stage0_gate_decision.md"),
            "stage0_reevaluated": False,
        }
    args.output.mkdir(parents=True, exist_ok=False)
    manifest.update(status="running", started_utc=datetime.now(timezone.utc).isoformat())
    write_json(args.output / "manifest.json", manifest)
    write_json(args.output / "dataset.json", dataset)
    write_json(args.output / "selection.json", selection)
    try:
        if replay_manifest is None:
            started = time.perf_counter()
            if args.backend == "smoke":
                backend = PilotSmokeBackend()

                def set_seed(value):
                    backend.rng = np.random.default_rng(value)
            else:
                import mlx.core as mx
                from qwen_mlx_backend import QwenMLXBackend
                backend = QwenMLXBackend(repo=model)
                set_seed = mx.random.seed
            manifest["backend_load_ms"] = (time.perf_counter() - started) * 1000
            with (args.output / "attempts.jsonl").open("w", encoding="utf-8") as stream:
                records = collect(backend, dataset, strategies, budgets, seed, set_seed, stream)
        write_json(args.output / "records.json", records)
        summary = summarize(records)
        write_json(args.output / "summary.json", summary)
        (args.output / "report.md").write_text(render_report(manifest, summary), encoding="utf-8")
        manifest["artifact_sha256"] = {path.name: sha256_file(path) for path in sorted(args.output.iterdir()) if path.is_file() and path.name != "manifest.json"}
        manifest.update(status="complete", finished_utc=datetime.now(timezone.utc).isoformat())
        write_json(args.output / "manifest.json", manifest)
    except BaseException as error:
        manifest.update(status="failed", error=f"{type(error).__name__}: {error}")
        write_json(args.output / "manifest.json", manifest)
        raise
    print(f"{manifest['evidence']}: {args.output / 'report.md'}")
