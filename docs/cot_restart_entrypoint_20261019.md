# Fresh CoT restart smoke through the supported entry point

The offline fresh-base adapter now runs through the supported research command:

```bash
python3.12 -m experiments.research_study --cot-restart-fresh-smoke --output audit/NEW_FRESH_SMOKE
```

This fixed software check collects O/F/CONT/A on three authored synthetic
fixtures. It loads neither model weights nor Qt and never reads the pending
candidate questions. Fixture caps of 64 and q requested = 0.50 remain software
settings, not approved budgets for a new study. Dataset/model/seed/cap overrides
and real-execution flags are rejected before creating output. The older helper
`python3.12 -m scripts.smoke_cot_restart_fresh` forwards to this same mode.

The saved [acceptance run](../audit/cot_restart_entrypoint_20261019/report.md)
completed 12 mock calls / three original groups, with zero real model calls.
Twenty fresh-adapter cases, 29 required harness/stopping/predictor regressions
and five matched-runner cases passed: 54 tests in total. Completed CLI resume
preserves all run files byte for byte. Source fingerprints now include the
canonical `reasoning/` implementations behind the compatibility shims.

This is evaluation infrastructure for the RAT–CoT system described in
[project scope](project_scope.md). It does not establish equivalent online
execution in RAT, model-quality gains, online latency, a confirmatory result
or a Stage 0 change. Real fresh-data execution remains disabled.

## Source versioning and historical evidence

Before this change, both October 13 plans already differed from the current
checkout in `experiments/research_study.py` and `reasoning_strategies.py` after
the structural consolidation. This is recorded in the new audit; the October
16 statement that their current-source checks passed was true at that snapshot.

The entry-point extension changes the current source version again. Historical
plan files, journals, records and prior reports are preserved; 30 files were
checked against their pre-change hashes. The existing source guard is unchanged
and rejects old plans under mismatched code. Reproduction of those campaigns
requires their original pinned source/runtime, rather than relabeling them as
compatible with this checkout. Pre-change source copies and the exact patch
for this implementation step are retained in the acceptance directory.

## Remaining before real collection

The candidate packet still records human review as pending: 71 items / 70 groups.
Before real collection, record independent review evidence and freeze the
group frame, sample size/power, cap/cost scope, practical margin, decision code
and a bounded execution plan. Its method must then be wired into a separately
reviewed real mode. No sample size or Tango critical value is selected by this
software acceptance. Synthetic token counts do not represent full inference
cost or online latency.
