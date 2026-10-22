"""Paired GO / NO-GO / UNDETERMINED rule for two binary arms paired by item (stdlib only, v2).

b = items X correct & Y wrong, c = reverse, n = all paired items, delta = P(X) - P(Y).
ONE method decides every state: Tango (1998) score statistic Z(delta) evaluated at delta_prac.
    GO            CI lower > delta_prac   <=>  Z(delta_prac) >  z
    NO-GO         CI upper < delta_prac   <=>  Z(delta_prac) < -z
    UNDETERMINED  otherwise
Exact McNemar p is descriptive only; it never changes a state.

    python gonogo.py selftest    cross-checks, raw numbers
    python gonogo.py report      tables quoted in the advice
    python gonogo.py operating   actual size at the boundary + n for 80% power
    python gonogo.py calibrate   z* that holds worst-case size at 2.5% per side
"""
import random
import sys
from functools import lru_cache
from math import comb, copysign, exp, inf, lgamma, log, log1p, sqrt

Z = 1.959963984540054  # two-sided 95% == 2.5% in each one-sided test


def mcnemar_exact_p(b, c):
    m = b + c
    return 1.0 if m == 0 else min(1.0, 2 * sum(comb(m, i) for i in range(min(b, c) + 1)) / 2**m)


def _q(b, c, n, d):
    """restricted MLE of p01 given p10 - p01 = d: positive root of 2n q^2 + B q - c d (1-d) = 0"""
    B = -(b + c) + d * (2 * n - b + c)
    root = sqrt(max(B * B + 8 * n * c * d * (1 - d), 0.0))
    if B > 0:  # B > 0 implies d > 0; this form avoids cancellation
        return 2 * c * d * (1 - d) / (B + root)
    return (-B + root) / (4 * n)


def tango_z(b, c, n, d):
    num = b - c - n * d
    var = 0.0 if abs(d) >= 1.0 else n * (2 * _q(b, c, n, d) + d * (1 - d))
    if var <= 0.0:  # degenerate boundary: 0/0 is consistent with the data, x/0 is not
        return 0.0 if abs(num) < 1e-9 else copysign(inf, num)
    return num / sqrt(var)


def tango_ci(b, c, n, z=Z):
    """score CI by inversion; endpoints +-1 are kept when the data allow them (no clamp)"""

    def root(target):  # Z is decreasing in d
        lo, hi = -1.0, 1.0
        for _ in range(100):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if tango_z(b, c, n, mid) > target else (lo, mid)
        return (lo + hi) / 2

    lower = -1.0 if tango_z(b, c, n, -1.0) <= z else root(z)
    upper = 1.0 if tango_z(b, c, n, 1.0) >= -z else root(-z)
    return lower, upper


def decide(b, c, n, delta, z=Z):
    t = tango_z(b, c, n, delta)
    return "GO" if t > z else "NO-GO" if t < -z else "UNDETERMINED"


@lru_cache(maxsize=None)
def cuts(n, delta, z=Z):
    """per s=b+c: first b that is GO (s+1 if none), last b that is NO-GO (-1 if none).
    Relies on Z increasing in b at fixed s; selftest verifies it by brute force."""
    go, no = [], []
    for s in range(n + 1):
        lo, hi = 0, s + 1
        while lo < hi:
            mid = (lo + hi) // 2
            lo, hi = (lo, mid) if tango_z(mid, s - mid, n, delta) > z else (mid + 1, hi)
        go.append(lo)
        lo, hi = -1, s
        while lo < hi:
            mid = (lo + hi + 1) // 2
            lo, hi = (mid, hi) if tango_z(mid, s - mid, n, delta) < -z else (lo, mid - 1)
        no.append(lo)
    return tuple(go), tuple(no)


def _pmf(n, k, p):
    if not 0 <= k <= n:
        return 0.0
    if p <= 0.0:
        return float(k == 0)
    if p >= 1.0:
        return float(k == n)
    return exp(lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1) + k * log(p) + (n - k) * log1p(-p))


