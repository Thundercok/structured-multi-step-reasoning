"""Size / power at n = 60 questions of: (i) Tango on m=1 data (validated route), (ii) cluster t on question means (F m=3 draws,
CONT once, shared), (iii) distribution-free betting test (Waudby-Smith & Ramdas style one-sided capital process with the
predictable plug-in bet, averaged over random orderings -> still an e-value).  Synthetic populations B and A (sigma_q^2 = 0 by
construction), boundary effect (= delta_prac) and delta_prac + 0.15.  stdlib, CPU only.  Not a pilot result."""
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gonogo as g  # noqa: E402

DELTA, REPS, ALPHA, PERMS = 0.10, 4000, 0.025, 16
LOG = math.log(1 / ALPHA)
TC = {60: 2.0010}
POPS = {
    "B": lambda r: 0.05 if r.random() < 0.6 else 0.40,
    "A": lambda r: r.uniform(0.2, 0.7),
}


def draw(sampler, n, m, e, rng):
    xs, b, c = [], 0, 0
    for _ in range(n):
        q = sampler(rng)
        p = q + DELTA + e
        cc = rng.random() < q              # CONT once, shared across the m F draws
        tot = 0
        for _ in range(m):
            f = rng.random() < p
            if f and not cc:
                tot += 1
                b += 1
            elif cc and not f:
                tot -= 1
                c += 1
        xs.append(tot / m)
    return xs, b, c


def t_go(xs):
    n = len(xs)
    mean = sum(xs) / n
    var = sum((v - mean) ** 2 for v in xs) / (n - 1)
    return var > 0 and (mean - DELTA) / math.sqrt(var / n) > TC[n]


def bet_K(us, m0, c=0.75):
    """capital of a one-sided bettor against H0: E[u] <= m0, bets lambda_t in [0, c/m0] predictable (PrPl-style plug-in)"""
    cap = c / m0
    K, sum_u, ss, sig2 = 1.0, 0.0, 0.0, 0.25
    for t, u in enumerate(us, 1):
        lam = min(cap, math.sqrt(2 * LOG / (sig2 * t * math.log(1 + t))))
        K *= 1 + lam * (u - m0)
        sum_u += u
        mu_t = (0.5 + sum_u) / (t + 1)
        ss += (u - mu_t) ** 2
        sig2 = (0.25 + ss) / (t + 1)
    return K


def bet_go(xs, rng):
    us = [(x + 1) / 2 for x in xs]
    m0 = (1 + DELTA) / 2
    tot = 0.0
    for _ in range(PERMS):
        rng.shuffle(us)
        tot += bet_K(us, m0)
    return tot / PERMS >= 1 / ALPHA


t0 = time.time()
print("n=60 (Tango also n=100), reps=%d, delta_prac=%.2f; MC SE ~0.0025 at 2.5%%, ~0.007 at 50%%" % (REPS, DELTA))
for name, s in POPS.items():
    for e, label in ((0.0, "SIZE  (effect = delta_prac)"), (0.15, "POWER (effect = delta_prac + 0.15)")):
        rng = random.Random(4242 + int(e * 100))
        tg60 = tg100 = tt = tb = 0
        for _ in range(REPS):
            _, b, c = draw(s, 60, 1, e, rng)
            tg60 += g.decide(b, c, 60, DELTA) == "GO"
            _, b, c = draw(s, 100, 1, e, rng)
            tg100 += g.decide(b, c, 100, DELTA) == "GO"
            xs, _, _ = draw(s, 60, 3, e, rng)
            tt += t_go(xs)
            tb += bet_go(xs, rng)
        print("pop %s %-36s Tango m=1 n=60: %.3f | Tango m=1 n=100: %.3f | cluster t m=3 n=60: %.3f | betting m=3 n=60: %.3f   (%.0fs)" % (
            name, label, tg60 / REPS, tg100 / REPS, tt / REPS, tb / REPS, time.time() - t0), flush=True)
