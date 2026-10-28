# Entry predictor — exploratory development evaluation

Evidence: **synthetic_development_cv**
Input token scope: synthetic token units

Calibration fits stopping only. Group-isolated outer CV scores train only; held-out test outcomes are excluded.
No model calls, no configuration selection, no Stage 0 change. Synthetic inputs provide no model-quality evidence.

| Method | Accuracy | Mean cost (k units) | Utility | Mean per-repeat log-loss |
| --- | ---: | ---: | ---: | ---: |
| fixed_LADDER | 0.8750 | 1.8000 | 0.8390 | 0.6548 |
| fixed_PAL | 0.4167 | 0.3000 | 0.4107 | 0.6548 |
| fixed_REACT | 0.4583 | 0.6000 | 0.4463 | 0.6548 |
| old | 0.8750 | 1.6750 | 0.8415 | 0.5309 |
| pca32 | 0.9583 | 1.2167 | 0.9340 | 0.5092 |
| scaler_only | 0.9167 | 0.8583 | 0.8995 | 0.4985 |
| training_base_rate | 0.8750 | 1.8000 | 0.8390 | 0.6548 |

Exploratory group bootstrap of repeat-averaged OOF outcomes, conditional on the recorded generation draw, calibration policy and fitted CV models. Shared training-fold dependence and refitting/selection uncertainty are not covered.

Intervals and paired differences for accuracy, cost, utility and log-loss are in summary.json; no significance labels are assigned.
Fixed routes' log-loss uses the same training-only base-rate probabilities. Hindsight fixed/oracle values are descriptive only.
Costs sum generated-token counts along the selected route and divide by 1000; smoke counts are synthetic units. Prompt/full inference costs and online latency are not measured.
Negative Ridge cost predictions remain unclipped to match the shared predictor; realized route costs come from frozen attempts.
Input manifests retain their original source hashes. Current evaluator sources are fingerprinted separately; this is a new retrospective development analysis, not a historical-source verification pass.
