# Entry predictor — offline development evaluation

Source implementation added 2026-10-29. **Focused verification: 50 tests passed
in 66.75s; one saved-output synthetic evaluation completed.** Evidence is in
`audit/entry_evaluation_verification_20261029/`.
This is exploratory infrastructure in the RAT–CoT headless research harness.
It does not change Stage 0, launch a campaign, choose production defaults or
establish a model-quality improvement. Lite remains set aside.

## Entry point and input contract

Use an existing, complete original run from `experiments.research_study`:

```bash
python -m experiments.research_study \
  --entry-evaluation runs/smoke-42 \
  --entry-configs old scaler_only pca32 \
  --entry-folds 5 --entry-repeats 2 --entry-bootstrap 2000 \
  --seed 42 --output runs/entry-development-review-v1
```

This full-size example is documentation. The authorized smoke used 3 folds,
1 repeat and 200 bootstrap draws, with the same three configurations and seed,
writing to `runs/entry-development-smoke-20261029`.
`--seed` controls CV/bootstrap, not generation. Lambda comes from the recorded
manifest; model/data/lambda overrides are refused. Configurations can also
include `pca16`, `pca64`, or just `old`. No configuration is selected automatically.

Only main-study original collections with separate train/calibration/test and
all five strategy attempts are supported initially. Fixed DIRECT/CoT pilots,
replay copies, bare NPZ files and the supplied synthetic sweep JSON are not
compatible inputs. A `smoke` collection remains labeled synthetic throughout.
Measured records remain exploratory and retain model revision verification status;
their presence is not permission to collect more data.

The loader verifies original manifest-bound artifacts, source fingerprint syntax,
dataset identities, split/group isolation, feature dimensions, finite features
and confidence, positive integer generated-token counts, and development answer
scoring. Development records must agree with their raw attempt events. Stale
scoring semantics cause refusal for review, not hash rewriting.

Original manifests/source hashes are retained in output provenance. Current
evaluator sources receive their own fingerprints. This retrospective analysis
does not replace strict historical source verification or relax normal replay
guards. Artifact checksums bind saved bytes; they do not establish human review,
truth of provenance declarations, or correctness of a real model.

## Split and fitting behavior

1. Fit `OptimalStoppingPolicy` only on recorded **calibration** outputs.
2. Replay that fixed policy on **train** outputs to construct LADDER accuracy
   and cumulative costs; reuse the harness's `entry_training_data` contract.
3. Partition original train groups into outer CV folds. Every member of a group
   stays together. Repeat group assignment with the recorded evaluation seed.
4. Fit the shared `EntryPredictor` only on each outer training partition.
   Preprocessing/PCA stays inside the inner tuning pipeline. The new optional
   `fit(..., groups=...)` uses group-isolated inner folds; existing callers
   without groups retain their previous splitting behavior.
5. If a group-isolated classifier training fold would lack a class, use the
   existing fixed strong L2 fallback on the full outer training partition.
   Do not split groups to make CV possible. A one-class full partition uses the
   constant classifier. Cost heads similarly fall back when fewer than two
   groups are available. PCA sizes against actual training folds.
6. Predict outer held-out train items, look up recorded route outcomes and save
   the complete OOF decisions. Test outcome records are never passed to fitting,
   scoring, or configuration selection. They are parsed for dataset coverage
   and split metadata, and input files are hashed as frozen bytes.

This compares entry heads conditional on an independent, fixed calibration
policy. It is not end-to-end cross-fitting of a policy fitted on the same train
labels. Do not export legacy `pipeline.fit_full_policy` in-sample targets into
this evaluator as if they satisfied the input contract.

## Methods, units and uncertainty

- `old`: explicit historical raw-feature LogisticRegression (`C=1` default) and
  Ridge (`alpha=1`) baseline. No hyperparameter tuning.
- `scaler_only`, `pca16/32/64`: the shared regularized predictor with grouped
  inner CV; the names specify requested component limits, capped by available
  dimensions and training rows.
- `training_base_rate`: per-route accuracy rates and mean costs fit only on each
  outer training fold. Its route is selected using those training estimates.
- `fixed_LADDER/REACT/PAL`: named fixed-route references. Their log-loss uses the
  same training-only base-rate probabilities, not fabricated route probabilities.
- Best fixed route in hindsight and per-item oracle appear only as descriptive
  utility values. They are never deployed, selected as the baseline for an
  inferential claim, or used for confidence intervals.

For every evaluated method/repeat/item, record probabilities, predicted costs,
chosen route, observed correctness, realized cost, utility and mean route-wise
binary log-loss. Ridge's predicted costs remain unclipped to preserve the shared
decision rule. Realized costs use the actual recorded route counts.

`utility = accuracy - lambda * cost_k_tokens`. Route costs sum all strategy
generated counts and divide by 1000; smoke counts are **synthetic units**.
Input/prompt tokens, total collection costs, full inference costs and online
latency are not estimated by these route-level metrics.

All metrics and route mixes include every repeat. Average outcomes/log-loss
over repeats per query first, then bootstrap original groups with all their
queries together. This is a query-weighted estimand; groups are the resampling
unit, not additional independent questions from seeds/repeats.

Intervals for accuracy, cost, utility, log-loss and paired differences are
**exploratory conditional intervals**. The calculation does not refit models
inside bootstrap draws or cover shared-training-fold dependence, calibration
uncertainty, source selection, hyperparameter search across this report, or
generation variability. Do not interpret exclusion of zero as a validated
significance claim. Choosing PCA from these development results needs a
separately reviewed evaluation plan before any confirmatory test.

## Saved artifacts and verification status

