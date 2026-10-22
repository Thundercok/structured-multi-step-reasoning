"""Isolate the effect-heterogeneity contribution to gamma/kurtosis of x_i: same q-structure as H1-H3, with (het) the heterogeneous effect of regime_two_tails.py
versus (hom) a homogeneous shift p = min(1, q + 0.10).  Exact enumeration."""
import sys
sys.argv = ["x", "3", "1", "1"]
import math
DELTA = 0.10
def exact(comps, m):
    pts = []
    for w, q, p in comps:
        for c in (0, 1):
            pc = q if c else 1 - q
            for k in range(m + 1):
                pts.append((w * pc * math.comb(m, k) * p ** k * (1 - p) ** (m - k), (k - m * c) / m))
    mu = sum(pr * x for pr, x in pts)
    c2 = sum(pr * (x - mu) ** 2 for pr, x in pts)
    c3 = sum(pr * (x - mu) ** 3 for pr, x in pts)
    c4 = sum(pr * (x - mu) ** 4 for pr, x in pts)
    return mu, c2, c3 / c2 ** 1.5, c4 / c2 ** 2 - 3
def homify(comps):
    return [(w, q, min(1.0, q + DELTA)) for w, q, p in comps]
def grid_unif(qlo, qhi, dlo, dhi, k):
    return [(1.0 / (k * k), qlo + (qhi - qlo) * (i + 0.5) / k, qlo + (qhi - qlo) * (i + 0.5) / k + dlo + (dhi - dlo) * (j + 0.5) / k) for i in range(k) for j in range(k)]
H = {
 "H1": [(0.45, 0.30, 0.60), (0.07, 0.70, 0.20), (0.12, 0.05, 0.05), (0.12, 0.50, 0.50), (0.24, 0.90, 0.90)],
 "H2": [(0.30, 0.30, 0.80), (1 / 6, 0.60, 0.30), (0.10, 0.05, 0.05), (0.15, 0.50, 0.50), (1 - 0.30 - 1 / 6 - 0.10 - 0.15, 0.90, 0.90)],
 "H3": grid_unif(0.25, 0.60, -0.2, 0.4, 60),
}
print("pop m | het: mean var gamma exKurt | hom (same q's, effect +0.10 for all): mean var gamma exKurt | d_gamma")
for name, comps in H.items():
    for m in (3, 5):
        a, b = exact(comps, m), exact(homify(comps), m)
        print("%s  %d | %.3f %.3f %+.3f %+.2f | %.3f %.3f %+.3f %+.2f | %+.3f" % (name, m, a[0], a[1], a[2], a[3], b[0], b[1], b[2], b[3], a[2] - b[2]))
