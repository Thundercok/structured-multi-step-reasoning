# Codex review: RAT interaction kernel

Date: 2026-10-11. Scope: review and repair Gemini's Option 2 implementation,
while retaining the declarative presentation boundary for future Option 3.

The repaired implementation supports an inline birth-data request, a chart from
the existing calculation service, editing that chart, and explicit file exports.
Native model tool calls and direct controls use the same dispatcher. The checks
below establish software behavior with fixtures; they do not establish live-model
task quality or a learned controller's effectiveness.

## Review baseline and ownership

The workspace already contained extensive tracked and untracked changes. This
review did not revert, stage, commit, push, pull, reset, clean, or stash them.
Research sources, model settings, and dependency declarations were not changed.

- The original handback remains at
  `../rat_interaction_kernel_gemini_20261011_211500/REPORT_FOR_CODEX.md`.
- `before/` and `baseline_sha256.json` preserve the 18 source, specification, and
  test files captured before this review's edits.
- `review_changed_files.json` lists the 26 implementation, test, and documentation
  files changed or added by this review. Audit evidence files are additional.
- Scope follows `docs/adr-001-rat-interaction-kernel.md` and
  `docs/GEMINI_RAT_INTERACTION_HANDOFF.md`.

The original nine kernel fixtures primarily called handlers/dispatch directly.
They did not exercise the complete native-tool validation and Qt control paths.
The following findings came from inspection and added regression scenarios;
they are not a claim that the original untouched test suite failed.

## Findings and repairs

| Finding | Repair and observable result |
| --- | --- |
| Required native birth arguments prevented partial requests from reaching the handler. | A partial `create_natal_chart` call returns a stored `InputRequest`; the runtime ends that turn with `needs_input` and preserves supplied fields. |
| Native chart editing had no usable target/revision contract. | Target identifiers and revisions are exposed in tool schemas and model context. `inspect_artifact` reads an exact stored revision. Ambiguous references request clarification. |
| The time-edit button was a no-op. | Registered action input schemas produce real inline editors; Apply dispatches the edited value against the selected chart revision. |
| Export and document reading overwrote their source artifacts. | Export creates a `file_export`; reading creates `document_content`. Source charts and search results retain their identity and payload. |
| Progress updates destroyed partially completed forms. | `ArtifactPanel` keeps widgets by artifact ID/revision and updates incrementally. Chat progress reuses the panel. |
| View validation allowed arbitrary action prefixes and unbound resource content. | Views must use exact registered actions, valid versions, and permitted artifact field references. Resources bind to the observed artifact field; an alternative provider cannot inject replacement chart data. |
| IDs used timestamps; revisions could be overwritten; late results could reappear after reset. | UUID identities, monotonic revisions, revision/generation checks on commit, dispatcher reset, and GUI callback generation checks prevent these cases. |
| Direct actions and place lookup blocked the UI thread. | `ArtifactWorker` runs dispatch/resume off the UI thread with busy-state, shutdown, and reset handling. |
| Chart rendering recalculated data instead of displaying the observed result. | `NatalChart.from_dict` restores calculated positions/aspects. Registered Qt resource renderers consume that result without recalculation. |
| Detailed chart presentation omitted some positions and lacked house/aspect tables. | All positions, precise degrees, twelve house cusps when available, full aspects, and uncertainty notices are accessible through inline details. |
| Failed place lookup and repeated DST hours had no usable next step. | Typed coordinate/timezone controls allow manual location entry. A repeated-hour request offers the first or second occurrence and resumes with the chosen fold. |
| A central view-kind branch and duplicate tool/action declarations remained. | Operations register their view factories, resource bindings, and actions. Native definitions derive from the registry; a custom capability regression needs no core provider branch. |
| Declared output contracts were not enforced. | Invalid declared output is rejected before publishing an artifact. |

## Resulting interaction boundaries

Normal chart navigation and pending-input submissions remain in RAT's compact
conversational surface. They do not construct a natal feature `QMainWindow`.
An explicit request to expand the notebook and the existing standalone advanced
chart viewer remain available.

Missing input becomes a versioned pending artifact. Resume submits real values
or a validated candidate index to the same dispatcher; the resolved pending form
is removed from the current presentation. An edit preserves the target identity
and advances its revision. Independent read/export outcomes receive their own
identities. Actions carrying stale revisions are rejected, and a reset invalidates
in-flight commits and callbacks. Task history records pending attempts truthfully.

