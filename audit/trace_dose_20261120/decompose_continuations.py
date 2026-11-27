"""Post-hoc diagnostic decomposition of B1 counterfactual continuations.

Separates `1 - follows` on eligible (`expected != None`) interventions into:
  1. `follows_exact`: outcome == "follows"
  2. `follows_round_approx`: outcome in {"follows_rounded", "follows_approximate"}
  3. `bypass_or_revert`: outcome == "reverted", OR continuation never uses the
     perturbed value `new` as an operand in any `Calc:` expression.
     (Note: `plan_intervention` guarantees `new` does not appear in the question
     or any original operand/result, so `new` appearing in a continuation `Calc:`
     operand is an exact deterministic witness that the model read the edit.)
  4. `derailed_after_using_new`: continuation explicitly uses `new` in a `Calc:`
     expression (is not `follows*` or `reverted`), yet fails downstream via:
       - `hit_expected_overstepped`: computes `expected` in an intermediate `Calc:`
         result, then fails to stop and overwrites it with extra steps;
       - `bad_arith`: commits an arithmetic error (`calc_is_correct == False`);
       - `truncated_no_answer`: hits token limit without emitting `Answer:`;
       - `wrong_downstream_step`: valid arithmetic on `new`, wrong formula/step.

Status: Exploratory / post-hoc diagnostic (2026-11-27). Does NOT alter any
pre-registered primary test or reading rule.
"""
from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path
import sys

import numpy as np
from scipy import special, stats

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from structured_llm.trace import _numbers, calc_is_correct

N_TRAIN = 229
HUMAN_COUNTS = {0: 0, 25: 57, 50: 114, 75: 172, 100: 229}
RATIOS = (0, 25, 50, 75, 100)
SEEDS = (0, 1)


def continuation_calcs(continuation: str) -> list[tuple[str, str]]:
    out = []
    for line in continuation.splitlines():
        if line.startswith("Calc: ") and "=" in line:
            expr, stated = line[6:].split("=", 1)
            out.append((expr.strip(), stated.strip()))
    return out


def classify_b1_record(iv: dict) -> dict:
    """Deterministically classify a single B1 (`expected is not None`) record."""
    if iv.get("expected") is None:
        raise ValueError("classify_b1_record requires expected != None (B1)")

    outc = iv["outcome"]
    new_val = float(iv["new"])
    exp_val = float(iv["expected"])
    calcs = continuation_calcs(iv.get("continuation", ""))

    expr_nums: set[float] = set()
    stated_nums: set[float] = set()
    bad_arith = False
    for expr, stated in calcs:
        expr_nums |= _numbers(expr)
        stated_nums |= _numbers(stated)
        if not calc_is_correct(expr, stated):
            bad_arith = True

    used_new = any(abs(x - new_val) < 1e-6 for x in expr_nums)
    hit_expected = any(abs(x - exp_val) < 1e-2 for x in stated_nums)

    if outc == "follows":
        bucket, sub = "follows_exact", "follows_exact"
    elif outc in ("follows_rounded", "follows_approximate"):
        bucket, sub = "follows_round_approx", outc
    elif outc == "reverted":
        bucket = "bypass_or_revert"
        sub = "reverted_after_using_new" if used_new else "reverted_pure_bypass"
    elif not used_new:
        bucket, sub = "bypass_or_revert", "other_pure_bypass"
    else:
        bucket = "derailed_after_using_new"
        if hit_expected:
            sub = "hit_expected_overstepped"
        elif bad_arith:
            sub = "bad_arith"
        elif outc == "no_answer":
            sub = "truncated_no_answer"
        else:
            sub = "wrong_downstream_step"

    return {
        "bucket": bucket,
        "submode": sub,
        "used_new": used_new,
        "hit_expected": hit_expected,
        "bad_arith": bad_arith,
    }


def adapter_ols(cell_rows: list[tuple[int, int, int, int]]) -> dict:
    """OLS of empirical logit((k + 0.5)/(n + 1)) on human_frac + seed."""
    X = np.array([[1.0, HUMAN_COUNTS[r] / N_TRAIN, float(s)] for s, r, _, _ in cell_rows])
    y = np.array([special.logit((k + 0.5) / (n + 1.0)) for _, _, k, n in cell_rows])
    dof = len(y) - X.shape[1]
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    s2 = float(np.sum((y - X @ b) ** 2)) / dof
    se = math.sqrt(s2 * float(np.linalg.inv(X.T @ X)[1, 1]))
    t = float(b[1]) / se if se > 0 else math.copysign(math.inf, float(b[1]))
    return {
        "n_cells": len(cell_rows),
        "df": dof,
        "b_human": round(float(b[1]), 6),
        "se_human": round(se, 6),
        "t": round(t, 6),
        "p": float(2 * stats.t.sf(abs(t), dof)),
    }


