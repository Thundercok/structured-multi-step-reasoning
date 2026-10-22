"""Does the pooled-Tango inflation (CONT once, shared) shrink with n, and does the cluster-t error shrink with n?
Same synthetic populations as shared_baseline_mc.py (sigma_q^2 = 0), boundary effect == delta_prac = 0.10, m = 3.
n in {150, 600}.  stdlib, CPU only."""
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gonogo as g  # noqa: E402

Phi = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
DELTA, REPS, M = 0.10, 4000, 3
TC = {150: 1.9760, 600: 1.9640}      # t_{0.975, n-1}
POPS = {
    "B": (lambda r: 0.05 if r.random() < 0.6 else 0.40, 0.125, 0.177),
    "A": (lambda r: r.uniform(0.2, 0.7), 0.227, 0.227),
}


def run(sampler, n, m, rng):
    pool = cl = 0
    for _ in range(REPS):
        b = c = 0
        xs = []
        for _ in range(n):
            q = sampler(rng)
            p = q + DELTA
            cc = rng.random() < q
            tot = 0
            for _ in range(m):
                f = rng.random() < p
                if f and not cc:
                    b += 1
                    tot += 1
                elif cc and not f:
                    c += 1
                    tot -= 1
            xs.append(tot / m)
        if g.decide(b, c, n * m, DELTA) == "GO":
            pool += 1
        mean = sum(xs) / n
        var = sum((v - mean) ** 2 for v in xs) / (n - 1)
        if var > 0 and (mean - DELTA) / math.sqrt(var / n) > TC[n]:
            cl += 1
    return pool / REPS, cl / REPS


t0 = time.time()
print("m=%d, CONT once (shared), sigma_q^2 = 0, effect == delta_prac; reps=%d" % (M, REPS))
for name, (s, vC, vF) in POPS.items():
    deff = 1 + (M - 1) * vC / (vC + vF)
    pred = 1 - Phi(1.959964 / math.sqrt(deff))
    for n in (150, 600):
        rng = random.Random(777 + n)
        gp, gc = run(s, n, M, rng)
        print("pop %s n=%3d: pooled Tango %.4f (predicted %.4f) | cluster t %.4f   (%.0fs)" % (name, n, gp, pred, gc, time.time() - t0), flush=True)
