"""PILOT-REGIME validity of the cluster-level tests on BOTH decision tails (GO: T > c, NO-GO: T < -c) at the boundary (true effect = delta_prac = 0.10).
n = 60 questions, CONT once (shared), F m draws.  Populations are (weight, q, p) types: q = P(CONT correct), p = P(F correct) per question.
  M1-M5 : homogeneous shift p = q + 0.10 (sigma_q^2 = 0), mean accuracy 0.45-0.58 (pilot regime)
  H1    : heterogeneous effect, RARE-but-LARGE harm  (45%: +0.30, 7%: -0.50, rest 0)      -> negative skew expected
  H2    : heterogeneous effect, COMMON-but-moderate harm (30%: +0.50, 1/6: -0.30, rest 0) -> positive skew expected
  H3    : smooth heterogeneity q~U(.25,.60), effect~U(-.2,.4)
Tests on the SAME data sets: plain t | Johnson with plug-in g-hat | Johnson with EXACT gamma (oracle) | bootstrap-t (first RB reps only).
usage: regime_two_tails.py M R RB"""
import bisect
import math
import random
import sys
import time

M, R, RB = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
DELTA, N, X, BOOT = 0.10, 60, 2.0010, 399
SQ = math.sqrt(N)


def types_sampler(types):
    cum, s = [], 0.0
    for w, _, _ in types:
        s += w
        cum.append(s)

    def draw(r):
        _, q, p = types[min(bisect.bisect_left(cum, r.random() * s), len(types) - 1)]
        return q, p
    return draw


hom = lambda lst: [(w, q, min(1.0, q + DELTA)) for w, q in lst]


def grid_unif(qlo, qhi, dlo, dhi, k):          # exact-moment grid for q~U(qlo,qhi), delta~U(dlo,dhi)
    return [(1.0 / (k * k), qlo + (qhi - qlo) * (i + 0.5) / k, qlo + (qhi - qlo) * (i + 0.5) / k + dlo + (dhi - dlo) * (j + 0.5) / k)
            for i in range(k) for j in range(k)]


T_M1 = hom([(0.3, 0.10), (0.3, 0.50), (0.4, 0.85)])
T_M2 = hom([(0.25, 0.05), (0.25, 0.50), (0.5, 0.88)])
T_M4 = hom([(0.5, 0.20), (0.5, 0.70)])
T_M5 = hom([(0.4, 0.05), (0.6, 0.85)])
T_H1 = [(0.45, 0.30, 0.60), (0.07, 0.70, 0.20), (0.12, 0.05, 0.05), (0.12, 0.50, 0.50), (0.24, 0.90, 0.90)]
T_H2 = [(0.30, 0.30, 0.80), (1 / 6, 0.60, 0.30), (0.10, 0.05, 0.05), (0.15, 0.50, 0.50), (1 - 0.30 - 1 / 6 - 0.10 - 0.15, 0.90, 0.90)]
POPS = {
    "M1": (types_sampler(T_M1), T_M1),
    "M2": (types_sampler(T_M2), T_M2),
    "M3": (lambda r: (lambda q: (q, q + DELTA))(r.uniform(0.10, 0.88)),
           [(1 / 400, 0.10 + 0.78 * (i + 0.5) / 400, 0.10 + 0.78 * (i + 0.5) / 400 + DELTA) for i in range(400)]),
    "M4": (types_sampler(T_M4), T_M4),
    "M5": (types_sampler(T_M5), T_M5),
    "H1": (types_sampler(T_H1), T_H1),
    "H2": (types_sampler(T_H2), T_H2),
    "H3": (lambda r: (lambda q: (q, q + r.uniform(-0.2, 0.4)))(r.uniform(0.25, 0.60)), grid_unif(0.25, 0.60, -0.2, 0.4, 60)),
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
    mq = sum(w * q for w, q, p in comps)
    sq2 = sum(w * (p - q) ** 2 for w, q, p in comps) - (sum(w * (p - q) for w, q, p in comps)) ** 2
    return mu, c2, c3 / c2 ** 1.5, c4 / c2 ** 2 - 3, mq, sq2


def draw_data(sampler, rng):
    xs = []
    for _ in range(N):
        q, p = sampler(rng)
        cc = rng.random() < q
        tot = 0
        for _ in range(M):
            f = rng.random() < p
            tot += int(f and not cc) - int(cc and not f)
        xs.append(tot / M)
    return xs


t0 = time.time()
print("n=%d m=%d R=%d (SE of a 2.5%% size: %.2f pt) RB=%d (boot-t, SE %.2f pt)" % (N, M, R, 100 * math.sqrt(0.025 * 0.975 / R), RB, 100 * math.sqrt(0.025 * 0.975 / RB)), flush=True)
for name, (smp, comps) in POPS.items():
    mu, var, gam, kur, mq, sq2 = exact(comps, M)
    rng = random.Random(777 + 31 * M + ord(name[0]) * 5 + ord(name[1]))
    c = {k: 0 for k in ("gp", "np", "gj", "nj", "go", "no", "gb", "nb")}
    for it in range(R):
        xs = draw_data(smp, rng)
        mean = sum(xs) / N
        d2 = sum((x - mean) ** 2 for x in xs)
        if d2 <= 0:
            continue
        T = (mean - DELTA) / math.sqrt(d2 / (N - 1) / N)
        g = (sum((x - mean) ** 3 for x in xs) / N) / (d2 / N) ** 1.5
        cT = (2 * T * T + 1) / (6 * SQ)
        c["gp"] += T > X
        c["np"] += T < -X
        tj = T + g * cT
        c["gj"] += tj > X
        c["nj"] += tj < -X
        to = T + gam * cT
        c["go"] += to > X
        c["no"] += to < -X
        if it < RB:
            qs = []
            for _ in range(BOOT):
                ys = rng.choices(xs, k=N)
                my = sum(ys) / N
                vy = (sum(y * y for y in ys) - N * my * my) / (N - 1)
                if vy > 1e-12:
                    qs.append((my - mean) / math.sqrt(vy / N))
            qs.sort()
            c["gb"] += T > qs[int(0.975 * len(qs))]
            c["nb"] += T < qs[int(0.025 * len(qs))]
    f = lambda k, n=R: 100 * c[k] / n
    print("%s m=%d meanq %.2f sig2q %.3f gamma %+.2f kurt %+.1f | GO size: plain %.2f J %.2f Jor %.2f boot %.2f | NOGO size: plain %.2f J %.2f Jor %.2f boot %.2f   (%.0fs)" % (
        name, M, mq, sq2, gam, kur, f("gp"), f("gj"), f("go"), f("gb", RB), f("np"), f("nj"), f("no"), f("nb", RB), time.time() - t0), flush=True)