def _tail(s, k, p):  # P(Bin(s,p) >= k)
    return 1.0 if k <= 0 else 0.0 if k > s else sum(_pmf(s, j, p) for j in range(k, s + 1))


def _head(s, k, p):  # P(Bin(s,p) <= k)
    return 0.0 if k < 0 else 1.0 if k >= s else sum(_pmf(s, j, p) for j in range(k + 1))


def state_probs(n, effect, d, delta, z=Z):
    """(P(GO), P(NO-GO), P(UNDETERMINED)) for true P(X)-P(Y)=effect and discordance probability d"""
    if abs(effect) > d + 1e-12:
        raise ValueError("|effect| cannot exceed the discordance probability d")
    go, no = cuts(n, delta, z)
    pi = ((d + effect) / 2) / d if d > 0 else 0.5
    pgo = pno = 0.0
    for s in range(n + 1):
        ps = _pmf(n, s, d)
        if ps < 1e-16:
            continue
        pgo += ps * _tail(s, go[s], pi)
        pno += ps * _head(s, no[s], pi)
    return pgo, pno, max(0.0, 1.0 - pgo - pno)


def prob_curve(delta, effect, d, state, n_lo, n_hi, step=1, z=Z):
    k = 0 if state == "GO" else 1
    return {n: state_probs(n, effect, d, delta, z)[k] for n in range(n_lo, n_hi + 1, step)}


def first_n(curve, target=0.80):
    return next((n for n, p in curve.items() if p >= target), None)


def stable_n(curve, target=0.80, window=30):
    """smallest n whose power stays >= target for the next `window` values (power is sawtooth in n)"""
    ns = sorted(curve)
    for n in ns:
        if n + window <= ns[-1] and all(curve[m] >= target for m in ns if n <= m <= n + window):
            return n
    return None


def find_n(delta, effect, d, state, target=0.80, n_hi=1500, window=30, coarse=10, z=Z):
    """(first n, stable n) with P(state) >= target; coarse scan, then step-1 refinement around the first hit"""
    k = 0 if state == "GO" else 1

    def p(n):
        return state_probs(n, effect, d, delta, z)[k]

    n = coarse
    while n <= n_hi and p(n) < target:
        n += coarse
    if n > n_hi:
        return None, None
    curve = {m: p(m) for m in range(max(10, n - 3 * coarse), n + window + coarse + 1)}
    return first_n(curve, target), stable_n(curve, target, window)


def worst_size(n, delta, z=Z):
    """(max P(GO), max P(NO-GO)) when the true effect sits exactly on delta_prac, max over discordance d"""
    ds = sorted({round(delta + 0.01 * i, 4) for i in range(91) if delta + 0.01 * i <= 0.9}
                | {round(delta + 0.001 * i, 4) for i in range(61)})
    res = [state_probs(n, delta, d, delta, z)[:2] for d in ds]
    return max(r[0] for r in res), max(r[1] for r in res)


def calibrate_z(n, delta, alpha=0.025, coarse=0.02, fine=0.002, z_max=3.0):
    """first z on a grid (coarse scan, then fine scan inside the last coarse step) whose worst-case false-GO
    and false-NO-GO are both <= alpha. Size is sawtooth in z, so this is a verified choice, not a global minimum."""

    def ok(z):
        return max(worst_size(n, delta, z)) <= alpha

    if ok(Z):
        return Z
    z = Z
    while z < z_max:
        z += coarse
        if ok(z):
            break
    else:
        raise RuntimeError("no feasible z <= z_max")
    k = 1
    while Z + 0 < z - coarse + k * fine < z:
        if ok(z - coarse + k * fine):
            return z - coarse + k * fine
        k += 1
    return z


def p_at_least(N, prev, k):
    return 1.0 - sum(_pmf(N, j, prev) for j in range(k))


