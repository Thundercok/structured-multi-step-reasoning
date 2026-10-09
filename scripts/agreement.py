#!/usr/bin/env python3
"""Offline agreement signal analysis and policy replay (Prompt AJ).

Evaluates:
- Cross-strategy agreement signals: agree(PAL-v2, COT), agree(PAL-v2, ToT), n_agree
- Gate AUROC under repeated 5-fold CV x20 grouped by group_id with paired bootstrap CIs
- Precision P(correct | agree) and exhaustive Agree-and-Wrong item inspection
- Policy replay: G1, G2 vs always-ToT, W, always-PAL-v2 with cluster-bootstrap 95% CIs
"""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import random
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
import sklearn
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
ESTIMAND = "mean of item-pooled OOF AUROC across recorded CV repetitions"
TOKEN_SCOPE = "legacy prompt_tokens + completion_tokens proxy, summed across invoked arms; NOT full per-call input cost or full inference cost"
ANALYSIS_SETTINGS = {
    "n_splits": 5, "n_repeats": 20, "n_bootstrap": 2000, "seed": 42,
    "estimand": ESTIMAND, "delta_threshold": 0.05,
    "ci_scope": "paired group bootstrap of fixed OOF predictions; conditional on fitted folds and historical generations; no refitting",
    "multiplicity": "four signal comparisons per evaluable family; individual unadjusted intervals; exploratory only",
    "target": "retrospective PAL-v2 parsed-answer correctness; plurality is an auxiliary predictor of that same target",
    "token_scope": TOKEN_SCOPE,
}
PINNED_INPUTS = {
    RUN11_TRACE: "3d57df7f4e81c71513a30b46a190c2d848ea020dac78adf88776620b6e67e632",
    PALV2_TRACE: "c3f2bb0de9e1d04356497911dfb0377597fa7862799cff6754bd8a412ac0d57c",
    TUNE_PATH: "f3bfa9750038ecce95f31dcdd7362082c4d85487d37ff091282442874a12041c",
}
ANALYSIS_NOTES = [
    "EXPLORATORY reanalysis of exposed gen02_tune; its legacy test label does not make this a confirmatory test.",
    "Point estimates and paired cluster intervals both use mean-repeat OOF AUROC. Intervals condition on fixed predictions; folds/models are not refitted in bootstrap.",
    "Four signals per evaluable family have unadjusted intervals. An individual diagnostic threshold is not a global preregistration pass or evidence of VGC superiority.",
    "Historical prereg requires arith AND order, but its final verdict mentions order alone. This conflict remains review-pending; arith's single-class target is not evaluable.",
    "All gate signals predict PAL-v2 parsed-answer correctness. The plurality signal is an auxiliary predictor, not a separate plurality-correctness target.",
    "g24 agreement is validity-assisted: check24 maps different valid expressions to one key using question numbers. It is not pure answer identity or verifier-free agreement.",
    "Four-arm n_agree consumes historical PAL, CoT, candidate-selection and SC outputs (nominal collector configuration: 1+1+4+5 calls); no free or cheap online gate is established.",
    "Legacy candidate selection (labelled ToT) retains only one branch's prompt-token count; other branch and selector inputs are missing. All invoked arm fields are summed, but full per-call cost cannot be recovered.",
    "Parsed answers are retrospectively rescored. Candidate-selection and selected-SC termination cannot be fully reconstructed; this is not a corrected fresh model measurement.",
    "Replay G1/G2 use only PAL/CoT pair agreement, not four-arm n_agree. Their failure does not rule out every agreement policy or establish a verifier as the only solution.",
    "Agree-and-wrong lists demonstrate shared incorrect parsed answers; causal explanations require independent review.",
    "No new generation, GPU, model loading, prospective-test evaluation or Stage 0 change occurs.",
]


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

    items = tune_data["items"]
    if len(tasks) != len(items) or not items:
        raise ValueError("Duplicate IDs or empty development dataset")
    r11_by_id: Dict[str, Dict[str, Any]] = defaultdict(dict)
    for r in r11:
        if r["id"] not in tasks or r["arm"] in r11_by_id[r["id"]]:
            raise ValueError("Unknown or duplicate Run 11 item/arm")
        r11_by_id[r["id"]][r["arm"]] = r

    pal_by_id = {r["id"]: r for r in pal}
    if len(pal_by_id) != len(pal) or set(pal_by_id) != set(tasks):
        raise ValueError("Duplicate or incomplete PAL-v2 matrix")
    for item in items:
        rows = r11_by_id[item["id"]]
        if not {"COT", "TOT", "SC"} <= rows.keys():
            raise ValueError("Incomplete agreement arm matrix")
        for row in [pal_by_id[item["id"]], *rows.values()]:
            if any(row.get(key) != item[key] for key in ("group_id", "family", "level")) or row.get("gold") != item["answer"]:
                raise ValueError("Trace identity or gold differs from development data")
            if any(type(row.get(key)) is not int or row[key] < 0 for key in ("prompt_tokens", "completion_tokens")):
                raise ValueError("Invalid legacy token telemetry")
    return items, r11_by_id, pal_by_id


