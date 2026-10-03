# Research experiment protocol

## Scope

`python -m experiments.research_study` collects each strategy output once per
query and seed, fits policies on separate development splits, and replays them
on the same held-out outputs. This applies to the current strategies because
each receives only the original query, not earlier strategies' answers. It is
not a process-verification or targeted-correction experiment.

Replay isolates policy decisions from generation noise. It estimates selected
path quality and token cost. It does not simulate cache state, parallel
scheduling or online latency. Collection cost is additional: all strategies
execute during collection; test cost sums the path selected by each method.

## Dataset contract

Input is a UTF-8 JSON object with `name`, `version`, `source`, `license`, `items`.
Each item has string fields `id`, `group_id`, `split`, `query`, `answer` and
`answer_type`. Splits are `train`, `calibration`, `test`; all three are required.
Answer types are `number` and `text`. Numeric items may specify a nonnegative
absolute `tolerance` (default zero).

Single-item schema illustration, not a runnable study dataset:

```json
{
  "name": "reviewed-reasoning",
  "version": "1",
  "source": "Dataset origin and revision to be recorded here",
  "license": "Dataset license to be recorded here",
  "items": [
    {
      "id": "arithmetic-001",
      "group_id": "original-problem-001",
      "split": "test",
      "query": "Three notebooks cost 45000. At the same unit price, what do seven cost? Return the amount as a number.",
      "answer": "105000",
      "answer_type": "number",
      "tolerance": 0
    }
  ]
}
```

Build splits before generation. Original problems, translations and paraphrases
share a group and split. Validation rejects duplicate IDs/normalized queries,
groups crossing splits, missing splits and invalid numeric labels. It cannot
detect arbitrary semantic paraphrases or verify answer truth; those require review.
Record source, license, original split and review provenance in the release.

Procedural inputs additionally require a known `family`/matching `checker`,
matching answer type, valid problem metadata and the declared generator query
template. Validation recomputes label-free canonical fingerprints and rejects
the same problem appearing under different groups or splits, including runner
renamings in ordering puzzles and permutations of Game-of-24 numbers. The
fingerprint preserves arithmetic operation order and the asked ordering rank;
it does not detect every mathematical or semantic equivalence. Canonical
releases declare `identity_version=procedural-v1` and use the same stable
`problem_id` and `group_id`, while item IDs have a release namespace.

The candidate bundle `data/procedural_research_v1/` is reproducible without
model calls:

```bash
python -m scripts.build_procedural_research_data --split-seed 42 --output data/NEW_RELEASE_DIRECTORY
```

The builder never overwrites a directory or modifies `gen_v2.json`/`gen_tune.json`.
It excludes every main-source canonical class present anywhere in the legacy
tuning pool. The historical H4 sweep covers all tuning items, so its original
`test` label cannot establish a held-out study split. All tuning items are
treated as exposed development, regardless of whether their model evaluation
has finished. `tuning.json` contains train/calibration only and declares
`role=development_tuning`; the supported study runner rejects it. Its schema
can be checked by `validate_dataset(..., require_all_splits=False)` for data
preparation only; this option does not enable running a held-out experiment.

For `main.json`, canonical groups consisting solely of original test items
retain test status. Any group with an original development member stays in
development. Development groups are assigned by a deterministic SHA-256 rank
within family/level strata, approximately one-third train and two-thirds
calibration (split seed 42, distinct from generation seeds). No reviewed
development item is promoted into test. Group variants remain together.

The current candidate has 179 items/177 groups: train 36/36, calibration 72/71,
test 71/70. The exposed tuning candidate has 94 items/91 groups: train 32/32,
calibration 62/59. One main-source ordering item is excluded because it belongs
to the tuning pool. There are zero shared canonical problems or item IDs
between the two releases. Counts refer to retained questions and canonical
classes, not validated difficulty or sufficient statistical power.

The bundle records input/source/output hashes, original row fingerprints and
IDs/splits, development review evidence, exclusions and family/level counts.
Previously audited, unchanged development content retains its agent review;
human review, ownership/license confirmation, held-out gold review and prior
test-exposure review remain pending. This migration preserves question/label
content and does not freeze a publication dataset or change Stage 0.

Text scoring normalizes whitespace/case and matches the entire returned answer
against the label or optional, explicitly reviewed `answer_aliases`. Aliases
must be a nonempty list of distinct normalized strings on text items. They are
fixed before evaluation; substring matches and free-form synonyms are rejected.
Numeric scoring compares the entire returned scalar with the label within its
tolerance. Items may declare `decimal_separator` (`.` by default, or `,` for
reviewed Vietnamese development items). Dot notation remains accepted with
comma notation; comma grouping is never guessed from the gold answer. A label
appearing inside an incorrect explanation is not a correct answer.

