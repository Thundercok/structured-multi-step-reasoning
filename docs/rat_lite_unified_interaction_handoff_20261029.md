# RAT Lite .24 — unified interaction source handoff

2026-10-29. Implements the [interaction plan](rat_lite_unified_interaction_plan_20261029.md)
in small commits on main, as explicitly requested. Source only: no test, smoke,
build, launch, screenshot or live acceptance was run. Existing app bundles do
not contain this revision. Runtime/build metadata source is now `20261029.24`.

## Source changes

- `MiniPresentation` owns extent, composer visibility, source comparison and the
  existing interaction object. Old workspace values are computed compatibility
  aliases rather than independent mode state. No stored mode migration was
  needed in the inspected entry/settings path. Existing launch flags remain.
- One editor instance moves between the compact SpeechBubble accessory slot and
  the expanded task. Typed input and reading share the compact body and seated
  mascot. The four-mode menu and decorative stacked-paper layers are removed.
- Tap recalls current work; hold reveals the same composer. Mascot recall prefers
  the current task; pending status/menu opens a separately labelled preview.
  Translation of pending text remains a second explicit action. New copy only
  changes pending, including during reading/busy. Preview is available while busy;
  its Translate action is disabled until execution finishes.
- Clipboard listening starts off and has independent on/paused/off controls in
  the menu/tray. Recall, expansion and composition do not enable it. Listening
  still suspends during clarification and region capture. Stop clears pending
  without dismissing the current task. Clipboard is not sent on background copy.
- Compact retains dimensions when the composer closes for submission and through
  processing/completion, resetting sizing on a fresh hidden invocation. Width
  tiers, height budget, baseline and seated/error scale reuse .23. Working has
  an explicit Stop action; clarification exposes the composer.
- Expand/collapse keeps task identity and draft. Source comparison is side by
  side when wide, stacked in the scrollable body when narrow. OCR/image views and
  existing artifact-pinned Apply/Undo remain. Expanded placement starts from the
  companion's remembered home; collapse preserves its compact anchor. No hop
  animation runs during these transitions.
- Reader memory includes per-extent scroll, task selection, and an exact-text
  UTF-16 character anchor with pixel offset. Compact and expanded translation
  readers exchange that anchor. Different text projections (such as partial
  prefixes or Agent summaries) fall back to their own scroll; this does not claim
  exact cross-view anchoring for every projection. Finder selection remains in
  the existing task-owned QML state and is reset only for a new task.
- Clarification and requests with a pinned source no longer begin a new UI task
  merely because they use `submit_goal`. Actual execution state remains in the
  session/worker; extent changes never dispatch a tool. Hidden completion has no
  new show/activate path.

## Evidence and limits

Only source/diff review was performed. QML accessory reparenting, restored text
anchors, native focus, hotkey tap/hold, outside clicks, menu masks, tight screens,
and actual visual continuity need user acceptance on the intended future build.
Existing tests were not run or treated as validation of this revision; tests
asserting the old mode/default presentation may need updating in a separately
authorized verification pass. No generated/canned conversation was used.

Shared reasoning service, routing, dispatcher, tool contracts, artifacts and
verifiers are reused. No business executor was added in QML. This is UI/state
integration, not new evidence of a live Agent/model loop. Default LLM is opt-in;
main UI integration, recipient M3 and Stage 0 remain separately gated.

User authorized small local commits and normal pushes for RAT Lite, recorded in
README and AGENTS. The first push was rejected by automatic approval review
because main also contained two previous commits and the destination was not
confirmed. User subsequently explicitly approved the entire current main,
including those two commits, to the configured structured-multi-step-reasoning
GitHub remote. Publication status must be taken from the actual push result.
Unrelated edits to the .23 audit README were left outside this work's commits.
