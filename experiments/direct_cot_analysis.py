"""Development-only replay analysis for a DIRECT -> CoT fail-only cascade.

This module never calls a model.  It consumes a completed, hashed development
pilot containing matched DIRECT and COT attempts collected with the aligned
prompt profile.  The deployable rule is intentionally fixed before looking at
validation outcomes: escalate when DIRECT violates the answer-format contract
or any DIRECT generation reaches its length cap.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from experiments.research_study import (
    ROOT, check_answer, git_value, seed_for, validate_dataset, write_json,
)
from research_prompt_profiles import ALIGNED_DIRECT_COT_SUFFIX_TEXT
from reasoning_strategies import parse_answer_details


PROMPT_PROFILE = "aligned-direct-cot-v1"
METHODS = (
    "fixed_direct",
    "fixed_cot",
    "direct_cot_format_or_length",
    "always_direct_cot",
    "oracle_direct_cot_utility",
)
REQUIRED_ARTIFACTS = {"dataset.json", "records.json", "selection.json", "summary.json", "report.md"}
ANALYSIS_SOURCE_FILES = (
    "experiments/direct_cot_analysis.py",
    "experiments/research_study.py",
    "research_identity.py",
    "research_prompt_profiles.py",
    "research_scoring.py",
    "reasoning_strategies.py",
    "scripts/gen_tasks.py",
)
DIRECT_MAX_VISIBLE_RATIONALE_RATE = 0.05
COT_MIN_VISIBLE_RATIONALE_RATE = 0.80
DECISION_LAMBDA = 0.02
DECISION_TOKEN_BUDGET = 1024
ANSWER_MARKER = re.compile(
    r"(?im)^\s*(?:#{1,6}\s*)?(?:\*\*)?(?:final\s+)?answer(?:\*\*)?\s*:\s*"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def analysis_source_hashes() -> dict[str, str]:
    return {name: sha256_file(ROOT / name) for name in ANALYSIS_SOURCE_FILES}


def _finite_number(value, minimum=0.0) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= minimum
    )


def _generation_cost(record: dict) -> tuple[int, int]:
    trace = record.get("trace")
    generations = trace.get("generations") if isinstance(trace, dict) else None
    if not isinstance(generations, list) or not generations:
        raise ValueError("DIRECT/CoT analysis requires recorded generation traces")
    generated = 0
    prompt = 0
    for generation in generations:
        tokens = generation.get("tokens")
        prompt_tokens = generation.get("prompt_tokens")
        if type(tokens) is not int or tokens <= 0 or type(prompt_tokens) is not int or prompt_tokens < 0:
            raise ValueError("Generation token counts must be nonnegative integers")
        generated += tokens
        prompt += prompt_tokens
    if generated != record.get("tokens"):
        raise ValueError("Record token cost disagrees with its generation trace")
    return generated, prompt


def _visible_rationale(record: dict) -> bool:
    """Whether non-whitespace text precedes the final Answer marker."""
    generations = record["trace"]["generations"]
    text = "\n".join(str(generation.get("output", "")) for generation in generations)
    markers = list(ANSWER_MARKER.finditer(text))
    return bool(markers and text[:markers[-1].start()].strip())


def _direct_failure_reasons(record: dict) -> list[str]:
    reasons = []
    if record["trace"].get("parse_status") != "marker":
        reasons.append("answer_format")
    elif record["trace"].get("wordy") is True:
        reasons.append("answer_format")
    if any(generation.get("finish_reason") == "length" for generation in record["trace"]["generations"]):
        reasons.append("length")
    return reasons


def load_pilot(directory: Path, budget: int | None = None) -> dict:
    """Verify a complete aligned development pilot and return paired attempts."""
    directory = directory.resolve()
    manifest_path = directory / "manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if (
        not isinstance(manifest, dict)
        or manifest.get("status") != "complete"
        or manifest.get("pilot") is not True
        or manifest.get("mode") != "development_pilot"
        or manifest.get("policy_fitted") is not False
        or manifest.get("schema_version") != 1
    ):
        raise ValueError("DIRECT/CoT analysis requires a complete development-only pilot")
    if manifest.get("prompt_profile") != PROMPT_PROFILE:
        raise ValueError(f"DIRECT/CoT analysis requires prompt profile {PROMPT_PROFILE}")
    if manifest.get("strategies") not in (["DIRECT", "COT"], ["COT", "DIRECT"]):
        raise ValueError("Aligned pilot must contain exactly DIRECT and COT")
    backend = manifest.get("backend")
    expected_evidence = {
        "smoke": "synthetic_pilot_smoke",
        "mlx": "measured_development_pilot",
    }
    if backend not in expected_evidence or manifest.get("evidence") != expected_evidence[backend]:
        raise ValueError("Pilot backend and evidence labels are inconsistent")
    frozen_sources = manifest.get("source_sha256")
    if not isinstance(frozen_sources, dict):
        raise ValueError("Pilot manifest lacks frozen source hashes")
    for name in ANALYSIS_SOURCE_FILES:
        if name == "experiments/direct_cot_analysis.py":
            continue
        if frozen_sources.get(name) != sha256_file(ROOT / name):
            raise ValueError(f"Pilot semantic source differs from current implementation: {name}")

    hashes = manifest.get("artifact_sha256")
    if not isinstance(hashes, dict) or not REQUIRED_ARTIFACTS <= hashes.keys():
        raise ValueError("Pilot manifest lacks required artifact hashes")
    for name, expected in hashes.items():
        if not isinstance(name, str) or Path(name).name != name or name == "manifest.json":
            raise ValueError("Artifact hashes must name files inside the pilot directory")
        if not isinstance(expected, str) or sha256_file(directory / name) != expected:
            raise ValueError(f"Pilot artifact changed: {name}")

    provenance_valid = False
    if backend == "mlx" and "model_provenance.json" in hashes:
        provenance = json.loads((directory / "model_provenance.json").read_text(encoding="utf-8"))
        rows = provenance.get("files", []) if isinstance(provenance, dict) else []
        content_hashes = manifest.get("model_content_sha256")
        row_hashes = {
            row.get("name"): row.get("sha256")
            for row in rows if isinstance(row, dict) and isinstance(row.get("name"), str)
        }
        provenance_valid = bool(
            manifest.get("model_revision_verified") is True
            and isinstance(manifest.get("model"), str)
            and isinstance(content_hashes, dict)
            and bool(content_hashes)
            and len(rows) == len(row_hashes)
            and row_hashes == content_hashes
            and all(row.get("match") is True for row in rows)
            and provenance.get("local_content_matches_upstream_revision") is True
            and Path(provenance.get("local_directory", "")).resolve() == Path(manifest["model"]).resolve()
            and provenance.get("repository") == manifest.get("model_repository")
            and provenance.get("revision") == manifest.get("model_revision")
            and manifest.get("model_provenance_sha256") == sha256_file(directory / "model_provenance.json")
            and all(re.fullmatch(r"[0-9a-f]{64}", digest or "") for digest in row_hashes.values())
        )

    dataset = json.loads((directory / "dataset.json").read_text(encoding="utf-8"))
    items = validate_dataset(dataset, pilot=True)
    by_item = {item["id"]: item for item in items}
    if {item["split"] for item in items} != {"train", "calibration"}:
        raise ValueError("DIRECT/CoT analysis permits only train and calibration development splits")
    selection = json.loads((directory / "selection.json").read_text(encoding="utf-8"))
    selected_groups = selection.get("selected_group_ids") if isinstance(selection, dict) else None
    dataset_groups = {item["group_id"] for item in items}
    if (
        not isinstance(selected_groups, list)
        or selection.get("seed") != manifest.get("seed")
        or not all(isinstance(group, str) for group in selected_groups)
        or selected_groups != sorted(set(selected_groups))
        or set(selected_groups) != dataset_groups
    ):
        raise ValueError("Pilot selection does not reproduce the selected dataset groups")
    collection_seed = manifest.get("seed")
    if type(collection_seed) is not int:
        raise ValueError("Pilot collection seed must be an integer")

    records = json.loads((directory / "records.json").read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("Pilot records must be a list")
    available = sorted({
        row.get("token_budget")
        for row in records
        if row.get("strategy") in ("DIRECT", "COT") and type(row.get("token_budget")) is int
    })
    if budget is None:
        if len(available) != 1:
            raise ValueError("Choose one matched DIRECT/CoT budget with --direct-cot-budget")
        budget = available[0]
    if type(budget) is not int or budget <= 0 or budget not in available:
        raise ValueError("Requested DIRECT/CoT budget is unavailable")
    declared_budgets = manifest.get("token_budgets")
    if (
        not isinstance(declared_budgets, list)
        or any(type(value) is not int or value <= 0 for value in declared_budgets)
        or len(declared_budgets) != len(set(declared_budgets))
        or sorted(declared_budgets) != available
    ):
        raise ValueError("Pilot records disagree with declared token budgets")

    paired = {}
    for row in records:
        if row.get("strategy") not in ("DIRECT", "COT") or row.get("token_budget") != budget:
            continue
        identifier = row.get("id")
        if identifier not in by_item:
            raise ValueError("Pilot record refers to an unknown dataset item")
        item = by_item[identifier]
        if row.get("group_id") != item["group_id"] or row.get("split") != item["split"]:
            raise ValueError("Pilot record split/group differs from the frozen dataset")
        if row.get("seed") != seed_for(collection_seed, identifier, row["strategy"]):
            raise ValueError("Pilot record seed differs from the frozen collection seed")
        expected_family = str(item.get("family", item.get("category", "unspecified")))
        expected_level = str(item.get("level", "unspecified"))
        if row.get("family") != expected_family or row.get("level") != expected_level:
            raise ValueError("Pilot record family/level differs from the frozen dataset")
        if type(row.get("correct")) is not bool or not isinstance(row.get("answer"), str):
            raise ValueError("Pilot attempts require a string answer and boolean correctness")
        if row["correct"] != check_answer(row["answer"], item):
            raise ValueError("Pilot correctness does not reproduce from the frozen answer checker")
        if not _finite_number(row.get("confidence")) or row["confidence"] > 1:
            raise ValueError("Pilot confidence must be finite and in [0, 1]")
        if not _finite_number(row.get("strategy_ms")):
            raise ValueError("Pilot strategy time must be finite and nonnegative")
        answer_format = {
            "answer_type": (
                "expression" if item.get("family") == "g24"
                else "text" if item.get("family") == "order"
                else item["answer_type"]
            ),
            "decimal_separator": item.get("decimal_separator", "."),
        }
        trace = row.get("trace")
        if (
            not isinstance(trace, dict)
            or trace.get("strategy") != row["strategy"]
            or trace.get("prompt_profile") != PROMPT_PROFILE
            or trace.get("answer_format") != answer_format
            or row.get("answer_format") != answer_format
            or trace.get("parse_status") not in ("marker", "fallback", "fail")
            or type(trace.get("wordy")) is not bool
        ):
            raise ValueError("Pilot trace identity or answer-format metadata is inconsistent")
        generated, prompt = _generation_cost(row)
        generations = trace["generations"]
        if len(generations) != 1:
            raise ValueError("Aligned DIRECT and COT must each use exactly one generation call")
        generation = generations[0]
        expected_messages = [{
            "role": "user",
            "content": item["query"] + ALIGNED_DIRECT_COT_SUFFIX_TEXT[row["strategy"]],
        }]
        temperature = generation.get("temperature")
        if (
            generation.get("messages") != expected_messages
            or generation.get("max_tokens") != budget
            or isinstance(temperature, bool)
            or not isinstance(temperature, (int, float))
            or temperature != 0.0
            or generation.get("enable_thinking") is not False
            or generation.get("finish_reason") not in ("stop", "length", "stop_answer")
            or not isinstance(generation.get("output"), str)
            or prompt <= 0
            or generated <= 0
            or generation["tokens"] > generation["max_tokens"]
            or (
                generation.get("finish_reason") == "length"
                and generation["tokens"] != generation["max_tokens"]
            )
        ):
            raise ValueError("Pilot generation settings do not match the aligned fixed-arm protocol")
        parsed_answer, parsed_status, parsed_wordy = parse_answer_details(
            generation["output"], **answer_format,
        )
        if (
            row["answer"] != parsed_answer
            or trace["parse_status"] != parsed_status
            or trace["wordy"] != parsed_wordy
        ):
            raise ValueError("Pilot parsed answer does not reproduce from the recorded raw output")
        if (backend == "smoke") != (trace.get("synthetic") is True):
            raise ValueError("Pilot trace synthetic label is inconsistent with its backend")
        key = (identifier, row["strategy"])
        if key in paired:
            raise ValueError("Duplicate DIRECT/CoT pilot condition")
        paired[key] = row

    expected = {(identifier, strategy) for identifier in by_item for strategy in ("DIRECT", "COT")}
    if set(paired) != expected:
        raise ValueError("Every development item requires one matched DIRECT and COT attempt")
    return {
        "directory": directory,
        "manifest": manifest,
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "dataset": dataset,
        "items": by_item,
        "records": paired,
        "budget": budget,
        "provenance_valid": provenance_valid,
        "review_valid": manifest.get("human_review_status") == "approved",
    }


def _outcome(identifier: str, group_id: str, method: str, path: list[dict], lam: float,
             *, reasons: list[str] | None = None, oracle: bool = False) -> dict:
    generated_costs, prompt_costs = zip(*(_generation_cost(row) for row in path))
    generated = sum(generated_costs)
    prompt = sum(prompt_costs)
    final = path[-1]
    total = generated + prompt
    return {
        "id": identifier,
        "group_id": group_id,
        "method": method,
        "path": [row["strategy"] for row in path],
        "answer": final["answer"],
        "correct": final["correct"],
        "generated_tokens": generated,
        "prompt_tokens": prompt,
        "total_tokens": total,
        "utility": float(final["correct"]) - lam * total / 1000,
        "strategy_ms_sum": sum(row["strategy_ms"] for row in path),
        "escalated": len(path) > 1,
        "trigger_reasons": reasons or [],
        "uses_gold_at_decision_time": oracle,
    }


def evaluate(pilot: dict, lam: float, split: str = "calibration") -> list[dict]:
    """Replay fixed baselines and the preregisterable fail-only cascade."""
    if isinstance(lam, bool) or not isinstance(lam, (int, float)) or not math.isfinite(lam) or lam < 0:
        raise ValueError("Lambda must be finite and nonnegative")
    results = []
    for identifier, item in sorted(pilot["items"].items()):
        if item["split"] != split:
            continue
        direct = pilot["records"][identifier, "DIRECT"]
        cot = pilot["records"][identifier, "COT"]
        reasons = _direct_failure_reasons(direct)
        fixed_direct = _outcome(identifier, item["group_id"], "fixed_direct", [direct], lam)
        fixed_cot = _outcome(identifier, item["group_id"], "fixed_cot", [cot], lam)
        cascade_path = [direct, cot] if reasons else [direct]
        cascade = _outcome(
            identifier, item["group_id"], "direct_cot_format_or_length",
            cascade_path, lam, reasons=reasons,
        )
        always = _outcome(identifier, item["group_id"], "always_direct_cot", [direct, cot], lam)
        oracle = max(
            (
                _outcome(identifier, item["group_id"], "oracle_direct_cot_utility", [direct], lam, oracle=True),
                _outcome(identifier, item["group_id"], "oracle_direct_cot_utility", [direct, cot], lam, oracle=True),
            ),
            key=lambda row: (row["utility"], -row["total_tokens"]),
        )
        results.extend((fixed_direct, fixed_cot, cascade, always, oracle))
    if not results:
        raise ValueError(f"No {split} records are available")
    return results


def _method_summary(results: list[dict]) -> dict:
    summary = {}
    for method in METHODS:
        rows = [row for row in results if row["method"] == method]
        if not rows:
            raise ValueError(f"Missing outcomes for method {method}")
        summary[method] = {
            "n": len(rows),
            "accuracy": float(np.mean([row["correct"] for row in rows])),
            "mean_generated_tokens": float(np.mean([row["generated_tokens"] for row in rows])),
            "mean_prompt_tokens": float(np.mean([row["prompt_tokens"] for row in rows])),
            "mean_total_tokens": float(np.mean([row["total_tokens"] for row in rows])),
            "mean_utility": float(np.mean([row["utility"] for row in rows])),
            "escalation_rate": float(np.mean([row["escalated"] for row in rows])),
            "mean_strategy_ms_sum": float(np.mean([row["strategy_ms_sum"] for row in rows])),
        }
    return summary


def _paired_interval(results: list[dict], method: str, baseline: str, field: str,
                     seed: int = 42, repetitions: int = 2000) -> dict:
    candidate = {row["id"]: row for row in results if row["method"] == method}
    reference = {row["id"]: row for row in results if row["method"] == baseline}
    if not candidate or candidate.keys() != reference.keys():
        raise ValueError("Paired comparison requires identical nonempty query sets")
    groups = defaultdict(list)
    for identifier, row in candidate.items():
        groups[row["group_id"]].append(float(row[field]) - float(reference[identifier][field]))
    keys = sorted(groups)
    sums = np.array([sum(groups[key]) for key in keys])
    counts = np.array([len(groups[key]) for key in keys])
    mean = float(sums.sum() / counts.sum())
    if len(keys) < 2:
        return {"mean_difference": mean, "ci95": None, "groups": len(keys)}
    generator = np.random.default_rng(seed)
    draws = []
    for _ in range(repetitions):
        indices = generator.integers(0, len(keys), size=len(keys))
        draws.append(float(sums[indices].sum() / counts[indices].sum()))
    return {
        "mean_difference": mean,
        "ci95": np.quantile(draws, [0.025, 0.975]).tolist(),
        "groups": len(keys),
    }


def _manipulation_checks(pilot: dict) -> dict:
    result = {}
    for split in ("train", "calibration"):
        result[split] = {}
        for strategy in ("DIRECT", "COT"):
            rows = [
                pilot["records"][identifier, strategy]
                for identifier, item in pilot["items"].items()
                if item["split"] == split
            ]
            if not rows:
                raise ValueError(f"No {split} {strategy} records are available")
            result[split][strategy] = {
                "n": len(rows),
                "visible_rationale_rate": float(np.mean([_visible_rationale(row) for row in rows])),
                "answer_marker_rate": float(np.mean([row["trace"].get("parse_status") == "marker" for row in rows])),
                "length_stop_rate": float(np.mean([
                    any(generation.get("finish_reason") == "length" for generation in row["trace"]["generations"])
                    for row in rows
                ])),
            }
    return result


def _manipulation_gate(checks: dict) -> dict:
    split_results = {
        split: bool(
            rows["DIRECT"]["visible_rationale_rate"] <= DIRECT_MAX_VISIBLE_RATIONALE_RATE
            and rows["COT"]["visible_rationale_rate"] >= COT_MIN_VISIBLE_RATIONALE_RATE
        )
        for split, rows in checks.items()
    }
    return {
        "valid": all(split_results.values()),
        "split_results": split_results,
        "thresholds": {
            "direct_visible_rationale_rate_at_most": DIRECT_MAX_VISIBLE_RATIONALE_RATE,
            "cot_visible_rationale_rate_at_least": COT_MIN_VISIBLE_RATIONALE_RATE,
        },
    }


def summarize(pilot: dict, results: list[dict], lam: float) -> dict:
    methods = _method_summary(results)
    policy = "direct_cot_format_or_length"
    comparisons = {
        baseline: {
            field: _paired_interval(results, policy, baseline, field)
            for field in ("correct", "total_tokens", "utility")
        }
        for baseline in ("fixed_direct", "fixed_cot", "always_direct_cot")
    }
    indexed = {(row["id"], row["method"]): row for row in results}
    identifiers = sorted({row["id"] for row in results})
    available_rescue = sum(
        not indexed[identifier, "fixed_direct"]["correct"]
        and indexed[identifier, "fixed_cot"]["correct"]
        for identifier in identifiers
    )
    available_harm = sum(
        indexed[identifier, "fixed_direct"]["correct"]
        and not indexed[identifier, "fixed_cot"]["correct"]
        for identifier in identifiers
    )
    policy_rescue = sum(
        not indexed[identifier, "fixed_direct"]["correct"]
        and indexed[identifier, policy]["correct"]
        for identifier in identifiers
    )
    policy_harm = sum(
        indexed[identifier, "fixed_direct"]["correct"]
        and not indexed[identifier, policy]["correct"]
        for identifier in identifiers
    )
    cot_comparison = comparisons["fixed_cot"]
    token_ratio = methods[policy]["mean_total_tokens"] / methods["fixed_cot"]["mean_total_tokens"]
    accuracy_ci = cot_comparison["correct"]["ci95"]
    measured = pilot["manifest"].get("backend") == "mlx"
    manipulation_checks = _manipulation_checks(pilot)
    manipulation_gate = _manipulation_gate(manipulation_checks)
    decision_settings_frozen = bool(
        lam == DECISION_LAMBDA and pilot["budget"] == DECISION_TOKEN_BUDGET
    )
    go = bool(
        measured
        and pilot["provenance_valid"]
        and pilot["review_valid"]
        and manipulation_gate["valid"]
        and decision_settings_frozen
        and accuracy_ci is not None
        and accuracy_ci[0] >= -0.02
        and token_ratio <= 0.8
        and cot_comparison["utility"]["mean_difference"] > 0
        and policy_rescue > policy_harm
    )
    return {
        "development_only": True,
        "evaluation_split": "calibration",
        "lambda": lam,
        "utility_cost_scope": "prompt plus generated token counts; not full inference cost",
        "methods": methods,
        "paired_policy_minus_baseline": comparisons,
        "direct_cot_complementarity": {
            "available_direct_wrong_cot_right": available_rescue,
            "available_direct_right_cot_wrong": available_harm,
            "policy_rescue": policy_rescue,
            "policy_harm": policy_harm,
        },
        "manipulation_checks": manipulation_checks,
        "manipulation_gate": manipulation_gate,
        "verified_model_provenance": pilot["provenance_valid"],
        "approved_human_review": pilot["review_valid"],
        "decision_settings": {
            "eligible": decision_settings_frozen,
            "lambda": DECISION_LAMBDA,
            "token_budget_per_call": DECISION_TOKEN_BUDGET,
        },
        "development_decision": {
            "status": (
                "software_only" if not measured
                else "invalid_provenance" if not pilot["provenance_valid"]
                else "pending_review" if not pilot["review_valid"]
                else "invalid_manipulation" if not manipulation_gate["valid"]
                else "exploratory_settings" if not decision_settings_frozen
                else "go" if go else "no_go"
            ),
            "not_a_publication_claim": True,
            "criteria": {
                "accuracy_ci_lower_vs_fixed_cot_at_least": -0.02,
                "total_token_ratio_vs_fixed_cot_at_most": 0.8,
                "mean_utility_difference_vs_fixed_cot_positive": True,
                "policy_rescue_exceeds_policy_harm": True,
                "manipulation_gate_passes": True,
                "verified_model_provenance": True,
                "approved_human_review": True,
                "frozen_lambda_and_budget": True,
            },
            "observed_total_token_ratio_vs_fixed_cot": token_ratio,
        },
        "bootstrap": {"seed": 42, "repetitions": 2000, "unit": "original problem group"},
    }


def render_report(manifest: dict, summary: dict) -> str:
    lines = [
        "# DIRECT to CoT development analysis",
        "",
        f"Evidence: **{manifest['evidence']}**",
        "",
        "This is a development-only replay. It makes no model calls, opens no held-out test data,",
        "and does not modify the frozen run11 cascade. The conditional CoT attempt receives the",
        "original query; it is not a targeted revision of the DIRECT answer.",
        "",
        "The fixed policy escalates only when DIRECT misses the Answer marker/format contract or",
        "reaches a generation length cap. The oracle uses gold outcomes and is not deployable.",
        "",
        "| Method | N | Accuracy | Generated tokens | Prompt tokens | Total token proxy | Utility | Escalation |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for method, metrics in summary["methods"].items():
        lines.append(
            f"| {method} | {metrics['n']} | {metrics['accuracy']:.3f} | "
            f"{metrics['mean_generated_tokens']:.1f} | {metrics['mean_prompt_tokens']:.1f} | "
            f"{metrics['mean_total_tokens']:.1f} | {metrics['mean_utility']:.3f} | "
            f"{metrics['escalation_rate']:.3f} |"
        )
    lines.extend([
        "",
        "## Manipulation checks",
        "",
        "Visible rationale means non-whitespace output before the final Answer marker.",
        "",
        "| Split | Strategy | Visible-rationale rate | Answer-marker rate | Length-stop rate |",
        "| --- | --- | ---: | ---: | ---: |",
    ])
    for split in ("train", "calibration"):
        for strategy in ("DIRECT", "COT"):
            row = summary["manipulation_checks"][split][strategy]
            lines.append(
                f"| {split} | {strategy} | {row['visible_rationale_rate']:.3f} | "
                f"{row['answer_marker_rate']:.3f} | {row['length_stop_rate']:.3f} |"
            )
    lines.extend([
        "",
        "## Fixed policy paired differences",
        "",
        "Differences are fixed policy minus baseline; intervals resample original problem groups.",
        "",
        "| Baseline | Metric | Mean difference | Grouped 95% interval |",
        "| --- | --- | ---: | --- |",
    ])
    for baseline, comparisons in summary["paired_policy_minus_baseline"].items():
        for metric, comparison in comparisons.items():
            lines.append(
                f"| {baseline} | {metric} | {comparison['mean_difference']:.4f} | "
                f"{comparison['ci95']} |"
            )
    comp = summary["direct_cot_complementarity"]
    lines.extend([
        "",
        f"Available DIRECT-wrong/CoT-right pairs: {comp['available_direct_wrong_cot_right']}; "
        f"available DIRECT-right/CoT-wrong pairs: {comp['available_direct_right_cot_wrong']}.",
        f"Realized policy rescues: {comp['policy_rescue']}; "
        f"realized policy harms: {comp['policy_harm']}.",
        f"Manipulation gate: **{'pass' if summary['manipulation_gate']['valid'] else 'fail'}**.",
        f"Decision settings eligible: **{summary['decision_settings']['eligible']}**; "
        f"verified model provenance: **{summary['verified_model_provenance']}**.",
        "",
        f"Development decision: **{summary['development_decision']['status']}**. A GO only permits",
        "a separately preregistered development replication; it does not open main-study test data.",
        "",
        "Costs are prompt plus generated token counts, not FLOPs, energy, billing cost, or measured",
        "online controller latency. Synthetic smoke output validates software only.",
        "",
    ])
    return "\n".join(lines)


def write_analysis(directory: Path, output: Path, lam: float = 0.02,
                   budget: int | None = None) -> None:
    if output.exists():
        raise FileExistsError(output)
    pilot = load_pilot(directory, budget)
    results = evaluate(pilot, lam)
    summary = summarize(pilot, results, lam)
    evidence = "synthetic_smoke_analysis" if pilot["manifest"].get("backend") == "smoke" else "measured_development_analysis"
    manifest = {
        "schema_version": 1,
        "status": "running",
        "development_only": True,
        "publication_ready": False,
        "policy_fitted": False,
        "policy": "DIRECT; escalate to independent COT on marker/wordiness failure or length stop",
        "prompt_profile": PROMPT_PROFILE,
        "token_budget_per_call": pilot["budget"],
        "token_scope": "prompt plus generated tokens summed over invoked replay calls; not full inference cost",
        "lambda": lam,
        "evidence": evidence,
        "source_backend": pilot["manifest"].get("backend"),
        "source_model": pilot["manifest"].get("model"),
        "source_model_revision": pilot["manifest"].get("model_revision"),
        "source_model_revision_verified": pilot["manifest"].get("model_revision_verified"),
        "source_human_review_status": pilot["manifest"].get("human_review_status"),
        "source_run": str(pilot["directory"]),
        "source_manifest_sha256": pilot["manifest_sha256"],
        "source_artifact_sha256": pilot["manifest"]["artifact_sha256"],
        "source_code_sha256": pilot["manifest"].get("source_sha256"),
        "analysis_source_sha256": analysis_source_hashes(),
        "git_sha": git_value("rev-parse", "HEAD"),
        "git_status": git_value("status", "--porcelain"),
        "python": sys.version,
        "started_utc": datetime.now(timezone.utc).isoformat(),
    }
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "manifest.json", manifest)
    try:
        write_json(output / "policy.json", {
            "fit_split": None,
            "evaluation_split": "calibration",
            "signal": "DIRECT parse_status != marker OR wordy == true OR any finish_reason == length",
            "uses_gold_at_runtime": False,
            "downstream": "independent COT attempt from the original query",
            "lambda": lam,
        })
        write_json(output / "results.json", results)
        write_json(output / "summary.json", summary)
        (output / "report.md").write_text(render_report(manifest, summary), encoding="utf-8")
        manifest["artifact_sha256"] = {
            path.name: sha256_file(path)
            for path in sorted(output.iterdir())
            if path.is_file() and path.name != "manifest.json"
        }
        manifest.update(status="complete", finished_utc=datetime.now(timezone.utc).isoformat())
        write_json(output / "manifest.json", manifest)
    except BaseException as error:
        manifest.update(status="failed", error=f"{type(error).__name__}: {error}")
        write_json(output / "manifest.json", manifest)
        raise
