"""Paired-binary decision numbers for the q=1 follow-up advice (stdlib only).

b = #items where arm X correct & arm Y wrong, c = reverse, n = #items.
GO      : exact two-sided sign test p < .05 and b > c (single criterion; delta_min only sets n)
NO-GO   : upper end of the 95% Tango score CI for (X - Y) < delta_min
CI      : Tango (1998) score interval, computed here by numeric inversion
"""
import math
from math import comb, lgamma, log, sqrt

Z = 1.959963984540054


def tango_z(b, c, n, d0):
    r = n - b - c
    lo = max(0.0, -d0) + 1e-13
    hi = (1 - d0) / 2 - 1e-13
    if hi <= lo:
        return float("nan")

    def g(q):
        t = 0.0
        if b:
            t += b / (q + d0)
        if c:
            t += c / q
        if r:
            t -= 2 * r / (1 - 2 * q - d0)
        return t

    if g(lo) <= 0:
        q = lo
    elif g(hi) >= 0:
        q = hi
    else:
        a, bb = lo, hi
        for _ in range(80):
            m = (a + bb) / 2
            if g(m) > 0:
                a = m
            else:
                bb = m
        q = (a + bb) / 2
    var = n * ((q + d0) + q - d0 * d0)
    num = b - c - n * d0
    if var <= 0:
        return math.copysign(float("inf"), num) if num else 0.0
    return num / sqrt(var)


def solve(b, c, n, target, a, bb):
    fa = tango_z(b, c, n, a) - target
    fb = tango_z(b, c, n, bb) - target
    if fa < 0:
        return a
    if fb > 0:
        return bb
    for _ in range(60):
        m = (a + bb) / 2
        if tango_z(b, c, n, m) - target > 0:
            a = m
        else:
            bb = m
    return (a + bb) / 2


def tango_ci(b, c, n):
    dh = (b - c) / n
    lo = solve(b, c, n, Z, -0.999, dh)
    up = solve(b, c, n, -Z, dh, 0.999)
    return max(lo, -1.0), min(up, 1.0)


def sign_p(b, c):
    m = b + c
    if m == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(m, i) for i in range(k + 1)) / 2**m)
