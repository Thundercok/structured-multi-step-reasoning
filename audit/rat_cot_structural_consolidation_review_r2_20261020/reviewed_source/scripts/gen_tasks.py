#!/usr/bin/env python3
"""Procedural reasoning tasks: exact gold by construction + independent re-verification.

Families: arith (multi-step integer chain), order (unique-answer ordering puzzle), g24 (Game of 24).
One variant per group. Splits are by group, stratified by difficulty level.

  python gen_tasks.py --n-per-level 15 --seed 0 --out data/gen_v2.json
  python gen_tasks.py --verify data/gen_v2.json
  python gen_tasks.py --selftest

Harness contract: check(item, pred_str) -> bool. Use it instead of string match for EVERY item
(g24 accepts any valid expression, not just the reference one).
"""
import argparse, ast, hashlib, itertools, json, os, random, re, sys, time
from collections import Counter
from fractions import Fraction

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

VERSION = "0.2.2"
NAMES = ["Alice", "Bob", "Carol", "Dave", "Erin", "Frank", "Grace", "Heidi"]
ORD = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th"]
ARITH_LEVELS = [(2, 2, 9), (4, 3, 9), (6, 4, 9), (8, 5, 99), (10, 5, 99)]  # (steps, digits, max multiplier)
ORDER_LEVELS = [5, 6, 7, 8]                                                 # runners
G24_LEVELS = [(17, 10**9), (8, 16), (4, 7), (1, 3)]                         # (min, max) distinct solution strings
FAMILIES = ("arith", "order", "g24")
PERMS = {n: list(itertools.permutations(range(n))) for n in (4, 5, 6, 7, 8)}


# ---------- arith ----------
def render_arith(m):
    verb = {"add": "add {}", "sub": "subtract {}", "mul": "multiply the result by {}", "div": "divide the result by {}"}
    steps = "; ".join(f"({i}) " + verb[op].format(x) for i, (op, x) in enumerate(m["steps"], 1))
    return f"A counter starts at {m['start']}. Apply these steps in order: {steps}. What is the final value of the counter?"


def run_arith(m):  # independent evaluator: steps -> value
    v = m["start"]
    for op, x in m["steps"]:
        if op == "add": v += x
        elif op == "sub": v -= x
        elif op == "mul": v *= x
        else:
            assert v % x == 0, "non-integer division"
            v //= x
        assert v >= 0, "negative intermediate"
    return v


def gen_arith(rng, level):
    depth, digits, kmax = ARITH_LEVELS[level]
    lo, hi = 10 ** (digits - 1), 10 ** digits - 1
    m = {"start": rng.randint(lo, hi), "steps": []}
    v = m["start"]
    for _ in range(depth):
        ops = ["add", "mul"] + (["sub"] if v > 1 else []) + (["div"] if any(v % k == 0 for k in range(2, 10)) else [])
        op = rng.choice(ops)
        if op == "add": x = rng.randint(lo, hi); v += x
        elif op == "sub": x = rng.randint(1, min(hi, v)); v -= x
        elif op == "mul": x = rng.randint(2, kmax); v *= x
        else: x = rng.choice([k for k in range(2, 10) if v % k == 0]); v //= x
        m["steps"].append([op, x])
    return m, render_arith(m), str(run_arith(m)), {"steps": depth, "digits": digits, "max_mult": kmax}


# ---------- order ----------
def holds(c, pos):  # pos[i] = position of entity i
    t, x, y = c[0], c[1], c[2]
    if t == "b": return pos[x] < pos[y]
    if t == "a": return pos[y] == pos[x] + 1
    if t in ("g", "gap"): return pos[y] == pos[x] + c[3]
    raise ValueError(f"Unknown clue type: {t}")


def render_order(m, gap_style=None):
    if gap_style is None:
        gap_style = m.get("gap_style", "A")
    names, txt = m["names"], []
    for c in m["clues"]:
        t, x, y = c[0], c[1], c[2]
        if t == "a": txt.append(f"{names[x]} finished immediately before {names[y]}")
        elif t == "b":
            if (x + y) % 2: txt.append(f"{names[x]} finished before {names[y]}")
            else: txt.append(f"{names[y]} finished after {names[x]}")
        elif t in ("g", "gap"):
            k = c[3]
            if gap_style == "B":
                txt.append(f"{names[x]} finished {k} places ahead of {names[y]}: if {names[x]} is in position p, then {names[y]} is in position p+{k}")
            else:
                between = k - 1
                noun = "runner" if between == 1 else "runners"
                txt.append(f"{names[x]} finished exactly {k} places ahead of {names[y]}, with exactly {between} {noun} between them")
        else:
            raise ValueError(f"Unknown clue type: {t}")
    names_str = ", ".join(names)
    ask_ord = ORD[m["ask"]]
    return (f"{len(names)} runners ({names_str}) ran a race with no ties. Clues: " + "; ".join(txt)
            + f". Who finished in {ask_ord} place?")


