"""Exploratory: does SFT move the layer where the model commits to the answer digit?

Written 2026-11-19 before any forward pass on the base model; reading rule accepted by the student in chat the same day. Not pre-registered in docs/; every result is
exploratory. Motivation (seen before writing this): in audit/revert_logit_lens_20261118 the pooled mean d of the 7
adapters stays near 0 up to about layer 21 and separates sharply at layers 29-30, where LoRA starts (layers 29-36,
1-based). Without the base model we cannot tell whether that is where Qwen3-8B always commits, or where SFT moved it.

Cases: `follows` interventions on the 500 GSM-Plus questions of 2026-11-14, with a known `expected` that differs
from `original` at some digit (same selection and decision point as lens.py).
  base:  base model (no adapter), mode base_prefill, audit/gsm_plus_replication_20261114/eval_base. Computed here.
  plain: Plain 2000 (adapters/gsm8k_enriched_2000_s0), mode tuned, the same run's eval_plain. Its per-layer d is
         reused from revert_logit_lens_20261118/cases.jsonl (same code path, same adapter).
Each model reads its own trace and its own intervention, so a pair shares the question, not the edit.

d(layer) = logit(expected digit) - logit(original digit) by logit lens (final norm, then lm_head), layers 1-36.
Commit layer: the smallest L such that d > 0 at every layer from L to 36 (37 if d <= 0 at layer 36).

Reading rule (fixed before running):
  - Primary: questions where both base and plain have a usable `follows` case. Paired difference
    plain_commit - base_commit, two-sided Wilcoxon signed-rank (scipy, zero differences dropped), alpha 0.05.
  - median difference > 0 and p < 0.05: "SFT moved the commit later" (toward the LoRA layers).
  - median difference < 0 and p < 0.05: "SFT moved the commit earlier".
  - otherwise: "not distinguishable"; do not read it as "SFT did not move it".
  - Fewer than 30 pairs: report descriptively only, no reading.
Descriptive only: mean d by layer for each model, commit-layer histograms, base reverted cases (expected ~6).

    python compare.py run   # appends base cases to base_cases.jsonl (resumes), then results.json
"""

import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / "revert_logit_lens_20261118"))
from lens import MODEL, number, split_digit  # noqa: E402

BASE = ROOT / "audit/gsm_plus_replication_20261114/eval_base"
PLAIN_RUN = "gsm_plus_replication_20261114/eval_plain"
LENS_CASES = HERE.parent / "revert_logit_lens_20261118/cases.jsonl"
OUT = HERE / "base_cases.jsonl"


def base_cases():
    questions = {r["id"]: r["question"] for r in map(json.loads, (BASE / "base_prefill.jsonl").read_text().splitlines())}
    out = []
    for r in map(json.loads, (BASE / "base_prefill_interventions.jsonl").read_text().splitlines()):
        if r["outcome"] not in ("reverted", "follows") or r["expected"] is None:
            continue
        e, o = number(r["expected"]), number(r["original"])
        i = split_digit(e, o)
        if i is not None:
            out.append({"id": r["id"], "outcome": r["outcome"], "question": questions[r["id"]],
                        "text": r["prefix"] + r["continuation"], "index": i,
                        "written": o if r["outcome"] == "reverted" else e, "exp_digit": e[i], "orig_digit": o[i]})
    return out


