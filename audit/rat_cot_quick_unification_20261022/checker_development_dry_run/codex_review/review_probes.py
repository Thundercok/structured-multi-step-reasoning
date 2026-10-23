"""Independent, offline counterexamples for the received checker dry-run.

Writes only beside this script. Uses authored fixtures and the already exposed
development artifacts; never imports or calls a model backend.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from experiments import checker_dry_run as module

OUT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def budget_cases():
    ledger = module.GenerationLedger()
    large = ledger.record_attempt("authored", "COT", "cot", 0, 2048)
    oversize = {"accepted": True, "declared": large.declared_max_tokens,
                "configured_per_call_cap": ledger.max_tokens_per_call}
    ledger2 = module.GenerationLedger()
    attempt = ledger2.record_attempt("authored", "COT", "cot", 0)
    ledger2.record_success(attempt, "Answer: 24", 2048, 1)
    overreported = {"accepted": True, "measured": attempt.measured_tokens,
                    "declared": attempt.declared_max_tokens,
                    "status": attempt.status}
    ledger3 = module.GenerationLedger()
    negative_attempt = ledger3.record_attempt("authored", "COT", "cot", 0)
    ledger3.record_success(negative_attempt, "Answer: 24", -100, 1)
    negative = {"accepted": True, "remaining_tokens": ledger3.remaining_tokens,
                "configured_total": ledger3.max_total_tokens}
    return {"oversize_dispatch": oversize, "oversize_outcome": overreported,
            "negative_outcome": negative}


def interruption_accounting(method):
    ledger = module.GenerationLedger()
    scripted = {
        ("authored-cancel", "cot", 0): {"output": "Answer: 99", "tokens": 50, "prompt_tokens": 7},
        ("authored-cancel", "sc_sample", 0): {"output": "Answer: 99", "tokens": 60, "prompt_tokens": 8},
        ("authored-cancel", "sc_sample", 1): {"output": "Answer: 99", "tokens": 70, "prompt_tokens": 9},
    }
    evaluator = module.G24CheckerLadderEvaluator(module.ScriptedGenerationBackend(ledger, scripted))
    item = {"id": "authored-cancel", "query": "Make 24 using 1, 2, 3, 4.",
            "numbers_from_query": [1, 2, 3, 4]}
    result = getattr(evaluator, method)(item, should_cancel=lambda: ledger.total_calls_succeeded >= 3)
    actual_tokens = sum(a.measured_tokens for a in ledger.attempts if isinstance(a.measured_tokens, int))
    return {"stop_reason": result.stop_reason, "reported_calls": result.total_calls,
            "ledger_calls": ledger.total_calls_started,
            "reported_tokens": result.total_generated_tokens, "ledger_tokens": actual_tokens,
            "reported_reserved": result.total_reserved_tokens,
            "ledger_reserved": ledger.total_reserved_tokens}


def selector_case():
    ledger = module.GenerationLedger()
    bad, good = "1+2+3+4", "(1+3)*(2+4)"
    scripts = {("authored-selector", "tot_candidate", i):
               {"output": "Answer: " + answer, "tokens": 20}
               for i, answer in enumerate((bad, good, good))}
    scripts[("authored-selector", "tot_selector", 0)] = {"output": "no selection", "tokens": 5}

    class CapturingBackend(module.ScriptedGenerationBackend):
        def generate(self, *args, **kwargs):
            if kwargs.get("call_kind") == "tot_selector":
                self.selector_query = kwargs["query"]
            return super().generate(*args, **kwargs)

    backend = CapturingBackend(ledger, scripts)
    evaluator = module.G24CheckerLadderEvaluator(backend)
    result = evaluator.evaluate_rung("TOT", "authored-selector", "Make 24 using 1, 2, 3, 4.", [1, 2, 3, 4])
    return {"selected_answer": result.extracted_answer,
            "verification_status": result.verification_status,
            "documented_backend_majority_answer": Counter((bad, good, good)).most_common(1)[0][0],
            "selector_query": backend.selector_query,
            "selector_has_question": "Make 24" in backend.selector_query,
            "selector_has_candidate_expressions": good in backend.selector_query}


def interrupted_builder():
    original = module.ScriptedGenerationBackend.generate
    observed = {"completed": 0}
    with tempfile.TemporaryDirectory(prefix="checker-interruption-", dir=OUT) as temporary:
        target = Path(temporary) / "run"

        def generate(self, *args, **kwargs):
            if observed["completed"] == 1:
                observed["persisted_files_before_interruption"] = sorted(p.name for p in target.iterdir())
                raise KeyboardInterrupt("authored interruption after first completed call")
            result = original(self, *args, **kwargs)
            observed["completed"] += 1
            return result

        module.ScriptedGenerationBackend.generate = generate
        try:
            module.build_checker_development_dry_run_artifacts(ROOT, target)
        except KeyboardInterrupt:
            observed["interruption_propagated"] = True
        finally:
            module.ScriptedGenerationBackend.generate = original
        observed["persisted_files_after_interruption"] = sorted(p.name for p in target.iterdir())
    return observed


def duplicate_input():
    # Isolated copies only. Original exposed artifacts remain byte-identical.
    base = Path("audit/development-pilot-measured-20261004-runtimefix")
    index_rel = Path("audit/rat_cot_quick_unification_20261022/independent_review/stopping_signals/development_review_index.json")
    with tempfile.TemporaryDirectory(prefix="checker-duplicate-", dir=OUT) as temporary:
        fixture_root = Path(temporary)
        (fixture_root / base).mkdir(parents=True)
        (fixture_root / index_rel).parent.mkdir(parents=True)
        for name in ("dataset.json", "records.json"):
            (fixture_root / base / name).write_bytes((ROOT / base / name).read_bytes())
        (fixture_root / index_rel).write_bytes((ROOT / index_rel).read_bytes())
        records = read(fixture_root / base / "records.json")
        original = next(r for r in records if r["family"] == "g24" and r["strategy"] == "COT" and r["token_budget"] == 1024)
        duplicate = {**original, "answer": "99"}
        records.append(duplicate)
        (fixture_root / base / "records.json").write_text(json.dumps(records))
        target = fixture_root / "output"
        module.build_checker_development_dry_run_artifacts(fixture_root, target)
        summary = read(target / "development_review_summary.json")
        row = next(row for row in summary["items"] if row["id"] == duplicate["id"])
        return {"duplicate_rejected": False, "duplicate_id": duplicate["id"],
                "chosen_answer": row["historical_cot_1024"]["answer"],
                "original_record_count": len(records) - 1, "modified_record_count": len(records)}


def main():
    historical = ROOT / "audit/development-pilot-measured-20261004-runtimefix"
    protected = [historical / "dataset.json", historical / "records.json"]
    before = {str(p.relative_to(ROOT)): digest(p) for p in protected}
    target = OUT / "rebuilt"
    if target.exists():
        raise ValueError("Preserve prior evidence; use a new output directory")
    module.build_checker_development_dry_run_artifacts(ROOT, target)
    summary = read(target / "dry_run_summary.json")
    original_dir = Path(__file__).resolve().parent.parent
    manifest = read(original_dir / "manifest.json")
    findings = {
        "received_manifest_artifact_hashes": {name: digest(original_dir / name) == expected
            for name, expected in manifest["artifact_sha256"].items()},
        "rebuilt_comparison": {"ledger": summary["ledger_usage"], "paths": summary["paths"]},
        "report_still_claims_23_gated_calls": "**23**" in (target / "report.md").read_text(),
        "budget_validation": budget_cases(),
        "cancelled_checker_gated": interruption_accounting("evaluate_checker_gated"),
        "cancelled_always_escalate": interruption_accounting("evaluate_always_escalate"),
        "selector_contract": selector_case(),
        "interrupted_builder": interrupted_builder(),
        "duplicate_input": duplicate_input(),
        "historical_inputs_before": before,
        "historical_inputs_after": {str(p.relative_to(ROOT)): digest(p) for p in protected},
        "new_model_calls": 0,
        "forbidden_imports": [name for name in ("mlx", "mlx_lm", "sentence_transformers", "PyQt6", "PySide6") if name in sys.modules],
    }
    assert findings["historical_inputs_before"] == findings["historical_inputs_after"]
    (OUT / "probes.json").write_text(json.dumps(findings, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in findings.items() if key != "rebuilt_comparison"}, indent=2))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New evidence directory; never overwrite an earlier run")
    args = parser.parse_args()
    if args.output is not None:
        OUT = args.output.resolve()
        OUT.mkdir(parents=True, exist_ok=False)
    main()
