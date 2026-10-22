"""User's point: if CONT is called ONCE per question and reused against m draws of F, CONT's seed noise is a shared
question-level term, so pooled Tango inflates false-GO EVEN WHEN sigma_q^2 = 0 (p_i = q_i + delta for every question).
Check by Monte Carlo at the boundary (true effect == delta_prac).  Synthetic populations, stdlib, CPU only.
DEFF_shared = 1 + (m-1)(sigma_q^2 + v_C) / (sigma_q^2 + v_C + v_F)."""
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gonogo as g  # noqa: E402

Phi = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
DELTA, N_Q, REPS, TCRIT = 0.10, 150, 4000, 1.9760
POPS = {
    "B (v_C~0.12, = CP bound of 0/12)": lambda r: 0.05 if r.random() < 0.6 else 0.40,
    "A (v_C~0.23, mid-range q)": lambda r: r.uniform(0.2, 0.7),
}


def moments(sampler, N=200000):
    r = random.Random(3)
    qs = [sampler(r) for _ in range(N)]
    vC = sum(q * (1 - q) for q in qs) / N
    vF = sum((q + DELTA) * (1 - q - DELTA) for q in qs) / N
    return vC, vF


def run(sampler, m, shared, rng):
    pool = cl = 0
    for _ in range(REPS):
        b = c = 0
        xs = []
        for _ in range(N_Q):
            q = sampler(rng)
            p = q + DELTA                      # sigma_q^2 = 0 by construction
            cc = rng.random() < q              # CONT, drawn once (shared) ...
            tot = 0
            for _ in range(m):
                f = rng.random() < p
                if not shared:
                    cc = rng.random() < q      # ... or independently per draw
                if f and not cc:
                    b += 1
                    tot += 1
                elif cc and not f:
                    c += 1
                    tot -= 1
            xs.append(tot / m)
        if g.decide(b, c, N_Q * m, DELTA) == "GO":
            pool += 1
        mean = sum(xs) / N_Q
        var = sum((v - mean) ** 2 for v in xs) / (N_Q - 1)
        if var > 0 and (mean - DELTA) / math.sqrt(var / N_Q) > TCRIT:
            cl += 1
    return pool / REPS, cl / REPS


t0 = time.time()
print(f"n={N_Q}, reps={REPS}, sigma_q^2 = 0, true effect == delta_prac = {DELTA}; nominal one-sided false-GO 0.025")
for name, sampler in POPS.items():
    vC, vF = moments(sampler)
    print(f"\npopulation {name}: v_C={vC:.3f} v_F={vF:.3f}  (CONT disagreement d_null = 2 v_C = {2 * vC:.3f})")
    print(f"{'m':>2s} | {'CONT once (shared)':>18s} {'predicted':>9s} {'cluster t':>9s} | {'CONT m times':>12s} | DEFF_shared")
    rng = random.Random(20261015)
    for m in (1, 2, 3, 5):
        gp, gc = run(sampler, m, True, rng)
        gi = run(sampler, m, False, rng)[0] if m > 1 else gp
        deff = 1 + (m - 1) * vC / (vC + vF)
        pred = 1 - Phi(1.959964 / math.sqrt(deff))
        print(f"{m:2d} | {gp:18.4f} {pred:9.4f} {gc:9.4f} | {gi:12.4f} | {deff:.3f}", flush=True)
    print(f"   ({time.time() - t0:.0f}s elapsed)")