def forward():
    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm.models.base import create_attention_mask
    sys.path.insert(0, str(ROOT))
    from structured_llm.evaluate import prompt_for

    seen = {r["id"] for r in map(json.loads, OUT.read_text().splitlines())} if OUT.exists() else set()
    model, tok = load(str(MODEL))
    hf = tok._tokenizer
    digit_id = {str(d): hf.convert_tokens_to_ids(str(d)) for d in range(10)}
    with OUT.open("a") as handle:
        def emit(record):
            handle.write(json.dumps(record) + "\n")
            handle.flush()

        for n, c in enumerate(base_cases()):
            if c["id"] in seen:
                continue
            prompt = prompt_for("base_prefill", c["question"])
            text = prompt + c["text"]
            at = text.rfind("Answer:")
            if at < len(prompt):
                emit({"id": c["id"], "skipped": "no_answer_line"})
                continue
            start = next((i for i in range(at + 7, len(text)) if text[i].isdigit() or text[i] == "-"), None)
            if start is None or not text.startswith(c["written"], start):
                emit({"id": c["id"], "skipped": "answer_text_mismatch"})
                continue
            dig = start + c["index"]
            enc = hf(text, return_offsets_mapping=True, add_special_tokens=False)
            ids, offs = enc["input_ids"], enc["offset_mapping"]
            t = next((i for i, (a, b) in enumerate(offs) if a <= dig < b), None)
            if t is None or offs[t] != (dig, dig + 1) or ids[t] != digit_id[text[dig]]:
                emit({"id": c["id"], "skipped": "answer_digit_mismatch"})
                continue
            h = model.model.embed_tokens(mx.array([ids[:t]]))
            mask = create_attention_mask(h, None)
            d = []
            for layer in model.model.layers:
                h = layer(h, mask, None)
                logits = model.lm_head(model.model.norm(h[:, -1:]))[0, 0]
                d.append(float(logits[digit_id[c["exp_digit"]]] - logits[digit_id[c["orig_digit"]]]))
                mx.eval(h)
            emit({k: c[k] for k in ("id", "outcome", "index", "exp_digit", "orig_digit")} | {"d": d})
            if n % 25 == 0:
                print(n, flush=True)


def commit_layer(d):
    layer = len(d) + 1
    for i in range(len(d) - 1, -1, -1):
        if d[i] <= 0:
            break
        layer = i + 1
    return layer


def analyze():
    from scipy.stats import wilcoxon

    base = [r for r in map(json.loads, OUT.read_text().splitlines()) if "skipped" not in r]
    plain = [r for r in map(json.loads, LENS_CASES.read_text().splitlines())
             if r.get("run") == PLAIN_RUN and "skipped" not in r]
    bf = {r["id"]: r for r in base if r["outcome"] == "follows"}
    pf = {r["id"]: r for r in plain if r["outcome"] == "follows"}
    pairs = sorted(bf.keys() & pf.keys())
    diff = [commit_layer(pf[i]["d"]) - commit_layer(bf[i]["d"]) for i in pairs]
    result = {"exploratory": True, "pairs": len(pairs),
              "base_follows": len(bf), "plain_follows": len(pf),
              "skipped_base": sum(1 for r in map(json.loads, OUT.read_text().splitlines()) if "skipped" in r)}
    if len(pairs) >= 30 and any(diff):
        p = float(wilcoxon(diff, zero_method="wilcox", alternative="two-sided").pvalue)
        med = float(np.median(diff))
        reading = ("SFT moved the commit later" if med > 0 and p < 0.05 else
                   "SFT moved the commit earlier" if med < 0 and p < 0.05 else "not distinguishable")
        result |= {"median_diff": med, "mean_diff": round(float(np.mean(diff)), 3), "wilcoxon_p": p,
                   "later_same_earlier": [sum(x > 0 for x in diff), sum(x == 0 for x in diff), sum(x < 0 for x in diff)],
                   "reading": reading}
    else:
        result["reading"] = "fewer than 30 pairs: descriptive only"
    hist = lambda rs: {str(k): v for k, v in sorted(
        {L: sum(commit_layer(r["d"]) == L for r in rs) for L in {commit_layer(r["d"]) for r in rs}}.items())}
    mean = lambda rs: np.mean([r["d"] for r in rs], axis=0).round(3).tolist() if rs else []
    result["descriptive"] = {
        "commit_hist_paired": {"base": hist([bf[i] for i in pairs]), "plain": hist([pf[i] for i in pairs])},
        "mean_d_follows": {"base": mean(list(bf.values())), "plain": mean(list(pf.values()))},
        "base_reverted": {"n": sum(r["outcome"] == "reverted" for r in base),
                          "mean_d": mean([r for r in base if r["outcome"] == "reverted"])},
        "final_layer_sanity_base": {"follows_d_last_positive": sum(r["d"][-1] > 0 for r in bf.values()),
                                    "reverted_d_last_negative": sum(r["d"][-1] < 0 for r in base
                                                                    if r["outcome"] == "reverted")}}
    text = json.dumps(result, indent=2)
    print(text)
    (HERE / "results.json").write_text(text + "\n")


if __name__ == "__main__":
    if sys.argv[1:] == ["run"]:
        forward()
    analyze()
