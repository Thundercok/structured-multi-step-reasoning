# RAT: internal and external changes — 2026-10-15

The scope is the whole RAT experience: conversation, files, calculation,
timetable, notes and derived results. The intended experience is one bottom
composer and a companion that takes responsibility for the work. Feature
buttons remain debugging tools. This is a proposed implementation order,
supported by a current source audit, not a report that these changes shipped.

## Evidence and limits

- Source baseline: local `main`, `11c748a7a60c3da72e24f2e4cbb2233e5aa6a2b5`,
  plus the existing working tree. Unrelated research and context-snapshot edits
  are outside this audit. No source was changed by this audit.
- The native session opened earlier recorded an initial FastEmbed tokenizer
  cache failure, followed later by loading/eviction activity. This establishes
  a readiness problem during that launch, not that search is currently broken.
- Existing [development observations](../audit/rat_magic_validation_20261015/model_review_sanitized.json)
  show tool-free replies without a runtime error and very slow real requests.
  In run 13, three client wall times were approximately 144, 106 and 86 seconds;
  the first request timed out. These are narrow local-file observations,
  **not** an overall-app success rate or a controlled model comparison.
- The earlier expanded native UI replay has a small result at the top of a
  large empty panel. It is a presentation observation, not a live-model UI run.
- This audit did not run a new model campaign or verify every domain in the
  native app. Cross-domain journeys below are acceptance work still to do.

## 1. Internal: make work dependable and continuous

The useful foundation already exists: typed operations, versioned artifacts,
execution IDs, guarded commits, input requests and receipt-based reconciliation.
Extend these components; avoid introducing another competing task store.

| ID | Current finding and evidence | Proposed change | I / R / E | Score |
| --- | --- | --- | --- | --- |
| I1 | UI cancellation rejects late commits, but `SLMEngine.chat_with_meta` uses a blocking, non-streaming HTTP read without a cancellation argument. The UI releases its active worker before that read necessarily finishes. | Give each execution an explicit cancellation/deadline lifecycle through the transport. Bound outstanding requests per backend. Distinguish UI release, client cancellation and any observed backend acknowledgement. Retain the existing generation and commit guards. | 5 / 5 / 3 | 30 |
| I2 | `SearchWorker.__init__` warms the embedder before `moveToThread`, so initialization runs in the constructing UI thread. Hybrid search obtains lexical candidates and then calls embedding without a local failure fallback. The assistant's document tool uses a separate lexical path, so the startup error does not prove all file search fails. Native logs also show memory-pressure eviction and subsequent reloads. | Move warmup off the UI thread; expose service/model/index readiness internally. Preserve usable lexical results when semantic retrieval fails. Profile foreground inference, indexing and memory eviction together before changing their policies; background QoS already exists. | 4 / 4 / 2 | 32 |
| I3 | Chat falls back from `assistant_model` to the general `ollama_model`. The app runs with `plan_tasks=False`; absent an explicit contract, intent coverage is `unchecked`. A fluent final reply is not proof of a requested effect. | Evaluate the assistant role on representative app tasks, then choose its configuration. Reuse existing contracts and receipts for executable outcomes, including partial completion and clarification. Measure the cost of any extra planning call before adopting it. Do not label arbitrary prose as semantically verified. | 5 / 4 / 3 | 27 |
| I4 | Conversation history, notebook state and artifact revisions are held in memory. Note restore is an in-session undo, not restart recovery. Revision tracking exists, but derived results are not generally refreshed when their sources change. | Persist a coherent, versioned session snapshot using the existing ownership IDs. On restart, mark interrupted work as interrupted and revalidate local references. Track source revisions for derived results; refresh affected results or mark them stale. | 4 / 3 / 4 | 14 |
| I5 | Omnibar owns search helpers, model selection, workers, state projection and rendering. Companion state is largely reduced to busy/waiting/error/done, while progress text is written to several presentation objects. | Extract orchestration and one presentation projection incrementally. Derive companion, status and result updates from the same execution events. Keep the current registry, stores and worker guards; remove legacy routes only after reachability checks. | 4 / 3 / 3 | 21 |
| I6 | Software regressions and several local-file observations exist; a reviewed whole-app interaction baseline is missing. Standard model error paths also record unavailable token counts as zero. | Add a bounded journey recorder: first feedback, first usable result, final outcome, correction, cancellation and resource recovery. Preserve unknown metrics as unknown. Review actual outcomes separately from runtime errors and passing tests. | 5 / 4 / 2 | 36 |

I = impact, R = risk of leaving the issue, E = effort, each 1–5.
Score = `(I + R) * (6 - E)`. These are planning estimates, not measured defects
or delivery dates. Dependencies determine execution order within each phase.

Source anchors: [transport](../rat/engine/slm.py),
[window and workers](../rat/ui/omnibar.py),
[hybrid retrieval](../rat/engine/hybrid_search.py),
[runtime](../rat/engine/assistant_runtime.py),
[history](../rat/ui/chat_session.py),
[notebook](../rat/engine/work_notes.py),
[artifact store](../rat/kernel/contracts.py).

## 2. External: make that work feel like one experience