def consistent(m):  # independent brute force: occupants of the asked position over all consistent orders
    out = set()
    n = len(m["names"])
    perms = PERMS.get(n) or list(itertools.permutations(range(n)))
    for pos in perms:
        if all(holds(c, pos) for c in m["clues"]):
            out.add(pos.index(m["ask"]))
    return out


def canonical_order_key(m):
    n = len(m["names"])
    clues = m["clues"]
    perms = PERMS.get(n) or list(itertools.permutations(range(n)))
    norm_clues = [(c[0], c[1], c[2], c[3] if len(c) > 3 else (1 if c[0] == "a" else 0)) for c in clues]
    min_relabeling = min(
        tuple(sorted((t, p[x], p[y], k) for t, x, y, k in norm_clues))
        for p in perms
    )
    return (n, m["ask"], min_relabeling)


def gen_order(rng, level, gap_style="A"):
    n = ORDER_LEVELS[level]
    names = rng.sample(NAMES, n)
    truth = list(range(n)); rng.shuffle(truth)  # truth[i] = position of entity i
    ask = rng.randrange(n)
    cands = [("b", x, y, 0) for x, y in itertools.permutations(range(n), 2) if truth[x] < truth[y]]
    cands += [("a", x, y, 1) for x, y in itertools.permutations(range(n), 2) if truth[y] == truth[x] + 1]
    for k in (2, 3):
        cands += [("g", x, y, k) for x, y in itertools.permutations(range(n), 2) if truth[y] == truth[x] + k]
    rng.shuffle(cands)
    allp = PERMS[n]
    clues, alive = [], allp
    for c in cands:  # add true clues until the asked position is determined
        clues.append(c); alive = [p for p in alive if holds(c, p)]
        if len({p.index(ask) for p in alive}) == 1: break
    for c in list(clues):  # prune to a minimal sufficient set: every clue is needed
        rest = [d for d in clues if d != c]
        if len({p.index(ask) for p in allp if all(holds(d, p) for d in rest)}) == 1: clues = rest
    rng.shuffle(clues)
    m = {"names": names, "clues": [list(c) for c in clues], "ask": ask, "gap_style": gap_style}
    return m, render_order(m, gap_style=gap_style), names[truth.index(ask)], {"runners": n, "clues": len(clues)}


# ---------- g24 ----------
def sols24(nums):  # distinct solution strings (commutative ops canonicalised once per unordered pair)
    out = set()

    def rec(items):
        if len(items) == 1:
            if items[0][0] == 24: out.add(items[0][1])
            return
        for i in range(len(items)):
            for j in range(len(items)):
                if i == j: continue
                (a, ea), (b, eb) = items[i], items[j]
                rest = [t for k, t in enumerate(items) if k not in (i, j)]
                opts = [(a - b, f"({ea}-{eb})")]
                if i < j: opts += [(a + b, f"({ea}+{eb})"), (a * b, f"({ea}*{eb})")]
                if b: opts.append((a / b, f"({ea}/{eb})"))
                for v, e in opts: rec(rest + [(v, e)])

    rec([(Fraction(x), str(x)) for x in nums])
    return out


def check24(expr, nums):
    try:
        parts = expr.replace("×", "*").replace("÷", "/").split("=")
        if len(parts) > 2 or (len(parts) == 2 and not re.fullmatch(r"\s*24(?:\.0+)?\s*", parts[1])):
            return False
        tree = ast.parse(parts[0].strip(), mode="eval").body
        used = []

        def ev(n):
            if isinstance(n, ast.Constant) and type(n.value) is int:
                used.append(n.value); return Fraction(n.value)
            if isinstance(n, ast.BinOp) and type(n.op) in (ast.Add, ast.Sub, ast.Mult, ast.Div):
                a, b = ev(n.left), ev(n.right)
                if isinstance(n.op, ast.Add): return a + b
                if isinstance(n.op, ast.Sub): return a - b
                if isinstance(n.op, ast.Mult): return a * b
                return a / b
            raise ValueError("disallowed")

        return ev(tree) == 24 and sorted(used) == sorted(nums)
    except Exception:
        return False


