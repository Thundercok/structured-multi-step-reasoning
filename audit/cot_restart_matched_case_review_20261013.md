# Matched pilot: F rescue/harm case review

Exposed development evidence, one draw per arm, q=0.50. This review uses the
saved M replays and independent exact arithmetic/enumeration. No model calls,
weights or tokenizer loading were needed. Raw collection artifacts remain the
source of the generated answers; this is an agent review, not human publication
approval.

Sources: [paired replay report](cot_restart_matched_analysis_20261013/report.md),
[replay rows](cot_restart_matched_analysis_20261013/replays.json), and
[rescue/harm diagnostics](cot_restart_matched_diagnostics_20261013/report.md).
Rescue and harm refer to the same saved historical base answer: five wrong and
seven correct. They are outcome-selected diagnostics rather than estimates of
a population treatment effect.

| Case | M observation | Independent check |
| --- | --- | --- |
| `order_0006_en_orig` | F rescues with `Frank`; A reaches length; CONT answers `5`. | Exhaustive enumeration of all 120 runner permutations leaves six valid orders, all with Frank fifth. The requested answer is the runner's name. |
| `g24_0014_en_orig` | F rescues with `9 * 4 - 3 * 4`; A and CONT reach length. | The expression equals 24 and uses 9, 3, 4, 4 exactly once. |
| `g24_0023_en_orig` | F rescues with `(7 - 12 + 9) * 6`; A and CONT also rescue. | All three returned expressions equal 24 and use 7, 6, 9, 12 exactly once. This case supplies no arm-specific rescue evidence. |
| `arith_0032_en_orig` | F harms with `49835799`; A and CONT retain `49835709`. | Exact rational evaluation gives 13361, 9729, 3861, 663, 53703, 17901, 5746, 551616, 503391, then 49835709. F's final multiplication is 90 too high. |

These checks support the recorded answer labels. They do not identify a causal
mechanism for prefix retention, restart wording, or removal of an erroneous
tail. CONT's sole M rescue is the shared G24 case above, with a length-finished
historical base. Its answer requires 408 new sampled tokens; the D(w=1) cap is
324, so that replay does not rescue the case.

The recommended next development step is one further independent draw for
each of the same 12 questions and A/F/CONT arms: 36 additional calls, with q,
prompts, model, decoding settings and M/D caps fixed. Freeze the new seed
identities and a concrete resource allowance before collection. The current
36-call authorization is already consumed; this review does not initiate a
new batch or change the frozen collector sources.

Report each draw separately and, if aggregating, average outcomes within each
question before paired group resampling. Two draws still contain 12 questions;
replayed cap points are also repetitions of the same draw. This small exposed
set remains diagnostic even after replication. Formal study planning requires
fresh reviewed groups, a preregistered primary contrast/decision rule and cost
scope, and a separate power assessment. Stage 0 is unchanged.
