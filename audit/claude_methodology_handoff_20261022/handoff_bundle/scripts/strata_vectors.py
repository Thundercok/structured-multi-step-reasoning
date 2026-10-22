"""Which base-correct question-level patterns are consistent with the REPORTED aggregates? (stdlib, CPU only)
Inputs are reported numbers/IDs from the user (not raw artifacts): this tests consistency, it does not measure anything.
e_i = (F-A diff in draw 0) + (F-A diff in draw 1), each diff in {-1,0,+1}  ->  e_i in half-units, -2..2."""
import itertools
from collections import Counter


def signflip_p(vals):
    dist = Counter({0: 1})
    for v in vals:
        nd = Counter()
        for s, c in dist.items():
            nd[s + v] += c
            nd[s - v] += c
        dist = nd
    tot = abs(sum(vals))
    return sum(c for s, c in dist.items() if abs(s) >= tot) / 2 ** len(vals)


def boot_sum_dist(vals, n=12):
    """Exact distribution of the sum of n iid draws from the empirical distribution of vals (percentile bootstrap, B->inf)."""
    m, cnt, dist = len(vals), Counter(vals), {0: 1.0}
    for _ in range(n):
        nd = {}
        for s, p in dist.items():
            for v, c in cnt.items():
                nd[s + v] = nd.get(s + v, 0.0) + p * c / m
        dist = nd
    return dist


def tails(dist, lo, hi):
    ple = lambda k: sum(p for s, p in dist.items() if s <= k)
    pge = lambda k: sum(p for s, p in dist.items() if s >= k)
    return ple(lo - 1), ple(lo), pge(hi), pge(hi + 1)


# base-wrong stratum (5 questions), e in half-units, from the IDs the user gave
#            g24_0014 order_0006 arith_0039 g24_0023 5th
BW_M = [+1, +1, -1, +1, 0]    # M:    d0: g24_0014 +1 (A cut), order_0006 +1, arith_0039 -1 | d1: g24_0023 +1
BW_D = [-1, +1, -1, 0, 0]     # D_w0: A rescued on g24_0014 (both draws) and g24_0023 (draw 1); F wrong on g24_0014 in draw 1
assert sum(BW_M) == 2 and sum(BW_D) == -1

# base-correct stratum (7 questions): draw 0 has 3 x(+1) and 1 x(-1); draw 1 has 2 x(+1) and 0 x(-1)   [strata table at M]
patterns = {}
for P in itertools.combinations(range(7), 3):
    for S in (i for i in range(7) if i not in P):
        for T in itertools.combinations(range(7), 2):
            d0, d1 = [0] * 7, [0] * 7
            for i in P:
                d0[i] = 1
            d0[S] = -1
            for i in T:
                d1[i] = 1
            e = tuple(sorted(a + b for a, b in zip(d0, d1)))
            both = sum(a == 1 and b == 1 for a, b in zip(d0, d1))
            swap = sum(a == -1 and b == 1 for a, b in zip(d0, d1))
            patterns.setdefault(e, Counter())[(both, swap)] += 1

n_assign = sum(sum(c.values()) for c in patterns.values())
print(f"base-correct assignments: {n_assign} -> {len(patterns)} distinct e-multisets")
print("REPORTED at M: F-A mean +25.0 pp, sign-flip p=0.109375, percentile CI [+4.2, +45.8] pp = bootstrap-sum quantiles [1, 11] half-units\n")
hdr = f"{'base-correct e (sorted)':28s} {'#assign':>7s} {'(both,swap)':>12s} | {'p_M':>8s} {'P(S<=0)':>8s} {'P(S<=1)':>8s} {'P(S>=11)':>9s} {'P(S>=12)':>9s} | {'p_D_w0':>8s}"
print(hdr)
keep = []
for e, c in sorted(patterns.items()):
    vm, vd = BW_M + list(e), BW_D + list(e)
    pm, pd = signflip_p(vm), signflip_p(vd)
    t = tails(boot_sum_dist(vm), 1, 11)
    ci_ok = t[0] <= 0.035 and t[1] >= 0.015 and t[2] >= 0.015 and t[3] <= 0.035   # MC noise of B=2000 is ~0.35pp per tail
    p_ok = abs(pm - 0.109375) < 1e-9
    tag = "  <== matches p_M and CI" if (ci_ok and p_ok) else ""
    pat = ",".join(f"{k}:{v}" for k, v in sorted(c.items()))
    print(f"{str(e):28s} {sum(c.values()):7d} {pat:>12s} | {pm:8.5f} {t[0]:8.4f} {t[1]:8.4f} {t[2]:9.4f} {t[3]:9.4f} | {pd:8.5f}{tag}")
    if ci_ok and p_ok:
        keep.append((e, c, pd))

print("\nretained e-multisets:", len(keep))
for e, c, pd in keep:
    allv = sorted(BW_M + list(e))
    print("  M vector (12):", Counter(allv), "| D_w0 sign-flip p =", round(pd, 6), "| (both,swap) types:", dict(c))
