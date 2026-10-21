# Antigravity — implement the approved RAT Workbench in native PyQt

Implement this task through to a working, visually checked native application.
The user has approved the design. This is implementation work, not another
design exploration. Do not stop at a plan, a browser mockup or a screenshot.
Make routine reversible implementation decisions without asking the user to
choose again. Keep the final report concise and evidence-based.

## 1. Objective and authoritative references

RAT should feel like a small desktop companion that handles work through one
bottom input. The selected interface is a **compact Workbench with separate,
closely aligned compartments**, and a prominent mouse companion. The user
explicitly rejected both a large window and one opaque box enclosing everything.

Start in `/Users/thundercock2/Documents/Github/multi-step-structured-reasoning`.
Read `AGENTS.md`, resolve the actual Git root/canonical checkout and any aliases,
and report the path, branch and HEAD used. Do not migrate repositories, change
remotes or edit multiple checkouts to resolve naming differences.

Read these project-local references in this order:

1. `docs/design/rat_workbench_20261015/approved-desktop.png` — approved default
   composition with the final, larger mouse. Inspect the actual image.
2. `docs/design/rat_workbench_20261015/approved-fragment.html` — exact current
   geometry, typography, colors and local presentation interactions. It contains
   an embedded PNG: do not dump base64 into logs or model context. Strip image
   data when reading source as text.
3. `docs/rat_workbench_design_20261015.md` — detailed handoff, including narrow
   and expanded geometry, input behavior, motion and native acceptance.
4. `docs/design/rat_workbench_20261015/reference-narrow.png`,
   `reference-expanded.png`, `reference-dark.png` — other presentation states.
5. `docs/design/rat_workbench_20261015/manifest.json` and
   `browser-validation.json` — frozen reference hashes, source baseline and
   prototype-only evidence. They do not establish native or model correctness.

The reference HTML uses synthetic examples, local keyword matching and an
850 ms timer. Those are demonstration mechanics, **not production logic**.
Do not port its fixed answers, sample study plan, sample file, keyword router,
timer, widget-state writer, Tweak controls or browser host APIs into RAT.
Implement the native UI using real existing RAT data and execution events.

Priority when interpreting references: the approved compact separated design
with 104px desktop mouse; then the detailed spec; then existing implementation
where it does not conflict. Earlier mockups, including `rat-work-surface.html`,
the small-mouse revision and the enclosing opaque-shell revision are obsolete.

## 2. Scope and repository discipline

This task is the **external/UI implementation**. Runtime intelligence, inference
speed, persistence infrastructure and research work remain separate tasks.

- Stay in PyQt6. Do not rewrite as a web/Electron/Tauri application, embed the
  HTML through a web view, introduce a new UI framework or download new fonts.
- Work on `main`. Do not create feature/checkpoint branches. No push, pull,
  reset, force operations or publication are authorized by this prompt.
- The checkout is already dirty. Record a scoped baseline before edits and
  preserve all pre-existing changes, untracked material and recovery files.
  Do not stage unrelated work. Do not commit unless separately requested.
- In particular, existing research, `rat/engine/context_snapshot.py`, its tests,
  build scripts and DocAI/intake work are not yours to revert, overwrite or
  opportunistically refactor. Re-read a file before editing if another agent
  may have changed it.
- Keep DocAI out of the RAT default registry/startup. Do not change research
  protocols, model behavior/defaults, planner flags, tool schemas, verifier
  semantics, artifact ownership or the Stage 0 gate.
- Do not optimize Ollama or change the user's saved model, start downloads,
  rebuild their index or run a real-model campaign as part of this UI task.
- Keep the approved reference packet immutable. Put implementation evidence
  separately, without personal file content, raw model prompts or full traces.

## 3. Visual contract: preserve this composition

There are three visually separate parts within one coordinated interaction:

1. **Work canvas** above: a quiet paper card with a small brand header, actual
   work title and useful result content. Only this canvas has a subtle elevation.
2. **RAT stage and speech** directly below: the mouse stands outside the card,
   with a short speech bubble whose tail points back toward it.
3. **User speech/composer** below that: a softly green bubble, tail down-right,
   aligned with RAT speech on desktop. This is the sole editable main input.

The outer layout is transparent and unframed. Do not put all three parts back
inside a large white rectangle. Do not add a dashboard, navigation rail, feature
tiles, send button, action strip, model picker, technical badge or tool menu to
the default experience. Existing diagnostic controls remain behind
`RAT_DEBUG_UI=1`.

Compact defaults at normal text size:

- Visible group width approximately **520 logical pixels**. The approved
  three-row plan specimen measures approximately **520 × 335 CSS px** in the
  browser. It is a sizing reference, not a hard height for all native content.
  Allow modest transparent shadow margins; do not turn those into giant padding.
- Canvas radius 16; inner padding approximately `8,16,5`; title 20/medium.
  Three compact rows show index, title and duration only when those fields
  actually exist. Row title 14, duration/secondary UI 12, row padding 5 vertically.
