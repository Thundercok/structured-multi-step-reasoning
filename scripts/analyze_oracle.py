#!/usr/bin/env python3
"""Oracle and per-arm comparative analysis with cluster-bootstrapped CIs (Prompt R2).

Usage:
  python3 scripts/analyze_oracle.py --input audit/sweep_trace.jsonl
  python3 scripts/analyze_oracle.py --test-synthetic
"""

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def analyze_trace(records: list[dict], n_bootstrap: int = 1000, seed: int = 42, _is_sub: bool = False) -> dict:
    if not records:
        raise ValueError("No records to analyze")

    # Map by item_id -> list of records across arms
    by_item = defaultdict(list)
    arms_set = set()
    for r in records:
        item_id = r["id"]
        by_item[item_id].append(r)
        arms_set.add(r["arm"])

    all_arms = sorted(list(arms_set))
    unique_items = list(by_item.keys())
    n_items = len(unique_items)

    # 1. Per-arm descriptive statistics
    arm_stats = {}
    for arm in all_arms:
        arm_recs = [r for r in records if r["arm"] == arm]
        n_arm = len(arm_recs)
        if n_arm == 0:
            continue
        corr = sum(1 for r in arm_recs if r["correct"])
        acc = corr / n_arm
        p_toks = sum(r.get("prompt_tokens", 0) for r in arm_recs) / n_arm
        c_toks = sum(r.get("completion_tokens", 0) for r in arm_recs) / n_arm
        tot_toks = p_toks + c_toks
        # Length rate:
        len_cnt = sum(1 for r in arm_recs if r.get("finish_reason") == "length")
        pct_length = (len_cnt / n_arm) if n_arm > 0 else 0.0

        # Finished-only parse-fail:
        fin_recs = [r for r in arm_recs if r.get("finish_reason") != "length"]
        n_fin = len(fin_recs)
        parse_fail_cnt = sum(
            1 for r in fin_recs if not str(r.get("parsed", "")).strip() or r.get("parse_status") in ("fail", "pal_fail")
        )
        pct_parse_fail_fin = (parse_fail_cnt / n_fin) if n_fin > 0 else 0.0

        arm_stats[arm] = {
            "n": n_arm,
            "correct": corr,
            "accuracy": acc,
            "pct_length": pct_length,
            "pct_parse_fail_finished": pct_parse_fail_fin,
            "n_finished": n_fin,
            "mean_prompt_tokens": p_toks,
            "mean_completion_tokens": c_toks,
            "mean_total_tokens": tot_toks,
        }

    # Best-single arm (highest accuracy; tie break by lowest total tokens)
    best_single_arm = max(
        arm_stats.keys(),
        key=lambda a: (arm_stats[a]["accuracy"], -arm_stats[a]["mean_total_tokens"]),
    )
    best_single_acc = arm_stats[best_single_arm]["accuracy"]
    best_single_tokens = arm_stats[best_single_arm]["mean_total_tokens"]

    # 2. Oracle (cheapest correct arm per item)
    oracle_correct_cnt = 0
    oracle_total_tokens = 0

    for item_id, item_recs in by_item.items():
        correct_recs = [r for r in item_recs if r["correct"]]
        if correct_recs:
            # Choose correct arm with minimum total tokens
            best_rec = min(
                correct_recs,
                key=lambda r: (r.get("prompt_tokens", 0) + r.get("completion_tokens", 0)),
            )
            oracle_correct_cnt += 1
            oracle_total_tokens += best_rec.get("prompt_tokens", 0) + best_rec.get("completion_tokens", 0)
        else:
            # No arm correct: choose cheapest overall arm
            best_rec = min(
                item_recs,
                key=lambda r: (r.get("prompt_tokens", 0) + r.get("completion_tokens", 0)),
            )
            oracle_total_tokens += best_rec.get("prompt_tokens", 0) + best_rec.get("completion_tokens", 0)

    oracle_acc = oracle_correct_cnt / n_items
    oracle_mean_tokens = oracle_total_tokens / n_items
    gap = oracle_acc - best_single_acc

    # 3. Cluster bootstrap by group_id
    groups = defaultdict(list)
    for item_id in unique_items:
        # group_id from first record
        gid = by_item[item_id][0].get("group_id", item_id)
        groups[gid].append(item_id)

    unique_gids = list(groups.keys())
    rng = random.Random(seed)

    boot_oracle_accs = []
    boot_best_accs = []
    boot_gaps = []

    for _ in range(n_bootstrap):
        sampled_gids = rng.choices(unique_gids, k=len(unique_gids))
        sampled_item_ids = [iid for gid in sampled_gids for iid in groups[gid]]
        s_n_items = len(sampled_item_ids)
        if s_n_items == 0:
            continue

        s_oracle_corr = 0
        s_best_single_corr = 0

        for iid in sampled_item_ids:
            recs = by_item[iid]
            # Oracle
            c_recs = [r for r in recs if r["correct"]]
            if c_recs:
                s_oracle_corr += 1
            # Best single arm
            b_recs = [r for r in recs if r["arm"] == best_single_arm]
            if b_recs and b_recs[0]["correct"]:
                s_best_single_corr += 1

        b_ora = s_oracle_corr / s_n_items
        b_bst = s_best_single_corr / s_n_items
        boot_oracle_accs.append(b_ora)
        boot_best_accs.append(b_bst)
        boot_gaps.append(b_ora - b_bst)

    boot_oracle_accs.sort()
    boot_best_accs.sort()
    boot_gaps.sort()

    def ci(arr):
        if not arr:
            return (0.0, 0.0)
        lo_idx = int(0.025 * len(arr))
        hi_idx = min(int(0.975 * len(arr)), len(arr) - 1)
        return (arr[lo_idx], arr[hi_idx])

    family_results = {}
    arm_x_family = {}
    if not _is_sub:
        families = sorted(list(set(r.get("family", "") for r in records if r.get("family"))))
        for fam in families:
            fam_recs = [r for r in records if r.get("family") == fam]
            if fam_recs:
                family_results[fam] = analyze_trace(fam_recs, n_bootstrap=n_bootstrap, seed=seed, _is_sub=True)

        for arm in all_arms:
            arm_x_family[arm] = {}
            for fam in families:
                sub = [r for r in records if r["arm"] == arm and r.get("family") == fam]
                if not sub:
                    continue
                n_sub = len(sub)
                c_sub = sum(1 for r in sub if r["correct"])
                p_sub = sum(r.get("prompt_tokens", 0) for r in sub) / n_sub
                cm_sub = sum(r.get("completion_tokens", 0) for r in sub) / n_sub
                l_sub = sum(1 for r in sub if r.get("finish_reason") == "length")
                fin_sub = [r for r in sub if r.get("finish_reason") != "length"]
                n_fin_sub = len(fin_sub)
                pf_sub = sum(
                    1 for r in fin_sub if not str(r.get("parsed", "")).strip() or r.get("parse_status") in ("fail", "pal_fail")
                )
                arm_x_family[arm][fam] = {
                    "n": n_sub,
                    "accuracy": c_sub / n_sub,
                    "pct_length": l_sub / n_sub,
                    "pct_parse_fail_finished": (pf_sub / n_fin_sub) if n_fin_sub > 0 else 0.0,
                    "mean_prompt_tokens": p_sub,
                    "mean_completion_tokens": cm_sub,
                    "mean_total_tokens": p_sub + cm_sub,
                }

    out = {
        "n_items": n_items,
        "arms": arm_stats,
        "best_single": {
            "arm": best_single_arm,
            "accuracy": best_single_acc,
            "mean_total_tokens": best_single_tokens,
            "ci_95": ci(boot_best_accs),
        },
        "oracle": {
            "accuracy": oracle_acc,
            "mean_total_tokens": oracle_mean_tokens,
            "ci_95": ci(boot_oracle_accs),
        },
        "gap": {
            "gap": gap,
            "ci_95": ci(boot_gaps),
        },
    }
    if family_results:
        out["families"] = family_results
    if arm_x_family:
        out["arm_x_family"] = arm_x_family
    return out


