"""Fixed-gamma0 Johnson test == plain t with a FIXED critical value (monotone form).  Johnson(gamma0): reject iff T + c(T) gamma0 > x, c(T) = (2T^2+1)/(6 sqrt n),
x = t_{.975,59} = 2.0010; for gamma0 < 0 this is T > T_lo(gamma0), the smaller root of  2 b T^2 - T + (b + x) = 0,  b = |gamma0|/(6 sqrt n)
(T_lo(-1.0)=2.238, T_lo(-1.6)=2.448, T_lo(-2.0)=2.647 at n = 60).  The upper root (~12) is an artefact of the non-monotone Johnson form and is ignored.
Populations: design (B, A, S2, S1), HELD-OUT validation (V1-V4, not used to choose gamma0, larger kurtosis), OUT-OF-RANGE at m=5 (X1, X2: gamma < -1.6).
n = 60, CONT once, boundary effect = delta_prac = 0.10, alternative +0.15.  usage: fixed_critical.py M R0 R1"""
import bisect
import math
import random
import sys
import time

M, R0, R1 = (int(a) for a in sys.argv[1:4])
DELTA, N, X = 0.10, 60, 2.0010
SQ = math.sqrt(N)
G0 = -1.6
mix = lambda qlo, qhi, w: (lambda r: qlo if r.random() < w else qhi)
POPS = {
    "B ": (mix(0.05, 0.40, 0.6), [(0.6, 0.05), (0.4, 0.40)]),
    "A ": (lambda r: r.uniform(0.2, 0.7), [(1 / 2000, 0.2 + 0.5 * (i + 0.5) / 2000) for i in range(2000)]),
    "S2": (mix(0.05, 0.60, 0.9), [(0.9, 0.05), (0.1, 0.60)]),
    "S1": (mix(0.05, 0.30, 0.9), [(0.9, 0.05), (0.1, 0.30)]),
    "V1": (mix(0.02, 0.20, 0.80), [(0.80, 0.02), (0.20, 0.20)]),
    "V2": (mix(0.03, 0.60, 0.97), [(0.97, 0.03), (0.03, 0.60)]),
    "V3": (mix(0.01, 0.20, 0.93), [(0.93, 0.01), (0.07, 0.20)]),
    "V4": (mix(0.05, 0.45, 0.95), [(0.95, 0.05), (0.05, 0.45)]),
    "X1": (mix(0.05, 0.20, 0.93), [(0.93, 0.05), (0.07, 0.20)]),
    "X2": (mix(0.03, 0.20, 0.97), [(0.97, 0.03), (0.03, 0.20)]),
}


def t_lo(g):
    if g >= 0:
        return X
    b = abs(g) / (6 * SQ)
    return (1 - math.sqrt(1 - 8 * b * (b + X))) / (4 * b)


def moments(comps, m):
    pts = []
    for w, q in comps:
        p = q + DELTA
        for c in (0, 1):
            pc = q if c else 1 - q
            for k in range(m + 1):
                pts.append((w * pc * math.comb(m, k) * p ** k * (1 - p) ** (m - k), (k - m * c) / m))
    mu = sum(pr * x for pr, x in pts)
    c2 = sum(pr * (x - mu) ** 2 for pr, x in pts)
    return c2, sum(pr * (x - mu) ** 3 for pr, x in pts) / c2 ** 1.5, sum(pr * (x - mu) ** 4 for pr, x in pts) / c2 ** 2 - 3


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


def tstat(xs):
    mean = sum(xs) / N
    d2 = sum((x - mean) ** 2 for x in xs)
    return -9.0 if d2 <= 0 else (mean - DELTA) / math.sqrt(d2 / (N - 1) / N)


def upper(sorted_t, c):                     # P(T > c)
    return (len(sorted_t) - bisect.bisect_right(sorted_t, c)) / len(sorted_t)


t0 = time.time()
cstar = t_lo(G0)
print("n=%d m=%d R0=%d R1=%d | gamma0=%.1f -> critical value T_lo = %.3f (plain t: %.3f) | MC SE of size at 2.5%%: %.2f pt" % (
    N, M, R0, R1, G0, cstar, X, 100 * math.sqrt(0.025 * 0.975 / R0)), flush=True)
print("pop  gamma  exKurt | q97.5(T) | size: plain  J(gamma)  J(g0)  [user-recipe pred] | power: plain  J(gamma)  J(g0)", flush=True)
for name, (smp, comps) in POPS.items():
    var, gam, kur = moments(comps, M)
    rng = random.Random(31415 + 100 * M + ord(name[0]) * 3 + ord(name[1]))
    tb = sorted(tstat(draw(smp, 0.0, rng)) for _ in range(R0))
    ta = sorted(tstat(draw(smp, 0.15, rng)) for _ in range(R1))
    cg = t_lo(gam)
    q975 = tb[int(0.975 * R0)]
    s_plain, s_or, s_g0 = upper(tb, X), upper(tb, cg), upper(tb, cstar)
    pred = s_or + 0.056 * ((2 * X * X + 1) / (6 * SQ)) * (G0 - gam)      # the first-order recipe used for B m=3 (0.056, c(2.001))
    print("%s %+.2f  %+5.1f | %.3f | %.2f%%  %.2f%%  %.2f%%  [%.2f%%] | %.1f%%  %.1f%%  %.1f%%   (%.0fs)" % (
        name, gam, kur, q975, 100 * s_plain, 100 * s_or, 100 * s_g0, 100 * pred, 100 * upper(ta, X), 100 * upper(ta, cg), 100 * upper(ta, cstar), time.time() - t0), flush=True)
