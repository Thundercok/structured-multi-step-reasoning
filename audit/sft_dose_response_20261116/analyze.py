"""Apply docs/sft_dose_response_prereg.md (reading rule and descriptive measures).

Usage: analyze.py [RUN_DIR]  (default: this folder; RUN_DIR holds eval_50, eval_200, eval_1000).
Base and iteration 2000 come from audit/gsm_plus_replication_20261114.
"""

from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).parent
AUDIT = HERE.parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sealed = module("sealed", AUDIT / "gsm8k_sealed_test_20261111/analyze.py")
replication = module("replication", AUDIT / "gsm_plus_replication_20261114/analyze.py")
read, paired, wilson, correct, holm = sealed.read, sealed.paired, sealed.wilson, sealed.correct, replication.holm
FIRST = AUDIT / "gsm_plus_replication_20261114"


def follows(r):
    return r["outcome"] == "follows"


def marks(run):
    out = {"base": (FIRST / "eval_base/base_prefill.jsonl", FIRST / "eval_base/base_prefill_interventions.jsonl")}
    for it in (50, 200, 1000):
        out[str(it)] = (run / f"eval_{it}/tuned.jsonl", run / f"eval_{it}/tuned_interventions.jsonl")
    out["2000"] = (FIRST / "eval_plain/tuned.jsonl", FIRST / "eval_plain/tuned_interventions.jsonl")
    return {k: (read(a), read(b)) for k, (a, b) in out.items()}


def main():
    run = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
    data = marks(run)
    ids = sorted(data["base"][0])
    if any(set(evals) != set(ids) for evals, _ in data.values()):
        raise SystemExit("marks answered different questions")

    def test(a, b):
        x, y = data[a][1], data[b][1]
        return paired(x, y, sorted(set(x) & set(y)), follows)

    t1, t2 = test("base", "50"), test("50", "2000")
    verdict = holm({"T1": (t1["p"], t1["only_x"] > t1["only_y"]), "T2": (t2["p"], t2["only_x"] > t2["only_y"])})
    t1["verdict"], t2["verdict"] = verdict["T1"], verdict["T2"]
    reading = {("supports", "does not support"): "early drop",
               ("does not support", "supports"): "gradual drop",
               ("supports", "supports"): "early drop and further drop",
               ("does not support", "does not support"): "not distinguishable"}[(t1["verdict"], t2["verdict"])]

    curve = {}
    for k, (evals, ints) in data.items():
        n = len(ints)
        curve[k] = {"planned": n, "follows": sum(follows(r) for r in ints.values()),
                    "follows_rate": sum(follows(r) for r in ints.values()) / n if n else None,
                    "accuracy": sum(correct(evals[i]) for i in ids),
                    "accuracy_wilson95": wilson(sum(correct(evals[i]) for i in ids), len(ids)),
                    "truncated": sum(evals[i]["truncated"] for i in ids),
                    "answer_format": Counter(str(evals[i].get("answer_format")) for i in ids),
                    "taxonomy": Counter(r["outcome"] for r in ints.values())}
    result = {"questions": len(ids), "T1_base_vs_50": t1, "T2_50_vs_2000": t2, "reading": reading,
              "curve_descriptive": curve}
    text = json.dumps(result, indent=2)
    print(text)
    if run == HERE:
        (HERE / "results.json").write_text(text + "\n")


if __name__ == "__main__":
    main()
