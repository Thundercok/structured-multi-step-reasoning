# CoT restart: CPU-only preflight

Assessment: share with caveats as preparation diagnostics. No model calls or repair-quality measurements.

The pinned Run 11 file has 571 records, including 100 CoT traces / 100 canonical questions. All are already exposed development, including obsolete source split labels. No new calibration or held-out dataset was opened.

## Trace inventory

| Family | Traces | Historical correct | Retyped correct | Length stops | Checkpoint candidates | Completion mean / median |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| arith | 40 | 30 | 30 | 0 | 39 | 180.0 / 165.0 |
| g24 | 29 | 14 | 14 | 13 | 16 | 549.8 / 331.0 |
| order | 31 | 14 | 14 | 10 | 21 | 595.1 / 415.0 |

Retyped scores are retrospective diagnostics with the current parser/checker, not replacements for historical scores or fresh model results.

Failure profiles: `{"correct": 58, "format_or_missing_final": 1, "truncation": 23, "wrong_final_answer_not_localized": 18}`. A wrong final answer is not a localized reasoning error.

## Checkpoint preparation

Prepared 400 rows for q = 0, .25, .5, .75. Targets are fractions of the locally retokenized reasoning body, snapped to conservative interior sentence boundaries; ties select the earlier boundary. This is a text-boundary heuristic, not identification of correct prefixes or logical steps.

Only exact source substrings are retained. The first explicit final-answer block and everything after it are excluded. Gold/outcome annotations are in observations.json; model_input contains only query and prefix. Inspect prefixes manually before any collection.

Candidate traces: 76 (58 correct / 18 wrong under retrospective scoring). Candidates still need human boundary and contract review. Non-candidates remain in the denominator and observation bundle.

Review flags (overlap allowed): `{"answer_format_needs_review": 24, "menu_prefixes_collapsed": 48, "missing_or_multiple_final_markers": 23, "source_truncated": 23}`.

Short traces can collapse several requested q values to the same prefix. Those are not independent restart arms; deduplicate by cut_char before any future allocation, and report the actual fractions.

## Token scope and cost warning

Retokenized raw-text counts disagree with saved completion counts in 77 traces. No generated token IDs or saved KV state are available in these records. Retokenization is not reconstruction of generation tokens or exact assistant-prefix replay.

The dense diagnostic matrix m_s=m_e=4 over four q values means 32 calls per trace. The ideal completion-only approximation is 20L; re-prefilling each saved prefix adds about 12L, plus 32 copies of the original query prompt (32P). Thus the simplified input+completion approximation is 32L+32P, before new wrappers/special tokens. Actual boundary snapping and answer removal differ; neither estimate is a measured cost or a hard cap.

For every trace, observations.json stores a snapped-text completion proxy and an input proxy separately. They deliberately assume all four points are evaluated; evaluating only the selected point on fresh draws would be a different, cheaper allocation to preregister.

## Development grouping

Outcome-blind canonical-question halves: `{"dev_eval": {"canonical_questions": 49, "traces": 49}, "dev_fit": {"canonical_questions": 51, "traces": 51}}`. Both halves are exposed development, not held-out test. Keep all variants and every trace from one canonical question together; bootstrap by canonical question.

## What this preflight does not establish

- No V(k,m,b), rescue/harm after repair, repairability class, menu oracle C, fixed restart F, or probe performance was measured.
- Boundary availability and software tests do not show that restart improves accuracy or cost.
- Truncation, schema failures, and wrong stopped answers must be reviewed separately; excluding any category changes the target population.
- Native thinking requires its own matched-budget baseline. Switching repairer or continuation contract invalidates reuse of value labels.
- No model weights were loaded or authenticated; only the local tokenizer was loaded. Stage 0 is unchanged.

## Next decision

Review a small, outcome-balanced set of prefixes and freeze a continuation contract with verified token accounting. Only then propose an explicitly capped development run; no generation has been authorized by this preflight. The protocol draft is docs/cot_restart_preflight_protocol_20261009.md.

## Reproduction

From the repository root:

```bash
python3.12 -B -m scripts.prepare_cot_restart --output audit/NEW_COT_RESTART_PREFLIGHT
```

The command is CPU-only, reads only the pinned exposed sources/local tokenizer, and refuses an existing output directory. It does not alter the research collector, fit thresholds, or update legacy runs.
