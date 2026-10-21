# RAT: result-first and public execution flow — 2026-10-21

The user selected two views of the work trace: a visual flow as the primary
detail presentation, and a compact summary in short mode. This follows the
UI polish pass and supersedes its short-answer-in-the-companion presentation.

## Presentation

- Completed answers appear first on the desk. The companion gives a short
  acknowledgment; the full original answer remains available through the
  result card's copy action. Sources and excerpts sit behind a disclosure after
  completion and stay visible during work. Opening them preserves the editor.
- `ExecutionFlowWidget` renders existing public `TraceEntry` events as a linked
  vertical flow. The line means event order, not a proof of causality. Details
  come from observed tool results, declared plans and recorded checks.
- Expanded mode defaults to the visual flow; compact mode defaults to one
  progress row. Clicking the row switches views. Each presentation remembers
  its own choice across resizing and reopening. Empty turns have no fake nodes.
- Status labels distinguish proposed/running/found/read, verification outcomes,
  unverified conditions, waiting, errors and cancellation. The UI does not
  infer that finding or reading a source verifies the answer.
- Flow links resolve only against the scene's observed sources. If a recorded
  step used an older artifact revision, a link to the current revision says so.
  Source inspection uses the existing view and does not trigger a new model
  call or document read. Nodes update in place rather than rebuilding inputs.
- Finder rows have one primary Open button. Hover/keyboard focus exposes a
  menu for Ask, Quick Look and Reveal, keeping the exact resource target.

## Boundaries and validation

No model behavior, routing/controller policy, stopping rule, verifier semantics,
research harness, Stage 0 gate or quality claims change in this UI work. Private
thoughts, model inputs and raw completions are not input to the flow widget.
The engine's existing public event construction remains unchanged.

`work/rat_ui_flow_20261021/` holds before snapshots, the scoped patch, command
logs, fixture captures, HTML gallery and validation report. Preview responses
and tool events are authored/synthetic; the document-read fixture reads its own
authored text and checks literal number presence. That narrow check is not
evidence of model reasoning quality or validity outside the observed text.

The first expanded render process exited with SIGBUS after producing captures;
subsequent diagnostic and multi-mode renders completed normally. The original
failure is retained. Offscreen tests/captures do not establish native desktop or
motion acceptance. The packaged app and macOS permissions remain unchanged.

## Minor interaction follow-up

`work/rat_ui_minor_fit_20261021/` records the follow-up requested by the user:

- Expanded mode now measures the active content before applying its existing
  screen/anchor height limit. Opening sources or the visual flow grows the same
  surface upward; folding them releases space. The bottom composer stays put.
  Wrapped content is measured again after resizing. If new content raises Qt's
  minimum above the old idle size, the initial fit anchors immediately; later
  transitions retain the existing animation. Idle dialogue aligns to the bottom
  even when the narrow layout has a few spare pixels.
- Size measurements use explicit child visibility, so hiding/reopening the
  window does not temporarily erase Finder content or its chrome height.
- Copying the full result briefly shows “Đã chép ✓” with a stable button width.
  Feedback resets on content/revision/status changes and after its timer.
- Finder rows also expose their secondary menu with Shift+F10 or the Menu key.
  The short flow row names the current public running step, with its full title
  retained in the accessible name and tooltip.

These changes preserve the mascot artwork, sizes and motion, the existing two
flow modes and backend semantics. The new regression journeys exercise result
disclosures with and without window animation, draft/selection retention, full
copy feedback, keyboard menus and Finder hide/reopen. Captures cover expanded,
compact and narrow layouts, with light/dark variants for the first two. They
remain offscreen fixture evidence, not native macOS acceptance or model-quality
measurements. The packaged application has not been rebuilt by this pass.

## Workbench and the “!” update bubble

The user requested folding the whole workbench and then clarified that “!”
should appear when there is new information worth inspecting. The header minus
button hides the canvas and its connecting trail. An unchanged, already shown
result stays quiet; the companion's “Xem kết quả” action can reopen it at any
time. An empty folded desk also retains a quiet “Mở workbench” action.

While folded, a 34px thought bubble beside the companion appears for new public
information: a completed result/revision, newly read source content, a recorded
check/calculation result, required input or an error. Metadata search hits,
progress text and streaming tokens alone stay quiet. Duplicate snapshots do not
repeat a notice. Opening the workbench acknowledges current notices, and folding
the same information again does not bring the bubble back. This is a fixed UI
event filter, not a model judgment of importance or a new verification claim.

The bubble uses existing paper/accent tokens, a visible focus border and a
tooltip/accessibility name describing the pending update. Recorded errors and
failed checks use the existing error color. It does not flash, play a sound or
open the desk automatically. It consumes public scene summaries only.

The canvas, source viewer, result renderers and editor stay alive. Reopening
restores their reading position after geometry settles. Input text/selection,
source selection and flow/disclosure choices remain intact. Updates continue
while folded. Keyboard users can Tab to either reopen action and use Space.
The fold and acknowledgement state survive hiding/reopening in the same chat;
a new chat clears them. Other sections keep their ordinary visibility. The
default remains the open workbench, with compact idle behavior unchanged.

`work/rat_ui_workbench_badge_20261021/` contains before snapshots, scoped patch,
tests and the current `gallery/` fixture gallery in six size/theme combinations.
Command records include source hashes to detect concurrent file replacement.
Offscreen evidence does not establish native macOS acceptance; the packaged app
remains unchanged. No model, controller, verifier or execution behavior changes.

One narrow-light render exited SIGBUS in native Qt code after printing capture
metadata. The fixture now explicitly destroys the window and drains deferred
deletion before interpreter exit; the retry is kept separately. The original
failure is retained, and its cause has not been established as a product defect
or a confirmed Qt teardown bug.
