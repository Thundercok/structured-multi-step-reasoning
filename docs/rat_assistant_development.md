# RAT: model-driven chat and honest development checks

RAT chat now sends natural-language requests through one live model loop. The
model chooses tools, arguments, order, clarification questions and the final
answer. Python implements indexed-file access, timetable arithmetic, calculation
and execution limits. There is no keyword dispatcher or simulated answer policy
in this chat path. Adding more tools alone does not establish stronger AI ability.
The separate file/schedule views and CLI shortcuts retain their own interfaces.

## User experience

- A submitted request opens the conversation, with a status describing actual
  execution: looking up a timetable, finding a file, reading a file or composing.
- Inference and tools run on a Qt worker thread. The input remains usable. The
  send button becomes Stop; another draft is preserved while a turn is pending.
- Observed documents and timetable cards appear during the request. Files can be
  opened, previewed or revealed in Finder. `Đã tìm thấy` and `Đã đọc` are distinct;
  neither is a correctness certificate for the answer.
- Follow-ups receive completed conversation turns, observed source metadata,
  active member and current time. Documents can be reread from their real paths.
  Failed/cancelled requests remain in a separate bounded context with an explicit
  runtime status and `successful_answer_produced: false`. They are never inserted
  into successful answer history. The model can retain the original goal after
  a timeout instead of treating the next short follow-up as a new isolated task.
- A real schema-constrained model call records the initial task goal, explicit
  constraints, success criteria and remaining work before acting. Its raw request,
  completion, counts and failures are retained. There is no keyword intent policy
  or rule-written plan fallback. The native `update_task_state` tool then lets the
  actor update completed/remaining work as observations arrive. Memory persists
  across follow-ups and clears on Chat mới. The displayed goal/constraints are
  model-authored, not verified understanding. A completed status remains a model
  self-report. The low-level runtime leaves initial planning opt-in; RAT UI and
  live app-development collectors enable it, while scripted smoke does not.
- Stop preserves already observed sources and ignores late callbacks. A stopped
  or failed turn is not saved as a successful model answer. In-flight local
  inference may finish before the worker observes cancellation; subsequent tool
  calls are prevented.
- Missing service, invalid calls and truncated completions remain failures. The
  UI offers retry. There is no remote-provider or rule-written answer fallback.

Live chat uses Ollama's [native tool-calling messages](https://docs.ollama.com/capabilities/tool-calling)
through `/api/chat`. Settings now has a separate **model for the assistant**
selector. `assistant_model` affects the next chat turn; an empty value inherits
`ollama_model`. It does not change document helpers or research model settings.
Start the desktop demonstration with `python -m rat.main`.
App chat requests `think: false` and an 8192-token context explicitly, preserving
both in raw inputs. The native output budget is 640 tokens per call, one initial
plan plus eight execution steps in the UI, and a soft 24,000 reported-token ceiling
checked between calls. Research generation behavior is unchanged. The
[natal atlas](natal_chart.md) is available as a deterministic calculation tool and
separate desktop window.
The native per-call deadline is now 90 seconds. The previous 30-second deadline
aborted some actual read-and-synthesis sequences and model startup on this Mac.
This change prevents premature transport failures; it does not make inference
fast. The worker keeps the UI usable, and raw measured latency remains visible.

## What the actual local model did

Development runs used the installed `qwen2.5:1.5b` and artificial documents plus a
fixed student timetable. They are exposed development fixtures, not unseen tests.
The records retain successes and poor outputs without automatic success labels.

The earlier bundle `audit/rat_assistant_recorded_inputs_20261011/` contains
three conversational requests, the fixture text/context, actual model input
messages and tool schemas, raw assistant messages, tool results, reported prompt
and completion counts, and measured elapsed time. Its review status is pending.
Observed shortcomings include:

- Asking the user for a course name instead of checking the active timetable.
- Finding a document but skipping the requested reading and summary.
- Claiming document content from search metadata without reading it.

Earlier bundles retain additional failures: a guessed nonexistent path and an
incorrect English weekday despite a correct timetable result. Direct timetable
and arithmetic tool calls also executed. Passing transport or UI tests does not
establish task completion. This model is still the main limitation on helpfulness;
the implementation does not establish that RAT provides impressive autonomous
assistance.

Reproduce a new development collection (each output directory must be new):

```bash
python -m scripts.eval_assistant_agent --mode live --output audit/NEW_RAT_DEV
python -m scripts.collect_agent_trajectories --mode live --output audit/NEW_RAW_TRACES
python -m scripts.eval_assistant_agent --mode smoke --output audit/NEW_RAT_SMOKE
```

