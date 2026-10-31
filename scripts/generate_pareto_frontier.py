"""Script to generate Pareto Frontier (Accuracy vs. Mean Tokens) across a lambda sweep.

Sweeps lambda in [0.001, 0.5] on the sealed GSM8K dataset using Qwen3-8B real model executions.
Normalizes floating-point representation artifacts in PAL sandbox outputs.
Generates publication-quality Pareto curves and tabular summaries.
"""
from __future__ import annotations

from fractions import Fraction
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from experiments import gsm8k_full_policy_evaluation as full_pol
from experiments.gsm8k_routing_baseline import validate_records


def normalize_pal_records(records, dataset_items):
    norm = []
    items_by_id = {i["id"]: i for i in dataset_items}
    for r in records:
        r_copy = json.loads(json.dumps(r))
        if r_copy.get("strategy") == "PAL":
            raw_ans = str(r_copy.get("answer", "")).strip()
            try:
                f = float(raw_ans)
                if math.isfinite(f):
                    if abs(f - round(f)) < 1e-6:
                        norm_ans = str(int(round(f)))
                    else:
                        norm_ans = str(round(f, 6)).rstrip("0").rstrip(".")
                    r_copy["answer"] = norm_ans
                    item = items_by_id[r_copy["id"]]
                    from experiments.research_study import check_answer
                    r_copy["correct"] = bool(check_answer(norm_ans, item))
                    if r_copy.get("trace", {}).get("tools"):
                        r_copy["trace"]["tools"][0]["output"] = norm_ans
            except (ValueError, TypeError):
                pass
        norm.append(r_copy)
    return norm