def render_g24(m):
    a, b, c, d = m["numbers"]
    return (f"Using each of the numbers {a}, {b}, {c} and {d} exactly once, together with +, -, *, / and "
            f"parentheses, write an expression that equals 24.")


def gen_g24(rng, level):
    lo, hi = G24_LEVELS[level]
    for _ in range(10_000):
        nums = [rng.randint(1, 13) for _ in range(4)]
        s = sols24(nums)
        if lo <= len(s) <= hi:
            m = {"numbers": nums}
            return m, render_g24(m), min(s, key=lambda e: (len(e), e)), {"n_solutions": len(s)}
    raise RuntimeError("difficulty band is empty")


# ---------- check / verify / build ----------
def check(item, pred):
    pred = (pred or "").strip()
    f = item["family"]
    if f == "arith":
        from research_scoring import numeric_literal
        scalar = numeric_literal(pred, item.get("decimal_separator", "."), allow_units=True)
        return scalar is not None and Fraction(scalar) == Fraction(item["answer"])
    if f == "order":
        match = re.fullmatch(r"([A-Za-z]+)(?:\s+finished\s+(?:in\s+)?(\d+(?:st|nd|rd|th))(?:\s+place)?)?\.?", pred, re.I)
        if not match or match.group(1).casefold() != item["answer"].casefold():
            return False
        ask = item.get("meta", {}).get("ask")
        return match.group(2) is None or ask is None or match.group(2).casefold() == ORD[ask]
    if f == "g24":
        return check24(pred, item["meta"]["numbers"])
    raise KeyError(f)


def verify(item):  # uses only serialised fields; never trusts generator state; corrupt item -> False, not crash
    try:
        return _verify(item)
    except Exception:
        return False


def _verify(item):
    f, m = item["family"], item["meta"]
    if f == "arith":
        return render_arith(m) == item["query"] and str(run_arith(m)) == item["answer"]
    if f == "order":
        return render_order(m, gap_style=m.get("gap_style", "A")) == item["query"] and consistent(m) == {m["names"].index(item["answer"])}
    if f == "g24":
        return render_g24(m) == item["query"] and check24(item["answer"], m["numbers"]) and bool(sols24(m["numbers"]))
    return False


def _key(fam, m, q):
    if fam == "g24":
        return tuple(sorted(m["numbers"]))
    if fam == "order":
        return canonical_order_key(m)
    return q


def build(n_per_level=15, seed=0, ratios=(0.2, 0.4, 0.4), families=FAMILIES, gap_style="A"):
    rng = random.Random(seed)
    gens = {"arith": (gen_arith, len(ARITH_LEVELS)), "order": (gen_order, len(ORDER_LEVELS)), "g24": (gen_g24, len(G24_LEVELS))}
    b = [round(n_per_level * sum(ratios[:i + 1])) for i in range(len(ratios))]
    b[-1] = n_per_level
    items = []
    for fam in families:
        fn, n_levels = gens[fam]
        seen, idx = set(), 0
        for lvl in range(n_levels):
            for i in range(n_per_level):
                while True:
                    if fam == "order":
                        m, q, a, diff = fn(rng, lvl, gap_style=gap_style)
                    else:
                        m, q, a, diff = fn(rng, lvl)
                    k = _key(fam, m, q)
                    if k not in seen:
                        break
                seen.add(k)
                split = "dev" if i < b[0] else "calib" if i < b[1] else "test"
                items.append({"id": f"{fam}_{idx:04d}_en_orig", "group_id": f"grp_{fam}_{idx:04d}", "query": q,
                              "answer": a, "split": split, "category": fam, "family": fam, "level": lvl + 1,
                              "difficulty": diff, "checker": fam, "source": f"procedural:gen_tasks.py@{VERSION}/seed={seed}",
                              "meta": m})
                idx += 1
    return items


def digest(items):
    return hashlib.sha256(json.dumps(items, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def dump(items, path, seed, n_per_level):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    meta = {"generator": f"gen_tasks.py {VERSION}", "seed": seed, "n_per_level": n_per_level,
            "n_items": len(items), "sha256_items": digest(items)}
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "items": items}, f, ensure_ascii=False, indent=1)
    return meta


