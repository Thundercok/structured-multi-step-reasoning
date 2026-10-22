import math
import random
from statistics import NormalDist

nd = NormalDist()

print("== plan arithmetic (from the Phase 1/2 prompt) ==")
print("12*6*2+12+4 =", 12 * 6 * 2 + 12 + 4, "| over cap 136 by", 12 * 6 * 2 + 12 + 4 - 136, "| 12*2048 =", 12 * 2048)


def sign_p(n, k):
    """exact two-sided binomial(n, .5) p-value for k successes"""
    tail = sum(math.comb(n, i) for i in range(0, min(k, n - k) + 1)) / 2**n
    return min(1.0, 2 * tail)


print("\n== exact sign test, all discordant pairs in one direction ==")
for n in range(3, 9):
    print(f"n_discordant={n}: two-sided p={sign_p(n, n):.5f}")


def binom_cdf(k, n, p):
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(0, k + 1))


def cp(x, n, alpha=0.05):
    def bisect(f):
        lo, hi = 0.0, 1.0
        for _ in range(200):
            mid = (lo + hi) / 2
            if f(mid) > 0:
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2

    lo = 0.0 if x == 0 else bisect(lambda p: (1 - binom_cdf(x - 1, n, p)) - alpha / 2)
    hi = 1.0 if x == n else bisect(lambda p: alpha / 2 - binom_cdf(x, n, p))
    return lo, hi


print("\n== Clopper-Pearson 95% CI ==")
for x, n in ((2, 12), (3, 12), (5, 12), (6, 12), (9, 12), (2, 5), (1, 4)):
    lo, hi = cp(x, n)
    print(f"{x}/{n}: [{lo:.3f}, {hi:.3f}]")


def mcnemar_n(d, delta, alpha=0.05, power=0.80):
    za = nd.inv_cdf(1 - alpha / 2)
    zb = nd.inv_cdf(power)
    return ((za * math.sqrt(d) + zb * math.sqrt(d - delta**2)) / delta) ** 2


print("\n== McNemar paired n (two-sided alpha .05, power .80); d = discordant fraction, delta = net shift ==")
for d in (0.2, 0.3):
    for delta in (0.10, 0.15, 0.20):
        print(f"d={d} delta={delta}: n={math.ceil(mcnemar_n(d, delta))}")


def expected_max_of_K(m, p, K):
    pmf = [math.comb(m, j) * p**j * (1 - p) ** (m - j) for j in range(m + 1)]
    cdf = [sum(pmf[: j + 1]) for j in range(m + 1)]
    e, prev = 0.0, 0.0
    for j in range(m + 1):
        cur = cdf[j] ** K
        e += (j / m) * (cur - prev)
        prev = cur
    return e


print("\n== E[max over K arms of (mean of m Bernoulli(.5) draws)], all arms truly equal at 0.5 ==")
for m in (2, 4, 8, 16):
    for K in (3, 6):
        print(f"m={m:2d} K={K}: select-and-score on same draws -> {expected_max_of_K(m, .5, K):.3f}")

random.seed(0)


def split_sim(m, K, trials=50000):
    h = m // 2
    tot = 0.0
    for _ in range(trials):
        a = [sum(random.random() < 0.5 for _ in range(h)) for _ in range(K)]
        b = [sum(random.random() < 0.5 for _ in range(m - h)) for _ in range(K)]
        best = max(range(K), key=lambda k: (a[k], random.random()))
        tot += b[best] / (m - h)
    return tot / trials


print("split-sample (select on half, score on other half) m=4 K=6 ->", round(split_sim(4, 6), 3))

print("\n== trigger headroom, ILLUSTRATIVE numbers only (a=base acc, r=rescue rate on wrong, h=harm rate on correct) ==")
a, r, h = 0.6, 0.25, 0.10
print(f"G_always={r*(1-a)-h*a:.3f}  G_oracle_trigger={r*(1-a):.3f}  headroom={h*a:.3f}")
