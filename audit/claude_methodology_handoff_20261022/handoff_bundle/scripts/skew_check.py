"""Population skewness / sparsity of the question-level mean x_i = mean_j(F_ij) - C_i (CONT once) at the boundary (effect = delta_prac).
Supports (or not) the claim that the cluster-t small-n error tracks skewness/sparsity.  stdlib, CPU only."""
import math, random
DELTA, N = 0.10, 400000
POPS = {"B": lambda r: 0.05 if r.random() < 0.6 else 0.40, "A": lambda r: r.uniform(0.2, 0.7)}
for name, s in POPS.items():
    for m in (1, 3, 5):
        rng = random.Random(11)
        xs = []
        for _ in range(N):
            q = s(rng); p = q + DELTA
            c = rng.random() < q
            xs.append(sum(int(rng.random() < p) for _ in range(m)) / m - int(c))
        mu = sum(xs) / N
        v = sum((x - mu) ** 2 for x in xs) / N
        m3 = sum((x - mu) ** 3 for x in xs) / N
        m4 = sum((x - mu) ** 4 for x in xs) / N
        nz = sum(1 for x in xs if x != 0) / N
        print(f"pop {name} m={m}: mean {mu:.3f} var {v:.3f} skew {m3 / v ** 1.5:+.3f} excess-kurt {m4 / v ** 2 - 3:+.3f} P(x!=0) {nz:.3f}")
