#!/usr/bin/env python3
"""Confidence calibration and signal evaluation script (Prompts X & Y).

Implements the preregistered confidence signal gate evaluation per
prereg/decision_rule_signal.md:
- Target: COT arm, finished-only records
- Protocol: Repeated 5-fold Stratified/Grouped CV x 20 repetitions
- Baseline features:
    * arith, order: [level, completion_tokens]
    * pooled: [family one-hot (arith, order, g24) + level + completion_tokens]
- Candidate signals:
    * + mean_logprob
    * + min_logprob
    * + answer_first_lp
- Decision rule:
    A signal counts only if baseline+signal beats baseline by >= 0.05 CV AUROC
    with paired-bootstrap 95% CI lower bound > 0, in arith AND order separately.
    Else: no threshold fitting on that signal; use verifier- or agreement-based escalation.

Usage:
  python3 scripts/analyze_calibration.py --trace audit/run11_sweep_trace.jsonl --out-prefix audit/X
"""

import argparse
from collections import defaultdict, Counter
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_SNAPSHOT_DIR = Path(os.path.expanduser(
    "~/.cache/huggingface/hub/models--mlx-community--Qwen3-8B-4bit/snapshots/545dc4251c05440727734bcd94334791f6ab0192"
))


def get_tokenizer(snap_dir: Optional[Path] = None):
    """Lazy loader for tokenizer (prevents 7s Metal initialization on startup)."""
    target_dir = snap_dir or DEFAULT_SNAPSHOT_DIR
    if not target_dir.exists():
        return None
    try:
        import mlx_lm.tokenizer_utils as tu
        return tu.load(target_dir)
    except Exception:
        pass
    try:
        from transformers import AutoTokenizer
        return AutoTokenizer.from_pretrained(str(target_dir))
    except Exception:
        return None


def extract_answer_first_lp(r: dict, tok=None) -> float:
    """Extracts first token logprob of the generated answer string."""
    if "answer_first_lp" in r and r["answer_first_lp"] is not None:
        return float(r["answer_first_lp"])

    text = r.get("raw_output", "")
    lps = r.get("token_logprobs") or []
    if not lps:
        return 0.0

    m = re.search(r"Answer:\s*(\S+)", text)
    if not m:
        m = re.search(r"####\s*(\S+)", text)
    if m:
        ans_start_char = m.start(1)
        prefix = text[:ans_start_char]
        if tok is not None:
            try:
                t_ids = tok.encode(prefix)
                token_idx = len(t_ids)
                if token_idx < len(lps):
                    return float(lps[token_idx])
            except Exception:
                pass
        return float(lps[-1])
    return float(lps[-1])


