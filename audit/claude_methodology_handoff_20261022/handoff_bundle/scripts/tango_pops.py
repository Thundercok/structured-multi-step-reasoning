"""Tango GO rate for the validated m=1 route, NOMINAL z = 1.96 vs the worst-case CALIBRATED z* (gonogo.calibrate_z: worst-case size over the
discordance d held <= 2.5% per side), at n = 60, 70, 80.  Same populations as fixed_critical.py.  Size at the boundary (effect = delta_prac = 0.10),
power at delta_prac + 0.15.  CONT once, F once per question.  n = 70 / 80 are the equal-COST sizes of (m=3 / m=5, n=60) under the scenario costs
c_fixed = 11 per question, c_F = 1 per F draw (scenario numbers, NOT the user's).  stdlib, CPU only."""
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gonogo as g  # noqa: E402

DELTA, REPS = 0.10, 20000
NS = (60, 70, 80)
ZS = {n: g.calibrate_z(n, DELTA) for n in NS}
mix = lambda qlo, qhi, w: (lambda r: qlo if r.random() < w else qhi)
POPS = {
    "B ": mix(0.05, 0.40, 0.6),
    "A ": lambda r: r.uniform(0.2, 0.7),
    "S2": mix(0.05, 0.60, 0.9),
    "S1": mix(0.05, 0.30, 0.9),
    "V1": mix(0.02, 0.20, 0.80),
    "V2": mix(0.03, 0.60, 0.97),
    "V3": mix(0.01, 0.20, 0.93),
    "V4": mix(0.05, 0.45, 0.95),
    "X1": mix(0.05, 0.20, 0.93),
    "X2": mix(0.03, 0.20, 0.97),
}


def rates(sampler, n, e, rng):
    nom = cal = 0
    for _ in range(REPS):
        b = c = 0
        for _ in range(n):
            q = sampler(rng)
            f = rng.random() < q + DELTA + e
            cc = rng.random() < q
            b += f and not cc
            c += cc and not f
        nom += g.decide(b, c, n, DELTA) == "GO"
        cal += g.decide(b, c, n, DELTA, ZS[n]) == "GO"
    return nom / REPS, cal / REPS


t0 = time.time()
print("calibrated z*: " + "  ".join("n=%d: %.3f" % (n, ZS[n]) for n in NS) + "   (nominal 1.960); reps=%d" % REPS, flush=True)
print("pop | n=60 size nom/cal, power nom/cal | n=70 ... | n=80 ...", flush=True)
for name, smp in POPS.items():
    rng = random.Random(2718 + ord(name[0]) * 7 + ord(name[1]))
    cells = []
    for n in NS:
        s_nom, s_cal = rates(smp, n, 0.0, rng)
        p_nom, p_cal = rates(smp, n, 0.15, rng)
        cells.append("size %.1f/%.1f%% power %.1f/%.1f%%" % (100 * s_nom, 100 * s_cal, 100 * p_nom, 100 * p_cal))
    print("%s | %s   (%.0fs)" % (name, " | ".join(cells), time.time() - t0), flush=True)
