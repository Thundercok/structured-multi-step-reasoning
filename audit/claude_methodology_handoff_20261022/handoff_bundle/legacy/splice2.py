src = open("gonogo.py").read()

def sub(old, new):
    global src
    assert src.count(old) == 1, old[:60]
    src = src.replace(old, new)

sub('''    go, no = cuts(n, delta, z)
    pi = ((d + effect) / 2) / d if d > 0 else 0.5
''', '''    if abs(effect) > d + 1e-12:
        raise ValueError("|effect| cannot exceed the discordance probability d")
    go, no = cuts(n, delta, z)
    pi = ((d + effect) / 2) / d if d > 0 else 0.5
''')

sub('''def p_at_least(N, prev, k):''', '''def worst_size(n, delta, z=Z):
    """(max P(GO), max P(NO-GO)) when the true effect sits exactly on delta_prac, max over discordance d"""
    ds = sorted({round(delta + 0.01 * i, 4) for i in range(91) if delta + 0.01 * i <= 0.9}
                | {round(delta + 0.001 * i, 4) for i in range(61)})
    res = [state_probs(n, delta, d, delta, z)[:2] for d in ds]
    return max(r[0] for r in res), max(r[1] for r in res)


def calibrate_z(n, delta, alpha=0.025, z_hi=3.0, iters=9):
    """critical value z* >= Z whose worst-case false-GO and false-NO-GO are both <= alpha (re-verified at the end)"""
    if max(worst_size(n, delta, Z)) <= alpha:
        return Z
    lo, hi = Z, z_hi
    for _ in range(iters):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if max(worst_size(n, delta, mid)) <= alpha else (mid, hi)
    assert max(worst_size(n, delta, hi)) <= alpha
    return hi


def p_at_least(N, prev, k):''')

sub('''def operating():
''', '''def _fs(dp, eff, d, state):
    if eff > d:
        return "n/a"
    first, stable = find_n(dp, eff, d, state)
    return f"{first}/{stable}"


def calibration():
    print("== z calibration: worst-case size at the boundary, nominal z=1.96 -> calibrated z* (alpha=.025 per side) ==")
    for dp, n in ((0.10, 100), (0.10, 150), (0.10, 250), (0.05, 150)):
        zc = calibrate_z(n, dp)
        g0, h0 = worst_size(n, dp)
        g1, h1 = worst_size(n, dp, zc)
        extra = ""
        if (dp, n) == (0.10, 250):
            extra = f" | power(+20pp, d=.3): {state_probs(n, .2, .3, dp)[0]:.3f} -> {state_probs(n, .2, .3, dp, zc)[0]:.3f}"
        print(f"delta_prac={dp:.2f} n={n:3d}: size GO/NO-GO {g0:.4f}/{h0:.4f} -> z*={zc:.3f}: {g1:.4f}/{h1:.4f}{extra}")
    print("\\n== N=12 pilot, delta_prac=.10, d=.3 ==")
    for eff in (0.20, 0.0):
        pg, pn, pu = state_probs(12, eff, 0.3, 0.10)
        print(f"true effect {eff:+.2f}: P(GO)={pg:.4f} P(NO-GO)={pn:.4f} P(UNDETERMINED)={pu:.4f}")


def operating():
''')

sub('''            cells = [find_n(dp, eff, d, "GO") for d in ds]
            print(f"GO    delta_prac={dp:.2f} effect={eff:.2f} | " + " | ".join(f"d={d}: {f}/{s}" for d, (f, s) in zip(ds, cells)))''',
    '''            print(f"GO    delta_prac={dp:.2f} effect={eff:.2f} | " + " | ".join(f"d={d}: {_fs(dp, eff, d, 'GO')}" for d in ds))''')
sub('''            cells = [find_n(dp, eff, d, "NO-GO") for d in ds]
            print(f"NO-GO delta_prac={dp:.2f} effect={eff:.2f} | " + " | ".join(f"d={d}: {f}/{s}" for d, (f, s) in zip(ds, cells)))''',
    '''            print(f"NO-GO delta_prac={dp:.2f} effect={eff:.2f} | " + " | ".join(f"d={d}: {_fs(dp, eff, d, 'NO-GO')}" for d in ds))''')

sub('''{"selftest": selftest, "report": report, "operating": operating}''',
    '''{"selftest": selftest, "report": report, "operating": operating, "calibrate": calibration}''')
sub('''    python gonogo.py report      tables quoted in the advice
''', '''    python gonogo.py report      tables quoted in the advice
    python gonogo.py operating   actual size at the boundary + n for 80% power
    python gonogo.py calibrate   z* that holds worst-case size at 2.5% per side
''')
open("gonogo.py", "w").write(src)
print("ok")
