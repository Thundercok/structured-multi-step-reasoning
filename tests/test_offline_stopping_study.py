"""
Tests for offline stopping study invariants.

Validates the 5 foundational theoretical invariants requested by Claude:
1. Margin m=1 matches Fixed k=1 identically.
2. ESC w=K matches Fixed k=K identically.
3. Oracle accuracy >= accuracy of all other methods on any pool.
4. Fixed-k token counts increase strictly monotonically with k.
5. Tie-break is strictly deterministic and first-seen across all families.
6. Diagnostic case: sequence ['A', 'B', 'B'] at k=3 stops under ESC w=2, but does NOT stop under margin m=2.
"""

from __future__ import annotations

import pytest
import numpy as np

from experiments.offline_stopping_study import (
    QuestionPool,
    SamplePoint,
    eval_family_0_oracle,
    eval_family_1_fixed_k,
    eval_family_2_margin,
    eval_family_2_esc_window,
    eval_family_2_adaptive_consistency,
    majority_winner,
)


@pytest.fixture
def mock_pool() -> list[QuestionPool]:
    """Generates a diverse synthetic pool of 100 questions with K=10 samples each."""
    rng = np.random.default_rng(12345)
    pool = []
    answers = ["A", "B", "C", "D"]
    for i in range(100):
        gold = "A"
        samples = []
        p_gold = rng.uniform(0.3, 0.9)
        for _ in range(10):
            if rng.uniform(0, 1) < p_gold:
                ans = gold
            else:
                ans = rng.choice(["B", "C", "D"])
            tok = int(rng.normal(250, 30))
            tok = max(tok, 50)
            samples.append(SamplePoint(answer=ans, tokens=tok, correct=(ans == gold)))
        pool.append(QuestionPool(id=f"q_{i}", query=f"query_{i}", gold=gold, split="test", samples=samples))
    return pool


def test_invariant_margin_m1_equals_fixed_k1(mock_pool):
    """Invariant 1: margin m=1 must identically match Fixed k=1."""
    res_m1 = eval_family_2_margin(mock_pool, m=1)
    res_k1 = eval_family_1_fixed_k(mock_pool, k=1)
    assert len(res_m1) == len(res_k1)
    for i in range(len(mock_pool)):
        assert res_m1[i] == res_k1[i], f"Mismatch at question {i}: m=1 {res_m1[i]} vs k=1 {res_k1[i]}"


def test_invariant_esc_wK_equals_fixed_kK(mock_pool):
    """Invariant 2: ESC w=K must identically match Fixed k=K."""
    K = 10
    res_esc_K = eval_family_2_esc_window(mock_pool, w=K)
    res_fixed_K = eval_family_1_fixed_k(mock_pool, k=K)
    assert len(res_esc_K) == len(res_fixed_K)
    for i in range(len(mock_pool)):
        assert res_esc_K[i] == res_fixed_K[i], f"Mismatch at question {i}: ESC w=K {res_esc_K[i]} vs Fixed k=K {res_fixed_K[i]}"


def test_invariant_oracle_dominates_all_families(mock_pool):
    """Invariant 3: Oracle accuracy must be >= accuracy of EVERY other family."""
    res_oracle = eval_family_0_oracle(mock_pool)
    acc_oracle = np.mean([x[0] for x in res_oracle])

    # Check against all Fixed-k
    for k in range(1, 11):
        res_k = eval_family_1_fixed_k(mock_pool, k=k)
        acc_k = np.mean([x[0] for x in res_k])
        assert acc_oracle >= acc_k, f"Oracle {acc_oracle} < Fixed-k={k} {acc_k}"

    # Check against all Margin m
    for m in range(1, 6):
        res_m = eval_family_2_margin(mock_pool, m=m)
        acc_m = np.mean([x[0] for x in res_m])
        assert acc_oracle >= acc_m, f"Oracle {acc_oracle} < Margin m={m} {acc_m}"

    # Check against ESC window
    for w in [2, 3, 4]:
        res_w = eval_family_2_esc_window(mock_pool, w=w)
        acc_w = np.mean([x[0] for x in res_w])
        assert acc_oracle >= acc_w, f"Oracle {acc_oracle} < ESC w={w} {acc_w}"

    # Check against Adaptive-Consistency
    for th in [0.7, 0.8, 0.9, 0.95]:
        res_ac = eval_family_2_adaptive_consistency(mock_pool, threshold=th)
        acc_ac = np.mean([x[0] for x in res_ac])
        assert acc_oracle >= acc_ac, f"Oracle {acc_oracle} < AC threshold={th} {acc_ac}"


