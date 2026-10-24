"""Offline repair review: isolated outputs and authored selector variants only."""
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments import checker_dry_run as m
from reasoning.reasoning_strategies import majority_vote


def main():
    with tempfile.TemporaryDirectory(prefix="checker-repair-second-review-") as temp:
        target = Path(temp) / "run"
        m.build_checker_development_dry_run_artifacts(ROOT, target)
        first = [json.loads(line) for line in (target / "calls.jsonl").read_text().splitlines()]
        before = (target / "manifest.json").read_bytes()
        rejected_occupied = False
        rejection_error = None
        try:
            m.build_checker_development_dry_run_artifacts(ROOT, target)
        except ValueError as exc:
            rejected_occupied = True
            rejection_error = str(exc)
        second = [json.loads(line) for line in (target / "calls.jsonl").read_text().splitlines()]
        ledger = json.loads((target / "generation_ledger.json").read_text())
        summary = json.loads((target / "dry_run_summary.json").read_text())
        after = (target / "manifest.json").read_bytes()
        rerun = dict(first_journal_rows=len(first), second_journal_rows=len(second),
                     unique_second_call_ids=len({r["call_id"] for r in second}),
                     rejected_occupied=rejected_occupied,
                     rejection_error=rejection_error,
                     bytes_unchanged=before == after,
                     manifest_replaced=before != after,
                     final_ledger_calls=ledger["total_calls_started"],
                     fixed_cot=summary["paths"]["fixed_cot"])
        assert rejected_occupied is True
        assert before == after
        assert len(second) == len(first)
    candidates = ["1+2+3+4", "(1+3)*(2+4)", "(1 + 3) * (2 + 4)"]
    scripted = {("authored", "tot_candidate", i): {"output":"Answer: "+a,"tokens":20}
                for i,a in enumerate(candidates)}
    scripted[("authored", "tot_selector", 0)] = {"output":"no selection","tokens":5}
    evaluator = m.G24CheckerLadderEvaluator(m.ScriptedGenerationBackend(m.GenerationLedger(),scripted))
    selected = evaluator.evaluate_rung("TOT","authored","Make 24 using 1,2,3,4.",[1,2,3,4])
    vote, _ = majority_vote(candidates, answer_type="expression")
    result = {"same_directory_rerun":rerun,
              "selector_whitespace_variants":{"candidates":candidates,"dry_run_answer":selected.extracted_answer,
                  "dry_run_verification_status":selected.verification_status,"backend_vote_expression_key":vote},
              "new_model_calls":0,"gsm8k_candidate_read":False}
    (Path(__file__).parent/"counterexamples.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    main()
