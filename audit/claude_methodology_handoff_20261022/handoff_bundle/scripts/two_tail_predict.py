"""Edgeworth (1st / 2nd order) predictions of the PLAIN-t size on BOTH tails for the regime_two_tails.py populations vs the observed MC sizes
parsed from rt_m3.txt / rt_m5.txt.  Populations copied from regime_two_tails.py (exact gamma printed there is cross-checked against the recomputed one).
F(x) = Phi(x) + n^-1/2 q1(x) phi(x) + n^-1 q2(x) phi(x);  q1 even, q2 odd   (Hall 1992, divisor-n Studentized mean; our T uses n-1 and t_{.975,59}=2.0010
 <=> T_n > 2.0010 sqrt(n/(n-1)))      GO size = 1 - F(x),   NO-GO size = F(-x)."""
import math
import re

N, DELTA = 60, 0.10
Phi = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
phi = lambda x: math.exp(-x * x / 2) / math.sqrt(2 * math.pi)
hom = lambda lst: [(w, q, min(1.0, q + DELTA)) for w, q in lst]


def grid_unif(qlo, qhi, dlo, dhi, k):
    return [(1.0 / (k * k), qlo + (qhi - qlo) * (i + 0.5) / k, qlo + (qhi - qlo) * (i + 0.5) / k + dlo + (dhi - dlo) * (j + 0.5) / k)
            for i in range(k) for j in range(k)]


COMPS = {
    "M1": hom([(0.3, 0.10), (0.3, 0.50), (0.4, 0.85)]),
    "M2": hom([(0.25, 0.05), (0.25, 0.50), (0.5, 0.88)]),
    "M3": [(1 / 400, 0.10 + 0.78 * (i + 0.5) / 400, 0.10 + 0.78 * (i + 0.5) / 400 + DELTA) for i in range(400)],
    "M4": hom([(0.5, 0.20), (0.5, 0.70)]),
    "M5": hom([(0.4, 0.05), (0.6, 0.85)]),
    "H1": [(0.45, 0.30, 0.60), (0.07, 0.70, 0.20), (0.12, 0.05, 0.05), (0.12, 0.50, 0.50), (0.24, 0.90, 0.90)],
    "H2": [(0.30, 0.30, 0.80), (1 / 6, 0.60, 0.30), (0.10, 0.05, 0.05), (0.15, 0.50, 0.50), (1 - 0.30 - 1 / 6 - 0.10 - 0.15, 0.90, 0.90)],
    "H3": grid_unif(0.25, 0.60, -0.2, 0.4, 60),
}


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
    return c3 / c2 ** 1.5, c4 / c2 ** 2 - 3


def predict(g, k):
    x = 2.0010 * math.sqrt(N / (N - 1))
    q1 = g * (2 * x * x + 1) / 6
    q2 = x * (k * (x * x - 3) / 12 - g * g * (x ** 4 + 2 * x * x - 3) / 18 - (x * x + 3) / 4)
    a = q1 * phi(x) / math.sqrt(N)
    b = q2 * phi(x) / N
    go1, go2 = 1 - (Phi(x) + a), 1 - (Phi(x) + a + b)
    no1, no2 = Phi(-x) + a, Phi(-x) + a - b
    return [100 * v for v in (go1, go2, no1, no2)]


pat = re.compile(r"^(\w\d) m=(\d) meanq ([\d.]+) sig2q ([-\d.]+) gamma ([+-][\d.]+) kurt ([+-][\d.]+) \| GO size: plain ([\d.]+) J ([\d.]+) Jor ([\d.]+) boot ([\d.]+) \| NOGO size: plain ([\d.]+) J ([\d.]+) Jor ([\d.]+) boot ([\d.]+)")
print("pop  m  gamma(exact) kurt | GO plain: obs  1st  2nd  (obs-2nd) | NO-GO plain: obs  1st  2nd  (obs-2nd)   [sizes in %, nominal 2.50]")
worst = [0, 0]
for fn in ("rt_m3.txt", "rt_m5.txt"):
    for line in open(fn):
        mt = pat.match(line)
        if not mt:
            continue
        name, m = mt.group(1), int(mt.group(2))
        printed_g = float(mt.group(5))
        g, k = exact(COMPS[name], m)
        assert abs(g - printed_g) < 0.006, (name, m, g, printed_g)       # same population as the MC script
        go_obs, no_obs = float(mt.group(7)), float(mt.group(11))
        go1, go2, no1, no2 = predict(g, k)
        worst[0] = max(worst[0], abs(go_obs - go2))
        worst[1] = max(worst[1], abs(no_obs - no2))
        print("%-3s  %d  %+.3f %+.2f | %.2f %.2f %.2f (%+.2f) | %.2f %.2f %.2f (%+.2f)" % (name, m, g, k, go_obs, go1, go2, go_obs - go2, no_obs, no1, no2, no_obs - no2))
print("max |obs - 2nd order|: GO %.2f pt, NO-GO %.2f pt (MC SE of a 2.5%% cell: 0.04 pt)" % tuple(worst))