def test_invariant_fixed_k_tokens_monotonically_increase(mock_pool):
    """Invariant 4: Fixed-k token counts must increase strictly monotonically with k."""
    tokens = []
    for k in range(1, 11):
        res_k = eval_family_1_fixed_k(mock_pool, k=k)
        mean_tok = np.mean([x[1] for x in res_k])
        tokens.append(mean_tok)

    for i in range(len(tokens) - 1):
        assert tokens[i] < tokens[i + 1], f"Tokens not strictly increasing: k={i+1} ({tokens[i]}) >= k={i+2} ({tokens[i+1]})"


def test_invariant_tie_break_first_seen_across_all_families():
    """Invariant 5: When answers tie, the winner is deterministically the first-seen candidate."""
    # Sequence: A, B (tie 1-1 at k=2) -> A was seen first at idx 0, B at idx 1
    samples = [
        SamplePoint("A", 100, True),
        SamplePoint("B", 100, False),
    ]
    winner = majority_winner(samples)
    assert winner == "A", f"Expected first-seen winner 'A', got {winner}"

    # Inverted sequence: B, A (tie 1-1 at k=2) -> B was seen first at idx 0
    samples_inv = [
        SamplePoint("B", 100, False),
        SamplePoint("A", 100, True),
    ]
    winner_inv = majority_winner(samples_inv)
    assert winner_inv == "B", f"Expected first-seen winner 'B', got {winner_inv}"


def test_diagnostic_abb_at_k3():
    """Diagnostic check: sequence ['A', 'B', 'B', 'C'] with gold='B'.
    At k=3:
    - ESC w=2 MUST STOP at k=3 (last 2 samples are identical 'B').
    - Margin m=2 MUST NOT STOP at k=3 (counts: B=2, A=1 -> margin=1 < 2). It stops at k=4.
    """
    q = QuestionPool(
        id="diag_q",
        query="test query",
        gold="B",
        split="test",
        samples=[
            SamplePoint("A", 100, False),  # k=1
            SamplePoint("B", 100, True),   # k=2
            SamplePoint("B", 100, True),   # k=3
            SamplePoint("C", 100, False),  # k=4
        ]
    )
    pool = [q]

    # ESC w=2:
    # At k=2: window ['A', 'B'] -> len(set)=2 -> no stop
    # At k=3: window ['B', 'B'] -> len(set)=1 -> STOPS at k=3!
    res_esc = eval_family_2_esc_window(pool, w=2)
    acc_esc, tok_esc = res_esc[0]
    assert tok_esc == 300.0, f"ESC w=2 should stop at k=3 (300 tokens), got {tok_esc}"
    assert acc_esc == 1.0, f"ESC w=2 should output winner 'B' (correct), got acc={acc_esc}"

    # Margin m=2:
    # At k=1: counts={'A':1} -> margin=1-0=1 < 2 -> no stop
    # At k=2: counts={'A':1, 'B':1} -> margin=1-1=0 < 2 -> no stop
    # At k=3: counts={'B':2, 'A':1} -> margin=2-1=1 < 2 -> NO STOP!
    # At k=4: counts={'B':2, 'A':1, 'C':1} -> margin=2-1=1 < 2 -> k=K=4 reached -> stops at k=4!
    res_margin = eval_family_2_margin(pool, m=2)
    acc_margin, tok_margin = res_margin[0]
    assert tok_margin == 400.0, f"Margin m=2 should NOT stop at k=3; should reach k=4 (400 tokens), got {tok_margin}"
    assert acc_margin == 1.0, f"Margin m=2 at k=4 should output winner 'B' (correct), got acc={acc_margin}"