Research collection supplies answer-type/decimal metadata to the MLX adapter,
without labels or aliases. Typed numeric extraction accepts only a whole scalar
with optional currency/a bounded unit vocabulary, text extraction retains the
whole final response, and expression extraction preserves the complete
expression and optional equality. Thus negation or alternative answers cannot
be reduced to a matching number/Yes/No. Unit suffix normalization does not
validate physical dimensions. This conservative format contract can reject
correct free-form explanations; prompts already request a bare final answer.
Whole-answer bold Markdown, bold labels and contiguous repeated `Answer:`
prefixes are presentation-normalized before typed parsing. The complete
remaining candidate is still scored; the normalization never searches for a
gold name or discards explanatory/contradictory clauses.

Procedural arithmetic scores a complete scalar, ordering scores one named
occupant with an optional rank consistent with the declared question, and
Game-of-24 scores an exact binary arithmetic expression using each supplied
integer exactly once. A single optional equality suffix must assert 24; wrong
or chained equality suffixes are rejected. Voting compares preserved expression
strings rather than their common result 24. These rules change scoring and need
fresh source-pinned runs; legacy artifacts retain their original implementation.
Audit extraction rules and labels on development examples before freezing test.

The development-only audit is reproducible with
`python -m scripts.audit_development_data --output audit/NEW_DIRECTORY`.
It records agent proofs and query fingerprints, checks original group and
canonical procedural problem identities, and compares blind held-out row
hashes. Ordering identities canonicalize clue graphs under runner renaming with
the asked rank retained. See `audit/development_data_review.json` for the
reviewed variants; this is not independent human approval. Existing procedural
legacy releases have structural split overlap; use the separate regrouped
candidate for subsequent preparation. The audit leaves held-out content
unchanged and does not change Stage 0.

The completed historical Qwen3-8B H4 sweep is verified in
`audit/G_completion_verification.json`. Its offline review is reproducible with
`python -m scripts.review_tuning_sweep --output audit/NEW_REVIEW_DIRECTORY`.
The [review report](../audit/qwen3-8b-tuning-review-20261003/report.md) reproduces
all 188 historical scores, independently checks all 94 exposed tuning items,
and separately records retrospective typed scores. It does not overwrite the
raw trace/summary, generate new answers, fit policies or freeze parameters.
DIRECT's 96-token budget and CoT's 1,024-token budget confound instruction and
budget effects. Observed ceilings, floors and inconsistent ordering level
accuracy require further development review before claiming calibrated
difficulty. The checkpoint name recorded by that runner is cache metadata;
fresh supported runs must pin an explicit local model snapshot.

## Fit and test separation

1. Freeze dataset version, grouped splits, model snapshot, prompts, generation
   seeds, lambda and primary comparisons before viewing test results.
2. Collect all strategies and one embedding for each item. The model receives
   the query only; the evaluator holds the answer. A SHA-256-derived seed
   identifies each query/strategy draw. Strategy order varies per query.
3. Fit stopping thresholds only on `calibration` records.
4. Build full-policy entry targets on `train` using the frozen ladder. Fit a
   separate one-shot router to fixed CoT/ReAct/PAL outcomes.
5. Evaluate fixed strategies, ladder only, one-shot, entry without escalation
   and full policy on `test`, using identical recorded outputs.

Lambda is fixed: utility = accuracy − lambda × mean tokens/1000. For tuning,
reserve an extra development validation set outside the runner's test split or
preregister a lambda grid. A test sweep is descriptive, not a way to select a
winning lambda and report it as held out. Model size and token scope must match
across controller comparisons.

## Measurement

`smoke` uses artificial category markers, correctness probabilities and token
costs. All artifacts say `synthetic_smoke`. It validates software without model
downloads. Its timings measure Python execution only.

`mlx` calls `QwenMLXBackend`; failures terminate the run and preserve completed
attempts. Supply a locally pinned model snapshot and record its revision in the
release. The manifest stores the supplied model path and explicitly says
`model_revision_verified=false`: checkpoint provenance is not verified by the
runner. Seeds are recorded; identical samples across hardware/library versions
are not guaranteed.

