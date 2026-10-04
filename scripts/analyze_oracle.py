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
        arm_stats[arm] = {
            "n": n_arm,
            "correct": corr,
            "accuracy": acc,
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
    if not _is_sub:
        families = sorted(list(set(r.get("family", "") for r in records if r.get("family"))))
        for fam in families:
            fam_recs = [r for r in records if r.get("family") == fam]
            if fam_recs:
                family_results[fam] = analyze_trace(fam_recs, n_bootstrap=n_bootstrap, seed=seed, _is_sub=True)

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
    print("=== PER-ARM COMPARISON TABLE (POOLED) ===")
    print("| arm | n | acc | prompt tok | compl tok | total tok |")
    print("| --- | --- | --- | --- | --- | --- |")
    for arm, s in res["arms"].items():
        print(
            f"| {arm} | {s['n']} | {s['accuracy']:.1%} | {s['mean_prompt_tokens']:.1f} | "
            f"{s['mean_completion_tokens']:.1f} | {s['mean_total_tokens']:.1f} |"
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
        print("\n=== PER-FAMILY BREAKDOWN ===")
        for fam, f_res in res["families"].items():
            print(f"\n--- Family: {fam.upper()} (n={f_res['n_items']}) ---")
            print("| arm | n | acc | total tok |")
            print("| --- | --- | --- | --- |")
            for arm, s in f_res["arms"].items():
                print(f"| {arm} | {s['n']} | {s['accuracy']:.1%} | {s['mean_total_tokens']:.1f} |")
            fb = f_res["best_single"]
            fo = f_res["oracle"]
            fg = f_res["gap"]
            print(f"Best single: {fb['arm']} ({fb['accuracy']:.1%}, [{fb['ci_95'][0]:.1%}, {fb['ci_95'][1]:.1%}])")
            print(f"Oracle: {fo['accuracy']:.1%} ([{fo['ci_95'][0]:.1%}, {fo['ci_95'][1]:.1%}])")
            print(f"Oracle Gap: +{fg['gap']:.1%} ([{fg['ci_95'][0]:.1%}, {fg['ci_95'][1]:.1%}])")



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
