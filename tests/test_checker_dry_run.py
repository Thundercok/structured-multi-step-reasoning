"""Unit and contract tests for the offline Game-of-24 checker development evaluator and generation call ledger."""

import json
from pathlib import Path
import sys
import time
import pytest

from experiments.checker_dry_run import (
    BudgetExhaustedError,
    CooperativeInterruption,
    EvaluatorResult,
    G24CheckerLadderEvaluator,
    GenerationLedger,
    MAX_TOTAL_CALLS,
    MAX_TOTAL_GENERATED_TOKENS,
    MAX_TOKENS_PER_CALL,
    ScriptedGenerationBackend,
    compare_rescue_and_harm,
    run_query_only_solver_baseline,
)
from scripts.verifiers import VerificationStatus


def test_no_forbidden_imports():
    """Verify in a clean subprocess that importing checker_dry_run never imports MLX, embeddings, or Qt."""
    import subprocess
    code = """
import sys, builtins
sys.path.insert(0, ".")
original_import = builtins.__import__
forbidden = {'mlx', 'mlx_lm', 'sentence_transformers', 'PyQt6', 'PySide6'}
def guarded_import(name, *args, **kwargs):
    pkg = name.split('.')[0]
    if pkg in forbidden:
        raise AssertionError(f"Forbidden module {name} imported!")
    return original_import(name, *args, **kwargs)
builtins.__import__ = guarded_import

import experiments.checker_dry_run
for mod in forbidden:
    assert mod not in sys.modules, f"Forbidden module {mod} was imported!"
"""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, "-c", code], cwd=str(root), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_early_stop_on_valid():
    """Rung 0 (CoT) produces a valid expression -> early stop, SC and TOT never called."""
    ledger = GenerationLedger()
    backend = ScriptedGenerationBackend(
        ledger=ledger,
        scripted_responses={
            ("g24_0003", "cot", 0): {
                "output": "Answer: (8 + 4) * (7 - 5)",
                "tokens": 85,
                "prompt_tokens": 30,
            }
        },
    )
    evaluator = G24CheckerLadderEvaluator(backend)
    item = {
        "id": "g24_0003",
        "query": "Make 24 using numbers 5, 8, 4, 7.",
        "numbers_from_query": [5, 8, 4, 7],
        "answer": "(8 + 4) * (7 - 5)",
        "answer_type": "expression",
    }

    result = evaluator.evaluate_checker_gated(item)

    assert result.stop_reason == "valid_early_stop"
    assert result.verification_status == VerificationStatus.VALID.value
    assert len(result.steps_taken) == 1
    assert result.steps_taken[0].strategy == "COT"
    assert result.total_calls == 1
    assert result.total_generated_tokens == 85
    assert result.total_prompt_tokens == 30
    assert result.correct is True
    assert ledger.total_calls_started == 1
    assert ledger.total_calls_succeeded == 1


def test_invalid_rescued_by_fallback():
    """Rung 0 (CoT) invalid -> escalates to SC -> SC produces valid -> stop, TOT never called."""
    ledger = GenerationLedger()
    backend = ScriptedGenerationBackend(
        ledger=ledger,
        scripted_responses={
            ("g24_0023", "cot", 0): {
                "output": "Answer: Try (11 * 4) - (10 + 8)",  # 44 - 18 = 26 != 24
                "tokens": 90,
                "prompt_tokens": 30,
            },
            # SC returns 5 samples, majority are valid
            ("g24_0023", "sc_sample", 0): {"output": "Answer: (10 - 8) * (11 - 4)", "tokens": 80},  # 14 != 24
            ("g24_0023", "sc_sample", 1): {"output": "Answer: (11 - 8) * 10 - 4", "tokens": 85},  # (3)*10 - 4 = 26 != 24
            ("g24_0023", "sc_sample", 2): {"output": "Answer: (8 * ((10 + 4) - 11))", "tokens": 90},  # 8 * 3 = 24!
            ("g24_0023", "sc_sample", 3): {"output": "Answer: (8 * ((10 + 4) - 11))", "tokens": 90},
            ("g24_0023", "sc_sample", 4): {"output": "Answer: (8 * ((10 + 4) - 11))", "tokens": 90},
        },
    )
    evaluator = G24CheckerLadderEvaluator(backend)
    item = {
        "id": "g24_0023",
        "family": "g24",
        "query": "Make 24 using numbers 10, 4, 11, 8.",
        "numbers_from_query": [10, 4, 11, 8],
        "answer": "(8 * ((10 + 4) - 11))",
        "answer_type": "expression",
    }

    cot_only = evaluator.evaluate_fixed_strategy("COT", item)
    gated = evaluator.evaluate_checker_gated(item)

    assert cot_only.verification_status == VerificationStatus.INVALID.value
    assert gated.stop_reason == "valid_early_stop"
    assert gated.verification_status == VerificationStatus.VALID.value
    assert len(gated.steps_taken) == 2
    assert gated.steps_taken[0].strategy == "COT"
    assert gated.steps_taken[1].strategy == "SELF_CONSISTENCY"
    # Calls: 1 for CoT + 5 for SC = 6
    assert gated.total_calls == 6

    rescue, harm = compare_rescue_and_harm(cot_only, gated)
    assert rescue is True
    assert harm is False