- Hide secondary descriptions and repeated metadata in compact view, with
  “Nói ‘xem chi tiết’” as the presentation affordance. Preserve the full content.
  Long essential names and critical questions/errors must remain accessible.
- Gap from canvas to RAT stage: approximately 8. Desktop actor column 112,
  gap 8; RAT and user speech therefore share a left inset of 120 and the same
  right edge. Desktop user composer is not full-width across the canvas.
- **Final approved desktop mouse is 104px wide**, increased from 80. The layout
  slot is 112 × 82; the illustration uses free space beside the composer, not
  extra window height. Its image starts around y=-1 within that slot. See the
  reference and exact ground/prop anchors in the spec.
- RAT speech uses paper fill, 13px text and approximately `9,12` padding.
  User bubble uses approximately `9,13` padding and 15px editable text.
  Keep the subtle parent-bubble focus indication; no second inner rectangle.
- On narrow group widths around 450 and below: **80px mouse**, 84 × 88 slot,
  7px dialogue gap, full-width user composer underneath. Keep input readable
  at 16px where appropriate; do not scale the entire interface down as an image.
- Expanded reading is approximately 640px wide. Reveal retained detail and
  history while keeping the same work, composer, draft and bottom anchor.

Use the system sans family with reliable Vietnamese diacritics. Match the
approved light/dark tokens rather than scattering QSS literals. CSS variables,
`light-dark()`, layout grids and CSS tails are references to translate into
native palette/layout/QPainter behavior; do not assume Qt QSS supports them.

Keep the sprite's silhouette, eye and limbs crisp. Reuse the existing full-body
RAT artwork under `rat/assets/`; do not replace it with emoji or newly generated
art. The artist will supply richer animation later.

## 4. Native geometry and interaction requirements

Anchor the actual window/composer near the **bottom** of the available screen.
When content or reading mode grows, grow upward, preserving the bottom anchor
where space allows. Use available geometry excluding the Dock/menu bar. Handle
multiple monitors, negative screen coordinates and screen/scale changes.

Long work must scroll in the upper reading area rather than pushing the input
offscreen. Idle/empty mode should be smaller than the three-row specimen; do not
reserve an empty full-height canvas. At large text sizes or very small screens,
prioritize readable text and an accessible input over exact specimen dimensions.

Qt-specific pitfall: HTML allows the 104px sprite to overflow an 82px layout
slot. A native QWidget painter may clip it. Use a transparent overlay/staging
arrangement with sufficient real paint bounds while keeping the visible group
compact. Never clip feet, tail, prop or bounded motion. Keep decorative artwork
out of input hit areas and keyboard focus. Do not make the whole app transparent
to mouse input just to obtain click-through decoration.

Retain one `ChatComposer` object across modes. Preserve draft, selection, cursor,
focus, reading position, active execution and artifact identities. Do not rebuild
the whole widget tree or resubmit a request when resizing or changing modes.

Enter submits exactly once; Shift+Enter adds a newline; IME composition must not
submit. Preserve the existing text-stop/Escape behavior and late-result guards.
Do not claim that this UI task cancels the blocking backend transport.

Recognize only the explicit presentation commands from the spec, e.g.
“xem chi tiết” / “thu gọn”, before the normal task/busy-submit path. These must
change presentation without a model call, new user turn, new artifact, reset,
task cancellation or invalidation of the running execution. Preserve current
work and hidden detail. Keyboard mode changes must preserve an unsent draft;
typed view commands consume only their own command text. Do not intercept
ordinary requests merely because they contain the word “chi tiết”.

Keep the existing honest handling of input while busy. Do not pretend a retained
draft was accepted as steering. A clarification uses the same composer; do not
force the user into hidden forms or feature buttons.

## 5. Bind presentation to the real application

Inspect these existing seams rather than inventing a second controller:

- `rat/ui/omnibar.py`: `OmnibarWindow`, `_init_ui`, `_resize_overlay`,
  `_surface_height`, `set_expanded`, `_sync_compact_surface`, submission,
  progress/step/response handlers, artifact actions, cancellation and shutdown.
- `rat/ui/surface_layout.py`: `ChatComposer`, `CurrentPageStack`, motion policy.
- `rat/ui/live_companion.py`: current companion states, painting, reaction timing,
  hidden-window timer suspension and reduced motion.
- `rat/ui/assistant_presenter.py`: `ArtifactPanel`, actual observed file cards,
  revision-aware views and `source_panel`.
- `rat/ui/chat_stream.py`, `chat_session.py`, `work_context.py`: conversation,
  history, file opening, work notes, drafts and reading behavior.
- `rat/ui/assistant_worker.py` and the existing runtime/kernel contracts: consume
  their signals and typed results; preserve their execution guards.

A small reusable native Workbench surface and shared visual tokens are welcome.
Keep runtime orchestration in the existing runtime/dispatcher/notebook/store.
Do not create another source of task truth or import Qt into headless research
or capability modules. Avoid adding more independent renderer paths to Omnibar.

