"""Exploratory: is the answer readable earlier inside the human-trace adapter than inside the self-trace adapter?

Written 2026-11-18, after audit/trace_source_20261117 (H3: self follows edited steps more than human, p = 0.023)
and audit/probe_early_answer_20261118 (base model: not distinguishable at layer 24 before Step 1), before any
adapter hidden state was extracted. Not pre-registered in docs/; every result is exploratory.

Idea: if human-trace training makes the model settle its answer before writing steps, a probe should read the
answer earlier inside adapters/trace_human_200_s0 than inside adapters/trace_self_200_s0.

Same inputs for both adapters: the 644 base-model traces in audit/probe_early_answer_20261118/items.json, with the
prompt the adapters were trained on (`tuned`: the question alone, no instruction) followed by the same trace.
Target: the last digit of that trace's answer. Only the weights differ.

LoRA changes layers 29-36 only (adapter keys layers.28-35), so layers 1-28 are identical across adapters. Layers
kept: 28 (identity check: must match between adapters), 32, 36. Positions and probe as in probe.py.

Reading rule (one test, fixed before extraction):
  layer 32 at k0, human vs self probe, per-item correct (same out-of-fold folds), exact two-sided McNemar, alpha 0.05.
  - human right more often and p < 0.05: the answer digit is more readable before Step 1 inside the human-trace
    adapter. Consistent with, not proof of, "settles early, so ignores edited steps".
  - self right more often and p < 0.05: more readable inside the self-trace adapter (opposite of that idea).
  - otherwise: not distinguishable.
Other layers and positions are descriptive.

    python probe_adapters.py extract self|human
    python probe_adapters.py fit
"""

import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
BASE_RUN = ROOT / "audit/probe_early_answer_20261118"
sys.path.insert(0, str(BASE_RUN))
import probe  # noqa: E402

ADAPTERS = {"self": ROOT / "adapters/trace_self_200_s0", "human": ROOT / "adapters/trace_human_200_s0"}
LAYERS = [28, 32, 36]
PRIMARY_LAYER = 32


def items():
    meta = json.loads((BASE_RUN / "items.json").read_text())
    outputs = {}
    for src in probe.SOURCES:
        for line in (ROOT / src).read_text().splitlines():
            r = json.loads(line)
            outputs[(src, r["id"])] = r["output"]
    return [m | {"output": outputs[(m["source"], m["id"])]} for m in meta]


def extract(name):
    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm.models.base import create_attention_mask
    sys.path.insert(0, str(ROOT))
    from structured_llm.evaluate import prompt_for

    model, tok = load(str(probe.MODEL), adapter_path=str(ADAPTERS[name]))
    hf = tok._tokenizer
    its = items()
    feats = {f"L{l}_{p}": np.full((len(its), model.args.hidden_size), np.nan, np.float16)
             for l in LAYERS for p in probe.POSITIONS}
    for n, item in enumerate(its):
        output = item["output"] if item["output"].startswith("<think>") else "<think>\n" + item["output"]
        text, pos = probe.char_positions(prompt_for("tuned", item["question"]), output)
        enc = hf(text, return_offsets_mapping=True, add_special_tokens=False)
        tok_at = {p: next(i for i, (a, b) in enumerate(enc["offset_mapping"]) if a <= c < b) for p, c in pos.items()}
        order = sorted(set(tok_at.values()))
        h = model.model.embed_tokens(mx.array([enc["input_ids"]]))
        mask = create_attention_mask(h, None)
        for depth, layer in enumerate(model.model.layers, start=1):
            h = layer(h, mask, None)
            if depth in LAYERS:
                lookup = dict(zip(order, np.array(h[0, mx.array(order)].astype(mx.float32))))
                for p, t in tok_at.items():
                    feats[f"L{depth}_{p}"][n] = lookup[t]
            mx.eval(h)
        if n % 50 == 0:
            print(f"{name} {n}/{len(its)}", flush=True)
    np.savez_compressed(HERE / f"features_{name}.npz", **feats)


def fit():
    from sklearn.model_selection import StratifiedKFold

    meta = json.loads((BASE_RUN / "items.json").read_text())
    y_all = np.array([m["digit"] for m in meta])
    feats = {k: np.load(HERE / f"features_{k}.npz") for k in ADAPTERS}

    def model_fn():
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import GridSearchCV
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        return GridSearchCV(make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000)),
                            {"logisticregression__C": [1e-3, 1e-2, 1e-1]}, cv=3)

    cells, preds = {}, {}
    for p in probe.POSITIONS:
        for l in LAYERS:
            key = f"L{l}_{p}"
            Xs = {k: f[key].astype(np.float32) for k, f in feats.items()}
            keep = ~np.isnan(Xs["self"]).any(axis=1) & ~np.isnan(Xs["human"]).any(axis=1)
            y = y_all[keep]
            folds = list(StratifiedKFold(5, shuffle=True, random_state=0).split(y, y))
            right = {k: probe.oof(X[keep], y, folds, model_fn) == y for k, X in Xs.items()}
            b, c = int((right["human"] & ~right["self"]).sum()), int((right["self"] & ~right["human"]).sum())
            cells[key] = {"n": int(keep.sum()), "human_acc": float(right["human"].mean()),
                          "self_acc": float(right["self"].mean()), "only_human": b, "only_self": c,
                          "p": probe.mcnemar(b, c),
                          "max_abs_diff_features": float(np.nanmax(np.abs(Xs["self"] - Xs["human"])))}
    prim = cells[f"L{PRIMARY_LAYER}_k0"]
    if prim["p"] >= 0.05:
        reading = "not distinguishable"
    elif prim["only_human"] > prim["only_self"]:
        reading = "answer digit more readable before Step 1 inside the human-trace adapter"
    else:
        reading = "answer digit more readable before Step 1 inside the self-trace adapter"
    result = {"exploratory": True, "items": len(meta), "majority_acc_all": float(np.mean(y_all == 0)),
              "primary": {"cell": f"L{PRIMARY_LAYER}_k0", **prim, "reading": reading}, "cells": cells}
    text = json.dumps(result, indent=2)
    print(text)
    (HERE / "results.json").write_text(text + "\n")


if __name__ == "__main__":
    extract(sys.argv[2]) if sys.argv[1] == "extract" else fit()
