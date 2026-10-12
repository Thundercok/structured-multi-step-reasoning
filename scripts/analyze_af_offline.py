#!/usr/bin/env python3
"""Offline analysis script for Prompt AF (AF2 and AF3).

AF2:
- Order & G24: Oracle restricted to strong arms:
  * Subset 1: {COT, TOT, PAL-v2}
  * Subset 2: {TOT, PAL-v2}
- Metrics: Acc, tokens, gap vs best-single, 95% cluster-bootstrap CI.
- 2x2 contingency counts for PAL-v2 vs TOT:
  * both right
  * only PAL-v2
  * only TOT
  * neither
- Labeled: 'exploratory; arms added after seeing 6-arm results'

AF3:
- For the 11 failed order PAL-v2 items:
  * Item ID, level
  * Rendered query / clues
  * Code mistranslation / error explanation
  * Whether COT and TOT also failed on that item
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


def load_traces():
    with open(RUN11_TRACE) as f:
        r11 = [json.loads(line) for line in f if line.strip()]
    with open(PALV2_TRACE) as f:
        palv2 = [json.loads(line) for line in f if line.strip()]
    with open(TUNE_PATH) as f:
        tasks = {item["id"]: item for item in json.load(f)["items"]}
    return r11 + palv2, tasks


def run_af2(recs, seed=42, n_bootstrap=2000):
    lines = []
    lines.append("# AF2: Oracle Analysis Restricted to Strong Arms (Exploratory)")
    lines.append("> Label: **exploratory; arms added after seeing 6-arm results**\n")

    subsets = [
        ("{COT, TOT, PAL-v2}", ["COT", "TOT", "PAL-v2"]),
        ("{TOT, PAL-v2}", ["TOT", "PAL-v2"]),
    ]

    target_fams = ["order", "g24"]

    by_fam = defaultdict(lambda: defaultdict(list))
    for r in recs:
        by_fam[r["family"]][r["id"]].append(r)

    # 1. Oracle Table for each subset
    for subset_name, arm_set in subsets:
        lines.append(f"### Subset: {subset_name}")
        lines.append("| Family | Best-Single Arm (Acc, Tok) | Oracle(Arms) (Acc, Tok) | Gap vs Best-Single (pp) | 95% Cluster-Bootstrap CI |")
        lines.append("| :--- | :--- | :--- | :---: | :---: |")

        for fam in target_fams:
            items = by_fam[fam]
            n_items = len(items)

            arm_stats = {}
            for arm in arm_set:
                sub = [r for iid in items for r in items[iid] if r["arm"] == arm]
                acc = sum(r["correct"] for r in sub) / len(sub)
                tok = sum(r.get("prompt_tokens", 0) + r.get("completion_tokens", 0) for r in sub) / len(sub)
                arm_stats[arm] = (acc, tok)

            best_arm = max(arm_set, key=lambda a: (arm_stats[a][0], -arm_stats[a][1]))
            best_acc, best_tok = arm_stats[best_arm]

            ora_corr = 0
            ora_tokens = 0
            for iid, i_recs in items.items():
                relevant = [r for r in i_recs if r["arm"] in arm_set]
                corr = [r for r in relevant if r["correct"]]
                if corr:
                    ora_corr += 1
                    cheapest = min(corr, key=lambda r: r.get("prompt_tokens", 0) + r.get("completion_tokens", 0))
                else:
                    cheapest = min(relevant, key=lambda r: r.get("prompt_tokens", 0) + r.get("completion_tokens", 0))
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
                s_ora_corr = sum(1 for i in s_iids if any(r["correct"] for r in items[i] if r["arm"] in arm_set))
                s_best_corr = sum(1 for i in s_iids if any(r["correct"] for r in items[i] if r["arm"] == best_arm))
                boot_gaps.append((s_ora_corr - s_best_corr) / len(s_iids))

            boot_gaps.sort()
            ci_low = boot_gaps[int(0.025 * len(boot_gaps))]
            ci_high = boot_gaps[min(int(0.975 * len(boot_gaps)), len(boot_gaps) - 1)]

            lines.append(
                f"| {fam:5s} | {best_arm} ({best_acc*100:.1f}%, {best_tok:.1f} tok) | {ora_acc*100:.1f}% ({ora_corr}/{n_items}), {ora_tok:.1f} tok | {gap*100:+.1f} pp | [{ci_low*100:+.1f} pp; {ci_high*100:+.1f} pp] |"
            )
        lines.append("")

    # 2. 2x2 Contingency Table: PAL-v2 vs TOT
    lines.append("### Contingency Table: PAL-v2 vs TOT (Item-Level Agreement)")
    lines.append("| Family | n | Both Right | Only PAL-v2 Right | Only TOT Right | Neither Right | Discordant Rate |")
    lines.append("| :--- | ---: | :---: | :---: | :---: | :---: | :---: |")

    for fam in target_fams:
        items = by_fam[fam]
        n_items = len(items)

        both_right = 0
        only_pal = 0
        only_tot = 0
        neither = 0

        for iid, i_recs in items.items():
            pal_r = next((r for r in i_recs if r["arm"] == "PAL-v2"), None)
            tot_r = next((r for r in i_recs if r["arm"] == "TOT"), None)

            pal_ok = bool(pal_r and pal_r["correct"])
            tot_ok = bool(tot_r and tot_r["correct"])

            if pal_ok and tot_ok:
                both_right += 1
            elif pal_ok and not tot_ok:
                only_pal += 1
            elif not pal_ok and tot_ok:
                only_tot += 1
            else:
                neither += 1

        disc_rate = (only_pal + only_tot) / n_items * 100.0
        lines.append(
            f"| {fam:5s} | {n_items} | {both_right} ({both_right/n_items*100:.1f}%) | {only_pal} ({only_pal/n_items*100:.1f}%) | {only_tot} ({only_tot/n_items*100:.1f}%) | {neither} ({neither/n_items*100:.1f}%) | {disc_rate:.1f}% |"
        )

    out_text = "\n".join(lines)
    (AUDIT_DIR / "AF_strong_arms_oracle.txt").write_text(out_text + "\n", encoding="utf-8")
    return out_text


def run_af3(recs, tasks):
    by_arm_id = {(r["arm"], r["id"]): r for r in recs}
    order_pal_failed = [
        r for r in recs
        if r["family"] == "order" and r["arm"] == "PAL-v2" and not r["correct"]
    ]
    order_pal_failed.sort(key=lambda r: r["id"])

    lines = []
    lines.append("# AF3: Failure Analysis of 11 Failed Order PAL-v2 Items\n")
    lines.append(f"Total failed items: {len(order_pal_failed)} / 31\n")
    lines.append("| ID | Level | Gold | PAL-v2 Parsed | PAL-v2 Status | COT Result | TOT Result | Mistranslated Clue / Error Root Cause |")
    lines.append("| :--- | :---: | :---: | :---: | :--- | :---: | :---: | :--- |")

    detailed_blocks = []

    for it in order_pal_failed:
        iid = it["id"]
        task = tasks.get(iid, {})
        query = task.get("query", it.get("query", ""))
        gold = it.get("gold")
        parsed = it.get("parsed")
        exec_info = it.get("pal_exec", {})
        out = exec_info.get("output", "")
        code = it.get("raw_output", "")

        cot_r = by_arm_id.get(("COT", iid))
        tot_r = by_arm_id.get(("TOT", iid))

        cot_status = "Right" if cot_r and cot_r["correct"] else "Wrong"
        tot_status = "Right" if tot_r and tot_r["correct"] else "Wrong"

        # Diagnose the specific clue mistranslated
        # Look for offset error or contradictory logic in code
        clue_error = "Unknown"
        if not exec_info.get("ok"):
            if "no result" in out:
                status_short = "no result (contradiction)"
                clue_error = "Permutations loop yielded no match; mutually contradictory constraints coded"
            else:
                status_short = f"exec error: {out[:20]}"
                clue_error = out[:40]
        else:
            status_short = f"wrong: '{parsed}'"
            if "- dave_idx == 3" in code or "- 3" in code or "+ 3" in code or "!= 3" in code:
                clue_error = "Offset 3 used for '2 places ahead with 1 runner between' (should be offset 2)"
            elif "abs(" in code:
                clue_error = "Directional clue translated with undirected abs() or wrong distance"
            else:
                clue_error = "Condition logic returned premature True or incorrect index comparison"

        lines.append(
            f"| `{iid}` | {it.get('level')} | `{gold}` | `{parsed}` | {status_short} | {cot_status} | {tot_status} | {clue_error} |"
        )

        detailed_blocks.append(f"### Item `{iid}` (Level {it.get('level')})")
        detailed_blocks.append(f"- **Query**: {query}")
        detailed_blocks.append(f"- **Gold Answer**: `{gold}` | **PAL-v2**: `{parsed}` (COT: {cot_status}, TOT: {tot_status})")
        detailed_blocks.append(f"- **Sandbox Output**: `{out}`")
        detailed_blocks.append(f"- **Generated Code Snippet**:\n```python\n{code[:800]}\n```\n")

    lines.append("\n---\n")
    lines.extend(detailed_blocks)

    out_text = "\n".join(lines)
    (AUDIT_DIR / "AF_order_palv2_failed_clues.txt").write_text(out_text + "\n", encoding="utf-8")
    return out_text


def main():
    recs, tasks = load_traces()
    af2_text = run_af2(recs)
    af3_text = run_af3(recs, tasks)
    print("=== AF2 Output ===")
    print(af2_text)
    print("\n=== AF3 Summary Table ===")
    print("\n".join(af3_text.splitlines()[:20]))


if __name__ == "__main__":
    main()
