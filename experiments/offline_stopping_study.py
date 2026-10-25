"""
Offline evaluation of stopping rules for Multi-step Reasoning / Self-Consistency.

Baselines implemented:
- Family 0 (Oracle): Omniscient upper bound (stops at earliest k where winner is correct, else k=1).
- Family 1 (Fixed-k): Standard SC at fixed k in {1, ..., K}.
- Family 2a (Margin): Stops when (n1 - n2) >= m, m in {1, 2, ..., K}.
- Family 2b (Adaptive-Consistency / Beta): Beta distribution stopping rule (Aggarwal et al., EMNLP 2023).
- Family 2c (ESC / Window): Consecutive window consensus w in {2, 3, 4} (Li et al., ICLR 2024).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy.special import betainc


@dataclass(frozen=True)
class SamplePoint:
    answer: str
    tokens: int
    correct: bool


@dataclass(frozen=True)
class QuestionPool:
    id: str
    query: str
    gold: str
    split: str
    samples: List[SamplePoint]  # length K


# =============================================================================
# SHARED TIE-BREAK & VOTING UTILITY
# =============================================================================

def majority_winner(sub_samples: List[SamplePoint]) -> str:
    """Computes the majority winner with deterministic first-seen tie-breaking."""
    counts: Dict[str, int] = {}
    first_seen: Dict[str, int] = {}
    for idx, s in enumerate(sub_samples):
        if s.answer not in first_seen:
            first_seen[s.answer] = idx
        counts[s.answer] = counts.get(s.answer, 0) + 1
    # Max by count; on tie, min by first_seen index (earlier seen wins)
    return max(counts.keys(), key=lambda ans: (counts[ans], -first_seen[ans]))


def get_top2_counts(sub_samples: List[SamplePoint]) -> Tuple[int, int]:
    """Returns (n1, n2) counts from sub_samples."""
    counts = Counter(s.answer for s in sub_samples)
    top = counts.most_common(2)
    n1 = top[0][1] if len(top) > 0 else 0
    n2 = top[1][1] if len(top) > 1 else 0
    return n1, n2


# =============================================================================
# STOPPING RULES EVALUATION
# =============================================================================

def eval_family_0_oracle(pool: List[QuestionPool]) -> List[Tuple[float, float]]:
    """Family 0: Omniscient Oracle.
    Stops at earliest k in [1, K] where majority winner is correct; if never correct, stops at k=1.
    """
    results = []
    for q in pool:
        earliest_k = None
        for k in range(1, len(q.samples) + 1):
            winner = majority_winner(q.samples[:k])
            if winner == q.gold:
                earliest_k = k
                break
        stop_k = earliest_k if earliest_k is not None else 1
        winner_final = majority_winner(q.samples[:stop_k])
        acc = 1.0 if winner_final == q.gold else 0.0
        tok = sum(s.tokens for s in q.samples[:stop_k])
        results.append((acc, float(tok)))
    return results


def eval_family_1_fixed_k(pool: List[QuestionPool], k: int) -> List[Tuple[float, float]]:
    """Family 1: Fixed k samples."""
    results = []
    for q in pool:
        assert 1 <= k <= len(q.samples), f"k={k} out of range [1, {len(q.samples)}]"
        sub = q.samples[:k]
        winner = majority_winner(sub)
        acc = 1.0 if winner == q.gold else 0.0
        tok = sum(s.tokens for s in sub)
        results.append((acc, float(tok)))
    return results


def eval_family_2_margin(pool: List[QuestionPool], m: int) -> List[Tuple[float, float]]:
    """Family 2a: Margin stopping (n1 - n2 >= m)."""
    results = []
    for q in pool:
        assert m >= 1, "Margin m must be >= 1"
        stop_k = len(q.samples)
        for k in range(1, len(q.samples) + 1):
            n1, n2 = get_top2_counts(q.samples[:k])
            if (n1 - n2) >= m or k == len(q.samples):
                stop_k = k
                break
        sub = q.samples[:stop_k]
        winner = majority_winner(sub)
        acc = 1.0 if winner == q.gold else 0.0
        tok = sum(s.tokens for s in sub)
        results.append((acc, float(tok)))
    return results


def eval_family_2_esc_window(pool: List[QuestionPool], w: int) -> List[Tuple[float, float]]:
    """Family 2c: Early-Stopping Self-Consistency (Li et al., ICLR 2024).
    Stops when the last w consecutive samples produce identical answers.
    Requires w >= 2 and k >= w.
    """
    results = []
    for q in pool:
        assert w >= 2, "ESC window size w must be >= 2 to prevent degeneracy"
        assert w <= len(q.samples), f"w={w} exceeds pool size {len(q.samples)}"
        stop_k = len(q.samples)
        for k in range(w, len(q.samples) + 1):
            window_answers = [q.samples[i].answer for i in range(k - w, k)]
            if len(set(window_answers)) == 1 or k == len(q.samples):
                stop_k = k
                break
        sub = q.samples[:stop_k]
        winner = majority_winner(sub)
        acc = 1.0 if winner == q.gold else 0.0
        tok = sum(s.tokens for s in sub)
        results.append((acc, float(tok)))
    return results


def compute_beta_top2_prob(n1: int, n2: int, alpha: float = 1.0, beta: float = 1.0) -> float:
    """Computes P(p1 > 0.5) under Beta(n1 + alpha, n2 + beta) for Top-1 vs Top-2."""
    return float(1.0 - betainc(n1 + alpha, n2 + beta, 0.5))


def compute_beta_rest_prob(n1: int, k: int, alpha: float = 1.0, beta: float = 1.0) -> float:
    """Computes P(p1 > 0.5) under Beta(n1 + alpha, (k - n1) + beta) for Top-1 vs Rest."""
    return float(1.0 - betainc(n1 + alpha, (k - n1) + beta, 0.5))


def eval_family_2_adaptive_consistency(
    pool: List[QuestionPool], threshold: float = 0.95, alpha: float = 1.0, beta: float = 1.0
) -> List[Tuple[float, float]]:
    """Family 2b: Adaptive-Consistency (Aggarwal et al., EMNLP 2023).
    Beta distribution stopping rule: Top-1 vs Top-2 comparison.
    Models p1 / (p1 + p2) ~ Beta(n1 + alpha, n2 + beta).
    Stops when P(p1 > 0.5) = 1 - I_0.5(n1 + alpha, n2 + beta) >= threshold or k == K.
    """
    results = []
    for q in pool:
        stop_k = len(q.samples)
        for k in range(1, len(q.samples) + 1):
            n1, n2 = get_top2_counts(q.samples[:k])
            prob_majority = compute_beta_top2_prob(n1, n2, alpha=alpha, beta=beta)
            if prob_majority >= threshold or k == len(q.samples):
                stop_k = k
                break
        sub = q.samples[:stop_k]
        winner = majority_winner(sub)
        acc = 1.0 if winner == q.gold else 0.0
        tok = sum(s.tokens for s in q.samples[:stop_k])
        results.append((acc, float(tok)))
    return results


def eval_family_2_beta_top_vs_rest(
    pool: List[QuestionPool], threshold: float = 0.95, alpha: float = 1.0, beta: float = 1.0
) -> List[Tuple[float, float]]:
    """Ablation: Beta stopping rule using Top-1 vs Rest (all other candidates pooled).
    Models p1 ~ Beta(n1 + alpha, (k - n1) + beta).
    Stops when P(p1 > 0.5) = 1 - I_0.5(n1 + alpha, (k - n1) + beta) >= threshold or k == K.
    """
    results = []
    for q in pool:
        stop_k = len(q.samples)
        for k in range(1, len(q.samples) + 1):
            n1, _ = get_top2_counts(q.samples[:k])
            prob_majority = compute_beta_rest_prob(n1, k, alpha=alpha, beta=beta)
            if prob_majority >= threshold or k == len(q.samples):
                stop_k = k
                break
        sub = q.samples[:stop_k]
        winner = majority_winner(sub)
        acc = 1.0 if winner == q.gold else 0.0
        tok = sum(s.tokens for s in q.samples[:stop_k])
        results.append((acc, float(tok)))
    return results


def eval_rule_with_permutations(
    eval_fn: Callable[[List[QuestionPool]], List[Tuple[float, float]]],
    pool: List[QuestionPool],
    n_perms: int = 30,
    seed: int = 42,
) -> List[Tuple[float, float]]:
    """Evaluates an offline stopping rule over R random permutations of the K samples.
    Averages (acc, tokens) per question to eliminate sample ordering bias.
    Bootstrap across questions is performed downstream on these per-question averages.
    """
    rng = np.random.default_rng(seed)
    N = len(pool)
    acc_matrix = np.zeros((N, n_perms))
    tok_matrix = np.zeros((N, n_perms))

    for r in range(n_perms):
        permuted_pool = []
        for q in pool:
            perm_indices = rng.permutation(len(q.samples))
            perm_samples = [q.samples[idx] for idx in perm_indices]
            permuted_pool.append(
                QuestionPool(id=q.id, query=q.query, gold=q.gold, split=q.split, samples=perm_samples)
            )
        res_r = eval_fn(permuted_pool)
        for i, (acc, tok) in enumerate(res_r):
            acc_matrix[i, r] = acc
            tok_matrix[i, r] = tok

    mean_acc_per_q = acc_matrix.mean(axis=1)
    mean_tok_per_q = tok_matrix.mean(axis=1)
    return [(float(mean_acc_per_q[i]), float(mean_tok_per_q[i])) for i in range(N)]


# =============================================================================
# STATISTICAL METRICS: PAIRED BOOTSTRAP & PARETO FRONTIER
# =============================================================================

def paired_bootstrap_diff(
    res_a: List[Tuple[float, float]],
    res_b: List[Tuple[float, float]],
    n_boot: int = 2000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Question-paired bootstrap difference between Method A and Method B.
    Computes Delta = Metric(A) - Metric(B) on identical resampled question indices.
    """
    assert len(res_a) == len(res_b)
    N = len(res_a)
    rng = np.random.default_rng(seed)

    acc_a = np.array([x[0] for x in res_a])
    acc_b = np.array([x[0] for x in res_b])
    tok_a = np.array([x[1] for x in res_a])
    tok_b = np.array([x[1] for x in res_b])

    d_acc = acc_a - acc_b
    d_tok = tok_a - tok_b

    boot_indices = rng.integers(0, N, size=(n_boot, N))
    boot_d_acc = d_acc[boot_indices].mean(axis=1)
    boot_d_tok = d_tok[boot_indices].mean(axis=1)

    return {
        "mean_diff_acc": float(d_acc.mean()),
        "ci95_diff_acc": (float(np.percentile(boot_d_acc, 2.5)), float(np.percentile(boot_d_acc, 97.5))),
        "mean_diff_tok": float(d_tok.mean()),
        "ci95_diff_tok": (float(np.percentile(boot_d_tok, 2.5)), float(np.percentile(boot_d_tok, 97.5))),
    }


def compute_pareto_frontier(df: pd.DataFrame) -> pd.DataFrame:
    """Filter rows that are Pareto-optimal (maximizing accuracy while minimizing tokens)."""
    sorted_df = df.sort_values(by=["tokens", "accuracy"], ascending=[True, False])
    frontier = []
    max_acc = -1.0
    for _, row in sorted_df.iterrows():
        if row["accuracy"] > max_acc:
            frontier.append(row)
            max_acc = row["accuracy"]
    return pd.DataFrame(frontier)
