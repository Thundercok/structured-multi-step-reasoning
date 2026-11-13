"""Post-hoc: does base_prefill follow an edited step as often as the adapters?

Not pre-registered; written 2026-11-13 after the sealed results, before base_prefill interventions ran.
Compares exact `follows` on questions where all three models have an intervention plan.
"""

from collections import Counter
import json
import math
from pathlib import Path

RUN = Path(__file__).parent
FILES = {"cf": "eval_cf/tuned_interventions.jsonl", "plain": "eval_plain/tuned_interventions.jsonl",
         "base_prefill": "eval_base/base_prefill_interventions.jsonl"}


def read(path):
    return {r["id"]: r for r in map(json.loads, (RUN / path).read_text().splitlines())}


def mcnemar(b, c):
    n = b + c
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2**n) if n else 1.0


def main():
    runs = {name: read(path) for name, path in FILES.items()}
    shared = sorted(set.intersection(*(set(r) for r in runs.values())))
    follows = {name: {i for i in shared if r[i]["outcome"] == "follows"} for name, r in runs.items()}
    result = {
        "planned": {name: len(r) for name, r in runs.items()},
        "shared_all_three": len(shared),
        "follows": {name: len(f) for name, f in follows.items()},
        "taxonomy": {name: Counter(r[i]["outcome"] for i in shared) for name, r in runs.items()},
    }
    for name in ("cf", "plain"):
        b = len(follows[name] - follows["base_prefill"])
        c = len(follows["base_prefill"] - follows[name])
        result[f"{name}_vs_base_prefill"] = {"only_adapter": b, "only_base": c, "p": mcnemar(b, c)}
    text = json.dumps(result, indent=2)
    print(text)
    (RUN / "posthoc_base.json").write_text(text + "\n")


if __name__ == "__main__":
    main()
