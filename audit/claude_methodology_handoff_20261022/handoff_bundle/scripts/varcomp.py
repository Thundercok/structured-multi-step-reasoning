"""Variance components of the F-A contrast from the 12-question x 2-draw structure (stdlib, CPU only).
Structure = reconstruction consistent with REPORTED numbers (per-draw counts A 6/5, F 9/8; b,c per draw (5,2),(3,0);
d_null A=7/12, F=3/12; question_means vector 8x+0.5, 2x-0.5, 2x0; user text: 6 questions F right in both draws & A flips,
2 questions A wrong in both draws & F flips). It is a consistency construction, not a measurement."""
import random
from collections import Counter
from math import sqrt


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


# name -> ((A0, A1), (F0, F1)) correctness in draw 0 / draw 1 at M
Q = {}
for i in range(3):
    Q[f"P1a{i}"] = ((1, 0), (1, 1))   # F right both, A right only in draw 0
    Q[f"P1b{i}"] = ((0, 1), (1, 1))   # F right both, A right only in draw 1
for i in range(2):
    Q[f"P2_{i}"] = ((0, 0), (1, 0))   # A wrong both, F right only in draw 0
Q["N1"] = ((1, 0), (0, 0))            # A right in draw 0 only, F wrong both
Q["N2"] = ((1, 1), (0, 1))            # A right both, F right only in draw 1
Q["T1"] = ((1, 1), (1, 1))
Q["T0"] = ((0, 0), (0, 0))


def summarize(Q, label):
    A0 = sum(a[0] for a, f in Q.values()); A1 = sum(a[1] for a, f in Q.values())
    F0 = sum(f[0] for a, f in Q.values()); F1 = sum(f[1] for a, f in Q.values())
    d = {k: (f[0] - a[0], f[1] - a[1]) for k, (a, f) in Q.items()}
    b0 = sum(v[0] == 1 for v in d.values()); c0 = sum(v[0] == -1 for v in d.values())
    b1 = sum(v[1] == 1 for v in d.values()); c1 = sum(v[1] == -1 for v in d.values())
    e = [v[0] + v[1] for v in d.values()]
    flipsA = sum(a[0] != a[1] for a, f in Q.values()); flipsF = sum(f[0] != f[1] for a, f in Q.values())
    print(f"[{label}] correct A {A0}/{A1}  F {F0}/{F1} | (b,c) draw0 {(b0, c0)} draw1 {(b1, c1)} | e (half-units) {dict(sorted(Counter(e).items()))}"
          f" | mean {sum(e) / 24 * 100:.1f} pp | sign-flip p {signflip_p(e):.6f} | flips A {flipsA}/12 F {flipsF}/12")
    return d


d = summarize(Q, "M   ")

# D_w0: A rescued on g24_0014 (= P2_0, both draws) and g24_0023 (= P1a0, draw 1) -- an inference from the reported trace facts
QD = dict(Q)
QD["P2_0"] = ((1, 1), Q["P2_0"][1])
QD["P1a0"] = ((1, 1), Q["P1a0"][1])
summarize(QD, "D_w0")

# ---- variance components of x_i = mean over the 2 draws of (F - A) ----
vals = list(d.values())
x = [(a + b) / 2 for a, b in vals]
s2 = [(a - b) ** 2 / 2 for a, b in vals]   # unbiased within-question variance of a single-draw difference


def comps(x, s2):
    n = len(x)
    xb = sum(x) / n
    var_x = sum((v - xb) ** 2 for v in x) / (n - 1)
    vbar = sum(s2) / n
    return xb, var_x, vbar, var_x - vbar / 2


xb, var_x, vbar, sq = comps(x, s2)
print(f"\nF-A at M: mean {xb * 100:.1f} pp | var of question means {var_x:.4f} | vbar (within-question var of a 1-draw difference) {vbar:.4f}"
      f" | vbar/2 {vbar / 2:.4f} | sigma_q^2 hat = {sq:+.4f}")
rng = random.Random(7)
bs = []
for _ in range(20000):
    idx = [rng.randrange(12) for _ in range(12)]
    bs.append(comps([x[i] for i in idx], [s2[i] for i in idx]))
bs_sq = sorted(b[3] for b in bs)
bs_v = sorted(b[2] for b in bs)
sd = lambda L: sqrt(sum((v - sum(L) / len(L)) ** 2 for v in L) / (len(L) - 1))
print(f"bootstrap (over questions): sigma_q^2 SD {sd(bs_sq):.3f}, 2.5/97.5% [{bs_sq[500]:+.3f}, {bs_sq[19500]:+.3f}] | vbar SD {sd(bs_v):.3f}, [{bs_v[500]:.3f}, {bs_v[19500]:.3f}]")
print(f"SE of the mean implied by var_x: {sqrt(var_x / 12) * 100:.1f} pp; implied t = {xb / sqrt(var_x / 12):.2f}")

# single-arm seed noise (for contrasts against deterministic CONT / O)
vF = sum((f[0] - f[1]) ** 2 / 2 for a, f in Q.values()) / 12
vA = sum((a[0] - a[1]) ** 2 / 2 for a, f in Q.values()) / 12
print(f"\nvbar_F = {vF:.4f} (F flips 3/12 x 0.5/12)  vbar_A = {vA:.4f}  vbar_FA check = {vA + vF:.4f} (independent arms) vs direct {vbar:.4f}")

# ---- design: Var(mean) = (sigma_q^2 + v/m)/n ; fixed N=n*m calls -> (sigma_q^2*m + v)/N ; cost n*(cq + m*cd) -> m*
print("\nm* = sqrt(v * (cq/cd) / sigma_q^2):")
print(f"{'v':>8s} {'cq/cd':>6s} " + " ".join(f"s2={s:<5}" for s in (0.02, 0.05, 0.10)))
for v in (vbar, vF):
    for r in (1, 10):
        print(f"{v:8.4f} {r:6d} " + " ".join(f"{sqrt(v * r / s):8.1f}" for s in (0.02, 0.05, 0.10)))
print("\nvariance x cost per question-draw bundle, sigma_q^2=0.05, v=vbar, cq/cd=10, relative to m=1:")
base = (0.05 + vbar / 1) * (10 + 1)
for m in (1, 2, 3, 5, 9, 14):
    print(f"m={m:2d}: {(0.05 + vbar / m) * (10 + m) / base:.2f}")
print("fixed N (no question cost): Var ratio vs m=1 =", {m: round((0.05 * m + vbar) / (0.05 + vbar), 3) for m in (1, 2, 3, 5)})
