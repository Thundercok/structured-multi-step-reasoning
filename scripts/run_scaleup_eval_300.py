"""Comprehensive Scale-up Evaluation (N=300 & Exhaustive Step-Depth Sweep)

Runs an extensive evaluation comparing Enriched CF vs. Enriched Plain SFT:
1. 300 disjoint held-out questions (Dev-100 + Valid-100 + Held-out Tail 100).
2. Clean performance & Paired McNemar test on Clean Accuracy.
3. Standard intermediate interventions.
4. Exhaustive Step-Depth Sweep across all intermediate steps k on common correct items.
5. Emits full statistical analysis and Markdown report to audit/scaleup_eval_300_20261109/REPORT.md.
"""

from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import sys
import time

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("MLX_MAX_OPS_PER_BUFFER", "10")
os.environ.setdefault("MLX_MAX_MB_PER_BUFFER", "512")

from scipy import stats

# Ensure structured_llm is importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from structured_llm import gsm8k
from structured_llm.counterfactual import (
    _DECISION,
    _also_written_as_word,
    _collides,
    _operands,
    flat_calcs,
    fmt,
    reexecute,
    safe_float,
    substitute,
    values,
)
from structured_llm.evaluate import (
    MODEL_ID,
    MODEL_REVISION,
    generate_text,
    model_path,
    prompt_for,
    read_jsonl,
    score,
)
from structured_llm.intervene import classify
from structured_llm.trace import calc_is_correct, loose_answer, parse

OUT_DIR = ROOT / "audit/scaleup_eval_300_20261109"
DATA_DIR = OUT_DIR / "data"
EVAL_CF_DIR = OUT_DIR / "eval_cf"
EVAL_PLAIN_DIR = OUT_DIR / "eval_plain"

CF_ADAPTER = ROOT / "adapters/gsm8k_cf_enriched_2000_s0"
PLAIN_ADAPTER = ROOT / "adapters/gsm8k_enriched_2000_s0"


def prepare_300_dataset():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_file = DATA_DIR / "dev_300.jsonl"
    if out_file.is_file():
        items = read_jsonl(out_file)
        if len(items) == 300:
            print(f"[Dataset] Using existing {out_file} (N=300)")
            return out_file

    print("[Dataset] Building 300 disjoint held-out questions...")
    dev_src = ROOT / "data/structured_gsm8k_enriched_v1/dev.jsonl"
    dev_items = [dict(json.loads(l), split="dev") for l in dev_src.read_text().splitlines() if l.strip()]

    valid_src = ROOT / "data/structured_gsm8k_v1/valid_eval.jsonl"
    valid_items = [dict(json.loads(l), split="valid") for l in valid_src.read_text().splitlines() if l.strip()]

    # Tail 101 items from untouched pool
    train_pool, valid_pool, dev_pool = gsm8k.load_splits()
    tail_items = []
    for row in train_pool[-101:]:
        tail_items.append({
            "id": gsm8k.rank_key(row["question"])[:16],
            "question": row["question"],
            "answer": gsm8k.gold_answer(row["answer"]),
            "split": "heldout_tail",
        })

    combined = (dev_items + valid_items + tail_items)[:300]
    with out_file.open("w") as f:
        for c in combined:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"[Dataset] Saved {len(combined)} questions to {out_file}")
    return out_file


