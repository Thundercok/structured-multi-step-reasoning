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

import argparse
import hashlib
from collections import Counter
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
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


# =============================================================================
# DATA LOADER & FULL OFFLINE EXPERIMENT RUNNER
# =============================================================================

def load_question_pools_from_run11(trace_path: str = "audit/run11_sweep_trace.jsonl") -> List[QuestionPool]:
    """Loads Self-Consistency (arm='SC') records from run11 sweep trace into QuestionPools."""
    pools = []
    with open(trace_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if d.get("arm") == "SC":
                cands = d.get("sc_candidates") or []
                if not cands:
                    continue
                gold = str(d.get("gold", "")).strip()
                comp_tokens = int(d.get("completion_tokens", 0))
                per_cand_tok = max(1, comp_tokens // len(cands))
                samples = [
                    SamplePoint(answer=str(c).strip(), tokens=per_cand_tok, correct=(str(c).strip() == gold))
                    for c in cands
                ]
                pools.append(QuestionPool(
                    id=str(d.get("id", "")),
                    query=str(d.get("raw_output", d.get("id", ""))),
                    gold=gold,
                    split="dev",
                    samples=samples,
                ))
    return pools


def plot_pareto_curve(df: pd.DataFrame, output_path: str) -> None:
    """Plots publication-quality Accuracy vs. Generated Tokens Pareto trade-off curve."""
    plt.figure(figsize=(9, 6), dpi=300)
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    # Color palette by family
    family_colors = {
        "Oracle": "#8e44ad",
        "Fixed-k": "#2980b9",
        "Margin": "#e67e22",
        "Beta-Top2": "#27ae60",
        "Beta-Rest": "#16a085",
        "ESC-Window": "#d35400",
    }
    family_markers = {
        "Oracle": "*",
        "Fixed-k": "o",
        "Margin": "s",
        "Beta-Top2": "^",
        "Beta-Rest": "v",
        "ESC-Window": "D",
    }

    # Plot empirical non-oracle points
    for family in df["family"].unique():
        fam_df = df[df["family"] == family]
        color = family_colors.get(family, "#7f8c8d")
        marker = family_markers.get(family, "o")
        size = 140 if family == "Oracle" else 75
        plt.scatter(
            fam_df["tokens"],
            fam_df["accuracy"],
            label=family,
            color=color,
            marker=marker,
            s=size,
            alpha=0.9,
            edgecolors="black",
            linewidth=0.6,
            zorder=3,
        )

    # Plot Pareto frontier line (for empirical non-oracle rules)
    non_oracle_pareto = df[(df["family"] != "Oracle") & (df["is_pareto"])].sort_values("tokens")
    if not non_oracle_pareto.empty:
        plt.plot(
            non_oracle_pareto["tokens"],
            non_oracle_pareto["accuracy"],
            linestyle="--",
            color="#2c3e50",
            linewidth=1.8,
            label="Empirical Pareto Frontier",
            zorder=2,
        )

    # Annotations for notable points
    for _, row in df.iterrows():
        rule_name = row["rule"]
        if row["is_pareto"] or rule_name in ["Oracle (Omniscient)", "Fixed-k=5", "Beta-Top2 (θ=0.80)", "ESC-Window (w=2)"]:
            offset_y = 0.0008 if rule_name != "Fixed-k=4" else -0.0012
            plt.annotate(
                rule_name,
                (row["tokens"], row["accuracy"]),
                textcoords="offset points",
                xytext=(0, 6 if offset_y > 0 else -12),
                ha="center",
                fontsize=8,
                weight="bold" if row["is_pareto"] else "normal",
                color="#2c3e50",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.7),
            )

    plt.xlabel("Imputed completion-token proxy per question", fontsize=11, fontweight="bold")
    plt.ylabel("Mean Accuracy (Majority Vote)", fontsize=11, fontweight="bold")
    plt.title("Offline Stopping Rules Evaluation & Pareto Frontier (Run 11 SC Sweep, R=30)", fontsize=12, fontweight="bold", pad=12)
    plt.legend(frameon=True, facecolor="white", edgecolor="#bdc3c7", loc="lower right", fontsize=9)
    plt.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path)
    plt.close()


