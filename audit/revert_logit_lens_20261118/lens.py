"""Exploratory, step 1 of "bug or gap" for reverted interventions: did Plain consider the followed answer inside?

Written 2026-11-18 before any forward pass. Not pre-registered in docs/; every result is exploratory.

Models: the 7 fine-tuned adapters already scored on GSM-Plus (Plain 2000, CF 2000, Plain checkpoints 50/200/1000,
trace self/human 200), pooled because Plain 2000 alone has only 11 usable reverted cases (chosen 2026-11-18 before
any forward pass). Each case is re-read by the adapter that wrote it (adapter from the run's manifest.json).
Cases: each run's own GSM-Plus interventions (RUNS below), outcome
`reverted` or `follows`, with a known `expected` answer that differs from `original` at some digit position
(neither number is a prefix of the other).

Teacher forcing: prompt (`tuned`) + intervention prefix + the model's own continuation. Decision point: the token
just before the first digit at which the expected and original answers differ (the model writes the answer digit
by digit, so this token predicts that digit; the digits before it are shared). At each of the 36 layers, logit lens
(final norm, then the output head) gives d = logit(expected's digit there) - logit(original's digit there).

  reverted_lead: share of reverted cases where d > 0 at some layer 16-32 (the followed answer led at some middle
                 layer, though the model then wrote the original).
  follows_lead:  share of follows cases where d < 0 at some layer 16-32 (the mirror: how often the losing answer
                 leads somewhere in the middle anyway).

Reading rule (fixed before running):
  - reverted_lead > follows_lead and two-sided Fisher exact p < 0.05: "bug-like": in reverted cases the followed
    answer was represented and then overridden. Worth step 2 (find what overrides it).
  - otherwise: no evidence of a bug at this decision point; stop here.
Limitation known before running: by the answer token, the model may already have rewritten the old value in its
continuation, so this looks at the last decision, not the first.

    python lens.py run   # writes cases.jsonl (per-layer d) and results.json
"""

import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
MODEL = (Path.home() / ".cache/huggingface/hub/models--mlx-community--Qwen3-8B-4bit/snapshots/"
         "545dc4251c05440727734bcd94334791f6ab0192")
RUNS = [ROOT / "audit" / d for d in (
    "gsm_plus_replication_20261114/eval_plain", "gsm_plus_h1_holdout_20261115/eval_plain",
    "gsm_plus_replication_20261114/eval_cf", "gsm_plus_h1_holdout_20261115/eval_cf",
    "sft_dose_response_20261116/eval_50", "sft_dose_response_20261116/eval_200", "sft_dose_response_20261116/eval_1000",
    "trace_source_20261117/eval_self", "trace_source_20261117/eval_human")]
MIDDLE = range(16, 33)


def number(x):
    return str(int(x)) if float(x).is_integer() else repr(float(x))


def split_digit(e, o):
    """Index of the first differing character if both are digits there, else None."""
    i = next((i for i, (a, b) in enumerate(zip(e, o)) if a != b), None)
    return i if i is not None and e[i].isdigit() and o[i].isdigit() else None


def cases():
    out = []
    for run in RUNS:
        questions = {r["id"]: r["question"] for r in map(json.loads, (run / "tuned.jsonl").read_text().splitlines())}
        adapter = json.loads((run / "manifest.json").read_text())["adapter"]
        for r in map(json.loads, (run / "tuned_interventions.jsonl").read_text().splitlines()):
            if r["outcome"] not in ("reverted", "follows") or r["expected"] is None:
                continue
            e, o = number(r["expected"]), number(r["original"])
            i = split_digit(e, o)
            if i is None:
                continue
            out.append({"run": f"{run.parent.name}/{run.name}", "adapter": adapter, "id": r["id"], "outcome": r["outcome"], "question": questions[r["id"]],
                        "text": r["prefix"] + r["continuation"], "index": i, "written": o if r["outcome"] == "reverted"
                        else e, "exp_digit": e[i], "orig_digit": o[i]})
    return out


def fisher(a, b, c, d):
    from math import comb
    n, r1, c1 = a + b + c + d, a + b, a + c
    p = lambda x: comb(r1, x) * comb(n - r1, c1 - x) / comb(n, c1)
    obs = p(a)
    return min(1.0, sum(p(x) for x in range(max(0, c1 - (n - r1)), min(r1, c1) + 1) if p(x) <= obs * (1 + 1e-9)))


