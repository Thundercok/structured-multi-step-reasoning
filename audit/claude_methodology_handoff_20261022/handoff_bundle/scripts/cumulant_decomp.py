"""Law of total cumulance for x_i = mean_j F_ij - C_i:  k3(x) = E[k3(x|i)] + 3 Cov_i(mu_i, s2_i) + k3(mu_i),  Var(x) = E[s2_i] + Var(mu_i),
with mu_i = p_i - q_i, s2_i = q(1-q) + p(1-p)/m, k3(x|i) = p(1-p)(1-2p)/m^2 - q(1-q)(1-2q).  Which term separates the effect models E2 / E3 at the same q-law?"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import beta_exact as be

def decomp(comps, m):
    W = sum(w for w, q, p in comps)
    E = lambda f: sum(w * f(q, p) for w, q, p in comps) / W
    mu = lambda q, p: p - q
    s2 = lambda q, p: q * (1 - q) + p * (1 - p) / m
    k3w = lambda q, p: p * (1 - p) * (1 - 2 * p) / m ** 2 - q * (1 - q) * (1 - 2 * q)
    m_mu, m_s2 = E(mu), E(s2)
    var = m_s2 + E(lambda q, p: (mu(q, p) - m_mu) ** 2)
    t1 = E(k3w)
    t2 = 3 * E(lambda q, p: (mu(q, p) - m_mu) * (s2(q, p) - m_s2))
    t3 = E(lambda q, p: (mu(q, p) - m_mu) ** 3)
    return var, t1, t2, t3, (t1 + t2 + t3) / var ** 1.5

print("population (m=3)                      Var(x) | E[k3(x|i)]  3Cov(mu,s2)  k3(mu_i) | gamma (sum/Var^1.5)   check vs exact gamma")
hom = lambda lst: [(w, q, q + 0.10) for w, q in lst]
for name, comps in (
    ("M5 hom .05/.85 @ .4/.6", hom([(0.4, 0.05), (0.6, 0.85)])),
    ("PC0 mu.5 s.5 E2", be.with_effect(be.beta_grid(0.25, 0.25), "E2")),
    ("PC0 mu.5 s.5 E3", be.with_effect(be.beta_grid(0.25, 0.25), "E3")),
    ("PC2 mu.667 s.5 E2", be.with_effect(be.beta_grid(0.3335, 0.1665), "E2")),
    ("PC2 mu.667 s.5 E3", be.with_effect(be.beta_grid(0.3335, 0.1665), "E3")),
):
    var, t1, t2, t3, g = decomp(comps, 3)
    ex = be.exact(comps, 3)[2]
    print("%-34s %.3f | %+.4f     %+.4f      %+.4f | %+.3f              %+.3f" % (name, var, t1, t2, t3, g, ex))
