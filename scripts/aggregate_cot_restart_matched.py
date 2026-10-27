"""Audit two matched development draws and average within question before bootstrap.

Reads saved records/replays only. No tokenizer, model, MLX, policy fit or new
calls. Uses the second plan's prospectively frozen group-bootstrap settings.
"""

from __future__ import annotations

import argparse
from collections import Counter
from importlib import metadata
import json
from pathlib import Path
import random

from experiments.cot_restart_matched import ARMS, read_plan
from experiments.cot_restart_pilot import ROOT, file_sha256
from scripts.analyze_cot_restart_matched import CONTRASTS, audit_records, paired_summary
from scripts.prepare_cot_restart_replication import validate_replication_plan

POINTS = ("M_minus8", "M", "M_plus8", "D_w0", "D_w1")
INTERVAL_POINTS = ("M", "D_w0", "D_w1")
METRICS = ("correct", "completion_tokens", "path_token_cost")
ANALYSIS_SOURCES = (
    "scripts/analyze_cot_restart_matched.py", "experiments/cot_restart_replay.py",
    "reasoning/reasoning_strategies.py", "research_scoring.py", "scripts/gen_tasks.py",
)


def checked_files(directory: Path, hashes: dict, required: set[str]) -> dict:
    if not required <= hashes.keys():
        raise ValueError("input lacks required artifact hashes")
    checked = {}
    for name, digest in hashes.items():
        if Path(name).name != name or name in (".", ".."):
            raise ValueError("artifact path must stay within its input directory")
        actual = file_sha256(directory / name)
        if actual != digest:
            raise ValueError(f"input artifact hash mismatch: {name}")
        checked[str((directory / name).resolve())] = actual
    return checked


def index_rows(rows: list[dict], groups: dict) -> dict:
    expected = {(point, identifier, arm) for point in POINTS for identifier in groups for arm in ARMS}
    indexed = {}
    for row in rows:
        key = (row["point"], row["question_id"], row["arm"])
        if key in indexed:
            raise ValueError("duplicate replay cell")
        if type(row["correct"]) is not bool:
            raise ValueError("per-draw correctness must be binary")
        for metric in METRICS[1:]:
            value = row[metric]
            if type(value) is not int or value < 0:
                raise ValueError("replay costs must be nonnegative integer token counts")
        indexed[key] = row
    if set(indexed) != expected:
        raise ValueError("each draw requires all paired questions/arms/cap points")
    return indexed


def load_bundle(plan_directory: Path, run_directory: Path, analysis_directory: Path) -> dict:
    plan_directory, run_directory, analysis_directory = (
        Path(p).resolve() for p in (plan_directory, run_directory, analysis_directory))
    plan = read_plan(plan_directory)
    manifest, records = audit_records(run_directory, plan)
    if (manifest["failed_attempts"] or manifest["total_attempted_calls"] != 36
            or manifest["limits"] != plan["limits"] or manifest["source_sha256"] != plan["source_sha256"]):
        raise ValueError("aggregate requires a complete compatible 36-call draw without unknown cost")
    audit = json.loads((analysis_directory / "audit.json").read_text())
    hashes = checked_files(analysis_directory, audit["outputs_sha256"], {"summary.json", "replays.json", "report.md"})
    if (audit["plan_sha256"] != plan["plan_sha256"]
            or audit["journal_head"] != manifest["journal_head"]
            or audit["run_artifact_hashes"] != manifest["artifact_hashes"]):
        raise ValueError("analysis provenance differs from its raw run/plan")
    if audit["source_sha256"] != {name: file_sha256(ROOT / name) for name in ANALYSIS_SOURCES}:
        raise ValueError("analysis sources changed since the saved replay")
    renderer_source = Path(metadata.distribution("mlx-lm").locate_file("mlx_lm/tokenizer_utils.py"))
    if audit["tokenizer_renderer_source_sha256"] != file_sha256(renderer_source):
        raise ValueError("token renderer changed since the saved replay")
    items = json.loads((Path(plan["historical_dir"]) / "dataset.json").read_text())["items"]
    groups = {item["id"]: item["group_id"] for item in items}
    rows = json.loads((analysis_directory / "replays.json").read_text())
    indexed = index_rows(rows, groups)
    raw = {(r["question_id"], r["arm"]): r for r in records}
    for (point, identifier, arm), row in indexed.items():
        original = raw[identifier, arm]
        cap = (original["M_cap"] + {"M_minus8": -8, "M": 0, "M_plus8": 8}[point]
               if point.startswith("M") else original["D_caps"][point[-1]])
        retained = original["completion_token_ids"][:cap]
        finished = any(token in original["eos_token_ids"] for token in retained)
        w = 0 if point == "D_w0" else 1
        expected_cost = (original["base_completion_tokens"] + w * original["base_prompt_tokens"]
                         + w * original["prompt_tokens"] + len(retained))
        if (row["replay_cap"] != cap or row["completion_tokens"] != len(retained)
                or row["finish_reason"] != ("stop" if finished else "length")
                or row["finished"] != finished or row["includes_eos"] != finished
                or row["path_token_cost"] != expected_cost):
            raise ValueError("saved replay caps/counts/finish/cost disagree with raw token IDs")
        if point.startswith("D") and expected_cost > plan["T_star"]:
            raise ValueError("deployment replay exceeds its fixed allowance")
    summary = json.loads((analysis_directory / "summary.json").read_text())
    recomputed = {point: paired_summary([r for r in rows if r["point"] == point], intervals=point in INTERVAL_POINTS)
                  for point in POINTS}
    if summary["points"] != recomputed:
        raise ValueError("saved per-draw summary differs from its replay rows")
    for directory, names in ((plan_directory, ("plan.json",)),
                             (run_directory, ("manifest.json", "records.json", "calls.jsonl")),
                             (analysis_directory, ("audit.json",))):
        hashes.update({str(directory / name): file_sha256(directory / name) for name in names})
    return {"plan": plan, "manifest": manifest, "analysis_audit": audit, "rows": rows,
            "groups": groups, "indexed": indexed, "input_sha256": hashes,
            "directories": [str(p) for p in (plan_directory, run_directory, analysis_directory)]}


