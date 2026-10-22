"""Independent check of the n-for-80%-power rows I quote: full step-1 scan from n=10 (no coarse prescan),
compared with find_n(). Usage: python verify_rows.py GO|NOGO"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gonogo as g  # noqa: E402

kind = sys.argv[1]
rows = (
    [("GO", 0.10, 0.20, d) for d in (0.2, 0.3, 0.4)]
    if kind == "GO"
    else [("NO-GO", 0.10, 0.0, d) for d in (0.2, 0.3, 0.4)]
)
for state, dp, eff, d in rows:
    fast = g.find_n(dp, eff, d, state)
    top = fast[0] + 45
    curve = g.prob_curve(dp, eff, d, state, 10, top, 1)
    full = (g.first_n(curve), g.stable_n(curve, 0.80, 30))
    below = [n for n, p in curve.items() if p >= 0.80 and n < full[1]]
    print(
        f"{state:5s} delta_prac={dp:.2f} effect={eff:+.2f} d={d}: find_n={fast[0]}/{fast[1]} | full step-1 scan={full[0]}/{full[1]}"
        f" | match={fast == full} | n with power>=.80 below stable n: {below[:6]}{'...' if len(below) > 6 else ''}"
        f" | power at first={curve[full[0]]:.4f}",
        flush=True,
    )
