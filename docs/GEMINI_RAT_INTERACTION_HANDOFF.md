# Implementation handoff to Gemini: RAT interaction kernel

You are taking over implementation in this existing repository:

`/Users/thundercock2/Documents/Github/multi-step-structured-reasoning`

The user has authorized work on option 2 below, with architectural preparation
for option 3 in the far future. Implement and verify the current scope. Do not
stop at a plan or another architecture document. Codex will review your changes
and correct them in a later session. Leave concrete, inspectable evidence.

## Product intent

The user does not want every capability to become a large application or a
separate workflow. They want to ask naturally, receive the useful result directly
in a small conversational surface, and use a few easy controls or a follow-up
sentence to continue working on that result.

Their examples: class timetable, file search, and a detailed personal natal chart.
They explicitly rejected merely shrinking the existing natal window or inserting
three unrelated feature widgets into chat. This is an architectural change.

- **Option 2 now:** shared capability/operation contracts, input requests,
  versioned artifacts, actions, execution state and a common presentation system.
  The live model interprets requests and composes operations. Registered services
  perform actual retrieval/calculation.
- **Prepare for option 3:** presentation uses a versioned declarative contract
  independent of Qt and of the provider that produces it. A future model could
  propose views; farther in the future, new components or capabilities could be
  generated and checked in an isolated runner. Build the boundaries now. Do not
  implement model-generated executable code, an isolated runner, an AI view
  inference stage, or a large plugin framework in this task.

Read `docs/adr-001-rat-interaction-kernel.md` for the design rationale and proposed
boundaries. The implementation request is authorization to proceed with the
current scope; do not treat its earlier Proposed status as a requirement to ask
the user for routine implementation permission. Record actual implemented scope
honestly; leave future milestones labeled future work.

## Read first and protect existing work

1. Read `AGENTS.md`, `docs/research_plan.md`, `docs/research_protocol.md`,
   `docs/adr-001-rat-interaction-kernel.md`, `docs/rat_assistant_development.md`
   and `docs/natal_chart.md`.
2. Inspect the actual source before designing changes. Capture the initial git
   status. This workspace already contains substantial modified AND untracked
   work from other tasks. Untracked source files are real work, not disposable.
3. Preserve unrelated edits, especially research experiments, test changes,
   existing audit bundles, datasets, model settings and bundled ephemeris data.
   Never clean, reset, stash, revert, or overwrite them to obtain a clean tree.
4. Do not git push/pull/reset/force. Do not stage or commit on the user's behalf.
5. Research remains the primary project outcome. This UI/runtime task is
   explicitly requested, but it does not authorize changing the research scope,
   fitting/deploying a controller, changing Stage 0, or making model-quality claims.

## Current implementation: inspect rather than assume

- `rat/engine/assistant_runtime.py`: real native tool-calling loop, tool schemas,
  execution validation, raw traces, costs, observed sources and task memory.
  There is already live model selection; do not resurrect a simulated reference
  policy or keyword intent dispatcher. Central tool/source branches are a
  migration target, not the desired extension mechanism.
- `rat/engine/task_state.py`: model-authored task descriptions. A model status of
  completed is not execution verification or a reviewed success label.
- `rat/ui/assistant_worker.py`: Qt worker, progress, stop and response handling.
- `rat/ui/assistant_presenter.py`: separate document/schedule presenters and a
  natal button that currently opens a dedicated window.
- `rat/ui/chat_stream.py`: streaming messages, file cards, timetable cards and
  replacement of result widgets during updates.
- `rat/ui/omnibar.py`: UI/runtime integration; `open_natal_chart` currently hides
  the main RAT surface and opens `NatalChartWindow`; submitting chat currently
  calls `set_expanded(True)`. Inspect compact geometry and content visibility
  before changing this so results remain readable.
- `rat/ui/chat_session.py`: bounded successful history plus truthful context for
  failed/cancelled requests. Preserve that distinction.
- `rat/astrology/chart.py`, `places.py`, `svg.py`: actual deterministic chart
  calculation, place lookup and accurate vector rendering. Reuse these services.
- `rat/ui/natal_chart.py`: the existing large natal application, controls,
  interactive wheel, profile and SVG/PNG/PDF exports. Reuse useful mechanics,
  factoring them out if needed; do not instantiate its QMainWindow to implement
  inline execution. The explicitly invoked standalone CLI may remain available.
- `rat/os/app.py`, `rat/os/menu_bar.py`, `rat/main.py`, `rat.spec`: navigation and
  packaging paths that may need consistent integration updates.