def percentile(values: list[float], probability: float) -> float:
    if not values or not 0 <= probability <= 1:
        raise ValueError("invalid percentile input")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    left = int(position)
    right = min(left + 1, len(ordered) - 1)
    return ordered[left] + (position - left) * (ordered[right] - ordered[left])


def compute_statistics(draws: list[list[dict]], groups: dict, *, samples=2000, seed=20261013) -> tuple[dict, list, dict]:
    if len(draws) < 2 or not groups or type(samples) is not int or samples < 1:
        raise ValueError("require multiple complete draws and positive bootstrap repetitions")
    indexed = [index_rows(rows, groups) for rows in draws]
    identifiers, group_names = sorted(groups), sorted(set(groups.values()))
    means, mean_index = [], {}
    for point in POINTS:
        for identifier in identifiers:
            for arm in ARMS:
                row = {"point": point, "question_id": identifier, "group_id": groups[identifier], "arm": arm,
                       "observed_draws": len(draws)}
                row.update({metric: sum(values[point, identifier, arm][metric] for values in indexed) / len(indexed)
                            for metric in METRICS})
                means.append(row)
                mean_index[point, identifier, arm] = row
    # The same group samples apply to every arm/contrast/metric. All question
    # members of a sampled group survive; group-size variation changes n.
    rng = random.Random(seed)
    selections = [Counter(rng.choice(group_names) for _ in group_names) for _ in range(samples)]
    group_sizes = Counter(groups.values())
    distributions, points = {}, {}
    for point in POINTS:
        arms = {arm: {metric: sum(mean_index[point, i, arm][metric] for i in identifiers) / len(identifiers)
                      for metric in METRICS} for arm in ARMS}
        contrasts = []
        for X, Y in CONTRASTS:
            contrasts_row = {"X": X, "Y": Y, "n_questions": len(identifiers)}
            key = f"{point}:{X}-{Y}"
            if point in INTERVAL_POINTS:
                distributions[key] = {}
            for metric in METRICS:
                differences = {i: mean_index[point, i, X][metric] - mean_index[point, i, Y][metric]
                               for i in identifiers}
                delta = sum(differences.values()) / len(identifiers)
                ci = None
                if point in INTERVAL_POINTS and len(group_names) > 1:
                    sums = {g: sum(differences[i] for i in identifiers if groups[i] == g) for g in group_names}
                    values = [sum(count * sums[g] for g, count in selection.items())
                              / sum(count * group_sizes[g] for g, count in selection.items()) for selection in selections]
                    ci = [percentile(values, .025), percentile(values, .975)]
                    distributions[key][metric] = values
                contrasts_row[metric] = {"delta": delta, "paired_group_percentile_95_ci": ci}
            contrasts.append(contrasts_row)
        points[point] = {"arms": arms, "contrasts": contrasts}
    sensitivity, unstable = [], set()
    for draw_index, values in enumerate(indexed):
        for identifier in identifiers:
            arm_rows = {arm: {str(offset): {field: values[point, identifier, arm].get(field)
                                         for field in ("correct", "finish_reason", "parse_status", "replay_cap")}
                              for offset, point in ((-8, "M_minus8"), (0, "M"), (8, "M_plus8"))} for arm in ARMS}
            changed = any(len({r["correct"] for r in caps.values()}) > 1 for caps in arm_rows.values())
            if changed:
                unstable.add(identifier)
            sensitivity.append({"draw_index": draw_index, "question_id": identifier, "arms": arm_rows,
                                "outcome_changed": changed,
                                "paired_differences": {f"{X}-{Y}": {str(s): int(arm_rows[X][str(s)]["correct"])
                                                                     - int(arm_rows[Y][str(s)]["correct"])
                                                                     for s in (-8, 0, 8)} for X, Y in CONTRASTS}})
    variability = {arm: sum(len({values["M", i, arm]["correct"] for values in indexed}) > 1 for i in identifiers)
                   for arm in ARMS}
    summary = {"n_questions": len(identifiers), "n_original_groups": len(group_names), "observed_draws": len(draws),
               "points": points, "unique_boundary_sensitive_questions": len(unstable),
               "M_questions_with_correctness_disagreement_between_draws": variability,
               "bootstrap": {"samples": samples, "seed": seed, "unit": "original problem group",
                             "seed_handling": "average within question before resampling groups",
                             "interval": "linear-interpolated paired percentile 95%; descriptive and unadjusted",
                             "conditional_on": "observed draws and fixed historical bases",
                             "one_group_interval": None}, "sensitivity": sensitivity}
    return summary, means, distributions


