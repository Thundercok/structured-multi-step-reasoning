# Query-only baseline: software acceptance — 2026-10-23

**Implemented; 81 tests passed in 22.05s.** This accepts research software on
authored fixtures, not model quality, candidate data, a campaign or live RAT UI.
New model/embedding calls: **0**. No real 48/48 questions/outcomes were read or fit.
Stage 0 and human/source/publication review remain unchanged.

## Change and tested behavior

- `experiments/gsm8k_routing_baseline.py` implements the 27 candidates already
  declared in the development protocol. It selects both the rule and fixed
  comparator from fitting only, using exact utility/tie ordering.
- `experiments.research_study --gsm8k-routing-analysis` is the supported
  analysis entry point. No model is instantiated; collection/seed/lambda
  overrides, incompatible/partial/tampered banks and output overwrites fail.
- The fitter can receive validation rows whose outcome fields raise on read:
  tests confirm those fields are never accessed. Changing validation outcomes
  leaves the selection byte-identical, including all fitting scores/fingerprint.
- `selection.json` is atomically written and fsynced before validation scoring.
  A semantic validation failure preserves it and a failed manifest, without a
  fabricated successful summary. Negative validation results remain negative.
- Typed public answers and PAL's recorded tool result are checked without
  executing saved programs. Generated/prompt counts, groups, seeds and settings
  are reconciled. Collection costs include all three arms; each selected path
  contains exactly one. PAL execution failures are retained as costed outcomes.
- Paired bootstrap resamples original groups, retaining variants and their
  question weights. The interval is descriptive/conditional; one group has no
  interval. The new mode does not evaluate main H1 or fit stopping thresholds.
- Fresh-process tests run the real entry point while blocking MLX, Torch,
  embeddings and Qt imports. These research unit fixtures are not UI answers
  injected into RAT and provide no live-app acceptance.

## Evidence

- [Verification](evidence/verification.json): source/input fingerprints and
  three independently invoked CLI cases.
- `evidence/base/`: four fitting and four validation groups, authored outputs
  only; positive synthetic case by construction.
- `evidence/validation_changed/`: same fitting inputs, deliberately different
  valid validation outcomes; identical selection and negative synthetic result.
- `evidence/validation_invalid/`: inconsistent validation correctness flag;
  CLI exits with error, retaining selection/failed manifest.
- `regression.txt` and `regression.xml`: 26 new routing tests plus 55 existing
  research/pilot/data tests, including the mandatory 29 research checks.

All outcomes/token counts in these cases are synthetic software fixtures.
No percentage/utility difference from them is a measured routing improvement.
The real candidate remains review-pending, with zero inference budget allocated
by this acceptance. Existing UI/AGENTS/.gitignore work was preserved.

## Reproduce

From the repository root, into a new evidence directory:

```bash
.venv/bin/python audit/gsm8k_query_only_software_20261023/run_software_check.py --output /private/tmp/gsm8k-query-only-repeat
.venv/bin/python -m pytest tests/test_gsm8k_routing_baseline.py tests/test_research_pilot.py tests/test_gsm8k_development.py tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q
```

Use the [existing protocol](../../docs/gsm8k_development_validation_protocol_20261004.md#offline-implementation--2026-10-23)
for the real-data review/configuration prerequisites. Historical collection
source guards remain active; do not rewrite an older run's hashes to use it.