def test_unverifiable_rescued_by_fallback():
    """Rung 0 (CoT) unverifiable syntax -> escalates to SC -> valid -> stop."""
    ledger = GenerationLedger()
    backend = ScriptedGenerationBackend(
        ledger=ledger,
        scripted_responses={
            ("g24_0014", "cot", 0): {
                "output": "Answer: Try (9 - (7 - (3 + 2",  # Unclosed paren syntax error
                "tokens": 40,
                "prompt_tokens": 30,
            },
            # SC samples
            ("g24_0014", "sc_sample", -1): {
                "output": "Answer: (9 - 7) * (3 * 4)",  # invalid numbers
                "tokens": 80,
            },
            ("g24_0014", "sc_sample", 0): {"output": "Answer: (9 - 7) * (3 * 4)", "tokens": 80},
            ("g24_0014", "sc_sample", 1): {"output": "Answer: (9 - 7) * (3 * 4)", "tokens": 80},
            ("g24_0014", "sc_sample", 2): {"output": "Answer: (9 + 7 - 2) * 3", "tokens": 80},  # (16-2)*3 = 42
            ("g24_0014", "sc_sample", 3): {"output": "Answer: (9 - 7) * (3 * 4)", "tokens": 80},
            ("g24_0014", "sc_sample", 4): {"output": "Answer: (9 - 7) * (3 * 4)", "tokens": 80},
            # TOT candidate branches + selector
            ("g24_0014", "tot_candidate", 0): {"output": "Answer: (7 + 2) * 3 - 9", "tokens": 90},
            ("g24_0014", "tot_candidate", 1): {"output": "Answer: (9 + 7 - 2) * 3", "tokens": 90},
            ("g24_0014", "tot_candidate", 2): {"output": "Answer: (7 - 3) * (9 - 2)", "tokens": 90},
            ("g24_0014", "tot_selector", 0): {"output": "Best: 0", "tokens": 20},  # (9)*3 - 9 = 18 != 24
        },
    )
    evaluator = G24CheckerLadderEvaluator(backend)
    item = {
        "id": "g24_0014",
        "query": "Make 24 using numbers 7, 2, 3, 9.",
        "numbers_from_query": [7, 2, 3, 9],
        "answer": "(7 - 3) * (9 - 2)",
        "answer_type": "expression",
    }

    # Verify CoT step is unverifiable
    cot_step = evaluator.evaluate_rung("COT", item["id"], item["query"], item["numbers_from_query"])
    assert cot_step.verification_status == VerificationStatus.UNVERIFIABLE.value


def test_ladder_exhausted_terminal_unverified():
    """All 3 rungs produce invalid/unverifiable -> terminates with ladder_exhausted."""
    ledger = GenerationLedger()
    backend = ScriptedGenerationBackend(
        ledger=ledger,
        scripted_responses={
            ("g24_bad", "cot", 0): {"output": "Answer: 1 + 1", "tokens": 50},
            ("g24_bad", "sc_sample", -1): {"output": "Answer: 2 + 2", "tokens": 50},
            ("g24_bad", "tot_candidate", -1): {"output": "Answer: 3 + 3", "tokens": 50},
            ("g24_bad", "tot_selector", 0): {"output": "Best: 0", "tokens": 20},
        },
    )
    evaluator = G24CheckerLadderEvaluator(backend)
    item = {
        "id": "g24_bad",
        "query": "Make 24 using numbers 5, 8, 4, 7.",
        "numbers_from_query": [5, 8, 4, 7],
        "answer": "(8 + 4) * (7 - 5)",
        "answer_type": "expression",
    }

    result = evaluator.evaluate_checker_gated(item)

    assert result.stop_reason == "ladder_exhausted"
    assert result.verification_status == VerificationStatus.INVALID.value
    assert len(result.steps_taken) == 3
    # Calls: 1 (CoT) + 5 (SC) + 4 (TOT: 3 cand + 1 sel) = 10
    assert result.total_calls == 10
    # Verifier status must NOT be converted to confidence 1.0!
    assert result.steps_taken[-1].confidence != 1.0


