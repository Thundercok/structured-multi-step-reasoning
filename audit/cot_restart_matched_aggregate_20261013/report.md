# Two-draw matched development aggregate

72 completed real calls; 12 exposed questions/12 original groups, two draws per arm.
No new inference. Average draws within question before paired group bootstrap.

| Point | A mean accuracy | F mean accuracy | CONT mean accuracy |
| --- | ---: | ---: | ---: |
| M_minus8 | 45.8% | 70.8% | 66.7% |
| M | 45.8% | 70.8% | 66.7% |
| M_plus8 | 45.8% | 70.8% | 66.7% |
| D_w0 | 58.3% | 70.8% | 66.7% |
| D_w1 | 58.3% | 70.8% | 58.3% |

| Point | Contrast | Delta accuracy (pp) | Paired group percentile 95% CI (pp) | Delta path tokens |
| --- | --- | ---: | --- | ---: |
| M_minus8 | CONT-A | +20.8 | descriptive sensitivity only | +29.0 |
| M_minus8 | F-A | +25.0 | descriptive sensitivity only | -76.0 |
| M_minus8 | F-CONT | +4.2 | descriptive sensitivity only | -105.1 |
| M | CONT-A | +20.8 | [+4.2, +37.5] | +27.0 |
| M | F-A | +25.0 | [+4.2, +45.8] | -78.4 |
| M | F-CONT | +4.2 | [-8.3, +16.7] | -105.4 |
| M_plus8 | CONT-A | +20.8 | descriptive sensitivity only | +25.0 |
| M_plus8 | F-A | +25.0 | descriptive sensitivity only | -80.7 |
| M_plus8 | F-CONT | +4.2 | descriptive sensitivity only | -105.8 |
| D_w0 | CONT-A | +8.3 | [-16.8, +33.3] | -601.9 |
| D_w0 | F-A | +12.5 | [-12.5, +33.3] | -469.8 |
| D_w0 | F-CONT | +4.2 | [-8.3, +16.7] | +132.1 |
| D_w1 | CONT-A | +0.0 | [-33.3, +29.2] | -238.7 |
| D_w1 | F-A | +12.5 | [-12.5, +33.3] | -239.0 |
| D_w1 | F-CONT | +12.5 | [-4.2, +33.3] | -0.3 |

| Point | Arm | Mean new completion tokens | Mean conditional path tokens |
| --- | --- | ---: | ---: |
| M | A | 714.4 | 1507.7 |
| M | F | 374.6 | 1429.3 |
| M | CONT | 217.2 | 1534.8 |
| D_w0 | A | 925.2 | 1457.5 |
| D_w0 | F | 455.4 | 987.7 |
| D_w0 | CONT | 323.2 | 855.6 |
| D_w1 | A | 857.9 | 1651.2 |
| D_w1 | F | 357.5 | 1412.2 |
| D_w1 | CONT | 95.0 | 1412.5 |

Unique M +/-8 outcome-sensitive questions across both draws: 0/12.
M correctness differs between draws on {'A': 7, 'F': 3, 'CONT': 0} questions per arm.
Per-draw paired tables/nominal Tango intervals remain in summary.json; fractional means do not receive binary Tango intervals.
Intervals are descriptive, unadjusted, conditional on these observed draws/fixed bases and resample only original groups.
They do not estimate uncertainty over a population of new generation seeds or fitted policies.
The 12 questions, two draws and replayed caps are not pooled as independent observations.
D retains historical base counts with an unverified EOS convention; costs are token counts, not FLOPs/billing/full inference costs.
Collection time at the larger caps is not online latency at replayed M/D caps.
No lambda/practical margin, formal GO/NO-GO, mechanistic, held-out-quality or Stage 0 conclusion is enabled.
Human/publication review remains pending.