def run():
    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm.models.base import create_attention_mask
    sys.path.insert(0, str(ROOT))
    from structured_llm.evaluate import prompt_for

    done, skipped, loaded = [], {}, None
    for n, c in enumerate(cases()):
        if c["adapter"] != loaded:
            model, tok = load(str(MODEL), adapter_path=str(ROOT / c["adapter"]))
            hf, loaded = tok._tokenizer, c["adapter"]
            digit_id = {str(d): hf.convert_tokens_to_ids(str(d)) for d in range(10)}
            print(f"loaded {loaded}", flush=True)
        prompt = prompt_for("tuned", c["question"])
        text = prompt + c["text"]
        at = text.rfind("Answer:")
        if at < len(prompt):
            skipped["no_answer_line"] = skipped.get("no_answer_line", 0) + 1
            continue
        start = next((i for i in range(at + 7, len(text)) if text[i].isdigit() or text[i] == "-"), None)
        if start is None or not text.startswith(c["written"], start):
            skipped["answer_text_mismatch"] = skipped.get("answer_text_mismatch", 0) + 1
            continue
        dig = start + c["index"]
        enc = hf(text, return_offsets_mapping=True, add_special_tokens=False)
        ids, offs = enc["input_ids"], enc["offset_mapping"]
        t = next((i for i, (a, b) in enumerate(offs) if a <= dig < b), None) if dig is not None else None
        if t is None or offs[t] != (dig, dig + 1) or ids[t] != digit_id[text[dig]]:
            skipped["answer_digit_mismatch"] = skipped.get("answer_digit_mismatch", 0) + 1
            continue
        pos = t - 1
        h = model.model.embed_tokens(mx.array([ids[:t]]))
        mask = create_attention_mask(h, None)
        d = []
        for layer in model.model.layers:
            h = layer(h, mask, None)
            logits = model.lm_head(model.model.norm(h[:, -1:]))[0, 0]
            d.append(float(logits[digit_id[c["exp_digit"]]] - logits[digit_id[c["orig_digit"]]]))
            mx.eval(h)
        assert pos == len(ids[:t]) - 1
        done.append({k: c[k] for k in ("run", "adapter", "id", "outcome", "index", "exp_digit", "orig_digit")} | {"d": d})
        if n % 50 == 0:
            print(f"{n}", flush=True)
    (HERE / "cases.jsonl").write_text("".join(json.dumps(r) + "\n" for r in done))

    rev = [r for r in done if r["outcome"] == "reverted"]
    fol = [r for r in done if r["outcome"] == "follows"]
    rl = sum(any(r["d"][l - 1] > 0 for l in MIDDLE) for r in rev)
    fl = sum(any(r["d"][l - 1] < 0 for l in MIDDLE) for r in fol)
    p = fisher(rl, len(rev) - rl, fl, len(fol) - fl)
    reading = ("bug-like: followed answer represented then overridden" if rl / len(rev) > fl / len(fol) and p < 0.05
               else "no evidence of a bug at this decision point")
    mean = lambda rs: np.mean([r["d"] for r in rs], axis=0).round(3).tolist()
    result = {"exploratory": True, "cases": {"reverted": len(rev), "follows": len(fol)}, "skipped": skipped,
              "reverted_lead": [rl, len(rev)], "follows_lead": [fl, len(fol)], "fisher_p": p, "reading": reading,
              "final_layer_sanity": {"reverted_d_last_negative": sum(r["d"][-1] < 0 for r in rev),
                                     "follows_d_last_positive": sum(r["d"][-1] > 0 for r in fol)},
              "mean_d_by_layer": {"reverted": mean(rev), "follows": mean(fol)},
              "by_adapter": {a: {"reverted_lead": [sum(any(r["d"][l - 1] > 0 for l in MIDDLE) for r in rev
                                                       if r["adapter"] == a), sum(r["adapter"] == a for r in rev)],
                                 "follows_lead": [sum(any(r["d"][l - 1] < 0 for l in MIDDLE) for r in fol
                                                      if r["adapter"] == a), sum(r["adapter"] == a for r in fol)]}
                             for a in sorted({r["adapter"] for r in done})}}
    text = json.dumps(result, indent=2)
    print(text)
    (HERE / "results.json").write_text(text + "\n")


if __name__ == "__main__":
    run()
