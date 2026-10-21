# Offline two-draw matched development aggregation

This implementation follows the analysis specification frozen in the second
[matched draw plan](../audit/cot_restart_replication_plan_20261013/plan.json).
Both real draws have completed. It reads saved original records and per-draw
replays; no tokenizer/model loading, inference, threshold fitting or new budget
is needed. The observed 12 questions remain exposed development.

Verify both exact plans against current generation/runtime/history identities,
the complete real journals/records against each plan, and every saved analysis
artifact and source/renderer hash. Require exactly draw 0 and draw 1 with the
same prompts/caps/groups and disjoint registered seed identities. Check each
replay's cap, retained token count, finish flag and path-token sum against raw
IDs, then recompute per-draw summary tables from replay rows. Reject incomplete,
synthetic, duplicate, changed or incompatible inputs before writing any output.

For each question, arm and M/D point, average correctness and token costs across
the two draws. The point estimate is the mean over questions of these values;
fractional correctness is expected and is not a new binary paired table.
Preserve per-draw b/c and nominal Tango intervals separately. Average within
question before resampling, rather than pooling 24 question-draw observations.

Use the registered 2,000 bootstrap samples and seed 20261013. Sort original
group identifiers, sample the original number of groups with replacement using
Python's standard random generator, and retain every question member of each
sampled group. All arms, both observed draws and all metrics share these same
group samples. Compute question-weighted means within each resample, accounting
for changing group sizes. Report paired percentile 95% intervals with linear
interpolation. One original group yields no interval. The intervals are
descriptive, unadjusted and conditional on the two observed draws and fixed
bases; they do not estimate variability over a population of new seeds or
uncertainty from fitting a policy.

M at registered L_i remains the primary point. M +/-8 receives no extra
interval, is not averaged into M and does not add independent observations.
Save per-question/per-draw arm correctness, finish and parse status together
with the paired differences at all three caps. Mean new completion costs and
conditional path costs are reported separately. D retains the historical base
count/EOS limitation. These are token counts, not measured FLOPs/billing/full
inference costs. Collection time at the larger caps is not online replay-point
latency. No lambda, practical margin, automatic GO/NO-GO, mechanistic prefix,
held-out-quality or Stage 0 claim is introduced.

Use a new output directory:

```bash
python3.12 -m scripts.aggregate_cot_restart_matched \
  --input audit/cot_restart_matched_plan_20261013 \
          audit/cot_restart_matched_real_20261013 \
          audit/cot_restart_matched_analysis_20261013 \
  --input audit/cot_restart_replication_plan_20261013 \
          audit/cot_restart_replication_real_20261013 \
          audit/cot_restart_replication_analysis_20261013 \
  --output audit/NEW_MATCHED_AGGREGATE
```

Outputs are `summary.json` (per-draw and combined metrics, sensitivity),
`question_means.json`, `bootstrap_distribution.json`, `report.md` and a
`manifest.json` linking all input/output/analysis-source hashes. Inputs are
checked again before saving. Human/publication review remains required.
This is supplementary offline postprocessing; actual collection continues to
use `python -m experiments.research_study`.
