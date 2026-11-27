"""Generate publication-grade 3-panel figure for the EACL 2027 SRW 4-page short paper.

Reads raw results directly from:
  - audit/trace_dose_20261120/results.json (pre-registered H4)
  - audit/trace_dose_20261120/decomposition.json (post-hoc diagnostic decomposition)
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "audit" / "trace_dose_20261120" / "results.json"
DECOMP = ROOT / "audit" / "trace_dose_20261120" / "decomposition.json"
OUT = Path(__file__).resolve().parent / "fig_dose_response.pdf"


def main() -> None:
    data = json.loads(RESULTS.read_text())
    decomp = json.loads(DECOMP.read_text())
    desc = data["descriptive"]
    ratios = [0, 25, 50, 75, 100]

    s0_b1 = [100.0 * desc[f"s0_r{r}"]["follows_rate_B1"] for r in ratios]
    s1_b1 = [100.0 * desc[f"s1_r{r}"]["follows_rate_B1"] for r in ratios]
    pooled_b1 = [100.0 * data["descriptive_glmm_B1"]["pooled_by_ratio"][str(r)]["rate"] for r in ratios]

    bypass_rate = [100.0 * decomp["h4_pooled_by_ratio"][str(r)]["bypass_rate"] for r in ratios]
    derail_rate = [100.0 * decomp["h4_pooled_by_ratio"][str(r)]["derailed_rate"] for r in ratios]

    s0_acc = [100.0 * desc[f"s0_r{r}"]["accuracy"] / 500.0 for r in ratios]
    s1_acc = [100.0 * desc[f"s1_r{r}"]["accuracy"] / 500.0 for r in ratios]
    mean_acc = [(a + b) / 2.0 for a, b in zip(s0_acc, s1_acc)]

    s0_fmt = [100.0 * desc[f"s0_r{r}"]["format_valid"] / 500.0 for r in ratios]
    s1_fmt = [100.0 * desc[f"s1_r{r}"]["format_valid"] / 500.0 for r in ratios]
    mean_fmt = [(a + b) / 2.0 for a, b in zip(s0_fmt, s1_fmt)]

    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 8.2,
        "axes.labelsize": 8.2,
        "axes.titlesize": 8.6,
        "legend.fontsize": 7.2,
        "xtick.labelsize": 7.8,
        "ytick.labelsize": 7.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(6.5, 1.82), constrained_layout=True)

    # Panel A: Step-following rate (B1)
    ax1.plot(ratios, s0_b1, marker="o", ms=4.0, lw=1.1, ls="--", color="#2b6cb0", alpha=0.85, label="Seed 0")
    ax1.plot(ratios, s1_b1, marker="s", ms=4.0, lw=1.1, ls=":", color="#c53030", alpha=0.85, label="Seed 1")
    ax1.plot(ratios, pooled_b1, marker="D", ms=4.5, lw=1.9, color="#1a202c", label="Pooled (B1)")
    ax1.set_title("(a) Step Dependence (Primary B1)", pad=4)
    ax1.set_xlabel("Human Trace Fraction (%)")
    ax1.set_ylabel("Follows Edited Step (%)")
    ax1.set_xticks(ratios)
    ax1.set_ylim(75, 93)
    ax1.grid(axis="y", ls=":", alpha=0.4)
    ax1.legend(frameon=False, loc="lower left")
    ax1.text(
        0.97, 0.94,
        r"$b = -0.65,\ p = 0.0010$",
        transform=ax1.transAxes, ha="right", va="top", fontsize=7.0,
        bbox=dict(boxstyle="round,pad=0.22", fc="white", ec="#cbd5e0", lw=0.6),
    )

    # Panel B: Post-hoc Decomposition (Bypass vs Derailment)
    ax2.plot(ratios, derail_rate, marker="o", ms=4.6, lw=1.9, color="#dd6b20", label="Derailed after edit")
    ax2.plot(ratios, bypass_rate, marker="s", ms=4.3, lw=1.5, ls="--", color="#4a5568", label="Bypass / Revert")
    ax2.set_title("(b) Failure Mode (Post-Hoc)", pad=4)
    ax2.set_xlabel("Human Trace Fraction (%)")
    ax2.set_ylabel("Share of B1 Items (%)")
    ax2.set_xticks(ratios)
    ax2.set_ylim(0, 12.2)
    ax2.grid(axis="y", ls=":", alpha=0.4)
    ax2.legend(frameon=False, loc="upper left")
    ax2.text(
        0.97, 0.06,
        "Derail: $p = 0.0014$\nBypass: $p = 0.33$ (ns)",
        transform=ax2.transAxes, ha="right", va="bottom", fontsize=6.8,
        bbox=dict(boxstyle="round,pad=0.22", fc="white", ec="#cbd5e0", lw=0.6),
    )

    # Panel C: Accuracy & Format Validity
    ax3.plot(ratios, mean_acc, marker="o", ms=4.5, lw=1.8, color="#2f855a", label="Accuracy (mean)")
    ax3.fill_between(ratios, np.minimum(s0_acc, s1_acc), np.maximum(s0_acc, s1_acc), color="#2f855a", alpha=0.15)
    ax3.plot(ratios, mean_fmt, marker="^", ms=4.3, lw=1.5, ls="--", color="#718096", label="Format Valid (mean)")
    ax3.fill_between(ratios, np.minimum(s0_fmt, s1_fmt), np.maximum(s0_fmt, s1_fmt), color="#718096", alpha=0.12)
    ax3.set_title("(c) Clean Accuracy & Format", pad=4)
    ax3.set_xlabel("Human Trace Fraction (%)")
    ax3.set_ylabel("Rate on 500 Items (%)")
    ax3.set_xticks(ratios)
    ax3.set_ylim(57, 94)
    ax3.grid(axis="y", ls=":", alpha=0.4)
    ax3.legend(frameon=False, loc="upper right", ncol=1)

    fig.savefig(OUT, bbox_inches="tight")
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