def synthetic_oracle_test(n_items: int = 2000, p: float = 0.5, seed: int = 42) -> dict:
    rng = random.Random(seed)
    arms = ["arm1", "arm2", "arm3", "arm4", "arm5", "arm6"]
    records = []

    for i in range(n_items):
        item_id = f"item_{i:04d}"
        group_id = f"grp_{i // 2:04d}"
        for arm_idx, arm in enumerate(arms):
            correct = rng.random() < p
            records.append({
                "id": item_id,
                "group_id": group_id,
                "family": "synthetic",
                "arm": arm,
                "correct": correct,
                "prompt_tokens": 20,
                "completion_tokens": (arm_idx + 1) * 20,
            })

    res = analyze_trace(records, n_bootstrap=200, seed=seed)
    ora_acc = res["oracle"]["accuracy"]
    best_acc = res["best_single"]["accuracy"]
    gap = res["gap"]["gap"]

    # Theoretical: 1 - (1 - 0.5)^6 = 98.44%
    assert 0.97 <= ora_acc <= 0.995, f"Expected oracle ~98%, got {ora_acc:.3%}"
    assert 0.47 <= best_acc <= 0.54, f"Expected best-single ~50%, got {best_acc:.3%}"
    assert 0.45 <= gap <= 0.52, f"Expected gap ~48%, got {gap:.3%}"
    return res


