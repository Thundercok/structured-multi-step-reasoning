"""PC4 (mu=.78, s=.5, E3) GO power at a FEASIBLE alternative (e = 0.18 <= headroom 0.22) for the insured / plain thresholds, m=3 and m=5 (n=60), plus boundary size.
usage: pc4_insured.py R"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import beta_exact as be  # noqa: E402

R = int(sys.argv[1])
DELTA, N = 0.10, 60
a, b = 0.78 * 0.5, 0.22 * 0.5
grid = be.beta_grid(a, b)


def theta_for(e):
    lo, hi = 0.0, 40.0
    for _ in range(100):
        th = 0.5 * (lo + hi)
        eff = sum(w * (be.expit(be.logit(q) + th) - q) for w, q in grid)
        lo, hi = (th, hi) if eff < e else (lo, th)
    return 0.5 * (lo + hi)


for M in (3, 5):
    rng = random.Random(31337 + M)
    out = {}
    for e in (0.10, 0.18):
        th = theta_for(e)
        ts = []
        for _ in range(R):
            xs = []
            for _ in range(N):
                q = rng.betavariate(a, b)
                p = be.expit(be.logit(q) + th)
                cc = rng.random() < q
                tot = 0
                for _ in range(M):
                    f = rng.random() < p
                    tot += int(f and not cc) - int(cc and not f)
                xs.append(tot / M)
            mean = sum(xs) / N
            d2 = sum((x - mean) ** 2 for x in xs)
            ts.append(-99.0 if d2 <= 0 else (mean - DELTA) / math.sqrt(d2 / (N - 1) / N))
        out[e] = ts
    up = lambda ts, c: 100 * sum(1 for t in ts if t > c) / len(ts)
    print("m=%d R=%d PC4: theta(e=.10)=%.3f theta(e=.18)=%.3f | GO size c=2.001: %.2f  c=2.156: %.2f | GO power(e=.18) c=2.001: %.1f  c=2.156: %.1f" % (
        M, R, theta_for(0.10), theta_for(0.18), up(out[0.10], 2.001), up(out[0.10], 2.156), up(out[0.18], 2.001), up(out[0.18], 2.156)), flush=True)
