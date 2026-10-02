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
detect semantic paraphrases or verify answer truth; those require review.
Record source, license, original split and review provenance in the release.

Text scoring normalizes whitespace/case only. Numeric scoring compares the
entire returned answer with the label within its tolerance. A label appearing
inside an incorrect explanation is not a correct answer. Audit extraction rules
and labels on development examples before freezing test.

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
interval. Multiple seeds need a separate aggregate analysis and must not be
treated as independent new questions. No automatic superiority claim is made.

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
