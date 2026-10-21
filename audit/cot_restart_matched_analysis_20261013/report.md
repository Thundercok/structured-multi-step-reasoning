# A/F/CONT development replay review

All 36 real records/journal entries and their original token IDs were audited. No new model calls.
Exposed development, 12 questions, one draw per arm; no GO/NO-GO decision or Stage 0 change.

| Point | A correct | F correct | CONT correct |
| --- | ---: | ---: | ---: |
| M_minus8 | 6/12 | 9/12 | 8/12 |
| M | 6/12 | 9/12 | 8/12 |
| M_plus8 | 6/12 | 9/12 | 8/12 |
| D_w0 | 7/12 | 9/12 | 8/12 |
| D_w1 | 7/12 | 9/12 | 7/12 |

| Point | Contrast | b | c | Delta (pp) | Nominal Tango 95% CI (pp) |
| --- | --- | ---: | ---: | ---: | --- |
| M_minus8 | CONT-A | 3 | 1 | +16.7 | descriptive sensitivity only |
| M_minus8 | F-A | 5 | 2 | +25.0 | descriptive sensitivity only |
| M_minus8 | F-CONT | 2 | 1 | +8.3 | descriptive sensitivity only |
| M | CONT-A | 3 | 1 | +16.7 | [-18.9, +48.5] |
| M | F-A | 5 | 2 | +25.0 | [-18.8, +59.7] |
| M | F-CONT | 2 | 1 | +8.3 | [-24.4, +39.7] |
| M_plus8 | CONT-A | 3 | 1 | +16.7 | descriptive sensitivity only |
| M_plus8 | F-A | 5 | 2 | +25.0 | descriptive sensitivity only |
| M_plus8 | F-CONT | 2 | 1 | +8.3 | descriptive sensitivity only |
| D_w0 | CONT-A | 3 | 2 | +8.3 | [-29.5, +43.7] |
| D_w0 | F-A | 4 | 2 | +16.7 | [-24.2, +52.0] |
| D_w0 | F-CONT | 2 | 1 | +8.3 | [-24.4, +39.7] |
| D_w1 | CONT-A | 3 | 3 | +0.0 | [-38.8, +38.8] |
| D_w1 | F-A | 4 | 2 | +16.7 | [-24.2, +52.0] |
| D_w1 | F-CONT | 3 | 1 | +16.7 | [-18.9, +48.5] |

M +/-8 outcome-sensitive questions: 0/12.
M +/-8 finish-sensitive questions: 0/12.

The score intervals are nominal/asymptotic, unadjusted and descriptive at n=12.
Sensitivity points reuse the same draw, remain paired, and are not pooled as independent data.
D at T*=2560 is conditional on logged historical base counts with unverified EOS convention.
Costs are sampled/prefill token counts, not measured FLOPs, billing or full inference costs.
Collection timing is from the larger collected caps; it is not online latency for M/D replay.
CONT-A measures the continuation package. F-CONT changes retained context and the restart/continuation package.
M gives every arm the same new-completion cap; D(w=1) also changes that allowance through prompt charging.
Neither contrast isolates formatting or removal of an erroneous tail. No learned locator/probe conclusion follows.

Collection: 36 calls, 19,715 completion tokens including EOS,
33,840 prompt+completion tokens; prior base collection is excluded.
