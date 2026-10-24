# Independent query-only baseline review — 2026-10-24

Verdict: **no new blocking defect found in the reviewed fitting/evaluation
logic**. This is a scoped software review, not approval to collect or inspect
the real candidate. Inference/embedding calls: 0. Candidate questions, source
solutions and outcomes: not accessed. Bridge acceptance and Stage 0 unchanged.
No production implementation or protocol was edited in this review.

## Scope and evidence

Reviewed `experiments/gsm8k_routing_baseline.py`, its supported CLI dispatch,
the relevant pilot/replay and atomic-write contracts, tests and the existing
[development protocol](../../docs/gsm8k_development_validation_protocol_20261004.md).
Applied the engineering code-review skill. Independent means a separately
written reference calculation in this chat, not a second human reviewer or
independent model/agent.

Fresh regression command:

```bash
.venv/bin/python -m pytest tests/test_gsm8k_routing_baseline.py tests/test_research_pilot.py tests/test_gsm8k_development.py tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q
```

Observed result: **81 passed in 19.95s**, exit 0. This includes the mandatory
research checks. Tests use authored fixtures, not measured model outcomes.

Additional reproducible probe:

```bash
.venv/bin/python audit/gsm8k_query_only_independent_review_20261024/probe.py
```

[Probe results](probe_results.json) record source hashes. One hundred randomized
authored banks matched an independently enumerated 27-rule menu, integer
utility ranking (`10000 * correct - generated_tokens`, common sample count),
tie ordering and fixed-comparator selection. All 324 menu/boundary checks
matched, including cutoff equality and mixed whitespace. An unequal-size
three-group example matched all reported percentile interval endpoints using
2,000 whole-group resamples and explicit linear interpolation. This checks
implementation of the declared estimator, not its statistical coverage/power.

## Protocol correspondence

| Requirement | Source/readback and verification | Conclusion within scope |
| --- | --- | --- |
| Original-query word count, exactly 27 rules | `Rule.choose`/`candidate_rules`, independent boundaries/menu | Matches |
| Fit only on train outcomes | `fit_selection` filters records by fitting IDs; existing blind/poisoned-validation tests | No validation-outcome dependence found; validation query metadata is inspected for frame checks |
| Utility and tie order | Exact fractions in production; independent integer oracle and existing tie fixture | Matches lambda 0.1, accuracy, tokens, constant, lexical ID order |
| Fixed comparator selected on fitting | Restricted constant-rule scores, independently checked | Matches; no winner selected from validation |
| Durable selection before validation scoring | `write_analysis` atomic selection and selection_saved manifest precede evaluator; failure test rerun | Matches normal process/exception contract; not a power-loss filesystem durability test |
| Paired effects and group bootstrap | `paired_comparison`, unequal-group reference calculation, one-group test | Matches; variants retain question weights, intervals conditional/descriptive |
| Collection versus selected-path cost | All three recipes in full bank; exactly one selected record per query | Matches; prompt tokens separate, stored strategy duration is replay timing |
| Failure/tamper/overrides | Existing negative and failure-after-selection tests rerun | Tested failures remain failures and keep selection where applicable |

No actionable inline finding is emitted for the reviewed algorithm. This does
not establish correctness outside tested contracts or approve candidate data.

## Remaining pre-collection decisions

The [readiness dossier](../../docs/gsm8k_development_review_readiness_20261023.md)
continues to apply. In particular, the generic pilot collector writes a
completed record only after `backend.run` and record validation; it flushes
without a per-record fsync and has no partial-run resume. Started/failed calls
can lack completed cost records. This existing limitation was rechecked in
source; it is not a newly demonstrated fitter bug. Review the accounting and
recovery contract before authorizing collection; do not silently retry a bank.

The descriptive pilot report exposes both development roles. Automated
fitting does not consume validation outcomes, but it cannot prevent a person
from viewing them in the collection report. Name who holds those artifacts,
record access/exposure and pin selections before validation inspection. Do
not claim technical blinding from the poisoning test alone.

Gold/wording/semantic-group/human/source review, model-content revalidation,
clean source/configuration pinning and an explicit collection budget remain
pending. A source hash is integrity evidence, not human review. Proposed
288-call/294,912-generated-token envelope remains unallocated; budget is 0.
The SoL-Pi backlog and Anti's checker work are outside this review. The next
research preparation step is a concrete collector accounting/recovery and
validation-access design on authored fixtures, before opening candidate data.
