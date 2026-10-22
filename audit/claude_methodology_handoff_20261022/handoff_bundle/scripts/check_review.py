"""Consistency checks on the 14/10 retrospective review (reported numbers only; stdlib).
Question-level mean differences e_i are multiples of 0.5 (two draws averaged), so e_i in {-1,-.5,0,.5,1}."""
import itertools
import random
from collections import Counter
from math import sqrt

# 1. plan hash quoted in the disclosure vs the hash in the earlier (13/10) handoff
earlier = "132f850d304de9e7026a5cc42ac65691ac3249e3d4eb4315f9c1a28436925bd6"
now = "132f850d304de9e7026a5cc42ac65691ac3249e3d4eb4315f9c1a28436925bd6"
print("plan hash identical:", earlier == now, "| hex length", len(now))

# 2. reported percentile-bootstrap CIs at M -> rough SE and t-corrected interval (symmetric, ~normal assumption)
rep = {"F-A": (4.2, 45.8, 0.109375), "CONT-A": (4.2, 37.5, 0.125), "F-CONT": (-8.3, 16.7, 1.0)}
print("\n== t-corrected reading of the reported CIs (pp) ==")
for k, (lo, hi, p) in rep.items():
    c, hw = (lo + hi) / 2, (hi - lo) / 2
    se_boot = hw / 1.96
    se_unb = se_boot / sqrt(11 / 12)
    print(f"{k:7s} centre {c:5.1f}  SE_boot {se_boot:5.2f}  t11-interval [{c - 2.201 * se_unb:+6.1f}, {c + 2.201 * se_unb:+6.1f}]"
          f"  reported percentile [{lo:+.1f}, {hi:+.1f}]  sign-flip p {p:.6f}")


# 3. which question-level vectors reproduce (sum, exact two-sided sign-flip p)?  units of 0.5 -> ints in -2..2
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


def mc_percentile(vals, reps=20000, seed=1):
    rng = random.Random(seed)
    n = len(vals)
    ms = sorted(sum(rng.choices(vals, k=n)) / n for _ in range(reps))
    return ms[int(0.025 * reps)] * 50, ms[int(0.975 * reps)] * 50  # half-units -> pp (x0.5 x100)


print("\n== vectors e (12 questions) reproducing reported mean and sign-flip p; their percentile-bootstrap CI (pp) ==")
cases = {"F-A": (6, 0.109375, 20.8), "CONT-A": (5, 0.125, 16.65), "F-CONT": (1, 1.0, 12.5)}  # (sum in half-units, p, reported half-width)
for name, (s_half, p_rep, hw_rep) in cases.items():
    found = []
    for combo in itertools.combinations_with_replacement(range(-2, 3), 12):
        if sum(combo) != s_half:
            continue
        if abs(signflip_p(combo) - p_rep) < 1e-9:
            found.append(combo)
    print(f"{name}: {len(found)} multisets match sum and p; reported CI half-width {hw_rep} pp")
    shown = 0
    for combo in found:
        lo, hi = mc_percentile(list(combo))
        hw = (hi - lo) / 2
        if abs(hw - hw_rep) <= 2.5 and shown < 4:
            cnt = Counter(combo)
            print("   e counts (half-units):", dict(sorted(cnt.items())), f"-> MC percentile CI [{lo:+.1f}, {hi:+.1f}] half-width {hw:.1f}")
            shown += 1
    if not shown:
        print("   none with percentile half-width within 2.5 pp of the reported one")

# 4. per-draw discordance of F-A from the strata table (b,c per stratum), and the floor identity
d0 = (3 + 2) + (1 + 1)
d1 = (2 + 1) + (0 + 0)
print("\nF-A discordant questions per draw:", d0, d1, "-> mean d_cross-hat", (d0 + d1) / 24)
print("plug-in floor d_null_mean + Delta^2 =", round((3 / 12 + 7 / 12) / 2 + 0.25 ** 2, 4))
print("A: M->D_w0 correct per draw:", (6, 7), (5, 7), "| F:", (9, 9), (8, 8), "| CONT M->D_w1:", (8, 7), (8, 7))
