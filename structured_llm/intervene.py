"""Test whether the answer depends on the thinking, by changing the thinking.

Run: python -m structured_llm.intervene --run audit/run --modes tuned base_instructed --adapter adapters/smoke

Reads the outputs saved by evaluate, changes one intermediate Calc result in each eligible
trace, lets the model continue from there, and sorts what it answers:

follows   the answer the changed result leads to: the thinking drives the answer
reverted  the original answer: the model ignored the change or repaired it
other     neither
moved     a different answer, on a flagged trace whose expected answer is unknown

Flagged traces (a wrong Calc, or an answer not from the last Calc) stay in, so `rq1` can
compare how often answers are wrong across dependence on the thinking and checker flags.

Report every eligible trace first, plus the eligibility rate, since filtering to correct
answers changes the population measured (arXiv:2610.37070). Correct-only counts are secondary.
Comparisons between modes should use `shared`, the questions eligible in every mode.
"""

import argparse
import collections
import json
from pathlib import Path

from .counterfactual import plan_intervention
from .evaluate import ADAPTER_MODES, generate_text, model_path, prompt_for, read_jsonl
from .trace import loose_answer

_TOLERANCE = 0.01
_MOVED = ("follows", "other", "moved")


def classify(continued, plan):
    answer = loose_answer(continued)
    if answer is None:
        return "no_answer"
    if plan["expected"] is not None and abs(answer - plan["expected"]) <= _TOLERANCE:
        return "follows"
    if abs(answer - plan["original"]) <= _TOLERANCE:
        return "reverted"
    return "other" if plan["expected"] is not None else "moved"


def tally(records):
    counts = collections.Counter(record["outcome"] for record in records)
    outcomes = ("follows", "reverted", "other", "moved", "no_answer")
    return {"n": len(records), **{key: counts[key] for key in outcomes}}


def rq1_table(records):
    """Wrong answers by whether the answer moved and whether a checker would flag the trace."""
    table = collections.defaultdict(lambda: {"n": 0, "wrong": 0})
    for record in records:
        if record["outcome"] == "no_answer":
            continue
        moved = "moved" if record["outcome"] in _MOVED else "unmoved"
        flagged = "flagged" if record.get("flags") else "clean"
        cell = table[f"{moved}|{flagged}"]
        cell["n"] += 1
        cell["wrong"] += not record["originally_correct"]
    return dict(sorted(table.items()))


def summarize(by_mode, skipped):
    shared = set.intersection(*[{record["id"] for record in records} for records in by_mode.values()])
    return {
        mode: {
            "eligible": tally(records),
            "eligibility_rate": round(len(records) / max(len(records) + sum(skipped[mode].values()), 1), 3),
            "skipped": dict(skipped[mode]),
            "rq1": rq1_table(records),
            "correct_only": tally([record for record in records if record["originally_correct"]]),
            "shared": tally([record for record in records if record["id"] in shared]),
            "shared_correct_only": tally([
                record for record in records if record["id"] in shared and record["originally_correct"]]),
        }
        for mode, records in by_mode.items()
    }


def run(run_dir, modes, adapter, max_tokens):
    from mlx_lm import load
    from mlx_lm.sample_utils import make_sampler

    run_dir = Path(run_dir)
    sampler = make_sampler(temp=0.0)
    path, loaded, by_mode = model_path(), None, {}
    skipped = {mode: collections.Counter() for mode in modes}
    for mode in modes:
        wanted = adapter if mode in ADAPTER_MODES else None
        if mode in ADAPTER_MODES and not adapter:
            raise SystemExit("tuned modes need --adapter")
        if loaded is None or loaded[0] != wanted:
            loaded = (wanted, *load(path, adapter_path=str(wanted) if wanted else None))
        _, model, tokenizer = loaded

        file = run_dir / f"{mode}_interventions.jsonl"
        records = read_jsonl(file)
        done = {record["id"] for record in records}
        with file.open("a") as handle:
            for source in read_jsonl(run_dir / f"{mode}.jsonl"):
                plan, reason = plan_intervention(source["output"], source["question"], source["id"])
                if plan is None:
                    skipped[mode][reason] += 1
                    continue
                if source["id"] in done:
                    continue
                generated, _ = generate_text(mode, model, tokenizer, prompt_for(mode, source["question"]) + plan["prefix"],
                                             max_tokens, sampler)
                continued = plan["prefix"] + generated
                record = {
                    "id": source["id"], **plan, "continuation": generated, "outcome": classify(continued, plan),
                    "tokens": len(tokenizer.encode(generated)),
                    "originally_correct": bool(source["check"]["correct"]),
                }
                records.append(record)
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()
        by_mode[mode] = records
    summary = summarize(by_mode, skipped)
    (run_dir / "interventions_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--modes", nargs="+", default=["tuned", "base_instructed"])
    parser.add_argument("--adapter")
    parser.add_argument("--max-tokens", type=int, default=512)
    args = parser.parse_args()
    run(args.run, args.modes, args.adapter, args.max_tokens)
