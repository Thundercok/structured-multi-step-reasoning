"""Apply docs/trace_source_prereg.md: H3 (self vs human, exact follows) and the descriptive measures.

Usage: analyze.py [RUN_DIR]  (default: this folder; RUN_DIR holds eval_self, eval_human, data/manifest.json).
Base and Plain 2000 come from audit/gsm_plus_replication_20261114 and are descriptive only.
"""

from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).parent
AUDIT = HERE.parent
ALPHA = 0.05


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sealed = module("sealed", AUDIT / "gsm8k_sealed_test_20261111/analyze.py")
read, paired, wilson, correct = sealed.read, sealed.paired, sealed.wilson, sealed.correct
FIRST = AUDIT / "gsm_plus_replication_20261114"


def follows(r):
    return r["outcome"] == "follows"


def main():
    run = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
    paths = {"self": run / "eval_self", "human": run / "eval_human"}
    data = {k: (read(p / "tuned.jsonl"), read(p / "tuned_interventions.jsonl")) for k, p in paths.items()}
    data["base"] = (read(FIRST / "eval_base/base_prefill.jsonl"), read(FIRST / "eval_base/base_prefill_interventions.jsonl"))
    data["plain_2000"] = (read(FIRST / "eval_plain/tuned.jsonl"), read(FIRST / "eval_plain/tuned_interventions.jsonl"))
    ids = sorted(data["base"][0])
    if any(set(evals) != set(ids) for evals, _ in data.values()):
        raise SystemExit("runs answered different questions")

    x, y = data["self"][1], data["human"][1]
    h3 = paired(x, y, sorted(set(x) & set(y)), follows)
    if h3["p"] >= ALPHA:
        reading = "not distinguishable"
    elif h3["only_x"] > h3["only_y"]:
        reading = "trace source matters; self traces keep step-following better"
    else:
        reading = "trace source matters; human traces keep step-following better"

    describe = {}
    for k, (evals, ints) in data.items():
        n = len(ints)
        describe[k] = {"planned": n, "follows": sum(follows(r) for r in ints.values()),
                       "follows_rate": sum(follows(r) for r in ints.values()) / n if n else None,
                       "accuracy": sum(correct(evals[i]) for i in ids),
                       "accuracy_wilson95": wilson(sum(correct(evals[i]) for i in ids), len(ids)),
                       "truncated": sum(evals[i]["truncated"] for i in ids),
                       "answer_format": Counter(str(evals[i].get("answer_format")) for i in ids),
                       "format_valid": sum(bool(evals[i]["check"]["format_valid"]) for i in ids),
                       "taxonomy": Counter(r["outcome"] for r in ints.values())}
    manifest = json.loads((run / "data/manifest.json").read_text())
    check = run / "check.json"
    result = {"questions": len(ids), "H3_self_vs_human": h3, "alpha": ALPHA, "reading": reading,
              "training_set": manifest, "training_check": json.loads(check.read_text()) if check.exists() else None,
              "descriptive": describe}
    text = json.dumps(result, indent=2)
    print(text)
    if run == HERE:
        (HERE / "results.json").write_text(text + "\n")


if __name__ == "__main__":
    main()
