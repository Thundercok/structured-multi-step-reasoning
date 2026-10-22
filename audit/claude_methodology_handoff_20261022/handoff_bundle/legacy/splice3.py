src = open("gonogo.py").read()
i = src.index("def calibrate_z(")
j = src.index("def p_at_least(N, prev, k):")
new = '''def calibrate_z(n, delta, alpha=0.025, coarse=0.02, fine=0.002, z_max=3.0):
    """first z on a grid (coarse scan, then fine scan inside the last coarse step) whose worst-case false-GO
    and false-NO-GO are both <= alpha. Size is sawtooth in z, so this is a verified choice, not a global minimum."""

    def ok(z):
        return max(worst_size(n, delta, z)) <= alpha

    if ok(Z):
        return Z
    z = Z
    while z < z_max:
        z += coarse
        if ok(z):
            break
    else:
        raise RuntimeError("no feasible z <= z_max")
    k = 1
    while Z + 0 < z - coarse + k * fine < z:
        if ok(z - coarse + k * fine):
            return z - coarse + k * fine
        k += 1
    return z


'''
src = src[:i] + new + src[j:]
open("gonogo.py", "w").write(src)
print("ok")
