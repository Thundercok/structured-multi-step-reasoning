"""Exploratory: after the edited Calc, does the model write that same calculation again (re-check it)?

Written 2026-11-19 before counting anything in the continuations. Not pre-registered in docs/; every result is
exploratory. The student delegated the choice of next step in chat ("pick best option"); the agent chose this one
and fixed the rule below before counting.

Why: H3 (audit/trace_source_20261117) found `self` follows the edited step more than `human` (p = 0.023). The
logit-lens runs (revert_logit_lens_20261118, base_lens_20261119, final_layer_soften_20261119) looked only at the
answer digit and found nothing that separates the two. One untested reading of H3: `human` does not ignore the edit,
it re-computes it. Seen before writing: only the prefixes (every edit is the last `Calc:` line of the prefix, in
Step 1), not the continuations.

Data: trace_source_20261117/eval_self and eval_human, tuned_interventions.jsonl. No model run.
Re-check: the continuation contains a `Calc:` line whose expression (left of `=`, spaces removed) equals the
edited Calc's expression.

Reading rule (fixed before counting):
  - Primary: questions where both adapters have an intervention plan (the 140 of H3). Per adapter, re-check yes/no.
    Exact two-sided McNemar on the discordant pairs, alpha 0.05.
  - human re-checks more and p < 0.05: "human re-computes the edited step more than self".
  - self re-checks more and p < 0.05: "self re-computes the edited step more than human".
  - otherwise: "not distinguishable".
Descriptive only: what value a re-check gives (the original true value, the edited value, other); the outcome mix
with and without a re-check per adapter; re-check counts in H3's discordant pairs (self follows / human does not,
and the reverse).

    python recheck.py   # writes results.json
"""

from collections import Counter
import json
from math import comb
from pathlib import Path
import re

HERE = Path(__file__).parent
SRC = HERE.parent / "trace_source_20261117"
CALC = re.compile(r"^Calc:\s*(.+?)=\s*([-\d.,]+)", re.M)


def norm(expr):
    return re.sub(r"\s+", "", expr)


def value(text):
    try:
        return float(text.replace(",", "").rstrip("."))
    except ValueError:
        return None


def recheck(r):
    edited = CALC.findall(r["prefix"])[-1][0]
    hits = [value(v) for e, v in CALC.findall(r["continuation"]) if norm(e) == norm(edited)]
    if not hits:
        return None
    v = hits[0]
    return "old" if v == r["old"] else "new" if v == r["new"] else "other"


def mcnemar(b, c):
    n = b + c
    return min(1.0, 2 * sum(comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n) if n else 1.0


def main():
    load = lambda run: {r["id"]: r for r in map(json.loads, (SRC / run / "tuned_interventions.jsonl").read_text().splitlines())}
    s, h = load("eval_self"), load("eval_human")
    pairs = sorted(s.keys() & h.keys())
    rs = {i: recheck(s[i]) is not None for i in pairs}
    rh = {i: recheck(h[i]) is not None for i in pairs}
    only_h = sum(rh[i] and not rs[i] for i in pairs)
    only_s = sum(rs[i] and not rh[i] for i in pairs)
    p = mcnemar(only_h, only_s)
    reading = ("human re-computes the edited step more than self" if only_h > only_s and p < 0.05 else
               "self re-computes the edited step more than human" if only_s > only_h and p < 0.05 else
               "not distinguishable")

    def describe(rows):
        kinds = Counter(recheck(r) or "none" for r in rows)
        mix = {k: dict(Counter(r["outcome"] for r in rows if (recheck(r) or "none") == k)) for k in kinds}
        return {"recheck_value": dict(kinds), "outcome_by_recheck": mix}

    fol = lambda r: r["outcome"] == "follows"
    s_only = [i for i in pairs if fol(s[i]) and not fol(h[i])]
    h_only = [i for i in pairs if fol(h[i]) and not fol(s[i])]
    result = {"exploratory": True, "pairs": len(pairs),
              "recheck": {"self": sum(rs.values()), "human": sum(rh.values())},
              "discordant": {"human_only": only_h, "self_only": only_s}, "mcnemar_p": p, "reading": reading,
              "descriptive": {
                  "self_pairs": describe([s[i] for i in pairs]), "human_pairs": describe([h[i] for i in pairs]),
                  "self_all": describe(list(s.values())), "human_all": describe(list(h.values())),
                  "h3_self_follows_human_not": {"n": len(s_only), "human_recheck": sum(rh[i] for i in s_only),
                                                "self_recheck": sum(rs[i] for i in s_only)},
                  "h3_human_follows_self_not": {"n": len(h_only), "human_recheck": sum(rh[i] for i in h_only),
                                                "self_recheck": sum(rs[i] for i in h_only)}}}
    text = json.dumps(result, indent=2)
    print(text)
    (HERE / "results.json").write_text(text + "\n")


if __name__ == "__main__":
    main()
