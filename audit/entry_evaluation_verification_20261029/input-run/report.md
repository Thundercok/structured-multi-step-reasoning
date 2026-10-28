# Reasoning research run

Evidence: **synthetic_smoke**

These are paired replay estimates from frozen strategy outputs. They do not measure online end-to-end latency.
Synthetic runs only validate the experiment software; they provide no evidence of model quality.

| Method | Test N | Accuracy | Mean tokens | Utility | Escalation |
| --- | ---: | ---: | ---: | ---: | ---: |
| entry_without_escalation | 24 | 0.667 | 337.5 | 0.660 | 0.000 |
| fixed_cot | 24 | 0.458 | 300.0 | 0.452 | 0.000 |
| fixed_pal | 24 | 0.375 | 300.0 | 0.369 | 0.000 |
| fixed_react | 24 | 0.292 | 600.0 | 0.280 | 0.000 |
| fixed_self_consistency | 24 | 0.417 | 1500.0 | 0.387 | 0.000 |
| fixed_tot | 24 | 0.625 | 5000.0 | 0.525 | 0.000 |
| full_policy | 24 | 0.833 | 1462.5 | 0.804 | 0.333 |
| ladder_only | 24 | 0.708 | 2841.7 | 0.652 | 0.583 |
| one_shot_router | 24 | 0.833 | 387.5 | 0.826 | 0.000 |

Differences below are full policy minus baseline. Accuracy is on the 0–1 scale; negative token differences mean fewer tokens.
Intervals resample problem groups and are conditional on this fitted policy and generation seed.

| Baseline | Metric | Mean difference | Paired 95% interval |
| --- | --- | ---: | --- |
| one_shot_router | correct | 0.0000 | [-0.16666666666666666, 0.16666666666666666] |
| one_shot_router | tokens | 1075.0000 | [362.5, 1983.4374999999993] |
| one_shot_router | utility | -0.0215 | [-0.2014354166666667, 0.14783333333333332] |
| fixed_self_consistency | correct | 0.4167 | [0.16666666666666666, 0.625] |
| fixed_self_consistency | tokens | -37.5000 | [-787.5, 920.9374999999994] |
| fixed_self_consistency | utility | 0.4174 | [0.17470208333333337, 0.6391020833333332] |
| entry_without_escalation | correct | 0.1667 | [0.041666666666666664, 0.3333333333333333] |
| entry_without_escalation | tokens | 1125.0000 | [375.0, 2083.3333333333335] |
| entry_without_escalation | utility | 0.1442 | [0.01746875, 0.3029479166666665] |

Token scope: synthetic token units. All invoked strategy costs are added.
Strategy timings and embedding overhead are logged separately. Router execution, model loading, and live scheduling are not included in replay latency sums.
The legacy TOT identifier denotes candidate generation and selection in the MLX adapter, not a full tree search.
The one-shot router is an internal baseline, not a reproduction of Route-to-Reason.
Publication needs reviewed data/answers, pinned model provenance, multiple generation seeds, prior-art comparisons, and a separate online timing run.
