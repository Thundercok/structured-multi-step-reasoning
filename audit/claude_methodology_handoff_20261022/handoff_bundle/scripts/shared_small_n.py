"""Cluster-level one-sided t (question means) for F (m draws) vs CONT (called once, shared) at SMALL n:
false-GO at the boundary (true effect == delta_prac = 0.10).  Same synthetic populations as shared_baseline_mc.py
(sigma_q^2 = 0 by construction, so all shared variance is CONT noise).  stdlib, CPU only."""
import math
import random
import time

DELTA, REPS = 0.10, 4000
TC = {30: 2.0452, 60: 2.0010, 150: 1.9760}     # t_{0.975, n-1}
POPS = {
    "B (q=.05 w.p. .6 / .40 w.p. .4)": lambda r: 0.05 if r.random() < 0.6 else 0.40,
    "A (q~U(.2,.7))": lambda r: r.uniform(0.2, 0.7),
}


def run(sampler, n, m, rng):
    go = 0
    tc = TC[n]
    for _ in range(REPS):
        xs = []
        for _ in range(n):
            q = sampler(rng)
            p = q + DELTA
            cc = rng.random() < q
            tot = 0
            for _ in range(m):
                f = rng.random() < p
                tot += int(f and not cc) - int(cc and not f)
            xs.append(tot / m)
        mean = sum(xs) / n
        var = sum((v - mean) ** 2 for v in xs) / (n - 1)
        if var > 0 and (mean - DELTA) / math.sqrt(var / n) > tc:
            go += 1
    return go / REPS


t0 = time.time()
print("cluster t, CONT once, true effect == delta_prac = 0.10, sigma_q^2 = 0, reps = %d (MC SE ~ 0.0025 at 2.5%%)" % REPS)
for name, s in POPS.items():
    for n in (30, 60):
        rng = random.Random(20261015 + n)
        row = "  ".join("m=%d %.4f" % (m, run(s, n, m, rng)) for m in (1, 3, 5))
        print("pop %-32s n=%3d: %s   (%.0fs)" % (name, n, row, time.time() - t0), flush=True)
