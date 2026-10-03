# Development pilot preparation

Status: implementation and synthetic validation. Human/source and pilot
configuration review remain pending. The existing Stage 0 decision is unchanged;
this checkpoint does not freeze parameters or establish measured model quality.

## Purpose and boundary

H4 used DIRECT at 96 tokens and CoT at 1,024, confounding prompt and budget
effects. `python -m experiments.research_study --pilot` collects fixed-strategy
diagnostics without fitting thresholds or routers. Both development splits are
descriptive; this exposed pool provides no held-out estimate. The pilot creates
no policy or test-results artifact and cannot enter the main-study aggregate.

Inputs must declare `role=development_tuning` and contain train/calibration
only. Main-study or test-containing inputs are rejected before model loading.
The candidate `data/procedural_research_v1/tuning.json` has 94 exposed items in
91 canonical groups; human/source review is pending. The main study continues
to require three grouped splits and all five controller strategies.

## Selection and conditions

Within each split/family/level stratum, rank whole groups by SHA-256 of seed
and group ID, without consulting gold labels or historical outcomes. Keep all
variants in a selected group. Default: one group per stratum. `selection.json`
records counts and group IDs; `dataset.json` freezes the selected content.

Proposed defaults are DIRECT and CoT at **both 96 and 1,024 tokens per call**,
seed 42. These are diagnostic preparation defaults, not a preregistration or
parameter freeze. An item/strategy shares its draw seed across caps, without
guaranteeing identical later samples for multi-call strategies. Condition order
varies deterministically within each question.

Other fixed strategies: SELF_CONSISTENCY (five samples), TOT (three complete
candidates plus selection), REACT (bounded calculator loop), PAL. Caps apply
per generation call. ReAct uses `min(cap, 200)` per turn. Total generated tokens
can exceed one cap; matched caps do not imply matched full inference costs.
Variants and budget repetitions do not create independent original problems.

## Reproduce software validation

No download or model inference is needed:

```bash
python -m experiments.research_study --backend smoke --pilot --strategies DIRECT COT --token-budgets 96 1024 --groups-per-stratum 1 --seed 42 --output runs/NEW_PILOT_SMOKE
python -m experiments.research_study --replay runs/NEW_PILOT_SMOKE --output runs/NEW_PILOT_REPLAY
python -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q
python -m pytest tests/test_research_pilot.py test_qwen_mlx_backend_mocked.py -q
```

Smoke traces, outcomes and token counts are artificial; timing measures Python
fixture execution. Replay checks all declared artifact/source hashes, retains
settings, makes no model call and recomputes diagnostic summaries. Outputs are
never overwritten; failures preserve every completed, flushed attempt.

## Prepare measured collection after review

Preparation command, **not executed for this checkpoint**:

```bash
python -m experiments.research_study --backend mlx --pilot --dataset data/procedural_research_v1/tuning.json --model /path/to/pinned-local-mlx-snapshot --strategies DIRECT COT --token-budgets 96 1024 --groups-per-stratum 1 --seed 42 --output runs/NEW_MEASURED_DEVELOPMENT_PILOT
```

The placeholder must be replaced with a reviewed local model directory.
Repository identifiers are rejected. The manifest hashes safetensors weights
and JSON/model tokenizer files before loading and records the resolved path.
These hashes alone identify local content without authenticating an upstream
revision; `model_revision_verified` remains false unless an upstream-content
verification is supplied with `--model-provenance`. Preparation can independently
match LFS SHA-256 and ordinary Git blob hashes to a saved, pinned Hugging Face
API response:

```bash
python -m scripts.prepare_development_pilot --model /path/to/pinned-local-mlx-snapshot --upstream-metadata /path/to/saved-upstream-responses --output audit/NEW_PILOT_PREFLIGHT
```

The resulting review packet includes the selected queries/golds, independent
exact solutions, model content hashes and license/source evidence. Game-of-24
verification constructs an expression by subset dynamic programming without
using the supplied answer; arithmetic and ordering are solved from the query.
This is automated verification, not human sign-off. Supply its
`model_provenance.json` to measured pilot collection; the runner rehashes the
actual local content, rejects a mismatch and saves the provenance with the run.

The latest DIRECT suffix is Vietnamese and the CoT suffix is English. Record
that difference with any development comparison; matching caps does not alone
isolate instruction effects from prompt-language effects. Human/publication
review remains pending even when local model content is authenticated.

Record reviewer, date and evidence for candidate wording/golds/groups and
ownership/license; selected development groups and prior exposure; applicable
Stage 0 decision (`docs/stage0_gate_decision.md`); model content, prompt/parser
revision, caps, seeds and resource limits. Keep held-out gold/prior-exposure
review separate. Then review raw pilot failures, ceilings/floors and truncation
before freezing the main-study prompt, budgets, dataset, seeds and lambda.

## Artifacts and interpretation

Each run saves manifest, selection, dataset, attempts JSONL, records, summary
and report. Attempts retain strategy/cap, seed, format, answer, correctness,
heuristic confidence, all-call generated tokens and strategy duration. Raw
generation traces include messages, output, actual cap, temperature, thinking
flag, prompt tokens, termination reason and tool events. The backend receives
query and format metadata without gold labels or aliases. No embedding or
controller call is needed.

Descriptive cells report items/groups, accuracy, generated/prompt tokens,
parse failures, length stops and confidence errors at 0.8. No intervals or
superiority claim is generated. Generated-token counts exclude prefill/full
inference cost. Strategy duration includes invoked tools but excludes loading
and online controller scheduling; replay retains recorded duration.

Historical manifests retain the source hashes that produced them. Rebuilding
unchanged data with a newer harness creates a fresh manifest and must not
rewrite historical provenance merely to make a test pass.
