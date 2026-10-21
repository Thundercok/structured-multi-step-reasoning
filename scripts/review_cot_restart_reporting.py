"""Retrospective CPU reporting checks; never alter collection or old analyses."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.cot_restart_pilot import ROOT, file_sha256
from scripts.aggregate_cot_restart_matched import ARMS, INTERVAL_POINTS, POINTS, checked_files, load_bundle
from scripts.analyze_cot_restart_matched import CONTRASTS, paired_summary
from scripts.cot_restart_rescue_diagnostics import clopper_pearson
from scripts.prepare_cot_restart_replication import validate_replication_plan


def strata_tables(rows: list[dict], base_correct: dict[str, bool]) -> list[dict]:
    tables = []
    for point in INTERVAL_POINTS:
        by_arm = {arm: {r["question_id"]: r for r in rows if r["point"] == point and r["arm"] == arm} for arm in ARMS}
        if any(set(values) != set(base_correct) for values in by_arm.values()):
            raise ValueError("strata require all fixed base questions in every arm")
        if any(len(values) != sum(r["point"] == point and r["arm"] == arm for r in rows) for arm, values in by_arm.items()):
            raise ValueError("duplicate rows in strata")
        for label, state in (("base_correct", True), ("base_wrong", False)):
            ids = sorted(i for i, value in base_correct.items() if value == state)
            if not ids:
                continue
            correct = {arm: {i: by_arm[arm][i]["correct"] for i in ids} for arm in ARMS}
            correct["O"] = {i: base_correct[i] for i in ids}
            contrasts = []
            for X, Y in (*CONTRASTS, *((arm, "O") for arm in ARMS)):
                wins = [i for i in ids if correct[X][i] and not correct[Y][i]]
                losses = [i for i in ids if correct[Y][i] and not correct[X][i]]
                contrasts.append({"X": X, "Y": Y, "n": len(ids), "b": len(wins), "c": len(losses),
                                  "delta": (len(wins)-len(losses))/len(ids),
                                  "contribution_to_all_question_delta": (len(wins)-len(losses))/len(base_correct),
                                  "wins": wins, "losses": losses})
            tables.append({"point": point, "stratum": label, "n": len(ids), "question_ids": ids,
                           "correct": {arm: sum(values.values()) for arm, values in correct.items()}, "contrasts": contrasts})
    return tables


def sign_flip(group_differences: list[float], n_questions: int) -> dict:
    """Exhaustive two-sided group sign-flips on half-integer two-draw sums.

    Exact enumeration assumes groupwise sign exchangeability under the null;
    it is not automatically an exact test of a weak zero-mean null.
    """
    if not group_differences or n_questions < 1:
        raise ValueError("sign-flip requires groups and questions")
    units = [round(2*v) for v in group_differences]
    if any(abs(2*v-u) > 1e-12 for v, u in zip(group_differences, units)):
        raise ValueError("two-draw binary differences must be half-integer")
    observed = sum(units)
    total = 2**len(units)
    extreme = sum(abs(sum(v if mask & (1 << i) else -v for i, v in enumerate(units))) >= abs(observed)
                  for mask in range(total))
    return {"n_questions": n_questions, "n_groups": len(units), "assignments": total,
            "observed_delta": observed/(2*n_questions), "two_sided_p": extreme/total,
            "extreme_assignments": extreme,
            "null_assumption": "groupwise sign-exchangeability of paired differences; not only zero mean",
            "scope": "retrospective descriptive cross-check, unadjusted"}


def choice_ledger(plan: dict) -> dict:
    return {"plan_sha256": plan["plan_sha256"], "plan_artifact": "audit/cot_restart_replication_plan_20261013/plan.json",
            "chronology": [
                "Within-question averaging, group sampling, 2000 replicates, seed 20261013 and descriptive percentile intervals were in the hashed replication plan before draw 1 (the second draw) collection.",
                "The second-draw report was read before aggregator code was written, tested and hashed.",
                "The 27 NumPy distribution/CI checks were performed after aggregation as implementation checks, not pre-specification.",
                "This ledger, first-draw regression, strata/O comparisons, CP null rates and sign-flip checks are retrospective additions requested after both draws were inspected."],
            "choices": [
                {"choice": "average within question then question-weighted mean", "status": "pre_specified",
                 "evidence": "replication.analysis_spec.aggregation"},
                {"choice": "original group bootstrap; retain members and draws; 2000 samples; seed 20261013", "status": "pre_specified",
                 "evidence": "replication.analysis_spec.bootstrap_unit/bootstrap_samples/bootstrap_seed"},
                {"choice": "conditional descriptive percentile 95% intervals; no binary Tango on fractional means", "status": "pre_specified",
                 "evidence": "replication.analysis_scope; analysis_spec.interval; frozen replication protocol"},
                {"choice": "linear quantile interpolation; Python RNG; sorted groups; common samples across all metrics", "status": "post_report_implementation",
                 "evidence": "not explicitly fixed by the plan; implemented in scripts/aggregate_cot_restart_matched.py"},
                {"choice": "M/D points and CONT-A, F-A, F-CONT contrasts", "status": "pre_specified",
                 "evidence": "replication.analysis_spec.points/contrasts"},
                {"choice": "completion and conditional path costs as separate aggregate metrics, each with bootstrap CI", "status": "partly_pre_specified",
                 "evidence": "token scopes/counts existed in the frozen collector/plan; the exact aggregate metric list and cost CIs were not explicitly fixed"},
                {"choice": "27 saved distributions and independent NumPy checks", "status": "post_report_validation",
                 "evidence": "3 points x 3 contrasts x 3 metrics; points/contrasts were fixed, metric CI/reporting and validation were implementation choices"},
                {"choice": "M +/-8 paired sensitivity without independent pooling", "status": "pre_specified",
                 "evidence": "M_offsets and replication.analysis_spec.M_offsets"},
                {"choice": "O comparisons, base-outcome strata, null CP and sign-flip checks", "status": "retrospective_addition",
                 "evidence": "requested after inspection; not confirmatory primary comparisons"},
                {"choice": "no practical margin, lambda or GO/NO-GO decision", "status": "pre_specified_absence",
                 "evidence": "decision_states_enabled=false and frozen pilot protocol"}],
            "methods_sentence": f"Aggregation rules were pre-specified in audit/cot_restart_replication_plan_20261013/plan.json (SHA-256 {plan['plan_sha256']}); aggregator code was written after the second-draw report was read. Implementation details and added cost intervals were selected after inspection. An independent NumPy re-implementation checked computation, not pre-specification. All results are exploratory.",
            "confirmatory_requirement": "Freeze and record the actual commit and SHA-256 of dataset, aggregator, decision rule, practical margin/cost scope before the first confirmatory call; an unrelated repository HEAD does not freeze uncommitted analysis code."}


def review(output: Path) -> dict:
    output = Path(output).resolve()
    if output.exists() or output.is_relative_to(ROOT / "audit/cot_restart_matched_aggregate_20261013"):
        raise ValueError("reporting review requires a new isolated directory")
    paths = [(ROOT/"audit/cot_restart_matched_plan_20261013", ROOT/"audit/cot_restart_matched_real_20261013", ROOT/"audit/cot_restart_matched_analysis_20261013"),
             (ROOT/"audit/cot_restart_replication_plan_20261013", ROOT/"audit/cot_restart_replication_real_20261013", ROOT/"audit/cot_restart_replication_analysis_20261013")]
    if any(output.is_relative_to(p) for triple in paths for p in triple):
        raise ValueError("review must stay outside existing inputs")
    # Standalone first-draw regression runs before loading the second draw.
    first = load_bundle(*paths[0])
    saved = json.loads((paths[0][2]/"summary.json").read_text())
    reproduced = {point: paired_summary([r for r in first["rows"] if r["point"] == point], intervals=point in INTERVAL_POINTS)
                  for point in POINTS}
    if reproduced != saved["points"]:
        raise ValueError("standalone first-draw regression failed")
    regression = {"status": "exact_match", "scope": "all five first-draw per-point accuracy/token/b/c/nominal-Tango tables",
                  "saved_summary_sha256": file_sha256(paths[0][2]/"summary.json"),
                  "second_draw_needed_for_regression": False,
                  "implementation_note": "Uses the frozen single-draw scoring summary helper. This is regression validation, not proof of analysis pre-specification.",
                  "reproduced_points": reproduced}
    second = load_bundle(*paths[1])
    validate_replication_plan(first["plan"], second["plan"])
    aggregate_dir = ROOT/"audit/cot_restart_matched_aggregate_20261013"
    manifest = json.loads((aggregate_dir/"manifest.json").read_text())
    aggregate_hashes = checked_files(aggregate_dir, manifest["output_sha256"], {"summary.json", "question_means.json", "bootstrap_distribution.json", "report.md"})
    for mapping in (manifest["input_sha256"], manifest["source_sha256"]):
        for name, digest in mapping.items():
            if file_sha256(Path(name)) != digest:
                raise ValueError("aggregate input/source hash mismatch")
    second_saved = json.loads((paths[1][2]/"summary.json").read_text())
    if saved["base_rescoring"] != second_saved["base_rescoring"] or any(r["historical_correct"] != r["retrospective_correct"] for r in saved["base_rescoring"]):
        raise ValueError("review base-stratum definitions first")
    base = {r["question_id"]: r["retrospective_correct"] for r in saved["base_rescoring"]}
    bundles = [first, second]
    strata = [{"draw_index": index, "tables": strata_tables(bundle["rows"], base)} for index, bundle in enumerate(bundles)]
    nulls = []
    for arm in ARMS:
        masks = [{i: bundle["indexed"]["M", i, arm]["correct"] for i in base} for bundle in bundles]
        up = [i for i in base if not masks[0][i] and masks[1][i]]
        down = [i for i in base if masks[0][i] and not masks[1][i]]
        count = len(up)+len(down)
        nulls.append({"arm": arm, "changed": count, "n": len(base), "d_null": count/len(base),
                      "cp95": clopper_pearson(count, len(base)), "wrong_to_correct": up, "correct_to_wrong": down,
                      "scope": "question-level within-arm draw disagreement at M; binomial CP, unadjusted"})
    aggregate_summary = json.loads((aggregate_dir/"summary.json").read_text())
    boundary = {"changed_unique_questions": aggregate_summary["unique_boundary_sensitive_questions"], "n": len(base)}
    boundary["cp95"] = clopper_pearson(boundary["changed_unique_questions"], len(base))
    flips = []
    for point in INTERVAL_POINTS:
        for X, Y in CONTRASTS:
            by_group = {}
            for i, group in first["groups"].items():
                diff = sum(int(b["indexed"][point, i, X]["correct"])-int(b["indexed"][point, i, Y]["correct"]) for b in bundles)/2
                by_group[group] = by_group.get(group, 0)+diff
            flips.append({"point": point, "X": X, "Y": Y, **sign_flip(list(by_group.values()), len(base))})
    ledger = choice_ledger(second["plan"])
    inputs = {**first["input_sha256"], **second["input_sha256"], **aggregate_hashes,
              str(aggregate_dir/"manifest.json"): file_sha256(aggregate_dir/"manifest.json")}
    for name, digest in inputs.items():
        if file_sha256(Path(name)) != digest:
            raise ValueError("input changed during reporting review")
    output.mkdir(parents=True, exist_ok=False)
    files = {"choices.json": ledger, "draw0_regression.json": regression, "strata.json": strata,
             "null_and_boundary.json": {"nulls": nulls, "M_boundary": boundary}, "sign_flip.json": flips}
    for name, value in files.items():
        (output/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n")
    lines = ["# Retrospective reporting review", "", ledger["methods_sentence"], "",
             "First-draw standalone regression exactly matches all five saved tables; second-draw outcomes were not needed for that check.",
             "Tests and NumPy validate implementation, not independence of analytic choices from inspected outcomes.", "",
             "Draw indices 0 and 1 below mean the first and second collected draws, respectively.", "",
             "| Draw | M stratum | n | F-A b | c | Net contribution across all 12 questions (pp) |",
             "| --- | --- | ---: | ---: | ---: | ---: |"]
    for draw in strata:
        for table in draw["tables"]:
            if table["point"] != "M":
                continue
            c = next(c for c in table["contrasts"] if (c["X"], c["Y"]) == ("F", "A"))
            lines.append(f"| {draw['draw_index']} | {table['stratum']} | {table['n']} | {c['b']} | {c['c']} | {100*c['contribution_to_all_question_delta']:+.1f} |")
    lines.extend(["", "Base-outcome strata are descriptive subsets, not population treatment effects. Full M/D/arm/O tables and item IDs are in strata.json.",
                  "O is the fixed historical stop/no-extra-call answer, not a second fresh arm. Its 7/12 baseline is shared by both draws; quality comparisons do not imply equal costs.", "",
                  "| Arm | M draw disagreement | CP 95% |",
                  "| --- | ---: | --- |"])
    for row in nulls:
        lines.append(f"| {row['arm']} | {row['changed']}/{row['n']} | [{row['cp95'][0]:.4f}, {row['cp95'][1]:.4f}] |")
    lines.extend(["", f"M +/-8 unique-question boundary count: {boundary['changed_unique_questions']}/{boundary['n']}, CP 95% [{boundary['cp95'][0]:.4f}, {boundary['cp95'][1]:.4f}].",
                  "The denominator is questions, not the correlated arm/cap/draw cells. This does not certify D sensitivity.", "",
                  "| Point | Contrast | Exhaustive assignments | Two-sided sign-flip p |",
                  "| --- | --- | ---: | ---: |"])
    for row in flips:
        lines.append(f"| {row['point']} | {row['X']}-{row['Y']} | {row['assignments']} | {row['two_sided_p']:.6f} |")
    lines.extend(["", "Sign-flip p values assume groupwise sign exchangeability, beyond a weak zero-mean null; enumeration is exhaustive, descriptive and unadjusted.",
                  "No practical margin/utility, confirmatory decision, superiority, mechanism or Stage 0 result is established.",
                  "CONT is the active continuation comparator for restart benefit. O is the required stop baseline for deployment value; A is a reset/resample ablation.",
                  "Deployment comparisons require matched total budget/cost scope and online measurement; historical base EOS counts remain unverified."])
    (output/"report.md").write_text("\n".join(lines)+"\n")
    (output/"manifest.json").write_text(json.dumps({"status": "complete", "evidence": "retrospective_exposed_development_reporting_review",
        "confirmatory": False, "stage_0_changed": False, "new_model_calls": 0, "input_sha256": inputs,
        "source_sha256": {name: file_sha256(ROOT/name) for name in ("scripts/review_cot_restart_reporting.py", "scripts/aggregate_cot_restart_matched.py", "scripts/cot_restart_rescue_diagnostics.py")},
        "output_sha256": {p.name: file_sha256(p) for p in output.iterdir()}}, ensure_ascii=False, indent=2)+"\n")
    return {"draw0_regression": regression["status"], "null_counts": {r["arm"]: r["changed"] for r in nulls}, "new_model_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(review(args.output), indent=2))


if __name__ == "__main__":
    main()
