"""Exploratory probe: does the base model's hidden state already hold its final answer before Step 1?

Written 2026-11-18 before any hidden state was extracted. Not pre-registered in docs/; label every result exploratory.

Data: the base model's own base_prefill traces already in audit/ (GSM8K train/dev and GSM-Plus; never the sealed test,
never MATH). One record per distinct question, format_valid, with a whole-number answer. Target: the last digit of
the model's OWN final answer (check.answer), not the gold answer.

The model re-reads each prompt + trace once (teacher forcing, no generation). Hidden states (residual stream after a
layer) are kept at four places:
  k0    the last token before "Step 1:"  (before any step is written)
  k1    the newline ending the first Calc line
  k2    the newline ending the second Calc line (traces with >= 2 Calc lines only)
  last  the newline ending the last Calc line (that line usually contains the answer: a positive control)

Probe: standardized multinomial logistic regression, C picked by inner 3-fold CV from {1e-3, 1e-2, 1e-1}, scored by
outer 5-fold stratified CV (seed 0), so every item gets one out-of-fold prediction.

Baselines, same CV: majority digit (fit on the training folds); question digits (counts of last digits of the numbers
in the question, one-hot last digit of the first and last number, number count).

Reading rule (one test, fixed before extraction):
  layer 24 at k0, probe vs question-digits baseline, per-item correct, exact two-sided McNemar, alpha 0.05.
  - probe right more often and p < 0.05: before writing any step, the hidden state holds information about the last
    digit of the answer beyond what the question's numbers give. It says the information is present, not that the
    model uses it.
  - otherwise: not distinguishable.
Every other layer, position and the shuffled-label control are descriptive.

    python probe.py extract   # MLX forward passes -> features.npz (not committed: large)
    python probe.py fit       # sklearn -> results.json
"""

import json
from pathlib import Path
import re
import sys

import numpy as np

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
SOURCES = [
    "audit/gsm_plus_replication_20261114/eval_base/base_prefill.jsonl",
    "audit/trace_source_20261117/gen/base_prefill.jsonl",
    "audit/gate1_dev100_20261103/base_prefill.jsonl",
    "audit/lora_gsm8k_20261105/eval_base/base_prefill.jsonl",
    "audit/lora_gsm8k_20261105/valid/base/base_prefill.jsonl",
    "audit/structured_smoke_20261102/eval/base_prefill.jsonl",
]
LAYERS = [8, 16, 24, 32, 36]
PRIMARY_LAYER = 24
POSITIONS = ["k0", "k1", "k2", "last"]
MODEL = (Path.home() / ".cache/huggingface/hub/models--mlx-community--Qwen3-8B-4bit/snapshots/"
         "545dc4251c05440727734bcd94334791f6ab0192")
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def records():
    seen, out = set(), []
    for src in SOURCES:
        for line in (ROOT / src).read_text().splitlines():
            r = json.loads(line)
            ans = r["check"].get("answer")
            if r["question"] in seen or not r["check"]["format_valid"] or ans is None:
                continue
            if not re.fullmatch(r"-?\d+", str(ans).replace(",", "")):
                continue
            seen.add(r["question"])
            out.append({"source": src, "id": r["id"], "question": r["question"], "output": r["output"],
                        "digit": int(str(ans).replace(",", "")[-1])})
    return out


def char_positions(prompt, output):
    """Character index (in prompt + output) of the last char before each probe place."""
    text = prompt + output
    step1 = len(prompt) + output.index("Step 1:")
    think_end = output.index("</think>") if "</think>" in output else len(output)
    calc_ends = [len(prompt) + m.end() - 1 for m in re.finditer(r"Calc:[^\n]*\n", output[:think_end + 1])]
    pos = {"k0": step1 - 1}
    if calc_ends:
        pos["k1"], pos["last"] = calc_ends[0], calc_ends[-1]
    if len(calc_ends) >= 2:
        pos["k2"] = calc_ends[1]
    return text, pos


