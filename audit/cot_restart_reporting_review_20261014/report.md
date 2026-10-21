# Retrospective reporting review

Aggregation rules were pre-specified in audit/cot_restart_replication_plan_20261013/plan.json (SHA-256 132f850d304de9e7026a5cc42ac65691ac3249e3d4eb4315f9c1a28436925bd6); aggregator code was written after the second-draw report was read. Implementation details and added cost intervals were selected after inspection. An independent NumPy re-implementation checked computation, not pre-specification. All results are exploratory.

First-draw standalone regression exactly matches all five saved tables; second-draw outcomes were not needed for that check.
Tests and NumPy validate implementation, not independence of analytic choices from inspected outcomes.

Draw indices 0 and 1 below mean the first and second collected draws, respectively.

| Draw | M stratum | n | F-A b | c | Net contribution across all 12 questions (pp) |
| --- | --- | ---: | ---: | ---: | ---: |
| 0 | base_correct | 7 | 3 | 1 | +16.7 |
| 0 | base_wrong | 5 | 2 | 1 | +8.3 |
| 1 | base_correct | 7 | 2 | 0 | +16.7 |
| 1 | base_wrong | 5 | 1 | 0 | +8.3 |

Base-outcome strata are descriptive subsets, not population treatment effects. Full M/D/arm/O tables and item IDs are in strata.json.
O is the fixed historical stop/no-extra-call answer, not a second fresh arm. Its 7/12 baseline is shared by both draws; quality comparisons do not imply equal costs.

| Arm | M draw disagreement | CP 95% |
| --- | ---: | --- |
| A | 7/12 | [0.2767, 0.8483] |
| F | 3/12 | [0.0549, 0.5719] |
| CONT | 0/12 | [0.0000, 0.2646] |

M +/-8 unique-question boundary count: 0/12, CP 95% [0.0000, 0.2646].
The denominator is questions, not the correlated arm/cap/draw cells. This does not certify D sensitivity.

| Point | Contrast | Exhaustive assignments | Two-sided sign-flip p |
| --- | --- | ---: | ---: |
| M | CONT-A | 4096 | 0.125000 |
| M | F-A | 4096 | 0.109375 |
| M | F-CONT | 4096 | 1.000000 |
| D_w0 | CONT-A | 4096 | 0.765625 |
| D_w0 | F-A | 4096 | 0.507812 |
| D_w0 | F-CONT | 4096 | 1.000000 |
| D_w1 | CONT-A | 4096 | 1.000000 |
| D_w1 | F-A | 4096 | 0.507812 |
| D_w1 | F-CONT | 4096 | 0.500000 |

Sign-flip p values assume groupwise sign exchangeability, beyond a weak zero-mean null; enumeration is exhaustive, descriptive and unadjusted.
No practical margin/utility, confirmatory decision, superiority, mechanism or Stage 0 result is established.
CONT is the active continuation comparator for restart benefit. O is the required stop baseline for deployment value; A is a reset/resample ablation.
Deployment comparisons require matched total budget/cost scope and online measurement; historical base EOS counts remain unverified.
