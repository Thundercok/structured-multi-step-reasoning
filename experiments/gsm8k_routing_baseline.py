"""Offline query-only baseline for the existing GSM8K development protocol.

Fits the declared 27-rule menu on train only, durably saves selection, then
evaluates on calibration (development validation). Never invokes a model.
"""
from __future__ import annotations

from collections import Counter
import copy
from dataclasses import asdict, dataclass
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import sys
import time

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


ALLOWED_LEGACY_EVIDENCE = ("synthetic_pilot_smoke", "measured_development_pilot")
ALLOWED_STAGED_EVIDENCE = ("synthetic_staged_pilot_collection", "synthetic_staged_collector_fixture")


def load_fitting_bank(run: Path) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    """Fitting-only bank reader with strict validation-outcome isolation (G4)."""
    manifest_path = run / "manifest.json"
    require(manifest_path.is_file(), f"Missing manifest.json in {run}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Check if this is a staged collection run with separate fitting bank
    fitting_records_path = run / "records_fitting.json"
    if fitting_records_path.is_file():
        expected_sha = manifest.get("artifact_sha256", {}).get("records_fitting.json")
        require(expected_sha is not None, "Manifest lacks checksum for records_fitting.json")
        actual_sha = sha256_file(fitting_records_path)
        require(actual_sha == expected_sha, f"Checksum mismatch for records_fitting.json: {actual_sha} vs {expected_sha}")

        dataset_path = run / "dataset.json"
        require(dataset_path.is_file(), f"Missing dataset.json in {run}")
        expected_ds_sha = manifest.get("artifact_sha256", {}).get("dataset.json")
        if expected_ds_sha:
            require(sha256_file(dataset_path) == expected_ds_sha, "Checksum mismatch for dataset.json")
        dataset = json.loads(dataset_path.read_text(encoding="utf-8"))

        records_fitting = json.loads(fitting_records_path.read_text(encoding="utf-8"))
        # Strict isolation check: every record must belong to train role
        for r in records_fitting:
            require(r.get("split") == "train", f"Validation record leaked into records_fitting.json: {r.get('id')}")

        return dataset, records_fitting, manifest

    # Fallback for legacy pilot runs
    dataset, records, manifest = verify_replay(run, manifest)
    fit_items = [i for i in dataset["items"] if i["split"] == "train"]
    fit_ids = {i["id"] for i in fit_items}
    records_fitting = [r for r in records if r["id"] in fit_ids]
    return dataset, records_fitting, manifest


def write_fitting_seal(run: Path, output: Path) -> Dict[str, Any]:
    """Fit rule menu on train items only, write selection.json, and seal manifest with selection_sha256 (G4, G5, H2)."""
    if output.exists():
        raise FileExistsError(f"Output directory {output} already exists")
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))

    is_staged = manifest.get("mode") == "gsm8k_development_pilot_collection"
    if is_staged:
        require(manifest.get("status") == "complete", f"Staged run not complete: {manifest.get('status')}")
        identity = manifest.get("identity")
        require(isinstance(identity, dict), "Staged run manifest missing identity dictionary")
        require("evidence" in identity, "Staged run identity missing required 'evidence' field")
        evidence = identity["evidence"]
        require(isinstance(evidence, str) and bool(evidence), "Staged evidence must be a non-empty string")

        # H2: Reject non-synthetic staged evidence as deferred until real model adapter exists
        if evidence in ("measured_development_pilot", "measured_staged_pilot_collection") or not evidence.startswith("synthetic"):
            raise ValueError(
                "Measured staged collection is deferred; non-synthetic evidence is not permitted on staged schema "
                "until real model adapter is implemented and reviewed."
            )
        require(evidence in ALLOWED_STAGED_EVIDENCE, f"Unsupported staged collection evidence: {evidence}")
        synthetic = True

        require(identity.get("seed") == 42 and identity.get("prompt_profile") == "english-math-v1", "Unexpected seed/profile")
        require(set(identity.get("strategies", [])) == set(ACTIONS) and len(identity["strategies"]) == 3, "Expected DIRECT/COT/PAL only")
        require(identity.get("max_tokens") == 1024, "Expected single matched cap 1024")

        backend = identity.get("backend", "mock")
        require(backend in ("mock", "smoke"), f"Unsupported staged collection backend: {backend}")

        source_hashes = identity.get("source_hashes")
        require(isinstance(source_hashes, dict) and bool(source_hashes), "Staged identity missing source_hashes dictionary")
        for path_name, h in source_hashes.items():
            require(
                isinstance(h, str) and len(h) == 64 and all(c in "0123456789abcdef" for c in h.lower()),
                f"Invalid sha256 source hash for {path_name}: {h}",
            )
        require("experiments/research_study.py" in source_hashes, "Missing experiments/research_study.py in staged source_hashes")
        source_sha256 = source_hashes
        dataset, fit_records, _ = load_fitting_bank(run)
        items = dataset["items"]
    else:
        require(manifest.get("evidence") in ALLOWED_LEGACY_EVIDENCE, f"Unknown input evidence: {manifest.get('evidence')}")
        evidence = manifest["evidence"]
        synthetic = manifest["evidence"] == "synthetic_pilot_smoke"
        require(manifest.get("backend") == ("smoke" if synthetic else "mlx"), "Backend/evidence mismatch")
        require(manifest.get("seed") == 42 and manifest.get("prompt_profile") == "english-math-v1", "Unexpected seed/profile")
        require(set(manifest.get("strategies", [])) == set(ACTIONS) and len(manifest["strategies"]) == 3, "Expected DIRECT/COT/PAL only")
        require(manifest.get("token_budgets") == [1024], "Expected single matched cap 1024")
        source_sha256 = manifest.get("source_hashes", manifest.get("source_sha256", {}))
        dataset, fit_records, _ = load_fitting_bank(run)
        items = dataset["items"]
        if not synthetic:
            require(manifest.get("model_revision_verified") is True and manifest.get("model_repository") == "mlx-community/Qwen3-8B-4bit"
                    and manifest.get("model_revision") == "545dc4251c05440727734bcd94334791f6ab0192", "Review model provenance for this development comparison")
            require(len(items) == len({i["group_id"] for i in items}) == 96 and Counter(i["split"] for i in items) == {"train": 48, "calibration": 48}, "Measured comparison requires its declared 48/48 frame")
            require(all(i.get("category") == "gsm8k" and i.get("source_provenance", {}).get("original_split") == "train"
                        and i["source_provenance"].get("revision") == "3101c7d5072418e28b9008a6636bde82a006892c" for i in items), "Expected pinned GSM8K source-train provenance")

    frame(items)
    selection = fit_selection(items, fit_records)
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "selection.json", selection)
    selection_file_sha = sha256_file(output / "selection.json")

    state = {
        "kind": "query_only_gsm8k_development_analysis",
        "status": "selection_saved",
        "new_model_calls": 0,
        "evidence": "synthetic_routing_software_check" if synthetic else "measured_development_saved_output_analysis",
        "input_run": str(run.resolve()),
        "collection_source_sha256": source_sha256,
        "input_manifest_sha256": sha256_file(run / "manifest.json"),
        "input_artifact_sha256": manifest["artifact_sha256"],
        "analysis_source_sha256": sha256_file(Path(__file__)),
        "protocol_sha256": sha256_file(PROTOCOL),
        "atomic_writer_sha256": sha256_file(ROOT / "experiments/order_pilot_checkpoint.py"),
        "analysis_python": sys.version,
        "analysis_numpy": np.__version__,
        "cost_scope": "synthetic token units" if synthetic else "generated tokens summed over selected calls; prompt tokens separate; full inference costs excluded",
        "rule_version": RULE_VERSION,
        "selection_sha256": selection_file_sha,
        "publication_ready": False,
        "human_review_status": "pending",
        "main_h1_evaluated": False,
    }
    atomic_json(output / "exposure_ledger.json", [{
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "action": "fitting_sealed",
        "accessor": "gsm8k_routing_baseline.write_fitting_seal",
        "files_accessed": ["records_fitting.json", "dataset.json"] if is_staged else ["records.json", "dataset.json"],
    }])
    atomic_json(output / "manifest.json", state)
    return state


