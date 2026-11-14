"""Apply docs/gsm_plus_replication_prereg.md sections 3 and 4.

Usage: analyze.py [RUN_DIR]  (default: this folder). RUN_DIR holds eval_cf, eval_plain and eval_base.
"""

from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("sealed", HERE.parent / "gsm8k_sealed_test_20261111/analyze.py")
sealed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sealed)
read, paired, wilson, correct = sealed.read, sealed.paired, sealed.wilson, sealed.correct


def follows(r):
    return r["outcome"] == "follows"


def holm(tests, alpha=0.05):
    """tests: {name: (p, right_direction)}. Holm step-down; stop at the first p that misses its threshold."""
    passed, order = {}, sorted(tests, key=lambda k: tests[k][0])
    alive = True
    for rank, name in enumerate(order):
        p, right = tests[name]
        alive = alive and p < alpha / (len(order) - rank)
        passed[name] = "supports" if alive and right else "does not support"
    return passed


def main():
    run = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
    cf, plain = read(run / "eval_cf/tuned.jsonl"), read(run / "eval_plain/tuned.jsonl")
    base = read(run / "eval_base/base_prefill.jsonl")
    if not set(cf) == set(plain) == set(base):
        raise SystemExit("models answered different questions")
    ids = sorted(cf)
    ints = {"cf": read(run / "eval_cf/tuned_interventions.jsonl"),
            "plain": read(run / "eval_plain/tuned_interventions.jsonl"),
            "base_prefill": read(run / "eval_base/base_prefill_interventions.jsonl")}

    h1 = paired(ints["cf"], ints["plain"], sorted(set(ints["cf"]) & set(ints["plain"])), follows)
    h2 = paired(ints["plain"], ints["base_prefill"], sorted(set(ints["plain"]) & set(ints["base_prefill"])), follows)
    verdict = holm({"H1": (h1["p"], h1["only_x"] > h1["only_y"]), "H2": (h2["p"], h2["only_y"] > h2["only_x"])})
    h1["verdict"], h2["verdict"] = verdict["H1"], verdict["H2"]

    models = {"cf": cf, "plain": plain, "base_prefill": base}
    result = {
        "questions": len(ids),
        "H1_follows_cf_vs_plain": h1,
        "H2_follows_plain_vs_base_prefill": h2,
        "accuracy": {k: {"k": sum(correct(m[i]) for i in ids), "wilson95": wilson(sum(correct(m[i]) for i in ids), len(ids))}
                     for k, m in models.items()},
        "follows_cf_vs_base_prefill": paired(ints["cf"], ints["base_prefill"],
                                             sorted(set(ints["cf"]) & set(ints["base_prefill"])), follows),
        "planned": {k: len(v) for k, v in ints.items()},
        "taxonomy": {k: Counter(r["outcome"] for r in v.values()) for k, v in ints.items()},
        "truncated": {k: sum(m[i]["truncated"] for i in ids) for k, m in models.items()},
    }
    text = json.dumps(result, indent=2)
    print(text)
    if run == HERE:
        (HERE / "results.json").write_text(text + "\n")


if __name__ == "__main__":
    main()
