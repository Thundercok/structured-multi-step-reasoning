# Rescue/harm development diagnostics

All 12 base correctness labels agree with retrospective typed rescoring. Denominators: 5 wrong, 7 correct.
CP intervals are unadjusted, under a binomial model; subsets were selected by the base outcome.
These are not population treatment effects. Primary evidence remains all-question A/F/CONT paired contrasts.

| Point | Arm | Rescue | CP 95% | Harm | CP 95% |
| --- | --- | ---: | --- | ---: | --- |
| M | A | 2/5 | [0.053, 0.853] | 3/7 | [0.099, 0.816] |
| M | F | 3/5 | [0.147, 0.947] | 1/7 | [0.004, 0.579] |
| M | CONT | 1/5 | [0.005, 0.716] | 0/7 | [0.000, 0.410] |
| D_w0 | A | 3/5 | [0.147, 0.947] | 3/7 | [0.099, 0.816] |
| D_w0 | F | 3/5 | [0.147, 0.947] | 1/7 | [0.004, 0.579] |
| D_w0 | CONT | 1/5 | [0.005, 0.716] | 0/7 | [0.000, 0.410] |
| D_w1 | A | 3/5 | [0.147, 0.947] | 3/7 | [0.099, 0.816] |
| D_w1 | F | 3/5 | [0.147, 0.947] | 1/7 | [0.004, 0.579] |
| D_w1 | CONT | 0/5 | [0.000, 0.522] | 0/7 | [0.000, 0.410] |

CONT rescue observables at M are recorded in diagnostics.json.
Tokens before the marker count complete tokens whose emitted text ends before the first explicit marker.
Answer changes are compared only for stop-finished bases with parsed answers; text changes are not mechanistic classifications.
Neither rescue, short visible reasoning nor a parse failure establishes a formatting-only or tail-repair cause.
