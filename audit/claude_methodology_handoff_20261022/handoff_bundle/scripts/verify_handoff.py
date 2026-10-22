"""Check the 13/10 handoff numbers from the counts they imply. Stdlib only; imports gonogo.py (v2).
Inputs are REPORTED numbers (handoff text), not raw artifacts: this checks internal consistency only."""
import itertools
import os
import random
import sys
from collections import Counter
from math import comb, sqrt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gonogo as g  # noqa: E402

N = 12
REPORTED = {  # contrast: (Delta pp, CI pp) as written in the handoff, at M
    "F-A": (25.0, (-18.8, 59.7)),
    "CONT-A": (16.7, (-18.9, 48.5)),
    "F-CONT": (8.3, (-24.4, 39.7)),
}

# ---- 1. which (b,c) do the reported marginals allow? (base: 5 wrong, 7 correct; at M) ----
# A rescues 2/5 harms 3/7 | F rescues 3/5 harms 1/7 | CONT rescues 1/5 harms 0/7  -> accuracy 6/9/8 of 12
WRONG, RIGHT = range(5), range(5, 12)


def correct_set(rescued, harmed):
    return set(rescued) | (set(RIGHT) - set(harmed))


def bc(x, y):
    return len(x - y), len(y - x)


allcfg, g24 = Counter(), Counter()
for ra in itertools.combinations(WRONG, 2):
    for rf in itertools.combinations(WRONG, 3):
        for rc in itertools.combinations(WRONG, 1):
            for ha in itertools.combinations(RIGHT, 3):
                for hf in itertools.combinations(RIGHT, 1):
                    A, F, C = correct_set(ra, ha), correct_set(rf, hf), correct_set(rc, ())
                    key = (bc(F, A), bc(C, A), bc(F, C))
                    allcfg[key] += 1
                    if set(rc) <= set(ra) and set(rc) <= set(rf):  # "G24 rescued by A, F and CONT"
                        g24[key] += 1

print("== 1. (b,c) for (F-A, CONT-A, F-CONT) allowed by the reported marginals ==")
print(f"configurations: {sum(allcfg.values())}; F-A=(5,2) attainable: {any(k[0] == (5, 2) for k in allcfg)}")
print("F-A (b,c) distribution over all configurations:",
      sorted(Counter({k: sum(v for kk, v in allcfg.items() if kk[0] == k) for k in {kk[0] for kk in allcfg}}).items()))
sel = {k: v for k, v in g24.items() if k[0] == (5, 2)}
print("with F-A=(5,2) and G24 rescued by all three arms ->", sorted(sel.items()), "(key = F-A, CONT-A, F-CONT)")

print("\n== 2. Tango 95% CI recomputed (gonogo v2) vs handoff, n=12 ==")
derived = {"F-A": (5, 2), "CONT-A": (3, 1), "F-CONT": (2, 1)}
for name, (b, c) in derived.items():
    lo, up = g.tango_ci(b, c, N)
    d_rep, ci_rep = REPORTED[name]
    ok = abs(100 * lo - ci_rep[0]) < 0.06 and abs(100 * up - ci_rep[1]) < 0.06 and abs(100 * (b - c) / N - d_rep) < 0.06
    print(f"{name:7s} b={b} c={c} Delta={100 * (b - c) / N:+.1f}pp  recomputed [{100 * lo:+.1f}, {100 * up:+.1f}]"
          f"  reported [{ci_rep[0]:+.1f}, {ci_rep[1]:+.1f}]  match={ok}  state@10pp={g.decide(b, c, N, 0.10)}"
          f"  exact p={g.mcnemar_exact_p(b, c):.3f}")

print("\n== 2b. uniqueness: every (b,c) with the same b-c whose CI is within 0.15pp of the reported one ==")
for name, diff in (("F-A", 3), ("CONT-A", 2), ("F-CONT", 1)):
    ci_rep = REPORTED[name][1]
    hits = []
    for c in range(0, N):
        b = c + diff
        if b + c > N:
            continue
        lo, up = g.tango_ci(b, c, N)
        if abs(100 * lo - ci_rep[0]) < 0.15 and abs(100 * up - ci_rep[1]) < 0.15:
            hits.append((b, c))
    print(f"{name}: {hits}")

print("\n== 3. Clopper-Pearson 95% ==")
for label, x in (("0/12 flips", 0), ("2/12 (the earlier ASSUMPTION)", 2), ("discordant F-A 7/12", 7),
                 ("discordant CONT-A 4/12", 4), ("discordant F-CONT 3/12", 3)):
    lo, up = g.clopper_pearson(x, N)
    print(f"{label:32s}: [{lo:.4f}, {up:.4f}]")
print(f"closed form upper for 0/12: 1-0.025**(1/12) = {1 - 0.025 ** (1 / 12):.4f}")

print("\n== 4. identity: P(cross-arm discordant) - mean(P(same-arm discordant)) = (p-q)^2 ==")
random.seed(1)
worst = 0.0
for _ in range(100000):
    p, q = random.random(), random.random()
    cross = p * (1 - q) + q * (1 - p)
    same = (2 * p * (1 - p) + 2 * q * (1 - q)) / 2
    worst = max(worst, abs((cross - same) - (p - q) ** 2))
print(f"max |lhs - rhs| over 1e5 random (p,q): {worst:.2e}")
print(f"sqrt(11/12) = {sqrt(11 / 12):.4f}; 1.96*sqrt(11/12)/2.201 = {1.96 * sqrt(11 / 12) / 2.201:.3f}")
print(f"plan arithmetic: 36*5={36 * 5}; 72996+14125={72996 + 14125}; 19715+14125={19715 + 14125}")