def extract():
    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm.models.base import create_attention_mask
    sys.path.insert(0, str(ROOT))
    from structured_llm.evaluate import prompt_for

    model, tok = load(str(MODEL))
    hf = tok._tokenizer
    items = records()
    feats = {f"L{l}_{p}": np.full((len(items), model.args.hidden_size), np.nan, np.float16)
             for l in LAYERS for p in POSITIONS}
    for n, item in enumerate(items):
        prompt = prompt_for("base_prefill", item["question"])
        output = item["output"] if item["output"].startswith("<think>") else "<think>\n" + item["output"]
        text, pos = char_positions(prompt, output)
        enc = hf(text, return_offsets_mapping=True, add_special_tokens=False)
        offsets = enc["offset_mapping"]
        tok_at = {p: next(i for i, (a, b) in enumerate(offsets) if a <= c < b) for p, c in pos.items()}
        h = model.model.embed_tokens(mx.array([enc["input_ids"]]))
        mask = create_attention_mask(h, None)
        idx = mx.array(sorted(set(tok_at.values())))
        for depth, layer in enumerate(model.model.layers, start=1):
            h = layer(h, mask, None)
            if depth in LAYERS:
                rows = np.array(h[0, idx].astype(mx.float32))
                lookup = dict(zip(sorted(set(tok_at.values())), rows))
                for p, t in tok_at.items():
                    feats[f"L{depth}_{p}"][n] = lookup[t]
            mx.eval(h)
        if n % 50 == 0:
            print(f"{n}/{len(items)}", flush=True)
    meta = [{k: it[k] for k in ("source", "id", "digit")} | {"question": it["question"]} for it in items]
    np.savez_compressed(HERE / "features.npz", **feats)
    (HERE / "items.json").write_text(json.dumps(meta, ensure_ascii=False) + "\n")
    print(json.dumps({"items": len(items)}))


def question_features(q):
    nums = [m.group().replace(",", "") for m in NUM.finditer(q)]
    last = [int(x.split(".")[0][-1]) for x in nums]
    f = np.zeros(31)
    for d in last:
        f[d] += 1
    if last:
        f[10 + last[0]] = 1
        f[20 + last[-1]] = 1
    f[30] = len(nums)
    return f


def mcnemar(b, c):
    from math import comb
    n, k = b + c, min(b, c)
    return 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, j) for j in range(k + 1)) / 2 ** n)


def oof(X, y, folds, model_fn):
    pred = np.empty(len(y), int)
    for train, test in folds:
        m = model_fn()
        m.fit(X[train], y[train])
        pred[test] = m.predict(X[test])
    return pred


def fit():
    from sklearn.dummy import DummyClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GridSearchCV, StratifiedKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    meta = json.loads((HERE / "items.json").read_text())
    feats = np.load(HERE / "features.npz")
    y_all = np.array([m["digit"] for m in meta])
    q_all = np.array([question_features(m["question"]) for m in meta])

    def probe():
        lr = LogisticRegression(max_iter=3000)
        return GridSearchCV(make_pipeline(StandardScaler(), lr), {"logisticregression__C": [1e-3, 1e-2, 1e-1]},
                            cv=3)

    def run(pos, layer, shuffle=False):
        X = feats[f"L{layer}_{pos}"].astype(np.float32)
        keep = ~np.isnan(X).any(axis=1)
        X, y, Q = X[keep], y_all[keep].copy(), q_all[keep]
        if shuffle:
            y = np.random.default_rng(0).permutation(y)
        folds = list(StratifiedKFold(5, shuffle=True, random_state=0).split(X, y))
        p = oof(X, y, folds, probe)
        out = {"n": int(len(y)), "probe_acc": float((p == y).mean())}
        if layer == PRIMARY_LAYER or shuffle:
            base = oof(Q, y, folds, lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000, C=0.1)))
            maj = oof(Q, y, folds, lambda: DummyClassifier(strategy="most_frequent"))
            b, c = int(((p == y) & (base != y)).sum()), int(((base == y) & (p != y)).sum())
            out |= {"question_baseline_acc": float((base == y).mean()), "majority_acc": float((maj == y).mean()),
                    "only_probe": b, "only_baseline": c, "p": mcnemar(b, c)}
        return out

    cells = {f"L{l}_{p}": run(p, l) for p in POSITIONS for l in LAYERS}
    primary = cells[f"L{PRIMARY_LAYER}_k0"]
    if primary["p"] < 0.05 and primary["only_probe"] > primary["only_baseline"]:
        reading = "hidden state before Step 1 holds answer-digit information beyond the question's numbers"
    else:
        reading = "not distinguishable"
    result = {"exploratory": True, "items": len(meta), "digit_counts": np.bincount(y_all, minlength=10).tolist(),
              "primary": {"cell": f"L{PRIMARY_LAYER}_k0", **primary, "reading": reading},
              "shuffled_label_control": run("k0", PRIMARY_LAYER, shuffle=True), "cells": cells}
    text = json.dumps(result, indent=2)
    print(text)
    (HERE / "results.json").write_text(text + "\n")


if __name__ == "__main__":
    {"extract": extract, "fit": fit}[sys.argv[1]]()