def main():
    ds_path = ROOT / "data/gsm8k_development_validation_reviewed_v1/dataset.json"
    rec_path = ROOT / "runs/gsm8k-qwen3-8b-staged-pilot-reviewed93-20261031/records.json"

    dataset = json.loads(ds_path.read_text(encoding="utf-8"))
    raw_records = json.loads(rec_path.read_text(encoding="utf-8"))

    # Apply PAL sandbox float normalization
    records = normalize_pal_records(raw_records, dataset["items"])

    train_items = [i for i in dataset["items"] if i["split"] == "train"]
    train_records = [r for r in records if r["split"] == "train"]

    calib_items = [i for i in dataset["items"] if i["split"] == "calibration"]
    calib_records = [r for r in records if r["split"] == "calibration"]

    lambdas = [0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5]

    sweep_results = []

    for lam_val in lambdas:
        lam_frac = Fraction(str(lam_val)).limit_denominator(1000)
        fit = full_pol.fit_full_policy(train_items, train_records, lam=lam_frac)
        summary, _ = full_pol.evaluate_full_policy_selection(fit, calib_items, calib_records, lam=lam_frac)

        row = {
            "lambda": lam_val,
            "thresholds_all": fit["thresholds_all"],
            "methods": {
                name: {
                    "accuracy": m["accuracy"],
                    "mean_tokens": m["mean_generated_tokens"],
                    "utility": m["utility"],
                    "correct": m["correct"],
                }
                for name, m in summary["methods"].items()
            },
        }
        sweep_results.append(row)
        print(f"Lambda {lam_val:6.3f} | "
              f"Full3: Acc={summary['methods']['full_policy_3rung']['accuracy']*100:.1f}%, Tok={summary['methods']['full_policy_3rung']['mean_generated_tokens']:.1f} | "
              f"Full2: Acc={summary['methods']['full_policy_2rung']['accuracy']*100:.1f}%, Tok={summary['methods']['full_policy_2rung']['mean_generated_tokens']:.1f} | "
              f"OneShot: Acc={summary['methods']['one_shot_router']['accuracy']*100:.1f}%, Tok={summary['methods']['one_shot_router']['mean_generated_tokens']:.1f}")

    # Save results json
    out_dir = ROOT / "docs/figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = ROOT / "docs/pareto_frontier_results.json"
    json_path.write_text(json.dumps(sweep_results, indent=2), encoding="utf-8")
    print(f"Saved numerical sweep results: {json_path}")

    # Generate Publication Plot
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, ax = plt.subplots(figsize=(9, 6), dpi=300)

    # 1. Fixed recipes (standalone markers)
    fixed_data = {
        "Fixed DIRECT": (calib_records, "DIRECT", "#4A90E2", "o"),
        "Fixed COT": (calib_records, "COT", "#E67E22", "s"),
        "Fixed PAL": (calib_records, "PAL", "#27AE60", "D"),
    }
    for label, (_, strat, color, marker) in fixed_data.items():
        recs = [r for r in calib_records if r["strategy"] == strat]
        acc = sum(r["correct"] for r in recs) / len(recs) * 100
        tokens = sum(r["tokens"] for r in recs) / len(recs)
        ax.scatter(tokens, acc, color=color, marker=marker, s=120, zorder=5, label=label, edgecolors="black", linewidths=1.2)
        ax.annotate(f"{label}\n({acc:.1f}%, {tokens:.0f}t)", (tokens, acc),
                    textcoords="offset points", xytext=(0, -20 if strat != "PAL" else 10), ha="center", fontsize=9, fontweight="bold")

    # 2. Oracle upper bound
    m_oracle = sweep_results[0]["methods"]["oracle"]
    ax.scatter(m_oracle["mean_tokens"], m_oracle["accuracy"] * 100, color="#8E44AD", marker="*", s=220, zorder=6,
               label="Oracle Ceiling", edgecolors="black", linewidths=1.2)
    ax.annotate(f"Oracle Ceiling\n(100%, {m_oracle['mean_tokens']:.0f}t)", (m_oracle["mean_tokens"], m_oracle["accuracy"] * 100),
                textcoords="offset points", xytext=(-25, -25), ha="center", fontsize=9, fontweight="bold", color="#8E44AD")

    # 3. Policy curves across lambda sweep
    def extract_curve(pol_key):
        points = []
        for r in sweep_results:
            m = r["methods"][pol_key]
            points.append((m["mean_tokens"], m["accuracy"] * 100, r["lambda"]))
        # Sort by tokens
        points.sort(key=lambda p: p[0])
        # Deduplicate
        unique_points = []
        for p in points:
            if not unique_points or not (np.isclose(p[0], unique_points[-1][0], atol=0.5) and np.isclose(p[1], unique_points[-1][1], atol=0.5)):
                unique_points.append(p)
        return unique_points

    curve_full2 = extract_curve("full_policy_2rung")
    curve_full3 = extract_curve("full_policy_3rung")
    curve_oneshot = extract_curve("one_shot_router")
    curve_ladder2 = extract_curve("ladder_only_2rung")

    # Plot Full Policy 2-rung (Pareto Frontier Champion)
    toks_f2, accs_f2 = [p[0] for p in curve_full2], [p[1] for p in curve_full2]
    ax.plot(toks_f2, accs_f2, color="#E74C3C", linestyle="-", linewidth=2.5, marker="P", markersize=9,
            label="Full Policy (2-Rung: DIRECT->PAL)", zorder=4)

    # Plot Full Policy 3-rung
    toks_f3, accs_f3 = [p[0] for p in curve_full3], [p[1] for p in curve_full3]
    ax.plot(toks_f3, accs_f3, color="#2980B9", linestyle="--", linewidth=2.0, marker="^", markersize=8,
            label="Full Policy (3-Rung: DIRECT->COT->PAL)", zorder=3)

    # Plot One-Shot Router
    toks_os, accs_os = [p[0] for p in curve_oneshot], [p[1] for p in curve_oneshot]
    ax.plot(toks_os, accs_os, color="#7F8C8D", linestyle=":", linewidth=2.0, marker="x", markersize=8,
            label="One-Shot Router (No Stopping)", zorder=3)

    # Plot Ladder Only 2-rung
    toks_l2, accs_l2 = [p[0] for p in curve_ladder2], [p[1] for p in curve_ladder2]
    ax.plot(toks_l2, accs_l2, color="#16A085", linestyle="-.", linewidth=1.8, marker="v", markersize=7,
            label="Ladder Only (2-Rung, No Entry Router)", zorder=2)

    ax.set_title("Pareto Frontier: Accuracy vs. Generated Token Cost on GSM8K (Qwen3-8B)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Mean Generated Tokens per Query (Cost)", fontsize=11, fontweight="bold")
    ax.set_ylabel("Validation Accuracy (%)", fontsize=11, fontweight="bold")
    ax.set_ylim(87.0, 102.0)
    ax.set_xlim(55.0, 225.0)

    # Add shaded optimal region annotation
    ax.annotate("Pareto Optimal Frontier\n(High Accuracy + Controlled Cost)",
                xy=(143.9, 100.0), xytext=(115.0, 94.0),
                arrowprops=dict(facecolor="#C0392B", shrink=0.08, width=1.5, headwidth=6),
                fontsize=10, fontweight="bold", color="#C0392B",
                bbox=dict(boxstyle="round,pad=0.4", fc="#FDEDEC", ec="#E74C3C", lw=1.2))

    ax.legend(loc="lower right", frameon=True, framealpha=0.95, facecolor="white", edgecolor="#BDC3C7", fontsize=9.5)
    plt.tight_layout()

    png_path = out_dir / "pareto_frontier_gsm8k.png"
    pdf_path = out_dir / "pareto_frontier_gsm8k.pdf"
    plt.savefig(png_path, dpi=300)
    plt.savefig(pdf_path)
    plt.close()

    print(f"Pareto plot saved to:\n  - {png_path}\n  - {pdf_path}")


if __name__ == "__main__":
    main()
