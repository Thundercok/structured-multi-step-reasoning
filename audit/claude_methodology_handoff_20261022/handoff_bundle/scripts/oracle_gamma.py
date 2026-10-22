"""Is the residual size error of the Johnson test (plug-in skewness) due to the NOISE of gamma-hat?  Compare, on the SAME data sets
(n = 60, CONT once, F m draws, boundary effect = delta_prac = 0.10; alternative +0.15):
   plain t | Johnson with plug-in g-hat | Johnson with the EXACT population gamma (oracle).
Also SD(g-hat), mean(g-hat) and corr(g-hat, T) at the boundary.   usage: oracle_gamma.py M R0 R1"""
import math
import random
import sys
import time

M, R0, R1 = (int(a) for a in sys.argv[1:4])
DELTA, N, TCRIT = 0.10, 60, 2.0010
mix = lambda qlo, qhi, w: (lambda r: qlo if r.random() < w else qhi)
POPS = {
    "B ": (mix(0.05, 0.40, 0.6), [(0.6, 0.05), (0.4, 0.40)]),
    "A ": (lambda r: r.uniform(0.2, 0.7), [(1 / 2000, 0.2 + 0.5 * (i + 0.5) / 2000) for i in range(2000)]),
    "S2": (mix(0.05, 0.60, 0.9), [(0.9, 0.05), (0.1, 0.60)]),
    "S1": (mix(0.05, 0.30, 0.9), [(0.9, 0.05), (0.1, 0.30)]),
}


def exact_gamma(comps, m):
    pts = []
    for w, q in comps:
        p = q + DELTA
        for c in (0, 1):
            pc = q if c else 1 - q
            for k in range(m + 1):
                pts.append((w * pc * math.comb(m, k) * p ** k * (1 - p) ** (m - k), (k - m * c) / m))
    mu = sum(pr * x for pr, x in pts)
    c2 = sum(pr * (x - mu) ** 2 for pr, x in pts)
    return sum(pr * (x - mu) ** 3 for pr, x in pts) / c2 ** 1.5


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


def run(sampler, gam, e, reps, rng):
    go_p = go_j = go_o = 0
    gs, ts = [], []
    for _ in range(reps):
        xs = draw(sampler, e, rng)
        mean = sum(xs) / N
        d2 = sum((x - mean) ** 2 for x in xs)
        if d2 <= 0:
            gs.append(0.0)
            ts.append(-9.0)
            continue
        T = (mean - DELTA) / math.sqrt(d2 / (N - 1) / N)
        g = (sum((x - mean) ** 3 for x in xs) / N) / (d2 / N) ** 1.5
        corr = (1 + 2 * T * T) / (6 * math.sqrt(N))
        go_p += T > TCRIT
        go_j += T + g * corr > TCRIT
        go_o += T + gam * corr > TCRIT
        gs.append(g)
        ts.append(T)
    mg = sum(gs) / reps
    sg = math.sqrt(sum((g - mg) ** 2 for g in gs) / reps)
    mt = sum(ts) / reps
    st = math.sqrt(sum((t - mt) ** 2 for t in ts) / reps)
    cov = sum((g - mg) * (t - mt) for g, t in zip(gs, ts)) / reps
    return go_p / reps, go_j / reps, go_o / reps, mg, sg, cov / (sg * st)


t0 = time.time()
print("n=%d m=%d R0=%d R1=%d  (size SE ~%.2f pt at 3%%)" % (N, M, R0, R1, 100 * math.sqrt(0.03 * 0.97 / R0)), flush=True)
for name, (smp, comps) in POPS.items():
    gam = exact_gamma(comps, M)
    rng = random.Random(5150 + 10 * M + ord(name[0]) + (3 if name[1] == "1" else 0) + (5 if name[1] == "2" else 0))
    sp, sj, so, mg, sg, rho = run(smp, gam, 0.0, R0, rng)
    pp, pj, po, _, _, _ = run(smp, gam, 0.15, R1, rng)
    print("%s m=%d gamma=%+.3f | SIZE plain %.4f  Johnson(g-hat) %.4f  Johnson(oracle gamma) %.4f | POWER plain %.3f  J(g-hat) %.3f  J(oracle) %.3f | g-hat: mean %+.2f SD %.2f corr(g-hat,T) %+.2f  (%.0fs)" % (
        name, M, gam, sp, sj, so, pp, pj, po, mg, sg, rho, time.time() - t0), flush=True)
