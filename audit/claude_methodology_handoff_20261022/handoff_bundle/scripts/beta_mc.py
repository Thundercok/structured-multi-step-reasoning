"""MC check of PILOT-CONSISTENT q_i shapes: q ~ Beta(mu s, (1-mu) s), effect model E2 (headroom) or E3 (logit shift), both with mean effect exactly 0.10 (boundary).
n = 60, CONT once, m F draws.  Per population and tail: exact (gamma, kurt), 2nd-order Edgeworth plain-t size, MC plain-t size, Johnson(gamma-hat), Johnson(exact gamma),
the MC critical values q_.025(T), q_.975(T) (what a perfectly calibrated test would need) and the MC size of FIXED thresholds 2.238 / 2.448 / 2.647 (= T_lo(-1.0/-1.6/-2.0) at n=60).
usage: beta_mc.py M R"""
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import beta_exact as be  # noqa: E402

M, R = int(sys.argv[1]), int(sys.argv[2])
DELTA, N, X = 0.10, 60, 2.0010
SQ = math.sqrt(N)
FIXED = (2.238, 2.448, 2.647)
POPS = [("PC0 mu.50 s.5  E3", 0.50, 0.5, "E3"), ("PC1 mu.667 s1.0 E2", 0.667, 1.0, "E2"), ("PC2 mu.667 s.5 E3", 0.667, 0.5, "E3"),
        ("PC3 mu.78 s1.46 E3", 0.78, 1.46, "E3"), ("PC4 mu.78 s.5 E3", 0.78, 0.5, "E3")]


def solve_theta(grid):
    lo, hi = 0.0, 40.0
    for _ in range(100):
        th = 0.5 * (lo + hi)
        eff = sum(w * (be.expit(be.logit(q) + th) - q) for w, q in grid)
        lo, hi = (th, hi) if eff < DELTA else (lo, th)
    return 0.5 * (lo + hi)


def make_sampler(mu_t, s, model, grid):
    a, b = mu_t * s, (1 - mu_t) * s
    mu = sum(w * q for w, q in grid)
    if model == "E2":
        k2 = DELTA / (1 - mu)
        return lambda r: (lambda q: (q, q + k2 * (1 - q)))(r.betavariate(a, b))
    th = solve_theta(grid)
    return lambda r: (lambda q: (q, be.expit(be.logit(q) + th)))(r.betavariate(a, b))


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
print("n=%d m=%d R=%d (MC SE of a 2.5%% cell %.2f pt)" % (N, M, R, 100 * math.sqrt(0.025 * 0.975 / R)), flush=True)
for name, mu_t, s, model in POPS:
    grid = be.beta_grid(mu_t * s, (1 - mu_t) * s)
    comps = be.with_effect(grid, model)
    mean_x, var_x, gam, kur = be.exact(comps, M)
    e_go, e_no = be.predict(gam, kur)
    smp = make_sampler(mu_t, s, model, grid)
    rng = random.Random(9001 + 17 * M + int(1000 * mu_t) + int(10 * s))
    ts, c = [], {"gj": 0, "nj": 0, "go": 0, "no": 0}
    for _ in range(R):
        xs = draw_data(smp, rng)
        mean = sum(xs) / N
        d2 = sum((x - mean) ** 2 for x in xs)
        if d2 <= 0:
            continue
        T = (mean - DELTA) / math.sqrt(d2 / (N - 1) / N)
        g = (sum((x - mean) ** 3 for x in xs) / N) / (d2 / N) ** 1.5
        cT = (2 * T * T + 1) / (6 * SQ)
        ts.append(T)
        tj, to = T + g * cT, T + gam * cT
        c["gj"] += tj > X
        c["nj"] += tj < -X
        c["go"] += to > X
        c["no"] += to < -X
    ts.sort()
    L = len(ts)
    f = lambda v: 100 * v / L
    go_plain = f(L - sum(1 for t in ts if t <= X))
    no_plain = f(sum(1 for t in ts if t < -X))
    fixed = [f(sum(1 for t in ts if t < -cc)) for cc in FIXED]
    print("%s m=%d | exact: mean %.3f gamma %+.2f kurt %+.1f | Edgeworth GO %.2f NO %.2f | MC plain GO %.2f NO %.2f | J(g^) GO %.2f NO %.2f | J(g) GO %.2f NO %.2f | "
          "needed c: GO %.3f NO %.3f | NO-GO size at 2.238/2.448/2.647: %.2f/%.2f/%.2f  (%.0fs)" % (
              name, M, mean_x, gam, kur, e_go, e_no, go_plain, no_plain, f(c["gj"]), f(c["nj"]), f(c["go"]), f(c["no"]),
              ts[int(0.975 * L)], -ts[int(0.025 * L)], fixed[0], fixed[1], fixed[2], time.time() - t0), flush=True)
