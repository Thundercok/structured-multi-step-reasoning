"""Exact skewness / excess kurtosis of the question mean x_i (CONT once, shared; boundary effect delta=0.10) for the simulated
populations, and the Edgeworth predictions of the plain-t false-GO size at n = 60:
  first order :  size1 = 1 - [Phi(x) + n^-1/2 q1(x) phi(x)]
  second order:  size2 = 1 - [Phi(x) + n^-1/2 q1(x) phi(x) + n^-1 q2(x) phi(x)]
  q1 = g (2x^2+1)/6 ;  q2 = x{ k (x^2-3)/12 - g^2 (x^4+2x^2-3)/18 - (x^2+3)/4 }      (Hall 1992, Studentized mean, divisor n)
Our T uses divisor n-1 and t_{0.975,59} = 2.0010  <=>  T_n > 2.0010*sqrt(n/(n-1)).  Observed = plain-t sizes from corrected_t2.py (pooled where replicated)."""
import math

Phi = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
phi = lambda x: math.exp(-x * x / 2) / math.sqrt(2 * math.pi)
N, DELTA = 60, 0.10


def binom(m, k, p):
    return math.comb(m, k) * p ** k * (1 - p) ** (m - k)


def moments(comps, m):                      # comps: [(weight, q)] -> (mean, var, skew, excess kurtosis)
    pts = []
    for w, q in comps:
        p = q + DELTA
        for c in (0, 1):
            pc = q if c else 1 - q
            for k in range(m + 1):
                pts.append((w * pc * binom(m, k, p), (k - m * c) / m))
    mu = sum(pr * x for pr, x in pts)
    c2 = sum(pr * (x - mu) ** 2 for pr, x in pts)
    c3 = sum(pr * (x - mu) ** 3 for pr, x in pts)
    c4 = sum(pr * (x - mu) ** 4 for pr, x in pts)
    return mu, c2, c3 / c2 ** 1.5, c4 / c2 ** 2 - 3


def predict(g, k):
    x = 2.0010 * math.sqrt(N / (N - 1))
    q1 = g * (2 * x * x + 1) / 6
    q2 = x * (k * (x * x - 3) / 12 - g * g * (x ** 4 + 2 * x * x - 3) / 18 - (x * x + 3) / 4)
    s1 = 1 - (Phi(x) + q1 * phi(x) / math.sqrt(N))
    s2 = s1 - q2 * phi(x) / N
    return 100 * s1, 100 * s2


A_GRID = [(1 / 2000, 0.2 + 0.5 * (i + 0.5) / 2000) for i in range(2000)]
POPS = {
    "B": [(0.6, 0.05), (0.4, 0.40)],
    "A": A_GRID,
    "S2": [(0.9, 0.05), (0.1, 0.60)],
    "S1": [(0.9, 0.05), (0.1, 0.30)],
}
OBS = {("B", 3): 3.11, ("B", 5): 3.10, ("A", 3): 2.65, ("A", 5): 2.56,
       ("S2", 3): 3.35, ("S2", 5): 3.93, ("S1", 3): 3.84, ("S1", 5): 4.65}
print("pop  m   skew   exKurt   size(1st order)  size(1st+2nd)  observed plain t")
for name, comps in POPS.items():
    for m in (3, 5):
        mu, v, g, k = moments(comps, m)
        s1, s2 = predict(g, k)
        print("%-3s %d  %+.3f  %+.3f   %.2f%%           %.2f%%         %.2f%%   (mean %.3f, var %.3f)" % (name, m, g, k, s1, s2, OBS[(name, m)], mu, v))
