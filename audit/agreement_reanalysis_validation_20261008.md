# Agreement correction — offline validation, 2026-10-08

Assessment: share with development caveats; not confirmatory/publication-ready.
The statistical-analysis, analysis-validation and debugging checks drove a
same-statistic regression fix, explicit undefined denominators, provenance
preservation and narrower interpretation. No new model call, GPU/runtime load,
download, prospective-test evaluation, commit, push, pull or reset was performed.
Unrelated/concurrent edits, including RAT changes, were left untouched.

Fresh [report](agreement_reanalysis_20261008/report.md),
[manifest](agreement_reanalysis_20261008/manifest.json),
[OOF/bootstrap records](agreement_reanalysis_20261008/cv.json) and
[per-item replay](agreement_reanalysis_20261008/policy_rows.json).
The [correction protocol](../docs/agreement_reanalysis_protocol_20261008.md)
is retrospective, not a replacement preregistration.

## Corrected development findings

All figures below are **EXPLORATORY**, using 100 exposed questions/groups:
arith 40, order 31, g24 29. Source generations were historical measurements;
scoring and routing here are offline retrospective replays.

- Order PAL-count signal: baseline mean-repeat AUROC 0.7175, signal
  0.858181818181818, Δ 0.14068181818181802. The corrected mean-repeat paired
  group interval is [0.022146865325077817, 0.2775315656565657], not the old
  interval obtained by ranking averaged OOF predictions. This meets only an
  **individual, unadjusted diagnostic**, not a global preregistration pass.
- Arithmetic and g24 PAL targets are single-class; their AUROC is undefined,
  not zero. The prereg's arith-and-order vs order-only conflict remains open.
- Order W: 23/31, legacy token proxy 915.9677419354839; G1: 22/31,
  2406.064516129032; G2: 22/31, 2228.483870967742. These pairwise-agreement
  policies do not implement the four-arm PAL-count signal. Do not infer that
  every agreement policy fails or that a verifier is the only solution.
- g24 plurality agreement ≥2: 16 correct among 17 agreements (94.1176%),
  not 16/16. PAL-pair agreement has 0/0 precision: JSON null and table N/A.
  g24 keys already use `check24`; this is validity-assisted agreement.
- Four-arm PAL-count needs all historical arms, not a free early gate. Full
  repeated prompt cost cannot be recovered from candidate-selection telemetry;
  all cost tables explicitly say **legacy token proxy**. Online efficiency and
  VGC superiority are not established.
- Shared incorrect parsed answers are listed without assigning an unreviewed
  mechanism by task family. Original parsed/raw-score and termination limits
  remain visible.

## Reproduction and software checks

```bash
python3.12 -m experiments.research_study --agreement-analysis --output audit/agreement_reanalysis_20261008
```

The command above already produced the saved directory; use a new path to
reproduce. Existing directories, collection overrides and unpinned inputs reject
before output creation. The old no-argument script cannot overwrite AJ reports.

```bash
python3.12 -m pytest tests/test_agreement.py -q
```

38 passed in 11.18 s, including a complete writer run in a temporary directory.
Checks cover the mean-AUC vs AUC-of-mean counterexample, ties, exact paired
bootstrap agreement with a direct AUROC calculation, repeated group variants,
group-isolated folds, deterministic results, constant-label training folds,
invalid joins/telemetry, undefined precision, output preservation and no native
MLX imports.

```bash
python3.12 -m pytest tests/test_agreement.py tests/test_order_certificate_pilot.py tests/test_order_certificate_study.py tests/test_verified_pal_order.py tests/test_procedural_research_data.py tests/test_research_study.py tests/test_research_scoring.py tests/test_research_pilot.py tests/test_research_aggregate.py test_optimal_stopping.py test_entry_predictor.py -q -p no:cacheprovider
```

225 passed in 29.35 s. This is the relevant selection, not the entire repository.
It includes the required research-harness regression files. `git diff --check`
passed. Passing software tests are not measured model-quality evidence.

The required selection was also run separately with
`python3.12 -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q -p no:cacheprovider`:
29 passed in 3.44 s.

Independent inspection of the saved run (not the analyzer's kernel) recomputed
the first 50 accepted bootstrap draws for order and pooled using direct
`roc_auc_score` in all 20 repetitions: **100/100 matched**. Every saved point
estimate and percentile CI recomputed correctly. All ten artifact hashes, six
source hashes, three measured-input hashes and six historical hashes matched.
The original five AJ text files, raw traces, development data and prereg have
the same SHA-256 bytes as before this correction.

## Remaining research work

Keep agreement as a baseline/possible auxiliary signal. Review the deployable
checker and full per-call token adapter before a small raw-artifact development
pilot when resources permit; review data, inference and execution freeze before
confirmation. No automatic real-model run was authorized here. Stage 0 is
unchanged. Historical source hashes stay historical after source edits; never
rewrite old manifests to make them match a newer analyzer/CLI.