def aggregate(inputs: list[tuple[Path, Path, Path]], output: Path) -> dict:
    if len(inputs) != 2:
        raise ValueError("this frozen addendum requires exactly draw 0 and draw 1")
    output = Path(output).resolve()
    if output.exists() or any(output.is_relative_to(Path(p).resolve()) for paths in inputs for p in paths):
        raise ValueError("aggregate needs a new directory outside every input")
    bundles = sorted([load_bundle(*paths) for paths in inputs], key=lambda b: b["plan"].get("draw_index", 0))
    first, second = bundles
    if [b["plan"].get("draw_index", 0) for b in bundles] != [0, 1]:
        raise ValueError("draw identity must be 0 and 1, without duplicate/replayed draws")
    validate_replication_plan(first["plan"], second["plan"])
    if (first["groups"] != second["groups"]
            or first["analysis_audit"]["source_sha256"] != second["analysis_audit"]["source_sha256"]):
        raise ValueError("draw groups/analysis sources are incompatible")
    spec = second["plan"]["replication"]["analysis_spec"]
    if (spec["bootstrap_samples"] != 2000 or spec["bootstrap_seed"] != 20261013
            or spec["points"] != list(INTERVAL_POINTS) or spec["contrasts"] != [list(pair) for pair in CONTRASTS]
            or spec["decision_states_enabled"]):
        raise ValueError("unsupported prospective analysis specification")
    summary, means, distributions = compute_statistics([b["rows"] for b in bundles], first["groups"],
                                                       samples=spec["bootstrap_samples"], seed=spec["bootstrap_seed"])
    summary.update({"evidence": "exposed_development_two_draw_conditional_aggregate", "confirmatory": False,
                    "stage_0_changed": False, "decision_states_enabled": False,
                    "q_star": first["plan"]["q_star"], "W": first["plan"]["W"], "T_star": first["plan"]["T_star"],
                    "base_cost_scope": first["plan"]["base_cost_scope"],
                    "collection": {"calls": sum(b["manifest"]["executed_model_calls"] for b in bundles),
                                   "completion_tokens_including_eos": sum(b["manifest"]["total_completion_tokens"] for b in bundles),
                                   "new_prompt_plus_completion_tokens": sum(b["manifest"]["total_incurred_tokens"] for b in bundles)},
                    "per_draw": [{"draw_index": b["plan"].get("draw_index", 0),
                                  "collection": {k: b["manifest"][k] for k in ("executed_model_calls", "total_completion_tokens", "total_incurred_tokens", "active_seconds")},
                                  "points": {point: paired_summary([r for r in b["rows"] if r["point"] == point], intervals=point in INTERVAL_POINTS)
                                             for point in POINTS}} for b in bundles]})
    input_hashes = {path: digest for b in bundles for path, digest in b["input_sha256"].items()}
    for path, digest in input_hashes.items():
        if file_sha256(Path(path)) != digest:
            raise ValueError("input changed while aggregate was computed")
    output.mkdir(parents=True, exist_ok=False)
    for name, content in (("summary.json", summary), ("question_means.json", means), ("bootstrap_distribution.json", distributions)):
        (output / name).write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n")
    lines = ["# Two-draw matched development aggregate", "",
             "72 completed real calls; 12 exposed questions/12 original groups, two draws per arm.",
             "No new inference. Average draws within question before paired group bootstrap.", "",
             "| Point | A mean accuracy | F mean accuracy | CONT mean accuracy |",
             "| --- | ---: | ---: | ---: |"]
    for point, values in summary["points"].items():
        lines.append(f"| {point} | " + " | ".join(f"{100*values['arms'][arm]['correct']:.1f}%" for arm in ARMS) + " |")
    lines.extend(["", "| Point | Contrast | Delta accuracy (pp) | Paired group percentile 95% CI (pp) | Delta path tokens |",
                  "| --- | --- | ---: | --- | ---: |"])
    for point, values in summary["points"].items():
        for c in values["contrasts"]:
            ci = c["correct"]["paired_group_percentile_95_ci"]
            interval = f"[{100*ci[0]:+.1f}, {100*ci[1]:+.1f}]" if ci else "descriptive sensitivity only"
            lines.append(f"| {point} | {c['X']}-{c['Y']} | {100*c['correct']['delta']:+.1f} | {interval} | {c['path_token_cost']['delta']:+.1f} |")
    lines.extend(["", "| Point | Arm | Mean new completion tokens | Mean conditional path tokens |",
                  "| --- | --- | ---: | ---: |"])
    for point in INTERVAL_POINTS:
        for arm, values in summary["points"][point]["arms"].items():
            lines.append(f"| {point} | {arm} | {values['completion_tokens']:.1f} | {values['path_token_cost']:.1f} |")
    lines.extend(["", f"Unique M +/-8 outcome-sensitive questions across both draws: {summary['unique_boundary_sensitive_questions']}/12.",
                  f"M correctness differs between draws on {summary['M_questions_with_correctness_disagreement_between_draws']} questions per arm.",
                  "Per-draw paired tables/nominal Tango intervals remain in summary.json; fractional means do not receive binary Tango intervals.",
                  "Intervals are descriptive, unadjusted, conditional on these observed draws/fixed bases and resample only original groups.",
                  "They do not estimate uncertainty over a population of new generation seeds or fitted policies.",
                  "The 12 questions, two draws and replayed caps are not pooled as independent observations.",
                  "D retains historical base counts with an unverified EOS convention; costs are token counts, not FLOPs/billing/full inference costs.",
                  "Collection time at the larger caps is not online latency at replayed M/D caps.",
                  "No lambda/practical margin, formal GO/NO-GO, mechanistic, held-out-quality or Stage 0 conclusion is enabled.",
                  "Human/publication review remains pending."])
    (output / "report.md").write_text("\n".join(lines) + "\n")
    manifest = {"status": "complete", "evidence": summary["evidence"], "confirmatory": False,
                "publication_review_required": True, "stage_0_changed": False, "new_model_calls": 0,
                "inputs": [b["directories"] for b in bundles], "input_sha256": input_hashes,
                "analysis_spec": spec,
                "source_sha256": {name: file_sha256(ROOT / name) for name in (
                    "scripts/aggregate_cot_restart_matched.py", *ANALYSIS_SOURCES,
                    "scripts/prepare_cot_restart_replication.py", "docs/cot_restart_matched_aggregate_20261013.md")},
                "output_sha256": {p.name: file_sha256(p) for p in output.iterdir()}}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", nargs=3, type=Path, metavar=("PLAN", "RUN", "ANALYSIS"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = aggregate(args.input, args.output)
    print(json.dumps({"questions": result["n_questions"], "groups": result["n_original_groups"],
                      "draws": result["observed_draws"], "collection": result["collection"], "new_model_calls": 0}, indent=2))


if __name__ == "__main__":
    main()