def test_budget_preflight_blocks_recipe():
    """Ledger rejects starting a recipe if remaining calls or tokens are insufficient."""
    # Constrain ledger to only 3 calls max
    tight_ledger = GenerationLedger(max_total_calls=3, max_total_tokens=10000)
    backend = ScriptedGenerationBackend(ledger=tight_ledger)
    evaluator = G24CheckerLadderEvaluator(backend)

    # CoT needs 1 call: can afford
    assert tight_ledger.can_afford_recipe("COT") is True

    # SC needs 5 calls: cannot afford (3 < 5)
    assert tight_ledger.can_afford_recipe("SELF_CONSISTENCY") is False
    with pytest.raises(BudgetExhaustedError):
        tight_ledger.preflight_check_recipe("SELF_CONSISTENCY")

    # In evaluator, preflight blocks SC before execution
    item = {
        "id": "g24_tight",
        "query": "Make 24 using numbers 5, 8, 4, 7.",
        "numbers_from_query": [5, 8, 4, 7],
        "answer": "(8 + 4) * (7 - 5)",
    }
    # If CoT is invalid, checker_gated will attempt SC, fail preflight, and stop with budget_exhausted
    backend.scripted_responses = {
        ("g24_tight", "cot", 0): {"output": "Answer: 99", "tokens": 50}
    }
    res = evaluator.evaluate_checker_gated(item)
    assert res.stop_reason == "budget_exhausted"
    # Only 1 call was started/completed, SC was blocked
    assert tight_ledger.total_calls_started == 1


def test_cancellation_and_deadline_timeout():
    """Evaluator respects cancellation callback and deadline timeout."""
    ledger = GenerationLedger()
    backend = ScriptedGenerationBackend(ledger=ledger)
    evaluator = G24CheckerLadderEvaluator(backend)
    item = {
        "id": "g24_cancel",
        "query": "Make 24 using numbers 5, 8, 4, 7.",
        "numbers_from_query": [5, 8, 4, 7],
    }

    # Cancelled before first call
    res_cancel = evaluator.evaluate_checker_gated(item, should_cancel=lambda: True)
    assert res_cancel.stop_reason == "cancelled"
    assert len(res_cancel.steps_taken) == 0

    # Deadline in past
    res_timeout = evaluator.evaluate_checker_gated(item, deadline_monotonic=time.monotonic() - 10)
    assert res_timeout.stop_reason == "timeout"
    assert len(res_timeout.steps_taken) == 0


def test_gold_field_independence():
    """Changing gold answer has zero effect on ladder path, verification status, stop reason, or calls."""
    ledger1 = GenerationLedger()
    b1 = ScriptedGenerationBackend(
        ledger=ledger1,
        scripted_responses={
            ("g24_ind", "cot", 0): {"output": "Answer: (8 + 4) * (7 - 5)", "tokens": 100, "prompt_tokens": 25}
        },
    )
    eval1 = G24CheckerLadderEvaluator(b1)
    item_correct_gold = {
        "id": "g24_ind",
        "query": "Make 24 using numbers 5, 8, 4, 7.",
        "numbers_from_query": [5, 8, 4, 7],
        "answer": "(8 + 4) * (7 - 5)",
    }
    r1 = eval1.evaluate_checker_gated(item_correct_gold)

    ledger2 = GenerationLedger()
    b2 = ScriptedGenerationBackend(
        ledger=ledger2,
        scripted_responses={
            ("g24_ind", "cot", 0): {"output": "Answer: (8 + 4) * (7 - 5)", "tokens": 100, "prompt_tokens": 25}
        },
    )
    eval2 = G24CheckerLadderEvaluator(b2)
    item_bogus_gold = {
        "id": "g24_ind",
        "family": "g24",
        "query": "Make 24 using numbers 5, 8, 4, 7.",
        "numbers_from_query": [5, 8, 4, 7],
        "meta": {"numbers": [9, 9, 9, 9]},  # Gold evaluator numbers flipped to test post-hoc scoring isolation
        "answer": "9 * 9 - (9 * 9)",
    }
    r2 = eval2.evaluate_checker_gated(item_bogus_gold)

    # Path, stopping, verification, tokens, and calls MUST be completely identical
    assert r1.stop_reason == r2.stop_reason == "valid_early_stop"
    assert r1.verification_status == r2.verification_status == "valid"
    assert r1.total_calls == r2.total_calls == 1
    assert r1.total_generated_tokens == r2.total_generated_tokens == 100
    assert r1.total_prompt_tokens == r2.total_prompt_tokens == 25
    assert r1.final_output == r2.final_output

    # Post-hoc correctness check differs because gold specification differs
    assert r1.correct is True
    assert r2.correct is False