`--request '…'` can be repeated to collect a custom conversation. Smoke decisions
are explicitly scripted, with synthetic zero token counts. Live totals sum
Ollama's reported prompt and completion counts across every call, including final
synthesis. On transport failure unavailable counts remain unknown, represented as
zero rather than an estimate. Wall time includes inference, tool execution and
client overhead; it is measured online development latency, not replay time or
energy/monetary cost. Older bundles without `model_input` retain output traces but
cannot fully reconstruct their original input messages.

The UI preview in `audit/rat_assistant_ui_preview_20261011/` replays a recorded
live search output against artificial sources. It makes no new model calls. The
answer shown did not complete reading or summarization; this is an interface
preview, not evidence of model quality.

## Experimental learned stopping predictor

`rat/engine/controller.py` now fits a ridge predictor from reviewed paired
continuation outcomes and calibrates a stopping threshold. An unfitted predictor
passes decisions through. If a fitted predictor stops a proposed lookup, the model
gets one synthesis turn using existing observations; code never supplies a canned
preparation plan. This predictor controls whether to continue a lookup. It does
not learn new tools, generate new app features or train the language model.

No controller trained on reviewed measured pairs is currently deployed. The
pipeline is validated only with explicitly synthetic fitting/replay data. The
old `data/agent_dev_trajectories.jsonl` labels inferred from tool presence are not
accepted as training outcomes. Historical benchmark JSON files are retained but
are not endorsed as quality evidence.

Each measured dataset row needs:

- `id`, `group_id`, and `split` (`train`, `calibration`, or `test`). All variants,
  documents and states of one underlying problem stay in the same group/split.
- `features`: the numeric vector declared by `FEATURE_NAMES`, captured before
  deciding whether to execute the proposed lookup.
- `quality_gain`: reviewed continuation-answer quality minus stop-answer quality,
  on a stated quality rubric scaled to [0, 1]. The difference lies in [-1, 1].
- `stop_tokens`, `continue_tokens`: reported prompt plus completion tokens for
  every model call from the common decision state through each branch's final
  answer. Do not omit tool selection or final synthesis.
- `delta_tokens = continue_tokens - stop_tokens`, which may be negative.
- `evidence: "measured_paired_continuation"`, `reviewed: true`, and
  `pair_trace_sha256`: the hash of the preserved raw branch artifacts. Human
  review must inspect those artifacts; a metadata flag alone is not evidence.

Both branches start from the same state, history, sources and proposed action.
The stop branch synthesizes immediately; the continuation branch executes the
proposal and follows the bounded model loop. Preserve paired raw artifacts before
rating answer quality. Plain online traces do not contain this counterfactual and
cannot be used as paired labels. The separate paired collector now pauses before
a proposed single lookup, runs immediate synthesis and continuation from the
shared state, and preserves both raw branches. Parallel proposals are recorded as
unsupported rather than quietly changing the proposal. If the model skips lookup,
it records `checkpoint_not_reached` and produces no fake pair.

```bash
python -m scripts.collect_agent_pairs --mode smoke --group-id network-prep \
  --split train --output audit/NEW_PAIR_SMOKE
python -m scripts.collect_agent_pairs --mode live --model INSTALLED_MODEL \
  --group-id network-prep --split train --output audit/NEW_PAIR_LIVE
```

`pair.json` is canonical JSON with a SHA-256 digest. Costs include shared proposal
selection in each path and every branch call. Collection overhead counts the
shared selection once; prefix inference is recorded separately. Branch times are
sequential counterfactual development times, not deployed-policy latency.
`pending_row.json` and `review_template.json` contain no quality labels. A human
reviewer can fill the template and use `scripts.review_agent_pair` to verify raw
hashes and costs before generating a reviewed row. Synthetic smoke pairs cannot
be relabeled measured. Enough disjoint reviewed groups in all three splits are
still required before fitting or deployment.

For exposed grouped paraphrase/model comparisons:

```bash
python -m scripts.eval_rat_tasks --mode live --model qwen2.5:1.5b \
  --model ANOTHER_INSTALLED_MODEL --output audit/NEW_TASK_COMPARISON
```

All variants share the same underlying artificial fixture group. `review.json`
retains final answers, actions, reading observations, self-reports, latency/tokens
and blank completion/grounding/constraint scores. Neither tool presence nor
self-report is a success label; these are not unseen tests. `--model` changes only
the run client, not RAT settings, and never downloads a model. The early
`audit/rat_task_memory_live_20261011/` was collected before initial schema planning
was enabled. Its two 1.5B turns skipped both lookup and optional state updates;
that failure prompted the explicit, measured initial-plan stage.

