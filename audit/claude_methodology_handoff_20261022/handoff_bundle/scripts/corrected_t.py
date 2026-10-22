"""Cluster-level one-sided tests at n = 60 questions, F with m draws, CONT once (shared); synthetic populations B, A (sigma_q^2 = 0).
All three tests are computed on the SAME simulated data sets:
  plain t          : T = (mean - delta)/(s/sqrt n)  >  t_{0.975,59} = 2.0010
  Johnson-corrected: T* = T + g/(6 sqrt n) (1 + 2 T^2)  >  2.0010      (g = plug-in skewness of the question means; first-order Edgeworth fix)
  bootstrap-t      : T > upper 2.5% quantile of T*_b = (mean*_b - mean)/(s*_b/sqrt n), B resamples of the question means
Size at the boundary (effect = delta_prac) and power at delta_prac + 0.15.  stdlib, CPU only.  usage: corrected_t.py M REPS B"""
import math
import random
import sys
import time

M, REPS, BOOT = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
DELTA, N, TCRIT = 0.10, 60, 2.0010
POPS = {
    "B": lambda r: 0.05 if r.random() < 0.6 else 0.40,
    "A": lambda r: r.uniform(0.2, 0.7),
}


def draw(sampler, e, rng):
    xs = []
    for _ in range(N):
        q = sampler(rng)
        p = q + DELTA + e
        cc = rng.random() < q
        tot = 0
        for _ in range(M):
            f = rng.random() < p
            tot += int(f and not cc) - int(cc and not f)
        xs.append(tot / M)
    return xs


def run(sampler, e, rng):
    plain = john = boot = 0
    skews = []
    for _ in range(REPS):
        xs = draw(sampler, e, rng)
        mean = sum(xs) / N
        d2 = sum((x - mean) ** 2 for x in xs)
        if d2 <= 0:
            continue
        s2 = d2 / (N - 1)
        T = (mean - DELTA) / math.sqrt(s2 / N)
        plain += T > TCRIT
        m2 = d2 / N
        g = (sum((x - mean) ** 3 for x in xs) / N) / m2 ** 1.5
        skews.append(g)
        john += (T + g / (6 * math.sqrt(N)) * (1 + 2 * T * T)) > TCRIT
        qs = []
        for _b in range(BOOT):
            ys = rng.choices(xs, k=N)
            my = sum(ys) / N
            vy = (sum(y * y for y in ys) - N * my * my) / (N - 1)
            if vy > 1e-12:
                qs.append((my - mean) / math.sqrt(vy / N))
        qs.sort()
        boot += T > qs[int(0.975 * len(qs))]
    return plain / REPS, john / REPS, boot / REPS, sum(skews) / len(skews)


t0 = time.time()
print("n=%d m=%d reps=%d boot=%d; MC SE ~%.4f at 2.5%%" % (N, M, REPS, BOOT, math.sqrt(0.025 * 0.975 / REPS)), flush=True)
for name, s in POPS.items():
    for e, label in ((0.0, "SIZE "), (0.15, "POWER")):
        rng = random.Random(31337 + 1000 * M + int(e * 100) + (7 if name == "A" else 0))
        p, j, b, g = run(s, e, rng)
        print("pop %s m=%d %s: plain t %.4f | Johnson %.4f | bootstrap-t %.4f   (mean sample skew %+.2f; %.0fs)" % (name, M, label, p, j, b, g, time.time() - t0), flush=True)
