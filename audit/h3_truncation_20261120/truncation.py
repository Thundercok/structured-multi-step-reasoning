"""Exploratory: does H3 survive when continuations that ran to the token cap are removed?

Written 2026-11-20 before computing H3 on any subset. Not pre-registered in docs/; every result is exploratory. The
student chose this check in chat ("1") on the agent's proposal.

Why: in the seed 1 clean run, `human` was truncated at 1,024 tokens 51 times against 9 for `self` (seed 0: 27 and
14). If the pairs where `human` does not follow are mostly continuations that ramble to the cap, H3 measures
"the human-trace adapter degenerates on long outputs", not "it ignores the edited step". Seen before writing: those
clean-run truncation counts and the outcome mixes in results.json; not the truncation of intervention continuations,
nor any cross-tab of truncation with outcome.

Data: audit/trace_source_20261117 (seed 0) and audit/trace_source_seed1_20261119 (seed 1), eval_{self,human}/
tuned_interventions.jsonl. No model run. Intervention continuations were generated with max_tokens 512; `tokens` is
the re-encoded length of the continuation. Capped: tokens >= 500 (a margin for re-encoding differences, fixed here).

Reading rule (fixed before computing):
  - Per seed, separately: questions where both adapters have a plan and neither continuation is capped. `follows`
    exact, exact two-sided McNemar, alpha 0.05 per seed (two tests, one per seed, not pooled).
  - Both seeds: self follows more and p < 0.05: "H3 holds without capped continuations".
  - Neither seed reaches p < 0.05: "not distinguishable without capped continuations". Read with the pair counts:
    dropping pairs costs power, so this alone does not show that truncation carries H3.
  - Otherwise (one seed only, or opposite directions): "mixed".
Descriptive only: capped counts per adapter and seed; in H3's discordant pairs (all pairs), how many of the
non-following side's continuations are capped; outcome mix of capped continuations.

    python truncation.py   # writes results.json
"""

from collections import Counter
import json
from math import comb
from pathlib import Path

HERE = Path(__file__).parent
SEEDS = {"seed0": HERE.parent / "trace_source_20261117", "seed1": HERE.parent / "trace_source_seed1_20261119"}
CAP = 500


def mcnemar(b, c):
    n = b + c
    return min(1.0, 2 * sum(comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n) if n else 1.0


def capped(r):
    return r["tokens"] >= CAP


def fol(r):
    return r["outcome"] == "follows"


def seed_result(run):
    load = lambda a: {r["id"]: r for r in map(json.loads, (run / f"eval_{a}/tuned_interventions.jsonl").read_text().splitlines())}
    s, h = load("self"), load("human")
    pairs = sorted(s.keys() & h.keys())
    clean = [i for i in pairs if not capped(s[i]) and not capped(h[i])]
    only_s = sum(fol(s[i]) and not fol(h[i]) for i in clean)
    only_h = sum(fol(h[i]) and not fol(s[i]) for i in clean)
    s_only_all = [i for i in pairs if fol(s[i]) and not fol(h[i])]
    h_only_all = [i for i in pairs if fol(h[i]) and not fol(s[i])]
    return {"pairs_all": len(pairs), "pairs_uncapped": len(clean),
            "follows_uncapped": {"self": sum(fol(s[i]) for i in clean), "human": sum(fol(h[i]) for i in clean)},
            "discordant_uncapped": {"self_only": only_s, "human_only": only_h}, "p": mcnemar(only_s, only_h),
            "direction": "self" if only_s > only_h else "human" if only_h > only_s else "tie",
            "descriptive": {
                "capped_in_pairs": {"self": sum(capped(s[i]) for i in pairs), "human": sum(capped(h[i]) for i in pairs)},
                "capped_all_plans": {"self": sum(map(capped, s.values())), "human": sum(map(capped, h.values()))},
                "discordant_all_self_only": {"n": len(s_only_all), "human_capped": sum(capped(h[i]) for i in s_only_all)},
                "discordant_all_human_only": {"n": len(h_only_all), "self_capped": sum(capped(s[i]) for i in h_only_all)},
                "capped_outcomes": {"self": dict(Counter(r["outcome"] for r in s.values() if capped(r))),
                                    "human": dict(Counter(r["outcome"] for r in h.values() if capped(r)))}}}


def main():
    per = {k: seed_result(v) for k, v in SEEDS.items()}
    sig = [r["p"] < 0.05 for r in per.values()]
    dirs = [r["direction"] for r in per.values()]
    if all(sig) and all(d == "self" for d in dirs):
        reading = "H3 holds without capped continuations"
    elif not any(sig):
        reading = "not distinguishable without capped continuations"
    else:
        reading = "mixed"
    result = {"exploratory": True, "cap_tokens": CAP, "per_seed": per, "reading": reading}
    text = json.dumps(result, indent=2)
    print(text)
    (HERE / "results.json").write_text(text + "\n")


if __name__ == "__main__":
    main()
