"""Audit and report generation script for Sweep AG.

Evaluates:
- Table 1: PAL-v4 per family next to PAL-v2 and ToT (acc | tokens | %length | failure modes)
- R1 verdict: g24 code-solvability (PAL-v4 >= 17/29 AND mean total tokens <= 723)
- R2 verdict: order gapB code-solvability (PAL-v4 acc >= ToT acc AND tokens <= 0.5x ToT)
- R3 verdict: Cascade W with PAL-v4 on all 3 families vs always-ToT, always-PAL-v4, oracle(PAL-v4, ToT)
"""

import json
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent


def load_jsonl(path):
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def analyze_arm(records, family=None):
    if family:
        recs = [r for r in records if r.get("family") == family]
    else:
        recs = records
    n = len(recs)
    if n == 0:
        return {"n": 0, "correct": 0, "acc": 0.0, "tokens": 0.0, "pct_length": 0.0, "failures": {}}
    correct = sum(r.get("correct", False) for r in recs)
    acc = correct / n * 100.0
    toks = [r.get("prompt_tokens", 0) + r.get("completion_tokens", 0) for r in recs]
    mean_tok = sum(toks) / n
    pct_len = sum(r.get("finish_reason") == "length" for r in recs) / n * 100.0

    # Categorize failures
    fails = Counter()
    for r in recs:
        if not r.get("correct", False):
            if r.get("finish_reason") == "length":
                fails["length_cutoff"] += 1
            elif r.get("arm") in ("PAL", "PAL-v2", "PAL-v3", "PAL-v4"):
                pe = r.get("pal_exec", {})
                ok = pe.get("ok", False)
                out = str(pe.get("output", ""))
                if "blocked keyword" in out:
                    fails["blocked_keyword"] += 1
                elif "timeout" in out:
                    fails["timeout"] += 1
                elif "code produced no result" in out:
                    fails["no_result"] += 1
                elif out in ("None", "") or r.get("parsed") in ("None", "", None):
                    fails["empty_or_none"] += 1
                else:
                    fails["wrong_value"] += 1
            else:
                fails["wrong_answer"] += 1

    return {
        "n": n,
        "correct": correct,
        "acc": acc,
        "tokens": mean_tok,
        "pct_length": pct_len,
        "failures": dict(fails),
    }


def evaluate_policy_w(pal_recs, tot_recs):
    tot_by_id = {r["id"]: r for r in tot_recs}
    pal_by_id = {r["id"]: r for r in pal_recs}
    common_ids = sorted(set(pal_by_id.keys()) & set(tot_by_id.keys()))

    w_records = []
    escalations = 0

    for qid in common_ids:
        p_rec = pal_by_id[qid]
        t_rec = tot_by_id[qid]

        p_ok = p_rec.get("pal_exec", {}).get("ok", False)
        p_res = str(p_rec.get("pal_exec", {}).get("output", ""))
        p_parsed = p_rec.get("parsed")
        p_len = p_rec.get("finish_reason") == "length"

        escalate = False
        if not p_ok:
            escalate = True
        elif p_res in ("", "None", "None\n") or p_parsed in ("", "None", None):
            escalate = True
        elif p_len:
            escalate = True

        p_tok = p_rec.get("prompt_tokens", 0) + p_rec.get("completion_tokens", 0)
        t_tok = t_rec.get("prompt_tokens", 0) + t_rec.get("completion_tokens", 0)

        if escalate:
            escalations += 1
            tot_tokens = p_tok + t_tok
            correct = t_rec.get("correct", False)
            resolved_by = "TOT"
        else:
            tot_tokens = p_tok
            correct = p_rec.get("correct", False)
            resolved_by = "PAL"

        w_records.append({
            "id": qid,
            "group_id": p_rec.get("group_id", qid.split("_")[0]),
            "escalate": escalate,
            "resolved_by": resolved_by,
            "correct": correct,
            "tokens": tot_tokens,
            "pal_correct": p_rec.get("correct", False),
            "tot_correct": t_rec.get("correct", False),
            "oracle_correct": p_rec.get("correct", False) or t_rec.get("correct", False),
            "pal_tok": p_tok,
            "tot_tok": t_tok,
        })

    n = len(w_records)
    if n == 0:
        return None

    w_corr = sum(r["correct"] for r in w_records)
    pal_corr = sum(r["pal_correct"] for r in w_records)
    tot_corr = sum(r["tot_correct"] for r in w_records)
    ora_corr = sum(r["oracle_correct"] for r in w_records)

    w_tok = sum(r["tokens"] for r in w_records) / n
    pal_tok = sum(r["pal_tok"] for r in w_records) / n
    tot_tok = sum(r["tot_tok"] for r in w_records) / n

    # Bootstrap CI for W - ToT
    groups = defaultdict(list)
    for r in w_records:
        groups[r["group_id"]].append(r)
    group_keys = list(groups.keys())
    rng = np.random.default_rng(42)
    B = 5000
    diffs = []
    for _ in range(B):
        sg = rng.choice(group_keys, size=len(group_keys), replace=True)
        srecs = [r for g in sg for r in groups[g]]
        diffs.append((sum(r["correct"] for r in srecs) - sum(r["tot_correct"] for r in srecs)) / len(srecs))

    ci_low = np.percentile(diffs, 2.5) * 100
    ci_high = np.percentile(diffs, 97.5) * 100

    return {
        "n": n,
        "w_corr": w_corr, "w_acc": w_corr / n * 100.0, "w_tok": w_tok,
        "pal_corr": pal_corr, "pal_acc": pal_corr / n * 100.0, "pal_tok": pal_tok,
        "tot_corr": tot_corr, "tot_acc": tot_corr / n * 100.0, "tot_tok": tot_tok,
        "ora_corr": ora_corr, "ora_acc": ora_corr / n * 100.0,
        "escalations": escalations, "esc_rate": escalations / n * 100.0,
        "diff": (w_corr - tot_corr) / n * 100.0,
        "ci_low": ci_low, "ci_high": ci_high,
    }


