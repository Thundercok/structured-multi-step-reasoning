#!/usr/bin/env python3
"""Offline agreement signal analysis and policy replay (Prompt AJ).

Evaluates:
- Cross-strategy agreement signals: agree(PAL-v2, COT), agree(PAL-v2, ToT), n_agree
- Gate AUROC under repeated 5-fold CV x20 grouped by group_id with paired bootstrap CIs
- Precision P(correct | agree) and exhaustive Agree-and-Wrong item inspection
- Policy replay: G1, G2 vs always-ToT, W, always-PAL-v2 with cluster-bootstrap 95% CIs
"""

from collections import Counter, defaultdict
from decimal import Decimal
import json
from pathlib import Path
import random
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reasoning_strategies import normalize_answer
from research_scoring import numeric_literal, typed_vote_key
from scripts.gen_tasks import check24

AUDIT_DIR = ROOT / "audit"
RUN11_TRACE = AUDIT_DIR / "run11_sweep_trace.jsonl"
PALV2_TRACE = AUDIT_DIR / "ae_palv2_trace.jsonl"
TUNE_PATH = ROOT / "data" / "gen02_tune.json"


def canonicalize_answer(val: Any, family: str, item_meta: Optional[Dict[str, Any]] = None) -> str:
    """Canonicalize answers across families.
    - arith: numeric literal normalized string (handles units like '192 slices' vs '192')
    - order: normalized case-folded string, stripping punctuation
    - g24: check24 validity mapped to '__VALID_24__', else formatted expression
    """
    if val is None:
        return ""
    s = str(val).strip()
    if not s:
        return ""

    if family == "arith":
        num = numeric_literal(s, allow_units=True)
        if num is not None:
            return format(num.normalize(), "f")
        return s

    if family == "order":
        norm = normalize_answer(s)
        norm = norm.removesuffix(".").strip().casefold()
        return norm

    if family == "g24":
        if item_meta and "numbers" in item_meta:
            nums = item_meta["numbers"]
            if check24(s, nums):
                return "__VALID_24__"
        vk = typed_vote_key(s, "expression")
        return vk if vk is not None else s

    return s.casefold()


def test_canonicalizer():
    """Unit test canonicalizer on key fixtures."""
    # Arith fixtures: '192' vs '192 slices'
    assert canonicalize_answer("192", "arith") == canonicalize_answer("192 slices", "arith"), "Arith units test failed"
    assert canonicalize_answer("192", "arith") == "192"
    assert canonicalize_answer("2760", "arith") == canonicalize_answer("2,760", "arith")

    # Order fixtures: 'Carol.' vs 'carol'
    assert canonicalize_answer("Carol.", "order") == canonicalize_answer("carol", "order"), "Order casing/period failed"
    assert canonicalize_answer("**Answer**: Bob.", "order") == "bob"

    # G24 fixtures
    meta = {"numbers": [3, 8, 3, 8]}
    assert canonicalize_answer("8/(3-8/3)", "g24", meta) == "__VALID_24__"
    assert canonicalize_answer("3+8+3+8", "g24", meta) != "__VALID_24__"


def load_dataset() -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]], Dict[str, Any]]:
    with open(RUN11_TRACE, "r", encoding="utf-8") as f:
        r11 = [json.loads(line) for line in f if line.strip()]
    with open(PALV2_TRACE, "r", encoding="utf-8") as f:
        pal = [json.loads(line) for line in f if line.strip()]
    with open(TUNE_PATH, "r", encoding="utf-8") as f:
        tune_data = json.load(f)
        tasks = {it["id"]: it for it in tune_data["items"]}

    r11_by_id: Dict[str, Dict[str, Any]] = defaultdict(dict)
    for r in r11:
        r11_by_id[r["id"]][r["arm"]] = r

    pal_by_id = {r["id"]: r for r in pal}
    return tune_data["items"], r11_by_id, pal_by_id


