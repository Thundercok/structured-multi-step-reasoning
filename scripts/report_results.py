#!/usr/bin/env python3
"""Comprehensive empirical reporting and audit verification script (Prompt AD).

Implements:
- AD1: Per-family x arm descriptive performance table (n, acc, tokens, %length)
- AD2: Decision rule oracle evaluation over all 6 arms per family with cluster bootstrap
- AD3: Post-hoc V' policy (COT -> verifier/length -> TOT) on order and g24
- AD4: Failure mode diagnosis for PAL (order, g24) and REACT (g24) with raw examples
- AD5: SC vote share distribution and consensus convergence analysis
- AD6: Per-family Pareto frontier chart saved to audit/AD_pareto.png
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import random
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verifiers import order_verifier
from scripts.gen_tasks import check24
from reasoning_strategies import majority_vote

AUDIT_DIR = ROOT / "audit"
TRACE_PATH = AUDIT_DIR / "run11_sweep_trace.jsonl"
TUNE_PATH = ROOT / "data" / "gen02_tune.json"

FAMILIES = ["arith", "order", "g24"]
ALL_ARMS = ["DIRECT-v2", "COT", "SC", "TOT", "REACT", "PAL"]


def load_data():
    if not TRACE_PATH.exists():
        raise FileNotFoundError(f"Trace not found: {TRACE_PATH}")
    with open(TRACE_PATH) as f:
        recs = [json.loads(line) for line in f if line.strip()]
    with open(TUNE_PATH) as f:
        tasks = {item["id"]: item for item in json.load(f)["items"]}
    return recs, tasks


# ==============================================================================
# AD1: Per family x arm descriptive statistics
# ==============================================================================
def run_ad1(recs: list[dict]) -> str:
    lines = []
    lines.append("| Family | Arm | n | Accuracy (corr/n) | Mean Prompt Tok | Mean Comp Tok | Mean Total Tok | %Length |")
    lines.append("| :--- | :--- | ---: | :---: | ---: | ---: | ---: | ---: |")
    
    for fam in FAMILIES:
        for arm in ALL_ARMS:
            sub = [r for r in recs if r.get("family") == fam and r.get("arm") == arm]
            if not sub:
                continue
            n = len(sub)
            corr = sum(1 for r in sub if r["correct"])
            acc = corr / n
            p_tok = sum(r.get("prompt_tokens", 0) for r in sub) / n
            c_tok = sum(r.get("completion_tokens", 0) for r in sub) / n
            tot_tok = p_tok + c_tok
            pct_len = (sum(1 for r in sub if r.get("finish_reason") == "length") / n) * 100.0
            lines.append(
                f"| {fam:5s} | {arm:9s} | {n:2d} | {acc*100:5.1f}% ({corr:2d}/{n:2d}) | {p_tok:6.1f} | {c_tok:6.1f} | {tot_tok:6.1f} | {pct_len:5.1f}% |"
            )
    out_text = "\n".join(lines)
    (AUDIT_DIR / "AD_report_results.txt").write_text(out_text + "\n", encoding="utf-8")
    return out_text


# ==============================================================================
# AD2: Preregistered Decision Rule Oracle across ALL 6 arms per family
# ==============================================================================
def run_ad2(recs: list[dict], n_bootstrap: int = 2000, seed: int = 42) -> str:
    by_fam = defaultdict(lambda: defaultdict(list))
    for r in recs:
        by_fam[r["family"]][r["id"]].append(r)
    
    lines = []
    lines.append("| Family | Best-Single Arm (Acc, Tok) | 6-Arm Oracle (Acc, Tok) | Gap (pp) | 95% Cluster-Bootstrap CI | Prereg Gate Decision |")
    lines.append("| :--- | :--- | :--- | :---: | :---: | :---: |")
    
    for fam in FAMILIES:
        items = by_fam[fam]
        n_items = len(items)
        arms_present = sorted(list(set(r["arm"] for iid in items for r in items[iid])))
        
        arm_stats = {}
        for arm in arms_present:
            sub = [r for iid in items for r in items[iid] if r["arm"] == arm]
            acc = sum(r["correct"] for r in sub) / len(sub)
            tok = sum(r.get("prompt_tokens", 0) + r.get("completion_tokens", 0) for r in sub) / len(sub)
            arm_stats[arm] = (acc, tok)
        
        # Best-single: highest acc; tie break: lowest total tokens
        best_arm = max(arms_present, key=lambda a: (arm_stats[a][0], -arm_stats[a][1]))
        best_acc, best_tok = arm_stats[best_arm]
        
        # Oracle: cheapest correct arm per item; if none correct, cheapest overall arm
        ora_corr = 0
        ora_tokens = 0
        for iid, i_recs in items.items():
            corr = [r for r in i_recs if r["correct"]]
            if corr:
                ora_corr += 1
                cheapest = min(corr, key=lambda r: r.get("prompt_tokens", 0) + r.get("completion_tokens", 0))
            else:
                cheapest = min(i_recs, key=lambda r: r.get("prompt_tokens", 0) + r.get("completion_tokens", 0))
            ora_tokens += cheapest.get("prompt_tokens", 0) + cheapest.get("completion_tokens", 0)
        
        ora_acc = ora_corr / n_items
        ora_tok = ora_tokens / n_items
        gap = ora_acc - best_acc
        
        # Cluster bootstrap by group_id
        groups = defaultdict(list)
        for iid, i_recs in items.items():
            gid = i_recs[0].get("group_id", iid)
            groups[gid].append(iid)
        gids = list(groups.keys())
        
        rng = random.Random(seed)
        boot_gaps = []
        for _ in range(n_bootstrap):
            sg = rng.choices(gids, k=len(gids))
            s_iids = [i for gid in sg for i in groups[gid]]
            s_ora_corr = sum(1 for i in s_iids if any(r["correct"] for r in items[i]))
            s_best_corr = sum(1 for i in s_iids if any(r["correct"] for r in items[i] if r["arm"] == best_arm))
            boot_gaps.append((s_ora_corr - s_best_corr) / len(s_iids))
        
        boot_gaps.sort()
        ci_low = boot_gaps[int(0.025 * len(boot_gaps))]
        ci_high = boot_gaps[min(int(0.975 * len(boot_gaps)), len(boot_gaps) - 1)]
        
        # Prereg rule: gap >= 10pp AND ci_low >= 5pp
        go = (gap >= 0.10 and ci_low >= 0.05)
        decision = "**GO**" if go else "**NO-GO**"
        
        lines.append(
            f"| {fam:5s} | {best_arm} ({best_acc*100:.1f}%, {best_tok:.1f} tok) | {ora_acc*100:.1f}% ({ora_corr}/{n_items}), {ora_tok:.1f} tok | {gap*100:+.1f} pp | [{ci_low*100:+.1f} pp; {ci_high*100:+.1f} pp] | {decision} |"
        )
    
    out_text = "\n".join(lines)
    (AUDIT_DIR / "AD_oracle_rule.txt").write_text(out_text + "\n", encoding="utf-8")
    return out_text


# ==============================================================================
# AD3: Post-hoc V' (COT -> verifier/length -> TOT) on order and g24
# ==============================================================================
def run_ad3(recs: list[dict], tasks: dict[str, dict], n_bootstrap: int = 2000, seed: int = 42) -> str:
    by_arm_id = {(r["arm"], r["id"]): r for r in recs}
    
    lines = []
    lines.append("| Family | Always-COT | Always-TOT | Oracle(COT,TOT) | Policy V' (post-hoc E=TOT) | Delta (V' - COT) [95% CI] | Token Ratio (V' / TOT) |")
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
    
    for fam in ["order", "g24"]:
        ids = sorted([iid for iid, t in tasks.items() if t["family"] == fam])
        n = len(ids)
        
        cot_recs = [by_arm_id[("COT", iid)] for iid in ids]
        tot_recs = [by_arm_id[("TOT", iid)] for iid in ids]
        
        cot_acc = sum(r["correct"] for r in cot_recs) / n
        cot_tok = sum(r.get("prompt_tokens", 0) + r.get("completion_tokens", 0) for r in cot_recs) / n
        
        tot_acc = sum(r["correct"] for r in tot_recs) / n
        tot_tok = sum(r.get("prompt_tokens", 0) + r.get("completion_tokens", 0) for r in tot_recs) / n
        
        # Oracle(COT, TOT)
        ora_corr = 0
        ora_tokens = 0
        for c, t in zip(cot_recs, tot_recs):
            c_cost = c.get("prompt_tokens", 0) + c.get("completion_tokens", 0)
            t_cost = t.get("prompt_tokens", 0) + t.get("completion_tokens", 0)
            if c["correct"] and t["correct"]:
                ora_corr += 1
                ora_tokens += min(c_cost, t_cost)
            elif c["correct"]:
                ora_corr += 1
                ora_tokens += c_cost
            elif t["correct"]:
                ora_corr += 1
                ora_tokens += t_cost
            else:
                ora_tokens += min(c_cost, t_cost)
        ora_acc = ora_corr / n
        ora_tok = ora_tokens / n
        
        # V' policy: COT -> if verifier flags or length -> TOT
        v_corr = 0
        v_tokens = 0
        esc_count = 0
        v_item_corr = {}
        for c, t in zip(cot_recs, tot_recs):
            iid = c["id"]
            task = tasks[iid]
            hit_len = (c.get("finish_reason") == "length")
            if fam == "order":
                flagged, _ = order_verifier(c.get("raw_output", ""), task["meta"], flag_unextractable=False)
            else: # g24
                parsed = c.get("parsed", "")
                numbers = task["meta"]["numbers"]
                valid = check24(parsed, numbers) if parsed else False
                flagged = not valid
            
            esc = hit_len or flagged
            if esc:
                esc_count += 1
                final_r = t
                cost = (c.get("prompt_tokens", 0) + c.get("completion_tokens", 0)) + (t.get("prompt_tokens", 0) + t.get("completion_tokens", 0))
            else:
                final_r = c
                cost = c.get("prompt_tokens", 0) + c.get("completion_tokens", 0)
            
            if final_r["correct"]:
                v_corr += 1
            v_tokens += cost
            v_item_corr[iid] = final_r["correct"]
        
        v_acc = v_corr / n
        v_tok = v_tokens / n
        delta = v_acc - cot_acc
        ratio = v_tok / tot_tok
        
        # Cluster bootstrap
        groups = defaultdict(list)
        for iid in ids:
            gid = tasks[iid].get("group_id", iid)
            groups[gid].append(iid)
        gids = list(groups.keys())
        
        rng = random.Random(seed)
        boot_deltas = []
        for _ in range(n_bootstrap):
            sg = rng.choices(gids, k=len(gids))
            s_iids = [i for gid in sg for i in groups[gid]]
            s_v = sum(1 for i in s_iids if v_item_corr[i]) / len(s_iids)
            s_c = sum(1 for i in s_iids if by_arm_id[("COT", i)]["correct"]) / len(s_iids)
            boot_deltas.append(s_v - s_c)
        
        boot_deltas.sort()
        ci_low = boot_deltas[int(0.025 * len(boot_deltas))]
        ci_high = boot_deltas[min(int(0.975 * len(boot_deltas)), len(boot_deltas) - 1)]
        
        lines.append(
            f"| {fam:5s} | {cot_acc*100:.1f}% ({cot_tok:.1f} tok) | {tot_acc*100:.1f}% ({tot_tok:.1f} tok) | {ora_acc*100:.1f}% ({ora_tok:.1f} tok) | {v_acc*100:.1f}% ({v_tok:.1f} tok, esc: {esc_count}/{n}) | {delta*100:+.1f} pp [{ci_low*100:+.1f} pp; {ci_high*100:+.1f} pp] | {ratio:.2f} |"
        )
    
    out_text = "\n".join(lines)
    (AUDIT_DIR / "AD_posthoc_tot.txt").write_text(out_text + "\n", encoding="utf-8")
    return out_text


# ==============================================================================
# AD4: Failure mode diagnosis for PAL (order, g24) and REACT (g24)
# ==============================================================================
def run_ad4(recs: list[dict]) -> tuple[str, str]:
    table_lines = []
    table_lines.append("| Arm | Family | Total | Failure Mode | Count | Share (%) | Primary Root Cause |")
    table_lines.append("| :--- | :--- | ---: | :--- | ---: | ---: | :--- |")
    
    raw_details = []
    
    targets = [
        ("PAL", "order", "Order expects string name; sandbox blocks imports (`itertools`) and prompt asks for numeric scalar `result`"),
        ("PAL", "g24", "G24 expects arithmetic expression; sandbox blocks itertools/product; model emits scalar 24 or syntax errors"),
        ("REACT", "g24", "ReAct calculator loop computes scalar arithmetic; emits scalar 24 or exceeds loop steps instead of binary tree expression"),
    ]
    
    for arm, fam, root_cause in targets:
        sub = [r for r in recs if r["arm"] == arm and r["family"] == fam]
        n = len(sub)
        modes = []
        for r in sub:
            raw = r.get("raw_output", "")
            parsed = r.get("parsed", "")
            status = r.get("parse_status", "")
            
            if arm == "PAL":
                if status == "pal_fail" or "Traceback" in raw or "Error" in raw or "Disallowed import" in raw:
                    m = "exception (sandbox import/execution block)"
                elif not parsed or parsed == "None":
                    m = "no result"
                elif fam == "order":
                    try:
                        float(parsed)
                        m = "wrong type (numeric scalar instead of name)"
                    except (ValueError, TypeError):
                        m = "wrong value (syntax token or comment parsed)"
                elif fam == "g24":
                    if str(parsed).strip() == "24":
                        m = "wrong type (scalar 24 instead of expression string)"
                    else:
                        m = "wrong value / invalid syntax expression"
                else:
                    m = "other"
            else: # REACT
                if not parsed or parsed == "None":
                    m = "no result / turn limit"
                elif str(parsed).strip() == "24":
                    m = "wrong type (scalar 24 instead of expression string)"
                else:
                    m = "wrong value / invalid format"
            modes.append(m)
        
        counts = Counter(modes)
        for m, cnt in counts.most_common():
            table_lines.append(f"| {arm:5s} | {fam:5s} | {n:2d} | {m} | {cnt:2d} | {cnt/n*100:5.1f}% | {root_cause[:45]}... |")
        
        raw_details.append(f"=== {arm} on {fam} Raw Examples (First 3) ===")
        for i, r in enumerate(sub[:3]):
            raw_details.append(f"Example {i+1} [{r['id']}]:")
            raw_details.append(f"  Raw: {repr(r.get('raw_output', '')[:140])}")
            raw_details.append(f"  Parsed: {repr(r.get('parsed', ''))} | Gold: {repr(r.get('gold', ''))} | Status: {r.get('parse_status')}")
        raw_details.append("")
    
    table_text = "\n".join(table_lines)
    full_text = table_text + "\n\n" + "\n".join(raw_details)
    (AUDIT_DIR / "AD_failure_modes.txt").write_text(full_text + "\n", encoding="utf-8")
    return table_text, full_text


# ==============================================================================
# AD5: SC vote share distribution and consensus convergence analysis
# ==============================================================================
def run_ad5(recs: list[dict]) -> str:
    lines = []
    lines.append("| Family | Status | n | Mean Winner Vote Share (Reconstructed k/5) | Median Winner Share | Mean Logged sc_vote_share (Double-div /5) | Share with Winner Share >= 0.6 (>=3/5 votes) |")
    lines.append("| :--- | :--- | ---: | :---: | :---: | :---: | :---: |")
    
    for fam in ["order", "g24"]:
        sub = [r for r in recs if r["arm"] == "SC" and r["family"] == fam]
        corr = [r for r in sub if r["correct"]]
        wrong = [r for r in sub if not r["correct"]]
        
        for name, group in [("Correct", corr), ("Wrong", wrong), ("Total", sub)]:
            n = len(group)
            if n == 0:
                continue
            real_shares = [majority_vote(r["sc_candidates"])[1] for r in group]
            logged_shares = [r.get("sc_vote_share", 0) for r in group]
            ge_60 = sum(1 for s in real_shares if s >= 0.6)
            pct_ge_60 = (ge_60 / n) * 100.0
            
            lines.append(
                f"| {fam:5s} | {name:7s} | {n:2d} | {np.mean(real_shares):.3f} | {np.median(real_shares):.3f} | {np.mean(logged_shares):.3f} | {ge_60:2d}/{n:2d} ({pct_ge_60:5.1f}%) |"
            )
    
    out_text = "\n".join(lines)
    (AUDIT_DIR / "AD_sc_consensus.txt").write_text(out_text + "\n", encoding="utf-8")
    return out_text


# ==============================================================================
# AD6: Per-family Pareto Frontier PNG
# ==============================================================================
def run_ad6(recs: list[dict], tasks: dict[str, dict]):
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5), dpi=300)
    plt.subplots_adjust(wspace=0.25)
    
    by_arm_id = {(r["arm"], r["id"]): r for r in recs}
    by_fam = defaultdict(lambda: defaultdict(list))
    for r in recs:
        by_fam[r["family"]][r["id"]].append(r)
    
    arm_colors = {
        "DIRECT-v2": "#7f7f7f",
        "COT": "#1f77b4",
        "SC": "#ff7f0e",
        "TOT": "#2ca02c",
        "REACT": "#d62728",
        "PAL": "#9467bd",
    }
    arm_markers = {
        "DIRECT-v2": "o",
        "COT": "s",
        "SC": "^",
        "TOT": "D",
        "REACT": "v",
        "PAL": "P",
    }
    
    family_titles = {
        "arith": "Arithmetic (N=40)",
        "order": "Ordering (N=31)",
        "g24": "Game-of-24 (N=29)",
    }
    
    for ax_idx, fam in enumerate(FAMILIES):
        ax = axes[ax_idx]
        items = by_fam[fam]
        n_items = len(items)
        
        # Plot individual arms
        for arm in ALL_ARMS:
            sub = [r for iid in items for r in items[iid] if r["arm"] == arm]
            if not sub:
                continue
            acc = (sum(r["correct"] for r in sub) / len(sub)) * 100.0
            tok = sum(r.get("prompt_tokens", 0) + r.get("completion_tokens", 0) for r in sub) / len(sub)
            ax.scatter(
                tok, acc, color=arm_colors[arm], marker=arm_markers[arm],
                s=110, label=arm, zorder=5, edgecolors="black", linewidth=0.8
            )
            ax.annotate(
                f" {arm}\n ({acc:.0f}%, {tok:.0f}t)",
                (tok, acc), fontsize=8.5,
                xytext=(5, 3 if acc < 90 else -18), textcoords="offset points"
            )
        
        # Plot Family-specific Policies and Oracles
        if fam == "arith":
            # Policy V (COT -> PAL)
            # 100%, 371.6 tokens
            ax.scatter(371.6, 100.0, color="#8c564b", marker="*", s=160, label="Policy V (COT->PAL)", zorder=6, edgecolors="black")
            ax.annotate(" Policy V\n (100%, 372t)", (371.6, 100.0), fontsize=8.5, xytext=(5, -18), textcoords="offset points")
            # Oracle (6-arm)
            ax.scatter(169.2, 100.0, color="#e377c2", marker="X", s=130, label="6-Arm Oracle", zorder=6, edgecolors="black")
            ax.annotate(" 6-Arm Oracle\n (100%, 169t)", (169.2, 100.0), fontsize=8.5, xytext=(-65, 8), textcoords="offset points")
            
        elif fam == "order":
            # Policy V (COT -> SC): 45.2%, 2952.1 tok
            ax.scatter(2952.1, 45.2, color="#8c564b", marker="*", s=130, label="Policy V (COT->SC)", zorder=6, edgecolors="black")
            ax.annotate(" Policy V (SC)\n (45%, 2952t)", (2952.1, 45.2), fontsize=8, xytext=(5, -15), textcoords="offset points")
            # Policy V' (COT -> TOT): 71.0%, 2088.1 tok
            ax.scatter(2088.1, 71.0, color="#17becf", marker="*", s=160, label="Policy V' (COT->TOT)", zorder=6, edgecolors="black")
            ax.annotate(" Policy V' (TOT)\n (71%, 2088t)", (2088.1, 71.0), fontsize=8.5, xytext=(5, 5), textcoords="offset points")
            # Oracle (6-arm): 80.6%, 645.9 tok
            ax.scatter(645.9, 80.6, color="#e377c2", marker="X", s=130, label="6-Arm Oracle", zorder=6, edgecolors="black")
            ax.annotate(" 6-Arm Oracle\n (81%, 646t)", (645.9, 80.6), fontsize=8.5, xytext=(5, 5), textcoords="offset points")
            
        elif fam == "g24":
            # Policy V' (COT -> TOT): 62.1%, 1649.8 tok
            ax.scatter(1649.8, 62.1, color="#17becf", marker="*", s=160, label="Policy V' (COT->TOT)", zorder=6, edgecolors="black")
            ax.annotate(" Policy V' (TOT)\n (62%, 1650t)", (1649.8, 62.1), fontsize=8.5, xytext=(5, 5), textcoords="offset points")
            # Oracle (6-arm): 65.5%, 533.6 tok
            ax.scatter(533.6, 65.5, color="#e377c2", marker="X", s=130, label="6-Arm Oracle", zorder=6, edgecolors="black")
            ax.annotate(" 6-Arm Oracle\n (66%, 534t)", (533.6, 65.5), fontsize=8.5, xytext=(5, 5), textcoords="offset points")
            
        ax.set_title(family_titles[fam], fontsize=13, fontweight="bold", pad=12)
        ax.set_xlabel("Mean Total Tokens (Prompt + Completion)", fontsize=10.5)
        if ax_idx == 0:
            ax.set_ylabel("Accuracy (%)", fontsize=11, fontweight="bold")
        ax.set_ylim(-5, 108)
        ax.grid(True, linestyle="--", alpha=0.5, zorder=0)
        ax.legend(loc="lower right" if fam != "arith" else "center right", fontsize=8.5, framealpha=0.9)
    
    plt.suptitle("Per-Family Accuracy vs. Token Cost Trade-Offs (Qwen3-8B-4bit, Run 11)", fontsize=15, fontweight="bold", y=1.02)
    png_path = AUDIT_DIR / "AD_pareto.png"
    plt.savefig(png_path, bbox_inches="tight")
    plt.close()
    return png_path


# ==============================================================================
# Main entrypoint
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(description="Audit Reporting and Evaluation (Prompt AD)")
    args = parser.parse_args()
    
    recs, tasks = load_data()
    
    # Run all analyses and save artifacts
    ad1_text = run_ad1(recs)
    ad2_text = run_ad2(recs)
    ad3_text = run_ad3(recs, tasks)
    ad4_table, ad4_full = run_ad4(recs)
    ad5_text = run_ad5(recs)
    png_path = run_ad6(recs, tasks)
    
    # Print formatted tables to stdout as requested by Prompt AD
    print("### AD1: Per-Family x Arm Descriptive Performance\n")
    print(ad1_text)
    print("\n---\n")
    print("### AD2: Preregistered Decision Rule Oracle (All 6 Arms)\n")
    print(ad2_text)
    print("\n---\n")
    print("### AD3: Post-hoc Escalation Policy V' (COT -> Verifier/Length -> TOT)\n")
    print(ad3_text)
    print("\n---\n")
    print("### AD4: Failure Mode Diagnosis for PAL and REACT\n")
    print(ad4_table)
    print("\n---\n")
    print("### AD5: SC Winner Vote Share and Consensus Analysis\n")
    print(ad5_text)
    print("\n---\n")
    print(f"### AD6: Per-family Pareto Plot saved to: {png_path.relative_to(ROOT)}\n")


if __name__ == "__main__":
    main()