The UI presents artifacts changed during the current turn rather than repeating
the entire store. Document results offer explicit open/read controls; reading is
distinct from merely finding a file. The OS-open path uses an argument list for an
indexed existing path. No actual OS file-open action was executed during review.

The standard view provider delegates to registered operation factories, and the
renderer resolves resources through registered renderers. An invalid optional
provider falls back to the standard view of the actual artifact. This is preparation
for Option 3; no AI-generated presentation or arbitrary code runner was added.
Validation checks structural contracts and authorized references/actions. It is
not a general verifier of the factual meaning of arbitrary prose.

Exports require an explicit destination. SVG is headless. PNG/PDF use an existing
Qt GUI application for painting and require no feature window; they are not
advertised as cold-process, Qt-free exports.

## Verification evidence

Commands use `python3.12`. Qt checks used `QT_QPA_PLATFORM=offscreen` with the
native execution permission needed in this environment. Tests use fixtures and
stubbed services/models. Counts overlap; do not sum them into a unique total.

| Check | Command | Result and log |
| --- | --- | --- |
| Runtime, kernel, memory, natal calculations and places | `python3.12 -m pytest tests/test_interaction_kernel_regressions.py tests/test_interaction_kernel.py tests/test_assistant_runtime.py tests/test_rat_task_memory.py tests/test_rat_chat_session.py tests/test_slm_chat.py tests/test_natal_chart.py tests/test_natal_places.py -q` | 93 passed; `headless_final.txt`. This run preceded the last two added contract regressions. |
| Integrated Qt controls, omnibar, chart, timetable cards and workers | `QT_QPA_PLATFORM=offscreen python3.12 -m pytest tests/test_interaction_kernel_ui.py tests/test_omnibar.py tests/test_natal_chart_ui.py tests/test_timetable_chat_cards.py tests/test_assistant_worker.py -q` | 81 passed and 3 subtests passed; `qt_final.txt`. One existing FastEmbed pooling warning. This run preceded the last manual-input component test and final resource-reference adjustment. |
| All new component controls after manual-coordinate/fold additions | `QT_QPA_PLATFORM=offscreen python3.12 -m pytest tests/test_interaction_kernel_ui.py -q` | 7 passed; `qt_controls_final.txt`. |
| Latest resource binding and rejected-provider regressions | `QT_QPA_PLATFORM=offscreen python3.12 -m pytest tests/test_interaction_kernel_ui.py -k 'render_uses or rejected_provider' -q` | 2 passed, 5 deselected; `resource_qt_final.txt`. |
| Latest output contract, strict view references, and JSON-roundtrip unknown-time chart regressions | `python3.12 -m pytest tests/test_interaction_kernel_regressions.py -k 'declared_output or view_rejects or serialized' -q` | 3 passed, 14 deselected; `contracts_final.txt`. |
| Required research smoke checks | `python3.12 -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q` | 29 passed; `research_smoke.txt`. Research implementation unchanged. |

The first extended Qt run exposed missing house/aspect presentation:
`qt_checks.txt` retains the failure (1 failed, 77 passed, 3 subtests passed).
The implementation was repaired and the subsequent focused/full runs passed.
Earlier iteration logs are retained as development evidence, not extra independent
benchmarks. Python compilation and whitespace checks cover the review's files.

`preview.py` generated `inline_birth_fixture.png` and `inline_natal_fixture.png`
from the actual inline components. Both were visually inspected. These are
component previews with artificial birth inputs, not a full live RAT screenshot
or a model-produced result.

## Remaining validation and claims

- No new live Ollama requests, model benchmarks, latency measurements, or controller
  training were performed. Passing these tests does not prove semantic tool choice,
  multi-step request completion, or learned stopping behavior.
- The existing Stage 0 research gate was preserved. These changes do not advance
  it or support new manuscript/model-quality claims.
- The default model and inference settings were preserved. No dependencies or
  additional models were installed.
- The PyInstaller specification includes the new modules, but a frozen `.app` or
  `.dmg` was not rebuilt or validated in this review.
- Option 3's generated views, isolated code/components, and dynamic plugin discovery
  remain future work. The current implementation provides registered operations
  and constrained presentation, not a model that invents arbitrary new abilities.

The original handback's broader completion claims should be read together with
these corrections and the evidence boundaries above.
