"""Preregistered analysis for docs/trace_dose_prereg.md: trace-source mixing dose response.

Amendment 2026-11-23 (docs/trace_dose_prereg_amendment_20261123.md), applied by analyze_run:
  - Primary H4 is `adapter_level_test` (10 adapter logits, OLS, t-test with 7 df), not the GLMM LRT below.
  - Primary metric (B1) counts only planned interventions whose expected answer is known.
  - Every GLMM below is reported as descriptive only.
The text that follows describes the original registered GLMM.

Fits a 1D random-intercept logistic regression (Gauss-Hermite quadrature, 21 nodes):
    logit P(follows_ij = 1 | u_i) = beta_0 + beta_human * x_ij + beta_seed * s_ij + sigma * u_i
where i indexes question, x_ij is exact human fraction k/229 in {0, 57/229, 114/229, 172/229, 1},
s_ij in {0, 1} is seed, and u_i ~ N(0, 1).

Primary test (H4): two-sided Likelihood Ratio Test (1 df) of H0: beta_human = 0 at alpha = 0.05.
Secondary diagnostics:
  - Linearity vs 5-level categorical LRT (3 df) to distinguish monotonic slope from a binary step.
  - Sensitivity GLMM restricted to questions planned in all 10 runs (no selection bias across ratios).
  - Per-seed GLMMs (seed 0 and seed 1 separately).
  - Fresh H3 replication: exact two-sided McNemar on 0% vs 100% (per seed) and 25% vs 75%.
  - Full descriptive metrics (planned, follows, accuracy + Wilson 95% CI, format_valid, truncated, taxonomy).

Usage: analyze.py [RUN_DIR]   (default: this folder)
"""

from collections import Counter, defaultdict
import importlib.util
import json
import math
from pathlib import Path
import sys

import numpy as np
from numpy.polynomial.hermite import hermgauss
from scipy import optimize, special, stats

HERE = Path(__file__).parent
AUDIT = HERE.parent
ALPHA = 0.05
RATIOS = (0, 25, 50, 75, 100)
SEEDS = (0, 1)
N_TRAIN = 229
HUMAN_COUNTS = {0: 0, 25: 57, 50: 114, 75: 172, 100: 229}
GH_NODES, GH_WEIGHTS = hermgauss(21)
GH_U = math.sqrt(2.0) * GH_NODES
GH_LOG_W = np.log(GH_WEIGHTS / math.sqrt(math.pi))