def screening_n(prev, k=60, conf=0.95):
    """smallest N with P(Bin(N, prev) >= k) >= conf (expected-count planning is only the 50% point)"""
    lo, hi = k, int(4 * k / prev) + 100
    while lo < hi:
        mid = (lo + hi) // 2
        lo, hi = (lo, mid) if p_at_least(mid, prev, k) >= conf else (mid + 1, hi)
    return lo


def clopper_pearson(x, n, alpha=0.05):
    def cdf(k, p):
        return sum(_pmf(n, i, p) for i in range(k + 1))

    def bis(f):
        lo, hi = 0.0, 1.0
        for _ in range(200):
            mid = (lo + hi) / 2
            lo, hi = (lo, mid) if f(mid) > 0 else (mid, hi)
        return (lo + hi) / 2

    lo = 0.0 if x == 0 else bis(lambda p: (1 - cdf(x - 1, p)) - alpha / 2)
    hi = 1.0 if x == n else bis(lambda p: alpha / 2 - cdf(x, p))
    return lo, hi


# ----------------------------------------------------------------------------- selftest
def _q_bisect(b, c, n, d):
    """independent q-hat: bisection on the profile-likelihood score equation (v1 method)"""
    r = n - b - c
    lo, hi = max(0.0, -d) + 1e-13, (1 - d) / 2 - 1e-13

    def g(q):
        return (b / (q + d) if b else 0.0) + (c / q if c else 0.0) - (2 * r / (1 - 2 * q - d) if r else 0.0)

    if g(lo) <= 0:
        return lo
    if g(hi) >= 0:
        return hi
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if g(mid) > 0 else (lo, mid)
    return (lo + hi) / 2


def selftest():
    rnd = random.Random(1)
    worst = 0.0
    for _ in range(4000):
        n = rnd.randint(2, 120)
        b = rnd.randint(0, n)
        c = rnd.randint(0, n - b)
        d = rnd.uniform(-0.98, 0.98)
        a, bq = _q(b, c, n, d), _q_bisect(b, c, n, d)
        worst = max(worst, abs(a - bq))
    print(f"[1] closed-form q-hat vs bisection q-hat, 4000 random cases: max |diff| = {worst:.2e}")
    assert worst < 1e-8

    bad = 0
    for _ in range(1500):
        n = rnd.randint(2, 80)
        b = rnd.randint(0, n)
        c = rnd.randint(0, n - b)
        zs = [tango_z(b, c, n, -0.98 + 1.96 * i / 60) for i in range(61)]
        bad += any(zs[i + 1] > zs[i] + 1e-9 for i in range(60))
    print(f"[2] Z(delta) decreasing in delta, 1500 random tables: violations = {bad}")
    assert bad == 0

    bad = checked = 0
    for _ in range(3000):
        n = rnd.randint(2, 90)
        b = rnd.randint(0, n)
        c = rnd.randint(0, n - b)
        delta = rnd.choice([0.0, 0.05, 0.1, 0.15, 0.2, -0.05])
        lo, hi = tango_ci(b, c, n)
        st = "GO" if lo > delta + 1e-9 else "NO-GO" if hi < delta - 1e-9 else "UNDETERMINED"
        near = min(abs(lo - delta), abs(hi - delta)) < 1e-7
        if not near:
            checked += 1
            bad += st != decide(b, c, n, delta)
    print(f"[3] state from CI endpoints == state from Z(delta_prac): {checked} cases, mismatches = {bad}")
    assert bad == 0

    bad = 0
    for n in (7, 12, 25, 40):
        for delta in (0.0, 0.05, 0.1, 0.2):
            go, no = cuts(n, delta)
            for s in range(n + 1):
                for b in range(s + 1):
                    st = decide(b, s - b, n, delta)
                    st2 = "GO" if b >= go[s] else "NO-GO" if b <= no[s] else "UNDETERMINED"
                    bad += st != st2
                zs = [tango_z(b, s - b, n, delta) for b in range(s + 1)]
                bad += any(zs[i + 1] < zs[i] - 1e-9 for i in range(s))
    print(f"[4] cut-point shortcut vs full (b,c) enumeration, Z increasing in b at fixed s: mismatches = {bad}")
    assert bad == 0

    n, eff, d, delta = 150, 0.2, 0.3, 0.1
    pg, pn, pu = state_probs(n, eff, d, delta)
    r, hits = random.Random(7), [0, 0, 0]
    reps = 60000
    for _ in range(reps):
        s = r.binomialvariate(n, d)
        b = r.binomialvariate(s, (d + eff) / 2 / d)
        hits["GO NO-GO UNDETERMINED".split().index(decide(b, s - b, n, delta))] += 1
    mc = [h / reps for h in hits]
    print(f"[5] enumeration {pg:.4f}/{pn:.4f}/{pu:.4f} vs Monte Carlo {mc[0]:.4f}/{mc[1]:.4f}/{mc[2]:.4f} (n={n}, +20pp, d=.3, delta_prac=.10)")
    assert abs(pg - mc[0]) < 0.01 and abs(pn - mc[1]) < 0.01

    lo, hi = tango_ci(12, 0, 12)
    lo2, hi2 = tango_ci(0, 12, 12)
    print(f"[6] boundaries: CI(b=n,c=0) upper = {hi!r}; CI(b=0,c=n) lower = {lo2!r}")
    assert hi == 1.0 and lo2 == -1.0
    lo, hi = tango_ci(4, 0, 12)
    print(f"[7] v1 row 4-0, n=12: CI [{lo:+.3f}, {hi:+.3f}]  exact p = {mcnemar_exact_p(4, 0):.4f}  Z(0) = {tango_z(4, 0, 12, 0.0):.4f}")
    assert round(lo, 3) == 0.010 and round(hi, 3) == 0.609
    print("selftest OK")