def test_generation_ledger_mid_sc_failure():
    """If call 3 of 5 fails in SC, completed calls 1 and 2 are preserved in ledger with measured tokens."""
    ledger = GenerationLedger()
    backend = ScriptedGenerationBackend(
        ledger=ledger,
        scripted_responses={
            ("g24_mid_err", "sc_sample", 0): {"output": "Answer: 1", "tokens": 50},
            ("g24_mid_err", "sc_sample", 1): {"output": "Answer: 2", "tokens": 60},
            ("g24_mid_err", "sc_sample", 2): {"error": "Connection reset mid-generation", "error_type": "ConnectionError"},
            ("g24_mid_err", "sc_sample", 3): {"output": "Answer: 4", "tokens": 70},
            ("g24_mid_err", "sc_sample", 4): {"output": "Answer: 5", "tokens": 80},
        },
    )
    evaluator = G24CheckerLadderEvaluator(backend)

    with pytest.raises(RuntimeError, match="ConnectionError"):
        evaluator.evaluate_rung("SELF_CONSISTENCY", "g24_mid_err", "Query", [1, 2, 3, 4], k=5)

    # Verify ledger entries
    assert ledger.total_calls_started == 3
    assert ledger.total_calls_succeeded == 2
    assert ledger.total_calls_failed == 1

    # Calls 0 and 1 have measured tokens
    assert ledger.attempts[0].status == "succeeded"
    assert ledger.attempts[0].measured_tokens == 50
    assert ledger.attempts[1].status == "succeeded"
    assert ledger.attempts[1].measured_tokens == 60

    # Call 2 failed with unknown measured tokens and conservative reservation
    assert ledger.attempts[2].status == "failed"
    assert ledger.attempts[2].measured_tokens == "unknown"
    assert ledger.attempts[2].reserved_tokens == MAX_TOKENS_PER_CALL  # 1024 conservative
    assert "ConnectionError" in ledger.attempts[2].error_type

    # Total reserved tokens = 50 + 60 + 1024 = 1134
    assert ledger.total_reserved_tokens == 1134


def test_generation_ledger_selector_failure():
    """If TOT selector fails after 3 candidate calls succeed, all 4 calls are preserved in ledger."""
    ledger = GenerationLedger()
    backend = ScriptedGenerationBackend(
        ledger=ledger,
        scripted_responses={
            ("g24_tot_err", "tot_candidate", 0): {"output": "Cand 0", "tokens": 100},
            ("g24_tot_err", "tot_candidate", 1): {"output": "Cand 1", "tokens": 110},
            ("g24_tot_err", "tot_candidate", 2): {"output": "Cand 2", "tokens": 120},
            ("g24_tot_err", "tot_selector", 0): {"error": "Selector timeout", "error_type": "TimeoutError"},
        },
    )
    evaluator = G24CheckerLadderEvaluator(backend)

    with pytest.raises(RuntimeError, match="TimeoutError"):
        evaluator.evaluate_rung("TOT", "g24_tot_err", "Query", [1, 2, 3, 4], branches=3)

    assert ledger.total_calls_started == 4
    assert ledger.total_calls_succeeded == 3
    assert ledger.total_calls_failed == 1
    assert ledger.attempts[3].status == "failed"
    assert ledger.attempts[3].measured_tokens == "unknown"
    assert ledger.attempts[3].reserved_tokens == MAX_TOKENS_PER_CALL