def run_offline_stopping_study(
    trace_path: str = "audit/run11_sweep_trace.jsonl",
    output_dir: str = "audit/stopping_study_20261025",
    n_perms: int = 30,
    seed: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, str]:
    """Export exploratory historical replay with imputed costs and literal scoring.

    This loader does not provide valid general-task accuracy or measured online
    costs. Do not promote these diagnostics to held-out research conclusions.
    """
    pools = load_question_pools_from_run11(trace_path)
    if not pools:
        raise ValueError(f"No valid QuestionPools loaded from {trace_path}")

    # Build evaluation rules
    rules: List[Tuple[str, str, Callable[[List[QuestionPool]], List[Tuple[float, float]]]]] = []
    rules.append(("Oracle", "Oracle (Omniscient)", lambda p: eval_family_0_oracle(p)))
    for k in range(1, 6):
        rules.append(("Fixed-k", f"Fixed-k={k}", lambda p, k=k: eval_family_1_fixed_k(p, k=k)))
    for m in [1, 2, 3]:
        rules.append(("Margin", f"Margin-m={m}", lambda p, m=m: eval_family_2_margin(p, m=m)))
    for th in [0.70, 0.80, 0.85, 0.90, 0.95]:
        rules.append(("Beta-Top2", f"Beta-Top2 (θ={th:.2f})", lambda p, th=th: eval_family_2_adaptive_consistency(p, threshold=th)))
    for th in [0.70, 0.80, 0.85, 0.90, 0.95]:
        rules.append(("Beta-Rest", f"Beta-Rest (θ={th:.2f})", lambda p, th=th: eval_family_2_beta_top_vs_rest(p, threshold=th)))
    for w in [2, 3]:
        rules.append(("ESC-Window", f"ESC-Window (w={w})", lambda p, w=w: eval_family_2_esc_window(p, w=w)))

    # Evaluate all rules under permutation replay
    raw_evals: Dict[str, List[Tuple[float, float]]] = {}
    for family, name, fn in rules:
        raw_evals[name] = eval_rule_with_permutations(fn, pools, n_perms=n_perms, seed=seed)

    ref_name = "Fixed-k=5"
    ref_res = raw_evals[ref_name]
    ref_tok = float(np.mean([x[1] for x in ref_res]))

    rng = np.random.default_rng(seed)
    N = len(pools)
    boot_indices = rng.integers(0, N, size=(2000, N))

    rows = []
    for family, name, fn in rules:
        res = raw_evals[name]
        acc_arr = np.array([x[0] for x in res])
        tok_arr = np.array([x[1] for x in res])
        mean_acc = float(acc_arr.mean())
        mean_tok = float(tok_arr.mean())

        boot_acc = acc_arr[boot_indices].mean(axis=1)
        boot_tok = tok_arr[boot_indices].mean(axis=1)
        ci95_acc = (float(np.percentile(boot_acc, 2.5)), float(np.percentile(boot_acc, 97.5)))
        ci95_tok = (float(np.percentile(boot_tok, 2.5)), float(np.percentile(boot_tok, 97.5)))

        diff_dict = paired_bootstrap_diff(res, ref_res, n_boot=2000, seed=seed)
        savings_pct = (1.0 - mean_tok / ref_tok) * 100.0

        rows.append({
            "family": family,
            "rule": name,
            "accuracy": mean_acc,
            "ci95_acc_low": ci95_acc[0],
            "ci95_acc_high": ci95_acc[1],
            "tokens": mean_tok,
            "ci95_tok_low": ci95_tok[0],
            "ci95_tok_high": ci95_tok[1],
            "delta_acc": diff_dict["mean_diff_acc"],
            "ci95_delta_acc_low": diff_dict["ci95_diff_acc"][0],
            "ci95_delta_acc_high": diff_dict["ci95_diff_acc"][1],
            "delta_tok": diff_dict["mean_diff_tok"],
            "ci95_delta_tok_low": diff_dict["ci95_diff_tok"][0],
            "ci95_delta_tok_high": diff_dict["ci95_diff_tok"][1],
            "savings_pct": savings_pct,
        })

    df = pd.DataFrame(rows)

    # Determine empirical Pareto frontier (excluding oracle)
    non_oracle_df = df[df["family"] != "Oracle"].copy()
    pareto_empirical = compute_pareto_frontier(non_oracle_df)
    pareto_rules = set(pareto_empirical["rule"])
    df["is_pareto"] = df["rule"].apply(lambda r: r in pareto_rules)

    # Export paths
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    plot_path = str(out_dir / "stopping_pareto_curve.png")
    plot_pareto_curve(df, plot_path)

    # Export JSON
    json_path = str(out_dir / "results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(df.to_dict(orient="records"), f, indent=2)

    # Generate Markdown Report
    lines = [
        "# Báo cáo Thực nghiệm Offline Stopping Rules & Phân tích Đánh đổi Pareto",
        "",
        f"- **Tập dữ liệu nguồn:** `{trace_path}` ({len(pools)} câu hỏi, development đã lộ, cánh Self-Consistency)",
        f"- **Số lượt hoán vị ngẫu nhiên ($R$):** {n_perms}",
        f"- **Phương pháp tái lập:** Paired Bootstrap CI 95% ($B=2.000$ draws), seed {seed}",
        "- **Giới hạn:** chi phí proxy chia đều completion tokens cho từng candidate; không phải số đo per-call hoặc full inference cost.",
        "- **Scoring:** literal string equality; chưa xử lý tương đương đáp án (đặc biệt Game24). Không dùng accuracy này làm kết luận nghiên cứu.",
        "- **Replay:** hoán vị lại cùng các đầu ra; không đo online latency, không tăng số câu độc lập; Stage 0 không đổi.",
        f"- **Biểu đồ Pareto:** Lưu tại `stopping_pareto_curve.png`",
        "",
        "## Bảng Kết quả Chi tiết",
        "",
        "| Họ (Family) | Quy tắc Dừng (Rule) | Accuracy (95% CI) | Tokens (95% CI) | Δ Acc vs k=5 | Δ Tokens vs k=5 | Tiết kiệm (%) | Pareto? |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :---: | :---: |",
    ]
    for _, r in df.iterrows():
        acc_str = f"{r['accuracy']:.4f} [{r['ci95_acc_low']:.4f}, {r['ci95_acc_high']:.4f}]"
        tok_str = f"{r['tokens']:.1f} [{r['ci95_tok_low']:.1f}, {r['ci95_tok_high']:.1f}]"
        d_acc_str = f"{r['delta_acc']:+.4f} [{r['ci95_delta_acc_low']:+.4f}, {r['ci95_delta_acc_high']:+.4f}]"
        d_tok_str = f"{r['delta_tok']:+.1f} [{r['ci95_delta_tok_low']:+.1f}, {r['ci95_delta_tok_high']:+.1f}]"
        pareto_str = "**CÓ**" if r["is_pareto"] else "Không"
        lines.append(
            f"| {r['family']} | {r['rule']} | {acc_str} | {tok_str} | {d_acc_str} | {d_tok_str} | {r['savings_pct']:.1f}% | {pareto_str} |"
        )

    lines.extend([
        "", "## Phạm vi diễn giải",
        "Bảng trên mô tả replay với scoring literal và chi phí nội suy. Không có kết luận tương đương, noninferiority hoặc cải thiện chất lượng được xác nhận.",
        "Fixed-k=3 có chi phí proxy bằng 3/5 fixed-k=5 do giả định chia đều chi phí; không phải bằng chứng tiết kiệm inference thực tế.",
        "Oracle dùng gold và không triển khai được. CI không bao phủ lỗi scoring, sai lệch nguồn hoặc giả định chi phí.",
    ])
    metadata = {
        "evidence_kind": "exploratory_replay_diagnostic", "held_out": False,
        "trace_sha256": hashlib.sha256(Path(trace_path).read_bytes()).hexdigest(),
        "question_count": len(pools), "permutations": n_perms, "seed": seed,
        "scoring": "literal_string_equality_not_validated_for_general_task_correctness",
        "cost_scope": "equal_share_imputed_completion_token_proxy",
        "per_candidate_tokens_observed": False, "prompt_cost_included": False,
        "online_latency_measured": False, "stage0_changed": False,
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    report_md = "\n".join(lines)
    readme_path = str(out_dir / "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    return df, pareto_empirical, report_md


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline evaluation of stopping rules for Multi-step Reasoning.")
    parser.add_argument("--trace", type=str, default="audit/run11_sweep_trace.jsonl", help="Path to sweep trace JSONL.")
    parser.add_argument("--output-dir", type=str, default="audit/stopping_study_20261025", help="Output directory.")
    parser.add_argument("--perms", type=int, default=30, help="Number of random permutations.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    args = parser.parse_args()

    print(f"Running offline stopping study on {args.trace}...")
    df, pareto, report = run_offline_stopping_study(
        trace_path=args.trace,
        output_dir=args.output_dir,
        n_perms=args.perms,
        seed=args.seed,
    )
    print("\nStudy completed successfully!")
    print(f"Results written to: {args.output_dir}")
    print("\nEmpirical Pareto Frontier:")
    print(pareto[["rule", "accuracy", "tokens", "savings_pct"]].to_string(index=False))


if __name__ == "__main__":
    main()
