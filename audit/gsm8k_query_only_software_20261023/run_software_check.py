"""Reproduce research software evidence with authored fixtures and the official CLI.

No candidate data, model, embeddings or live UI conversation is used.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(output):
    output.mkdir(parents=True, exist_ok=False)
    helpers = runpy.run_path(str(ROOT / "tests/test_gsm8k_routing_baseline.py"))
    inputs = {}
    for case in ("base", "validation_changed", "validation_invalid"):
        items, records = helpers["fixture_data"]()
        if case == "validation_changed":
            for row in records:
                if row["split"] == "calibration" and row["strategy"] != "PAL":
                    row["correct"] = not row["correct"]
                    row["answer"] = "7" if row["correct"] else "8"
                    row["trace"]["generations"][0]["output"] = f"Answer: {row['answer']}"
        elif case == "validation_invalid":
            records[-1]["correct"] = not records[-1]["correct"]
        folder = output / case
        folder.mkdir()
        run = helpers["save_run"](folder / "pilot", items, records)
        inputs[case] = {p.name: digest(p) for p in run.iterdir()}
        command = [sys.executable, "-m", "experiments.research_study", "--gsm8k-routing-analysis", str(run), "--output", str(folder / "analysis")]
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        (folder / "stdout.txt").write_text(completed.stdout)
        (folder / "stderr.txt").write_text(completed.stderr)
        expected = 2 if case == "validation_invalid" else 0
        if completed.returncode != expected:
            raise RuntimeError(f"{case} exit {completed.returncode}: {completed.stderr}")
        if inputs[case] != {p.name: digest(p) for p in run.iterdir()}:
            raise RuntimeError("Input fixture changed during analysis")
    selection_hashes = {case: digest(output / case / "analysis/selection.json") for case in inputs}
    if len(set(selection_hashes.values())) != 1:
        raise AssertionError("Validation outcomes changed fitting selection")
    summaries = {case: json.loads((output / case / "analysis/summary.json").read_text()) for case in ("base", "validation_changed")}
    deltas = {case: summary["primary_comparison"]["metrics"]["utility"]["mean_difference"] for case, summary in summaries.items()}
    if not deltas["base"] > 0 > deltas["validation_changed"]:
        raise AssertionError("Authored negative validation case did not change the result")
    failed = json.loads((output / "validation_invalid/analysis/manifest.json").read_text())
    if failed["status"] != "failed" or (output / "validation_invalid/analysis/summary.json").exists():
        raise AssertionError("Invalid validation did not preserve honest failure state")
    sources = ["experiments/gsm8k_routing_baseline.py", "experiments/research_study.py", "tests/test_gsm8k_routing_baseline.py",
               "docs/gsm8k_development_validation_protocol_20261004.md", str(Path(__file__).relative_to(ROOT))]
    result = {"kind": "authored_research_software_validation_not_model_quality", "new_model_calls": 0,
              "candidate_questions_or_outcomes_read": False, "held_out_content_read": False,
              "live_ui_acceptance": False, "stage0_changed": False,
              "synthetic_fitting_groups": 4, "synthetic_validation_groups": 4,
              "candidate_rule_count": 27, "selection_hashes_by_case": selection_hashes,
              "validation_changes_leave_selection_identical": True,
              "synthetic_utility_differences": deltas,
              "negative_validation_preserved": True, "invalid_validation_keeps_selection_and_failed_manifest": True,
              "input_fixture_hashes_unchanged": inputs,
              "source_sha256": {name: digest(ROOT / name) for name in sources},
              "model_inference_budget_used": 0, "publication_ready": False,
              "note": "Synthetic token units and constructed outcomes; these are not measured routing gains or live app results."}
    (output / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"selection_identical": True, "synthetic_utility_differences": deltas, "new_model_calls": 0}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args().output.resolve())