def _mean_auc_kernel(predictions, y):
    """Pairwise AUROC kernel, averaged AFTER evaluating each CV repetition.

    Counting positive > negative as 1 and ties as 0.5 gives exactly the
    binary empirical AUROC. Averaging these comparisons across repetitions
    preserves mean-repetition AUROC, unlike ranking averaged predictions.
    """
    predictions = np.asarray(predictions, dtype=float)
    y = np.asarray(y)
    if y.ndim != 1 or predictions.ndim != 2 or predictions.shape[1] != len(y) or not len(predictions) or not np.isfinite(predictions).all():
        raise ValueError("Expected finite repetition x item OOF predictions")
    if set(y) != {0, 1}:
        raise ValueError("AUROC requires both binary classes")
    diff = predictions[:, y == 1, None] - predictions[:, None, y == 0]
    return ((diff > 0) + 0.5 * (diff == 0)).mean(axis=0)


def paired_oof_bootstrap(oof_predictions, y, groups, *, n_bootstrap=2000, seed=42):
    """Fast paired group bootstrap of the SAME mean-repeat AUROC statistic.

    All models and repetitions use each identical cluster draw. Weights retain
    every item/variant within a sampled group. Degenerate draws are counted and
    rejected with a bounded retry budget, never an unbounded loop.
    """
    y, groups = np.asarray(y), np.asarray(groups)
    if y.ndim != 1 or groups.ndim != 1 or type(n_bootstrap) is not int or n_bootstrap < 1 or len(y) != len(groups):
        raise ValueError("Invalid bootstrap count or grouping")
    unique_groups = sorted(set(groups))
    if len(unique_groups) < 2 or set(y) != {0, 1} or "Baseline" not in oof_predictions:
        raise ValueError("Bootstrap needs two groups, both classes and Baseline")
    kernels = {name: _mean_auc_kernel(preds, y) for name, preds in oof_predictions.items()}
    if len({np.asarray(preds).shape for preds in oof_predictions.values()}) != 1:
        raise ValueError("Models must share the same OOF repetitions and items")
    group_lookup = {group: index for index, group in enumerate(unique_groups)}
    item_group = np.array([group_lookup[group] for group in groups])
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
        denominator = pos.sum(axis=1) * neg.sum(axis=1)
        valid = denominator > 0
        for name, kernel in kernels.items():
            scores = np.einsum("bi,ij,bj->b", pos[valid], kernel, neg[valid]) / denominator[valid]
            samples[name].extend(scores.tolist())
        accepted += int(valid.sum())
        attempted += size
    if accepted != n_bootstrap:
        raise ValueError("Insufficient nondegenerate bootstrap draws; review grouping")
    base = np.array(samples["Baseline"])
    differences = {name: (np.array(values) - base).tolist() for name, values in samples.items() if name != "Baseline"}
    return differences, {"accepted_draws": accepted, "attempted_draws": attempted,
                         "discarded_one_class_draws": attempted - accepted, "seed": seed,
                         "estimand": ESTIMAND, "refit": False}


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
    artifacts=None,
) -> Dict[str, Any]:
    """Repeated grouped CV; point estimate and CI both use mean-repeat AUROC."""
    y, groups = np.asarray(y), np.asarray(groups)
    if y.ndim != 1 or groups.ndim != 1:
        raise ValueError("Expected one-dimensional binary labels and groups")
    models_dict = {name: np.asarray(X, dtype=float) for name, X in models_dict.items()}
    n_samples = len(y)
    unique_groups = sorted(set(groups))
    if (y.ndim != 1 or groups.ndim != 1 or len(groups) != n_samples
            or set(y) != {0, 1} or type(n_splits) is not int
            or not 2 <= n_splits <= len(unique_groups)
            or type(n_repeats) is not int or n_repeats < 1
            or type(n_bootstrap) is not int or n_bootstrap < 1
            or "Baseline" not in models_dict
            or not np.array_equal(models_dict["Baseline"], X_base)):
        raise ValueError("Invalid binary grouped-CV design or baseline")
    if any(np.asarray(X).ndim != 2 or len(X) != n_samples or not np.isfinite(X).all()
           for X in models_dict.values()):
        raise ValueError("Invalid feature matrix")
    group_to_indices = defaultdict(list)
    for index, group in enumerate(groups):
        group_to_indices[group].append(index)
    oof_preds = {name: np.full((n_repeats, n_samples), np.nan) for name in models_dict}
    assignments = np.full((n_repeats, n_samples), -1, dtype=int)
    constant_training_folds = 0

    for rep in range(n_repeats):
        shuffled_groups = unique_groups.copy()
        random.Random(seed + rep).shuffle(shuffled_groups)
        folds = [shuffled_groups[i::n_splits] for i in range(n_splits)]
        for fold_index, validation_groups in enumerate(folds):
            validation_set = set(validation_groups)
            train_idx = sorted(i for group in unique_groups if group not in validation_set
                               for i in group_to_indices[group])
            val_idx = sorted(i for group in validation_groups for i in group_to_indices[group])
            assignments[rep, val_idx] = fold_index
            y_tr = y[train_idx]
            single_class = len(set(y_tr)) == 1
            constant_training_folds += int(single_class)
            for name, X in models_dict.items():
                if single_class:
                    oof_preds[name][rep, val_idx] = float(y_tr[0])
                else:
                    scaler = StandardScaler()
                    X_tr = scaler.fit_transform(X[train_idx])
                    X_va = scaler.transform(X[val_idx])
                    clf = LogisticRegression(C=1.0, random_state=0, max_iter=1000)
                    clf.fit(X_tr, y_tr)
                    oof_preds[name][rep, val_idx] = clf.predict_proba(X_va)[:, 1]
    if any(not np.isfinite(preds).all() for preds in oof_preds.values()) or (assignments < 0).any():
        raise ValueError("Incomplete OOF predictions")

    rep_aucs = {name: [float(roc_auc_score(y, scores)) for scores in preds]
                for name, preds in oof_preds.items()}
    differences, bootstrap = paired_oof_bootstrap(
        oof_preds, y, groups, n_bootstrap=n_bootstrap, seed=seed,
    )
    base_mean = float(np.mean(rep_aucs["Baseline"]))
    results = {}
    for name, aucs in rep_aucs.items():
        mean = float(np.mean(aucs))
        delta = mean - base_mean
        ci_low, ci_high = (np.quantile(differences[name], [0.025, 0.975]).tolist()
                           if name in differences else (None, None))
        met = bool(name != "Baseline" and delta >= 0.05 and ci_low > 0)
        results[name] = {
            "mean_auroc": mean, "std_auroc": float(np.std(aucs)), "delta": delta,
            "ci_low": ci_low, "ci_high": ci_high,
            "passed": met, "individual_diagnostic_threshold_met": met,
            "preregistration_pass": False, "estimand": ESTIMAND,
            "ci_scope": ANALYSIS_SETTINGS["ci_scope"], "multiplicity_adjusted": False,
        }
    if artifacts is not None:
        artifacts.update(
            target=y.tolist(), groups=groups.tolist(), fold_assignments=assignments.tolist(),
            oof_predictions={name: preds.tolist() for name, preds in oof_preds.items()},
            feature_matrices={name: np.asarray(X).tolist() for name, X in models_dict.items()},
            repeat_aurocs=rep_aucs, bootstrap_deltas=differences, bootstrap=bootstrap,
            constant_training_folds=constant_training_folds,
            cv_settings={"n_splits": n_splits, "n_repeats": n_repeats,
                         "split_seeds": [seed + rep for rep in range(n_repeats)]},
        )
    return results