# ----------------------------------------------------------------------------- report
def report():
    print("== (1) n=1000, b=40, c=10 ==")
    lo, hi = tango_ci(40, 10, 1000)
    print(f"exact p = {mcnemar_exact_p(40, 10):.6f}; Tango CI = [{100 * lo:.2f}, {100 * hi:.2f}] pp; delta_hat = {100 * 30 / 1000:.1f} pp")
    print(f"old rule: sign-test GO = {mcnemar_exact_p(40, 10) < .05}, CI-upper NO-GO(10pp) = {hi < .10};  new 3-state rule (10pp): {decide(40, 10, 1000, .10)}")

    print("\n== (2) 4-0 : score vs exact ==")
    for n in (4, 12, 40):
        lo, hi = tango_ci(4, 0, n)
        print(f"n={n:2d}: Tango CI [{lo:+.3f}, {hi:+.3f}], Z(0)={tango_z(4, 0, n, 0.0):.3f}, exact p={mcnemar_exact_p(4, 0):.4f}")

    print("\n== (3a) clamp: b=n,c=0 ==")
    for n in (5, 12, 30):
        print(f"n={n}: upper = {tango_ci(n, 0, n)[1]!r}, lower of (0,{n}) = {tango_ci(0, n, n)[0]!r}")

    print("\n== (3b) v1 NO-GO rule (true effect 0, need CI upper < delta_prac, power>=.80): step 2 vs step 1 ==")
    for d in (0.2, 0.3):
        for dp in (0.20, 0.15, 0.10):
            c2 = prob_curve(dp, 0.0, d, "NO-GO", 20, 600, 2)
            c1 = prob_curve(dp, 0.0, d, "NO-GO", 20, 600, 1)
            print(f"d={d} delta_prac={dp:.2f}: even-n only -> {first_n(c2)}; all n -> {first_n(c1)}; power at those n = {c2[first_n(c2)]:.4f}, {c1[first_n(c1)]:.4f}")

    print("\n== (4) screening: P(Bin(N,.08) >= 60) ==")
    print(f"N=750: {p_at_least(750, .08, 60):.4f}; smallest N for 95%: {screening_n(.08)}; 1/12 Clopper-Pearson = {clopper_pearson(1, 12)}")
    print("N for >=60 target items at 95% (prevalence: N): " + "; ".join(f"{p}: {screening_n(p)}" for p in (0.04, 0.06, 0.08, 0.10, 0.15, 0.25, 5 / 12)))

    print("\n== N=12, true +20pp, d=.3 : new-rule P(GO) by delta_prac ==")
    for dp in (0.0, 0.05, 0.10):
        print(f"delta_prac={dp:.2f}: P(GO)={state_probs(12, .2, .3, dp)[0]:.4f}  P(NO-GO | effect 0)={state_probs(12, 0.0, .3, dp)[1]:.4f}")


