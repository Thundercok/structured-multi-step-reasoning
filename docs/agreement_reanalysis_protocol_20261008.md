# Agreement reanalysis: retrospective correction, not new preregistration

This is an offline exploratory reanalysis of the exact exposed `gen02_tune`
items and historical Run 11 / PAL-v2 outputs. It changes the analyzer and its
reporting, not the original preregistration, model outputs or Stage 0 decision.
It does not inspect or solve the prospective ordering test candidate.

The supported entry point requires a **new directory**:

```bash
python -m experiments.research_study --agreement-analysis --output audit/agreement-reanalysis-new
```

No dataset/model/seed/lambda/budget overrides are accepted. Input SHA-256 hashes
are pinned; joins reject duplicate/missing arms, mismatched identity/gold and
invalid token fields. The three measured input files, historical AJ reports and
`prereg/decision_rule_agree.md` remain unchanged. The analyzer checks that inputs,
history and its source did not change during calculation before writing output.

## Statistic and uncertainty

Retain the historical 5 grouped folds × 20 repetitions, logistic regression
with C=1, train-only standardization, split seeds 42–61 and 2,000 paired group
bootstrap draws. The target for **every** gate comparison is retrospectively
parsed PAL-v2 answer correctness. The plurality-count signal is an auxiliary
predictor of that target, not a plurality-correctness evaluation. The precision
table separately scores the answer selected by each agreement rule.

The point statistic is the mean of 20 item-pooled out-of-fold AUROCs. Each
bootstrap sample retains every variant of each sampled group, uses the same
draw for baseline and signals, recomputes each repetition's AUROC, then averages
the 20 AUROCs and subtracts baseline. It **does not** compute AUROC after
averaging predictions: ranking and averaging do not commute. A pairwise
concordance kernel with half credit for ties computes precisely the same
mean-repeat statistic with low CPU overhead.

Intervals are 2.5/97.5 percentiles conditional on fixed OOF predictions, recorded
folds and historical generations. Models are not refitted during bootstrap;
training uncertainty, dependence induced by overlapping CV training sets and
new generation-seed uncertainty are not resolved by this correction. OOF and
bootstrap arrays, feature matrices and fold assignments are saved for inspection.
Single-class bootstrap samples are discarded with a bounded retry budget and
their count retained. A single-class family has no defined AUROC: report N/A,
not a fabricated zero or a failed predictive-model test.

Four signal comparisons per evaluable family have **unadjusted**, exploratory
intervals. Meeting Δ≥0.05 and lower CI>0 is an individual diagnostic only, not
family-wise error control or a formal winning-method selection. The old prereg
requires arith **and** order but gives an order-only final verdict. Keep that
conflict review-pending; arith's all-correct PAL target cannot satisfy a binary
AUROC gate on these data. Every output has `preregistration_pass=false`.

## Semantics, costs and interpretation

- Zero agreements mean undefined conditional precision (JSON null; table N/A),
  not evidence for 0% precision. Preserve numerator and denominator.
- For g24, `check24` uses the query's numbers to map different valid expressions
  to a common validity key. This is **validity-assisted agreement**, not pure
  answer equality or a verifier-free signal.
- Four-arm `n_agree` requires PAL, CoT, candidate-selection (legacy label ToT)
  and SC outputs. The nominal collector configuration has 1+1+4+5 model calls;
  these features are not available before those computations and are not free.
- Report historical prompt+completion fields as a **legacy token proxy**, summed
  across all invoked arms. Candidate-selection prompt telemetry omits two branch
  prompts and the selector input. Full per-call input cost and online latency
  cannot be reconstructed; proxy ratios cannot establish deployment savings.
- Scoring is retrospective on parsed answers. Legacy candidate branch stop
  reasons and the selected SC winner's termination are not fully retained.
  Changed raw-score comparisons must not be called fresh model measurements.
- G1/G2 replay PAL–CoT pair agreement, not four-arm `n_agree`. Negative G1/G2
  outcomes do not rule out other agreement policies or show that a verifier is
  the only viable improvement. Incremental AUROC is not a policy-cost win.
- Shared wrong answers are observable. Automatically labelling their cause by
  task family is not independent causal review; omit such diagnoses.

## Artifacts and review

The new directory contains settings, gate/precision/replay summaries, raw CV
predictions and bootstrap deltas, per-item policy records, agree-and-wrong cases,
tables, a caveated report and a manifest with input/source/artifact hashes and
runtime versions. Completed status means the offline analysis finished; it does
not mean human/publication review, global preregistration or confirmation passed.

Quality assessment: share with the above caveats for development decisions;
do not use as confirmatory manuscript evidence. Preserve agreement as a baseline
and potential auxiliary signal. Next substantive measurement still needs reviewed
data, a deployable checker, full per-call costs and a frozen prospective protocol.
