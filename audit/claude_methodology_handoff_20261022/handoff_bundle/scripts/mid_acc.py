"""REALISM CHECK: sign/size of skewness and excess kurtosis of x_i = mean_j F_ij - C_i (CONT once; boundary shift p = q + delta) when the
per-question accuracy q_i matches the PILOT regime (CONT/F accuracy ~ 0.5-0.7) instead of the low-accuracy S/V/X populations.
Exact enumeration.  Also prints mean accuracy of every population used so far."""
import math

DELTA = 0.10


def mom(comps, m):
    pts = []
    for w, q in comps:
        p = min(1.0, q + DELTA)
        for c in (0, 1):
            pc = q if c else 1 - q
            for k in range(m + 1):
                pts.append((w * pc * math.comb(m, k) * p ** k * (1 - p) ** (m - k), (k - m * c) / m))
    mu = sum(pr * x for pr, x in pts)
    c2 = sum(pr * (x - mu) ** 2 for pr, x in pts)
    c3 = sum(pr * (x - mu) ** 3 for pr, x in pts)
    c4 = sum(pr * (x - mu) ** 4 for pr, x in pts)
    return mu, c2, c3 / c2 ** 1.5, c4 / c2 ** 2 - 3


def unif(lo, hi, k=400):
    return [(1 / k, lo + (hi - lo) * (i + 0.5) / k) for i in range(k)]


POPS = {
    # earlier synthetic populations (mean accuracy of CONT)
    "B  (q .05/.40)": [(0.6, 0.05), (0.4, 0.40)],
    "A  U(.2,.7)": unif(0.2, 0.7),
    "S1 (q .05/.30)": [(0.9, 0.05), (0.1, 0.30)],
    "X2 (q .03/.20)": [(0.97, 0.03), (0.03, 0.20)],
    # mid-accuracy populations (pilot regime)
    "M1 .10/.50/.85 @ .3/.3/.4": [(0.3, 0.10), (0.3, 0.50), (0.4, 0.85)],
    "M2 .05/.50/.88 @ .25/.25/.5": [(0.25, 0.05), (0.25, 0.50), (0.5, 0.88)],
    "M3 U(.10,.88)": unif(0.10, 0.88),
    "M4 .20/.70 @ .5/.5": [(0.5, 0.20), (0.5, 0.70)],
    "M5 .05/.85 @ .4/.6": [(0.4, 0.05), (0.6, 0.85)],
}
print("population                       mean q | m=3: mean  skew  exKurt | m=5: mean  skew  exKurt   (p = min(1, q+0.10))")
for name, comps in POPS.items():
    mq = sum(w * q for w, q in comps)
    a, b = mom(comps, 3), mom(comps, 5)
    print("%-30s %.3f | %.3f %+.2f %+.1f | %.3f %+.2f %+.1f" % (name, mq, a[0], a[2], a[3], b[0], b[2], b[3]))
