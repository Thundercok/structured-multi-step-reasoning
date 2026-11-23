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


def simulate(rng, tau):
    cell = {(s, r): rng.normal(0, tau) for s in mod.SEEDS for r in mod.RATIOS}
    u = rng.normal(0, SIGMA, N_Q)
    rows = []
    for q in range(N_Q):
        for s in mod.SEEDS:
            for r in mod.RATIOS:
                if rng.random() < DROP:
                    continue
                p = special.expit(BETA0 + 0.1 * s + cell[(s, r)] + u[q])
                rows.append({"id": f"q{q}", "seed": s, "ratio": r,
                             "human_frac": mod.HUMAN_COUNTS[r] / mod.N_TRAIN,
                             "follows": bool(rng.random() < p)})
    return rows



_rows = simulate(np.random.default_rng(0), 0.2)
_g = mod._group_by_question(_rows); _f = lambda r: [1.0, r["human_frac"], float(r["seed"])]
_p = np.array([1.2, -0.3, 0.1, 0.05])
print("orig vs vec nll:", _orig_nll(_p, _orig_design(_g, _f)), _nll_vec(_p, _design_vec(_g, _f)), flush=True)
mod._neg_loglik_glmm, mod._design_arrays = _nll_vec, _design_vec

for tau in (0.0, 0.1, 0.2, 0.3):
    rng = np.random.default_rng(1000 + int(tau * 10))
    ps = []
    for _ in range(REPS):
        h4 = mod.fit_glmm_lrt(simulate(rng, tau),
                              lambda r: [1.0, r["human_frac"], float(r["seed"])],
                              lambda r: [1.0, float(r["seed"])])
        ps.append(h4["p"])
    ps = np.array(ps)
    print(f"tau={tau:.1f}  reject@0.05 = {np.mean(ps < 0.05):.2f}  (n={REPS})", flush=True)