| Change | Intended behavior | Dependency |
| --- | --- | --- |
| One continuing work surface | Present the active goal, useful evidence and current result together. Update the relevant block when the user says “change this”; preserve its position and identity. Existing artifact views already preserve some identity and can show results before the final reply. Extend that behavior across related artifacts instead of adding more disconnected cards. | I4, I5 |
| A companion with a job | Receiving, searching/reading/calculating, arranging, presenting, asking and recovering have distinct readable reactions. A file or other deliverable enters through a handoff associated with a committed result. Animation never manufactures completion or delays an already available result. | I1, I3, I5 |
| A consistent bottom layout | Keep the composer and companion anchored below the work. Expand upward as content needs space. Set readable widths, typography and spacing across files, timetable, notes and tables. Avoid expanding a short reply into a mostly empty panel. Preserve selection, scroll and keyboard focus. | I5 |
| Correction through the same input | Accept follow-ups and scoped edits without requiring a function button. While busy, distinguish an accepted steering request from a retained draft. If the target is ambiguous, ask one focused question and retain completed work. Show errors beside the affected work with a plain-language recovery path. | I1, I3, I4 |

The artist handoff should specify reaction events, placement anchors, loop and
exit behavior, delivery timing and reduced-motion poses. The current companion
already supports bounded animation and reduced motion; preserve those controls.
The missing part is the richer connection between real work and presentation.

Source anchors: [presenter](../rat/ui/assistant_presenter.py),
[companion](../rat/ui/live_companion.py),
[layout primitives](../rat/ui/surface_layout.py).

## First implementation slice

1. Establish the whole-app baseline and timing recorder (I6). Include cold
   launch, model unavailable, a slow call, stop, and a new request after stop.
2. Fix readiness and execution lifecycle (I2, I1). Keep useful results on failure,
   bound outstanding calls, and prove that an old execution cannot affect the
   new one. Transport/backend cancellation behavior must be observed explicitly.
3. Validate executable completion and follow-up behavior across domains (I3).
   A new model choice or extra planner call is a decision supported by these
   runs, not an assumed cure.
4. Build the external work surface and companion reactions on that event flow
   (I5), then add session recovery and derived-result invalidation (I4).

Each slice should leave a runnable app. The first reviewable milestone is a
request that can finish, fail, be stopped and be corrected honestly across
several existing capabilities. Visual exploration can proceed using recorded
events while the internal fixes are being validated.

## Whole-app acceptance journeys

These are proposed checks, not completed results:

| Journey | Required observation |
| --- | --- |
| Find an actual local file, read it, ask a follow-up, obtain the original | Correct source and usable local reference; no invented read or delivery. |
| Calculate, change a number, ask what changed | Fresh calculation receipt and correct reference to the revised result. |
| Ask about timetable information, refine the day/person | Correct existing data or a focused clarification; retain the relevant result. |
| Record a note, amend it, undo the amendment | Correct note identity and revision; other work remains intact. |
| Build a result table, change an input/source, export | Dependent output is refreshed or visibly stale; exported file actually exists. |
| Change topic, then refer back to earlier work | Correct target or explicit clarification; no silent use of the wrong artifact. |
| Stop during a slow call, immediately submit another request | Responsive input, bounded outstanding work, no late commits from the old run. |
| Model unavailable, semantic search unavailable, file moved/deleted | Specific recoverable state; retain any valid partial result. |
| Hide/show, expand/collapse, long response, reduced motion | Bottom anchor, readable content, stable draft/scroll/focus and usable static poses. |
| Restart during work | Recover saved work honestly; do not claim interrupted work completed. |

Use deterministic fixtures for state/receipt checks and separately reviewed,
bounded real-model journeys for assistant behavior. A replay validates rendering
and interaction mechanics, not live model latency. App validation does not
establish NCKH model quality or alter the research Stage 0 gate. DocAI remains
outside the default RAT registry. No Git push is part of this work.

## Research informing the proposal

- [Microsoft Research: Guidelines for human–AI interaction](https://www.microsoft.com/en-us/research/blog/guidelines-for-human-ai-interaction-design/)
  supports efficient correction/dismissal, recent-interaction memory and
  graceful degradation. Applied here to steering, recovery and continuity.
- [Anthropic: Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
  recommends simple, composable execution, clear tools and measured iteration.
  Applied here to reuse the current kernel and evaluate changes before adding
  orchestration layers. These principles do not establish RAT's effectiveness.

## Latency follow-up

Inspection of run 13's existing private raw responses found 7 completed calls
and 1 timeout. For the completed calls only, summed server `total_duration` was
243.14 s: prompt evaluation 184.70 s (76%), generation 53.05 s, model loading
3.66 s. One call spent 61.26 s evaluating input and 6.56 s generating output.
The timeout is excluded because server phase timings are unavailable. These
numbers are a diagnosis of this run, not an app-wide benchmark.

The calls already used `think=false`, 8K context and a Q4 model. Tool schema
text was about 4,902 characters per request; cached prompt tokens were nonzero
after the first completed call, so caching was already partly effective.
The inspected machine is an Apple M1 MacBook Pro with 16 GB RAM. No model was
loaded when current Ollama status was read; GPU residency during the old run
was not established.

Prioritize smaller relevant observations/history and tool descriptions, a
stable reusable prompt prefix, and fewer model round trips for completed
executable outcomes. Preserve ownership, receipts and unresolved requirements.
Measure whether each change improves both latency and task success. Reduce
allocated context only after the actual request fits; do not truncate required
facts to force a smaller window. Streaming is a separate responsiveness change.
Warm loading and GPU/backend checks are secondary profiling work; loading was
only a small share of this run. A smaller model or alternate runtime needs a
quality-and-latency comparison before becoming the default.

[Ollama's chat API](https://docs.ollama.com/api/chat) defines the phase timings
used here. Its [FAQ](https://docs.ollama.com/faq) documents GPU residency checks,
preloading, `keep_alive`, context size and memory options. No configuration was
changed and no new inference requests were issued for this inspection.
