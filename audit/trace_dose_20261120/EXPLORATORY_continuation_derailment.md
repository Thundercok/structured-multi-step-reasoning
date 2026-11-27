# Exploratory (post-hoc, 2026-11-27): Bypass vs. Continuation Derailment

**Status:** Exploratory post-hoc diagnostic run after H4 completed. Does **not** alter any pre-registered hypothesis, metric, or reading rule.
**Code & Tests:** `audit/trace_dose_20261120/decompose_continuations.py`, `tests/test_continuation_decomposition.py`, output saved in `audit/trace_dose_20261120/decomposition.json`.

---

## 1. Motivation

Standard counterfactual step-editing (`follows`) treats every non-following continuation (`1 - follows`) as "unfaithfulness" (ignoring the edited intermediate step).
However, in our `Step`/`Calc` setup, `plan_intervention` (`structured_llm/counterfactual.py:270-275`) constructs the perturbed value `new` so that `new` **never appears** in the problem statement or in any original operand or intermediate result.
Consequently, `new` appearing as an operand inside a continuation `Calc:` expression is an **exact deterministic witness** that the model causally read and propagated the edited value.

This lets us partition every B1 (`expected != None`) failure into two distinct mechanisms:
1. **Causal Bypass / Reversion (`bypass_or_revert`):** The model reverts to the unperturbed `original` answer OR never uses `new` as an operand in any continuation `Calc:` expression.
2. **Continuation Derailment (`derailed_after_using_new`):** The model *explicitly plugs `new` into a `Calc:` expression* (and neither reverts nor matches `expected`), failing downstream via:
   - `hit_expected_overstepped`: computes `expected` in an intermediate `Calc:` result, then fails to emit `</think>` and overwrites it with redundant/bogus steps;
   - `bad_arith`: commits an arithmetic slip (`calc_is_correct == False`);
   - `truncated_no_answer`: hits the token cap without emitting `Answer:`;
   - `wrong_downstream_step`: valid arithmetic on `new`, wrong downstream formula/step.

---

## 2. Main Finding on H4 (10 Adapters, 500 Clean GSM-Plus Holdout Items)

| Human Ratio | $N_{\text{B1}}$ | Exact `follows` | Round/Approx | **Bypass / Revert** | **Derailed *after* using `new`** | Submodes (`over` / `arith` / `trunc` / `step`) |
|---:|---:|---:|---:|---:|---:|---|
| **0%** | 464 | 415 (89.4%) | 24 (5.2%) | **15 (3.2%)** | **10 (2.2%)** | 0 / 3 / 0 / 7 |
| **25%** | 467 | 401 (85.9%) | 25 (5.4%) | **20 (4.3%)** | **21 (4.5%)** | 1 / 7 / 0 / 13 |
| **50%** | 486 | 403 (82.9%) | 24 (4.9%) | **28 (5.8%)** | **31 (6.4%)** | 2 / 13 / 0 / 16 |
| **75%** | 439 | 368 (83.8%) | 21 (4.8%) | **23 (5.2%)** | **27 (6.2%)** | 2 / 14 / 1 / 10 |
| **100%** | 418 | 335 (80.1%) | 24 (5.7%) | **19 (4.5%)** | **40 (9.6%)** | 8 / 8 / 3 / 21 |

### Adapter-Level OLS ($\text{df} = 7$, controlling for seed)
- **All B1 items:**
  - `bypass_or_revert`: $\hat b_{\text{human}} = +0.291$ ($\text{SE} = 0.281$), $t(7) = +1.04$, **$p = 0.335$ (null / flat)**.
  - `derailed_after_using_new`: $\hat b_{\text{human}} = +1.336$ ($\text{SE} = 0.261$), $t(7) = +5.12$, **$p = 0.00136$ (>4$\times$ increase)**.
- **Restricted to `originally_correct == True` (B1):**
  - `bypass_or_revert`: $\hat b_{\text{human}} = +0.137$ ($\text{SE} = 0.275$), $t(7) = +0.50$, **$p = 0.633$ (null / flat)**.
  - `derailed_after_using_new`: $\hat b_{\text{human}} = +1.024$ ($\text{SE} = 0.321$), $t(7) = +3.18$, **$p = 0.0154$**.

**Takeaway:** Across all 5 ratios, **94.2%–96.8%** of B1 continuations causally read and use the edited value `new`. Roughly **80% of the 9.3 pp drop** in `follows` from 0% to 100% human traces (+7.4 pp out of 9.3 pp) comes from **continuation fragility after consuming `new`**, not from ignoring the edited step.

---

## 3. Consistency on the Sealed GSM8K Test (1,319 Items, B1)

| Model | $N_{\text{B1}}$ | Exact `follows` | Bypass / Revert | Derailed *after* using `new` | Submodes (`over` / `arith` / `trunc` / `step`) |
|---|---:|---:|---:|---:|---|
| `base_prefill` | 570 | 490 (86.0%) | 33 (5.8%) | **15 (2.6%)** | 0 / 8 / 0 / 7 |
| `CF` (2,000 steps) | 748 | 615 (82.2%) | 36 (4.8%) | **53 (7.1%)** | 3 / 16 / 1 / 33 |
| `Plain` (2,000 steps) | 760 | 594 (78.2%) | 50 (6.6%) | **67 (8.8%)** | 6 / 16 / 0 / 45 |

The same pattern holds on GSM8K: `Plain` SFT's $-7.8$ pp deficit below `base_prefill` on B1 is driven primarily by downstream derailment after using `new` ($+6.2$ pp, 79% of the drop) rather than step bypass ($+0.8$ pp).

---

## 4. Relation to the 8/229 Decoupled Training-Row Check

In `EXPLORATORY_decoupled_rows.md`, we noted that 8/229 `human` training traces lack a `Calc:` line on their final step (`answer_from_last_calc == False`, vs. 0/229 in `self`).
Checking H4 continuations shows that `0/37` `other` failures at 100% human omit `Calc:` lines (all 37 emit `Calc:` equations using `new`), so the adapters are not simply imitating `Calc`-less final answers during interventions.
However, those 8/229 training rows (and 28 vs. 8 rows with any `Calc`-less `Step`) remain an uncontrolled structural difference in the training data that could indirectly weaken termination discipline (`hit_expected_overstepped` = 8 at 100% vs. 0 at 0%), and must be disclosed as a limitation until a filtered 221-pair ablation is run.