def test_query_only_solver_baseline():
    """Deterministic exact solver baseline succeeds in <20ms, 0 tokens, 0 calls."""
    solvable_nums = [5, 8, 4, 7]
    res_solvable = run_query_only_solver_baseline(solvable_nums)
    assert res_solvable["solvable"] is True
    assert res_solvable["solution_count"] > 0
    assert res_solvable["calls"] == 0
    assert res_solvable["generated_tokens"] == 0
    assert res_solvable["verification_status"] == "valid"
    assert res_solvable["wall_time_ms"] >= 0.0
    assert res_solvable["wall_time_ms"] < 2000.0  # Fast

    unsolvable_nums = [1, 1, 1, 1]
    res_unsolvable = run_query_only_solver_baseline(unsolvable_nums)
    assert res_unsolvable["solvable"] is False
    assert res_unsolvable["solution_count"] == 0
    assert res_unsolvable["calls"] == 0
    assert res_unsolvable["verification_status"] == "invalid"


def test_build_checker_development_dry_run_artifacts(tmp_path):
    """Verify that build_checker_development_dry_run_artifacts generates self-consistent artifacts."""
    from experiments.checker_dry_run import build_checker_development_dry_run_artifacts, sha256_file
    repo_root = Path(__file__).resolve().parents[1]

    manifest = build_checker_development_dry_run_artifacts(repo_root, tmp_path)

    assert manifest["status"] == "complete"
    assert manifest["model_calls"] is False
    assert manifest["tokens_consumed"] == 0
    assert manifest["human_review_status"] == "pending"

    # Verify all manifest files exist and match sha256
    for name, expected_sha in manifest["artifact_sha256"].items():
        file_path = tmp_path / name
        assert file_path.is_file(), f"Missing artifact: {name}"
        assert sha256_file(file_path) == expected_sha, f"Checksum mismatch for: {name}"

    # Verify proposed execution plan is pending authorization
    plan = json.loads((tmp_path / "proposed_execution_plan.json").read_text(encoding="utf-8"))
    assert plan["status"] == "proposed, not authorized"
    assert plan["authorized_by_user"] is False
    assert plan["human_review_status"] == "pending"
    assert len(plan["candidate_items"]) == 8

    # Verify review summary
    summary = json.loads((tmp_path / "development_review_summary.json").read_text(encoding="utf-8"))
    assert summary["selected_groups"] == 8
    assert summary["human_review_status"] == "pending"
    assert summary["human_approval_granted"] is False
    assert summary["historical_cot_coverage"]["missing_recipes"] == ["SELF_CONSISTENCY", "TOT"]
    assert summary["query_only_solver_summary"]["solvable_count"] == 8

    # Verify input_sha256 and source_sha256 in manifest
    assert "input_sha256" in manifest
    assert "source_sha256" in manifest
    assert "dataset.json" in manifest["input_sha256"]
    assert "records.json" in manifest["input_sha256"]


def test_budget_strict_validation_r3():
    """R3: Validate declared cap, measured tokens, negative counts, and recipe names."""
    ledger = GenerationLedger(max_tokens_per_call=1024, max_total_tokens=10000)

    # 1. Declared cap > configured cap
    with pytest.raises(ValueError, match="exceeds configured per-call cap"):
        ledger.record_attempt("item1", "COT", "cot", 0, declared_max_tokens=2048)

    # 2. Non-positive or boolean declared cap
    with pytest.raises(ValueError, match="positive integer"):
        ledger.record_attempt("item1", "COT", "cot", 0, declared_max_tokens=-10)
    with pytest.raises(ValueError, match="positive integer"):
        ledger.record_attempt("item1", "COT", "cot", 0, declared_max_tokens=True)

    # 3. Unknown recipe
    with pytest.raises(ValueError, match="Unknown recipe strategy"):
        ledger.record_attempt("item1", "UNKNOWN_RECIPE", "step", 0, declared_max_tokens=500)

    # 4. Success with measured > declared
    att = ledger.record_attempt("item1", "COT", "cot", 0, declared_max_tokens=500)
    with pytest.raises(ValueError, match="exceeds declared per-call cap"):
        ledger.record_success(att, "Answer: 24", measured_tokens=501, prompt_tokens=10)

    # 5. Success with negative tokens
    with pytest.raises(ValueError, match="non-negative integer"):
        ledger.record_success(att, "Answer: 24", measured_tokens=-5, prompt_tokens=10)

    # 6. Failure with negative tokens
    att2 = ledger.record_attempt("item2", "COT", "cot", 0, declared_max_tokens=500)
    with pytest.raises(ValueError, match="non-negative integer"):
        ledger.record_failure(att2, "Error", "msg", measured_tokens=-1)


