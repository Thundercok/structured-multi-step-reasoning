"""Recompute the scale-up results without the questions found in the training files."""
import collections
import json
import math
from pathlib import Path

RUN = Path(__file__).parent
TRAIN_FILES = ["data/structured_gsm8k_enriched_v1/train.jsonl", "data/structured_gsm8k_cf_enriched_v1/train.jsonl"]


def read(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def mcnemar(a, b):
    n = a + b
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(a, b) + 1)) / 2**n) if n else 1.0


def report(label, cf, plain, wins):
    ids = sorted(set(cf) & set(plain))
    a = sum(wins(cf[i]) and not wins(plain[i]) for i in ids)
    b = sum(wins(plain[i]) and not wins(cf[i]) for i in ids)
    print(f"{label}: n={len(ids)} cf={sum(wins(cf[i]) for i in ids)} plain={sum(wins(plain[i]) for i in ids)} "
          f"cf_only={a} plain_only={b} p={mcnemar(a, b):.4f}")


def main():
    questions = read(RUN / "data/dev_300.jsonl")
    split = {row["id"]: row["split"] for row in questions}
    for path in TRAIN_FILES:
        text = Path(path).read_text()
        found = sum(json.dumps(row["question"], ensure_ascii=False)[1:-1] in text
                    for row in questions if row["split"] == "heldout_tail")
        print(f"{path}: {found}/101 heldout_tail questions present")

    keep = {i for i, name in split.items() if name != "heldout_tail"}
    load = lambda name: {r["id"]: r for r in read(RUN / name) if r["id"] in keep}
    follows = lambda r: r["outcome"] == "follows"
    report("accuracy", load("eval_cf/tuned.jsonl"), load("eval_plain/tuned.jsonl"), lambda r: bool(r["check"]["correct"]))
    cf = load("eval_cf/tuned_interventions.jsonl")
    plain = load("eval_plain/tuned_interventions.jsonl")
    report("interventions", cf, plain, follows)

    load_sweep = lambda name: {r["id"]: r for r in read(RUN / name) if r["parent_id"] in keep}
    cf_sweep = load_sweep("step_sweep/eval_cf_sweep.jsonl")
    plain_sweep = load_sweep("step_sweep/eval_plain_sweep.jsonl")
    report("sweep", cf_sweep, plain_sweep, follows)
    shared = set(cf_sweep) & set(plain_sweep)
    print("sweep questions:", len({cf_sweep[i]["parent_id"] for i in shared}))
    by_step = collections.defaultdict(collections.Counter)
    for i in shared:
        by_step[cf_sweep[i]["k"]][cf_sweep[i]["outcome"]] += 1
    for step in sorted(by_step):
        print(f"cf k={step}", dict(by_step[step]))


if __name__ == "__main__":
    main()
