"""corrected_t.py + (i) two sparse 'stress' populations S1,S2 (heavier negative skew, pilot-like), (ii) SIZE-ADJUSTED power:
threshold of each statistic calibrated to exactly 2.5% on the boundary reps (R0), applied to independent alternative reps (R1).
Statistics (all on the SAME data sets): T (plain t) ; T_J = T + g/(6 sqrt n)(1+2T^2) ; S_B = T - q_{.975}(bootstrap-t).
n = 60 questions, F m draws, CONT once (shared), sigma_q^2 = 0 by construction, boundary effect = delta_prac = 0.10, alternative +0.15.
usage: corrected_t2.py M R0 R1 BOOT"""
import math
import random
import sys
import time

M, R0, R1, BOOT = (int(a) for a in sys.argv[1:5])
SEED = int(sys.argv[5]) if len(sys.argv) > 5 else 0            # independent-validation seed offset
ONLY = sys.argv[6].split(",") if len(sys.argv) > 6 else None    # e.g. "S2,B"
DELTA, N, TCRIT, ALPHA = 0.10, 60, 2.0010, 0.025
mix = lambda qlo, qhi, w: (lambda r: qlo if r.random() < w else qhi)
POPS = {
    "B ": mix(0.05, 0.40, 0.6),
    "A ": lambda r: r.uniform(0.2, 0.7),
    "S2": mix(0.05, 0.60, 0.9),
    "S1": mix(0.05, 0.30, 0.9),
}


def draw(sampler, e, rng):
    xs = []
    for _ in range(N):
        q = sampler(rng)
        p = q + DELTA + e
        cc = rng.random() < q
        tot = 0
        for _ in range(M):
            f = rng.random() < p
            tot += int(f and not cc) - int(cc and not f)
        xs.append(tot / M)
    return xs


def stats(xs, rng):
    mean = sum(xs) / N
    d2 = sum((x - mean) ** 2 for x in xs)
    if d2 <= 0:
        return None
    T = (mean - DELTA) / math.sqrt(d2 / (N - 1) / N)
    g = (sum((x - mean) ** 3 for x in xs) / N) / (d2 / N) ** 1.5
    TJ = T + g / (6 * math.sqrt(N)) * (1 + 2 * T * T)
    qs = []
    for _ in range(BOOT):
        ys = rng.choices(xs, k=N)
        my = sum(ys) / N
        vy = (sum(y * y for y in ys) - N * my * my) / (N - 1)
        if vy > 1e-12:
            qs.append((my - mean) / math.sqrt(vy / N))
    qs.sort()
    return T, TJ, T - qs[int(0.975 * len(qs))], g


def collect(sampler, e, reps, rng):
    out = []
    for _ in range(reps):
        s = stats(draw(sampler, e, rng), rng)
        out.append(s if s else (-9, -9, -9, 0.0))      # zero-variance data set = no GO
    return out


t0 = time.time()
print("n=%d m=%d  R0(boundary)=%d R1(alt)=%d boot=%d | MC SE at 2.5%%: %.2f pt (R0), power SE ~%.2f pt (R1)" % (
    N, M, R0, R1, BOOT, 100 * math.sqrt(0.025 * 0.975 / R0), 100 * math.sqrt(0.25 / R1)), flush=True)
for name, smp in POPS.items():
    if ONLY and name.strip() not in ONLY:
        continue
    rng = random.Random(SEED + 8800 + 100 * M + ord(name[0]) + (13 if name[1] == "1" else 0) + (29 if name[1] == "2" else 0))
    b0 = collect(smp, 0.0, R0, rng)
    b1 = collect(smp, 0.15, R1, rng)
    row = []
    for k, crit in ((0, TCRIT), (1, TCRIT), (2, 0.0)):
        size = sum(r[k] > crit for r in b0) / R0
        pw = sum(r[k] > crit for r in b1) / R1
        srt = sorted(r[k] for r in b0)
        c = srt[int((1 - ALPHA) * R0)]                      # oracle 2.5% threshold on the boundary reps
        pwa = sum(r[k] > c for r in b1) / R1
        row.append((size, pw, pwa))
    g0 = sum(r[3] for r in b0) / R0
    print("%s m=%d skew(sample mean) %+.2f | SIZE plain %.4f J %.4f boot %.4f | POWER plain %.3f J %.3f boot %.3f | ORACLE-2.5%% POWER plain %.3f J %.3f boot %.3f  (%.0fs)" % (
        name, M, g0, row[0][0], row[1][0], row[2][0], row[0][1], row[1][1], row[2][1], row[0][2], row[1][2], row[2][2], time.time() - t0), flush=True)
