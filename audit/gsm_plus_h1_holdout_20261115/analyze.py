"""Apply docs/gsm_plus_h1_holdout_prereg.md sections 3 and 4.

Usage: analyze.py [RUN_DIR]  (default: this folder). RUN_DIR holds eval_cf and eval_plain.
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
FIRST = HERE.parent / "gsm_plus_replication_20261114"


def follows(r):
    return r["outcome"] == "follows"


def load(run):
    cf, plain = read(run / "eval_cf/tuned.jsonl"), read(run / "eval_plain/tuned.jsonl")
    if set(cf) != set(plain):
        raise SystemExit(f"{run}: models answered different questions")
    return cf, plain, read(run / "eval_cf/tuned_interventions.jsonl"), read(run / "eval_plain/tuned_interventions.jsonl")


def main():
    run = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
    cf, plain, icf, ipl = load(run)
    ids = sorted(cf)
    h1 = paired(icf, ipl, sorted(set(icf) & set(ipl)), follows)
    h1["verdict"] = "supports" if h1["only_x"] > h1["only_y"] and h1["p"] < 0.05 else "does not support"

    result = {
        "questions": len(ids),
        "H1_follows_cf_vs_plain": h1,
        "accuracy": {k: {"k": sum(correct(m[i]) for i in ids), "wilson95": wilson(sum(correct(m[i]) for i in ids), len(ids))}
                     for k, m in {"cf": cf, "plain": plain}.items()},
        "accuracy_cf_vs_plain": paired(cf, plain, ids, correct),
        "planned": {"cf": len(icf), "plain": len(ipl)},
        "taxonomy": {"cf": Counter(r["outcome"] for r in icf.values()),
                     "plain": Counter(r["outcome"] for r in ipl.values())},
        "truncated": {k: sum(m[i]["truncated"] for i in ids) for k, m in {"cf": cf, "plain": plain}.items()},
    }
    if run == HERE:
        _, _, fcf, fpl = load(FIRST)
        if set(fcf) & set(icf):
            raise SystemExit("holdout overlaps the first 500")
        pcf, ppl = {**fcf, **icf}, {**fpl, **ipl}
        pooled = paired(pcf, ppl, sorted(set(pcf) & set(ppl)), follows)
        pooled.pop("p", None)  # descriptive only, section 4
        result["pooled_1319_descriptive"] = pooled
    text = json.dumps(result, indent=2)
    print(text)
    if run == HERE:
        (HERE / "results.json").write_text(text + "\n")


if __name__ == "__main__":
    main()