The current default assistant inherits the document model unless an assistant
model is explicitly selected. Previous real-model development attempts include
wrong tool choices and timeouts. Do not change defaults, download models, increase
budgets or run a broad live benchmark as a substitute for this refactor.

## Implement the shared foundation and migrate the three capabilities

Choose simple module boundaries appropriate to this codebase. Suggested contract
names below describe responsibilities, not a mandatory directory layout.

### Headless contracts and runtime

- A `CapabilityRegistry` registers operation descriptions, typed input schemas,
  handlers, result contracts and actions. Native tool definitions and execution
  should derive from registrations rather than separately maintained central
  lists and branches. Domain-specific code belongs in registered adapters.
- `InputRequest` belongs to a pending operation/task, carries validated supplied
  inputs and the fields/candidate choices still needed, and can resume the same
  operation. Support natural-language replies AND direct input. Do not introduce
  a keyword router to decide when to show a birth form.
- An `Artifact` has a stable ID, kind, revision, payload, inputs and provenance.
  An `ArtifactStore` preserves prior revisions and relevant task relationships.
  Keep actual observations available for grounding separately from user-facing
  deliverables. Define lifecycle/reset and reasonable bounds; do not create an
  unnecessary persistence/database project.
- `ArtifactAction` and `ActionDispatcher` bind direct controls and model requests
  to the same registered operation and target artifact/revision. Detect stale
  revisions. Do not silently update another artifact when a reference is unclear.
- Runtime execution events describe actual waiting, execution, failure and
  artifact creation/update. Keep these distinct from model-authored descriptions.
  A completed tool result can be shown before the final model synthesis arrives.
- Preserve native tool messages, cancellation, token accounting, raw failures,
  and current headless collector compatibility. Update consumers where necessary
  rather than quietly dropping evidence or breaking exported runtime contracts.

### Presentation and preparation for future providers

- Define a serializable, versioned `ViewSpec`, a `ViewProvider` interface and a
  common `ViewRenderer`. Use a standard provider today; do not make an extra model
  call to design each view. Data/contracts must not import Qt or contain widgets.
- Start with a small real component vocabulary: short text/summary, rows or
  tables, vector/image resource, input fields, actions and expandable details.
  Implement the components needed for all three capabilities; avoid speculative
  abstractions and empty scaffolding.
- Bind fields/resources/actions to actual artifact/capability references. Reject
  unknown schema versions, unsupported blocks, invalid references and invented
  actions. A rejected optional presentation proposal must not corrupt the artifact
  or disguise a failed model answer as success.
- Keep domain renderers, such as the natal wheel, registered and independent of
  application navigation. Domain rendering is legitimate; a domain-owned mini-app
  with its own conversation/input lifecycle is not this design.
- Keep view/widget updates attached to stable artifacts. Do not recreate all
  active input fields on every progress event, lose edits, or duplicate the same
  artifact under every follow-up. Handle immutable historical revisions clearly.
- Switching the view provider should preserve the artifact, pending operation and
  available actions. This seam is sufficient preparation for future AI-generated
  views; do not implement arbitrary code execution now.

### Visible product behavior

- Asking for a natal chart without birth data offers only the necessary missing
  information within the conversational surface. Do not silently use the sample
  birth date, today's date, a previous unrelated profile or guessed coordinates.
  Resolve place ambiguity explicitly using real candidates.
- With valid data, show the actual chart at once, with a readable wheel and a few
  relevant controls. Details, adjustments and export are available progressively
  in that workflow. No forced giant feature window or hidden RAT surface.
- A follow-up such as “đổi giờ sinh thành 9:30” addresses the referenced chart,
  recalculates through the same operation/action path and retains history.
  Two candidate charts require clarification if the user's reference is unclear.
- Schedule and file results use the same artifact/action/presentation lifecycle.
  Distinguish finding a file from reading it. Opening a file on explicit user
  action is fine; launching feature applications automatically is not.
- Existing natal nav/menu entry points enter the shared workflow. Explicit direct
  entry is a user action, not permission to add language keyword routing.
- Keep a useful compact surface by default. Expand details when requested. Do not
  simply remove expansion and leave results invisible or clipped.
- Use RAT's existing paper/ink/gold visual language and clear Vietnamese copy.
  Avoid exposing raw schemas, birth JSON, internal task bookkeeping or technical
  architecture terms as the normal user experience.
- Preserve chart precision, unknown-time omissions/uncertainty, DST validation,
  place lookup rules, profiles and SVG/PNG/PDF export correctness. Factor existing
  export utilities out where useful; maintain the standalone advanced CLI.

## Acceptance scenarios and meaningful verification

