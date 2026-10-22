"""Paired-binary decision numbers for the q=1 follow-up advice (stdlib only).

b = #items where arm X correct & arm Y wrong, c = reverse, n = #items.
GO      : exact two-sided sign test p < .05 and b > c (single criterion; delta_min only sets n)
NO-GO   : upper end of the 95% Tango score CI for (X - Y) < delta_min
CI      : Tango (1998) score interval, computed here by numeric inversion
"""
import math
from math import comb, lgamma, log, sqrt

Z = 1.959963984540054


def tango_z(b, c, n, d0):
    r = n - b - c
    lo = max(0.0, -d0) + 1e-13
    hi = (1 - d0) / 2 - 1e-13
    if hi <= lo:
        return float("nan")

    def g(q):
        t = 0.0
        if b:
            t += b / (q + d0)
        if c:
            t += c / q
        if r:
            t -= 2 * r / (1 - 2 * q - d0)
        return t

    if g(lo) <= 0:
        q = lo
    elif g(hi) >= 0:
        q = hi
    else:
        a, bb = lo, hi
        for _ in range(80):
            m = (a + bb) / 2
            if g(m) > 0:
                a = m
            else:
                bb = m
        q = (a + bb) / 2
    var = n * ((q + d0) + q - d0 * d0)
    num = b - c - n * d0
    if var <= 0:
        return math.copysign(float("inf"), num) if num else 0.0
    return num / sqrt(var)


def solve(b, c, n, target, a, bb):
    fa = tango_z(b, c, n, a) - target
    fb = tango_z(b, c, n, bb) - target
    if fa < 0:
        return a
    if fb > 0:
        return bb
    for _ in range(60):
        m = (a + bb) / 2
        if tango_z(b, c, n, m) - target > 0:
            a = m
        else:
            bb = m
    return (a + bb) / 2


def tango_ci(b, c, n):
    dh = (b - c) / n
    lo = solve(b, c, n, Z, -0.999, dh)
    up = solve(b, c, n, -Z, dh, 0.999)
    return max(lo, -1.0), min(up, 1.0)


def sign_p(b, c):
    m = b + c
    if m == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(m, i) for i in range(k + 1)) / 2**m)


print("== n=12 paired outcomes: b=X-only correct, c=Y-only correct ==")
print(" b c | delta_hat | Tango 95% CI      | exact sign p")
for b, c in [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (6, 0), (3, 1), (4, 1), (5, 1), (6, 1), (7, 1), (5, 2)]:
    lo, up = tango_ci(b, c, 12)
    print(f"{b:2d} {c:2d} | {(b - c) / 12:+.3f}     | [{lo:+.3f}, {up:+.3f}] | {sign_p(b, c):.4f}")


def cp(x, n, alpha=0.05):
    def cdf(k, p):
        return sum(comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1))

    def bis(f):
        lo, hi = 0.0, 1.0
        for _ in range(200):
            m = (lo + hi) / 2
            if f(m) > 0:
                hi = m
            else:
                lo = m
        return (lo + hi) / 2

    lo = 0.0 if x == 0 else bis(lambda p: (1 - cdf(x - 1, p)) - alpha / 2)
    hi = 1.0 if x == n else bis(lambda p: alpha / 2 - cdf(x, p))
    return lo, hi


print("\n== Clopper-Pearson 95% for strata (descriptive only) ==")
for x, n in [(1, 12), (0, 3), (1, 3), (2, 3), (3, 3), (0, 5), (1, 5), (2, 5), (3, 5), (0, 7), (1, 7)]:
    lo, hi = cp(x, n)
    print(f"{x}/{n}: [{lo:.3f}, {hi:.3f}]")

# ---------- power by exact enumeration ----------
crit_cache = {}


def crit(m):
    """largest c such that exact two-sided sign p < .05 when b+c=m (b>c); -1 if none"""
    if m in crit_cache:
        return crit_cache[m]
    best = -1
    for c in range(0, m // 2 + 1):
        if 2 * sum(comb(m, i) for i in range(c + 1)) / 2**m < 0.05 and (m - c) > c:
            best = c
    crit_cache[m] = best
    return best


def logp(n, b, c, tb, tc):
    r = n - b - c
    if (b and tb <= 0) or (c and tc <= 0) or (r and (1 - tb - tc) <= 0):
        return float("-inf")
    v = lgamma(n + 1) - lgamma(b + 1) - lgamma(c + 1) - lgamma(r + 1)
    if b:
        v += b * log(tb)
    if c:
        v += c * log(tc)
    if r:
        v += r * log(1 - tb - tc)
    return v


def window(n, t):
    mu = n * t
    sd = sqrt(n * t * (1 - t)) + 1
    return max(0, int(mu - 8 * sd)), min(n, int(mu + 8 * sd) + 1)


def power_go(n, tb, tc, dmin):
    s = 0.0
    b0, b1 = window(n, tb)
    c0, c1 = window(n, tc)
    for b in range(b0, b1 + 1):
        for c in range(c0, c1 + 1):
            if b + c > n or b <= c:
                continue
            m = b + c
            if c <= crit(m):  # single criterion: exact two-sided sign test p<.05, b>c
                s += math.exp(logp(n, b, c, tb, tc))
    return s


def power_nogo(n, tb, tc, dmin):
    s = 0.0
    b0, b1 = window(n, tb)
    c0, c1 = window(n, tc)
    for b in range(b0, b1 + 1):
        for c in range(c0, c1 + 1):
            if b + c > n:
                continue
            if tango_z(b, c, n, dmin) < -Z:
                s += math.exp(logp(n, b, c, tb, tc))
    return s


print("\n== P(GO) at n=12 (exact sign p<.05, b>c) for a true effect of size delta ==")
for d, delta in [(0.3, 0.2), (0.4, 0.3), (0.3, 0.1)]:
    tb, tc = (d + delta) / 2, (d - delta) / 2
    print(f"d={d} true delta={delta}: P(GO)={power_go(12, tb, tc, delta):.3f}")

print("\n== P(NO-GO) at n=12 when true delta=0, d=.3, by excluded effect size ==")
print("; ".join(f"exclude>={x}: {power_nogo(12, .15, .15, x):.3f}" for x in (0.30, 0.20, 0.15, 0.10)))

print("\n== smallest n with power>=.80 ==")
print("GO (true delta = delta_min):")
for d in (0.2, 0.3, 0.4):
    row = []
    for delta in (0.20, 0.15, 0.10):
        tb, tc = (d + delta) / 2, (d - delta) / 2
        n = 10
        while n <= 400 and power_go(n, tb, tc, delta) < 0.80:
            n += 1
        row.append(f"delta={delta}: n={n}")
    print(f"  d={d}: " + "; ".join(row))

print("NO-GO (true delta = 0; need CI upper < delta_min):")
for d in (0.2, 0.3):
    row = []
    for delta in (0.20, 0.15, 0.10):
        n = 20
        while n <= 600 and power_nogo(n, d / 2, d / 2, delta) < 0.80:
            n += 1
        row.append(f"delta={delta}: n={n}")
    print(f"  d={d}: " + "; ".join(row))

print("\n== base items needed to get n_cw complete-wrong items at prevalence p ==")
for ncw in (60, 105):
    print(f"n_cw={ncw}: " + "; ".join(f"p={p}: {math.ceil(ncw / p)}" for p in (0.08, 0.15, 0.25)))