`audit/rat_serial_model_comparison_20261011/` contains twelve serial turns on
three exposed two-turn conversations. The six 1.5B turns produced two failures
and no observed document reads. The six `qwen3:4b` turns all failed and also
produced no document reads. This is **not a fair instruct-model quality
comparison**: inspection of the actual downloaded weights identifies
`Qwen3-4B-Thinking-2507`, whose metadata only advertises thinking enabled, while
the app requested `think: false`. The generic registry family description did
not identify this incompatibility. Missing token counts after timeouts remain
unavailable, not actual zero inference cost. Normal desktop load was not
controlled as a hardware benchmark.

`audit/rat_qwen3_template_adapter_20261011/` retains an unsuccessful same-weight
template-adapter probe. The reply still contained reasoning and truncated. The
temporary alias was removed and the adapter was rejected; changing a template
does not convert thinking-only weights into an instruct model. Use the explicit
`qwen3:4b-instruct` variant for a non-thinking candidate and retain its actual
`/api/show` metadata before evaluation. Neither these failures nor a later
successful tool call supplies a human-reviewed task-quality label.

`audit/rat_instruct_serial_comparison_20261011/` preserves the subsequent
30-second-deadline attempt. All twelve turns failed. Server logs identified the
six 1.5B failures as llama-server startup cancellation at the client deadline
while Instruct was resident. Some Instruct turns actually reached schedule,
search and document reading before final synthesis timed out. These are serving
and budget failures, with task-quality ratings still blank. Do not present the
failed cold baseline versus a resident candidate as a fair latency comparison.
`audit/rat_instruct_deadline90_20261011/` records a later two-turn probe with the
longer deadline and incomplete-request context; it remains exposed development
data and needs review independently of the older failed attempts.
Its follow-up reached all three lookup steps but returned internal task-state
JSON as final content instead of the requested preparation plan. The native
adapter now records that structural protocol failure and never converts it into
a made-up tool call or user answer. The actor prompt also explicitly keeps state
bookkeeping separate from the reply. The Instruct candidate remains optional in
Settings; it has not replaced the default model on this machine.

`audit/rat_instruct_pair_20261011/` reached a real read checkpoint. Continuation
returned an explanation supported by the artificial notes; stop synthesis hit
the deadline. Its stop inference counts are therefore incomplete and the pair
is rejected by the review importer for fitting. Keeping this failed branch is
diagnostic evidence, not a reviewed training example or a reliable cost delta.

`audit/rat_instruct_pair_concise_20261011/` contains a later three-bullet probe
with both branches completing and reported prompt/completion costs available:
3,374 stop tokens, 4,751 continue tokens, with 2,520 prefix tokens recorded
separately. Both replies remained model-authored. This is one exposed train
group, not a held-out improvement or a reviewed reward label. The artificial
note fits inside the search snippet, so reading can add little information in
this particular fixture. `quality_gain` remains null; no measured controller
has been fitted or deployed from it. Branch times are sequential collection
times and must not be treated as deployed-policy latency.

The fitting target is `quality_gain - lambda * delta_tokens / 1000`. Train fits
weights; calibration chooses the threshold; test labels are never read during
fitting. Replay checks disjoint groups and dataset/policy hashes. It reports
one-step utility differences, not online task success or measured agent latency.
The app predictor uses compact state/action features and remains a limited
experimental baseline; no research novelty or optimality is claimed.

```bash
python -m scripts.fit_agent_controller --smoke --output audit/NEW_CONTROLLER_SMOKE
python -m scripts.eval_controlled_agent --bundle audit/NEW_CONTROLLER_SMOKE \
  --allow-synthetic --output audit/NEW_CONTROLLER_SMOKE/replay.json

python -m scripts.fit_agent_controller --dataset reviewed_pairs.json \
  --output audit/NEW_MEASURED_CONTROLLER
python -m scripts.eval_controlled_agent --bundle audit/NEW_MEASURED_CONTROLLER \
  --output audit/NEW_MEASURED_CONTROLLER/replay.json
```

For explicit development deployment, set `RAT_ASSISTANT_CONTROLLER` to a measured
`policy.json` before starting RAT. Synthetic policy artifacts are rejected by the
app. Version 2 uses signed paired cost differences; older version 1 smoke bundles
are historical plumbing checks and cannot be deployed.

## Relationship to the NCKH campaign

These app changes do not advance the Qwen/Meta-Reasoner Stage 0 gate. The supported
paper experiment entry point remains `python -m experiments.research_study`.
That pipeline remains headless and independent of Qt/personal-file indexing.
The new RAT predictor is an app development extension, not measured evidence for
the manuscript. Publication still requires reviewed data, valid comparisons and
reviewed raw run artifacts under `docs/research_protocol.md`.