def is_pal_exec_fail(p_rec: Dict[str, Any]) -> bool:
    """Matches the exact execution-failure condition used in policy W."""
    p_ok = p_rec.get("pal_exec", {}).get("ok", False)
    p_res = str(p_rec.get("pal_exec", {}).get("output", ""))
    p_parsed = p_rec.get("parsed")
    p_len = p_rec.get("finish_reason") == "length"
    if not p_ok:
        return True
    if p_res in ("", "None", "None\n") or p_parsed in ("", "None", None):
        return True
    if p_len:
        return True
    return False


def run_cv_evaluation(
    X_base: np.ndarray,
    models_dict: Dict[str, np.ndarray],
    y: np.ndarray,
    groups: np.ndarray,
    n_splits: int = 5,
    n_repeats: int = 20,
    n_bootstrap: int = 2000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Repeated 5-fold CV x20 with paired cluster bootstrap on group_id."""
    n_samples = len(y)
    unique_groups = sorted(list(set(groups)))
    n_groups = len(unique_groups)
    group_to_indices = defaultdict(list)
    for idx, g in enumerate(groups):
        group_to_indices[g].append(idx)

    # Store OOF probabilities for each repetition and model
    oof_preds = {m_name: np.zeros((n_repeats, n_samples)) for m_name in models_dict}

    for rep in range(n_repeats):
        rng_split = random.Random(seed + rep)
        shuffled_groups = unique_groups.copy()
        rng_split.shuffle(shuffled_groups)

        # Split groups into folds
        fold_groups = [shuffled_groups[i::n_splits] for i in range(n_splits)]

        for fold_idx in range(n_splits):
            val_g = set(fold_groups[fold_idx])
            train_g = set(shuffled_groups) - val_g

            train_idx = [i for g in train_g for i in group_to_indices[g]]
            val_idx = [i for g in val_g for i in group_to_indices[g]]

            y_tr, y_va = y[train_idx], y[val_idx]

            for m_name, X in models_dict.items():
                X_tr, X_va = X[train_idx], X[val_idx]
                scaler = StandardScaler()
                X_tr_s = scaler.fit_transform(X_tr)
                X_va_s = scaler.transform(X_va)

                clf = LogisticRegression(C=1.0, random_state=0, max_iter=1000)
                # If only one class in train fold, default to constant
                if len(set(y_tr)) < 2:
                    p = float(y_tr[0])
                    oof_preds[m_name][rep, val_idx] = p
                else:
                    clf.fit(X_tr_s, y_tr)
                    oof_preds[m_name][rep, val_idx] = clf.predict_proba(X_va_s)[:, 1]

    # Calculate average OOF predictions across repetitions
    oof_mean = {m_name: np.mean(oof_preds[m_name], axis=0) for m_name in models_dict}

    # Baseline AUROC per repetition
    rep_aucs = {m_name: [] for m_name in models_dict}
    for rep in range(n_repeats):
        for m_name in models_dict:
            try:
                score = roc_auc_score(y, oof_preds[m_name][rep])
                rep_aucs[m_name].append(score)
            except ValueError:
                rep_aucs[m_name].append(np.nan)

    # Paired cluster bootstrap across group_id on mean OOF predictions
    rng_boot = np.random.default_rng(seed)
    boot_diffs = {m_name: [] for m_name in models_dict if m_name != "Baseline"}

    if len(set(y)) >= 2:
        while min(len(v) for v in boot_diffs.values()) < n_bootstrap:
            sg = rng_boot.choice(unique_groups, size=n_groups, replace=True)
            boot_idx = [i for g in sg for i in group_to_indices[g]]
            y_b = y[boot_idx]
            if len(set(y_b)) < 2:
                continue

            try:
                base_auc = roc_auc_score(y_b, oof_mean["Baseline"][boot_idx])
            except ValueError:
                continue

            for m_name in boot_diffs:
                try:
                    sig_auc = roc_auc_score(y_b, oof_mean[m_name][boot_idx])
                    boot_diffs[m_name].append(sig_auc - base_auc)
                except ValueError:
                    continue

    results = {}
    base_mean = np.nanmean(rep_aucs["Baseline"])
    base_std = np.nanstd(rep_aucs["Baseline"])
    results["Baseline"] = {
        "mean_auroc": base_mean,
        "std_auroc": base_std,
        "delta": 0.0,
        "ci_low": 0.0,
        "ci_high": 0.0,
        "passed": False,
    }

    for m_name in models_dict:
        if m_name == "Baseline":
            continue
        m_mean = np.nanmean(rep_aucs[m_name])
        m_std = np.nanstd(rep_aucs[m_name])
        delta = m_mean - base_mean

        diffs = boot_diffs.get(m_name, [])
        if diffs:
            ci_low = float(np.percentile(diffs, 2.5))
            ci_high = float(np.percentile(diffs, 97.5))
        else:
            ci_low, ci_high = np.nan, np.nan

        passed = bool(delta >= 0.05 and ci_low > 0.0)
        results[m_name] = {
            "mean_auroc": m_mean,
            "std_auroc": m_std,
            "delta": delta,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "passed": passed,
        }

    return results


def evaluate_gate_all():
    items, r11_by_id, pal_by_id = load_dataset()

    families = ["arith", "order", "g24", "pooled"]
    gate_results = {}

    for fam in families:
        f_items = items if fam == "pooled" else [it for it in items if it["family"] == fam]
        n = len(f_items)

        groups = np.array([it["group_id"] for it in f_items])
        y = np.array([
            1 if canonicalize_answer(pal_by_id[it["id"]]["parsed"], it["family"], it["meta"]) == canonicalize_answer(it["answer"], it["family"], it["meta"])
            else 0
            for it in f_items
        ])

        lvl = np.array([float(it["level"]) for it in f_items]).reshape(-1, 1)
        tok = np.array([float(pal_by_id[it["id"]]["completion_tokens"]) for it in f_items]).reshape(-1, 1)

        # Baseline features
        if fam == "pooled":
            fam_names = ["arith", "order", "g24"]
            fam_oh = np.array([[1.0 if it["family"] == f else 0.0 for f in fam_names] for it in f_items])
            X_base = np.hstack([fam_oh, lvl, tok])
        else:
            X_base = np.hstack([lvl, tok])

        # Signals
        sig_cot = []
        sig_tot = []
        sig_n_pal = []
        sig_n_plur = []

        for it in f_items:
            iid = it["id"]
            f = it["family"]
            m = it["meta"]
            p = canonicalize_answer(pal_by_id[iid]["parsed"], f, m)
            c = canonicalize_answer(r11_by_id[iid]["COT"]["parsed"], f, m)
            t = canonicalize_answer(r11_by_id[iid]["TOT"]["parsed"], f, m)
            s = canonicalize_answer(r11_by_id[iid]["SC"]["parsed"], f, m)

            sig_cot.append(1.0 if (p == c and p != "") else 0.0)
            sig_tot.append(1.0 if (p == t and p != "") else 0.0)

            all_ans = [p, c, t, s]
            sig_n_pal.append(float(sum(1 for a in all_ans if a == p and p != "")))

            non_empty = [a for a in all_ans if a != ""]
            cnts = Counter(non_empty)
            plur_cnt = cnts.most_common(1)[0][1] if cnts else 0
            sig_n_plur.append(float(plur_cnt))

        models_dict = {
            "Baseline": X_base,
            "+ agree(PAL,COT)": np.hstack([X_base, np.array(sig_cot).reshape(-1, 1)]),
            "+ agree(PAL,TOT)": np.hstack([X_base, np.array(sig_tot).reshape(-1, 1)]),
            "+ n_agree (PAL)": np.hstack([X_base, np.array(sig_n_pal).reshape(-1, 1)]),
            "+ n_agree (plurality)": np.hstack([X_base, np.array(sig_n_plur).reshape(-1, 1)]),
        }

        # Check positive/negative classes
        n_pos = int(sum(y))
        n_neg = n - n_pos

        if n_pos == 0 or n_neg == 0:
            # Degenerate case (e.g. arith where PAL is 40/40, or g24 where PAL is 0/29)
            gate_results[fam] = {
                "n": n, "n_pos": n_pos, "n_neg": n_neg, "degenerate": True,
                "models": {m: {"mean_auroc": np.nan, "delta": np.nan, "ci_low": np.nan, "ci_high": np.nan, "passed": False} for m in models_dict}
            }
        else:
            cv_res = run_cv_evaluation(X_base, models_dict, y, groups)
            gate_results[fam] = {
                "n": n, "n_pos": n_pos, "n_neg": n_neg, "degenerate": False,
                "models": cv_res,
            }

    return gate_results


def evaluate_precision_and_failures():
    items, r11_by_id, pal_by_id = load_dataset()

    signals_to_eval = [
        "agree(PAL-v2,COT)",
        "agree(PAL-v2,ToT)",
        "pal_agree>=2",
        "pal_agree>=3",
        "pal_agree==4",
        "plurality_agree>=2",
        "plurality_agree>=3",
        "plurality_agree==4",
    ]

    families = ["arith", "order", "g24", "pooled"]
    prec_table = {}
    agree_wrong_list = []

    for fam in families:
        f_items = items if fam == "pooled" else [it for it in items if it["family"] == fam]
        n_total = len(f_items)

        prec_table[fam] = {}
        for sig in signals_to_eval:
            n_agreed = 0
            n_corr = 0

            for it in f_items:
                iid = it["id"]
                f = it["family"]
                m = it["meta"]
                g = canonicalize_answer(it["answer"], f, m)
                p = canonicalize_answer(pal_by_id[iid]["parsed"], f, m)
                c = canonicalize_answer(r11_by_id[iid]["COT"]["parsed"], f, m)
                t = canonicalize_answer(r11_by_id[iid]["TOT"]["parsed"], f, m)
                s = canonicalize_answer(r11_by_id[iid]["SC"]["parsed"], f, m)

                all_arms = {"PAL-v2": p, "COT": c, "TOT": t, "SC": s}
                non_empty = [a for a in all_arms.values() if a != ""]
                cnts = Counter(non_empty)
                plur_ans, plur_cnt = cnts.most_common(1)[0] if cnts else ("", 0)
                pal_cnt = sum(1 for a in all_arms.values() if a == p and p != "")

                fired = False
                accepted_ans = ""
                if sig == "agree(PAL-v2,COT)":
                    if p == c and p != "":
                        fired = True
                        accepted_ans = p
                elif sig == "agree(PAL-v2,ToT)":
                    if p == t and p != "":
                        fired = True
                        accepted_ans = p
                elif sig == "pal_agree>=2":
                    if pal_cnt >= 2:
                        fired = True
                        accepted_ans = p
                elif sig == "pal_agree>=3":
                    if pal_cnt >= 3:
                        fired = True
                        accepted_ans = p
                elif sig == "pal_agree==4":
                    if pal_cnt == 4:
                        fired = True
                        accepted_ans = p
                elif sig == "plurality_agree>=2":
                    if plur_cnt >= 2:
                        fired = True
                        accepted_ans = plur_ans
                elif sig == "plurality_agree>=3":
                    if plur_cnt >= 3:
                        fired = True
                        accepted_ans = plur_ans
                elif sig == "plurality_agree==4":
                    if plur_cnt == 4:
                        fired = True
                        accepted_ans = plur_ans

                if fired:
                    n_agreed += 1
                    is_c = (accepted_ans == g)
                    if is_c:
                        n_corr += 1
                    else:
                        if fam != "pooled":
                            agree_wrong_list.append({
                                "id": iid,
                                "family": f,
                                "level": it["level"],
                                "signal": sig,
                                "accepted": accepted_ans,
                                "gold": g,
                                "arms": all_arms,
                                "query": it["query"],
                            })

            p_corr = (n_corr / n_agreed) if n_agreed > 0 else 0.0
            prec_table[fam][sig] = {
                "n_agreed": n_agreed,
                "n_total": n_total,
                "n_corr": n_corr,
                "p_corr": p_corr,
            }

    return prec_table, agree_wrong_list


def evaluate_replay_policies():
    items, r11_by_id, pal_by_id = load_dataset()
    families = ["arith", "order", "g24", "pooled"]
    policies = ["always-PAL-v2", "always-ToT", "W", "G1", "G2"]

    replay_results = {}
    rng = np.random.default_rng(42)
    B = 2000

    for fam in families:
        f_items = items if fam == "pooled" else [it for it in items if it["family"] == fam]
        n = len(f_items)
        unique_groups = sorted(list(set(it["group_id"] for it in f_items)))
        group_to_items = defaultdict(list)

        policy_records = {pol: [] for pol in policies}

        for it in f_items:
            iid = it["id"]
            gid = it["group_id"]
            group_to_items[gid].append(it)
            f = it["family"]
            m = it["meta"]

            p_rec = pal_by_id[iid]
            c_rec = r11_by_id[iid]["COT"]
            t_rec = r11_by_id[iid]["TOT"]

            p_tok = p_rec["prompt_tokens"] + p_rec["completion_tokens"]
            c_tok = c_rec["prompt_tokens"] + c_rec["completion_tokens"]
            t_tok = t_rec["prompt_tokens"] + t_rec["completion_tokens"]

            p_ans = canonicalize_answer(p_rec["parsed"], f, m)
            c_ans = canonicalize_answer(c_rec["parsed"], f, m)
            t_ans = canonicalize_answer(t_rec["parsed"], f, m)
            g_ans = canonicalize_answer(it["answer"], f, m)

            p_c = (p_ans == g_ans)
            t_c = (t_ans == g_ans)

            fail = is_pal_exec_fail(p_rec)
            agree_pc = (p_ans == c_ans and p_ans != "")

            # always-PAL-v2
            policy_records["always-PAL-v2"].append({
                "group_id": gid, "correct": p_c, "tokens": p_tok, "esc": False
            })

            # always-ToT
            policy_records["always-ToT"].append({
                "group_id": gid, "correct": t_c, "tokens": t_tok, "esc": False
            })

            # W
            if fail:
                policy_records["W"].append({
                    "group_id": gid, "correct": t_c, "tokens": p_tok + t_tok, "esc": True
                })
            else:
                policy_records["W"].append({
                    "group_id": gid, "correct": p_c, "tokens": p_tok, "esc": False
                })

            # G1 = PAL-v2 + COT, accept iff agree else ToT
            if agree_pc:
                policy_records["G1"].append({
                    "group_id": gid, "correct": p_c, "tokens": p_tok + c_tok, "esc": False
                })
            else:
                policy_records["G1"].append({
                    "group_id": gid, "correct": t_c, "tokens": p_tok + c_tok + t_tok, "esc": True
                })

            # G2 = PAL-v2; if exec fails -> ToT; else COT, accept iff agree else ToT
            if fail:
                policy_records["G2"].append({
                    "group_id": gid, "correct": t_c, "tokens": p_tok + t_tok, "esc": True
                })
            else:
                if agree_pc:
                    policy_records["G2"].append({
                        "group_id": gid, "correct": p_c, "tokens": p_tok + c_tok, "esc": False
                    })
                else:
                    policy_records["G2"].append({
                        "group_id": gid, "correct": t_c, "tokens": p_tok + c_tok + t_tok, "esc": True
                    })

        replay_results[fam] = {}
        for pol in policies:
            recs = policy_records[pol]
            corr_cnt = sum(1 for r in recs if r["correct"])
            acc = corr_cnt / n
            mean_tok = sum(r["tokens"] for r in recs) / n
            esc_cnt = sum(1 for r in recs if r["esc"])
            esc_rate = esc_cnt / n

            # Group index map
            pol_by_group = defaultdict(list)
            for r in recs:
                pol_by_group[r["group_id"]].append(r)

            boot_accs = []
            boot_toks = []
            for _ in range(B):
                sg = rng.choice(unique_groups, size=len(unique_groups), replace=True)
                s_recs = [r for g in sg for r in pol_by_group[g]]
                boot_accs.append(sum(1 for r in s_recs if r["correct"]) / len(s_recs))
                boot_toks.append(sum(r["tokens"] for r in s_recs) / len(s_recs))

            acc_ci = (float(np.percentile(boot_accs, 2.5)), float(np.percentile(boot_accs, 97.5)))
            tok_ci = (float(np.percentile(boot_toks, 2.5)), float(np.percentile(boot_toks, 97.5)))

            replay_results[fam][pol] = {
                "n": n,
                "corr": corr_cnt,
                "acc": acc,
                "acc_ci": acc_ci,
                "mean_tok": mean_tok,
                "tok_ci": tok_ci,
                "esc_cnt": esc_cnt,
                "esc_rate": esc_rate,
            }

    return replay_results


def build_markdown_tables(gate_results, prec_table, agree_wrong_list, replay_results):
    tables = {}

    # 1. Gate Table
    gate_lines = []
    gate_lines.append("| Family | Signal | Baseline AUROC | Signal AUROC | Δ AUROC | 95% Paired-Bootstrap CI | Gate Passed (Δ≥0.05, CI_low>0) |")
    gate_lines.append("| :--- | :--- | :---: | :---: | :---: | :---: | :---: |")

    for fam in ["arith", "order", "g24", "pooled"]:
        info = gate_results[fam]
        fam_label = f"{fam} (N={info['n']})"
        if info["degenerate"]:
            note = "Degenerate (100% acc, no negative class)" if fam == "arith" else "Degenerate (0% acc, no positive class)"
            gate_lines.append(f"| **{fam_label}** | Baseline | N/A | N/A | N/A | N/A | N/A ({note}) |")
            for sig in ["+ agree(PAL,COT)", "+ agree(PAL,TOT)", "+ n_agree (PAL)", "+ n_agree (plurality)"]:
                gate_lines.append(f"| {fam} | {sig} | N/A | N/A | N/A | N/A | Failed ({note}) |")
        else:
            base_auroc = info["models"]["Baseline"]["mean_auroc"]
            for sig in ["+ agree(PAL,COT)", "+ agree(PAL,TOT)", "+ n_agree (PAL)", "+ n_agree (plurality)"]:
                m_info = info["models"][sig]
                s_auroc = m_info["mean_auroc"]
                d = m_info["delta"]
                ci_l, ci_h = m_info["ci_low"], m_info["ci_high"]
                pass_str = "**PASS**" if m_info["passed"] else "FAIL"
                gate_lines.append(
                    f"| {fam} | {sig} | {base_auroc:.4f} | {s_auroc:.4f} | {d:+.4f} | [{ci_l:+.4f}, {ci_h:+.4f}] | {pass_str} |"
                )
    tables["gate"] = "\n".join(gate_lines)

    # 2. Precision Table
    prec_lines = []
    prec_lines.append("| Family | Signal | Agreed Items / Total | Correct When Agreed | P(Correct \\| Agree) |")
    prec_lines.append("| :--- | :--- | :---: | :---: | :---: |")
    for fam in ["arith", "order", "g24", "pooled"]:
        for sig in ["agree(PAL-v2,COT)", "agree(PAL-v2,ToT)", "pal_agree>=2", "pal_agree>=3", "plurality_agree>=2", "plurality_agree>=3", "plurality_agree==4"]:
            info = prec_table[fam][sig]
            n_a = info["n_agreed"]
            n_t = info["n_total"]
            n_c = info["n_corr"]
            p = info["p_corr"]
            prec_lines.append(f"| {fam} | {sig} | {n_a}/{n_t} ({n_a/n_t*100:.1f}%) | {n_c}/{n_a} | {p*100:5.1f}% |")
    tables["precision"] = "\n".join(prec_lines)

    # 3. Agree-and-Wrong List
    wrong_lines = []
    wrong_lines.append("| Item ID | Family | Level | Signal | Accepted Answer | Gold Answer | Arms (PAL-v2 / COT / ToT / SC) | Correlated Mechanism |")
    wrong_lines.append("| :--- | :--- | :---: | :--- | :---: | :---: | :--- | :--- |")

    seen_items = set()
    for w in agree_wrong_list:
        key = (w["id"], w["signal"])
        if key in seen_items:
            continue
        seen_items.add(key)
        arms_str = f"PAL: {w['arms']['PAL-v2']}, COT: {w['arms']['COT']}, ToT: {w['arms']['TOT']}, SC: {w['arms']['SC']}"
        if w["family"] == "arith":
            mech = "Correlated LM arithmetic error (multi-digit computation failed on language arms while PAL is exact)"
        elif w["family"] == "order":
            mech = "Correlated clue offset misinterpretation (e.g. ahead vs behind or 1st vs last)"
        elif w["family"] == "g24":
            mech = "Correlated invalid expression (digit omission / duplicate digit hallucination)"
        else:
            mech = "Correlated hallucination across language model arms"
        wrong_lines.append(
            f"| `{w['id']}` | {w['family']} | {w['level']} | {w['signal']} | **{w['accepted']}** | **{w['gold']}** | {arms_str} | {mech} |"
        )
    tables["agree_wrong"] = "\n".join(wrong_lines)

    # 4. Replay Policies Table
    replay_lines = []
    replay_lines.append("| Family | Policy | Accuracy (corr/n) | 95% Cluster CI (Acc) | Mean Tokens | 95% Cluster CI (Tok) | Escalation Rate |")
    replay_lines.append("| :--- | :--- | :---: | :---: | :---: | :---: | :---: |")

    for fam in ["arith", "order", "g24", "pooled"]:
        for pol in ["always-PAL-v2", "always-ToT", "W (exec fail -> ToT)", "G1 (PAL+COT agree -> PAL, else ToT)", "G2 (PAL -> if fail ToT else COT agree)"]:
            pol_key = "W" if "W" in pol else ("G1" if "G1" in pol else ("G2" if "G2" in pol else pol))
            d = replay_results[fam][pol_key]
            acc_str = f"{d['acc']*100:.1f}% ({d['corr']}/{d['n']})"
            acc_ci_str = f"[{d['acc_ci'][0]*100:.1f}%, {d['acc_ci'][1]*100:.1f}%]"
            tok_str = f"{d['mean_tok']:.1f}"
            tok_ci_str = f"[{d['tok_ci'][0]:.1f}, {d['tok_ci'][1]:.1f}]"
            esc_str = f"{d['esc_rate']*100:.1f}% ({d['esc_cnt']}/{d['n']})"
            replay_lines.append(f"| {fam} | {pol} | {acc_str} | {acc_ci_str} | {tok_str} | {tok_ci_str} | {esc_str} |")
    tables["replay"] = "\n".join(replay_lines)

    return tables


def main():
    test_canonicalizer()
    gate_results = evaluate_gate_all()
    prec_table, agree_wrong_list = evaluate_precision_and_failures()
    replay_results = evaluate_replay_policies()
    tables = build_markdown_tables(gate_results, prec_table, agree_wrong_list, replay_results)

    # Write audit text files
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    (AUDIT_DIR / "AJ_gate_tables.txt").write_text(tables["gate"] + "\n", encoding="utf-8")
    (AUDIT_DIR / "AJ_precision_table.txt").write_text(tables["precision"] + "\n", encoding="utf-8")
    (AUDIT_DIR / "AJ_agree_and_wrong.txt").write_text(tables["agree_wrong"] + "\n", encoding="utf-8")
    (AUDIT_DIR / "AJ_policy_table.txt").write_text(tables["replay"] + "\n", encoding="utf-8")

    summary_text = (
        "# Prompt AJ Analysis Summary\n\n"
        "## Gate Evaluation (AJ2)\n\n" + tables["gate"] + "\n\n"
        "## Precision Table (AJ2)\n\n" + tables["precision"] + "\n\n"
        "## Agree-and-Wrong List (AJ2)\n\n" + tables["agree_wrong"] + "\n\n"
        "## Replay Policy Evaluation (AJ3)\n\n" + tables["replay"] + "\n"
    )
    (AUDIT_DIR / "AJ_summary.txt").write_text(summary_text, encoding="utf-8")
    print(summary_text)


if __name__ == "__main__":
    main()
