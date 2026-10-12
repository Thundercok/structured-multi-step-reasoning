#!/usr/bin/env python3
"""Analysis script for Prompt AE: PAL-v2 evaluation and 7-arm Oracle gate.

Computes:
1. Table Family x {PAL, PAL-v2, TOT}: acc | mean tokens | %length
2. PAL-v2 failure modes with raw examples
3. Verdict vs prereg/decision_rule_palv2.md
4. 7-Arm Oracle Rule saved to audit/AE_oracle_rule_7arm.txt
"""

from collections import Counter, defaultdict
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "audit"
RUN11_TRACE = AUDIT_DIR / "run11_sweep_trace.jsonl"
PALV2_TRACE = AUDIT_DIR / "ae_palv2_trace.jsonl"
TUNE_PATH = ROOT / "data" / "gen02_tune.json"

FAMILIES = ["arith", "order", "g24"]


def load_all_traces():
    with open(RUN11_TRACE) as f:
        r11 = [json.loads(line) for line in f if line.strip()]
    with open(PALV2_TRACE) as f:
        palv2 = [json.loads(line) for line in f if line.strip()]
    with open(TUNE_PATH) as f:
        tasks = {item["id"]: item for item in json.load(f)["items"]}
    return r11, palv2, tasks


def compute_ae4_table(r11, palv2):
    recs = r11 + palv2
    target_arms = ["PAL", "PAL-v2", "TOT"]
    lines = []
    lines.append("| Family | Arm | n | Accuracy (corr/n) | Mean Prompt Tok | Mean Comp Tok | Mean Total Tok | %Length |")
    lines.append("| :--- | :--- | ---: | :---: | ---: | ---: | ---: | ---: |")

    data_summary = {}

    for fam in FAMILIES:
        for arm in target_arms:
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
            data_summary[(fam, arm)] = {
                "n": n, "corr": corr, "acc": acc,
                "p_tok": p_tok, "c_tok": c_tok, "tot_tok": tot_tok,
                "pct_len": pct_len,
            }
            lines.append(
                f"| {fam:5s} | {arm:9s} | {n:2d} | {acc*100:5.1f}% ({corr:2d}/{n:2d}) | {p_tok:6.1f} | {c_tok:6.1f} | {tot_tok:6.1f} | {pct_len:5.1f}% |"
            )

    table_text = "\n".join(lines)
    (AUDIT_DIR / "AE_table_pal_palv2_tot.txt").write_text(table_text + "\n", encoding="utf-8")
    return table_text, data_summary


def diagnose_palv2_failures(palv2, tasks):
    incorrect = [r for r in palv2 if not r["correct"]]
    lines = []
    lines.append(f"Total PAL-v2 incorrect items: {len(incorrect)} / {len(palv2)}")

    by_mode = defaultdict(list)
    for r in incorrect:
        exec_info = r.get("pal_exec", {})
        ok = exec_info.get("ok", False)
        output = str(exec_info.get("output", ""))
        f_reason = r.get("finish_reason", "")
        parsed = r.get("parsed")

        if not ok:
            if "timeout" in output:
                mode = "exception (timeout)"
            elif "blocked keyword" in output or "is not allowed" in output:
                mode = "exception (blocked/import disallowed)"
            elif "SyntaxError" in output:
                mode = "exception (SyntaxError)"
            else:
                mode = f"exception ({output[:30].strip()})"
        else:
            if f_reason == "length":
                mode = "length truncation"
            elif not parsed:
                mode = "no result parsed"
            else:
                mode = "wrong value"

        by_mode[mode].append(r)

    lines.append("\n### PAL-v2 Failure Mode Breakdown:")
    for mode, items in sorted(by_mode.items(), key=lambda x: -len(x[1])):
        lines.append(f"- **{mode}**: {len(items)} items ({len(items)/len(palv2)*100:.1f}%)")
        fams = Counter(it["family"] for it in items)
        lines.append(f"  Families: {dict(fams)}")

    lines.append("\n### Raw Failure Examples (up to 3):")
    sample_items = incorrect[:3]
    for idx, it in enumerate(sample_items, 1):
        exec_info = it.get("pal_exec", {})
        task = tasks.get(it["id"], {})
        lines.append(f"\n#### Example {idx}: ID `{it['id']}` (Family: `{it['family']}`, Level: `{it.get('level')}`)")
        lines.append(f"- **Query**: {task.get('query', it.get('query'))}")
        lines.append(f"- **Gold Answer**: `{it.get('gold')}`")
        lines.append(f"- **Parsed**: `{it.get('parsed')}`")
        lines.append(f"- **Finish Reason**: `{it.get('finish_reason')}`")
        lines.append(f"- **Sandbox Exec ok**: `{exec_info.get('ok')}`")
        lines.append(f"- **Sandbox Output**: ```\n{exec_info.get('output')}\n```")
        lines.append(f"- **Raw Code Output**: ```python\n{it.get('raw_output')}\n```")

    diag_text = "\n".join(lines)
    (AUDIT_DIR / "AE_palv2_failures.txt").write_text(diag_text + "\n", encoding="utf-8")
    return diag_text