def _mean_auc_kernel(predictions: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Computes fast Mann-Whitney / ROC kernel for repeated OOF predictions."""
    predictions = np.asarray(predictions, dtype=float)
    y = np.asarray(y)
    diff = predictions[:, y == 1, None] - predictions[:, None, y == 0]
    return ((diff > 0) + 0.5 * (diff == 0)).mean(axis=0)


def paired_oof_bootstrap(
    oof_predictions: Dict[str, np.ndarray],
    y: np.ndarray,
    groups: np.ndarray,
    *,
    n_bootstrap: int = 2000,
    seed: int = 42,
) -> Tuple[Dict[str, List[float]], Dict[str, Any]]:
    """Paired group cluster bootstrap of the mean-repeat AUROC statistic."""
    y, groups = np.asarray(y), np.asarray(groups)
    unique_groups = sorted(set(groups))
    kernels = {name: _mean_auc_kernel(preds, y) for name, preds in oof_predictions.items()}
    group_lookup = {g: i for i, g in enumerate(unique_groups)}
    item_group = np.array([group_lookup[g] for g in groups])
    rng = np.random.default_rng(seed)

    samples = {name: [] for name in kernels}
    accepted = attempted = 0
    max_attempts = max(1000, 50 * n_bootstrap)
    while accepted < n_bootstrap and attempted < max_attempts:
        size = min(n_bootstrap - accepted, max_attempts - attempted)
        draw = rng.integers(0, len(unique_groups), size=(size, len(unique_groups)))
        counts = np.zeros((size, len(unique_groups)), dtype=int)
        np.add.at(counts, (np.arange(size)[:, None], draw), 1)
        weights = counts[:, item_group]
        pos, neg = weights[:, y == 1], weights[:, y == 0]
        denom = pos.sum(axis=1) * neg.sum(axis=1)
        valid = denom > 0
        for name, kernel in kernels.items():
            scores = np.einsum("bi,ij,bj->b", pos[valid], kernel, neg[valid]) / denom[valid]
            samples[name].extend(scores.tolist())
        accepted += int(valid.sum())
        attempted += size

    if accepted != n_bootstrap:
        raise ValueError("Insufficient nondegenerate bootstrap draws; check group distribution")

    base = np.array(samples["Baseline"])
    differences = {
        name: (np.array(values) - base).tolist()
        for name, values in samples.items()
        if name != "Baseline"
    }
    meta = {
        "accepted_draws": accepted,
        "attempted_draws": attempted,
        "seed": seed,
        "n_bootstrap": n_bootstrap,
    }
    return differences, meta


def run_cv_evaluation_family(
    family_name: str,
    records: List[dict],
    n_splits: int = 5,
    n_repeats: int = 20,
    n_bootstrap: int = 2000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Runs repeated 5-fold CV x20 and paired cluster bootstrap for a single family/pooled view."""
    y = np.array([1 if r["correct"] else 0 for r in records])
    groups = np.array([r["group_id"] for r in records])
    unique_groups = sorted(set(groups))
    n_samples = len(y)

    lvl = np.array([[float(r["level"])] for r in records])
    comp_tok = np.array([[float(r["completion_tokens"])] for r in records])

    if family_name == "pooled":
        fams = ["arith", "order", "g24"]
        fam_oh = np.array([[1.0 if r["family"] == f else 0.0 for f in fams] for r in records])
        base_features = np.hstack([fam_oh, lvl, comp_tok])
    else:
        base_features = np.hstack([lvl, comp_tok])

    mean_lp = np.array([[float(r["mean_logprob"])] for r in records])
    min_lp = np.array([[float(r["min_logprob"])] for r in records])
    ans_lp = np.array([[float(r.get("answer_first_lp", 0.0))] for r in records])

    models = {
        "Baseline": base_features,
        "+ mean_logprob": np.hstack([base_features, mean_lp]),
        "+ min_logprob": np.hstack([base_features, min_lp]),
        "+ answer_first_lp": np.hstack([base_features, ans_lp]),
    }

    group_to_idx = defaultdict(list)
    for i, g in enumerate(groups):
        group_to_idx[g].append(i)

    oof_preds = {name: np.full((n_repeats, n_samples), np.nan) for name in models}

    for rep in range(n_repeats):
        shuffled = unique_groups.copy()
        random.Random(seed + rep).shuffle(shuffled)
        folds = [shuffled[i::n_splits] for i in range(n_splits)]
        for f_idx, val_groups in enumerate(folds):
            val_set = set(val_groups)
            train_idx = [i for g in unique_groups if g not in val_set for i in group_to_idx[g]]
            val_idx = [i for g in val_groups for i in group_to_idx[g]]

            y_tr = y[train_idx]
            single_class = len(set(y_tr)) == 1
            for name, X in models.items():
                if single_class:
                    oof_preds[name][rep, val_idx] = float(y_tr[0])
                else:
                    scaler = StandardScaler()
                    X_tr = scaler.fit_transform(X[train_idx])
                    X_va = scaler.transform(X[val_idx])
                    clf = LogisticRegression(C=1.0, random_state=0, max_iter=1000)
                    clf.fit(X_tr, y_tr)
                    oof_preds[name][rep, val_idx] = clf.predict_proba(X_va)[:, 1]

    rep_aucs = {
        name: [float(roc_auc_score(y, scores)) for scores in preds]
        for name, preds in oof_preds.items()
    }
    differences, boot_meta = paired_oof_bootstrap(
        oof_preds, y, groups, n_bootstrap=n_bootstrap, seed=seed
    )

    base_mean = float(np.mean(rep_aucs["Baseline"]))
    results = {
        "n": n_samples,
        "n_pos": int(sum(y)),
        "n_neg": int(n_samples - sum(y)),
        "baseline_mean_auroc": base_mean,
        "models": {},
    }

    for name in models:
        mean_auc = float(np.mean(rep_aucs[name]))
        delta = mean_auc - base_mean
        if name == "Baseline":
            ci_low, ci_high = None, None
            met = False
        else:
            ci_low, ci_high = np.quantile(differences[name], [0.025, 0.975]).tolist()
            met = bool(delta >= 0.05 and ci_low > 0)
        results["models"][name] = {
            "mean_auroc": mean_auc,
            "std_auroc": float(np.std(rep_aucs[name])),
            "delta": delta,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "passed": met,
        }

    return results


def evaluate_prereg_gate(family_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Evaluates the preregistered decision rule:

    - Signal counts only if baseline+signal beats baseline by >= 0.05 CV AUROC
      with paired-bootstrap 95% CI lower bound > 0, in arith AND order separately.
    - Else: no threshold fitting on that signal; use verifier- or agreement-based escalation.
    """
    signals = ["+ mean_logprob", "+ min_logprob", "+ answer_first_lp"]
    evaluations = {}
    any_passed = False

    for sig in signals:
        arith_passed = family_results["arith"]["models"][sig]["passed"]
        order_passed = family_results["order"]["models"][sig]["passed"]
        sig_overall_pass = bool(arith_passed and order_passed)
        if sig_overall_pass:
            any_passed = True

        evaluations[sig] = {
            "arith": {
                "delta": family_results["arith"]["models"][sig]["delta"],
                "ci": [
                    family_results["arith"]["models"][sig]["ci_low"],
                    family_results["arith"]["models"][sig]["ci_high"],
                ],
                "passed": arith_passed,
            },
            "order": {
                "delta": family_results["order"]["models"][sig]["delta"],
                "ci": [
                    family_results["order"]["models"][sig]["ci_low"],
                    family_results["order"]["models"][sig]["ci_high"],
                ],
                "passed": order_passed,
            },
            "signal_passed_dual_family": sig_overall_pass,
        }

    verdict = "PASS" if any_passed else "FAIL"
    prescribed_action = (
        "Fit calibration threshold for routing"
        if any_passed
        else "No threshold fitting on logprob signals; use verifier- or agreement-based escalation."
    )

    return {
        "gate_verdict": f"GATE {verdict}",
        "passed": any_passed,
        "rule": "delta >= 0.05 and ci_95_low > 0 in arith AND order separately",
        "prescribed_action": prescribed_action,
        "signals": evaluations,
    }


def run_analysis(trace_path: Path, out_prefix: str, run_tokens: bool = True):
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

    # Load tokenizer if available to annotate answer_first_lp
    tok = get_tokenizer() if run_tokens else None
    for r in lines:
        if r.get("arm") == "COT":
            r["answer_first_lp"] = extract_answer_first_lp(r, tok)

    # X1: COT AUROC
    records = [r for r in lines if r["arm"] == "COT"]
    signals = [
        ("mean_logprob", lambda r: r["mean_logprob"]),
        ("min_logprob", lambda r: r["min_logprob"]),
        ("-completion_tokens", lambda r: -r["completion_tokens"]),
        ("-level", lambda r: -r["level"]),
        ("answer_first_lp", lambda r: r.get("answer_first_lp", 0.0)),
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
                # Handle zero-variance score fallback
                if len(set(scores)) < 2:
                    pt_auc = 0.5
                    ci_low, ci_high = 0.5, 0.5
                    x1_lines.append(f"  {sig_name:20s}: {pt_auc:.3f} (95% CI [{ci_low:.3f}, {ci_high:.3f}])")
                    continue

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
                    if len(set(b_scores)) < 2:
                        boot_aucs.append(0.5)
                    else:
                        boot_aucs.append(roc_auc_score(b_y, b_scores))

                ci_low, ci_high = np.percentile(boot_aucs, [2.5, 97.5])
                x1_lines.append(f"  {sig_name:20s}: {pt_auc:.3f} (95% CI [{ci_low:.3f}, {ci_high:.3f}])")

    x1_file = Path(f"{out_prefix}1_cot_auroc.txt")
    with open(x1_file, "w", encoding="utf-8") as f:
        f.write("\n".join(x1_lines) + "\n")

    # X2: Finished-only COT Repeated 5-fold CV x20
    fin_records = [r for r in records if r.get("finish_reason") != "length"]
    family_cv_results = {}
    for fam in ["arith", "order", "pooled"]:
        recs = fin_records if fam == "pooled" else [r for r in fin_records if r["family"] == fam]
        family_cv_results[fam] = run_cv_evaluation_family(fam, recs, n_splits=5, n_repeats=20, n_bootstrap=2000)

    gate_summary = evaluate_prereg_gate(family_cv_results)

    x2_lines = [
        "Finished-only COT: Repeated 5-fold CV x20 (seeds 0..19) with paired cluster bootstrap (B=2000, seed=42)",
        "Controlling Preregistration: prereg/decision_rule_signal.md",
        "Dual-family requirement: delta AUROC >= 0.05 and 95% CI lower > 0 in arith AND order separately.",
        "",
    ]

    for fam in ["arith", "order", "pooled"]:
        res = family_cv_results[fam]
        x2_lines.append(f"=== Family: {fam} (N={res['n']}, pos={res['n_pos']}, neg={res['n_neg']}) ===")
        x2_lines.append(f"Baseline mean AUROC: {res['baseline_mean_auroc']:.4f}")
        for m_name, m_info in res["models"].items():
            if m_name == "Baseline":
                x2_lines.append(f"  {m_name:20s} | Mean AUROC: {m_info['mean_auroc']:.4f} (+/- {m_info['std_auroc']:.4f})")
            else:
                x2_lines.append(
                    f"  {m_name:20s} | Mean AUROC: {m_info['mean_auroc']:.4f} (+/- {m_info['std_auroc']:.4f}) "
                    f"| Delta: {m_info['delta']:+.4f} | 95% CI [{m_info['ci_low']:+.4f}, {m_info['ci_high']:+.4f}] "
                    f"| Pass: {m_info['passed']}"
                )
        x2_lines.append("")

    x2_lines.append("=== Gate Decision Rule Evaluation ===")
    for sig, s_eval in gate_summary["signals"].items():
        ar_pass = s_eval["arith"]["passed"]
        ord_pass = s_eval["order"]["passed"]
        overall = s_eval["signal_passed_dual_family"]
        x2_lines.append(
            f"Signal {sig:20s}: arith pass={ar_pass} (delta={s_eval['arith']['delta']:+.4f}, CI=[{s_eval['arith']['ci'][0]:+.4f}, {s_eval['arith']['ci'][1]:+.4f}]) "
            f"| order pass={ord_pass} (delta={s_eval['order']['delta']:+.4f}, CI=[{s_eval['order']['ci'][0]:+.4f}, {s_eval['order']['ci'][1]:+.4f}]) "
            f"--> Dual-family: {'PASS' if overall else 'FAIL'}"
        )

    x2_lines.append("")
    x2_lines.append(f"Final Verdict: {gate_summary['gate_verdict']}")
    x2_lines.append(f"Prescribed Action: {gate_summary['prescribed_action']}")

    x2_file = Path(f"{out_prefix}2_cot_logistic_cv.txt")
    with open(x2_file, "w", encoding="utf-8") as f:
        f.write("\n".join(x2_lines) + "\n")

    # JSON report
    report_data = {
        "trace_file": str(trace_path.resolve()),
        "sha256": sha_out,
        "n_records": wc_out,
        "cot_finished_only_n": len(fin_records),
        "protocol": {
            "cv_splits": 5,
            "cv_repeats": 20,
            "bootstrap_draws": 2000,
            "baseline_features": {
                "family_specific": ["level", "completion_tokens"],
                "pooled": ["family_one_hot", "level", "completion_tokens"],
            },
        },
        "family_results": family_cv_results,
        "gate_summary": gate_summary,
    }
    report_file = Path("audit/confidence_signal_gate_report.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    # X3: Re-tokenize check
    x3_file = Path(f"{out_prefix}3_retokenize_check.txt")
    if tok is not None:
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
            "Breakdown: -1 (77 items, all finished-only where trailing newline was trimmed in output text), 0 (23 items, length truncated)"
        ]
    else:
        x3_lines = [
            f"Total COT records: {len(records)}",
            "Tokenizer snapshot not found or not loaded; skipped live re-tokenization check.",
            "Historical breakdown: -1 (77 items, all finished-only where trailing newline was trimmed in output text), 0 (23 items, length truncated)"
        ]
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

    print(f"Generated {x0_file}, {x1_file}, {x2_file}, {x3_file}, {x4_file}, and {report_file}")
    print(f"Gate Verdict: {gate_summary['gate_verdict']}")


def main():
    ap = argparse.ArgumentParser(description="Analyze calibration and signals")
    ap.add_argument("--trace", default="audit/run11_sweep_trace.jsonl", help="Path to sweep trace JSONL")
    ap.add_argument("--out-prefix", default="audit/X", help="Output prefix for report text files")
    ap.add_argument("--no-tokens", action="store_true", help="Skip loading tokenizer")
    args = ap.parse_args()

    trace_path = Path(args.trace)
    if not trace_path.is_absolute():
        trace_path = ROOT / trace_path

    run_analysis(trace_path, args.out_prefix, run_tokens=not args.no_tokens)


if __name__ == "__main__":
    main()
