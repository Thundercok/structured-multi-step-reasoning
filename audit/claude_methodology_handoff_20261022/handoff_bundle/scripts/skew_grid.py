"""Exact moments of the question mean x_i = (1/m) sum_j (F_ij - C_i)  (C once, shared) for 2-point mixtures of q; boundary effect = delta.
Also: sample skewness of the PILOT question-level F-A vector (8 x +0.5, 2 x -0.5, 2 ties), n = 12, as reported by the user."""
import math
from itertools import product

def binom(m, k, p): return math.comb(m, k) * p**k * (1 - p)**(m - k)

def moments(comps, m, delta):          # comps: [(weight, q)]
    pts = []                            # (prob, x)
    for w, q in comps:
        p = q + delta
        for c in (0, 1):
            pc = q if c else 1 - q
            for k in range(m + 1):
                pts.append((w * pc * binom(m, k, p), (k - m * c) / m))
    mu = sum(pr * x for pr, x in pts)
    v = sum(pr * (x - mu) ** 2 for pr, x in pts)
    m3 = sum(pr * (x - mu) ** 3 for pr, x in pts)
    return mu, v, m3 / v ** 1.5

# check against known: B (q=.05 w.p. .6 / .40 w.p. .4), m=1,3,5 -> +0.052, -0.497, -0.669 (CONT once, boundary)
for m in (1, 3, 5):
    mu, v, g = moments([(0.6, 0.05), (0.4, 0.40)], m, 0.10)
    print("B m=%d: mean %.4f var %.4f skew %+.3f" % (m, mu, v, g))

# pilot vector
vec = [0.5] * 8 + [-0.5] * 2 + [0.0] * 2
n = len(vec); mu = sum(vec) / n
m2 = sum((x - mu) ** 2 for x in vec) / n; m3 = sum((x - mu) ** 3 for x in vec) / n
g1 = m3 / m2 ** 1.5
print("pilot F-A question vector: n=%d mean %.3f g1 %.3f  G1(adj) %.3f ; normal-data SD(g1) ~ sqrt(6/n)=%.2f" % (
    n, mu, g1, g1 * math.sqrt(n * (n - 1)) / (n - 2), math.sqrt(6 / n)))

# search 2-point mixtures for heavier negative skew at m = 3, 5 (need q + delta + 0.15 <= 1 for the power run)
print("\nsearch: q_lo, q_hi, w_lo -> skew(m=3), skew(m=5), var(m=3)")
rows = []
for qlo, qhi, wlo in product((0.01, 0.02, 0.05), (0.3, 0.45, 0.6, 0.7), (0.5, 0.65, 0.8, 0.9)):
    g3 = moments([(wlo, qlo), (1 - wlo, qhi)], 3, 0.10)
    g5 = moments([(wlo, qlo), (1 - wlo, qhi)], 5, 0.10)
    rows.append((g5[2], qlo, qhi, wlo, g3[2], g5[2], g3[1]))
rows.sort()
for r in rows[:10]:
    print("  q_lo=%.2f q_hi=%.2f w_lo=%.2f -> skew3 %+.3f skew5 %+.3f var3 %.3f" % (r[1], r[2], r[3], r[4], r[5], r[6]))
