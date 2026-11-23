import importlib.util
from pathlib import Path

import numpy as np
from scipy import special


def _load_analyze():
    path = Path(__file__).resolve().parents[1] / "audit/trace_dose_20261120/analyze.py"
    spec = importlib.util.spec_from_file_location("trace_dose_analyze", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _simulate_rows(n_questions, beta0, beta_human, sigma, rng, drop_prob=0.15, step_fn=False):
    mod = _load_analyze()
    rows = []
    for q in range(n_questions):
        u_q = rng.normal(0.0, sigma)
        for seed in (0, 1):
            for pct in mod.RATIOS:
                if rng.random() < drop_prob:
                    continue
                frac = mod.HUMAN_COUNTS[pct] / mod.N_TRAIN
                x_eff = (1.0 if pct > 0 else 0.0) if step_fn else frac
                p = float(special.expit(beta0 + beta_human * x_eff + 0.1 * seed + u_q))
                rows.append({
                    "id": f"q{q:04d}",
                    "seed": seed,
                    "ratio": pct,
                    "human_frac": frac,
                    "follows": bool(rng.random() < p),
                })
    return rows


def test_glmm_recovers_negative_dose_slope():
    mod = _load_analyze()
    rng = np.random.default_rng(42)
    rows = _simulate_rows(n_questions=300, beta0=2.0, beta_human=-1.2, sigma=1.0, rng=rng)
    out = mod.run_dose_statistics(rows)

    h4 = out["H4_glmm_dose"]
    assert h4["converged"]
    assert h4["beta_human"] < -0.7
    assert h4["p"] < 1e-4
    assert out["reading"].startswith("dose-response supported")
    # True data are linear on logit scale -> nonlinearity check should not reject strongly
    assert out["nonlinearity_lrt_3df"]["p"] > 0.01
    assert out["common_intersection_glmm"]["beta_human"] < 0
    assert out["per_seed_glmm"]["seed0"]["beta_human"] < 0
    assert out["per_seed_glmm"]["seed1"]["beta_human"] < 0


def test_glmm_null_is_not_significant():
    mod = _load_analyze()
    rng = np.random.default_rng(7)
    rows = _simulate_rows(n_questions=250, beta0=1.5, beta_human=0.0, sigma=1.2, rng=rng)
    out = mod.run_dose_statistics(rows)

    assert out["H4_glmm_dose"]["converged"]
    assert out["H4_glmm_dose"]["p"] > 0.05
    assert out["reading"] == "not distinguishable"


def test_nonlinearity_lrt_flags_binary_step_function():
    mod = _load_analyze()
    rng = np.random.default_rng(123)
    # Sharp drop from 0% -> 25%, then completely flat at 25/50/75/100%
    rows = _simulate_rows(n_questions=400, beta0=2.4, beta_human=-2.0, sigma=0.8, rng=rng, step_fn=True)
    out = mod.run_dose_statistics(rows)

    assert out["nonlinearity_lrt_3df"]["converged"]
    assert out["nonlinearity_lrt_3df"]["p"] < 1e-3


def _simulate_cells(n_questions, beta_human, tau, rng, flag_prob=0.0):
    """Like _simulate_rows, plus one logit offset per (seed, ratio) adapter (training-run noise)
    and flagged traces whose `follows` is unreachable."""
    mod = _load_analyze()
    cell = {(s, p): rng.normal(0.0, tau) for s in mod.SEEDS for p in mod.RATIOS}
    u = rng.normal(0.0, 1.0, n_questions)
    rows = []
    for q in range(n_questions):
        for s in mod.SEEDS:
            for pct in mod.RATIOS:
                if rng.random() < 0.15:
                    continue
                frac = mod.HUMAN_COUNTS[pct] / mod.N_TRAIN
                known = not rng.random() < flag_prob
                p = float(special.expit(1.5 + beta_human * frac + 0.1 * s + cell[(s, pct)] + u[q]))
                rows.append({"id": f"q{q:04d}", "seed": s, "ratio": pct, "human_frac": frac,
                             "expected_known": known, "follows": known and bool(rng.random() < p)})
    return rows


def test_adapter_level_test_keeps_size_under_training_noise():
    # The question-only GLMM LRT rejects ~0.26 here (audit/trace_dose_20261120/amendment_20261123).
    mod = _load_analyze()
    rng = np.random.default_rng(2026)
    ps = [mod.adapter_level_test(_simulate_cells(300, 0.0, 0.2, rng))["p"] for _ in range(300)]
    assert np.mean(np.array(ps) < 0.05) <= 0.09


def test_adapter_level_test_detects_h3_sized_slope():
    mod = _load_analyze()
    rng = np.random.default_rng(11)
    out = mod.adapter_level_test(_simulate_cells(500, -0.9, 0.1, rng))
    assert out["n_cells"] == 10 and out["df"] == 7
    assert out["b_human"] < 0 and out["p"] < 0.05
    assert set(out["level_mean_logit"]) == {"0", "25", "50", "75", "100"}


def test_planned_rows_marks_flagged_traces():
    mod = _load_analyze()
    ints = {"a": {"outcome": "follows", "expected": 12.0}, "b": {"outcome": "moved", "expected": None}}
    rows = {r["id"]: r for r in mod._planned_rows(ints, 1, 50)}
    assert rows["a"]["expected_known"] and rows["a"]["follows"]
    assert not rows["b"]["expected_known"] and not rows["b"]["follows"]
    assert rows["a"]["human_frac"] == mod.HUMAN_COUNTS[50] / mod.N_TRAIN


def test_amended_statistics_uses_b1_rows_for_primary():
    mod = _load_analyze()
    rng = np.random.default_rng(5)
    rows = _simulate_cells(120, -0.9, 0.0, rng, flag_prob=0.1)
    out = mod.amended_statistics(rows)
    n_b1 = sum(c["n"] for c in out["H4_primary_adapter_level"]["cells"].values())
    n_all = sum(c["n"] for c in out["secondary_original_metric_adapter_level"]["cells"].values())
    assert n_b1 == sum(r["expected_known"] for r in rows) < n_all == len(rows)
    assert out["reading"] in {"not distinguishable", mod._reading(0.0, -1.0), mod._reading(0.0, 1.0)}
    assert "reading" in out["descriptive_glmm_B1"]