def evaluate_gate_all(artifacts=None):
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
                "models": {m: {"mean_auroc": None, "delta": None, "ci_low": None, "ci_high": None,
                               "passed": False, "individual_diagnostic_threshold_met": False,
                               "preregistration_pass": False, "status": "not_evaluable_single_class"} for m in models_dict}
            }
            if artifacts is not None:
                artifacts[fam] = {"ids": [it["id"] for it in f_items], "status": "not_evaluable_single_class"}
        else:
            detail = {} if artifacts is not None else None
            cv_res = run_cv_evaluation(X_base, models_dict, y, groups, artifacts=detail)
            if detail is not None:
                detail["ids"] = [it["id"] for it in f_items]
                artifacts[fam] = detail
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

            p_corr = (n_corr / n_agreed) if n_agreed > 0 else None
            prec_table[fam][sig] = {
                "n_agreed": n_agreed,
                "n_total": n_total,
                "n_corr": n_corr,
                "p_corr": p_corr,
            }

    return prec_table, agree_wrong_list


def evaluate_replay_policies(artifacts=None):
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
        if artifacts is not None:
            for pol, recs in policy_records.items():
                for item, rec in zip(f_items, recs):
                    rec["id"] = item["id"]
                    rec["token_scope"] = TOKEN_SCOPE
            artifacts[fam] = policy_records
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
                "token_scope": TOKEN_SCOPE,
                "scoring_scope": "retrospective parsed answers; legacy candidate/SC branch termination is not fully retained",
            }

    return replay_results