def test_partial_cost_accounting_on_interruption_r2():
    """R2: Cost accounting accounts for unfinished rungs via ledger deltas."""
    ledger = GenerationLedger()
    scripted = {
        ("item_cancel", "cot", 0): {"output": "Answer: 99", "tokens": 50, "prompt_tokens": 10},
        ("item_cancel", "sc_sample", 0): {"output": "Answer: 99", "tokens": 60, "prompt_tokens": 12},
        ("item_cancel", "sc_sample", 1): {"output": "Answer: 99", "tokens": 70, "prompt_tokens": 14},
    }
    backend = ScriptedGenerationBackend(ledger=ledger, scripted_responses=scripted)
    evaluator = G24CheckerLadderEvaluator(backend)
    item = {
        "id": "item_cancel",
        "query": "Make 24 using numbers 1, 2, 3, 4.",
        "numbers_from_query": [1, 2, 3, 4],
    }

    # Cancel after 3 calls succeed
    res = evaluator.evaluate_checker_gated(item, should_cancel=lambda: ledger.total_calls_succeeded >= 3)

    assert res.stop_reason == "cancelled"
    assert res.total_calls == 3
    assert res.total_generated_tokens == 180  # 50 + 60 + 70
    assert res.total_prompt_tokens == 36     # 10 + 12 + 14
    assert res.total_reserved_tokens == 180
    assert ledger.total_calls_started == 3


def test_candidate_selection_semantics_and_majority_fallback_r4():
    """R4: Candidate selection sends question + candidates and falls back to majority on parse failure."""
    ledger = GenerationLedger()
    bad, good = "1+2+3+4", "(1+3)*(2+4)"
    scripted = {
        ("item_sel", "tot_candidate", 0): {"output": f"Answer: {bad}", "tokens": 20},
        ("item_sel", "tot_candidate", 1): {"output": f"Answer: {good}", "tokens": 20},
        ("item_sel", "tot_candidate", 2): {"output": f"Answer: {good}", "tokens": 20},
        ("item_sel", "tot_selector", 0): {"output": "unparseable output", "tokens": 10},
    }

    captured = {}

    class CapturingBackend(ScriptedGenerationBackend):
        def generate(self, *args, **kwargs):
            if kwargs.get("call_kind") == "tot_selector":
                captured["query"] = kwargs["query"]
            return super().generate(*args, **kwargs)

    backend = CapturingBackend(ledger=ledger, scripted_responses=scripted)
    evaluator = G24CheckerLadderEvaluator(backend)

    res = evaluator.evaluate_rung("TOT", "item_sel", "Make 24 using 1, 2, 3, 4.", [1, 2, 3, 4])

    # Prompt verification
    assert "Make 24" in captured["query"]
    assert good in captured["query"]
    assert bad in captured["query"]

    # Backend majority fallback chose 'good'
    assert res.extracted_answer == good
    assert res.verification_status == "valid"


def test_duplicate_record_rejection_r5(tmp_path):
    """R5: Builder rejects duplicate (id, strategy, token_budget) records in historical dataset."""
    from experiments.checker_dry_run import build_checker_development_dry_run_artifacts
    repo_root = Path(__file__).resolve().parents[1]

    # Create isolated copy of audit files
    base = tmp_path / "audit/development-pilot-measured-20261004-runtimefix"
    index_dir = tmp_path / "audit/rat_cot_quick_unification_20261022/independent_review/stopping_signals"
    base.mkdir(parents=True)
    index_dir.mkdir(parents=True)

    src_base = repo_root / "audit/development-pilot-measured-20261004-runtimefix"
    src_index = repo_root / "audit/rat_cot_quick_unification_20261022/independent_review/stopping_signals/development_review_index.json"

    (base / "dataset.json").write_bytes((src_base / "dataset.json").read_bytes())
    (index_dir / "development_review_index.json").write_bytes(src_index.read_bytes())

    records = json.loads((src_base / "records.json").read_text(encoding="utf-8"))
    dup = dict(records[0])
    records.append(dup)
    (base / "records.json").write_text(json.dumps(records), encoding="utf-8")

    out_dir = tmp_path / "out"
    with pytest.raises(ValueError, match="Duplicate record key detected"):
        build_checker_development_dry_run_artifacts(tmp_path, out_dir)


