# Reasoning research run

Evidence: **synthetic_smoke**

These are paired replay estimates from frozen strategy outputs. They do not measure online end-to-end latency.
Synthetic runs only validate the experiment software; they provide no evidence of model quality.

| Method | Test N | Accuracy | Mean tokens | Utility | Escalation |
| --- | ---: | ---: | ---: | ---: | ---: |
| entry_without_escalation | 24 | 0.583 | 300.0 | 0.577 | 0.000 |
| fixed_cot | 24 | 0.458 | 300.0 | 0.452 | 0.000 |
| fixed_pal | 24 | 0.375 | 300.0 | 0.369 | 0.000 |
| fixed_react | 24 | 0.292 | 600.0 | 0.280 | 0.000 |
| fixed_self_consistency | 24 | 0.417 | 1500.0 | 0.387 | 0.000 |
| fixed_tot | 24 | 0.625 | 5000.0 | 0.525 | 0.000 |
| full_policy | 24 | 0.792 | 1966.7 | 0.752 | 0.417 |
| ladder_only | 24 | 0.708 | 2841.7 | 0.652 | 0.583 |
| one_shot_router | 24 | 0.792 | 400.0 | 0.784 | 0.000 |

Differences below are full policy minus baseline. Accuracy is on the 0–1 scale; negative token differences mean fewer tokens.
Intervals resample problem groups and are conditional on this fitted policy and generation seed.

| Baseline | Metric | Mean difference | Paired 95% interval |
| --- | --- | ---: | --- |
| one_shot_router | correct | 0.0000 | [-0.20833333333333334, 0.20833333333333334] |
| one_shot_router | tokens | 1566.6667 | [645.7291666666667, 2625.0] |
| one_shot_router | utility | -0.0313 | [-0.2527708333333334, 0.1863499999999999] |
| fixed_self_consistency | correct | 0.3750 | [0.16666666666666666, 0.5833333333333334] |
| fixed_self_consistency | tokens | 466.6667 | [-491.6666666666667, 1550.5208333333305] |
| fixed_self_consistency | utility | 0.3657 | [0.14400000000000002, 0.5873437499999999] |
| entry_without_escalation | correct | 0.2083 | [0.041666666666666664, 0.375] |
| entry_without_escalation | tokens | 1666.6667 | [708.3333333333334, 2750.5208333333303] |
| entry_without_escalation | utility | 0.1750 | [0.025822916666666664, 0.3375104166666666] |

Token scope: synthetic token units. All invoked strategy costs are added.
Strategy timings and embedding overhead are logged separately. Router execution, model loading, and live scheduling are not included in replay latency sums.
The legacy TOT identifier denotes candidate generation and selection in the MLX adapter, not a full tree search.
The one-shot router is an internal baseline, not a reproduction of Route-to-Reason.
Publication needs reviewed data/answers, pinned model provenance, multiple generation seeds, prior-art comparisons, and a separate online timing run.
