"""Exploratory: does SFT on human traces move the model further from the base model than SFT on self traces?

Written 2026-11-20 before any forward pass (only `check` ran: LoRA scale 0 matched the base model exactly, max
difference 0). Reading rule accepted by the student in chat the same day. Not pre-registered in docs/; exploratory.
Hypothesis taken from audit/trace_source_20261117/RESULTS.md ("Đọc kết quả"): self traces are close to how the base
model already writes, so training on them may change the model less. H3 (self follows the edited step more than
human) replicated at seed 1 (audit/trace_source_seed1_20261119).

Drift: KL(base || adapter) of the next-token distribution, averaged over the trace tokens of a fixed text (the
prompt tokens are not scored). The base distribution comes from the same loaded model with every LoRA scale set to
0, which is the base model exactly (checked in `check`).

Texts (the same for every model; neither is training data; GSM-Plus, 2026-11-14 run):
  A "base-written": the base model's base_prefill traces (gsm_plus_replication_20261114/eval_base).
  B "human-style":  Plain 2000's tuned traces (gsm_plus_replication_20261114/eval_plain), a model trained on
                    converted human solutions with the same conversion as `human`.
  Text A favours `self` and text B favours `human` by construction, which is why both are used.
  Items: the first 100 ids (sorted) where both traces are format-valid and not truncated. Each text is the `tuned`
  prompt followed by that trace.
Adapters: trace_self_200_s0, trace_human_200_s0, trace_self_200_s1, trace_human_200_s1.

Reading rule (fixed before running):
  - Four tests: seed 0 and seed 1, text A and text B. Each: paired over the 100 items, KL_human - KL_self, two-sided
    Wilcoxon signed-rank (scipy), alpha 0.05. No correction: the reading needs all four together.
  - All four have median > 0 and p < 0.05: "human-trace SFT moves the model further from base than self-trace SFT,
    on both text kinds and both seeds".
  - All four have median < 0 and p < 0.05: "self-trace SFT moves it further".
  - Otherwise: "not consistent across seeds and texts"; report each test.
Descriptive only: mean KL per adapter and text; each adapter's follows rate over all its plans next to its mean KL
(4 points, no test).

    python drift.py check   # one text: LoRA scale 0 vs a model loaded without adapter
    python drift.py run     # appends to kl.jsonl (resumes), then results.json
"""

import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
MODEL = (Path.home() / ".cache/huggingface/hub/models--mlx-community--Qwen3-8B-4bit/snapshots/"
         "545dc4251c05440727734bcd94334791f6ab0192")
SRC = ROOT / "audit/gsm_plus_replication_20261114"
ADAPTERS = ["trace_self_200_s0", "trace_human_200_s0", "trace_self_200_s1", "trace_human_200_s1"]
N = 100
OUT = HERE / "kl.jsonl"


def texts():
    sys.path.insert(0, str(ROOT))
    from structured_llm.evaluate import prompt_for

    read = lambda p: {r["id"]: r for r in map(json.loads, p.read_text().splitlines())}
    base, plain = read(SRC / "eval_base/base_prefill.jsonl"), read(SRC / "eval_plain/tuned.jsonl")
    ok = lambda r: r["check"]["format_valid"] and not r["truncated"]
    ids = [i for i in sorted(base) if ok(base[i]) and ok(plain[i])][:N]
    out = []
    for i in ids:
        prompt = prompt_for("tuned", base[i]["question"])
        out += [{"id": i, "text": "A", "prompt": prompt, "trace": base[i]["output"]},
                {"id": i, "text": "B", "prompt": prompt, "trace": plain[i]["output"]}]
    return out


def lora_layers(model):
    from mlx_lm.tuner.lora import LoRALinear
    return [m for _, m in model.named_modules() if isinstance(m, LoRALinear)]


def logprobs(model, ids, start):
    import mlx.core as mx
    logits = model(mx.array([ids]))[0, start - 1:-1].astype(mx.float32)
    return logits - mx.logsumexp(logits, axis=-1, keepdims=True)


def encode(tok, t):
    p = tok.encode(t["prompt"], add_special_tokens=False)
    full = tok.encode(t["prompt"] + t["trace"], add_special_tokens=False)
    assert full[:len(p)] == p, "prompt tokens changed when the trace was appended"
    return full, len(p)


