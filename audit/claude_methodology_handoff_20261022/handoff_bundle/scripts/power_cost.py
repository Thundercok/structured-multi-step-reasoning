"""PRICE OF NOT KNOWING gamma.  n=60 questions, CONT once, m F draws, boundary delta_prac=0.10.  One-sided decisions: GO if T>c_GO, NO-GO if T<-c_NO (T = (xbar-0.10)/se).
Fixed thresholds (n=60, Johnson-at-fixed-gamma0 == plain t with critical value T_lo(gamma0)):  c_GO = 2.001 (plain) | 2.156 (gamma_min=-0.7);
c_NO = 2.001 (plain) | 2.238 (gamma_max=+1.0) | 2.448 (+1.6) | 2.647 (+2.0).  ORACLE = per-population 2.5% quantile at the boundary (not realisable).
Tango (m=1, calibrated symmetric z*, worst-case over discordance) at n=60 and at the equal-COST n (70 for m=3, 80 for m=5; scenario costs c_fixed=11/question, c_F=1/draw - NOT the user's).
Populations: PC1/PC2/PC4 (Beta q_i, effect models E2/E3 recalibrated to each true effect e), NEG1 q~U(.05,.65) hom shift, B mix(.05,.40;.6) hom shift.
Effects e: 0.00 (NO-GO power), 0.10 (boundary = size), 0.25 (GO power).  usage: power_cost.py M R"""
import math, os, random, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import beta_exact as be
import gonogo as g

M, R = int(sys.argv[1]), int(sys.argv[2])
DELTA, N = 0.10, 60
SQ = math.sqrt(N)
CGO = (2.001, 2.156)
CNO = (2.001, 2.238, 2.448, 2.647)
NT = {3: 70, 5: 80}[M]
EFFECTS = (0.0, 0.10, 0.25)
ZS = {n: g.calibrate_z(n, DELTA) for n in (60, NT)}


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

    def comps_at_boundary():
        return be.with_effect(grid, model)
    return sampler, comps_at_boundary


def hom_pop(qsampler, qgrid):
    def sampler(e):
        return lambda r: (lambda q: (q, q + e))(qsampler(r))

    def comps_at_boundary():
        return [(w, q, q + DELTA) for w, q in qgrid]
    return sampler, comps_at_boundary


POPS = {
    "PC1 E2 mu.667 s1.0": beta_pop(0.667, 1.0, "E2"),
    "PC2 E3 mu.667 s.5": beta_pop(0.667, 0.5, "E3"),
    "PC4 E3 mu.78 s.5": beta_pop(0.78, 0.5, "E3"),
    "NEG1 U(.05,.65) hom": hom_pop(lambda r: r.uniform(0.05, 0.65), [(1 / 400, 0.05 + 0.60 * (i + 0.5) / 400) for i in range(400)]),
    "B mix .05/.40 @.6 hom": hom_pop(lambda r: 0.05 if r.random() < 0.6 else 0.40, [(0.6, 0.05), (0.4, 0.40)]),
}


def t_stats(sampler, rng):
    ts = []
    for _ in range(R):
        xs = []
        for _ in range(N):
            q, p = sampler(rng)
            cc = rng.random() < q
            tot = 0
            for _ in range(M):
                f = rng.random() < p
                tot += int(f and not cc) - int(cc and not f)
            xs.append(tot / M)
        mean = sum(xs) / N
        d2 = sum((x - mean) ** 2 for x in xs)
        ts.append(-99.0 if d2 <= 0 else (mean - DELTA) / math.sqrt(d2 / (N - 1) / N))
    return ts


def tango(sampler, n, rng):
    go = no = 0
    for _ in range(R):
        b = c = 0
        for _ in range(n):
            q, p = sampler(rng)
            cc = rng.random() < q
            f = rng.random() < p
            b += f and not cc
            c += cc and not f
        d = g.decide(b, c, n, DELTA, ZS[n])
        go += d == "GO"
        no += d == "NO-GO"
    return 100 * go / R, 100 * no / R


t0 = time.time()
print("n=%d m=%d R=%d | Tango z*: n=60 %.3f, n=%d %.3f | MC SE of a 50%% cell %.2f pt, of a 2.5%% cell %.2f pt" % (
    N, M, R, ZS[60], NT, ZS[NT], 100 * math.sqrt(0.25 / R), 100 * math.sqrt(0.025 * 0.975 / R)), flush=True)
for name, (mk, comps_b) in POPS.items():
    mu_x, var_x, gam, kur = be.exact([(w, q, p) for w, q, p in comps_b()], M)
    rng = random.Random(4242 + M * 13 + sum(map(ord, name)))
    T = {e: sorted(t_stats(mk(e), rng)) for e in EFFECTS}
    L = len(T[0.10])
    up = lambda ts, c: 100 * (len(ts) - sum(1 for t in ts if t <= c)) / len(ts)
    lw = lambda ts, c: 100 * sum(1 for t in ts if t < -c) / len(ts)
    c_go_or = T[0.10][int(0.975 * L)]
    c_no_or = -T[0.10][int(0.025 * L)]
    print("== %s | exact gamma %+.2f kurt %+.1f | oracle c_GO %.3f c_NO %.3f" % (name, gam, kur, c_go_or, c_no_or), flush=True)
    print("  GO  size(e=.10)  : " + "  ".join("c=%.3f: %.2f" % (c, up(T[0.10], c)) for c in CGO) + "  oracle: %.2f" % up(T[0.10], c_go_or))
    print("  GO  power(e=.25) : " + "  ".join("c=%.3f: %.1f" % (c, up(T[0.25], c)) for c in CGO) + "  oracle(c=%.3f): %.1f" % (c_go_or, up(T[0.25], c_go_or)))
    print("  NOGO size(e=.10) : " + "  ".join("c=%.3f: %.2f" % (c, lw(T[0.10], c)) for c in CNO) + "  oracle: %.2f" % lw(T[0.10], c_no_or))
    print("  NOGO power(e=0)  : " + "  ".join("c=%.3f: %.1f" % (c, lw(T[0.0], c)) for c in CNO) + "  oracle(c=%.3f): %.1f" % (c_no_or, lw(T[0.0], c_no_or)), flush=True)
    for n in (60, NT):
        sz = tango(mk(0.10), n, rng)
        pg = tango(mk(0.25), n, rng)
        pn = tango(mk(0.0), n, rng)
        print("  Tango n=%d z*=%.3f: size GO/NO %.2f/%.2f | GO power(e=.25) %.1f | NO-GO power(e=0) %.1f   (%.0fs)" % (n, ZS[n], sz[0], sz[1], pg[0], pn[1], time.time() - t0), flush=True)
