"""Does the sign/size of gamma change when the mean CONT accuracy is the PILOT's 0.667 (not 0.42-0.58)?  Exact (gamma, kurt) of x_i (homogeneous shift p=min(1,q+0.10))
for 3 q-shapes x mean q in {.35,...,.85}, and 2nd-order Edgeworth plain-t sizes (GO / NO-GO, n=60, t_.975,59=2.0010)."""
import math
N, DELTA = 60, 0.10
Phi = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
phi = lambda x: math.exp(-x * x / 2) / math.sqrt(2 * math.pi)
def exact(comps, m):
    pts = []
    for w, q in comps:
        p = min(1.0, q + DELTA)
        for c in (0, 1):
            pc = q if c else 1 - q
            for k in range(m + 1):
                pts.append((w * pc * math.comb(m, k) * p ** k * (1 - p) ** (m - k), (k - m * c) / m))
    mu = sum(pr * x for pr, x in pts)
    c2 = sum(pr * (x - mu) ** 2 for pr, x in pts)
    c3 = sum(pr * (x - mu) ** 3 for pr, x in pts)
    c4 = sum(pr * (x - mu) ** 4 for pr, x in pts)
    return mu, c3 / c2 ** 1.5, c4 / c2 ** 2 - 3
def predict(g, k):
    x = 2.0010 * math.sqrt(N / (N - 1))
    q1 = g * (2 * x * x + 1) / 6
    q2 = x * (k * (x * x - 3) / 12 - g * g * (x ** 4 + 2 * x * x - 3) / 18 - (x * x + 3) / 4)
    a, b = q1 * phi(x) / math.sqrt(N), q2 * phi(x) / N
    return 100 * (1 - (Phi(x) + a + b)), 100 * (Phi(-x) + a - b)
def shapeA(mq, lo=0.05, hi=0.90):                 # hard (q=lo) + easy (q=hi) questions
    w = (mq - lo) / (hi - lo)
    return [(1 - w, lo), (w, hi)]
def shapeB(mq, half=0.30, k=400):                 # uniform spread, clipped to [0.02, 0.95]
    a, b = max(0.02, mq - half), min(0.95, mq + half)
    return [(1 / k, a + (b - a) * (i + 0.5) / k) for i in range(k)]
def shapeC(mq, d=0.20):                           # two moderate levels
    return [(0.5, max(0.02, mq - d)), (0.5, min(0.95, mq + d))]
print("shape mean_q | m=3: gamma kurt  GO%  NOGO% | m=5: gamma kurt  GO%  NOGO%    (2nd-order Edgeworth, nominal 2.50)")
for nm, f in (("A hard/easy .05/.90", shapeA), ("B uniform +-.30", shapeB), ("C two-level +-.20", shapeC)):
    for mq in (0.35, 0.45, 0.55, 0.65, 0.75, 0.85):
        row = []
        for m in (3, 5):
            comps = f(mq)
            mu, g, k = exact(comps, m)
            go, no = predict(g, k)
            row.append("%+.2f %+5.1f %.2f %.2f" % (g, k, go, no))
        realq = sum(w * q for w, q in f(mq))
        print("%-20s %.2f (%.3f) | %s | %s" % (nm, mq, realq, row[0], row[1]))
