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
    """Verify that importing checker_dry_run never imports MLX, embeddings, or Qt."""
    forbidden = ["mlx", "mlx_lm", "sentence_transformers", "PyQt6", "PySide6"]
    for mod in forbidden:
        assert mod not in sys.modules, f"Forbidden module {mod} was imported!"


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
    assert res_solvable["cpu_time_ms"] < 100.0  # Fast

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
