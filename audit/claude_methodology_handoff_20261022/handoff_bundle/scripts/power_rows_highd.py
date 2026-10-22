"""n for 80% power at the discordance the 12-item pilot suggests (d ~ 0.5-0.6), delta_prac = 10pp.
d=0.4 rows are reproducibility anchors for the earlier table (expected first n: GO +20pp -> 288, NO-GO 0pp -> 315)."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gonogo as g  # noqa: E402

rows = [("GO", 0.20, 0.4), ("NO-GO", 0.0, 0.4)] + [
    (state, eff, d) for state, eff in (("GO", 0.20), ("GO", 0.25), ("NO-GO", 0.0)) for d in (0.5, 0.6)
]
for state, eff, d in rows:
    t = time.time()
    first, stable = g.find_n(0.10, eff, d, state)
    print(f"{state:5s} delta_prac=0.10 effect={eff:+.2f} d={d}: first n={first}, stable n={stable}  ({time.time() - t:.1f}s)",
          flush=True)
