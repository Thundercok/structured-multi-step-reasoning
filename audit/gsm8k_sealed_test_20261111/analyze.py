"""Apply docs/sealed_test_gsm8k_prereg.md sections 3 and 4.

Usage: analyze.py CF_DIR PLAIN_DIR [BASE_DIR] [--exclude IDS_JSON] [--out FILE]
Each dir holds tuned.jsonl (or base_prefill.jsonl) and, for CF and Plain, tuned_interventions.jsonl.
"""

import argparse
from collections import Counter
import json
import math
from pathlib import Path

Z = 1.959963984540054


def read(path):
    return {r["id"]: r for r in map(json.loads, Path(path).read_text().splitlines()) if r}


def mcnemar(b, c):
    n = b + c
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2**n) if n else 1.0


def paired(x, y, ids, value):
    """b = only x has it, c = only y has it; Wald CI of the paired difference in proportions."""
    b = sum(value(x[i]) and not value(y[i]) for i in ids)
    c = sum(value(y[i]) and not value(x[i]) for i in ids)
    n = len(ids)
    diff = (b - c) / n
    se = math.sqrt(max(b + c - (b - c) ** 2 / n, 0)) / n
    return {"n": n, "x": sum(bool(value(x[i])) for i in ids), "y": sum(bool(value(y[i])) for i in ids),
            "only_x": b, "only_y": c, "p": mcnemar(b, c),
            "diff": diff, "ci95": [diff - Z * se, diff + Z * se]}


def wilson(k, n):
    p, d = k / n, 1 + Z**2 / n
    centre, half = (p + Z**2 / (2 * n)) / d, Z * math.sqrt(p * (1 - p) / n + Z**2 / (4 * n * n)) / d
    return [centre - half, centre + half]


def correct(r):
    return bool(r["check"]["correct"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cf")
    parser.add_argument("plain")
    parser.add_argument("base", nargs="?")
    parser.add_argument("--exclude")
    parser.add_argument("--out")
    args = parser.parse_args()
    drop = set(json.loads(Path(args.exclude).read_text())) if args.exclude else set()

    cf, plain = read(Path(args.cf) / "tuned.jsonl"), read(Path(args.plain) / "tuned.jsonl")
    if set(cf) != set(plain):
        raise SystemExit("CF and Plain answered different questions")
    ids = sorted(set(cf) - drop)

    cf_int = read(Path(args.cf) / "tuned_interventions.jsonl")
    plain_int = read(Path(args.plain) / "tuned_interventions.jsonl")
    shared = sorted((set(cf_int) & set(plain_int)) - drop)
    h1 = paired(cf_int, plain_int, shared, lambda r: r["outcome"] == "follows")
    h1["verdict"] = "supports" if h1["only_x"] > h1["only_y"] and h1["p"] < 0.05 else "does not support"

    fmt = sum(bool(cf[i]["check"]["format_valid"]) for i in ids)
    calcs = sum(cf[i]["check"]["calcs"] for i in ids)
    wrong = sum(cf[i]["check"]["calcs"] * (1 - cf[i]["check"]["calc_accuracy"])
                for i in ids if cf[i]["check"]["calcs"])
    result = {
        "questions": len(ids),
        "excluded": len(drop & set(cf)),
        "H1_follows_cf_vs_plain": h1,
        "S1_accuracy_cf_vs_plain": paired(cf, plain, ids, correct),
        "T1_format_valid_cf": {"k": fmt, "n": len(ids), "rate": fmt / len(ids), "wilson95": wilson(fmt, len(ids)),
                               "met": fmt / len(ids) >= 0.90 and wilson(fmt, len(ids))[0] >= 0.88},
        "T3_calc_error_cf": {"calcs": calcs, "wrong": round(wrong), "rate": wrong / calcs if calcs else None,
                             "met": bool(calcs) and wrong / calcs < 0.01},
        "S3_taxonomy": {"cf": Counter(cf_int[i]["outcome"] for i in shared),
                        "plain": Counter(plain_int[i]["outcome"] for i in shared),
                        "planned_cf": len(cf_int), "planned_plain": len(plain_int)},
        "S4_truncated": {"cf": sum(cf[i]["truncated"] for i in ids), "plain": sum(plain[i]["truncated"] for i in ids)},
    }
    if args.base:
        base = read(Path(args.base) / "base_prefill.jsonl")
        if set(base) != set(cf):
            raise SystemExit("base_prefill answered different questions")
        s2 = paired(cf, base, ids, correct)
        s2["met"] = s2["ci95"][0] > -0.03
        result["S2_noninferiority_cf_vs_base_prefill"] = s2
        result["S4_truncated"]["base_prefill"] = sum(base[i]["truncated"] for i in ids)

    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n")


if __name__ == "__main__":
    main()