def evaluate_palv2_verdict(data_summary):
    # Rule from prereg/decision_rule_palv2.md:
    # If PAL-v2 accuracy >= ToT on order AND on g24 (point estimates) at <= 0.5x ToT mean tokens:
    # those families are code-solvable; ToT/SC/COT claims there are withdrawn,
    # and the routing study must add families where a program is not a free solution.
    # Else: ToT stays best on the failing family; PAL limits documented.

    order_palv2 = data_summary[("order", "PAL-v2")]
    order_tot = data_summary[("order", "TOT")]
    g24_palv2 = data_summary[("g24", "PAL-v2")]
    g24_tot = data_summary[("g24", "TOT")]

    order_acc_pass = order_palv2["acc"] >= order_tot["acc"]
    g24_acc_pass = g24_palv2["acc"] >= g24_tot["acc"]
    order_tok_ratio = order_palv2["tot_tok"] / order_tot["tot_tok"]
    g24_tok_ratio = g24_palv2["tot_tok"] / g24_tot["tot_tok"]
    order_tok_pass = order_tok_ratio <= 0.5
    g24_tok_pass = g24_tok_ratio <= 0.5

    cond_met = (order_acc_pass and g24_acc_pass and order_tok_pass and g24_tok_pass)

    lines = []
    lines.append("## Verdict vs prereg/decision_rule_palv2.md\n")
    lines.append(f"- **Order**: PAL-v2 {order_palv2['acc']*100:.1f}% ({order_palv2['corr']}/{order_palv2['n']}) vs ToT {order_tot['acc']*100:.1f}% ({order_tot['corr']}/{order_tot['n']}); Tokens: {order_palv2['tot_tok']:.1f} vs {order_tot['tot_tok']:.1f} (ratio {order_tok_ratio:.2f}x, threshold <= 0.50x)")
    lines.append(f"  Acc condition: {'PASS' if order_acc_pass else 'FAIL'}; Token condition: {'PASS' if order_tok_pass else 'FAIL'}")
    lines.append(f"- **G24**: PAL-v2 {g24_palv2['acc']*100:.1f}% ({g24_palv2['corr']}/{g24_palv2['n']}) vs ToT {g24_tot['acc']*100:.1f}% ({g24_tot['corr']}/{g24_tot['n']}); Tokens: {g24_palv2['tot_tok']:.1f} vs {g24_tot['tot_tok']:.1f} (ratio {g24_tok_ratio:.2f}x, threshold <= 0.50x)")
    lines.append(f"  Acc condition: {'PASS' if g24_acc_pass else 'FAIL'}; Token condition: {'PASS' if g24_tok_pass else 'FAIL'}")

    if cond_met:
        verdict_text = (
            "**VERDICT: CODE-SOLVABLE CONFIRMED.** PAL-v2 accuracy >= ToT on order AND g24 at <= 0.5x ToT mean tokens. "
            "Those families are code-solvable; ToT/SC/COT claims there are withdrawn, and the routing study must add families "
            "where a program is not a free solution."
        )
    else:
        failing = []
        if not (order_acc_pass and order_tok_pass):
            failing.append("order")
        if not (g24_acc_pass and g24_tok_pass):
            failing.append("g24")
        verdict_text = (
            f"**VERDICT: REJECTED / CODE-SOLVABLE NOT SATISFIED on {', '.join(failing)}.** "
            f"ToT stays best on the failing family ({', '.join(failing)}); PAL limits documented."
        )

    lines.append(f"\n{verdict_text}")
    out = "\n".join(lines)
    (AUDIT_DIR / "AE_palv2_verdict.txt").write_text(out + "\n", encoding="utf-8")
    return out


def evaluate_oracle_7arm(r11, palv2, n_bootstrap=2000, seed=42):
    recs = r11 + palv2
    by_fam = defaultdict(lambda: defaultdict(list))
    for r in recs:
        by_fam[r["family"]][r["id"]].append(r)

    lines = []
    lines.append("| Family | Best-Single Arm (Acc, Tok) | 7-Arm Oracle (Acc, Tok) | Gap (pp) | 95% Cluster-Bootstrap CI | Prereg Gate Decision |")
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

        best_arm = max(arms_present, key=lambda a: (arm_stats[a][0], -arm_stats[a][1]))
        best_acc, best_tok = arm_stats[best_arm]

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

        go = (gap >= 0.10 and ci_low >= 0.05)
        decision = "**GO**" if go else "**NO-GO**"

        lines.append(
            f"| {fam:5s} | {best_arm} ({best_acc*100:.1f}%, {best_tok:.1f} tok) | {ora_acc*100:.1f}% ({ora_corr}/{n_items}), {ora_tok:.1f} tok | {gap*100:+.1f} pp | [{ci_low*100:+.1f} pp; {ci_high*100:+.1f} pp] | {decision} |"
        )

    out_text = "\n".join(lines)
    (AUDIT_DIR / "AE_oracle_rule_7arm.txt").write_text(out_text + "\n", encoding="utf-8")
    return out_text


def main():
    r11, palv2, tasks = load_all_traces()
    table_text, data_summary = compute_ae4_table(r11, palv2)
    diag_text = diagnose_palv2_failures(palv2, tasks)
    verdict_text = evaluate_palv2_verdict(data_summary)
    oracle_text = evaluate_oracle_7arm(r11, palv2)

    print("=== AE4 Table: Family x {PAL, PAL-v2, TOT} ===")
    print(table_text)
    print("\n=== PAL-v2 Failure Diagnostics ===")
    print(diag_text)
    print("\n=== PAL-v2 Verdict ===")
    print(verdict_text)
    print("\n=== 7-Arm Oracle Rule ===")
    print(oracle_text)


if __name__ == "__main__":
    main()
