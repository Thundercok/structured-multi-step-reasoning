# DIRECT → CoT development extension

Status: **development-only protocol; no eligible measured run has been executed**.
This extension does not amend the frozen run11 cascade, reopen Stage 0, or create
evidence for the held-out main study. Its first question is narrower: can a
cheap direct attempt be retained when it follows the output contract, while an
independent CoT attempt is used only after an observable format or length
failure?

The supported entry point is `python -m experiments.research_study`. Collection
and replay stay headless and independent of RAT, Qt, and personal-file indexing.

## Research boundary

This is conditional escalation, not targeted correction. DIRECT and CoT each
receive the original query; CoT never receives the DIRECT answer or rationale.
Both use the same pinned Qwen snapshot, selected development questions,
generation seed, greedy decoding, 1,024-token per-call cap, answer contract, and
English prompt profile `aligned-direct-cot-v1`. The intended manipulation is
only whether visible reasoning steps are requested.

`enable_thinking=False` remains fixed. Therefore “CoT” here means an
**elicited visible rationale**, not access to or measurement of a model's hidden
chain of thought. Reports and the manuscript must preserve that terminology.

The input must declare `role=development_tuning` and contain only `train` and
`calibration`. Neither split is held out: train is used only for manipulation
diagnostics and calibration is the development evaluation split. The analyzer
rejects test items. `gen02_tune`, run11 outputs, and `gen02_tune_gapB` are already
exposed; gap-style B rephrases existing canonical problems and is not an
independent validation set. A later measured execution needs an addendum that
records the exact dataset hash, selected group IDs, review status, seed, model
content/upstream revision, and source commit before generation.

## Fixed arms and policy

Collect exactly one DIRECT and one CoT generation per selected item at the same
cap. Raw traces must retain the complete prompt, output, parser status,
wordiness flag, prompt/generated token counts, termination reason, temperature,
thinking flag, and answer-format metadata. The analysis rehashes artifacts,
re-parses raw output, recomputes correctness with the frozen answer checker, and
rejects inconsistent trace or manifest metadata.

The deployable policy is fixed before aligned measured outputs are inspected:

1. Run DIRECT.
2. Escalate to an independent CoT attempt if DIRECT lacks a valid `Answer:`
   marker, violates the bare-answer contract (`wordy=true`), or any DIRECT
   generation ends because of the length cap.
3. Otherwise retain DIRECT.

Confidence and log-probability are not policy inputs. Their earlier
preregistered signal test failed, so this extension must not fit a retrospective
confidence threshold. The analyzer evaluates these replay methods:

- `fixed_direct`
- `fixed_cot`
- `direct_cot_format_or_length` (the fixed deployable policy)
- `always_direct_cot` (always pay for both and use CoT)
- `oracle_direct_cot_utility` (gold-informed diagnostic; never deployable)

## Manipulation and decision gates

Before a measured run can receive a `go` status, both development splits must
pass the prompt-manipulation check:

- DIRECT visible-rationale rate ≤ 0.05;
- CoT visible-rationale rate ≥ 0.80.

Visible rationale is operationalized as non-whitespace output before the final
`Answer:` marker; missing-marker cases are tracked separately as format failures.

The decision-eligible settings are frozen at `lambda=0.02` and a 1,024-token
per-call cap. Other values remain useful for explicitly exploratory replay, but
the analyzer labels them `exploratory_settings`. Model provenance must match a
saved upstream revision and the actual local content hashes; otherwise the
status is `invalid_provenance`. The collected dataset must also record
`human_review_status=approved`; otherwise the status is `pending_review`.

For the fixed policy versus `fixed_cot`, a development `go` requires all of:

- grouped-bootstrap 95% lower bound for the accuracy difference ≥ −0.02;
- mean total-token ratio ≤ 0.80;
- positive mean utility difference;
- realized policy rescues exceed realized policy harms.

Bootstrap draws resample original `group_id` values and retain variants within
groups. Accuracy, prompt tokens, generated tokens, their sum, utility,
escalation rate, rescue/harm counts, and recorded strategy time are reported.
The utility cost is the sum of prompt plus generated tokens for every invoked
call. It is a token proxy—not FLOPs, energy, billing cost, full inference cost,
or measured online latency. Recorded strategy times are replayed measurements,
not controller latency.

A `go` authorizes only a separately preregistered development replication on a
new, non-overlapping development sample. It does not open held-out test data,
change the existing Stage 0 decision, or support a publication claim by itself.

## Software-only reproduction

These commands make no model-quality claim. The smoke backend is synthetic and
intentionally fails the visible-CoT manipulation check because it emits only
bare fixture answers.

```bash
python -m experiments.research_study --backend smoke --pilot \
  --strategies DIRECT COT \
  --prompt-profile aligned-direct-cot-v1 \
  --max-tokens 1024 \
  --seed 42 \
  --output runs/NEW_DIRECT_COT_SMOKE

python -m experiments.research_study \
  --direct-cot-analysis runs/NEW_DIRECT_COT_SMOKE \
  --direct-cot-budget 1024 \
  --lam 0.02 \
  --output runs/NEW_DIRECT_COT_SMOKE_ANALYSIS

python -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q
python -m pytest tests/test_research_pilot.py tests/test_direct_cot_analysis.py test_qwen_mlx_backend_mocked.py -q
```

Analysis makes no model call and never overwrites its input or an existing
output directory. It saves `manifest.json`, `policy.json`, `results.json`,
`summary.json`, and `report.md`, with source and artifact hashes.

## Measured execution template

Do not run another MLX workload concurrently with an active model campaign.
After the exact execution addendum is reviewed and resources are free, replace
the placeholder paths and the preregistered group count below:

```bash
python -m experiments.research_study --backend mlx --pilot \
  --dataset data/procedural_research_v1/tuning.json \
  --model /absolute/path/to/pinned-local-mlx-snapshot \
  --model-provenance /absolute/path/to/model_provenance.json \
  --strategies DIRECT COT \
  --prompt-profile aligned-direct-cot-v1 \
  --max-tokens 1024 \
  --groups-per-stratum PREREGISTERED_COUNT \
  --seed 42 \
  --output runs/NEW_DIRECT_COT_MEASURED

python -m experiments.research_study \
  --direct-cot-analysis runs/NEW_DIRECT_COT_MEASURED \
  --direct-cot-budget 1024 \
  --lam 0.02 \
  --output runs/NEW_DIRECT_COT_MEASURED_ANALYSIS
```

Review raw outputs and the manipulation gate before interpreting policy metrics.
Publish no number until question/answer/group review, model provenance, run
artifacts, and the execution addendum have been reviewed together. The broader
main-study constraints remain those in [research_protocol.md](research_protocol.md)
and [development_pilot_protocol.md](development_pilot_protocol.md).