def _fs(dp, eff, d, state):
    if eff > d:
        return "n/a"
    first, stable = find_n(dp, eff, d, state)
    return f"{first}/{stable}"


def calibration():
    print("== z calibration: worst-case size at the boundary, nominal z=1.96 -> calibrated z* (alpha=.025 per side) ==")
    for dp, n in ((0.10, 100), (0.10, 150), (0.10, 250), (0.05, 150)):
        zc = calibrate_z(n, dp)
        g0, h0 = worst_size(n, dp)
        g1, h1 = worst_size(n, dp, zc)
        extra = ""
        if (dp, n) == (0.10, 250):
            extra = f" | power(+20pp, d=.3): {state_probs(n, .2, .3, dp)[0]:.3f} -> {state_probs(n, .2, .3, dp, zc)[0]:.3f}"
        print(f"delta_prac={dp:.2f} n={n:3d}: size GO/NO-GO {g0:.4f}/{h0:.4f} -> z*={zc:.3f}: {g1:.4f}/{h1:.4f}{extra}")
    print("\n== N=12 pilot, delta_prac=.10, d=.3 ==")
    for eff in (0.20, 0.0):
        pg, pn, pu = state_probs(12, eff, 0.3, 0.10)
        print(f"true effect {eff:+.2f}: P(GO)={pg:.4f} P(NO-GO)={pn:.4f} P(UNDETERMINED)={pu:.4f}")


def operating():
    def grid(dp):
        return [dp + 0.01 * i for i in range(90) if dp + 0.01 * i <= 0.9]

    print("== actual size at the boundary (true effect == delta_prac): worst case over discordance d ==")
    print("delta_prac     n | max P(GO) at d      | max P(NO-GO) at d")
    for dp in (0.10, 0.05):
        for n in (50, 100, 150, 250):
            res = [(d, *state_probs(n, dp, d, dp)[:2]) for d in grid(dp)]
            g, h = max(res, key=lambda r: r[1]), max(res, key=lambda r: r[2])
            print(f"{dp:.2f}       {n:5d} | {g[1]:.4f} (d={g[0]:.2f})   | {h[2]:.4f} (d={h[0]:.2f})")

    print("\n== n for power >= .80: first / stable(30 consecutive n) ==")
    ds = (0.2, 0.3, 0.4)
    for dp, effs in ((0.10, (0.15, 0.20, 0.25)), (0.05, (0.10, 0.15))):
        for eff in effs:
            print(f"GO    delta_prac={dp:.2f} effect={eff:.2f} | " + " | ".join(f"d={d}: {_fs(dp, eff, d, 'GO')}" for d in ds))
    for dp, effs in ((0.10, (0.0, 0.05)), (0.05, (0.0,))):
        for eff in effs:
            print(f"NO-GO delta_prac={dp:.2f} effect={eff:.2f} | " + " | ".join(f"d={d}: {_fs(dp, eff, d, 'NO-GO')}" for d in ds))


if __name__ == "__main__":
    {"selftest": selftest, "report": report, "operating": operating, "calibrate": calibration}[sys.argv[1] if len(sys.argv) > 1 else "selftest"]()