def test_esc_w_validation():
    """ESC window w must be >= 2 to prevent degeneracy."""
    q = QuestionPool(id="q", query="q", gold="A", split="test", samples=[SamplePoint("A", 100, True)] * 5)
    with pytest.raises(AssertionError, match="ESC window size w must be >= 2"):
        eval_family_2_esc_window([q], w=1)


def test_diagnostic_beta_top_vs_rest_vs_top_vs_top2():
    """Diagnostic check: at k=4 with votes A=2, B=1, C=1.
    - Top-vs-Rest: Beta(n1+1, (k-n1)+1) = Beta(3, 3) -> P(p1 > 0.5) = 0.500000 (50%).
    - Top-vs-Top2 (Aggarwal et al.): Beta(n1+1, n2+1) = Beta(3, 2) -> P(p1 > 0.5) = 0.687500 (68.75%).
    - At threshold theta=0.95: at k=4 neither stops (0.50 < 0.95 and 0.6875 < 0.95).
    - As sampling continues with candidate 'A' winning (e.g. A=6, B=1, C=1 at k=8):
      Top-vs-Top2 reaches P=0.9648 >= 0.95 and STOPS at k=8.
      Top-vs-Rest reaches P=0.9102 < 0.95 and does NOT stop at k=8.
    """
    from experiments.offline_stopping_study import (
        compute_beta_rest_prob,
        compute_beta_top2_prob,
        eval_family_2_adaptive_consistency,
        eval_family_2_beta_top_vs_rest,
    )

    # 1. Direct function assertion on exact probabilities at k=4: A=2, B=1, C=1
    p_rest_k4 = compute_beta_rest_prob(n1=2, k=4)
    p_top2_k4 = compute_beta_top2_prob(n1=2, n2=1)
    assert abs(p_rest_k4 - 0.500000) < 1e-6, f"Expected 0.500000, got {p_rest_k4}"
    assert abs(p_top2_k4 - 0.687500) < 1e-6, f"Expected 0.687500, got {p_top2_k4}"

    # 2. Direct function assertion on exact probabilities at k=8: A=6, B=1, C=1
    p_top2_k8 = compute_beta_top2_prob(n1=6, n2=1)  # Beta(7, 2) = 494/512 = 0.96484375
    p_rest_k8 = compute_beta_rest_prob(n1=6, k=8)   # Beta(7, 3) = 466/512 = 0.91015625
    assert abs(p_top2_k8 - 0.96484375) < 1e-6, f"Expected 0.96484375, got {p_top2_k8}"
    assert abs(p_rest_k8 - 0.91015625) < 1e-6, f"Expected 0.91015625, got {p_rest_k8}"
    assert p_top2_k8 >= 0.95  # Stops under canonical theta=0.95
    assert p_rest_k8 < 0.95   # Fails to stop under canonical theta=0.95

    # 3. Behavior on QuestionPool: [A, B, C, A, A, A, A, A, B, C]
    # At k=8: A=6, B=1, C=1
    q = QuestionPool(
        id="beta_diag", query="q", gold="A", split="test",
        samples=[
            SamplePoint("A", 100, True),   # 1
            SamplePoint("B", 100, False),  # 2
            SamplePoint("C", 100, False),  # 3
            SamplePoint("A", 100, True),   # 4: A=2, B=1, C=1
            SamplePoint("A", 100, True),   # 5: A=3, B=1, C=1
            SamplePoint("A", 100, True),   # 6: A=4, B=1, C=1
            SamplePoint("A", 100, True),   # 7: A=5, B=1, C=1
            SamplePoint("A", 100, True),   # 8: A=6, B=1, C=1 -> Top-vs-Top2 stops!
            SamplePoint("B", 100, False),  # 9
            SamplePoint("C", 100, False),  # 10
        ]
    )
    # At theta=0.95: Top-vs-Top2 stops early at k=8 (800 tokens)
    res_top2 = eval_family_2_adaptive_consistency([q], threshold=0.95)
    assert res_top2[0][1] == 800.0

    # At theta=0.95: Top-vs-Rest fails to stop early at k=8; it runs to k=10 (1000 tokens)
    res_rest = eval_family_2_beta_top_vs_rest([q], threshold=0.95)
    assert res_rest[0][1] == 1000.0


