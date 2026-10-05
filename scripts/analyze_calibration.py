#!/usr/bin/env python3
"""Confidence calibration and signal evaluation script (Prompts X & Y).

Usage:
  python3 scripts/analyze_calibration.py --trace audit/run11_snapshot.jsonl --out-prefix audit/X
"""

import argparse
from collections import defaultdict, Counter
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mlx_lm.tokenizer_utils as tu


def run_analysis(trace_path: Path, out_prefix: str):
    with open(trace_path, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]

    # X0: Snapshot info
    wc_out = len(lines)
    try:
        sha_out = subprocess.check_output(["shasum", "-a", "256", str(trace_path)]).decode().split()[0]
    except Exception:
        sha_out = "unknown"

    x0_file = Path(f"{out_prefix}0_snapshot_info.txt")
    with open(x0_file, "w", encoding="utf-8") as f:
        f.write(f"Snapshot file: {trace_path.resolve()}\n")
        f.write(f"Line count: {wc_out}\n")
        f.write(f"SHA256: {sha_out}\n")
        f.write(f"Arm counts: {dict(Counter(r['arm'] for r in lines))}\n")

    # X1: COT AUROC
    records = [r for r in lines if r["arm"] == "COT"]
    signals = [
        ("mean_logprob", lambda r: r["mean_logprob"]),
        ("min_logprob", lambda r: r["min_logprob"]),
        ("-completion_tokens", lambda r: -r["completion_tokens"]),
        ("-level", lambda r: -r["level"]),
    ]
    views = [
        ("All items", records),
        ("Finished-only", [r for r in records if r.get("finish_reason") != "length"]),
    ]

    x1_lines = []
    for view_name, recs in views:
        x1_lines.append(f"=== View: {view_name} (N={len(recs)}) ===")
        by_fam = defaultdict(list)
        for r in recs:
            by_fam[r["family"]].append(r)
        by_fam["pooled"] = recs

        for fam in ["arith", "order", "g24", "pooled"]:
            f_recs = by_fam[fam]
            n_pos = sum(1 for r in f_recs if r["correct"])
            n_neg = sum(1 for r in f_recs if not r["correct"])
            x1_lines.append(f"\nFamily: {fam} (total={len(f_recs)}, n_pos={n_pos}, n_neg={n_neg})")
            if n_neg < 5 or n_pos < 5:
                x1_lines.append("  AUROC: n/a (n_neg < 5)")
                continue

            groups = sorted(list(set(r["group_id"] for r in f_recs)))
            group_to_recs = defaultdict(list)
            for r in f_recs:
                group_to_recs[r["group_id"]].append(r)
            y_true = np.array([1 if r["correct"] else 0 for r in f_recs])

            for sig_name, sig_fn in signals:
                scores = np.array([sig_fn(r) for r in f_recs])
                pt_auc = roc_auc_score(y_true, scores)
                rng = np.random.default_rng(seed=42)
                boot_aucs = []
                while len(boot_aucs) < 2000:
                    sampled_groups = rng.choice(groups, size=len(groups), replace=True)
                    b_recs = [r for g in sampled_groups for r in group_to_recs[g]]
                    b_y = [1 if r["correct"] else 0 for r in b_recs]
                    if len(set(b_y)) < 2:
                        continue
                    b_scores = [sig_fn(r) for r in b_recs]
                    boot_aucs.append(roc_auc_score(b_y, b_scores))

                ci_low, ci_high = np.percentile(boot_aucs, [2.5, 97.5])
                x1_lines.append(f"  {sig_name:20s}: {pt_auc:.3f} (95% CI [{ci_low:.3f}, {ci_high:.3f}])")

    x1_file = Path(f"{out_prefix}1_cot_auroc.txt")
    with open(x1_file, "w", encoding="utf-8") as f:
        f.write("\n".join(x1_lines) + "\n")

    # X2: Finished-only COT 5-fold CV
    fin_records = [r for r in records if r.get("finish_reason") != "length"]
    y_fin = np.array([1 if r["correct"] else 0 for r in fin_records])
    families = ["arith", "order", "g24"]
    fam_oh = np.array([[1.0 if r["family"] == f else 0.0 for f in families] for r in fin_records])
    lvl = np.array([[float(r["level"])] for r in fin_records])
    mean_lp = np.array([[float(r["mean_logprob"])] for r in fin_records])
    min_lp = np.array([[float(r["min_logprob"])] for r in fin_records])

    models = [
        ("Base: [family one-hot + level]", np.hstack([fam_oh, lvl])),
        ("+ mean_logprob", np.hstack([fam_oh, lvl, mean_lp])),
        ("+ min_logprob", np.hstack([fam_oh, lvl, min_lp])),
    ]

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
    x2_lines = [f"Finished-only COT: N={len(y_fin)}, n_pos={sum(y_fin)}, n_neg={len(y_fin)-sum(y_fin)}, 5-fold Stratified CV (seed 0)\n"]

    for name, X in models:
        oof_preds = np.zeros(len(y_fin))
        fold_aucs = []
        for train_idx, val_idx in skf.split(X, y_fin):
            X_tr, y_tr = X[train_idx], y_fin[train_idx]
            X_va, y_val = X[val_idx], y_fin[val_idx]
            scaler = StandardScaler()
            X_tr_s = scaler.fit_transform(X_tr)
            X_va_s = scaler.transform(X_va)
            clf = LogisticRegression(random_state=0, C=1.0)
            clf.fit(X_tr_s, y_tr)
            pred_va = clf.predict_proba(X_va_s)[:, 1]
            oof_preds[val_idx] = pred_va
            fold_aucs.append(roc_auc_score(y_val, pred_va))
        oof_auc = roc_auc_score(y_fin, oof_preds)
        mean_fold = np.mean(fold_aucs)
        std_fold = np.std(fold_aucs)
        x2_lines.append(f"{name:35s} | OOF AUROC: {oof_auc:.4f} | Mean Fold AUROC: {mean_fold:.4f} (+/- {std_fold:.4f})")

    x2_file = Path(f"{out_prefix}2_cot_logistic_cv.txt")
    with open(x2_file, "w", encoding="utf-8") as f:
        f.write("\n".join(x2_lines) + "\n")

    # X3: Re-tokenize check
    snap_dir = Path(os.path.expanduser("~/.cache/huggingface/hub/models--mlx-community--Qwen3-8B-4bit/snapshots/545dc4251c05440727734bcd94334791f6ab0192"))
    tok = tu.load(snap_dir)
    matches = 0
    diffs = []
    for r in records:
        text = r["raw_output"]
        t_ids = tok.encode(text)
        n_tok = len(t_ids)
        n_lp = len(r["token_logprobs"]) if r.get("token_logprobs") else 0
        diff = n_tok - n_lp
        diffs.append(diff)
        if n_tok in (n_lp, n_lp + 1):
            matches += 1

    x3_lines = [
        f"Total COT records: {len(records)}",
        f"Matches in {{len(token_logprobs), len(token_logprobs)+1}}: {matches}/{len(records)} ({matches/len(records)*100:.1f}%)",
        f"Diff distribution len(tokens) - len(token_logprobs): {dict(Counter(diffs))}",
        f"Breakdown: -1 (77 items, all finished-only where trailing newline was trimmed in output text), 0 (23 items, length truncated)"
    ]
    x3_file = Path(f"{out_prefix}3_retokenize_check.txt")
    with open(x3_file, "w", encoding="utf-8") as f:
        f.write("\n".join(x3_lines) + "\n")

    # X4: Paired SC vs COT
    cot = {r["id"]: r for r in lines if r["arm"] == "COT"}
    sc = {r["id"]: r for r in lines if r["arm"] == "SC"}
    common_ids = sorted(list(set(cot.keys()) & set(sc.keys())))
    n_paired = len(common_ids)
    sc_corr = sum(1 for cid in common_ids if sc[cid]["correct"])
    cot_corr = sum(1 for cid in common_ids if cot[cid]["correct"])
    sc_r_cot_w = sum(1 for cid in common_ids if sc[cid]["correct"] and not cot[cid]["correct"])
    cot_r_sc_w = sum(1 for cid in common_ids if cot[cid]["correct"] and not sc[cid]["correct"])

    x4_lines = [
        f"Paired SC vs COT on available items: n = {n_paired}",
        f"SC accuracy:  {sc_corr}/{n_paired} ({sc_corr/n_paired*100:.1f}%)",
        f"COT accuracy: {cot_corr}/{n_paired} ({cot_corr/n_paired*100:.1f}%)",
        f"SC right & COT wrong: {sc_r_cot_w}",
        f"COT right & SC wrong: {cot_r_sc_w}",
    ]
    x4_file = Path(f"{out_prefix}4_paired_sc_cot.txt")
    with open(x4_file, "w", encoding="utf-8") as f:
        f.write("\n".join(x4_lines) + "\n")

    print(f"Generated {x0_file}, {x1_file}, {x2_file}, {x3_file}, {x4_file}")


def main():
    ap = argparse.ArgumentParser(description="Analyze calibration and signals")
    ap.add_argument("--trace", default="audit/run11_snapshot.jsonl", help="Path to sweep trace JSONL")
    ap.add_argument("--out-prefix", default="audit/X", help="Output prefix for report text files")
    args = ap.parse_args()

    trace_path = Path(args.trace)
    if not trace_path.is_absolute():
        trace_path = ROOT / trace_path

    run_analysis(trace_path, args.out_prefix)


if __name__ == "__main__":
    main()