def kl(model, layers, ids, start):
    import mlx.core as mx
    scales = [m.scale for m in layers]
    for m in layers:
        m.scale = 0.0
    lp_base = logprobs(model, ids, start)
    mx.eval(lp_base)
    for m, s in zip(layers, scales):
        m.scale = s
    lp_ad = logprobs(model, ids, start)
    per_token = (mx.exp(lp_base) * (lp_base - lp_ad)).sum(axis=-1)
    mx.eval(per_token)
    return float(per_token.mean()), int(per_token.size)


def check():
    import mlx.core as mx
    from mlx_lm import load
    t = texts()[0]
    plain, tok = load(str(MODEL))
    ids, start = encode(tok, t)
    ref = logprobs(plain, ids, start)
    mx.eval(ref)
    del plain
    model, _ = load(str(MODEL), adapter_path=str(ROOT / "adapters" / ADAPTERS[0]))
    layers = lora_layers(model)
    for m in layers:
        m.scale = 0.0
    off = logprobs(model, ids, start)
    print(f"LoRA layers {len(layers)}; trace tokens {len(ids) - start}; "
          f"max |scale0 - no adapter| = {float(mx.abs(off - ref).max()):.2e}")


def run():
    from mlx_lm import load
    seen = {(r["adapter"], r["id"], r["text"]) for r in map(json.loads, OUT.read_text().splitlines())} if OUT.exists() else set()
    items = texts()
    with OUT.open("a") as handle:
        for a in ADAPTERS:
            if all((a, t["id"], t["text"]) in seen for t in items):
                continue
            model, tok = load(str(MODEL), adapter_path=str(ROOT / "adapters" / a))
            layers = lora_layers(model)
            print(f"loaded {a}: {len(layers)} LoRA layers", flush=True)
            for n, t in enumerate(items):
                if (a, t["id"], t["text"]) in seen:
                    continue
                ids, start = encode(tok, t)
                value, count = kl(model, layers, ids, start)
                handle.write(json.dumps({"adapter": a, "id": t["id"], "text": t["text"], "kl": value, "tokens": count}) + "\n")
                handle.flush()
                if n % 50 == 0:
                    print(a, n, flush=True)
    analyze()


def analyze():
    from scipy.stats import wilcoxon
    rows = [json.loads(line) for line in OUT.read_text().splitlines()]
    k = {(r["adapter"], r["text"], r["id"]): r["kl"] for r in rows}
    tests, means = {}, {}
    for a in ADAPTERS:
        for text in "AB":
            vals = [v for (aa, tt, _), v in k.items() if aa == a and tt == text]
            means[f"{a}/{text}"] = round(float(np.mean(vals)), 4)
    for seed in ("s0", "s1"):
        for text in "AB":
            ids = sorted({i for (a, t, i) in k if t == text and a == f"trace_self_200_{seed}"}
                         & {i for (a, t, i) in k if t == text and a == f"trace_human_200_{seed}"})
            diff = [k[(f"trace_human_200_{seed}", text, i)] - k[(f"trace_self_200_{seed}", text, i)] for i in ids]
            tests[f"{seed}/{text}"] = {"n": len(diff), "median_diff": round(float(np.median(diff)), 4),
                                       "human_higher": sum(d > 0 for d in diff),
                                       "p": float(wilcoxon(diff, alternative="two-sided").pvalue)}
    pos = [t["median_diff"] > 0 and t["p"] < 0.05 for t in tests.values()]
    neg = [t["median_diff"] < 0 and t["p"] < 0.05 for t in tests.values()]
    reading = ("human-trace SFT moves the model further from base than self-trace SFT, on both text kinds and both seeds"
               if all(pos) and len(pos) == 4 else "self-trace SFT moves it further" if all(neg) and len(neg) == 4
               else "not consistent across seeds and texts")
    follows = {}
    for seed, run_dir in (("s0", "trace_source_20261117"), ("s1", "trace_source_seed1_20261119")):
        for src in ("self", "human"):
            rs = [json.loads(l) for l in (ROOT / "audit" / run_dir / f"eval_{src}/tuned_interventions.jsonl").read_text().splitlines()]
            follows[f"trace_{src}_200_{seed}"] = round(sum(r["outcome"] == "follows" for r in rs) / len(rs), 3)
    result = {"exploratory": True, "items": N, "tests": tests, "reading": reading, "mean_kl": means,
              "follows_rate_all_plans": follows}
    text = json.dumps(result, indent=2)
    print(text)
    (HERE / "results.json").write_text(text + "\n")


if __name__ == "__main__":
    {"check": check, "run": run, "analyze": analyze}[sys.argv[1]]()