def _load_sealed():
    spec = importlib.util.spec_from_file_location("sealed", AUDIT / "gsm8k_sealed_test_20261111/analyze.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _follows(record):
    return record["outcome"] == "follows"


def _planned_rows(ints, seed, pct):
    """One row per planned intervention. `expected_known` is False for flagged original traces
    (wrong Calc, or answer not from the last Calc): plan_intervention sets expected=None and
    `follows` is unreachable there. Amendment 2026-11-23 (B1) keeps only expected_known rows."""
    frac = HUMAN_COUNTS[pct] / N_TRAIN
    return [{
        "id": qid,
        "seed": seed,
        "ratio": pct,
        "human_frac": frac,
        "follows": _follows(rec),
        "expected_known": rec["expected"] is not None,
    } for qid, rec in ints.items()]


def adapter_level_test(rows):
    """Amendment 2026-11-23 (A): one logit per (seed, ratio) adapter, OLS on human_frac + seed,
    two-sided t-test on the human_frac slope. Training-run noise then enters the residual
    instead of being read as dose effect (the question-only GLMM rejects too often under it)."""
    counts = defaultdict(lambda: [0, 0])
    for r in rows:
        c = counts[(r["seed"], r["ratio"])]
        c[0] += 1
        c[1] += r["follows"]
    cells = sorted(counts)
    X = np.array([[1.0, HUMAN_COUNTS[pct] / N_TRAIN, float(s)] for s, pct in cells])
    y = np.array([special.logit((counts[c][1] + 0.5) / (counts[c][0] + 1.0)) for c in cells])
    dof = len(y) - X.shape[1]
    if dof < 1:
        raise ValueError(f"adapter-level test needs more than 3 cells, got {len(y)}")
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    s2 = float(np.sum((y - X @ b) ** 2)) / dof
    se = math.sqrt(s2 * float(np.linalg.inv(X.T @ X)[1, 1]))
    t = float(b[1]) / se if se > 0 else math.copysign(math.inf, float(b[1]))
    level_means = {
        str(pct): round(float(np.mean([y[i] for i, (_, p) in enumerate(cells) if p == pct])), 6)
        for pct in sorted({p for _, p in cells})
    }
    return {
        "n_cells": len(cells),
        "df": dof,
        "b_human": round(float(b[1]), 6),
        "b_seed": round(float(b[2]), 6),
        "se_human": round(se, 6),
        "t": round(t, 6),
        "p": float(2 * stats.t.sf(abs(t), dof)),
        "cells": {f"s{s}_r{pct}": {"n": counts[(s, pct)][0], "follows": counts[(s, pct)][1],
                                   "logit": round(float(y[i]), 6)}
                  for i, (s, pct) in enumerate(cells)},
        "level_mean_logit": level_means,
    }


def _reading(p, slope):
    if p >= ALPHA:
        return "not distinguishable"
    if slope < 0:
        return "dose-response supported; higher human-trace fraction lowers step-following"
    return "opposite direction; higher human-trace fraction raises step-following"


def _common_to_all_cells(rows):
    by_cell = defaultdict(set)
    for r in rows:
        by_cell[(r["seed"], r["ratio"])].add(r["id"])
    if len(by_cell) < len(SEEDS) * len(RATIOS):
        return []
    common = set.intersection(*by_cell.values())
    return [r for r in rows if r["id"] in common]


def amended_statistics(rows):
    """Amendment 2026-11-23: primary H4 = adapter-level test on B1 rows (expected known).
    Every GLMM is descriptive only; its p-values may be too small."""
    b1 = [r for r in rows if r["expected_known"]]
    primary = adapter_level_test(b1)
    common = _common_to_all_cells(b1)
    return {
        "amendment": "docs/trace_dose_prereg_amendment_20261123.md",
        "H4_primary_adapter_level": primary,
        "reading": _reading(primary["p"], primary["b_human"]),
        "sensitivity_common_to_all_cells_adapter_level": adapter_level_test(common) if common else None,
        "secondary_original_metric_adapter_level": adapter_level_test(rows),
        "descriptive_glmm_B1": run_dose_statistics(b1),
        "descriptive_glmm_original_metric": run_dose_statistics(rows),
    }


def _group_by_question(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[r["id"]].append(r)
    return list(groups.values())


def _design_arrays(grouped, design_fn):
    """Pre-pack (X_i, y_i) arrays per question for fast vectorized quadrature."""
    packed = []
    for grp in grouped:
        X = np.asarray([design_fn(r) for r in grp], dtype=np.float64)
        y = np.asarray([1.0 if r["follows"] else 0.0 for r in grp], dtype=np.float64)
        packed.append((X, y))
    return packed


def _neg_loglik_glmm(params, packed):
    beta = params[:-1]
    sigma = math.exp(float(np.clip(params[-1], -10.0, 4.0)))
    total_ll = 0.0
    for X, y in packed:
        # eta shape: (n_obs_i, n_quad)
        eta = (X @ beta)[:, None] + sigma * GH_U[None, :]
        # Bernoulli log-likelihood: sum_j [y_j * eta - softplus(eta)]
        ll_obs = np.sum(y[:, None] * eta - np.logaddexp(0.0, eta), axis=0)
        total_ll += float(special.logsumexp(GH_LOG_W + ll_obs))
    return -total_ll


def fit_glmm_lrt(rows, full_design_fn, null_design_fn, df=1):
    """Fit full and nested null 1D random-intercept logistic GLMMs and compute LRT."""
    if not rows:
        raise ValueError("cannot fit GLMM on empty rows")
    grouped = _group_by_question(rows)
    packed_full = _design_arrays(grouped, full_design_fn)
    packed_null = _design_arrays(grouped, null_design_fn)

    p_full = packed_full[0][0].shape[1]
    p_null = packed_null[0][0].shape[1]
    p_bar = np.clip(np.mean([1.0 if r["follows"] else 0.0 for r in rows]), 1e-3, 1 - 1e-3)
    b0_init = float(special.logit(p_bar))

    def _fit(packed, p_dim):
        init = np.zeros(p_dim + 1, dtype=np.float64)
        init[0] = b0_init
        init[-1] = 0.0  # sigma = 1.0
        bounds = [(-25.0, 25.0)] * p_dim + [(-10.0, 4.0)]
        best = None
        for log_sig in (-1.0, 0.0, 1.0):
            x0 = init.copy()
            x0[-1] = log_sig
            res = optimize.minimize(_neg_loglik_glmm, x0, args=(packed,), method="L-BFGS-B", bounds=bounds)
            if best is None or res.fun < best.fun:
                best = res
        return best

    res_null = _fit(packed_null, p_null)
    res_full = _fit(packed_full, p_full)
    ll_null = -float(res_null.fun)
    ll_full = -float(res_full.fun)
    lrt = max(0.0, 2.0 * (ll_full - ll_null))
    p_val = float(stats.chi2.sf(lrt, df=df))

    return {
        "n_obs": len(rows),
        "n_questions": len(grouped),
        "full_params": [round(float(v), 6) for v in res_full.x[:-1]],
        "full_sigma": round(math.exp(float(res_full.x[-1])), 6),
        "full_loglik": round(ll_full, 6),
        "null_loglik": round(ll_null, 6),
        "lrt_stat": round(lrt, 6),
        "df": df,
        "p": p_val,
        "converged": bool(res_full.success and res_null.success),
    }


def run_dose_statistics(rows):
    """Run primary H4 test and preregistered secondary GLMM diagnostics on planned rows."""
    # Primary H4: follows ~ 1 + human_frac + seed + (1 | id)  vs  follows ~ 1 + seed + (1 | id)
    h4 = fit_glmm_lrt(
        rows,
        full_design_fn=lambda r: [1.0, r["human_frac"], float(r["seed"])],
        null_design_fn=lambda r: [1.0, float(r["seed"])],
        df=1,
    )
    beta_human = h4["full_params"][1]
    h4["beta_human"] = beta_human
    h4["beta_seed"] = h4["full_params"][2]

    if h4["p"] >= ALPHA:
        reading = "not distinguishable"
    elif beta_human < 0:
        reading = "dose-response supported; higher human-trace fraction lowers step-following"
    else:
        reading = "opposite direction; higher human-trace fraction raises step-following"

    # Nonlinearity check: 5-level categorical vs linear human_frac (df = 3)
    nonlin = fit_glmm_lrt(
        rows,
        full_design_fn=lambda r: [
            1.0,
            1.0 if r["ratio"] == 25 else 0.0,
            1.0 if r["ratio"] == 50 else 0.0,
            1.0 if r["ratio"] == 75 else 0.0,
            1.0 if r["ratio"] == 100 else 0.0,
            float(r["seed"]),
        ],
        null_design_fn=lambda r: [1.0, r["human_frac"], float(r["seed"])],
        df=3,
    )

    # Sensitivity: common intersection across all 10 (seed, ratio) cells
    by_cell = defaultdict(set)
    for r in rows:
        by_cell[(r["seed"], r["ratio"])].add(r["id"])
    expected_cells = {(s, pct) for s in SEEDS for pct in RATIOS}
    common_ids = set.intersection(*(by_cell[c] for c in expected_cells)) if expected_cells <= set(by_cell) else set()
    common_rows = [r for r in rows if r["id"] in common_ids]
    common_glmm = None
    if len(common_ids) >= 5:
        common_glmm = fit_glmm_lrt(
            common_rows,
            full_design_fn=lambda r: [1.0, r["human_frac"], float(r["seed"])],
            null_design_fn=lambda r: [1.0, float(r["seed"])],
            df=1,
        )
        common_glmm["beta_human"] = common_glmm["full_params"][1]

    # Per-seed GLMMs
    per_seed = {}
    for s in SEEDS:
        s_rows = [r for r in rows if r["seed"] == s]
        if s_rows:
            fit = fit_glmm_lrt(
                s_rows,
                full_design_fn=lambda r: [1.0, r["human_frac"]],
                null_design_fn=lambda r: [1.0],
                df=1,
            )
            fit["beta_human"] = fit["full_params"][1]
            per_seed[f"seed{s}"] = fit

    # Pooled ratio-level descriptive rates + Spearman monotonicity
    ratio_rates = {}
    for pct in RATIOS:
        sub = [r for r in rows if r["ratio"] == pct]
        n = len(sub)
        k = sum(1 for r in sub if r["follows"])
        ratio_rates[str(pct)] = {"planned": n, "follows": k, "rate": round(k / n, 6) if n else None}
    xs = [HUMAN_COUNTS[pct] / N_TRAIN for pct in RATIOS]
    ys = [ratio_rates[str(pct)]["rate"] for pct in RATIOS]
    spearman = None
    if all(v is not None for v in ys):
        rho, sp_p = stats.spearmanr(xs, ys)
        spearman = {"rho": round(float(rho), 6), "p": float(sp_p)}

    return {
        "alpha": ALPHA,
        "H4_glmm_dose": h4,
        "reading": reading,
        "nonlinearity_lrt_3df": nonlin,
        "common_intersection_glmm": common_glmm,
        "per_seed_glmm": per_seed,
        "pooled_by_ratio": ratio_rates,
        "spearman_ratio_means": spearman,
    }


def analyze_run(run_dir):
    sealed = _load_sealed()
    read, paired, wilson, correct = sealed.read, sealed.paired, sealed.wilson, sealed.correct
    run = Path(run_dir)

    cells = {}
    all_ids = None
    planned_rows = []
    descriptive = {}

    for s in SEEDS:
        for pct in RATIOS:
            key = f"s{s}_r{pct}"
            cell_dir = run / f"eval_{key}"
            evals = read(cell_dir / "tuned.jsonl")
            ints = read(cell_dir / "tuned_interventions.jsonl")
            if all_ids is None:
                all_ids = sorted(evals)
            elif sorted(evals) != all_ids:
                raise SystemExit(f"{key} answered different questions than other cells")
            cells[(s, pct)] = (evals, ints)

            frac = HUMAN_COUNTS[pct] / N_TRAIN
            planned_rows.extend(_planned_rows(ints, s, pct))

            n_plan = len(ints)
            n_fol = sum(_follows(r) for r in ints.values())
            n_flagged = sum(r["expected"] is None for r in ints.values())
            n_fol_b1 = sum(_follows(r) for r in ints.values() if r["expected"] is not None)
            n_acc = sum(correct(evals[i]) for i in all_ids)
            descriptive[key] = {
                "seed": s,
                "ratio": pct,
                "human_frac": round(frac, 6),
                "planned": n_plan,
                "follows": n_fol,
                "follows_rate": round(n_fol / n_plan, 6) if n_plan else None,
                "flagged_trace": n_flagged,
                "flagged_trace_rate": round(n_flagged / n_plan, 6) if n_plan else None,
                "follows_B1": n_fol_b1,
                "follows_rate_B1": round(n_fol_b1 / (n_plan - n_flagged), 6) if n_plan > n_flagged else None,
                "accuracy": n_acc,
                "accuracy_wilson95": wilson(n_acc, len(all_ids)),
                "format_valid": sum(bool(evals[i]["check"]["format_valid"]) for i in all_ids),
                "truncated": sum(evals[i]["truncated"] for i in all_ids),
                "taxonomy": dict(Counter(r["outcome"] for r in ints.values())),
            }

    stats_out = amended_statistics(planned_rows)

    # Fresh paired McNemar checks per seed: 0 vs 100 (H3 replication) and 25 vs 75
    paired_checks = {}
    for s in SEEDS:
        for a, b in ((0, 100), (25, 75)):
            x, y = cells[(s, a)][1], cells[(s, b)][1]
            common = sorted(set(x) & set(y))
            paired_checks[f"seed{s}_r{a}_vs_r{b}"] = paired(x, y, common, _follows)

    manifest_path = run / "data/manifest.json"
    check_path = run / "check.json"
    return {
        "questions": len(all_ids),
        **stats_out,
        "paired_checks": paired_checks,
        "descriptive": descriptive,
        "mix_manifest_sha256": manifest_path.exists() and json.loads(manifest_path.read_text()).get("ratios") is not None,
        "training_check": json.loads(check_path.read_text()) if check_path.exists() else None,
    }


def main():
    run = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
    result = analyze_run(run)
    text = json.dumps(result, indent=2)
    print(text)
    if run.resolve() == HERE.resolve():
        (HERE / "results.json").write_text(text + "\n")


if __name__ == "__main__":
    main()
