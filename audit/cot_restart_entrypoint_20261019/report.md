# Fresh CoT restart entry point — 19/10/2026

**Complete:** the supported `experiments.research_study` entry point now exposes
`--cot-restart-fresh-smoke`; the auxiliary command forwards to it. The saved
run completed **12 mock calls on three authored groups**, with **zero real model
calls** and **1,405 synthetic prompt+completion tokens**.

```bash
python3.12 -m experiments.research_study --cot-restart-fresh-smoke --output audit/NEW_FRESH_SMOKE
```

The O/F/CONT/A token-preserving adapter retains its existing generation, parser,
cost and checkpoint contracts. Fixed synthetic fixtures prevent the pending
candidate test pool from entering this smoke. Collection overrides, including
`--dataset`, `--model`, `--seed 0`, token caps and real-execution flags, fail
before output creation. The canonical reasoning source now participates in
the run identity, so changing implementation behind a root shim invalidates resume.

**Validation:** [54 tests passed](validation.json): 20 fresh-adapter acceptance
cases, 29 required research/stopping/predictor regressions and five historical
matched-runner cases. A subprocess verifies the actual `-m` entry point with
MLX/Qt imports forbidden. The saved official CLI run and its exact resume were
also checked; completed resume leaves all files unchanged.

## Historical source status

Before this task, both October 13 real plans already had source drift in:

- `experiments/research_study.py`: frozen `4c368d4ea51b86ef679cd6cf3bcddcb9017745cbdafffca8cb2c5ae5ea54952f`,
  pre-change checkout `7068c397797acd316511bf0a78c4f2c5bae32c4935be0b0a6fec2a4b1a26665d`.
- `reasoning_strategies.py`: frozen `bfeba9f683f4d8d87a7db3efd56d1574cb34cc7858e561444d45d0a93d109410`,
  pre-change checkout `fd77403c24b67dd5d7c777bd174aec158ecc9d90f1d6fa8d79f0e704aff8975b`.

The new entry-point extension intentionally creates a new current source version.
No historical plan hash, journal, record or report was rewritten: **30 protected
files retain their pre-change hashes**. The old `read_plan` guard still rejects
these real plans under mismatched sources. Passing matched tests here concerns
new synthetic plans prepared with current sources, not re-certification of old
real plans against this checkout. Historical replay needs its pinned environment.

Pre-change source copies are in `before/`; checksums in [before.json](before.json).
The exact local change is retained as [implementation.patch](implementation.patch).
These snapshots preserve this task's starting state; they are not represented as
the original October 13 source bundle.

## Next execution gate

The candidate packet still records 71 items / 70 groups pending independent
human review; no candidate generation was performed. Real fresh-data execution,
sample size/power, cap/cost scope, practical margin and decision implementation
remain unfrozen. In particular this run does not certify a nominal Tango cutoff
or either false-GO/false-NO-GO rate. All new results are software/synthetic;
Stage 0 is unchanged. RAT remains the application implementation of the same
method; this harness test makes no claim about online RAT behavior.