def build_markdown_tables(gate_results, prec_table, agree_wrong_list, replay_results):
    tables = {}

    # 1. Gate Table
    gate_lines = []
    gate_lines.append("| Family | Signal predicting PAL correctness | Mean repeat baseline AUROC | Mean repeat signal AUROC | Δ AUROC | Paired 95% CI, SAME statistic | Unadjusted diagnostic threshold |")
    gate_lines.append("| :--- | :--- | :---: | :---: | :---: | :---: | :---: |")

    for fam in ["arith", "order", "g24", "pooled"]:
        info = gate_results[fam]
        fam_label = f"{fam} (N={info['n']})"
        if info["degenerate"]:
            note = f"Single-class PAL target ({info['n_pos']} positive, {info['n_neg']} negative)"
            gate_lines.append(f"| **{fam_label}** | Baseline | N/A | N/A | N/A | N/A | N/A ({note}) |")
            for sig in ["+ agree(PAL,COT)", "+ agree(PAL,TOT)", "+ n_agree (PAL)", "+ n_agree (plurality)"]:
                gate_lines.append(f"| {fam} | {sig} | N/A | N/A | N/A | N/A | NOT EVALUABLE ({note}) |")
        else:
            base_auroc = info["models"]["Baseline"]["mean_auroc"]
            for sig in ["+ agree(PAL,COT)", "+ agree(PAL,TOT)", "+ n_agree (PAL)", "+ n_agree (plurality)"]:
                m_info = info["models"][sig]
                s_auroc = m_info["mean_auroc"]
                d = m_info["delta"]
                ci_l, ci_h = m_info["ci_low"], m_info["ci_high"]
                pass_str = "MET (exploratory only)" if m_info["passed"] else "NOT MET"
                gate_lines.append(
                    f"| {fam} | {sig} | {base_auroc:.4f} | {s_auroc:.4f} | {d:+.4f} | [{ci_l:+.4f}, {ci_h:+.4f}] | {pass_str} |"
                )
    tables["gate"] = "\n".join(gate_lines)

    # 2. Precision Table
    prec_lines = []
    prec_lines.append("| Family | Signal | Agreed Items / Total | Correct When Agreed | P(Correct \\| Agree) |")
    prec_lines.append("| :--- | :--- | :---: | :---: | :---: |")
    for fam in ["arith", "order", "g24", "pooled"]:
        for sig in ["agree(PAL-v2,COT)", "agree(PAL-v2,ToT)", "pal_agree>=2", "pal_agree>=3", "pal_agree==4", "plurality_agree>=2", "plurality_agree>=3", "plurality_agree==4"]:
            info = prec_table[fam][sig]
            n_a = info["n_agreed"]
            n_t = info["n_total"]
            n_c = info["n_corr"]
            p = info["p_corr"]
            precision = f"{p*100:.1f}%" if p is not None else "N/A (no agreements)"
            prec_lines.append(f"| {fam} | {sig} | {n_a}/{n_t} ({n_a/n_t*100:.1f}%) | {n_c}/{n_a} | {precision} |")
    tables["precision"] = "\n".join(prec_lines)

    # 3. Agree-and-Wrong List
    wrong_lines = []
    wrong_lines.append("| Item ID | Family | Level | Signal | Accepted Answer | Gold Answer | Arms (PAL-v2 / COT / candidate selection / SC) | Observation, NOT causal diagnosis |")
    wrong_lines.append("| :--- | :--- | :---: | :--- | :---: | :---: | :--- | :--- |")

    seen_items = set()
    for w in agree_wrong_list:
        key = (w["id"], w["signal"])
        if key in seen_items:
            continue
        seen_items.add(key)
        arms_str = f"PAL: {w['arms']['PAL-v2']}, COT: {w['arms']['COT']}, ToT: {w['arms']['TOT']}, SC: {w['arms']['SC']}"
        mech = "Shared incorrect parsed answer; underlying cause not independently reviewed"
        wrong_lines.append(
            f"| `{w['id']}` | {w['family']} | {w['level']} | {w['signal']} | **{w['accepted']}** | **{w['gold']}** | {arms_str} | {mech} |"
        )
    tables["agree_wrong"] = "\n".join(wrong_lines)

    # 4. Replay Policies Table
    replay_lines = []
    replay_lines.append("| Family | Policy | Retrospective accuracy (corr/n) | 95% Cluster CI (Acc) | Mean LEGACY token proxy | 95% Cluster CI (Proxy) | Escalation Rate |")
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


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _hash_paths(paths):
    return {str(path.relative_to(ROOT)): _sha256(path) for path in paths}