def main():
    tune_palv4_path = ROOT / "audit/ag_palv4_tune_trace.jsonl"
    gapb_path = ROOT / "audit/ag_gapb_trace.jsonl"
    palv2_path = ROOT / "audit/ae_palv2_trace.jsonl"
    run11_path = ROOT / "audit/run11_sweep_trace.jsonl"

    if not tune_palv4_path.exists():
        print(f"Error: {tune_palv4_path} not found.")
        return

    palv4_tune = load_jsonl(tune_palv4_path)
    palv2_recs = load_jsonl(palv2_path) if palv2_path.exists() else []
    run11_recs = load_jsonl(run11_path) if run11_path.exists() else []
    gapb_recs = load_jsonl(gapb_path) if gapb_path.exists() else []

    tot_tune = [r for r in run11_recs if r.get("arm") == "TOT"]

    out_lines = []
    out_lines.append("=== AG4: PAL-v4 EMPIRICAL BENCHMARK & VERDICT REPORT ===\n")

    # Table 1: PAL-v4 next to PAL-v2 and ToT per family on gen02_tune
    out_lines.append("--- BẢNG 1: SO SÁNH HIỆU NĂNG TỪNG HỌ TRÊN GEN02_TUNE ---")
    out_lines.append(f"{'Family':<8} | {'Strategy':<10} | {'Acc':<12} | {'Tokens':<10} | {'%Length':<9} | {'Failure Modes'}")
    out_lines.append("-" * 80)

    families = ["arith", "order", "g24"]
    for fam in families:
        st_v4 = analyze_arm(palv4_tune, fam)
        st_v2 = analyze_arm(palv2_recs, fam)
        st_tot = analyze_arm(tot_tune, fam)

        f_str_v4 = ", ".join(f"{k}:{v}" for k, v in st_v4["failures"].items()) or "None"
        f_str_v2 = ", ".join(f"{k}:{v}" for k, v in st_v2["failures"].items()) or "None"
        f_str_tot = ", ".join(f"{k}:{v}" for k, v in st_tot["failures"].items()) or "None"

        out_lines.append(f"{fam:<8} | {'PAL-v4':<10} | {st_v4['correct']:>2}/{st_v4['n']:<2} ({st_v4['acc']:>5.1f}%) | {st_v4['tokens']:>8.1f} | {st_v4['pct_length']:>6.1f}%  | {f_str_v4}")
        out_lines.append(f"{'':<8} | {'PAL-v2':<10} | {st_v2['correct']:>2}/{st_v2['n']:<2} ({st_v2['acc']:>5.1f}%) | {st_v2['tokens']:>8.1f} | {st_v2['pct_length']:>6.1f}%  | {f_str_v2}")
        out_lines.append(f"{'':<8} | {'TOT':<10} | {st_tot['correct']:>2}/{st_tot['n']:<2} ({st_tot['acc']:>5.1f}%) | {st_tot['tokens']:>8.1f} | {st_tot['pct_length']:>6.1f}%  | {f_str_tot}")
        out_lines.append("-" * 80)

    # R1 Verdict (g24)
    out_lines.append("\n--- R1 VERDICT (GAME-OF-24 CODE-SOLVABILITY) ---")
    g24_v4 = analyze_arm(palv4_tune, "g24")
    out_lines.append(f"Preregistered Rule R1: Code-solvable iff PAL-v4 >= 17/29 AND mean tokens <= 723.")
    out_lines.append(f"Observed PAL-v4 on g24: {g24_v4['correct']}/{g24_v4['n']} ({g24_v4['acc']:.1f}%), Mean Tokens: {g24_v4['tokens']:.1f}")
    if g24_v4["correct"] >= 17 and g24_v4["tokens"] <= 723:
        r1_verdict = "CODE-SOLVABLE (PAL-v4 matches or beats ToT under budget)"
    else:
        r1_verdict = "REJECTED (ToT stays best on g24)"
    out_lines.append(f"R1 Verdict: {r1_verdict}\n")

    # R2 Verdict (order, wording gapB)
    out_lines.append("--- R2 VERDICT (ORDERING WORDING GAP-B CODE-SOLVABILITY) ---")
    gapb_palv4 = [r for r in gapb_recs if r.get("arm") == "PAL-v4"]
    gapb_tot = [r for r in gapb_recs if r.get("arm") == "TOT"]
    st_gapb_v4 = analyze_arm(gapb_palv4)
    st_gapb_tot = analyze_arm(gapb_tot)
    out_lines.append(f"Preregistered Rule R2: On 31 gapB items, code-solvable iff PAL-v4 acc >= ToT acc AND tokens <= 0.5x ToT.")
    out_lines.append(f"Observed gapB PAL-v4: {st_gapb_v4['correct']}/{st_gapb_v4['n']} ({st_gapb_v4['acc']:.1f}%), Mean Tokens: {st_gapb_v4['tokens']:.1f}")
    out_lines.append(f"Observed gapB ToT:    {st_gapb_tot['correct']}/{st_gapb_tot['n']} ({st_gapb_tot['acc']:.1f}%), Mean Tokens: {st_gapb_tot['tokens']:.1f}")
    tot_tok_half = st_gapb_tot['tokens'] * 0.5 if st_gapb_tot['n'] > 0 else 0
    if st_gapb_v4["correct"] >= st_gapb_tot["correct"] and st_gapb_v4["tokens"] <= tot_tok_half:
        r2_verdict = "CODE-SOLVABLE (PAL-v4 >= ToT on gapB at <= 0.5x tokens)"
    else:
        r2_verdict = "REJECTED (ToT keeps its edge on gapB)"
    out_lines.append(f"R2 Verdict: {r2_verdict}\n")

    # R3: Cascade Policy W with PAL-v4 on all 3 families
    out_lines.append("--- R3 VERDICT: CASCADE POLICY W (PAL-V4 -> TOT) TRÊN CẢ 3 HỌ ---")
    out_lines.append(f"{'Family':<8} | {'Always-PAL-v4':<14} | {'Always-ToT':<14} | {'Policy W':<16} | {'Oracle':<10} | {'Escalation':<12} | {'Delta (W-ToT) [95% CI]'}")
    out_lines.append("-" * 110)

    for fam in families:
        f_pal = [r for r in palv4_tune if r.get("family") == fam]
        f_tot = [r for r in tot_tune if r.get("family") == fam]
        w_res = evaluate_policy_w(f_pal, f_tot)
        if w_res:
            pal_s = f"{w_res['pal_corr']}/{w_res['n']} ({w_res['pal_acc']:.1f}%)"
            tot_s = f"{w_res['tot_corr']}/{w_res['n']} ({w_res['tot_acc']:.1f}%)"
            w_s = f"{w_res['w_corr']}/{w_res['n']} ({w_res['w_acc']:.1f}%)"
            ora_s = f"{w_res['ora_corr']}/{w_res['n']} ({w_res['ora_acc']:.1f}%)"
            esc_s = f"{w_res['escalations']}/{w_res['n']} ({w_res['esc_rate']:.1f}%)"
            diff_s = f"{w_res['diff']:+.1f}pp [{w_res['ci_low']:+.1f}; {w_res['ci_high']:+.1f}]"
            out_lines.append(f"{fam:<8} | {pal_s:<14} | {tot_s:<14} | {w_s:<16} | {ora_s:<10} | {esc_s:<12} | {diff_s}")
            out_lines.append(f"{'  tokens':<8} | {w_res['pal_tok']:>8.1f} tok   | {w_res['tot_tok']:>8.1f} tok   | {w_res['w_tok']:>8.1f} tok     | {'N/A':<10} | {'':<12} | {'':<20}")
            out_lines.append("-" * 110)

    report_text = "\n".join(out_lines)
    print(report_text)

    out_file = ROOT / "audit/AG_ag4_tables.txt"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(report_text + "\n")
    print(f"\nSaved report to {out_file}")


if __name__ == "__main__":
    main()
