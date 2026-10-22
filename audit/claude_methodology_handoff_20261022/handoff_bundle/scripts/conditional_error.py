"""Does the CONDITIONAL error of gamma-hat at the rejection boundary explain size(Johnson(g-hat)) - size(Johnson(gamma))?
Boundary null (delta_prac = 0.10), n = 60, CONT once, F m draws; populations B, A, S2, S1 (as in corrected_t2.py).
Per data set: T (plain t), g = plug-in skewness, c(T) = (2T^2+1)/(6 sqrt n), S0 = T + c(T)*gamma (oracle Johnson), S1 = T + c(T)*g, D = S1 - S0 = c(T)(g - gamma).
  observed gap  = P(S1 > x) - P(S0 > x),  x = 2.0010                       (paired, same data sets)
  flux estimate = f_S0(x) * E[D | S0 = x]  ~ (1/(2 h R)) * sum_{|S0-x|<h} D   (first order: net crossings of the boundary)
  global-regression proxy for E[eps | boundary] from corr(g, T):  E[eps] + beta (Tbar_window - Tbar),  beta = cov(g,T)/var(T)
Also prints the profile E[g - gamma | T-bin].   usage: conditional_error.py M R"""
import math
import random
import sys
import time

M, R = int(sys.argv[1]), int(sys.argv[2])
DELTA, N, X = 0.10, 60, 2.0010
SQ = math.sqrt(N)
mix = lambda qlo, qhi, w: (lambda r: qlo if r.random() < w else qhi)
POPS = {
    "B ": (mix(0.05, 0.40, 0.6), [(0.6, 0.05), (0.4, 0.40)]),
    "A ": (lambda r: r.uniform(0.2, 0.7), [(1 / 2000, 0.2 + 0.5 * (i + 0.5) / 2000) for i in range(2000)]),
    "S2": (mix(0.05, 0.60, 0.9), [(0.9, 0.05), (0.1, 0.60)]),
    "S1": (mix(0.05, 0.30, 0.9), [(0.9, 0.05), (0.1, 0.30)]),
}
BINS = [(-99, -1), (-1, 0), (0, 1), (1, 2), (2, 3), (3, 99)]


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


def draw(sampler, rng):
    xs = []
    for _ in range(N):
        q = sampler(rng)
        p = q + DELTA
        cc = rng.random() < q
        tot = 0
        for _ in range(M):
            f = rng.random() < p
            tot += int(f and not cc) - int(cc and not f)
        xs.append(tot / M)
    return xs


t0 = time.time()
print("n=%d m=%d R=%d  boundary null; x=%.4f" % (N, M, R, X), flush=True)
for name, (smp, comps) in POPS.items():
    gam = exact_gamma(comps, M)
    rng = random.Random(60606 + 10 * M + ord(name[0]) + (3 if name[1] == "1" else 0) + (5 if name[1] == "2" else 0))
    go_p = go0 = go1 = 0
    nv = 0
    sT = sG = sTG = sTT = sE = 0.0
    win = {0.15: [0, 0.0, 0.0, 0.0], 0.30: [0, 0.0, 0.0, 0.0]}   # count, sum D, sum eps, sum T
    bins = [[0, 0.0] for _ in BINS]
    for _ in range(R):
        xs = draw(smp, rng)
        mean = sum(xs) / N
        d2 = sum((x - mean) ** 2 for x in xs)
        if d2 <= 0:
            continue
        T = (mean - DELTA) / math.sqrt(d2 / (N - 1) / N)
        g = (sum((x - mean) ** 3 for x in xs) / N) / (d2 / N) ** 1.5
        c = (2 * T * T + 1) / (6 * SQ)
        S0 = T + c * gam
        S1 = T + c * g
        eps = g - gam
        D = c * eps
        go_p += T > X
        go0 += S0 > X
        go1 += S1 > X
        nv += 1
        sT += T; sG += g; sTG += T * g; sTT += T * T; sE += eps
        for h, w in win.items():
            if abs(S0 - X) < h:
                w[0] += 1; w[1] += D; w[2] += eps; w[3] += T
        for k, (lo, hi) in enumerate(BINS):
            if lo <= T < hi:
                bins[k][0] += 1; bins[k][1] += eps
                break
    mT, mG = sT / nv, sG / nv
    beta = (sTG / nv - mT * mG) / (sTT / nv - mT * mT)
    mE = sE / nv
    w = win[0.15]
    eps_bd = w[2] / w[0]
    eps_reg = mE + beta * (w[3] / w[0] - mT)
    print("%s m=%d gamma=%+.3f | size plain %.4f  J(oracle) %.4f  J(g-hat) %.4f | OBSERVED gap %+.3f pt | E[eps] all %+.3f  E[eps|bdry] %+.3f  (regression proxy %+.3f)  n_win %d | FLUX h=.15 %+.3f pt  h=.30 %+.3f pt   (%.0fs)" % (
        name, M, gam, go_p / R, go0 / R, go1 / R, 100 * (go1 - go0) / R, mE, eps_bd, eps_reg, w[0],
        100 * win[0.15][1] / (2 * 0.15 * R), 100 * win[0.30][1] / (2 * 0.30 * R), time.time() - t0), flush=True)
    print("     E[g-gamma | T bin]: " + "  ".join("[%s,%s): %+.2f (n=%d)" % (("-inf" if lo < -50 else lo), ("inf" if hi > 50 else hi), (b[1] / b[0] if b[0] else float('nan')), b[0]) for (lo, hi), b in zip(BINS, bins)), flush=True)