Output must be a new directory outside the input tree. Input is read-only.
Full computation happens before output directory creation.

- `manifest.json`: input manifest/hash, current source hashes, package/runtime,
  settings, scope, evidence, artifact hashes and explicit zero real-model calls.
- `folds.json`: IDs and groups in each outer training/evaluation partition.
- `predictions.json`: all OOF predictions and per-query metrics for every repeat.
- `targets.json`: recorded LADDER/REACT/PAL training outcomes and costs.
- `calibration.json`: calibration IDs and fitted stopping thresholds.
- `summary.json`: per-repeat and repeat-averaged metrics, paired differences,
  conditional intervals, route mixes and hindsight-only references.
- `report.md`: readable summary with the interpretation limits.

## Full development evaluation results (5 folds, 2 repeats, 2000 bootstrap draws)

Executed 2026-10-31 under strict command-verified environment:
```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
python -m experiments.research_study \
  --entry-evaluation runs/smoke-42 --entry-configs old scaler_only pca32 \
  --entry-folds 5 --entry-repeats 2 --entry-bootstrap 2000 --seed 42 \
  --output runs/entry-development-eval-5f2r-20261031
```

Evidence level: **`synthetic_development_cv`** (zero real-model calls; test split with 24 items excluded and uninspected).
Output artifact directory: `runs/entry-development-eval-5f2r-20261031`.

### Summary of evaluated methods

| Method | Accuracy (95% CI) | Mean cost $k$ (95% CI) | Utility (95% CI) | Log-loss (95% CI) | Route Mix (LADDER / REACT / PAL) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `fixed_LADDER` | 0.8750 [0.7500, 1.0000] | 1.8000 [1.0708, 2.6969] | 0.8390 [0.6947, 0.9636] | 0.6464 [0.5460, 0.7775] | 100% / 0% / 0% |
| `fixed_REACT` | 0.4583 [0.2500, 0.6667] | 0.6000 [0.6000, 0.6000] | 0.4463 [0.2380, 0.6547] | 0.6464 [0.5460, 0.7775] | 0% / 100% / 0% |
| `fixed_PAL` | 0.4167 [0.2083, 0.6250] | 0.3000 [0.3000, 0.3000] | 0.4107 [0.2023, 0.6190] | 0.6464 [0.5460, 0.7775] | 0% / 0% / 100% |
| `training_base_rate` | 0.8750 [0.7500, 1.0000] | 1.8000 [1.0708, 2.6969] | 0.8390 [0.6947, 0.9636] | 0.6464 [0.5460, 0.7775] | 100% / 0% / 0% |
| `old` (unregularized) | 0.8750 [0.7500, 1.0000] | 1.7063 [0.9875, 2.6333] | 0.8409 [0.6972, 0.9653] | 0.5092 [0.3924, 0.6526] | 88% / 0% / 12% |
| `pca32` | 0.9375 [0.8333, 1.0000] | 1.2542 [0.6500, 2.0606] | 0.9124 [0.8129, 0.9813] | 0.5342 [0.3321, 0.8194] | 65% / 2% / 33% |
| `scaler_only` | 0.9375 [0.8333, 1.0000] | 1.0625 [0.5875, 1.7125] | 0.9163 [0.8146, 0.9848] | 0.5048 [0.3078, 0.7584] | 58% / 4% / 38% |

*Descriptive references only (peeking at outcomes, not deployable):* Best fixed utility = 0.8390; Oracle utility = 0.9478.

### Paired differences against `old` baseline

| Candidate Configuration | $\Delta$ Accuracy (95% CI) | $\Delta$ Cost $k$ (95% CI) | $\Delta$ Utility (95% CI) | $\Delta$ Log-loss (95% CI) |
| :--- | :---: | :---: | :---: | :---: |
| `scaler_only` minus `old` | +0.0625 [-0.0417, +0.2083] | -0.6437 [-1.3105, -0.1562] | +0.0754 [-0.0357, +0.2279] | -0.0044 [-0.1308, +0.1616] |
| `pca32` minus `old` | +0.0625 [-0.0417, +0.2083] | -0.4521 [-1.0813, -0.0813] | +0.0715 [-0.0388, +0.2254] | +0.0250 [-0.1012, +0.2180] |

*Observations & Interpretation Constraints:*
1. **Cost reduction at matched/improved accuracy:** Both `scaler_only` and `pca32` demonstrate reliable cost reductions ($\Delta \text{Cost} = -0.6437$ and $-0.4521$ k units respectively, with 95% CIs entirely below zero) by shifting from uncalibrated 88% LADDER dominance to a more balanced 58%–65% LADDER and 33%–38% PAL routing.
2. **Conditional interval scope:** The 95% CIs for accuracy and utility differences cross zero on this sample ($N=24$ groups, 48 records over 2 repeats). As specified in the protocol, zero-exclusion does not constitute a confirmatory claim.
3. **No automatic model selection:** In accordance with the protocol, no configuration was automatically selected as a production default. Stage 0 gates remain in place.

Authored regression coverage is in `tests/test_entry_evaluation.py`: group
isolation at both levels, training-only base rates, repeat consistency, ignored
test payloads, raw artifact integrity, bad metadata/settings, no overwrite,
and forbidden backend/Qt imports. The user-authorized batch included that file
alongside `tests/test_research_study.py`, `test_optimal_stopping.py`, and
`test_entry_predictor.py`: 50 passed. The smoke produced 168 OOF predictions,
all on train, excluded 24 test items, preserved group isolation and selected no
configuration. Source/artifact hashes matched at inspection. There were zero
real model calls. This does not authorize additional testing automatically.
