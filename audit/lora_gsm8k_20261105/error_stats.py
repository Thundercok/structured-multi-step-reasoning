"""Shape of traces in the training data and in each mode's dev outputs, for error_reading.md.

Run from the repo root: PYTHONPATH=. .venv/bin/python audit/lora_gsm8k_20261105/error_stats.py
"""

import json
import re
import statistics
from pathlib import Path

from structured_llm.trace import calc_is_correct, parse

RUN = Path(__file__).parent
_OP = re.compile(r"(?<=[\d)])\s*[-+*/]")


def trace_of(text):
    return text.split("<|im_start|>assistant\n")[1].removesuffix("<|im_end|>")


def shape(traces):
    steps = [step for trace in traces for step in parse(trace).steps]
    calcs = [calc for step in steps for calc in step.calcs]
    answers = [parse(trace).answer for trace in traces]
    chains = [calc for calc in calcs if len(_OP.findall(calc[0])) >= 2]
    return {
        "traces": len(traces),
        "steps_per_trace": round(len(steps) / len(traces), 2),
        "words_per_step": round(statistics.mean(len(step.text.split()) for step in steps), 1),
        "steps_without_calc": round(sum(not step.calcs for step in steps) / len(steps), 3),
        "vacuous_calc": round(sum(not re.search(r"\d\s*[-+*/]", expr) for expr, _ in calcs) / len(calcs), 3),
        "chain_calc": round(len(chains) / len(calcs), 3),
        "chain_calc_correct": f"{sum(calc_is_correct(*calc) for calc in chains)}/{len(chains)}",
        "non_integer_answer": sum(a is not None and float(a) != int(float(a)) for a in answers),
    }


def main():
    plain = [json.loads(line)["text"] for line in open("data/structured_gsm8k_v1/train.jsonl")]
    seen = set(plain)
    cf_only = [text for text in (json.loads(line)["text"] for line in open("data/structured_gsm8k_cf_v1/train.jsonl"))
               if text not in seen]
    table = {"train plain": shape([trace_of(text) for text in plain]),
             "train cf-only rows": shape([trace_of(text) for text in cf_only])}
    for name, path in [("tuned (plain)", "eval_plain/tuned.jsonl"), ("tuned_cf", "eval_cf/tuned.jsonl"),
                       ("base_prefill", "eval_base/base_prefill.jsonl")]:
        table[name] = shape([json.loads(line)["output"] for line in open(RUN / path)])
    print(json.dumps(table, indent=2))


if __name__ == "__main__":
    main()
