"""Is the betting test's ~0.2% size an implementation artifact or structural?  Test the lognormal-wealth (CLT-regime) explanation.
(1) CLT-regime ceiling of ANY smooth e-value test: max_s P(log K >= L) = 1 - Phi(sqrt(2 L)), L = ln(1/alpha).
(2) realized quadratic variation s = sum lambda_t^2 (u_t - m0)^2 of my plug-in bettor under the boundary null (single ordering) and the
    model-predicted size 1 - Phi((L + s/2)/sqrt(s)) vs the observed single-ordering size.
(3) ORACLE fixed-lambda bettor (knows the alternative): size at the boundary and power at delta_prac + 0.15, n = 60, m = 3, CONT once.
(4) CLT-regime power of the oracle e-test vs z-test as a function of information s0 = n d^2.
Synthetic populations B and A (sigma_q^2 = 0).  stdlib, CPU only."""
import math
import random

Phi = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
ALPHA, DELTA, N, M, REPS = 0.025, 0.10, 60, 3, 4000
L = math.log(1 / ALPHA)
m0 = (1 + DELTA) / 2
POPS = {
    "B": lambda r: 0.05 if r.random() < 0.6 else 0.40,
    "A": lambda r: r.uniform(0.2, 0.7),
}

print("(1) CLT-regime ceiling: L=ln(1/alpha)=%.3f, worst information s=2L=%.2f, max size 1-Phi(sqrt(2L)) = %.4f (nominal %.3f)" % (
    L, 2 * L, 1 - Phi(math.sqrt(2 * L)), ALPHA))


def draw_u(sampler, n, m, e, rng):
    us = []
    for _ in range(n):
        q = sampler(rng)
        p = q + DELTA + e
        cc = rng.random() < q
        tot = 0
        for _ in range(m):
            f = rng.random() < p
            tot += int(f and not cc) - int(cc and not f)
        us.append((tot / m + 1) / 2)
    return us


def plug_in(us, c=0.75):
    cap = c / m0
    K, sum_u, ss, sig2, s = 1.0, 0.0, 0.0, 0.25, 0.0
    for t, u in enumerate(us, 1):
        lam = min(cap, math.sqrt(2 * L / (sig2 * t * math.log(1 + t))))
        K *= 1 + lam * (u - m0)
        s += (lam * (u - m0)) ** 2
        sum_u += u
        mu_t = (0.5 + sum_u) / (t + 1)
        ss += (u - mu_t) ** 2
        sig2 = (0.25 + ss) / (t + 1)
    return K, s


def fixed(us, lam):
    K = 1.0
    for u in us:
        K *= 1 + lam * (u - m0)
    return K


for name, smp in POPS.items():
    rng = random.Random(99)
    # (2) plug-in bettor under the boundary null, single ordering
    hit = 0
    s_list = []
    for _ in range(REPS):
        K, s = plug_in(draw_u(smp, N, M, 0.0, rng))
        hit += K >= 1 / ALPHA
        s_list.append(s)
    s_bar = sum(s_list) / REPS
    pred = sum(1 - Phi((L + s / 2) / math.sqrt(s)) for s in s_list) / REPS
    print("\npop %s (2) plug-in bettor, single ordering, boundary null: observed size %.4f | mean realized s = %.2f | lognormal-model size %.4f" % (
        name, hit / REPS, s_bar, pred))
    # (3) oracle fixed lambda (optimal for the alternative delta+0.15)
    big = [u for u in draw_u(smp, 100000, M, 0.15, random.Random(5))]
    mu = sum(big) / len(big)
    var = sum((u - mu) ** 2 for u in big) / len(big)
    mu_p = mu - m0
    lam = min(0.999 / m0, mu_p / (var + mu_p ** 2))
    sz = sum(fixed(draw_u(smp, N, M, 0.0, rng), lam) >= 1 / ALPHA for _ in range(REPS)) / REPS
    pw = sum(fixed(draw_u(smp, N, M, 0.15, rng), lam) >= 1 / ALPHA for _ in range(REPS)) / REPS
    print("pop %s (3) ORACLE fixed lambda=%.2f (mu'=%.3f, var_u=%.4f): size %.4f, power %.3f   [cluster t m=3 n=60 gave 0.712 (B) / 0.554 (A); plug-in betting 0.356 / 0.256]" % (
        name, lam, mu_p, var, sz, pw))

print("\n(4) CLT-regime power at information s0 = n*d^2 (d = effect/sd): z-test vs ORACLE e-test (reject log K >= L)")
for s0 in (3.84, 6.3, 7.84, 11.0, 13.6):
    z = Phi(math.sqrt(s0) - 1.959964)
    e = Phi(math.sqrt(s0) / 2 - L / math.sqrt(s0))
    print("   s0=%5.2f  z-test %.3f   oracle e-test %.3f" % (s0, z, e))
print("   information needed for 50%% / 80%% power: z %.2f / %.2f ; e-test %.2f / %.2f  (ratio %.2f / %.2f)" % (
    1.959964 ** 2, (1.959964 + 0.841621) ** 2, 2 * L,
    ((0.841621 + math.sqrt(0.841621 ** 2 + 4 * 0.5 * L)) / (2 * 0.5)) ** 2,
    2 * L / 1.959964 ** 2,
    (((0.841621 + math.sqrt(0.841621 ** 2 + 2 * L)) / 1.0) ** 2) / (1.959964 + 0.841621) ** 2))
