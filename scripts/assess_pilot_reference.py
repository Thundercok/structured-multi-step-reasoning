"""Describe baseline headroom and confidence on an audited development pilot."""

import argparse
import json
import runpy
from pathlib import Path

from experiments.research_pilot import sha256_file, verify_replay


def ranking_auc(correct_scores, wrong_scores):
    if not correct_scores or not wrong_scores:
        return None
    return sum((a > b) + 0.5 * (a == b) for a in correct_scores for b in wrong_scores) / (len(correct_scores) * len(wrong_scores))


def assess(records):
    conditions, bounds = [], []
    for cap in sorted({row["token_budget"] for row in records}):
        selected = [row for row in records if row["token_budget"] == cap]
        by_id = {}
        for row in selected:
            by_id.setdefault(row["id"], {})[row["strategy"]] = row
        if any(set(pair) != {"DIRECT", "COT"} for pair in by_id.values()):
            raise ValueError("Each question must have both fixed-strategy outputs")
        bounds.append({"cap_per_call": cap, "questions": len(by_id),
            "gold_informed_best_of_two_correct": sum(any(row["correct"] for row in pair.values()) for pair in by_id.values()),
            "both_wrong": sum(not any(row["correct"] for row in pair.values()) for pair in by_id.values()),
            "uses_gold_labels": True, "deployable_method": False})
        for strategy in ("DIRECT", "COT"):
            rows = [row for row in selected if row["strategy"] == strategy]
            correct = [row for row in rows if row["correct"]]
            wrong = [row for row in rows if not row["correct"]]
            features = {
                "confidence": lambda row: row["confidence"],
                "sequence_probability": lambda row: row["trace"]["generations"][0]["signals"]["p_seq"],
                "token_margin": lambda row: row["trace"]["generations"][0]["signals"]["mean_margin"],
                "negative_token_entropy": lambda row: -row["trace"]["generations"][0]["signals"]["mean_entropy"],
                "not_length_stopped": lambda row: float(row["trace"]["generations"][0]["finish_reason"] != "length"),
                "has_parseable_answer": lambda row: float(row["trace"]["parse_status"] != "fail"),
            }
            conditions.append({"cap_per_call": cap, "strategy": strategy,
                "questions": len(rows), "correct": len(correct),
                "mean_generated_tokens": sum(row["tokens"] for row in rows) / len(rows),
                "mean_confidence_correct": sum(row["confidence"] for row in correct) / len(correct) if correct else None,
                "mean_confidence_wrong": sum(row["confidence"] for row in wrong) / len(wrong) if wrong else None,
                "wrong_with_confidence_at_least_0_8": sum(row["confidence"] >= 0.8 for row in wrong),
                "correct_wrong_pairs": len(correct) * len(wrong),
                "ranking_auc": {name: ranking_auc([feature(row) for row in correct], [feature(row) for row in wrong]) for name, feature in features.items()},
                "brier_if_heuristic_interpreted_as_probability": sum((row["confidence"] - int(row["correct"])) ** 2 for row in rows) / len(rows)})
    return {"conditions": conditions, "accuracy_bounds": bounds,
        "descriptive_only": True, "post_hoc_feature_inspection": True,
        "ranking_pairs_are_not_independent_questions": True,
        "calibrator_fitted": False, "controller_evaluated": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--audited-analysis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError(args.output)
    manifest = json.loads((args.run / "manifest.json").read_text())
    dataset, records, _ = verify_replay(args.run, manifest)
    analysis_manifest = json.loads((args.audited_analysis / "manifest.json").read_text())
    validator = args.audited_analysis / "analysis_source.py"
    if sha256_file(validator) != analysis_manifest["analysis_source_sha256"] or analysis_manifest["input_manifest_sha256"] != sha256_file(args.run / "manifest.json"):
        raise ValueError("Frozen score validator does not identify this measured run")
    runpy.run_path(str(validator))["validate_records"](dataset, records)
    # Known rankings check the treatment of ordering and ties without model calls.
    assert ranking_auc([0.9], [0.1]) == 1
    assert ranking_auc([0.1], [0.9]) == 0
    assert ranking_auc([0.5], [0.5]) == 0.5
    result = assess(records)
    args.output.mkdir(parents=True)
    (args.output / "assessment.json").write_text(json.dumps(result, indent=2) + "\n")
    (args.output / "manifest.json").write_text(json.dumps({"kind": "development_pilot_reference_assessment",
        "input_manifest_sha256": sha256_file(args.run / "manifest.json"),
        "audited_analysis_manifest_sha256": sha256_file(args.audited_analysis / "manifest.json"),
        "score_validator_sha256": sha256_file(validator),
        "source_sha256": sha256_file(Path(__file__)), "evidence": manifest["evidence"],
        "assessment_sha256": sha256_file(args.output / "assessment.json"),
        "new_model_calls": 0, "publication_ready": False, "policy_fitted": False}, indent=2) + "\n")
    print(args.output / "assessment.json")


if __name__ == "__main__":
    main()