def verify_file(path):
    d = json.load(open(path, encoding="utf-8"))
    items = d["items"]
    bad = [it["id"] for it in items if not verify(it)]
    gids = [it["group_id"] for it in items]
    print(f"items={len(items)} verify_fail={len(bad)} dup_groups={len(gids) - len(set(gids))} "
          f"sha_match={digest(items) == d['meta']['sha256_items']}")
    return not bad and len(gids) == len(set(gids)) and digest(items) == d["meta"]["sha256_items"]


def table(items):
    rows = Counter((it["family"], it["level"], it["split"]) for it in items)
    print(f"{'family':6} {'lvl':3} {'dev':>4} {'calib':>5} {'test':>4}  difficulty range")
    for fam in FAMILIES:
        for lvl in sorted({it["level"] for it in items if it["family"] == fam}):
            ds = [it["difficulty"] for it in items if it["family"] == fam and it["level"] == lvl]
            k = [k for k in ds[0] if k in ("n_solutions", "clues", "steps")][0]
            vals = [d[k] for d in ds]
            print(f"{fam:6} {lvl:3} {rows[(fam, lvl, 'dev')]:4} {rows[(fam, lvl, 'calib')]:5} {rows[(fam, lvl, 'test')]:4}"
                  f"  {k}={min(vals)}..{max(vals)}")


def selftest():
    t0 = time.time()
    a, b = build(3, seed=1), build(3, seed=1)
    assert digest(a) == digest(b), "not deterministic"
    assert digest(a) != digest(build(3, seed=2)), "seed ignored"
    assert all(verify(it) for it in a), "verify failed"
    gids = [it["group_id"] for it in a]; assert len(gids) == len(set(gids))
    for fam in FAMILIES:  # canonical duplicates = 0 on every build
        fam_items = [it for it in a if it["family"] == fam]
        fam_keys = [_key(it["family"], it["meta"], it["query"]) for it in fam_items]
        assert len(fam_keys) == len(set(fam_keys)), f"Canonical duplicates found in {fam}"
    for fam in FAMILIES:  # gold must satisfy check() and every wrong answer must fail it
        for it in (x for x in a if x["family"] == fam):
            assert check(it, it["answer"]), (fam, it["id"])
    ar = {"family": "arith", "answer": "192"}
    assert all(check(ar, p) for p in ["192", "192 slices", "192.0", "$192", "192."])
    assert not any(check(ar, p) for p in ["191", "24*8 = 192", "", "1,92", "192 and 5"])
    orr = {"family": "order", "answer": "Carol"}
    assert all(check(orr, p) for p in ["Carol", "carol.", "Carol finished 3rd"])
    assert not any(check(orr, p) for p in ["Bob", "Carol or Bob", ""])
    assert holds(["g", 0, 2, 2], [0, 1, 2])
    assert not holds(["g", 0, 2, 2], [0, 2, 1])
    g = {"family": "g24", "meta": {"numbers": [1, 2, 3, 4]}}
    assert all(check(g, p) for p in ["1*2*3*4", "(1+2+3)*4", "(1+2+3)*4 = 24", "4*3*2*1"])
    assert not any(check(g, p) for p in ["(1+2+3)*5", "24", "1*2*3*4*1", "-1+25", "2**3*3*1", "(1+2+3)*4.0", "1/0*2*3*4", "1*2*3"])
    for it in a:  # the independent checker must reject a corrupted gold
        bad = dict(it, answer=it["answer"] + "7" if it["family"] == "arith" else "Zed" if it["family"] == "order" else "1+1+1+1")
        assert not verify(bad), ("corrupted gold accepted", it["id"])
    print(f"selftest OK ({len(a)} items, {time.time() - t0:.1f}s)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-per-level", type=int, default=15)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--gap-style", default="A", choices=["A", "B"])
    ap.add_argument("--out", default="data/gen02_v2.json")
    ap.add_argument("--verify", metavar="PATH")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest: return selftest()
    if a.verify: sys.exit(0 if verify_file(a.verify) else 1)
    items = build(a.n_per_level, a.seed, gap_style=a.gap_style)
    meta = dump(items, a.out, a.seed, a.n_per_level)
    print(json.dumps(meta)); table(items)


if __name__ == "__main__":
    main()
