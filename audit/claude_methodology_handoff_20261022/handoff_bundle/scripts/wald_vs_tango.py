"""Is the equal-cost Tango advantage real, and is PC4's alternative feasible?  At the SAME feasible alternative e_high (<= 0.9 x headroom = 1 - mean q) compare
 (a) cluster t, m=3, n=60, ORACLE (size-adjusted at the boundary) threshold;  (b) Wald t on paired differences, m=1, n=70, ORACLE threshold;  (c) Tango m=1, n=70, calibrated z* (symmetric, worst-case over discordance).
(b) and (c) use the SAME simulated paired data.  GO power at e_high, NO-GO power at e=0, size at the boundary e=0.10.
NOTE: power_cost.py used e=0.25 for PC4, but its headroom is only 1-0.78=0.22, so its 'e=0.25' power was really e=0.22 (p=1 for all questions).  usage: wald_vs_tango.py R"""
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import beta_exact as be  # noqa: E402
import gonogo as g  # noqa: E402

R = int(sys.argv[1])
DELTA, N3, M3, N1 = 0.10, 60, 3, 70
ZT = g.calibrate_z(N1, DELTA)


def theta_for(grid, e):
    if e == 0:
        return 0.0
    lo, hi = 0.0, 40.0
    for _ in range(100):
        th = 0.5 * (lo + hi)
        eff = sum(w * (be.expit(be.logit(q) + th) - q) for w, q in grid)
        lo, hi = (th, hi) if eff < e else (lo, th)
    return 0.5 * (lo + hi)


def beta_pop(mu_t, s, model):
    a, b = mu_t * s, (1 - mu_t) * s
    grid = be.beta_grid(a, b)
    mu = sum(w * q for w, q in grid)

    def sampler(e):
        if model == "E2":
            k2 = e / (1 - mu)
            return lambda r: (lambda q: (q, q + k2 * (1 - q)))(r.betavariate(a, b))
        th = theta_for(grid, e)
        return lambda r: (lambda q: (q, be.expit(be.logit(q) + th)))(r.betavariate(a, b))
    return sampler, 1 - mu


def hom_pop(qs, mu):
    return (lambda e: (lambda r: (lambda q: (q, q + e))(qs(r)))), 1 - mu


POPS = {
    "PC1 E2 mu.667 s1.0": (beta_pop(0.667, 1.0, "E2"), 0.25),
    "PC2 E3 mu.667 s.5": (beta_pop(0.667, 0.5, "E3"), 0.25),
    "PC4 E3 mu.78 s.5": (beta_pop(0.78, 0.5, "E3"), 0.18),
    "NEG1 U(.05,.65) hom": (hom_pop(lambda r: r.uniform(0.05, 0.65), 0.35), 0.25),
    "B mix .05/.40 @.6 hom": (hom_pop(lambda r: 0.05 if r.random() < 0.6 else 0.40, 0.6 * 0.05 + 0.4 * 0.40), 0.25),
}


def cluster_T(sampler, rng):
    ts = []
    for _ in range(R):
        xs = []
        for _ in range(N3):
            q, p = sampler(rng)
            cc = rng.random() < q
            tot = 0
            for _ in range(M3):
                f = rng.random() < p
                tot += int(f and not cc) - int(cc and not f)
            xs.append(tot / M3)
        mean = sum(xs) / N3
        d2 = sum((x - mean) ** 2 for x in xs)
        ts.append(-99.0 if d2 <= 0 else (mean - DELTA) / math.sqrt(d2 / (N3 - 1) / N3))
    return sorted(ts)


def paired(sampler, rng):
    tw, dec = [], []
    for _ in range(R):
        b = c = 0
        for _ in range(N1):
            q, p = sampler(rng)
            cc = rng.random() < q
            f = rng.random() < p
            b += f and not cc
            c += cc and not f
        mean = (b - c) / N1
        d2 = (b + c) - (b - c) ** 2 / N1
        tw.append(-99.0 if d2 <= 0 else (mean - DELTA) / math.sqrt(d2 / (N1 - 1) / N1))
        dec.append(g.decide(b, c, N1, DELTA, ZT))
    return sorted(tw), dec


up = lambda ts, c: 100 * (len(ts) - sum(1 for t in ts if t <= c)) / len(ts)
lw = lambda ts, c: 100 * sum(1 for t in ts if t < -c) / len(ts)
t0 = time.time()
print("R=%d | Tango z*(n=70)=%.3f | cluster = m=3,n=60 ; paired = m=1,n=70 (Wald t and Tango on the same data)" % (R, ZT), flush=True)
for name, ((mk, headroom), e_hi) in POPS.items():
    rng = random.Random(777 + sum(map(ord, name)))
    res = {}
    for e in (0.0, 0.10, e_hi):
        cl = cluster_T(mk(e), rng)
        tw, dec = paired(mk(e), rng)
        res[e] = (cl, tw, dec)
    cl_b, tw_b, dec_b = res[0.10]
    L = len(cl_b)
    goc_cl, noc_cl = cl_b[int(0.975 * L)], -cl_b[int(0.025 * L)]
    goc_tw, noc_tw = tw_b[int(0.975 * L)], -tw_b[int(0.025 * L)]
    cl_h, tw_h, dec_h = res[e_hi]
    cl_0, tw_0, dec_0 = res[0.0]
    print("== %s | headroom %.2f, e_high %.2f | oracle c (GO/NO): cluster %.3f/%.3f, Wald-paired %.3f/%.3f" % (name, headroom, e_hi, goc_cl, noc_cl, goc_tw, noc_tw))
    print("   GO power(e=%.2f): cluster plain %.1f oracle %.1f | Wald-paired plain %.1f oracle %.1f | Tango %.1f   || Tango size GO/NO %.2f/%.2f" % (
        e_hi, up(cl_h, 2.001), up(cl_h, goc_cl), up(tw_h, 2.001), up(tw_h, goc_tw), 100 * dec_h.count("GO") / len(dec_h),
        100 * dec_b.count("GO") / len(dec_b), 100 * dec_b.count("NO-GO") / len(dec_b)))
    print("   NO-GO power(e=0): cluster plain %.1f oracle %.1f | Wald-paired plain %.1f oracle %.1f | Tango %.1f   (%.0fs)" % (
        lw(cl_0, 2.001), lw(cl_0, noc_cl), lw(tw_0, 2.001), lw(tw_0, noc_tw), 100 * dec_0.count("NO-GO") / len(dec_0), time.time() - t0), flush=True)