Demonstrate these using deterministic fixtures for software contracts. Label those
fixtures/scripted decisions explicitly; they do not measure AI understanding.

1. Request a natal chart with partial data → fill only missing inputs → get an
   actual computed chart in the same surface, without constructing a feature
   QMainWindow. Supplied inputs survive progress updates.
2. Change the birth time through a direct control and through a scripted native
   model action → same dispatcher semantics, recomputed chart, stable artifact ID
   and a new revision, prior revision preserved. Stale controls are detected.
3. Schedule lookup and file search/read both produce artifacts through the same
   foundation. Partial/model failures preserve actual results and accurate status.
4. A composed request uses schedule, search and reading in one task rather than a
   hardcoded preparation-plan feature. Check plumbing, not a scripted success claim.
5. Two charts with an ambiguous reference do not cause silent modification.
6. Register a small test capability without modifying central UI/runtime branches;
   it produces a usable standard view and action through the same contracts.
7. Swap the standard provider for a test provider on the same artifact; preserve
   state/actions. Invalid schema/field/resource/action references are rejected.
8. Stop, retry, chat reset, pending input and delayed worker callbacks do not
   lose results, leak workers or attach events to the wrong turn/artifact.
9. Headless contracts/runtime do not depend on Qt or launch file indexing. Preserve
   the research entry point's independence from RAT UI and personal data.

Run appropriate new contract/UI tests plus affected existing suites. Python 3.12
and PyQt6 are available; `pyswisseph` was installed previously. On macOS, offscreen
Qt tests may need the environment's normal approval mechanism. Report genuine
execution failures or unavailable dependencies; do not weaken tests to hide them.

Existing relevant test commands (add new tests for the kernel you implement):

```bash
python3.12 -m pytest tests/test_assistant_runtime.py tests/test_assistant_worker.py tests/test_rat_task_memory.py tests/test_rat_chat_session.py tests/test_slm_chat.py tests/test_natal_chart.py tests/test_natal_places.py -q
QT_QPA_PLATFORM=offscreen python3.12 -m pytest tests/test_omnibar.py tests/test_natal_chart_ui.py tests/test_timetable_chat_cards.py -q
```

Use `QT_QPA_PLATFORM=offscreen` for any suite importing Qt. An existing omnibar
test expects the old `_natal_window`; update it to assert the intended shared
workflow rather than preserving the rejected UX. Retain useful standalone atlas
regressions. Tests that mirror trivial helpers are less useful than the scenarios
above. Check packaging imports/resources if adding modules. Do not claim a frozen
`.app` or `.dmg` is updated unless you actually rebuilt and verified it.

If research harness or threshold fitting changes become necessary, explain why,
keep scope narrow, and run the AGENTS-required checks:

```bash
python3.12 -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q
```

Prefer keeping those areas unchanged. Preserve Stage 0. Software tests, mock
outputs and UI screenshots are not evidence of measured model quality. No live
experiment is required for this implementation handoff. If you run a small local
development probe, preserve raw requests/results, actual latency and reported
prompt/completion counts; keep failure counts unknown when unavailable. Do not
claim unseen evaluation, a learned deployed controller or improved model quality.

## Required handback for Codex

Create a NEW directory such as
`audit/rat_interaction_kernel_gemini_YYYYMMDD_HHMMSS/`; do not overwrite older audits.
Leave `REPORT_FOR_CODEX.md` with:

1. Initial workspace status and the exact files you changed/added in this task,
   distinguished from pre-existing changes. Do not imply all dirty files are yours.
2. Implemented contracts, module boundaries, actual request/action/event flow, and
   any compatibility or lifecycle choices needed to review the change.
3. A scenario-by-scenario acceptance matrix: passed, failed or not checked, with
   evidence. Include UI screenshots of genuine fixtures/new views if possible;
   identify fixture values and do not present them as the user's personal chart.
4. Exact test commands, results, environment limitations and remaining failures.
   Record checks actually run, not anticipated success.
5. What remains incomplete in the current scope and what is deliberately future
   work. If stopping early, say so; a registry-only scaffold is not a completed
   product migration. Do not call option 3 implemented.
6. Dependencies/settings changed, compatibility risks, and the main review points
   for Codex. Do not change defaults or add a service silently.
7. Entry points to try the changed app and any preview/test scripts you created.

Update user documentation to describe the implemented workflow. Finish with a
concise Vietnamese explanation and an absolute path to the handback report.
Do not promise that Codex is already monitoring or will resume automatically.
The user will return to the existing Codex chat; Codex can then inspect the report,
the actual code and your task-specific changes before correcting problems.