def write_validation_evaluation(selection_dir: Path, output: Path) -> Dict[str, Any]:
    """Evaluate sealed selection on validation items without re-fitting candidate rules (D4, D5, G3, H3)."""
    if output.exists():
        raise FileExistsError(f"Output directory {output} already exists")
    manifest_path = selection_dir / "manifest.json"
    require(manifest_path.is_file(), f"Missing manifest.json in {selection_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(manifest.get("status") in ("selection_saved", "selection_sealed", "complete"), f"Invalid manifest status for validation: {manifest.get('status')}")
    require("selection_sha256" in manifest, "Manifest missing selection_sha256 seal")

    selection_path = selection_dir / "selection.json"
    require(selection_path.is_file(), f"Missing selection.json in {selection_dir}")
    require(sha256_file(selection_path) == manifest["selection_sha256"], "Selection file tampered or differs from manifest seal")

    # Source code and protocol binding verification (G3)
    require(sha256_file(Path(__file__)) == manifest.get("analysis_source_sha256"), "Analysis source altered since sealing")
    require(sha256_file(PROTOCOL) == manifest.get("protocol_sha256"), "Protocol document altered since sealing")
    require(sha256_file(ROOT / "experiments/order_pilot_checkpoint.py") == manifest.get("atomic_writer_sha256"), "Atomic writer source altered since sealing")

    selection = json.loads(selection_path.read_text(encoding="utf-8"))

    # Load input run and verify strict bank binding (G3)
    run = Path(manifest["input_run"])
    require(run.is_dir(), f"Input run directory {run} not found")

    actual_manifest_sha = sha256_file(run / "manifest.json")
    require(
        actual_manifest_sha == manifest.get("input_manifest_sha256"),
        f"Input run manifest hash {actual_manifest_sha} differs from sealed hash {manifest.get('input_manifest_sha256')}"
    )

    for artifact_name, expected_sha in manifest.get("input_artifact_sha256", {}).items():
        art_path = run / artifact_name
        require(art_path.is_file(), f"Input artifact {artifact_name} missing in {run}")
        actual_art_sha = sha256_file(art_path)
        require(
            actual_art_sha == expected_sha,
            f"Input artifact {artifact_name} checksum {actual_art_sha} differs from sealed checksum {expected_sha}"
        )

    # Load dataset and validation records
    input_manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    if (run / "records_validation.json").is_file():
        dataset = json.loads((run / "dataset.json").read_text(encoding="utf-8"))
        val_records = json.loads((run / "records_validation.json").read_text(encoding="utf-8"))
        for r in val_records:
            require(r.get("split") == "calibration", "Non-calibration record in validation bank")
        items = dataset["items"]
        accessed_files = ["records_validation.json", "dataset.json", "selection.json"]
    else:
        dataset, all_records, _ = verify_replay(run, input_manifest)
        items = dataset["items"]
        val_records = [r for r in all_records if r.get("split") == "calibration"]
        accessed_files = ["records.json", "dataset.json", "selection.json"]

    frame(items)
    val_items = [i for i in items if i["split"] == "calibration"]
    val_ids = {i["id"] for i in val_items}
    summary, rows = evaluate_selection(selection, val_items, [r for r in val_records if r["id"] in val_ids])

    # H3: Complete collection cost across both fitting and validation roles
    if (run / "records.json").is_file():
        full_collection_records = json.loads((run / "records.json").read_text(encoding="utf-8"))
    else:
        full_collection_records = all_records

    total_gen_tokens = sum(r["tokens"] for r in full_collection_records)
    total_prompt_tokens = sum(r["trace"]["generations"][0]["prompt_tokens"] for r in full_collection_records)
    total_calls = len(full_collection_records)

    budget_charged = total_gen_tokens
    if (run / "summary.json").is_file():
        col_summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
        budget_charged = col_summary.get("budget_charged_tokens", total_gen_tokens)

    val_gen_tokens = sum(r["tokens"] for r in val_records)
    val_prompt_tokens = sum(r["trace"]["generations"][0]["prompt_tokens"] for r in val_records)

    fit_records = [r for r in full_collection_records if r.get("split") == "train"]
    fit_gen_tokens = sum(r["tokens"] for r in fit_records)
    fit_prompt_tokens = sum(r["trace"]["generations"][0]["prompt_tokens"] for r in fit_records)

    output.mkdir(parents=True, exist_ok=False)
    summary["cost_scope"] = manifest["cost_scope"]
    summary["full_collection"] = {
        "generation_calls": total_calls,
        "generated_tokens": total_gen_tokens,
        "prompt_tokens": total_prompt_tokens,
        "budget_charged_tokens": budget_charged,
    }
    summary["validation_only_collection"] = {
        "generation_calls": len(val_records),
        "generated_tokens": val_gen_tokens,
        "prompt_tokens": val_prompt_tokens,
    }
    summary["fitting_only_collection"] = {
        "generation_calls": len(fit_records),
        "generated_tokens": fit_gen_tokens,
        "prompt_tokens": fit_prompt_tokens,
    }

    atomic_json(output / "summary.json", summary)
    atomic_json(output / "results.json", rows)
    atomic_text(output / "report.md", render_report(summary, manifest["evidence"]))

    # Copy verified selection into output
    atomic_json(output / "selection.json", selection)
    atomic_json(output / "exposure_ledger.json", [{
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "action": "validation_evaluated",
        "accessor": "gsm8k_routing_baseline.write_validation_evaluation",
        "files_accessed": accessed_files,
    }])

    state = copy.deepcopy(manifest)
    state.update({
        "status": "complete",
        "validation_evaluated_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "artifact_sha256": {
            name: sha256_file(output / name)
            for name in ("selection.json", "summary.json", "results.json", "report.md", "exposure_ledger.json")
        },
    })
    atomic_json(output / "manifest.json", state)
    return state


def write_analysis(run, output):
    state = write_fitting_seal(run, output)
    try:
        manifest = json.loads((run / "manifest.json").read_text())
        dataset, records, _ = verify_replay(run, manifest)
        items = dataset["items"]
        selection = json.loads((output / "selection.json").read_text())
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
