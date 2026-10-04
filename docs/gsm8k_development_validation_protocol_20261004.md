# Next development comparison — prepared 2026-10-04

Status: data candidate and prospective design only. No new model generation,
rule fitting, validation result or main-study claim has been produced.

## Decision to answer

Can a simple rule using only question length select among DIRECT, CoT and PAL
more usefully than a fixed strategy on separate development groups? This is a
minimum routing baseline before adding learned entry selection or stopping.
The existing 23-question pilot motivates the question; it cannot evaluate the
new rule independently.

## Data and review

- Use the pinned, already archived GSM8K **training** file at revision `3101c7d5072418e28b9008a6636bde82a006892c`. The official test remains unused.
- Exclude all 24 original candidate normalized question identities, including the excluded walking question, before selecting new groups. Preserve original line numbers/IDs rather than renumbering filtered rows.
- SHA-256 ranking with seed 42 selects 96 new groups without consulting answers or model outcomes. Alternating ranks assign 48 to each development role.
- In the existing pilot schema, `split=train` supplies **rule fitting** and `split=calibration` supplies **development validation** for this comparison. The latter is not used to fit stopping thresholds or probability calibration. No full-policy fitting call is made. Both remain development data, with `role=development_tuning`; the main-study runner rejects this pool.
- The candidate is `data/gsm8k_development_validation_candidate_v1/dataset.json`. Structural/numeric extraction checks are complete; query-derived gold checks, wording assumptions, semantic groups and human review remain pending.
- Record exclusions/assumptions before generation. Do not replace questions after seeing outcomes. If review changes the retained groups, issue a new release and freeze its hashes before collection.

96 is a manageable development screening size, not a power calculation for
publication. Repetitions/strategies do not increase the independent group count.
The 48 validation groups will give imprecise effects; main-study sizing requires
a separate precision/power justification and reviewed grouped data.

## Frozen candidate rule family

Feature: whitespace-separated word count of the original question, before any
strategy suffix. No answer, source solution, confidence, generation or embedding
is available to this rule at inference.

Candidate cutoffs: **20, 40, 60, 80 words**. For each ordered pair of different
actions from DIRECT/CoT/PAL, choose the first when word count is at most the
cutoff and the second otherwise. Include the three constant actions: 27
candidates in total. Exactly one strategy is selected; there is no escalation,
repair, repeated generation or stopping component.

Choose one rule using fitting groups only, maximizing
`accuracy - 0.1 * mean_generated_tokens / 1000`. The value 0.1 is the named
development comparison's prospective utility weight; it does not freeze the
main-study lambda. For ties: higher accuracy, lower mean generated tokens,
constant before conditional, then lexical candidate ID.

Choose the primary fixed comparator on the same fitting groups with the same
utility/tie order. Save both selections, candidate scores, fit-group IDs,
protocol/data/record hashes and rule version before inspecting validation
scores. Include all three fixed conditions in the eventual table, but do not
choose the primary comparator from the validation outcomes.

## Collection and evaluation

After data review, collect the three fixed conditions using the supported
`python -m experiments.research_study --pilot` entry point: same verified local
Qwen snapshot, `english-math-v1`, temperature 0, thinking disabled, seed 42,
cap 1,024 per call, one PAL execution with the existing 5-second timeout.
This is 288 conditions at most before any pre-generation exclusions; no model
download, embeddings, personal-file indexing or Qt. Pin clean source first.

Collection caches all strategy outputs for replay, including its descriptive
pilot report. Do not use that report to select/modify the rule: fitting reads
only fitting-group outcomes, and validation is inspected after selections are
saved. Changing validation outcomes must not change either fitted selection;
verify this with a label-poisoning software test before measured use.

Evaluate once on the remaining groups using the same cached outputs. Report
accuracy, generated/prompt tokens, utility, chosen strategy counts, paired
rescues/harms and PAL execution failures. Token cost of the selected rule path
includes its chosen strategy only; collection cost includes all three. Tool
time is separate and included in measured strategy duration. Replayed strategy
duration excludes router overhead and does not measure online controller latency.

Primary contrast: fitted simple rule minus the fixed comparator selected on
fitting. Report paired differences and descriptive 95% percentile intervals
from 2,000 bootstrap draws of validation groups, seed 42. These intervals are
conditional on the selected rule/seed and do not include fitting uncertainty.
One greedy draw does not establish robustness across generation seeds. If a
rule is a constant action, report that collapse explicitly.

If the rule supplies no useful improvement, retain the result and reconsider
features/scope on a new development comparison. Do not repeatedly select rules
on these validation results and then describe them as independent. Entry plus
stopping, prior-art novelty and publication evaluation remain later questions.

## Preparation

```bash
python -m scripts.prepare_gsm8k_development \
  --source audit/gsm8k-source-20261004 \
  --exclude-dataset data/gsm8k_development_v1/dataset.json \
  --count 96 --seed 42 --output data/NEW_VALIDATION_CANDIDATE
python -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py tests/test_gsm8k_development.py -q
```

Current deliverable: reviewable candidate and disjointness evidence. The rule
fitter/evaluator is specified here and has not yet been implemented or run.
Stage 0 and the publication/main-study review requirements are unchanged.