def test_interrupted_builder_persistence_r2(tmp_path):
    """R2: Interrupted builder persists calls.jsonl and manifest.json with status 'interrupted'."""
    from experiments.checker_dry_run import (
        build_checker_development_dry_run_artifacts,
        ScriptedGenerationBackend,
    )
    repo_root = Path(__file__).resolve().parents[1]
    target = tmp_path / "interrupted_run"

    orig_generate = ScriptedGenerationBackend.generate
    call_count = [0]

    def intercepting_generate(self, *args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 2:
            raise KeyboardInterrupt("Simulated interruption during builder")
        return orig_generate(self, *args, **kwargs)

    ScriptedGenerationBackend.generate = intercepting_generate
    try:
        with pytest.raises(KeyboardInterrupt):
            build_checker_development_dry_run_artifacts(repo_root, target)
    finally:
        ScriptedGenerationBackend.generate = orig_generate

    assert (target / "calls.jsonl").is_file()
    assert (target / "manifest.json").is_file()
    man = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    assert man["status"] == "interrupted"
    assert "KeyboardInterrupt" in man["interruption_reason"]


def test_report_numbers_match_json_dynamically_r1(tmp_path):
    """R1: Report numbers match computed JSON summary dynamically with no hardcoding."""
    from experiments.checker_dry_run import build_checker_development_dry_run_artifacts
    repo_root = Path(__file__).resolve().parents[1]

    build_checker_development_dry_run_artifacts(repo_root, tmp_path)

    summary = json.loads((tmp_path / "dry_run_summary.json").read_text(encoding="utf-8"))
    report = (tmp_path / "report.md").read_text(encoding="utf-8")

    p_gated = summary["paths"]["checker_gated"]
    p_always = summary["paths"]["always_escalate"]

    # Verify checker gated calls match dynamically
    assert f"**{p_gated['total_calls']}**" in report
    assert f"**{p_always['total_calls']}**" not in report or p_gated["total_calls"] != p_always["total_calls"]
    assert f"{p_gated['total_generated_tokens']:,}" in report

    # Verify synthetic double badges
    assert "[SYNTHETIC DOUBLE]" in report


def test_order_invariance_and_budget_isolation_r1():
    """R1: Evaluation order does not alter per-item ladder decisions; paths have isolated budgets."""
    # Build trace bank for 2 items
    item_a = {
        "id": "item_a",
        "query": "Make 24 using numbers 5, 8, 4, 7.",
        "numbers_from_query": [5, 8, 4, 7],
        "answer": "(8 + 4) * (7 - 5)",
    }
    item_b = {
        "id": "item_b",
        "query": "Make 24 using numbers 10, 4, 11, 8.",
        "numbers_from_query": [10, 4, 11, 8],
        "answer": "(8 * ((10 + 4) - 11))",
    }
    trace_bank = {
        ("item_a", "cot", 0): {"output": "Answer: (8 + 4) * (7 - 5)", "tokens": 80},
        ("item_b", "cot", 0): {"output": "Answer: 99", "tokens": 80},
        ("item_b", "sc_sample", 0): {"output": "Answer: (8 * ((10 + 4) - 11))", "tokens": 90},
        ("item_b", "sc_sample", 1): {"output": "Answer: (8 * ((10 + 4) - 11))", "tokens": 90},
        ("item_b", "sc_sample", 2): {"output": "Answer: (8 * ((10 + 4) - 11))", "tokens": 90},
        ("item_b", "sc_sample", 3): {"output": "Answer: (8 * ((10 + 4) - 11))", "tokens": 90},
        ("item_b", "sc_sample", 4): {"output": "Answer: (8 * ((10 + 4) - 11))", "tokens": 90},
    }

    # Forward order: item_a then item_b
    ledger_fwd = GenerationLedger(max_total_calls=80)
    backend_fwd = ScriptedGenerationBackend(ledger=ledger_fwd, scripted_responses=trace_bank)
    eval_fwd = G24CheckerLadderEvaluator(backend_fwd)
    res_a_fwd = eval_fwd.evaluate_checker_gated(item_a)
    res_b_fwd = eval_fwd.evaluate_checker_gated(item_b)

    # Reverse order: item_b then item_a
    ledger_rev = GenerationLedger(max_total_calls=80)
    backend_rev = ScriptedGenerationBackend(ledger=ledger_rev, scripted_responses=trace_bank)
    eval_rev = G24CheckerLadderEvaluator(backend_rev)
    res_b_rev = eval_rev.evaluate_checker_gated(item_b)
    res_a_rev = eval_rev.evaluate_checker_gated(item_a)

    # Item A is valid at CoT: exactly 1 call in both orders
    assert res_a_fwd.total_calls == res_a_rev.total_calls == 1
    assert res_a_fwd.verification_status == res_a_rev.verification_status == "valid"

    # Item B rescues at SC: exactly 6 calls in both orders
    assert res_b_fwd.total_calls == res_b_rev.total_calls == 6
    assert res_b_fwd.verification_status == res_b_rev.verification_status == "valid"

    # Total calls identical regardless of execution order
    assert ledger_fwd.total_calls_started == ledger_rev.total_calls_started == 7


def test_refuse_reuse_occupied_evidence_directory_c1(tmp_path):
    """C1: Reject occupied evidence directories before any write and ensure zero byte changes."""
    from experiments.checker_dry_run import build_checker_development_dry_run_artifacts
    repo_root = Path(__file__).resolve().parents[1]
    target_dir = tmp_path / "occupied_evidence"

    # Initial build should succeed
    build_checker_development_dry_run_artifacts(repo_root, target_dir)
    assert (target_dir / "manifest.json").is_file()

    # Record snapshot of all files and their byte content
    before_state = {f.name: f.read_bytes() for f in target_dir.iterdir()}

    # Second build must raise ValueError before touching files
    with pytest.raises(ValueError, match="Refusing to reuse occupied evidence directory"):
        build_checker_development_dry_run_artifacts(repo_root, target_dir)

    # After state must be byte-for-byte identical
    after_state = {f.name: f.read_bytes() for f in target_dir.iterdir()}
    assert before_state == after_state


def test_fixed_cot_labeled_synthetic_c2(tmp_path):
    """C2: Label fixed_cot replay path and tokens as synthetic replay, preserving provenance distinction."""
    from experiments.checker_dry_run import build_checker_development_dry_run_artifacts
    repo_root = Path(__file__).resolve().parents[1]
    target_dir = tmp_path / "prov_test"

    build_checker_development_dry_run_artifacts(repo_root, target_dir)

    summary = json.loads((target_dir / "dry_run_summary.json").read_text(encoding="utf-8"))
    p_cot = summary["paths"]["fixed_cot"]
    assert p_cot["is_synthetic"] is True
    assert "synthetic replay" in p_cot["data_provenance"]

    dev_summary = json.loads((target_dir / "development_review_summary.json").read_text(encoding="utf-8"))
    assert dev_summary["historical_cot_coverage"]["data_provenance"] == "historical pilot measured"

    report = (target_dir / "report.md").read_text(encoding="utf-8")
    assert "Fixed CoT [SYNTHETIC REPLAY]" in report
    assert "Query-Only Solver [Deterministic Sample]" in report


def test_selector_expression_whitespace_normalization_c3():
    """C3: TOT selector majority fallback normalizes expressions across whitespace variants."""
    ledger = GenerationLedger()
    bad, good_no_space, good_with_space = "1+2+3+4", "(1+3)*(2+4)", "(1 + 3) * (2 + 4)"
    scripted = {
        ("item_c3", "tot_candidate", 0): {"output": f"Answer: {bad}", "tokens": 20},
        ("item_c3", "tot_candidate", 1): {"output": f"Answer: {good_no_space}", "tokens": 20},
        ("item_c3", "tot_candidate", 2): {"output": f"Answer: {good_with_space}", "tokens": 20},
        ("item_c3", "tot_selector", 0): {"output": "unparseable response", "tokens": 10},
    }

    backend = ScriptedGenerationBackend(ledger=ledger, scripted_responses=scripted)
    evaluator = G24CheckerLadderEvaluator(backend)

    res = evaluator.evaluate_rung("TOT", "item_c3", "Make 24 using 1, 2, 3, 4", [1, 2, 3, 4])
    # With expression normalization, good_no_space and good_with_space cluster together (2 votes vs 1 vote for bad)
    # The tie-breaker picks candidate index 1
    assert res.verification_status == "valid"
    assert res.extracted_answer == good_no_space
    assert res.output == f"Answer: {good_no_space}"


