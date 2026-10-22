import re, sys
src = open("gonogo.py").read()

find_n = '''def find_n(delta, effect, d, state, target=0.80, n_hi=1500, window=30, coarse=10, z=Z):
    """(first n, stable n) with P(state) >= target; coarse scan, then step-1 refinement around the first hit"""
    k = 0 if state == "GO" else 1

    def p(n):
        return state_probs(n, effect, d, delta, z)[k]

    n = coarse
    while n <= n_hi and p(n) < target:
        n += coarse
    if n > n_hi:
        return None, None
    curve = {m: p(m) for m in range(max(10, n - 3 * coarse), n + window + coarse + 1)}
    return first_n(curve, target), stable_n(curve, target, window)


'''
marker = "def p_at_least(N, prev, k):"
assert src.count(marker) == 1
src = src.replace(marker, find_n + marker)

new_operating = '''def operating():
    def grid(dp):
        return [dp + 0.01 * i for i in range(90) if dp + 0.01 * i <= 0.9]

    print("== actual size at the boundary (true effect == delta_prac): worst case over discordance d ==")
    print("delta_prac     n | max P(GO) at d      | max P(NO-GO) at d")
    for dp in (0.10, 0.05):
        for n in (50, 100, 150, 250):
            res = [(d, *state_probs(n, dp, d, dp)[:2]) for d in grid(dp)]
            g, h = max(res, key=lambda r: r[1]), max(res, key=lambda r: r[2])
            print(f"{dp:.2f}       {n:5d} | {g[1]:.4f} (d={g[0]:.2f})   | {h[2]:.4f} (d={h[0]:.2f})")

    print("\\n== n for power >= .80: first / stable(30 consecutive n) ==")
    ds = (0.2, 0.3, 0.4)
    for dp, effs in ((0.10, (0.15, 0.20, 0.25)), (0.05, (0.10, 0.15))):
        for eff in effs:
            cells = [find_n(dp, eff, d, "GO") for d in ds]
            print(f"GO    delta_prac={dp:.2f} effect={eff:.2f} | " + " | ".join(f"d={d}: {f}/{s}" for d, (f, s) in zip(ds, cells)))
    for dp, effs in ((0.10, (0.0, 0.05)), (0.05, (0.0,))):
        for eff in effs:
            cells = [find_n(dp, eff, d, "NO-GO") for d in ds]
            print(f"NO-GO delta_prac={dp:.2f} effect={eff:.2f} | " + " | ".join(f"d={d}: {f}/{s}" for d, (f, s) in zip(ds, cells)))


'''
i = src.index("def operating():")
j = src.index('if __name__ == "__main__":')
src = src[:i] + new_operating + src[j:]
open("gonogo.py", "w").write(src)
print("spliced; lines:", src.count("\n"))
