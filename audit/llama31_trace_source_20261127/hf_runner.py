"""PyTorch / HuggingFace + PEFT runner for H5 (Llama-3.1-8B-Instruct trace-source & derailment).

Implements docs/llama31_trace_source_prereg.md using the exact pure-Python parsing,
intervention planning, classification, and continuation-decomposition functions of `structured_llm`.

Subcommands:
  prep-pool --out BUNDLE_DIR          (Local CPU) Export Calc-clean GSM8K candidate pool + eval_500.jsonl
  gen-self  --bundle DIR --run DIR    (Kaggle GPU) Run base_prefill until K >= 200 strict pairs & check
  train     --run DIR --seed S --src {self,human}
  eval      --run DIR --tag TAG [--adapter DIR] --mode {base_prefill,tuned}
  analyze   --run DIR                 Compute pre-registered H5 & H5b tests -> results.json + RESULTS.md
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import platform
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from structured_llm.counterfactual import plan_intervention
from structured_llm.evaluate import INSTRUCTION, PREFILLS, summarize as summarize_eval
from structured_llm.intervene import classify, tally
from structured_llm.trace import _numbers, calc_is_correct, check, parse

DEFAULT_MODEL = "meta-llama/Llama-3.1-8B-Instruct"
TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
NUM_LORA_LAYERS = 8
LORA_RANK = 8
LORA_ALPHA = 160  # scale = alpha / r = 20.0, matching mlx_lm
MAX_SEQ_LEN = 512
ITERS = 200
LR = 5e-5
BATCH_SIZE_EVAL = 8
ALPHA = 0.05

EXPECTED_SOURCE_SHA = "17f347dc51477c50d4efb83959dbb7c56297aba886e5544ee2aaed3024813465"
EXPECTED_HOLDOUT_SHA = "d079e99a5b9cef8d887f28ac39ac20b0a1b14cdee5b003a451d67087651f6e7a"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    path.write_text(text)
    return sha256_bytes(text.encode())


def is_strict_trace_clean(trace_text: str, question: str, gold: str | None = None) -> tuple[bool, str | None]:
    """Verify strict H5 invariants: valid grammar, all Calcs right, every Step has >=1 Calc,
    and answer_from_last_calc == True (eliminating the 8/229 and 28/229 H3/H4 confound)."""
    sc = check(trace_text, question, gold)
    if not sc["format_valid"] or sc["errors"]:
        return False, "bad_format"
    if gold is not None and not sc["correct"]:
        return False, "wrong_answer"
    if sc["calc_accuracy"] != 1.0:
        return False, "wrong_calc"
    if not sc["answer_from_last_calc"]:
        return False, "answer_not_from_last_calc"
    tr = parse(trace_text)
    if not tr.steps or any(len(st.calcs) == 0 for st in tr.steps):
        return False, "step_without_calc"
    return True, None


def keep_strict_record(record: dict, tokenizer=None) -> str | None:
    """Return None if base_prefill record passes strict H5 filter, else rejection reason."""
    if record.get("truncated"):
        return "truncated"
    ok, reason = is_strict_trace_clean(record["output"], record["question"], record["gold"])
    if not ok:
        return reason
    if tokenizer is not None:
        chat_str = format_training_chat(tokenizer, record["question"], record["output"].strip())
        if len(tokenizer.encode(chat_str, add_special_tokens=False)) > MAX_SEQ_LEN:
            return "self_over_512_tokens"
    return None


def format_user_prompt(tokenizer, mode: str, question: str) -> str:
    content = (INSTRUCTION + question) if mode == "base_prefill" else question
    return tokenizer.apply_chat_template(
        [{"role": "user", "content": content}],
        tokenize=False,
        add_generation_prompt=True,
    )


def format_training_chat(tokenizer, question: str, trace_text: str) -> str:
    return tokenizer.apply_chat_template(
        [
            {"role": "user", "content": question},
            {"role": "assistant", "content": trace_text.strip()},
        ],
        tokenize=False,
        add_generation_prompt=False,
    )


def strip_stop_tokens(text: str, tokenizer) -> str:
    for tok in ("<|eot_id|>", "<|end_of_text|>", tokenizer.eos_token):
        if tok and tok in text:
            text = text.split(tok, 1)[0]
    return text


def classify_b1_continuation(iv: dict) -> dict:
    """Pre-registered H5b continuation classifier (identical to decompose_continuations.py)."""
    if iv.get("expected") is None:
        raise ValueError("B1 record must have expected != None")
    outc = iv["outcome"]
    new_val = float(iv["new"])
    exp_val = float(iv["expected"])

    calcs = []
    for line in iv.get("continuation", "").splitlines():
        if line.startswith("Calc: ") and "=" in line:
            e, st = line[6:].split("=", 1)
            calcs.append((e.strip(), st.strip()))

    expr_nums, stated_nums = set(), set()
    bad_arith = False
    for e, st in calcs:
        expr_nums |= _numbers(e)
        stated_nums |= _numbers(st)
        if not calc_is_correct(e, st):
            bad_arith = True

    used_new = any(abs(x - new_val) < 1e-6 for x in expr_nums)
    hit_exp = any(abs(x - exp_val) < 1e-2 for x in stated_nums)

    if outc == "follows":
        return {"bucket": "follows_exact", "submode": "follows_exact", "used_new": True}
    if outc in ("follows_rounded", "follows_approximate"):
        return {"bucket": "follows_round_approx", "submode": outc, "used_new": True}
    if outc == "reverted":
        sub = "reverted_after_using_new" if used_new else "reverted_pure_bypass"
        return {"bucket": "bypass_or_revert", "submode": sub, "used_new": used_new}
    if not used_new:
        return {"bucket": "bypass_or_revert", "submode": "other_pure_bypass", "used_new": False}
    if hit_exp:
        sub = "hit_expected_overstepped"
    elif bad_arith:
        sub = "bad_arith"
    elif outc == "no_answer":
        sub = "truncated_no_answer"
    else:
        sub = "wrong_downstream_step"
    return {"bucket": "derailed_after_using_new", "submode": sub, "used_new": True}


# ---------------------------------------------------------------------------
# Phase 0 (Local CPU): Export SHA-pinned candidate pool + 500 holdout items
# ---------------------------------------------------------------------------
def cmd_prep_pool(out_dir: Path, max_candidates: int = 2000) -> dict:
    from structured_llm import gsm8k

    train_rows, valid_rows, _ = gsm8k.load_splits()
    candidates = []
    dropped = Counter()
    for row in train_rows:
        human_trace, reason = gsm8k.convert(row, enrich_step1=True)
        if human_trace is None:
            dropped[reason] += 1
            continue
        gold = gsm8k.gold_answer(row["answer"])
        ok, s_reason = is_strict_trace_clean(human_trace, row["question"], gold)
        if not ok:
            dropped[f"human_{s_reason}"] += 1
            continue
        candidates.append({
            "id": gsm8k.rank_key(row["question"])[:16],
            "question": row["question"],
            "answer": gold,
            "human_trace": human_trace,
        })
        if len(candidates) == max_candidates:
            break

    valid_clean = []
    for row in valid_rows:
        ht, _ = gsm8k.convert(row, enrich_step1=True)
        if ht is None:
            continue
        gold = gsm8k.gold_answer(row["answer"])
        ok, _ = is_strict_trace_clean(ht, row["question"], gold)
        if ok:
            valid_clean.append({
                "id": gsm8k.rank_key(row["question"])[:16],
                "question": row["question"],
                "answer": gold,
                "trace": ht,
            })

    holdout_path = ROOT / "data" / "gsm_plus_v1" / "holdout_819.jsonl"
    if sha256_file(holdout_path) != EXPECTED_HOLDOUT_SHA:
        raise SystemExit("holdout_819.jsonl SHA-256 mismatch")
    eval_500 = read_jsonl(holdout_path)[:500]

    out_dir.mkdir(parents=True, exist_ok=True)
    cand_sha = write_jsonl(out_dir / "candidates_strict.jsonl", candidates)
    val_sha = write_jsonl(out_dir / "valid_strict.jsonl", valid_clean)
    eval_sha = write_jsonl(out_dir / "eval_500.jsonl", eval_500)
    manifest = {
        "gsm8k_source_sha256": EXPECTED_SOURCE_SHA,
        "holdout_819_sha256": EXPECTED_HOLDOUT_SHA,
        "candidates_count": len(candidates),
        "candidates_sha256": cand_sha,
        "valid_count": len(valid_clean),
        "valid_sha256": val_sha,
        "eval_500_count": len(eval_500),
        "eval_500_sha256": eval_sha,
        "human_dropped": dict(dropped),
    }
    (out_dir / "bundle_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


# ---------------------------------------------------------------------------
# PyTorch / HF helpers (lazy-imported only on GPU commands)
# ---------------------------------------------------------------------------
def _load_hf(model_id: str, adapter_dir: Path | None = None):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(model_id)
    tok.padding_side = "left"
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch.float16,
        device_map="auto",
    )
    if adapter_dir is not None:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, str(adapter_dir))
    model.eval()
    return model, tok


def _batched_greedy(model, tok, prompts: list[str], max_new_tokens: int) -> list[tuple[str, int]]:
    import torch

    stop_ids = [tok.eos_token_id]
    eot = tok.convert_tokens_to_ids("<|eot_id|>")
    if isinstance(eot, int) and eot != tok.unk_token_id and eot not in stop_ids:
        stop_ids.append(eot)

    first_dev = next(model.parameters()).device
    enc = tok(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to(first_dev)
    in_len = enc["input_ids"].shape[1]
    with torch.no_grad():
        out = model.generate(
            **enc,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            temperature=None,
            top_p=None,
            eos_token_id=stop_ids,
            pad_token_id=tok.pad_token_id,
        )
    results = []
    for seq in out:
        gen_ids = seq[in_len:]
        # Trim trailing pad tokens if any
        raw = tok.decode(gen_ids, skip_special_tokens=False)
        clean = strip_stop_tokens(raw, tok)
        n_tok = len(tok.encode(clean, add_special_tokens=False))
        results.append((clean, n_tok))
    return results


def cmd_gen_self(bundle_dir: Path, run_dir: Path, model_id: str = DEFAULT_MODEL) -> dict:
    bman = json.loads((bundle_dir / "bundle_manifest.json").read_text())
    cand_path = bundle_dir / "candidates_strict.jsonl"
    if sha256_file(cand_path) != bman["candidates_sha256"]:
        raise SystemExit("candidates_strict.jsonl SHA-256 mismatch")
    all_cands = read_jsonl(cand_path)

    model, tok = _load_hf(model_id, adapter_dir=None)
    gen_dir = run_dir / "gen"
    gen_dir.mkdir(parents=True, exist_ok=True)
    gen_file = gen_dir / "base_prefill.jsonl"

    # Filter candidates whose human chat also fits <= 512 Llama tokens
    usable_cands = [
        c for c in all_cands
        if len(tok.encode(format_training_chat(tok, c["question"], c["human_trace"]), add_special_tokens=False)) <= MAX_SEQ_LEN
    ]

    n_target = 400
    while True:
        subset = usable_cands[:n_target]
        existing = {r["id"]: r for r in read_jsonl(gen_file)}
        todo = [c for c in subset if c["id"] not in existing]
        with gen_file.open("a") as fh:
            for i in range(0, len(todo), BATCH_SIZE_EVAL):
                batch = todo[i : i + BATCH_SIZE_EVAL]
                prefill = PREFILLS["base_prefill"]
                prompts = [format_user_prompt(tok, "base_prefill", c["question"]) + prefill for c in batch]
                t0 = time.perf_counter()
                gens = _batched_greedy(model, tok, prompts, max_new_tokens=1024)
                dt = round((time.perf_counter() - t0) / len(batch), 2)
                for c, (gtxt, n_tok) in zip(batch, gens):
                    full_txt = prefill + gtxt
                    rec = {
                        "id": c["id"], "question": c["question"], "gold": c["answer"],
                        "output": full_txt, "tokens": n_tok, "truncated": n_tok >= 1024,
                        "tool_calls": 0, "answer_format": "number", "seconds": dt,
                        "check": check(full_txt, c["question"], c["answer"]),
                    }
                    existing[c["id"]] = rec
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()

        # Check how many pass keep_strict_record
        reasons = Counter()
        self_rows, human_rows = [], []
        for c in subset:
            rec = existing[c["id"]]
            r_drop = keep_strict_record(rec, tokenizer=tok)
            if r_drop:
                reasons[r_drop] += 1
                continue
            self_rows.append({
                "id": c["id"], "question": c["question"], "trace": rec["output"].strip(),
                "text": format_training_chat(tok, c["question"], rec["output"].strip()),
            })
            human_rows.append({
                "id": c["id"], "question": c["question"], "trace": c["human_trace"].strip(),
                "text": format_training_chat(tok, c["question"], c["human_trace"].strip()),
            })

        if len(self_rows) >= ITERS:
            break
        if n_target >= len(usable_cands) or n_target >= 2000:
            raise SystemExit(f"kept={len(self_rows)} < {ITERS} at N={n_target}; stopping per prereg")
        n_target = min(n_target + 200, len(usable_cands), 2000)

    data_dir = run_dir / "data"
    s_sha = write_jsonl(data_dir / "self" / "train.jsonl", self_rows)
    h_sha = write_jsonl(data_dir / "human" / "train.jsonl", human_rows)

    # Pre-training invariant check
    problems = []
    if [r["id"] for r in self_rows] != [r["id"] for r in human_rows]:
        problems.append("id order mismatch")
    stats_out = {}
    for name, rows_list in (("self", self_rows), ("human", human_rows)):
        lens = [len(tok.encode(r["text"], add_special_tokens=False)) for r in rows_list]
        bad_strict = sum(not is_strict_trace_clean(r["trace"], r["question"])[0] for r in rows_list)
        over = sum(L > MAX_SEQ_LEN for L in lens)
        if bad_strict:
            problems.append(f"{name}: {bad_strict} rows failed strict check")
        if over:
            problems.append(f"{name}: {over} rows > {MAX_SEQ_LEN} tokens")
        stats_out[name] = {
            "rows": len(rows_list),
            "bad_strict": bad_strict,
            "over_512": over,
            "tokens_mean": round(sum(lens) / len(lens), 1),
            "tokens_max": max(lens),
        }

    check_doc = {
        "model": model_id,
        "n_scanned": len(subset),
        "kept": len(self_rows),
        "dropped": dict(reasons),
        "self_train_sha256": s_sha,
        "human_train_sha256": h_sha,
        "stats": stats_out,
        "problems": problems,
    }
    (run_dir / "check.json").write_text(json.dumps(check_doc, indent=2) + "\n")
    if problems:
        raise SystemExit(f"Pre-training check failed: {problems}")
    return check_doc


def cmd_train(run_dir: Path, seed: int, src: str, model_id: str = DEFAULT_MODEL) -> Path:
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    dst = run_dir / "adapters" / f"trace_{src}_{ITERS}_s{seed}"
    if (dst / "adapter_model.safetensors").exists():
        print(f"Skip {dst}: already exists")
        return dst

    check_doc = json.loads((run_dir / "check.json").read_text())
    if check_doc["problems"]:
        raise SystemExit("Refusing to train: check.json has problems")

    rows = read_jsonl(run_dir / "data" / src / "train.jsonl")
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

    tok = AutoTokenizer.from_pretrained(model_id)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token

    base = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.float16, device_map="auto")
    n_layers = base.config.num_hidden_layers
    layers = list(range(n_layers - NUM_LORA_LAYERS, n_layers))
    cfg = LoraConfig(
        r=LORA_RANK,
        lora_alpha=LORA_ALPHA,
        lora_dropout=0.0,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=TARGET_MODULES,
        layers_to_transform=layers,
    )
    model = get_peft_model(base, cfg)
    model.train()

    # Exact MLX-matching optimizer: Adam, constant lr=5e-5, batch_size=1, 200 steps, full-sequence CE
    opt = torch.optim.Adam((p for p in model.parameters() if p.requires_grad), lr=LR)
    order = list(range(len(rows)))
    rng = random.Random(seed)
    rng.shuffle(order)

    first_dev = next(model.parameters()).device
    losses = []
    for step_idx in range(ITERS):
        row = rows[order[step_idx % len(order)]]
        ids = tok.encode(row["text"], add_special_tokens=False)[:MAX_SEQ_LEN]
        inp = torch.tensor([ids], dtype=torch.long, device=first_dev)
        opt.zero_grad(set_to_none=True)
        out = model(input_ids=inp, labels=inp)
        loss = out.loss
        loss.backward()
        opt.step()
        losses.append(float(loss.detach().cpu()))
        if (step_idx + 1) % 25 == 0:
            print(f"[{src} s{seed}] step {step_idx+1}/{ITERS} mean_loss={sum(losses[-25:])/25:.4f}", flush=True)

    dst.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(dst))
    (dst / "train_Meta.json").write_text(json.dumps({
        "model": model_id, "seed": seed, "src": src, "iters": ITERS,
        "lr": LR, "lora_r": LORA_RANK, "lora_alpha": LORA_ALPHA,
        "layers_transformed": layers, "final_25_loss": round(sum(losses[-25:]) / 25, 5),
    }, indent=2) + "\n")
    return dst


def cmd_eval_and_intervene(
    bundle_dir: Path, run_dir: Path, tag: str, mode: str,
    adapter_dir: Path | None = None, model_id: str = DEFAULT_MODEL,
) -> None:
    bman = json.loads((bundle_dir / "bundle_manifest.json").read_text())
    eval_path = bundle_dir / "eval_500.jsonl"
    if sha256_file(eval_path) != bman["eval_500_sha256"]:
        raise SystemExit("eval_500.jsonl SHA-256 mismatch")
    items = read_jsonl(eval_path)

    out_dir = run_dir / f"eval_{tag}"
    out_dir.mkdir(parents=True, exist_ok=True)
    model, tok = _load_hf(model_id, adapter_dir=adapter_dir)

    # 1. Clean evaluation
    clean_file = out_dir / f"{mode}.jsonl"
    done_ids = {r["id"] for r in read_jsonl(clean_file)}
    todo = [it for it in items if it["id"] not in done_ids]
    prefill = PREFILLS.get(mode, "")
    with clean_file.open("a") as fh:
        for i in range(0, len(todo), BATCH_SIZE_EVAL):
            batch = todo[i : i + BATCH_SIZE_EVAL]
            prompts = [format_user_prompt(tok, mode, it["question"]) + prefill for it in batch]
            t0 = time.perf_counter()
            gens = _batched_greedy(model, tok, prompts, max_new_tokens=1024)
            dt = round((time.perf_counter() - t0) / len(batch), 2)
            for it, (gtxt, n_tok) in zip(batch, gens):
                full_txt = prefill + gtxt
                rec = {
                    "id": it["id"], "question": it["question"], "gold": it["answer"],
                    "output": full_txt, "tokens": n_tok, "truncated": n_tok >= 1024,
                    "tool_calls": 0, "answer_format": "number", "seconds": dt,
                    "check": check(full_txt, it["question"], it["answer"]),
                }
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()

    clean_records = read_jsonl(clean_file)
    (out_dir / "summary.json").write_text(json.dumps({
        mode: summarize_eval(clean_records),
        "machine": platform.platform(),
    }, indent=2) + "\n")

    # 2. Deterministic interventions
    iv_file = out_dir / f"{mode}_interventions.jsonl"
    done_iv = {r["id"] for r in read_jsonl(iv_file)}
    planned_todo = []
    for src_rec in clean_records:
        plan, _ = plan_intervention(src_rec["output"], src_rec["question"], src_rec["id"])
        if plan is not None and src_rec["id"] not in done_iv:
            planned_todo.append((src_rec, plan))

    with iv_file.open("a") as fh:
        for i in range(0, len(planned_todo), BATCH_SIZE_EVAL):
            batch = planned_todo[i : i + BATCH_SIZE_EVAL]
            prompts = [format_user_prompt(tok, mode, s["question"]) + p["prefix"] for s, p in batch]
            gens = _batched_greedy(model, tok, prompts, max_new_tokens=512)
            for (s, p), (gtxt, n_tok) in zip(batch, gens):
                continued = p["prefix"] + gtxt
                rec = {
                    "id": s["id"], **p, "continuation": gtxt,
                    "outcome": classify(continued, p),
                    "tokens": n_tok,
                    "originally_correct": bool(s["check"]["correct"]),
                }
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()


# ---------------------------------------------------------------------------
# Phase 4 (CPU): Pre-registered H5 & H5b statistical analysis
# ---------------------------------------------------------------------------
def mcnemar_paired(x_map: dict, y_map: dict, ids: list[str], pred) -> dict:
    from scipy import stats

    n = len(ids)
    if n == 0:
        return {"n": 0, "x": 0, "y": 0, "only_x": 0, "only_y": 0, "p": 1.0, "diff": 0.0, "ci95": [0.0, 0.0]}
    xs = [bool(pred(x_map[i])) for i in ids]
    ys = [bool(pred(y_map[i])) for i in ids]
    only_x = sum(a and not b for a, b in zip(xs, ys))
    only_y = sum(b and not a for a, b in zip(xs, ys))
    disc = only_x + only_y
    p = float(stats.binomtest(min(only_x, only_y), disc, 0.5).pvalue) if disc > 0 else 1.0
    diff = (only_x - only_y) / n
    se = math.sqrt(max(disc - (only_x - only_y) ** 2 / n, 0.0)) / n
    return {
        "n": n, "x": sum(xs), "y": sum(ys),
        "only_x": only_x, "only_y": only_y,
        "p": p, "diff": round(diff, 6),
        "ci95": [round(diff - 1.96 * se, 6), round(diff + 1.96 * se, 6)],
    }


def wilson_ci(k: int, n: int) -> list[float]:
    if n == 0:
        return [0.0, 0.0]
    z = 1.959963984540054
    phat = k / n
    denom = 1.0 + z * z / n
    center = (phat + z * z / (2.0 * n)) / denom
    half = z * math.sqrt((phat * (1.0 - phat) + z * z / (4.0 * n)) / n) / denom
    return [round(center - half, 6), round(center + half, 6)]


def holm_reading_two_seeds(s0: dict, s1: dict, favor_positive: bool = True) -> str:
    """Apply pre-registered Holm-Bonferroni reading rule across two seeds (alpha = 0.05)."""
    pairs = [("s0", s0), ("s1", s1)]
    pairs.sort(key=lambda kv: kv[1]["p"])
    _, first = pairs[0]
    _, second = pairs[1]

    def right_dir(d):
        return (d["only_x"] > d["only_y"]) if favor_positive else (d["only_x"] < d["only_y"])

    if first["p"] >= ALPHA / 2.0:
        return "not_distinguishable"
    if not right_dir(first):
        return "opposite_direction"
    if second["p"] < ALPHA and right_dir(second):
        return "replicated_both_seeds"
    if second["p"] < ALPHA and not right_dir(second):
        return "inconsistent_across_seeds"
    return "supported_one_seed_holm"


def analyze_h5_run(run_dir: Path) -> dict:
    specs = {
        "self_s0": ("eval_self_s0", "tuned"),
        "human_s0": ("eval_human_s0", "tuned"),
        "self_s1": ("eval_self_s1", "tuned"),
        "human_s1": ("eval_human_s1", "tuned"),
    }
    if (run_dir / "eval_base" / "base_prefill.jsonl").exists():
        specs["base_prefill"] = ("eval_base", "base_prefill")

    loaded = {}
    for key, (sub, mode) in specs.items():
        ev = {r["id"]: r for r in read_jsonl(run_dir / sub / f"{mode}.jsonl")}
        iv = {r["id"]: r for r in read_jsonl(run_dir / sub / f"{mode}_interventions.jsonl")}
        loaded[key] = (ev, iv)

    qids = sorted(loaded["self_s0"][0])
    if any(sorted(ev) != qids for ev, _ in loaded.values()):
        raise ValueError("Mismatched evaluation question sets across cells")

    primary_b1, secondary_all, sens_orig_corr = {}, {}, {}
    h5b_derail, h5b_bypass = {}, {}

    for s in (0, 1):
        iv_s = loaded[f"self_s{s}"][1]
        iv_h = loaded[f"human_s{s}"][1]
        shared_all = sorted(set(iv_s) & set(iv_h))
        shared_b1 = [i for i in shared_all if iv_s[i]["expected"] is not None and iv_h[i]["expected"] is not None]
        shared_corr = [i for i in shared_b1 if iv_s[i]["originally_correct"] and iv_h[i]["originally_correct"]]

        primary_b1[f"seed{s}"] = mcnemar_paired(iv_s, iv_h, shared_b1, lambda r: r["outcome"] == "follows")
        secondary_all[f"seed{s}"] = mcnemar_paired(iv_s, iv_h, shared_all, lambda r: r["outcome"] == "follows")
        sens_orig_corr[f"seed{s}"] = mcnemar_paired(iv_s, iv_h, shared_corr, lambda r: r["outcome"] == "follows")

        # H5b: human vs self on derailment & bypass
        h5b_derail[f"seed{s}"] = mcnemar_paired(
            iv_h, iv_s, shared_b1,
            lambda r: classify_b1_continuation(r)["bucket"] == "derailed_after_using_new",
        )
        h5b_bypass[f"seed{s}"] = mcnemar_paired(
            iv_h, iv_s, shared_b1,
            lambda r: classify_b1_continuation(r)["bucket"] == "bypass_or_revert",
        )

    descriptive = {}
    for key, (ev, iv) in loaded.items():
        b1_recs = [r for r in iv.values() if r["expected"] is not None]
        buckets = Counter(classify_b1_continuation(r)["bucket"] for r in b1_recs)
        acc = sum(bool(ev[i]["check"]["correct"]) for i in qids)
        descriptive[key] = {
            "n_questions": len(qids),
            "format_valid": sum(bool(ev[i]["check"]["format_valid"]) for i in qids),
            "accuracy": acc,
            "accuracy_wilson95": wilson_ci(acc, len(qids)),
            "truncated": sum(bool(ev[i]["truncated"]) for i in qids),
            "planned": len(iv),
            "flagged_expected_none": len(iv) - len(b1_recs),
            "n_b1": len(b1_recs),
            "follows": sum(r["outcome"] == "follows" for r in iv.values()),
            "follows_rate_B1": round(buckets["follows_exact"] / len(b1_recs), 6) if b1_recs else None,
            "follows_rate_all": round(sum(r["outcome"] == "follows" for r in iv.values()) / len(iv), 6) if iv else None,
            "b1_bypass_or_revert": buckets["bypass_or_revert"],
            "b1_derailed_after_using_new": buckets["derailed_after_using_new"],
            "taxonomy": dict(tally(list(iv.values()))),
        }

    h5_reading = holm_reading_two_seeds(primary_b1["seed0"], primary_b1["seed1"], favor_positive=True)
    derail_reading = holm_reading_two_seeds(h5b_derail["seed0"], h5b_derail["seed1"], favor_positive=True)
    derail_dominates = all(
        h5b_derail[f"seed{s}"]["diff"] > h5b_bypass[f"seed{s}"]["diff"] for s in (0, 1)
    )

    out = {
        "prereg": "docs/llama31_trace_source_prereg.md",
        "questions": len(qids),
        "H5_primary_B1": primary_b1,
        "H5_reading": h5_reading,
        "H5b_mechanism_B1": {
            "human_vs_self_derailed": h5b_derail,
            "human_vs_self_bypass": h5b_bypass,
            "derail_holm_reading": derail_reading,
            "derail_diff_exceeds_bypass_both_seeds": derail_dominates,
        },
        "secondary_all_planned": secondary_all,
        "sensitivity_originally_correct_B1": sens_orig_corr,
        "training_check": json.loads((run_dir / "check.json").read_text()) if (run_dir / "check.json").exists() else None,
        "descriptive": descriptive,
    }
    (run_dir / "results.json").write_text(json.dumps(out, indent=2) + "\n")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    p_prep = sub.add_parser("prep-pool")
    p_prep.add_argument("--out", type=Path, required=True)

    p_gen = sub.add_parser("gen-self")
    p_gen.add_argument("--bundle", type=Path, required=True)
    p_gen.add_argument("--run", type=Path, required=True)
    p_gen.add_argument("--model", default=DEFAULT_MODEL)

    p_tr = sub.add_parser("train")
    p_tr.add_argument("--run", type=Path, required=True)
    p_tr.add_argument("--seed", type=int, choices=[0, 1], required=True)
    p_tr.add_argument("--src", choices=["self", "human"], required=True)
    p_tr.add_argument("--model", default=DEFAULT_MODEL)

    p_ev = sub.add_parser("eval")
    p_ev.add_argument("--bundle", type=Path, required=True)
    p_ev.add_argument("--run", type=Path, required=True)
    p_ev.add_argument("--tag", required=True)
    p_ev.add_argument("--mode", choices=["base_prefill", "tuned"], required=True)
    p_ev.add_argument("--adapter", type=Path, default=None)
    p_ev.add_argument("--model", default=DEFAULT_MODEL)

    p_an = sub.add_parser("analyze")
    p_an.add_argument("--run", type=Path, required=True)

    args = p.parse_args()
    if args.cmd == "prep-pool":
        print(json.dumps(cmd_prep_pool(args.out), indent=2))
    elif args.cmd == "gen-self":
        print(json.dumps(cmd_gen_self(args.bundle, args.run, args.model), indent=2))
    elif args.cmd == "train":
        print(cmd_train(args.run, args.seed, args.src, args.model))
    elif args.cmd == "eval":
        cmd_eval_and_intervene(args.bundle, args.run, args.tag, args.mode, args.adapter, args.model)
    elif args.cmd == "analyze":
        print(json.dumps(analyze_h5_run(args.run), indent=2))


if __name__ == "__main__":
    main()
