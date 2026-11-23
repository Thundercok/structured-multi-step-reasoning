"""Type I error of the preregistered H4 LRT when each (seed, ratio) adapter has its own offset.

Null: beta_human = 0. Each of the 10 adapters gets c ~ N(0, tau) on the logit scale
(training-run noise). Question effect u ~ N(0, sigma). 15% rows dropped (not planned).
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
from scipy import special

REPO = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("a", REPO / "audit/trace_dose_20261120/analyze.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


# --- vectorized drop-in for speed (same likelihood); checked against the original below ---
_orig_nll, _orig_design = mod._neg_loglik_glmm, mod._design_arrays
def _design_vec(grouped, design_fn):
    X, y, q = [], [], []
    for i, grp in enumerate(grouped):
        for r in grp:
            X.append(design_fn(r)); y.append(1.0 if r["follows"] else 0.0); q.append(i)
    return [(np.asarray(X, float), np.asarray(y, float), np.asarray(q), len(grouped))]
def _nll_vec(params, packed):
    X, y, q, nq = packed[0]
    sigma = np.exp(np.clip(params[-1], -10.0, 4.0))
    eta = (X @ params[:-1])[:, None] + sigma * mod.GH_U[None, :]
    ll = y[:, None] * eta - np.logaddexp(0.0, eta)
    per_q = np.zeros((nq, ll.shape[1])); np.add.at(per_q, q, ll)
    return -float(special.logsumexp(mod.GH_LOG_W + per_q, axis=1).sum())

N_Q, BETA0, SIGMA, DROP, REPS = 500, 1.5, 1.0, 0.15, int(sys.argv[2])


def simulate(rng, tau, beta=0.0):
    cell = {(s, r): rng.normal(0, tau) for s in mod.SEEDS for r in mod.RATIOS}
    u = rng.normal(0, SIGMA, N_Q)
    rows = []
    for q in range(N_Q):
        for s in mod.SEEDS:
            for r in mod.RATIOS:
                if rng.random() < DROP:
                    continue
                p = special.expit(BETA0 + beta * mod.HUMAN_COUNTS[r] / mod.N_TRAIN + 0.1 * s + cell[(s, r)] + u[q])
                rows.append({"id": f"q{q}", "seed": s, "ratio": r,
                             "human_frac": mod.HUMAN_COUNTS[r] / mod.N_TRAIN,
                             "follows": bool(rng.random() < p)})
    return rows



_rows = simulate(np.random.default_rng(0), 0.2)
_g = mod._group_by_question(_rows); _f = lambda r: [1.0, r["human_frac"], float(r["seed"])]
_p = np.array([1.2, -0.3, 0.1, 0.05])
print("orig vs vec nll:", _orig_nll(_p, _orig_design(_g, _f)), _nll_vec(_p, _design_vec(_g, _f)), flush=True)
mod._neg_loglik_glmm, mod._design_arrays = _nll_vec, _design_vec


from scipy import stats

def cell_test(rows):
    """Two-stage: one logit per adapter, OLS logit ~ human_frac + seed, t-test on 7 df."""
    agg = {}
    for r in rows:
        k = (r["seed"], r["ratio"]); n, f = agg.get(k, (0, 0)); agg[k] = (n + 1, f + r["follows"])
    X, y = [], []
    for (s, rr), (n, f) in agg.items():
        X.append([1.0, mod.HUMAN_COUNTS[rr] / mod.N_TRAIN, float(s)])
        y.append(special.logit((f + 0.5) / (n + 1.0)))
    X, y = np.array(X), np.array(y)
    b, res, *_ = np.linalg.lstsq(X, y, rcond=None)
    dof = len(y) - X.shape[1]
    s2 = float(np.sum((y - X @ b) ** 2)) / dof
    se = np.sqrt(s2 * np.linalg.inv(X.T @ X)[1, 1])
    return float(2 * stats.t.sf(abs(b[1] / se), dof))

configs = [(0.0, 0.0), (0.0, 0.1), (0.0, 0.2), (-0.9, 0.1), (-0.9, 0.2), (-0.45, 0.1), (-0.45, 0.2)]
for beta, tau in configs:
    rng = np.random.default_rng(int(5000 + 100 * tau + 10 * abs(beta)))
    pl, pc = [], []
    for _ in range(REPS):
        rows = simulate(rng, tau, beta)
        pl.append(mod.fit_glmm_lrt(rows, lambda r: [1.0, r["human_frac"], float(r["seed"])],
                                   lambda r: [1.0, float(r["seed"])])["p"])
        pc.append(cell_test(rows))
    print(f"beta={beta:+.2f} tau={tau:.1f}  reject@0.05  prereg_LRT={np.mean(np.array(pl) < 0.05):.2f}  "
          f"cell_t7={np.mean(np.array(pc) < 0.05):.2f}  (n={REPS})", flush=True)