def test_permutation_replay_preserves_monotonicity(mock_pool):
    """Permutation replay across R=30 orders stabilizes estimates across seeds within MC error."""
    from experiments.offline_stopping_study import eval_rule_with_permutations

    # 1. Monotonicity across fixed k
    res_k1 = eval_rule_with_permutations(lambda p: eval_family_1_fixed_k(p, k=1), mock_pool, n_perms=10, seed=42)
    res_k5 = eval_rule_with_permutations(lambda p: eval_family_1_fixed_k(p, k=5), mock_pool, n_perms=10, seed=42)
    tok1 = np.mean([x[1] for x in res_k1])
    tok5 = np.mean([x[1] for x in res_k5])
    assert tok1 < tok5

    # 2. Stability of dynamic stopping rule across different permutation seeds (within 4 * SE_MC bound)
    res_seed1 = eval_rule_with_permutations(lambda p: eval_family_2_margin(p, m=2), mock_pool, n_perms=30, seed=42)
    res_seed2 = eval_rule_with_permutations(lambda p: eval_family_2_margin(p, m=2), mock_pool, n_perms=30, seed=999)

    d_acc = np.array([x[0] for x in res_seed1]) - np.array([x[0] for x in res_seed2])
    d_tok = np.array([x[1] for x in res_seed1]) - np.array([x[1] for x in res_seed2])

    se_mc_acc = float(np.std(d_acc, ddof=1) / np.sqrt(len(mock_pool)))
    se_mc_tok = float(np.std(d_tok, ddof=1) / np.sqrt(len(mock_pool)))

    diff_acc = abs(float(np.mean(d_acc)))
    diff_tok = abs(float(np.mean(d_tok)))

    assert diff_acc <= 4.0 * se_mc_acc, f"|diff_acc| {diff_acc:.5f} exceeds 4*SE_MC {4.0 * se_mc_acc:.5f}"
    assert diff_tok <= 4.0 * se_mc_tok, f"|diff_tok| {diff_tok:.3f} exceeds 4*SE_MC {4.0 * se_mc_tok:.3f}"


def test_load_question_pools_from_run11(tmp_path):
    """Test loader parses real or synthetic run11 trace correctly."""
    from experiments.offline_stopping_study import load_question_pools_from_run11

    # Test on real trace if present
    trace_file = "audit/run11_sweep_trace.jsonl"
    pools = load_question_pools_from_run11(trace_file)
    assert len(pools) == 100
    for p in pools:
        assert len(p.samples) == 5
        assert p.gold != ""
        assert all(s.tokens > 0 for s in p.samples)


def test_run_offline_stopping_study_smoke(tmp_path):
    """Smoke test for complete study runner exporting table and plot."""
    from experiments.offline_stopping_study import run_offline_stopping_study

    out_dir = str(tmp_path / "study_smoke")
    df, pareto, report = run_offline_stopping_study(
        trace_path="audit/run11_sweep_trace.jsonl",
        output_dir=out_dir,
        n_perms=2,  # Quick 2 perms for test speed
        seed=7,
    )
    assert not df.empty
    assert "is_pareto" in df.columns
    assert (tmp_path / "study_smoke" / "results.json").exists()
    assert (tmp_path / "study_smoke" / "stopping_pareto_curve.png").exists()
    assert (tmp_path / "study_smoke" / "README.md").exists()
    import json
    metadata = json.loads((tmp_path / "study_smoke" / "metadata.json").read_text())
    assert metadata["seed"] == 7 and metadata["held_out"] is False
    assert metadata["cost_scope"] == "equal_share_imputed_completion_token_proxy"
    assert metadata["per_candidate_tokens_observed"] is False
    assert "seed 7" in report and "seed ngẫu nhiên 42" not in report
    assert "0.4320" not in report.split("## Phạm vi diễn giải")[1]




