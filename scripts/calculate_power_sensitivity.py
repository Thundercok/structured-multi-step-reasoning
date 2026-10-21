"""Calculate statistical power sensitivity for paired binary evaluations (McNemar test).

Evaluates power across sample sizes N in [30..150] and effect sizes delta in [0.05..0.25]
under explicit, reproducible paired outcome assumptions.
Outputs audit/rat_cot_runtime_acceptance_20261020/power_sensitivity.json.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "audit/rat_cot_runtime_acceptance_20261020/power_sensitivity.json"


def calculate_mcnemar_power(
    n: int,
    delta: float,
    *,
    p_disc_ratio: float = 0.30,
    alpha: float = 0.05,
    two_sided: bool = True,
) -> float:
    """Calculate asymptotic power for McNemar paired test of proportions.

    Args:
        n: Number of paired items (e.g. groups).
        delta: True difference in proportions (p10 - p01).
        p_disc_ratio: Proportion of discordant pairs (p10 + p01).
        alpha: Significance level.
        two_sided: Whether test is two-sided.

    Returns:
        Statistical power in [0.0, 1.0].
    """
    if delta <= 0:
        return alpha if two_sided else alpha / 2.0
    p_disc = max(p_disc_ratio, abs(delta))
    z_alpha = stats.norm.ppf(1.0 - alpha / 2.0 if two_sided else 1.0 - alpha)
    # Variance under alternative hypothesis:
    # Z = (sqrt(N) * delta - z_alpha * sqrt(p_disc)) / sqrt(p_disc)
    # Standard normal approximation for McNemar test:
    effect = np.sqrt(n) * delta / np.sqrt(p_disc)
    power = stats.norm.cdf(effect - z_alpha)
    return float(np.clip(power, 0.0, 1.0))


def find_mde(
    n: int,
    target_power: float = 0.80,
    *,
    p_disc_ratio: float = 0.30,
    alpha: float = 0.05,
    two_sided: bool = True,
) -> float:
    """Find minimum detectable effect (MDE) for given N and target power."""
    low, high = 0.001, 0.999
    for _ in range(50):
        mid = (low + high) / 2.0
        p = calculate_mcnemar_power(n, mid, p_disc_ratio=p_disc_ratio, alpha=alpha, two_sided=two_sided)
        if p >= target_power:
            high = mid
        else:
            low = mid
    return float(round((low + high) / 2.0, 4))


def find_required_n(
    delta: float,
    target_power: float = 0.80,
    *,
    p_disc_ratio: float = 0.30,
    alpha: float = 0.05,
    two_sided: bool = True,
) -> int:
    """Find minimum integer sample size N to achieve target power."""
    for n in range(1, 10000):
        if calculate_mcnemar_power(n, delta, p_disc_ratio=p_disc_ratio, alpha=alpha, two_sided=two_sided) >= target_power:
            return n
    return 10000


def main():
    sample_sizes = [30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150]
    effect_sizes = [0.05, 0.08, 0.10, 0.12, 0.14, 0.15, 0.18, 0.20, 0.25]
    discordant_scenarios = {
        "low_discordance_0.20": 0.20,
        "standard_discordance_0.30": 0.30,
        "high_discordance_0.40": 0.40,
    }

    grid = {}
    for sc_name, p_disc in discordant_scenarios.items():
        power_table = {}
        for n in sample_sizes:
            power_table[str(n)] = {
                f"{delta:.2f}": round(calculate_mcnemar_power(n, delta, p_disc_ratio=p_disc), 4)
                for delta in effect_sizes
            }
        mde_table = {str(n): find_mde(n, target_power=0.80, p_disc_ratio=p_disc) for n in sample_sizes}
        grid[sc_name] = {
            "p_discordant_assumed": p_disc,
            "power_by_n_and_delta": power_table,
            "mde_at_80_percent_power": mde_table,
        }

    # Focus analysis on N=70 candidate pool
    n70_standard = grid["standard_discordance_0.30"]
    result = {
        "metadata": {
            "test_type": "McNemar paired binary test (two-sided alpha = 0.05)",
            "purpose": "Statistical power sensitivity across candidate sample sizes and effect margins",
            "candidate_n": 70,
            "note": "Planning proposal; not pre-registered execution approval.",
        },
        "target_pool_n70_summary": {
            "candidate_groups_n": 70,
            "assumed_p_discordant": 0.30,
            "mde_at_80pct_power": n70_standard["mde_at_80_percent_power"]["70"],
            "power_at_delta_0.05": n70_standard["power_by_n_and_delta"]["70"]["0.05"],
            "power_at_delta_0.10": n70_standard["power_by_n_and_delta"]["70"]["0.10"],
            "power_at_delta_0.15": n70_standard["power_by_n_and_delta"]["70"]["0.15"],
            "power_at_delta_0.20": n70_standard["power_by_n_and_delta"]["70"]["0.20"],
            "sample_size_needed_for_delta_0.10_at_80pct_power": find_required_n(0.10, 0.80, p_disc_ratio=0.30),
            "sample_size_needed_for_delta_0.05_at_80pct_power": find_required_n(0.05, 0.80, p_disc_ratio=0.30),
        },
        "scenarios": grid,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Saved power sensitivity profile to {OUTPUT_PATH}")
    print(f"N=70 MDE at 80% power (p_disc=0.30): {result['target_pool_n70_summary']['mde_at_80pct_power']}")
    print(f"N=70 Power at delta=0.10: {result['target_pool_n70_summary']['power_at_delta_0.10']:.2%}")
    print(f"N=70 Power at delta=0.15: {result['target_pool_n70_summary']['power_at_delta_0.15']:.2%}")


if __name__ == "__main__":
    main()