def seed_existing_dev100(out_dir, src_eval_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    out_tuned = out_dir / "tuned.jsonl"
    src_tuned = ROOT / src_eval_dir / "tuned.jsonl"
    if not out_tuned.exists() and src_tuned.is_file():
        out_tuned.write_text(src_tuned.read_text())
        print(f"[Seed] Copied {src_tuned} -> {out_tuned} (100 items)")

    out_int = out_dir / "tuned_interventions.jsonl"
    src_int = ROOT / src_eval_dir / "tuned_interventions.jsonl"
    if not out_int.exists() and src_int.is_file():
        out_int.write_text(src_int.read_text())
        print(f"[Seed] Copied {src_int} -> {out_int} (interventions)")


def plan_all_interventions_for_trace(output, question, key):
    """Plan interventions at every eligible intermediate Calc step k."""
    trace = parse(output)
    if trace.errors:
        return []
    calcs = flat_calcs(trace.steps)
    if len(calcs) < 2:
        return []
    correct = [calc_is_correct(*calc) for calc in calcs]
    try:
        original = safe_float(trace.answer)
    except Exception:
        return []
    flags = []
    if not all(correct):
        flags.append("wrong_calc")
    try:
        last_calc = safe_float(calcs[-1][1])
        if abs(original - last_calc) > 1e-6:
            flags.append("answer_not_last_calc")
    except Exception:
        flags.append("answer_not_last_calc")

    usable = correct.index(False) if not all(correct) else len(calcs) - 1
    in_question = set(values(question))
    try:
        results = [safe_float(stated) for _, stated in calcs]
    except Exception:
        return []

    plans = []
    for target in range(usable):
        value = results[target]
        later = {number for expr, _ in calcs[target + 1:] for number in values(expr)}
        if not (value.is_integer() and value in later and value not in in_question and results.count(value) == 1):
            continue
        old = results[target]
        digest = int(hashlib.sha256(f"{key}_k{target+1}".encode()).hexdigest(), 16)
        used = in_question | set(results) | set(_operands(calcs))
        new = old + digest % 9 + 1
        while new in used:
            new += 1
        if old in _operands(calcs[:target + 1]) or _also_written_as_word(question, old):
            continue
        expected = None
        if not flags:
            if _DECISION.search(question):
                continue
            steps = reexecute(trace.steps, {old: new}, skip=target + 1)
            if steps is None or _collides(calcs, flat_calcs(steps), question):
                continue
            expected = safe_float(flat_calcs(steps)[-1][1])
            if abs(expected - original) < 1e-6:
                continue

        lines, seen = ["<think>"], 0
        for number, step in enumerate(trace.steps, 1):
            if seen + len(step.calcs) <= target:
                lines.append(f"Step {number}: {step.text}")
                lines.extend(f"Calc: {expr}={stated}" for expr, stated in step.calcs)
                seen += len(step.calcs)
                continue
            lines.append(f"Step {number}: {substitute(step.text, {old: new})}")
            lines.extend(f"Calc: {expr}={stated}" for expr, stated in step.calcs[:target - seen])
            lines.append(f"Calc: {step.calcs[target - seen][0]}={fmt(new)}")
            break
        plans.append({
            "id": f"{key}_k{target+1}",
            "parent_id": key,
            "k": target + 1,
            "K": len(trace.steps),
            "prefix": "\n".join(lines) + "\n",
            "old": old,
            "new": new,
            "expected": expected,
            "original": original,
            "flags": flags,
        })
    return plans


def run_clean_evaluation(adapter_path, out_dir, dataset_file, max_tokens=1024):
    out_dir.mkdir(parents=True, exist_ok=True)
    items = read_jsonl(dataset_file)

    manifest_file = out_dir / "manifest.json"
    if not manifest_file.exists():
        manifest_file.write_text(json.dumps({
            "model": MODEL_ID,
            "revision": MODEL_REVISION,
            "adapter": str(adapter_path),
            "data": str(dataset_file),
            "limit": len(items),
            "max_tokens": max_tokens,
            "machine": platform.platform(),
        }, indent=2) + "\n")

    tuned_file = out_dir / "tuned.jsonl"
    existing = read_jsonl(tuned_file) if tuned_file.is_file() else []
    done_ids = {r["id"] for r in existing}
    remaining = [it for it in items if it["id"] not in done_ids]

    if not remaining:
        print(f"[{out_dir.name}] All {len(items)} clean questions already evaluated.")
        return existing

    print(f"[{out_dir.name}] Evaluating {len(remaining)} remaining items (already have {len(done_ids)})...")
    from mlx_lm import load
    from mlx_lm.sample_utils import make_sampler

    sampler = make_sampler(temp=0.0)
    model, tokenizer = load(model_path(), adapter_path=str(adapter_path))

    with tuned_file.open("a") as handle:
        for i, item in enumerate(remaining, 1):
            t0 = time.perf_counter()
            text, tool_calls = generate_text("tuned", model, tokenizer, prompt_for("tuned", item["question"]), max_tokens, sampler)
            tokens = len(tokenizer.encode(text))
            ans_fmt = item.get("answer_format", "number")
            rec = {
                "id": item["id"],
                "question": item["question"],
                "gold": item["answer"],
                "output": text,
                "tokens": tokens,
                "truncated": tokens >= max_tokens,
                "tool_calls": tool_calls,
                "answer_format": ans_fmt,
                "seconds": round(time.perf_counter() - t0, 2),
                "check": score("tuned", text, item["question"], item["answer"], ans_fmt),
            }
            existing.append(rec)
            handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
            handle.flush()
            if i % 10 == 0 or i == len(remaining):
                print(f"[{out_dir.name}] Evaluated {i}/{len(remaining)} items...")

    del model, tokenizer
    import gc
    gc.collect()
    return existing


def run_standard_interventions(adapter_path, out_dir, max_tokens=512):
    from structured_llm.counterfactual import plan_intervention
    from mlx_lm import load
    from mlx_lm.sample_utils import make_sampler

    int_file = out_dir / "tuned_interventions.jsonl"
    existing = read_jsonl(int_file) if int_file.is_file() else []
    done_ids = {r["id"] for r in existing}

    sources = read_jsonl(out_dir / "tuned.jsonl")
    todo = []
    skipped = Counter()
    for s in sources:
        if s["id"] in done_ids:
            continue
        plan, reason = plan_intervention(s["output"], s["question"], s["id"])
        if plan is None:
            skipped[reason] += 1
            continue
        todo.append((s, plan))

    if not todo:
        print(f"[{out_dir.name}] All standard interventions already completed (N={len(existing)}).")
        return existing

    print(f"[{out_dir.name}] Running {len(todo)} standard interventions...")
    sampler = make_sampler(temp=0.0)
    model, tokenizer = load(model_path(), adapter_path=str(adapter_path))

    with int_file.open("a") as handle:
        for i, (s, plan) in enumerate(todo, 1):
            gen, _ = generate_text("tuned", model, tokenizer, prompt_for("tuned", s["question"]) + plan["prefix"], max_tokens, sampler)
            continued = plan["prefix"] + gen
            rec = {
                "id": s["id"],
                **plan,
                "continuation": gen,
                "outcome": classify(continued, plan),
                "tokens": len(tokenizer.encode(gen)),
                "originally_correct": bool(s["check"]["correct"]),
            }
            existing.append(rec)
            handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
            handle.flush()
            if i % 20 == 0 or i == len(todo):
                print(f"[{out_dir.name}] Intervened {i}/{len(todo)}...")

    del model, tokenizer
    import gc
    gc.collect()
    return existing


def run_exhaustive_step_sweep(adapter_path, out_dir, common_correct_ids, max_tokens=512):
    sweep_dir = OUT_DIR / "step_sweep"
    sweep_dir.mkdir(parents=True, exist_ok=True)
    sweep_file = sweep_dir / f"{out_dir.name}_sweep.jsonl"

    existing = read_jsonl(sweep_file) if sweep_file.is_file() else []
    done_ids = {r["id"] for r in existing}

    sources = [s for s in read_jsonl(out_dir / "tuned.jsonl") if s["id"] in common_correct_ids]
    todo = []
    for s in sources:
        plans = plan_all_interventions_for_trace(s["output"], s["question"], s["id"])
        for plan in plans:
            if plan["id"] not in done_ids:
                todo.append((s, plan))

    if not todo:
        print(f"[{out_dir.name} Sweep] All {len(existing)} sweep interventions already completed.")
        return existing

    print(f"[{out_dir.name} Sweep] Running {len(todo)} exhaustive step interventions...")
    from mlx_lm import load
    from mlx_lm.sample_utils import make_sampler

    sampler = make_sampler(temp=0.0)
    model, tokenizer = load(model_path(), adapter_path=str(adapter_path))

    with sweep_file.open("a") as handle:
        for i, (s, plan) in enumerate(todo, 1):
            gen, _ = generate_text("tuned", model, tokenizer, prompt_for("tuned", s["question"]) + plan["prefix"], max_tokens, sampler)
            continued = plan["prefix"] + gen
            rec = {
                "id": plan["id"],
                "parent_id": plan["parent_id"],
                "k": plan["k"],
                "K": plan["K"],
                "old": plan["old"],
                "new": plan["new"],
                "expected": plan["expected"],
                "original": plan["original"],
                "prefix": plan["prefix"],
                "continuation": gen,
                "outcome": classify(continued, plan),
                "tokens": len(tokenizer.encode(gen)),
            }
            existing.append(rec)
            handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
            handle.flush()
            if i % 20 == 0 or i == len(todo):
                print(f"[{out_dir.name} Sweep] Finished {i}/{len(todo)}...")

    del model, tokenizer
    import gc
    gc.collect()
    return existing


def generate_final_report():
    print("\n" + "=" * 70)
    print("COMPUTING FINAL STATISTICAL BENCHMARKS (N=300 & STEP SWEEP)")
    print("=" * 70)

    cf_clean = {r["id"]: r for r in read_jsonl(EVAL_CF_DIR / "tuned.jsonl")}
    plain_clean = {r["id"]: r for r in read_jsonl(EVAL_PLAIN_DIR / "tuned.jsonl")}
    common_clean = sorted(set(cf_clean.keys()) & set(plain_clean.keys()))

    # Clean McNemar
    n11, n01, n10, n00 = 0, 0, 0, 0
    for qid in common_clean:
        cf_ok = bool(cf_clean[qid]["check"]["correct"])
        pl_ok = bool(plain_clean[qid]["check"]["correct"])
        if cf_ok and pl_ok:
            n11 += 1
        elif cf_ok and not pl_ok:
            n01 += 1
        elif not cf_ok and pl_ok:
            n10 += 1
        else:
            n00 += 1

    d_clean = n01 + n10
    p_clean_2s = stats.binomtest(min(n01, n10), d_clean, 0.5).pvalue if d_clean > 0 else 1.0
    p_clean_1s = stats.binomtest(n01, d_clean, 0.5, alternative="greater").pvalue if d_clean > 0 else 1.0

    # Standard Interventions
    cf_int = {r["id"]: r for r in read_jsonl(EVAL_CF_DIR / "tuned_interventions.jsonl")}
    plain_int = {r["id"]: r for r in read_jsonl(EVAL_PLAIN_DIR / "tuned_interventions.jsonl")}
    shared_int_ids = sorted(set(cf_int.keys()) & set(plain_int.keys()))

    cf_c = Counter(cf_int[qid]["outcome"] for qid in shared_int_ids)
    pl_c = Counter(plain_int[qid]["outcome"] for qid in shared_int_ids)

    # Follows McNemar
    f_n11, f_n01, f_n10, f_n00 = 0, 0, 0, 0
    for qid in shared_int_ids:
        cf_f = (cf_int[qid]["outcome"] == "follows")
        pl_f = (plain_int[qid]["outcome"] == "follows")
        if cf_f and pl_f:
            f_n11 += 1
        elif cf_f and not pl_f:
            f_n01 += 1
        elif not cf_f and pl_f:
            f_n10 += 1
        else:
            f_n00 += 1
    d_f = f_n01 + f_n10
    p_f_2s = stats.binomtest(min(f_n01, f_n10), d_f, 0.5).pvalue if d_f > 0 else 1.0
    p_f_1s = stats.binomtest(f_n01, d_f, 0.5, alternative="greater").pvalue if d_f > 0 else 1.0

    # Exhaustive Sweep
    cf_sweep_file = OUT_DIR / "step_sweep/eval_cf_sweep.jsonl"
    pl_sweep_file = OUT_DIR / "step_sweep/eval_plain_sweep.jsonl"
    has_sweep = cf_sweep_file.is_file() and pl_sweep_file.is_file()

    sweep_lines = []
    if has_sweep:
        cf_sw = {r["id"]: r for r in read_jsonl(cf_sweep_file)}
        pl_sw = {r["id"]: r for r in read_jsonl(pl_sweep_file)}
        sw_ids = sorted(set(cf_sw.keys()) & set(pl_sw.keys()))
        sw_d01, sw_d10 = 0, 0
        for sid in sw_ids:
            if cf_sw[sid]["outcome"] == "follows" and pl_sw[sid]["outcome"] != "follows":
                sw_d01 += 1
            elif cf_sw[sid]["outcome"] != "follows" and pl_sw[sid]["outcome"] == "follows":
                sw_d10 += 1
        sw_d = sw_d01 + sw_d10
        sw_p2s = stats.binomtest(min(sw_d01, sw_d10), sw_d, 0.5).pvalue if sw_d > 0 else 1.0
        sw_p1s = stats.binomtest(sw_d01, sw_d, 0.5, alternative="greater").pvalue if sw_d > 0 else 1.0

        # Positional breakdown in sweep
        sw_pos = defaultdict(Counter)
        for sid in sw_ids:
            k = cf_sw[sid]["k"]
            sw_pos[k][cf_sw[sid]["outcome"]] += 1

        sweep_lines = [
            f"### C. Exhaustive Step Sweep Benchmarks (N={len(sw_ids)})",
            f"* **Discordant Pairs**: {sw_d} (CF+={sw_d01}, Plain+={sw_d10})",
            f"* **Exact McNemar p-value**: two-sided $p = {sw_p2s:.5f}$, one-sided $p = {sw_p1s:.5f}$",
            "\n| Step $k$ | Total $n$ | Follows (+Rounded) | Reverted | Moved | Other |",
            "| :---: | :---: | :---: | :---: | :---: | :---: |",
        ]
        for k in sorted(sw_pos):
            tot_k = sum(sw_pos[k].values())
            f_k = sw_pos[k]["follows"] + sw_pos[k]["follows_rounded"]
            r_k = sw_pos[k]["reverted"]
            m_k = sw_pos[k]["moved"]
            o_k = sw_pos[k]["other"]
            sweep_lines.append(f"| $k = {k}$ | {tot_k} | {f_k} ({f_k/tot_k*100:.1f}%) | {r_k} ({r_k/tot_k*100:.1f}%) | {m_k} | {o_k} |")

    report_md = f"""# Scale-Up Empirical Evaluation Report (N={len(common_clean)})

> Generated automatically by `scripts/run_scaleup_eval_300.py`
> Date: {time.strftime('%Y-%m-%d %H:%M:%S')}

---

## 1. Clean Accuracy & Paired McNemar Test ($N={len(common_clean)}$)

| Model | Correct | Accuracy |
| :--- | :---: | :---: |
| **Enriched CF (Proposed)** | {n11 + n01}/{len(common_clean)} | {(n11 + n01)/len(common_clean)*100:.2f}% |
| **Enriched Plain SFT (Baseline)** | {n11 + n10}/{len(common_clean)} | {(n11 + n10)/len(common_clean)*100:.2f}% |

### Paired Contingency Table
* Both Correct ($n_{{11}}$): **{n11}**
* CF Correct, Plain Wrong ($n_{{01}}$): **{n01}**
* Plain Correct, CF Wrong ($n_{{10}}$): **{n10}**
* Both Wrong ($n_{{00}}$): **{n00}**
* Total Discordant Pairs ($D = n_{{01}} + n_{{10}}$): **{d_clean}**
* **Exact McNemar Test**: Two-sided $p = \\mathbf{{{p_clean_2s:.5f}}}$, One-sided $p = \\mathbf{{{p_clean_1s:.5f}}}$

---

## 2. Causal Intervention Taxonomy ($N={len(shared_int_ids)}$ Shared Episodes)

| Metric | Enriched CF | Enriched Plain SFT |
| :--- | :---: | :---: |
| **Exact `follows`** | **{cf_c['follows']} ({cf_c['follows']/len(shared_int_ids)*100:.1f}%)** | {pl_c['follows']} ({pl_c['follows']/len(shared_int_ids)*100:.1f}%) |
| **`follows_rounded`** | {cf_c['follows_rounded']} ({cf_c['follows_rounded']/len(shared_int_ids)*100:.1f}%) | {pl_c['follows_rounded']} ({pl_c['follows_rounded']/len(shared_int_ids)*100:.1f}%) |
| **Total Compliance** | **{cf_c['follows'] + cf_c['follows_rounded']} ({(cf_c['follows'] + cf_c['follows_rounded'])/len(shared_int_ids)*100:.1f}%)** | {pl_c['follows'] + pl_c['follows_rounded']} ({(pl_c['follows'] + pl_c['follows_rounded'])/len(shared_int_ids)*100:.1f}%) |
| **`reverted`** | {cf_c['reverted']} ({cf_c['reverted']/len(shared_int_ids)*100:.1f}%) | {pl_c['reverted']} ({pl_c['reverted']/len(shared_int_ids)*100:.1f}%) |
| **`moved`** | {cf_c['moved']} | {pl_c['moved']} |
| **`other`** | {cf_c['other']} | {pl_c['other']} |

* **Exact Follows McNemar**: Discordant Pairs = **{d_f}** ($CF+={f_n01}, Plain+={f_n10}$), Two-sided $p = \\mathbf{{{p_f_2s:.5f}}}$, One-sided $p = \\mathbf{{{p_f_1s:.5f}}}$

---

## 3. Exhaustive Step Sweep & Positional Decay

{chr(10).join(sweep_lines) if sweep_lines else 'Sweep data running or not completed.'}
"""

    (OUT_DIR / "REPORT.md").write_text(report_md)
    print(f"\n[Report] Saved complete report to {OUT_DIR / 'REPORT.md'}")
    print(report_md)


def main():
    print("=== STARTING SCALE-UP PIPELINE ===")
    t_start = time.time()

    # 1. Dataset
    dataset_file = prepare_300_dataset()

    # 2. Seed existing Dev-100 clean evaluations to save 50+ min of compute
    seed_existing_dev100(EVAL_CF_DIR, "audit/lora_gsm8k_enriched_20261107/eval_cf")
    seed_existing_dev100(EVAL_PLAIN_DIR, "audit/lora_gsm8k_enriched_20261107/eval_plain")

    # 3. Clean Evaluation on remaining 200 items
    print("\n--- PHASE 1: CLEAN GENERATION (N=300) ---")
    cf_records = run_clean_evaluation(CF_ADAPTER, EVAL_CF_DIR, dataset_file)
    plain_records = run_clean_evaluation(PLAIN_ADAPTER, EVAL_PLAIN_DIR, dataset_file)

    # 4. Standard Interventions
    print("\n--- PHASE 2: STANDARD FIRST-STEP INTERVENTIONS ---")
    run_standard_interventions(CF_ADAPTER, EVAL_CF_DIR)
    run_standard_interventions(PLAIN_ADAPTER, EVAL_PLAIN_DIR)

    # 5. Exhaustive Step Sweep on Common Correct Items (n11)
    print("\n--- PHASE 3: EXHAUSTIVE STEP SWEEP ---")
    common_correct = [
        r["id"]
        for r in cf_records
        if bool(r["check"]["correct"]) and any(p["id"] == r["id"] and bool(p["check"]["correct"]) for p in plain_records)
    ]
    print(f"Total concordant clean-correct items (n11): {len(common_correct)}")
    run_exhaustive_step_sweep(CF_ADAPTER, EVAL_CF_DIR, common_correct)
    run_exhaustive_step_sweep(PLAIN_ADAPTER, EVAL_PLAIN_DIR, common_correct)

    # 6. Report
    generate_final_report()
    elapsed = time.time() - t_start
    print(f"\n=== SCALE-UP PIPELINE COMPLETE IN {elapsed / 60:.1f} MINUTES ===")


if __name__ == "__main__":
    main()
