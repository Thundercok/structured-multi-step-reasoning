"""Exploratory: do human-trace adapters lose more answer margin in the last layers than self-trace adapters?

Written 2026-11-19 before computing any per-adapter final-layer statistic. Not pre-registered in docs/; every result
is exploratory. The metric and the reading rule were accepted by the student in chat the same day.

Where the idea came from (seen before writing this, so this is not a confirmation):
  - audit/base_lens_20261119: on `follows` cases the base model's mean d keeps rising to layer 36 (about 17.7),
    while Plain 2000 peaks near 16 at layers 33-34 and ends near 10 at layer 36. Plain loses margin in the last
    layers, which LoRA modifies.
  - audit/trace_source_20261117 (H3): `self` follows the edited step more than `human` (p = 0.023), and RESULTS.md
    notes an untested idea that self traces change the model less.
  - The pooled mean d of revert_logit_lens_20261118 (7 adapters, including self and human) was seen; the self and
    human values were not looked at separately.
Prediction: `human` loses more margin than `self`.

Data: no forward pass. Per-layer d from revert_logit_lens_20261118/cases.jsonl (runs trace_source_20261117/eval_self
and eval_human, each read by its own adapter) and base_lens_20261119/base_cases.jsonl (base model).
d(layer) = logit(expected digit) - logit(original digit), layers 1-36, at the token before the first differing
answer digit.

Metric (softening): max(d at layers 29-36) - d at layer 36. 0 means the margin is largest at the last layer.

Reading rule (fixed before computing):
  - Primary: questions where both self and human have a usable `follows` case (104). Paired difference
    soft_human - soft_self, two-sided Wilcoxon signed-rank (scipy, zero differences dropped), alpha 0.05.
  - median difference > 0 and p < 0.05: "human softens the last layers more than self" (as predicted).
  - median difference < 0 and p < 0.05: "self softens more" (against the prediction).
  - otherwise: "not distinguishable"; do not read it as "same softening".
Descriptive only: median softening of base, self and human on the questions all three share; mean d by layer for
self and human on the 104 pairs.

    python soften.py   # writes results.json
"""

import json
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon

HERE = Path(__file__).parent
LENS = HERE.parent / "revert_logit_lens_20261118/cases.jsonl"
BASE = HERE.parent / "base_lens_20261119/base_cases.jsonl"
LATE = range(29, 37)


def soften(d):
    return max(d[l - 1] for l in LATE) - d[35]


def follows(rows, run=None):
    return {r["id"]: r for r in rows if "skipped" not in r and r["outcome"] == "follows"
            and (run is None or r.get("run") == run)}


def main():
    lens = [json.loads(line) for line in LENS.read_text().splitlines()]
    s = follows(lens, "trace_source_20261117/eval_self")
    h = follows(lens, "trace_source_20261117/eval_human")
    b = follows([json.loads(line) for line in BASE.read_text().splitlines()])
    pairs = sorted(s.keys() & h.keys())
    diff = [soften(h[i]["d"]) - soften(s[i]["d"]) for i in pairs]
    p = float(wilcoxon(diff, zero_method="wilcox", alternative="two-sided").pvalue)
    med = float(np.median(diff))
    reading = ("human softens the last layers more than self" if med > 0 and p < 0.05 else
               "self softens more" if med < 0 and p < 0.05 else "not distinguishable")
    triple = sorted(s.keys() & h.keys() & b.keys())
    median = lambda rows: round(float(np.median([soften(r["d"]) for r in rows])), 3)
    mean = lambda rows: np.mean([r["d"] for r in rows], axis=0).round(3).tolist()
    result = {"exploratory": True, "pairs": len(pairs), "median_diff": round(med, 3),
              "mean_diff": round(float(np.mean(diff)), 3), "wilcoxon_p": p,
              "human_more_same_less": [sum(x > 0 for x in diff), sum(x == 0 for x in diff), sum(x < 0 for x in diff)],
              "reading": reading,
              "descriptive": {
                  "median_softening_pairs": {"self": median([s[i] for i in pairs]), "human": median([h[i] for i in pairs])},
                  "median_softening_with_base": {"n": len(triple), "base": median([b[i] for i in triple]),
                                                 "self": median([s[i] for i in triple]),
                                                 "human": median([h[i] for i in triple])},
                  "mean_d_pairs": {"self": mean([s[i] for i in pairs]), "human": mean([h[i] for i in pairs])}}}
    text = json.dumps(result, indent=2)
    print(text)
    (HERE / "results.json").write_text(text + "\n")


if __name__ == "__main__":
    main()
