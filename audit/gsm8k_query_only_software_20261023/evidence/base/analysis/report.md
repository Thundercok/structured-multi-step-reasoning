# Query-only GSM8K development baseline

Evidence: **synthetic_routing_software_check**

27 declared rules; fitting=train, development validation=calibration. Lambda=0.1 is specific to this development comparison.
Selection and fixed reference were durably saved before validation scoring. No main H1 or held-out test evaluation.
Synthetic inputs validate software only. Generated tokens exclude prompt/tool/full inference costs; replay timing is not online latency.
Bootstrap intervals are descriptive, conditional on the selected rules and observed seed; human/publication review remains pending.

Selected rule collapsed to a constant: **False**.

| Method | Correct/items | Groups | Mean generated tokens | Mean prompt tokens | Utility | PAL execution failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| query_only_rule | 4/4 | 4 | 55.000 | 5.000 | 0.994500 | 0 |
| selected_fixed_reference | 4/4 | 4 | 300.000 | 5.000 | 0.970000 | 0 |
| fixed_direct | 2/4 | 4 | 10.000 | 5.000 | 0.499000 | 0 |
| fixed_cot | 2/4 | 4 | 100.000 | 5.000 | 0.490000 | 0 |
| fixed_pal | 4/4 | 4 | 300.000 | 5.000 | 0.970000 | 0 |

Primary contrast: query-only rule minus the fixed reference chosen on fitting.

- accuracy: 0.000000; descriptive 95% interval [0.0, 0.0]
- generated_tokens: -245.000000; descriptive 95% interval [-290.0, -200.0]
- utility: 0.024500; descriptive 95% interval [0.02, 0.029]

Collection costs include all three recipes; selected-path costs include exactly one. No winning comparator is chosen on validation.