Use real artifact IDs/revisions and existing selected results. A new revision
updates the relevant view in place; keep unaffected views, selections and drafts.
Compact presentation must work for actual files, calculations, timetable results,
notes and tables. The sample study plan is a visual example, not a required new
planning capability or a hardcoded home screen.

RAT's short speech and work content are different presentation roles. Preserve
the full actual assistant response in conversation/history. Show short factual
acknowledgements only when supported by actual state; do not invent a summary,
duration, source, completion or success from fluent text alone. Keep critical
clarification and error information readable. Long answers belong in reading
content rather than an enormous speech balloon.

Show useful results as committed steps arrive. Do not delay an available file
until a decorative animation or final model sentence completes. File cards must
come from trusted typed observations/receipts and open the exact observed path
on click/Enter. Never parse assistant prose into an attachment. Missing/moved
files need an explicit unavailable state. Preserve deduplication across
search/read/delivery and do not auto-open or copy files without the existing
user-triggered interaction.

Drive working, asking, result-ready, error and stopped reactions from actual
events. Motion must not mutate tasks, submit input or imply an unobserved effect.
Honor OS and app reduced-motion settings, stop idle timers while hidden and
guard delayed callbacks against deleted Qt objects. Keep default UI free of
raw reasoning traces, token metrics, tool internals and debugging forms.

## 6. Implementation and verification sequence

1. Inspect the actual approved images and current UI seams. Record the baseline
   and existing targeted failures, then implement the native composition.
2. Apply the layout and styling through reusable widgets/tokens. Preserve live
   signal wiring and compatibility aliases where they still have a purpose.
3. Wire compact/expanded projection and presentation commands. Check widget
   identity, drafts, focus, scroll and bottom anchoring before polishing motion.
4. Render native Qt screenshots with deterministic fixture results. Compare
   them visually to the approved reference and correct the visible differences.
5. Run focused regression checks and a real native-window smoke. Finish the
   implementation and report precise evidence and remaining limitations.

Prefer the installed Python environment that actually has PyQt6/pytest. The
local `.venv` has previously lacked GUI dependencies. A known useful interpreter
is `/Users/thundercock2/.local/bin/python`; verify it before use. Native entry is
`python -m rat.main spotlight`. Do not use a nonexistent `rat.__main__` entry.

Relevant existing checks, adapted to the available interpreter:

```sh
QT_QPA_PLATFORM=offscreen python -m pytest tests/test_rat_magic_ui.py tests/test_rat_one_box_ui.py tests/test_work_context_ui.py tests/test_rat_chat_session.py tests/test_rat_verification_ui.py tests/test_work_context.py -q
```

Qt may require the host's normal permission mechanism to launch even offscreen.
Use it when needed; do not weaken security settings or silently skip GUI checks.
Do not run unrelated research suites for a UI-only patch. If scope unexpectedly
touches research/model behavior, stop that expansion and follow `AGENTS.md`.

Add/update focused tests for meaningful changed behavior: layout bounds and
non-overlap, compact/detail transition during a request, one editor identity,
draft/selection/focus retention, no model call for view commands, exact local
file opening and stale callback protection. Some existing tests assert the old
widget geometry/layout indexes: replace only assertions genuinely superseded by
the approved design, retaining their functional intent. Do not delete difficult
tests, weaken correctness guards or count known baseline failures as new passes.

Required visual/interaction coverage:

- Empty, short reply and long answer; plan-like table, calculation, note and file.
- Working → partial result → completion; clarification; partial error; stop with
  a late callback; new request afterward; input typed while busy.
- Compact ↔ detail during idle and work; hide/show; multiline Vietnamese input,
  selection/copy; enlarged text; narrow windows; screen edges and display scale.
- Light/dark and reduced motion; no cut-off actor, overlapping text, clipped
  bubble tail, giant blank panel, duplicate composer or unexpected focus jump.
- Actual existing local file or harmless real on-disk fixture: use the real
  typed dispatch/presenter path, confirm existence and exact opening target.
  Keep private paths/content out of committed evidence. Label temporary fixtures
  as fixtures; do not present them as a personal-corpus search success.

For the native smoke, ensure a freshly launched process uses your edited source.
Opening an already-running old RAT instance is not verification of the patch.
Avoid killing unrelated Python/Ollama processes. Label offscreen Qt render,
native Cocoa window, fixture replay and any actual model run separately. Browser
reference checks are not native proof. No model-quality claim follows from UI
tests or a deterministic replay. Backend slowness remains a separate issue.

## 7. Deliverables and finish condition

Leave a working native Workbench implementation and focused tests, plus a short
implementation note with changed files, exact checks, before/after native
screenshots, measured specimen bounds and material limitations. Store shareable
fixture-based evidence separately from private real-file evidence.

The task is complete when the real Qt app reproduces the approved **compact,
separate-but-aligned** visual structure, the larger RAT is clearly visible, the
input remains at the bottom, real existing workflows still function and the
targeted checks pass or any pre-existing failures are independently documented.
Do not report completion for another mockup. Do not broaden into runtime/model
optimization, new features or a product redesign. Do not push.
