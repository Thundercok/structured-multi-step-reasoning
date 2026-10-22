"""What happens to the validated paired GO rule (Tango at delta_prac, gonogo.py v2) when m>1 draws per question are
POOLED as if all n*m pairs were independent?  Monte Carlo at the boundary (true effect == delta_prac): the false-GO
rate should be 2.5% (one-sided).  Also: question-level cluster analysis (t on per-question means) for reference.
Synthetic population (logit-normal / probit), NOT the pilot data; stdlib only, CPU only."""
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gonogo as g  # noqa: E402

Phi = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
DELTA = 0.10
N_Q = 150            # questions
TCRIT = 1.9760       # t_{0.975, df=149}
REPS = 4000


def calibrate(a_p, s, tau, N=100000, seed=1):
    rng = random.Random(seed)
    U = [rng.gauss(0, 1) for _ in range(N)]
    W = [rng.gauss(0, 1) for _ in range(N)]
    P = [Phi(a_p + s * u) for u in U]
    mp = sum(P) / N
    lo, hi = -1.5, 1.5
    for _ in range(36):
        mid = (lo + hi) / 2
        mq = sum(Phi(mid + s * u + tau * w) for u, w in zip(U, W)) / N
        lo, hi = (mid, hi) if mp - mq > DELTA else (lo, mid)
    a_q = (lo + hi) / 2
    Q = [Phi(a_q + s * u + tau * w) for u, w in zip(U, W)]
    D = [p - q for p, q in zip(P, Q)]
    dm = sum(D) / N
    vbar = sum(p * (1 - p) + q * (1 - q) for p, q in zip(P, Q)) / N
    sq2 = sum((d - dm) ** 2 for d in D) / (N - 1)
    return a_q, dm, vbar, sq2, mp


def run(a_p, a_q, s, tau, m, rng):
    go_pool = go_cl = 0
    for _ in range(REPS):
        b = c = 0
        xs = []
        for _ in range(N_Q):
            u, w = rng.gauss(0, 1), rng.gauss(0, 1)
            p, q = Phi(a_p + s * u), Phi(a_q + s * u + tau * w)
            tot = 0
            for _ in range(m):
                x, y = rng.random() < p, rng.random() < q
                if x and not y:
                    b += 1
                    tot += 1
                elif y and not x:
                    c += 1
                    tot -= 1
            xs.append(tot / m)
        if g.decide(b, c, N_Q * m, DELTA) == "GO":
            go_pool += 1
        mean = sum(xs) / N_Q
        var = sum((v - mean) ** 2 for v in xs) / (N_Q - 1)
        if var > 0 and (mean - DELTA) / math.sqrt(var / N_Q) > TCRIT:
            go_cl += 1
    return go_pool / REPS, go_cl / REPS


t0 = time.time()
a_p, s = 0.35, 0.6
print(f"n={N_Q} questions, reps={REPS}, true effect == delta_prac = {DELTA}; nominal one-sided false-GO = 0.025; MC SE ~ 0.0025")
print(f"{'tau':>4s} {'sigma_q^2':>9s} {'vbar':>6s} {'m':>2s} | {'pooled Tango':>12s} {'predicted':>9s} | {'cluster t':>9s} | DEFF")
for tau in (0.0, 0.6, 1.2):
    a_q, dm, vbar, sq2, mp = calibrate(a_p, s, tau)
    rng = random.Random(20261015)
    for m in (1, 2, 3, 5):
        gp, gc = run(a_p, a_q, s, tau, m, rng)
        deff = (m * sq2 + vbar) / (sq2 + vbar)
        pred = 1 - Phi(1.959964 / math.sqrt(deff))
        print(f"{tau:4.1f} {sq2:9.3f} {vbar:6.3f} {m:2d} | {gp:12.4f} {pred:9.4f} | {gc:9.4f} | {deff:.3f}", flush=True)
    print(f"      (calibrated: E[p]={mp:.3f}, effect={dm:.3f}; {time.time() - t0:.0f}s elapsed)", flush=True)