def write_analysis(output):
    """Reanalyse only pinned, exposed inputs into a NEW, provenance-rich directory.

    Historical AJ artifacts and the contradictory original prereg remain intact.
    Complete all calculations and recheck input/source hashes before creating any
    output. This mode cannot substitute prospective test data or start a model.
    """
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError("Agreement analysis requires a new output directory")
    for path, expected in PINNED_INPUTS.items():
        if _sha256(path) != expected:
            raise ValueError(f"Pinned development input hash mismatch: {path.name}")
    source_paths = [Path(__file__).resolve(), ROOT / "experiments/research_study.py",
                    ROOT / "reasoning_strategies.py", ROOT / "research_scoring.py",
                    ROOT / "scripts/gen_tasks.py", ROOT / "docs/agreement_reanalysis_protocol_20261008.md"]
    historical_paths = [ROOT / "prereg/decision_rule_agree.md",
                        *[AUDIT_DIR / name for name in (
                            "AJ_gate_tables.txt", "AJ_precision_table.txt", "AJ_agree_and_wrong.txt",
                            "AJ_policy_table.txt", "AJ_summary.txt")]]
    sources, inputs = _hash_paths(source_paths), _hash_paths(PINNED_INPUTS)
    historical = _hash_paths(historical_paths)
    test_canonicalizer()
    items, _, _ = load_dataset()
    cv_artifacts, policy_artifacts = {}, {}
    gate_results = evaluate_gate_all(artifacts=cv_artifacts)
    precision, wrong = evaluate_precision_and_failures()
    replay = evaluate_replay_policies(artifacts=policy_artifacts)
    tables = build_markdown_tables(gate_results, precision, wrong, replay)
    summary = {"status": "exploratory_review_pending", "preregistration_pass": False,
               "confirmatory": False, "gate": gate_results, "precision": precision,
               "replay": replay, "notes": ANALYSIS_NOTES}
    report = "# Agreement reanalysis — EXPLORATORY\n\n"
    report += "Review status: software/statistic correction; publication and prereg interpretation pending.\n\n"
    report += "\n".join(f"- {note}" for note in ANALYSIS_NOTES) + "\n\n"
    for heading, key in (("Gate diagnostics", "gate"), ("Conditional precision", "precision"),
                         ("Shared incorrect answers (not causal diagnoses)", "agree_wrong"),
                         ("Retrospective policy replay — legacy token proxy", "replay")):
        report += f"## {heading}\n\n{tables[key]}\n\n"
    if sources != _hash_paths(source_paths) or inputs != _hash_paths(PINNED_INPUTS) or historical != _hash_paths(historical_paths):
        raise ValueError("Source/input/history changed during analysis; rerun into a new directory")
    # Strict serialization catches nonfinite or nonportable output before writing.
    artifacts = {"settings.json": ANALYSIS_SETTINGS, "summary.json": summary,
                 "cv.json": cv_artifacts, "policy_rows.json": policy_artifacts,
                 "agree_and_wrong.json": wrong}
    serialized = {name: json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
                  for name, value in artifacts.items()}
    from experiments.research_study import git_value

    manifest = {
        "schema_version": 1, "status": "complete", "evidence": "historical_measured_development_reanalysis",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "new_model_calls": 0, "confirmatory": False, "prospective_test_evaluated": False,
        "publication_review_required": True, "preregistration_pass": False,
        "token_scope": TOKEN_SCOPE, "settings": ANALYSIS_SETTINGS,
        "inputs_sha256": inputs, "source_sha256": sources,
        "preserved_historical_sha256": historical,
        "n_items": len(items), "n_groups": len({item['group_id'] for item in items}),
        "family_counts": dict(Counter(item["family"] for item in items)),
        "runtime": {"python": platform.python_version(), "numpy": np.__version__,
                    "scikit_learn": sklearn.__version__, "platform": platform.platform()},
        "git_head": git_value("rev-parse", "HEAD"), "git_status": git_value("status", "--short"),
    }
    output.mkdir(parents=True, exist_ok=False)
    for name, content in serialized.items():
        (output / name).write_text(content, encoding="utf-8")
    for name, content in tables.items():
        (output / f"{name}_table.md").write_text(content + "\n", encoding="utf-8")
    (output / "report.md").write_text(report, encoding="utf-8")
    manifest["artifacts_sha256"] = {path.name: _sha256(path) for path in sorted(output.iterdir())}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="NEW directory; never overwrite historical AJ artifacts")
    args = parser.parse_args(argv)
    try:
        write_analysis(args.output)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f"agreement_exploratory_reanalysis: {args.output / 'report.md'}")


if __name__ == "__main__":
    main()
