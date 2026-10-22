"""Reply-7 arithmetic checks (stdlib, CPU only): DEFF / false-GO arithmetic, CP bounds, m* grid, provenance of the user's 1.87."""
import math
import random

Phi = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
fgo = lambda deff: 1 - Phi(1.959964 / math.sqrt(deff))


def deff_shared(m, s2q, vC, vF):
    return 1 + (m - 1) * (s2q + vC) / (s2q + vC + vF)


def var_delta(n, m, s2q, vC, vF):
    return (s2q + vC + vF / m) / n


def m_star(s2q, vC, vF, c_fixed, c_F):
    return max(1.0, math.sqrt(vF * c_fixed / ((s2q + vC) * c_F)))


def cp_upper0(n, alpha=0.05, two_sided=True):
    a = alpha / 2 if two_sided else alpha
    return 1 - a ** (1 / n)


print("1) user's DEFF 1.87: CI inflation x%.3f, false-GO %.2f%%" % (math.sqrt(1.87), 100 * fgo(1.87)))


def calibrate(a_p, s, tau, N=60000, seed=1, DELTA=0.10):
    rng = random.Random(seed)
    U = [rng.gauss(0, 1) for _ in range(N)]
    W = [rng.gauss(0, 1) for _ in range(N)]
    P = [Phi(a_p + s * u) for u in U]
    mp = sum(P) / N
    lo, hi = -1.5, 1.5
    for _ in range(30):
        mid = (lo + hi) / 2
        mq = sum(Phi(mid + s * u + tau * w) for u, w in zip(U, W)) / N
        lo, hi = (mid, hi) if mp - mq > DELTA else (lo, mid)
    a_q = (lo + hi) / 2
    Q = [Phi(a_q + s * u + tau * w) for u, w in zip(U, W)]
    D = [p - q for p, q in zip(P, Q)]
    dm = sum(D) / N
    vbar = sum(p * (1 - p) + q * (1 - q) for p, q in zip(P, Q)) / N
    s2 = sum((d - dm) ** 2 for d in D) / (N - 1)
    return s2, vbar


print("2) provenance of 1.87 (probit populations of pooled_tango_mc.py; DEFF = (m s2 + vbar)/(s2 + vbar))")
for tau in (0.6, 1.2):
    s2, vbar = calibrate(0.35, 0.6, tau)
    print("   tau=%.1f s2q=%.3f vbar=%.3f  DEFF m=2/3/5 = %s" % (
        tau, s2, vbar, [round((m * s2 + vbar) / (s2 + vbar), 2) for m in (2, 3, 5)]))

print("\n3) shared-CONT populations: predicted false-GO from DEFF_shared (sigma_q^2 = 0)")
for name, vC, vF in (("B", 0.125, 0.177), ("A", 0.227, 0.227)):
    print("   %s: " % name + " | ".join(
        "m=%d DEFF %.2f pred %.1f%%" % (m, deff_shared(m, 0, vC, vF), 100 * fgo(deff_shared(m, 0, vC, vF)))
        for m in (1, 2, 3, 5)))

print("\n4) Clopper-Pearson, 0 events, upper bound on d_null (= 2 v_CONT)")
print("   n=12 two-sided 95%%: d_null <= %.4f -> v_CONT <= %.4f" % (cp_upper0(12), cp_upper0(12) / 2))
for tgt in (0.06, 0.10):
    n2 = next(n for n in range(1, 500) if cp_upper0(n) <= tgt)
    n1 = next(n for n in range(1, 500) if cp_upper0(n, two_sided=False) <= tgt)
    print("   target d_null <= %.2f (v <= %.3f): n = %d (two-sided), %d (one-sided) with 0 flips" % (tgt, tgt / 2, n2, n1))

print("\n5) CONT once: s2q=.05, vF=.125, c_q=10, c_CONT=1, c_F=1 (unit = one draw), c_fixed=11")
for vC in (0, 0.03, 0.06, 0.1323):
    ms = m_star(0.05, vC, 0.125, 11, 1)
    f = lambda m: (0.05 + vC + 0.125 / m) * (11 + m)
    v1 = var_delta(1, 1, 0.05, vC, 0.125)
    v3 = var_delta(1, 3, 0.05, vC, 0.125)
    print("   vC=%.4f  m*=%.2f  ratio vs vC=0: %.3f | Var*cost at m=1/3/5: %s | Var(m=3)/Var(m=1) = %.3f" % (
        vC, ms, ms / m_star(0.05, 0, 0.125, 11, 1), [round(f(m), 3) for m in (1, 3, 5)], v3 / v1))
print("   F-O (v_O = 0, no CONT call, c_fixed=10): m* = %.2f" % m_star(0.05, 0, 0.125, 10, 1))
print("   factor sqrt(s2q/(s2q+vC)) at vC=0.1323, s2q=.05: %.4f (1/factor = %.2f)" % (
    math.sqrt(0.05 / (0.05 + 0.1323)), math.sqrt((0.05 + 0.1323) / 0.05)))
