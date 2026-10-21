# Claude follow-up: both draws complete; offline aggregate ready

This updates the earlier 15:43 snapshot in
`audit/cot_restart_handoff_claude_20261013.md`. Its 21/36 count was an earlier
observation. Antigravity has now completed draw 1 with **36/36 calls and zero
failed attempts**. All generation files and both frozen plans still verify.
No extra model calls were started by this offline review.

Draw 1 used 21,176 sampled completion tokens including EOS and 35,301 new
prompt+completion tokens, with about 34.7 minutes active collection. It has
separate raw, analysis and rescue/harm directories:

- `audit/cot_restart_replication_real_20261013/`
- `audit/cot_restart_replication_analysis_20261013/`
- `audit/cot_restart_replication_diagnostics_20261013/`

Its M A/F/CONT scores are 5/12, 8/12, 8/12. D(w=0) scores are 7/12, 8/12,
8/12; D(w=1) scores are 7/12, 8/12, 7/12. M +/-8 does not change correctness
or finish reason on any of the 12 questions.

The useful CPU follow-up is now complete: a separate matched-schema aggregator
verifies both raw journals/records, plans, source/renderer hashes and saved
analysis outputs. It checks cap/count/finish/path cost against original IDs and
recomputes per-draw tables. It averages within question, then resamples original
groups under the registered 2,000 samples / bootstrap seed 20261013. No tokenizer
or weights are loaded and no policy, lambda or practical margin is fitted.

| Point | A mean accuracy | F mean accuracy | CONT mean accuracy |
| --- | ---: | ---: | ---: |
| M | 45.8% | 70.8% | 66.7% |
| D(w=0) | 58.3% | 70.8% | 66.7% |
| D(w=1) | 58.3% | 70.8% | 58.3% |

At M, paired F-A is +25.0 pp, descriptive conditional group-percentile CI
[+4.2,+45.8] pp. CONT-A is +20.8 pp, CI [+4.2,+37.5]; F-CONT is +4.2 pp,
CI [-8.3,+16.7]. These are not binary Tango intervals on fractional seed means.
Per-draw b/c and nominal Tango intervals remain separately saved.

F-A mean new-completion difference at M is -339.8 tokens, CI [-531.8,-163.2].
With recorded prompt/base charges, its conditional path difference is -78.4
tokens, CI [-292.8,+124.5]. Thus completion-only saving cannot be described as
confirmed full-path efficiency. D retains the old base-count EOS limitation.
All costs are token counts, not measured FLOPs/billing/full inference costs;
collection time at larger caps is not online M/D latency.

Two draws still contain **12 questions/12 original groups**, not 24 independent
questions. Unique M +/-8 outcome-sensitive questions are 0/12. At M, correctness
differs between the two draws on 7 questions for A, 3 for F and 0 for CONT.
The conditional bootstrap does not capture uncertainty over a population of new
generation seeds. The set is exposed development, intervals are descriptive
and unadjusted, human/publication review is pending, and no mechanistic prefix,
held-out, formal GO/NO-GO or Stage 0 conclusion is enabled.

Both collections total 72 real calls, 40,891 completion tokens including EOS
and 69,141 new prompt+completion tokens. Aggregation added zero calls.

Reviewable outputs:

- `audit/cot_restart_matched_aggregate_20261013/report.md` — mean accuracy/cost and paired intervals.
- `audit/cot_restart_matched_aggregate_20261013/summary.json` — per-draw metrics and detailed per-question sensitivity, including D_i at each cap.
- `audit/cot_restart_matched_aggregate_20261013/question_means.json` — seed-averaged question outcomes/costs.
- `audit/cot_restart_matched_aggregate_20261013/bootstrap_distribution.json` — saved distributions for accuracy and both token scopes.
- `audit/cot_restart_matched_aggregate_20261013/manifest.json` — all input/output/analysis-source hashes.
- `audit/cot_restart_matched_aggregate_validation_20261013.json` — 42 tests passed and all 27 metric/contrast distributions and CIs independently checked with NumPy, 2,000 replicates each.

Code: `scripts/aggregate_cot_restart_matched.py`, with meaningful tests in
`tests/test_cot_restart_matched_aggregate.py`. Method and reproducible command:
`docs/cot_restart_matched_aggregate_20261013.md`. Generation sources remain
frozen; this postprocessor does not alter research collection entry points.

Next work is human review of these diagnostic results and design of a fresh
reviewed-group study with prospective decisions/cost scope and power assessment.
Do not launch a third draw, a 288-call sweep or a locator/probe fit from this
report alone. Keep original runs and unrelated RAT/DocAI changes intact.
