# CoT restart preflight: artifact QA

Assessment: **share with caveats as CPU-only preparation**. The package is not
ready for model execution, probe training, or a scientific headroom claim.

Reviewed package: [report](cot_restart_preflight_20261009/report.md),
[manifest](cot_restart_preflight_20261009/manifest.json),
[protocol draft](../docs/cot_restart_preflight_protocol_20261009.md).

## Verification

- Both exposed input SHA-256 values are unchanged from the pinned Run 11 review.
- All manifest input, analysis-source, tokenizer and output hashes match.
- Independent Ruby JSON/string checks verified all 400 checkpoint prefixes
  against the exact original raw-output substring and source line.
- All 400 model_input payloads contain only the matching query and prefix;
  gold/outcome annotations are separate. This verifies field separation, not
  that a rationale cannot mention an answer or contain a substantive error.
- All 100 CoT records remain in the denominator. The failure-profile counts
  and historical correct count reproduce the source; no duplicate item IDs.
- Canonical groups do not cross the new dev_fit/dev_eval halves (51/49).
  Both halves are already exposed development, not independent test data.
- Tokenization discrepancies are exactly -1 in 77 records, 0 in 23. This is
  compatible with an omitted stop token, but generated token IDs are absent:
  the cause and exact original token sequence were not independently verified.
- Menu cardinalities are 4 for 52 traces, 3 for 15, and 2 for 33. The 48
  collapsed menus require deduplication or explicit treatment before collection.

## Observed population

| Observation | Count |
| --- | ---: |
| CoT traces / canonical questions | 100 / 100 |
| Historical and retrospectively typed correct | 58 |
| Wrong stopped answers with accepted format | 18 |
| Truncated traces | 23 |
| Stopped trace with rejected answer format | 1 |
| Checkpoint review candidates | 76 |
| Candidate wrong: arithmetic / ordering / Game-of-24 | 9 / 7 / 2 |

These are preparation/scoring descriptions, not repairability labels.
Format and truncation categories describe visible contract failures, **not
exclusive root causes**: reasoning errors can coexist with either category.

## Prefix spot checks

- `arith_0000_en_orig`: .5 and .75 produce the same prefix. There are only three
  distinct menu points, not four independent arms.
- `arith_0024_en_orig`: requested fractions map close to .270/.497/.748; the
  retained rationale includes the incorrect subtraction 11314 - 11147 = 1767
  (the actual subtraction is 167). This demonstrates that a text checkpoint
  is not certification of a correct prefix; no restart benefit was measured.
- `arith_0025_en_orig`: the nonzero menu points all map to .035 because most
  calculation lines have no sentence-ending punctuation. Boundary preparation
  is incomplete for this style, and the repeating-decimal final answer also
  fails the typed output contract. Do not attribute the case solely to format.
- `order_0003_en_orig` and `g24_0024_en_orig`: sampled checkpoint ends match
  complete source-text sentences and exclude the explicit final-answer block.
  Semantic step boundaries and prefix correctness still need human review.

## Software validation

```bash
python3.12 -B -m pytest tests/test_cot_restart_preflight.py \
  tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q
```

Result: **44 passed**. Tests cover source consistency, exact substrings, label
separation, punctuation edge cases, grouping, truncation, denominator retention,
cost-proxy aggregation, artifact hashes and refusing existing output paths.
They do not measure repair quality, certify model provenance, or change Stage 0.

No model/GPU job, download, calibration/test evaluation, or generation occurred.
The open LaTeX document, historical runs and unrelated worktree edits were left
unchanged. A repository-wide whitespace check reported a pre-existing extra
EOF blank line in `rat/ui/preview_panel.py`; it was not changed. New files pass
their scoped whitespace check.

## Required next step

Review boundary handling and an actual continuation/prefill contract, then
request approval for a tightly capped development feasibility pilot. Include
both correct and wrong starting answers; a wrong-only diagnostic cannot measure
harm or define a deployable repair trigger. Keep collection/labeling costs
separate from deployed-policy costs. Do not start a model run from this package.