The adapter counts generated tokens across all samples and selection/tool turns.
Prompt tokens, embeddings and model loading are excluded from token cost.
Strategy times and embedding time are separate. Load time is in the manifest.
Replay timing sums omit router overhead and are not cold-load, TTFT, throughput
or whole-app latency measurements.

MLX strategy settings are in the hashed adapter: greedy CoT; SC with five samples;
three candidates plus selection under the legacy `TOT` name; a bounded ReAct
calculator loop; and PAL. These are specific implementations, not faithful
reproductions of every named paper. PAL's development execution helper is not a
security boundary; use a controlled experiment environment for model-generated
programs. Confidence is a heuristic, not a calibrated correctness probability.

## Artifacts and statistics

| File | Purpose |
| --- | --- |
| `manifest.json` | Status, seed, lambda, UTC time, Git/source hashes, versions, model/token scope, artifact hashes |
| `dataset.json` | Exact questions, answers, groups and splits |
| `attempts.jsonl` | Flushed completed outputs, retained after collection failure |
| `records.json` | Embeddings, outputs, confidence, costs and labels for replay |
| `policy.json` | Thresholds and mean calibration costs; entry regressors are refit from train records |
| `results.json` | Per-query test path, answer, correctness and cumulative cost per method |
| `summary.json` | Metrics and paired differences |
| `report.md` | Tables with evidence and measurement limitations |

Replay runs omit `attempts.jsonl` because no new model calls occur.
Reports show accuracy, tokens, utility and escalation frequency. Paired
differences compare full policy with one-shot routing, fixed SC and removing
escalation. Percentile 95% intervals use 2,000 bootstrap samples of original
problem groups, retaining all variants within sampled groups. Intervals are
conditional on the fitted policy and generation seed; one group yields no
interval. No automatic superiority claim is made.

### Multiple generation seeds

Use the supported entry point after collecting the preregistered seeds:

```bash
python -m experiments.research_study --aggregate runs/seed-1 runs/seed-2 runs/seed-3 --output runs/aggregate
```

These paths are placeholders for completed collection or replay runs, not
bundled measured results. At least two distinct seeds are required; the main
study still targets at least three seeds fixed before inspecting test results.
Replay copies of the same generation seed are rejected. Input runs must share
the exact dataset hash, lambda, backend, evidence/token scope, model metadata,
strategy labels, source hashes, Python/packages and platform. Different
hardware or library versions need separate analyses. All declared artifact
hashes are checked, and every method must contain every frozen test ID exactly
once with the original group. Answers and cumulative costs/timing sums must
agree with the selected attempts in `records.json`. The procedural checker
source is now included in collection/replay source hashes as well.

For each question and method, average correctness, tokens, utility and
escalation across the observed seeds. Report the resulting question-weighted
means and retain the unique test-question count; seed repetitions and variants
are not new independent original problems. The paired differences use those
seed-averaged question outcomes, followed by 2,000 percentile bootstrap draws
of original problem groups with all their variants retained. Intervals are
conditional on the frozen fitted policies and observed seed set; they do not
include policy-fitting uncertainty or uncertainty over a population of new
generation seeds. One original group gives no interval. Per-seed metrics and
sample SD/min/max across seeds remain available for descriptive variability.

Aggregation makes no model calls and fits no new policy. Its new directory
contains `manifest.json`, `summary.json` and `report.md`; the manifest references
each original run and its manifest/artifact hashes, and hashes the aggregate
analysis implementation and outputs. It never overwrites an existing path and
validates inputs before creating output. Hash consistency does not establish
label review, preregistration or checkpoint identity. Every aggregate is marked
as requiring publication review, and synthetic inputs retain the
`synthetic_smoke` label. Generated-token costs and strategy replay times retain
the same limits as individual runs. This analysis does not change Stage 0.

Replay requires matching source hashes, checks dataset/record artifact hashes
and retains seed/lambda. The dataset contains text and labels: publish only data
cleared for sharing. Personal feedback belongs outside the public benchmark.

## Publication gate

- Review answers/group assignments; freeze dataset/model revisions.
- Complete pilot checks, seed selection and resource estimates; satisfy Stage 0
  before the frozen Qwen/Meta-Reasoner campaign proceeds.
- Collect real outputs without synthetic fallback; retain failed runs too.
- Evaluate multiple seeds, ablations and failure/escalation-harmed examples.
- Audit input-token cost and online timing before claiming deployment efficiency.
- Compare prior work where feasible; identify missing reproductions explicitly.
- Build paper tables from reviewed artifacts, not README illustrations,
  simulator tables or passing-test counts.
