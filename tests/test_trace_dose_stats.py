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
