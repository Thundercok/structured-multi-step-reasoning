"""PILOT-CONSISTENT q_i shapes.  Pilot facts used: CONT accuracy 8/12 = 0.667 and 0/12 between-draw flips => CP95 upper of the flip probability 0.2646 => v_CONT = E[q(1-q)] <= 0.132.
For q ~ Beta(mu*s, (1-mu)*s):  v = mu(1-mu) s/(s+1)  =>  v <= 0.132 at mu = 0.667 needs s <= 1.46 (polarised q_i).
Exact (gamma, excess kurtosis) of x_i = mean_j F_ij - C_i (CONT once) at the boundary (mean effect = 0.10) and 2nd-order Edgeworth plain-t sizes (n=60).
Effect models (both calibrated to mean effect exactly 0.10; the per-question effect is heterogeneous):
  E2 headroom : p = q + 0.10 (1-q)/(1-mu)             (effect shrinks at ceiling)
  E3 logit    : p = expit(logit(q) + theta), theta solved (a question-difficulty / ability-shift model; effect ~ 0 at q ~ 0 or 1)
usage: beta_exact.py            (prints the table)"""
import math

N, DELTA = 60, 0.10
Phi = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
phi = lambda x: math.exp(-x * x / 2) / math.sqrt(2 * math.pi)


def betacf(a, b, x):
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > 1e-300 else 1e-300)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1 + aa / c
        c = c if abs(c) > 1e-300 else 1e-300
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1 + aa / c
        c = c if abs(c) > 1e-300 else 1e-300
        de = d * c
        h *= de
        if abs(de - 1) < 3e-14:
            break
    return h


def betainc(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1) / (a + b + 2):
        return bt * betacf(a, b, x) / a
    return 1 - bt * betacf(b, a, 1 - x) / b


def beta_grid(a, b, K=2500):                     # (weight, q) cells, Chebyshev-spaced, exact cell masses
    xs = [0.5 * (1 - math.cos(math.pi * j / K)) for j in range(K + 1)]
    cdf = [betainc(a, b, x) for x in xs]
    return [(cdf[j + 1] - cdf[j], 0.5 * (xs[j] + xs[j + 1])) for j in range(K)]


def expit(z):
    return 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))


def logit(q):
    q = min(max(q, 1e-12), 1 - 1e-12)
    return math.log(q / (1 - q))


def with_effect(grid, model):
    mu = sum(w * q for w, q in grid)
    if model == "E2":
        return [(w, q, q + DELTA * (1 - q) / (1 - mu)) for w, q in grid]
    lo, hi = 0.0, 40.0                           # E3: bisection on theta
    for _ in range(100):
        th = 0.5 * (lo + hi)
        eff = sum(w * (expit(logit(q) + th) - q) for w, q in grid)
        lo, hi = (th, hi) if eff < DELTA else (lo, th)
    return [(w, q, expit(logit(q) + th)) for w, q in grid]


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
    return mu, c2, c3 / c2 ** 1.5, c4 / c2 ** 2 - 3


def predict(g, k):
    x = 2.0010 * math.sqrt(N / (N - 1))
    q1 = g * (2 * x * x + 1) / 6
    q2 = x * (k * (x * x - 3) / 12 - g * g * (x ** 4 + 2 * x * x - 3) / 18 - (x * x + 3) / 4)
    a, b = q1 * phi(x) / math.sqrt(N), q2 * phi(x) / N
    return 100 * (1 - (Phi(x) + a + b)), 100 * (Phi(-x) + a - b)


if __name__ == "__main__":
    print("q ~ Beta(mu s, (1-mu) s); n=60; boundary mean effect 0.10 | v=E[q(1-q)] (pilot bound v<=0.132) | per effect model: Var(effect), m=3 and m=5: gamma, exKurt, plain-t GO%, NO-GO% (2nd-order Edgeworth)")
    for mu in (0.50, 0.667, 0.78):
        for s in (0.5, 1.0, 1.46, 2.0, 4.0):
            grid = beta_grid(mu * s, (1 - mu) * s)
            v = sum(w * q * (1 - q) for w, q in grid)
            cells = []
            for model in ("E2", "E3"):
                comps = with_effect(grid, model)
                vareff = sum(w * (p - q) ** 2 for w, q, p in comps) - DELTA ** 2
                row = []
                for m in (3, 5):
                    _, _, g, k = exact(comps, m)
                    go, no = predict(g, k)
                    row.append("%+.2f %+4.1f %.2f %.2f" % (g, k, go, no))
                cells.append("%s var(eff)=%.3f | m3 %s | m5 %s" % (model, vareff, row[0], row[1]))
            print("mu=%.3f s=%.2f v=%.3f%s || %s || %s" % (mu, s, v, "*" if v <= 0.132 else " ", cells[0], cells[1]))