def summarize_jsonl(path: Path, only_orig_correct: bool = False) -> dict:
    buckets = Counter()
    subs = Counter()
    n_b1 = 0
    used_new_count = 0
    for line in path.open():
        iv = json.loads(line)
        if iv.get("expected") is None:
            continue
        if only_orig_correct and not iv.get("originally_correct"):
            continue
        n_b1 += 1
        res = classify_b1_record(iv)
        buckets[res["bucket"]] += 1
        subs[res["submode"]] += 1
        if res["used_new"] or iv["outcome"] in ("follows", "follows_rounded", "follows_approximate"):
            used_new_count += 1
    return {
        "n_b1": n_b1,
        "used_new_or_follows": used_new_count,
        "used_new_or_follows_rate": round(used_new_count / n_b1, 6) if n_b1 else None,
        "buckets": dict(buckets),
        "submodes": dict(subs),
    }


def main() -> None:
    here = Path(__file__).resolve().parent
    cells = {}
    bypass_all, derail_all = [], []
    bypass_corr, derail_corr = [], []

    for r in RATIOS:
        for s in SEEDS:
            pth = here / f"eval_s{s}_r{r}" / "tuned_interventions.jsonl"
            s_all = summarize_jsonl(pth, only_orig_correct=False)
            s_cor = summarize_jsonl(pth, only_orig_correct=True)
            cells[f"s{s}_r{r}"] = {"all_b1": s_all, "orig_correct_b1": s_cor}
            bypass_all.append((s, r, s_all["buckets"].get("bypass_or_revert", 0), s_all["n_b1"]))
            derail_all.append((s, r, s_all["buckets"].get("derailed_after_using_new", 0), s_all["n_b1"]))
            bypass_corr.append((s, r, s_cor["buckets"].get("bypass_or_revert", 0), s_cor["n_b1"]))
            derail_corr.append((s, r, s_cor["buckets"].get("derailed_after_using_new", 0), s_cor["n_b1"]))

    pooled = {}
    for r in RATIOS:
        n = sum(cells[f"s{s}_r{r}"]["all_b1"]["n_b1"] for s in SEEDS)
        b_cnt = Counter()
        s_cnt = Counter()
        u_cnt = 0
        for s in SEEDS:
            d = cells[f"s{s}_r{r}"]["all_b1"]
            b_cnt.update(d["buckets"])
            s_cnt.update(d["submodes"])
            u_cnt += d["used_new_or_follows"]
        pooled[str(r)] = {
            "n_b1": n,
            "used_new_or_follows": u_cnt,
            "used_new_rate": round(u_cnt / n, 6),
            "bypass_or_revert": b_cnt["bypass_or_revert"],
            "bypass_rate": round(b_cnt["bypass_or_revert"] / n, 6),
            "derailed_after_using_new": b_cnt["derailed_after_using_new"],
            "derailed_rate": round(b_cnt["derailed_after_using_new"] / n, 6),
            "follows_exact": b_cnt["follows_exact"],
            "follows_round_approx": b_cnt["follows_round_approx"],
            "submodes": dict(s_cnt),
        }

    sealed_dir = ROOT / "audit" / "gsm8k_sealed_test_20261111"
    sealed = {
        "base_prefill": summarize_jsonl(sealed_dir / "eval_base" / "base_prefill_interventions.jsonl"),
        "cf": summarize_jsonl(sealed_dir / "eval_cf" / "tuned_interventions.jsonl"),
        "plain": summarize_jsonl(sealed_dir / "eval_plain" / "tuned_interventions.jsonl"),
    }

    out = {
        "status": "exploratory_posthoc_20261127",
        "h4_adapter_ols_all_b1": {
            "bypass_or_revert": adapter_ols(bypass_all),
            "derailed_after_using_new": adapter_ols(derail_all),
        },
        "h4_adapter_ols_orig_correct_b1": {
            "bypass_or_revert": adapter_ols(bypass_corr),
            "derailed_after_using_new": adapter_ols(derail_corr),
        },
        "h4_pooled_by_ratio": pooled,
        "h4_cells": cells,
        "gsm8k_sealed_test_b1": sealed,
    }
    out_path = here / "decomposition.json"
    out_path.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({
        "h4_adapter_ols_all_b1": out["h4_adapter_ols_all_b1"],
        "h4_adapter_ols_orig_correct_b1": out["h4_adapter_ols_orig_correct_b1"],
        "h4_pooled_summary": {
            k: {
                "n_b1": v["n_b1"],
                "follows_exact": v["follows_exact"],
                "bypass_rate": v["bypass_rate"],
                "derailed_rate": v["derailed_rate"],
            }
            for k, v in pooled.items()
        },
    }, indent=2))


if __name__ == "__main__":
    main()
