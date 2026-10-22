"""Exact variance/skewness/excess kurtosis of x_i (CONT once, boundary delta=0.10) for 2-point q-mixtures: look for HELD-OUT validation
populations (gamma inside [-1.6, 0]) and OUT-OF-RANGE populations (gamma < -1.6) for a fixed-gamma0 = -1.6 critical-value test."""
import math
from itertools import product

DELTA = 0.10


def mom(comps, m):
    pts = []
    for w, q in comps:
        p = q + DELTA
        for c in (0, 1):
            pc = q if c else 1 - q
            for k in range(m + 1):
                pts.append((w * pc * math.comb(m, k) * p ** k * (1 - p) ** (m - k), (k - m * c) / m))
    mu = sum(pr * x for pr, x in pts)
    c2 = sum(pr * (x - mu) ** 2 for pr, x in pts)
    c3 = sum(pr * (x - mu) ** 3 for pr, x in pts)
    c4 = sum(pr * (x - mu) ** 4 for pr, x in pts)
    return c2, c3 / c2 ** 1.5, c4 / c2 ** 2 - 3


rows = []
for qlo, qhi, w in product((0.01, 0.02, 0.03, 0.05), (0.2, 0.3, 0.45, 0.6), (0.8, 0.85, 0.9, 0.93, 0.95, 0.97)):
    c = [(w, qlo), (1 - w, qhi)]
    a3, a5 = mom(c, 3), mom(c, 5)
    rows.append((a5[1], qlo, qhi, w, a3, a5, w * qlo * (1 - qlo) + (1 - w) * qhi * (1 - qhi)))
rows.sort()
print("q_lo q_hi w_lo | m=3: var skew exKurt | m=5: var skew exKurt | v_CONT      (most negative m=5 skewness first)")
for r in rows[:16]:
    print("%.2f %.2f %.2f | %.3f %+.2f %+.1f | %.3f %+.2f %+.1f | %.3f" % (r[1], r[2], r[3], r[4][0], r[4][1], r[4][2], r[5][0], r[5][1], r[5][2], r[6]))
print("--- candidates with m=5 skewness in (-1.6, -1.0)")
for r in rows:
    if -1.6 < r[0] < -1.0:
        print("%.2f %.2f %.2f | %.3f %+.2f %+.1f | %.3f %+.2f %+.1f | %.3f" % (r[1], r[2], r[3], r[4][0], r[4][1], r[4][2], r[5][0], r[5][1], r[5][2], r[6]))