def print_report(res: dict):
    if res.get("arm_x_family"):
        print("=== ARM x FAMILY BREAKDOWN ===")
        print("| arm | family | n | acc | %length | %parse-fail(finished) | mean prompt+compl tok |")
        print("| :--- | :--- | :---: | :---: | :---: | :---: | :---: |")
        for arm, fams in res["arm_x_family"].items():
            for fam, s in fams.items():
                print(
                    f"| {arm} | {fam} | {s['n']} | {s['accuracy']:.1%} | {s['pct_length']:.1%} | "
                    f"{s['pct_parse_fail_finished']:.1%} | {s['mean_total_tokens']:.1f} |"
                )
        print()

    print("=== PER-ARM COMPARISON TABLE (POOLED) ===")
    print("| arm | n | acc | %length | %parse-fail(finished) | mean prompt tok | mean compl tok | total tok |")
    print("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    for arm, s in res["arms"].items():
        print(
            f"| {arm} | {s['n']} | {s['accuracy']:.1%} | {s['pct_length']:.1%} | {s['pct_parse_fail_finished']:.1%} | "
            f"{s['mean_prompt_tokens']:.1f} | {s['mean_completion_tokens']:.1f} | {s['mean_total_tokens']:.1f} |"
        )
    print()

    b = res["best_single"]
    o = res["oracle"]
    g = res["gap"]

    print("=== ORACLE & ROUTER HEADROOM (POOLED) ===")
    print(f"Best single arm: {b['arm']} (acc = {b['accuracy']:.1%}, 95% CI: [{b['ci_95'][0]:.1%}, {b['ci_95'][1]:.1%}], tokens = {b['mean_total_tokens']:.1f})")
    print(f"Oracle (cheapest correct): acc = {o['accuracy']:.1%}, 95% CI: [{o['ci_95'][0]:.1%}, {o['ci_95'][1]:.1%}], tokens = {o['mean_total_tokens']:.1f}")
    print(f"Oracle Gap: +{g['gap']:.1%} (95% CI: [{g['ci_95'][0]:.1%}, {g['ci_95'][1]:.1%}])")

    if res.get("families"):
        print("\n=== PER-FAMILY HEADROOM & 95% CI ===")
        for fam, f_res in res["families"].items():
            fb = f_res["best_single"]
            fo = f_res["oracle"]
            fg = f_res["gap"]
            print(f"- {fam.upper()} (n={f_res['n_items']}):")
            print(f"  Best single: {fb['arm']} ({fb['accuracy']:.1%}, 95% CI: [{fb['ci_95'][0]:.1%}, {fb['ci_95'][1]:.1%}], tok={fb['mean_total_tokens']:.1f})")
            print(f"  Oracle: {fo['accuracy']:.1%}, 95% CI: [{fo['ci_95'][0]:.1%}, {fo['ci_95'][1]:.1%}], tok={fo['mean_total_tokens']:.1f}")
            print(f"  Oracle Gap: +{fg['gap']:.1%}, 95% CI: [{fg['ci_95'][0]:.1%}, {fg['ci_95'][1]:.1%}]")

    print("\n=== VERDICT VS PREREG/DECISION_RULE_ORACLE.MD ===")
    gap_val = g["gap"]
    ci_lo = g["ci_95"][0]
    pass_pooled = (gap_val >= 0.10) and (ci_lo >= 0.05)
    print(f"Prereg threshold: gap >= 10.0pp and CI lower bound >= 5.0pp")
    print(f"Observed pooled: gap = {gap_val*100:.1f}pp, CI lower bound = {ci_lo*100:.1f}pp")
    if pass_pooled:
        print("Verdict: GO to fit/calibration.")
    else:
        print("Verdict: NO-GO (fix arms/knobs; no threshold fitting).")




def main():
    ap = argparse.ArgumentParser(description="Analyze oracle and per-arm comparative performance")
    ap.add_argument("--input", default=None, help="Input jsonl trace file")
    ap.add_argument("--bootstrap", type=int, default=1000, help="Number of bootstrap iterations")
    ap.add_argument("--test-synthetic", action="store_true", help="Run validation test on synthetic 6-arm data")
    args = ap.parse_args()

    if args.test_synthetic:
        print("Running synthetic test (6 arms, p=0.5, N=2000)...")
        res = synthetic_oracle_test()
        print_report(res)
        print("\nSynthetic test PASSED successfully!")
        return

    if not args.input:
        print("Error: --input required unless running --test-synthetic")
        sys.exit(1)

    in_path = Path(args.input)
    if not in_path.is_absolute():
        in_path = ROOT / in_path

    records = [json.loads(line) for line in open(in_path, encoding="utf-8") if line.strip()]
    res = analyze_trace(records, n_bootstrap=args.bootstrap)
    print_report(res)


if __name__ == "__main__":
    main()
