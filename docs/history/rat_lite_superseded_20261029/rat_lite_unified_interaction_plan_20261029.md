# RAT Lite — unified interaction and layout plan

Continuation: user authorized implementation and small commits/pushes. The .24
source changes and remaining acceptance limits are recorded in the
[source handoff](rat_lite_unified_interaction_handoff_20261029.md). The plan below
records intended behavior; it is not evidence of verified native behavior.

2026-10-29. User requested planning continued unified interaction and layout
refinement. This is a proposed implementation plan, not implemented behavior or
native acceptance. It advances the previously deferred proposal to planning.

## Intended experience

One rat, one current task, one draft. The user invokes RAT, types or supplies
context, receives a result, then expands it when needed. Minimal / Look / Single /
Full disappear as user-facing workspace choices. Clipboard listening remains an
explicit, independently controlled setting with visible on/paused/off status.

The existing large scale stays: 134px optical mascot height, 16px body text,
shared paper styling. Proposed visible change for this iteration: the same seated
rat accompanies both typed requests and Clipboard results, and a contextual
`Mở rộng` / `Thu gọn` action replaces the workspace selector. Existing error pose
keeps the same baseline and scale. No animation or new mascot assets are needed.

## Interaction rules to implement

| Action / event | Result |
| --- | --- |
| Tap ⌥⇧Space | Recall current reading/result; if none, show pending preview or a short idle hint. No execution. |
| Hold ⌥⇧Space, then release | Open and focus the single composer; retain current result and draft. |
| Type and Send | Submit through current session/router/service. Show working state in the same surface; preserve a separately editable next draft. |
| Eligible copy while listening | Replace the single pending snapshot and badge only. Do not show, submit, change current result or move the reader. |
| Open pending preview | Show source explicitly labelled `Chờ dịch`; require `Dịch đoạn này` to execute. Preview is distinct from translated output. |
| New pending input while reading/busy | Retain pending badge. Opening the preview preserves current reading; submission stays disabled while busy. No silent cancellation or queue execution. |
| Long result | Keep a scrollable compact reader, with explicit `Mở rộng`. Length alone never relocates or opens a larger window. |
| Expand / collapse | Change presentation extent for the same task/artifacts. Preserve draft, source, selection and reading position. No dispatch. |
| Ask a follow-up | Reveal the same composer below current content. Route through shared session with supported context; do not imply conversational model memory where absent. |
| Needs input | Show the actual clarification and composer; preserve the input request and its pinned source. |
| Edit OCR / inspect image | Open the expanded task's existing source/editor view; Back returns to that task and reading position. Correction/retry uses current tools. |
| Error / partial / cancellation | Keep source and recovery actions with the actual status. Retry is explicit. Dismissal is distinct from cancellation. |
| Close / Esc / outside click | Hide and retain task, draft, pending and reader context. Owned menus/dialogs exempt outside dismissal. Completion while hidden cannot reopen RAT. |
| Peek timeout | Five unengaged seconds applies only to idle/pending preview. Composing, working and explicit reading never time out. |

Mascot click recalls the current task first. With no current task it opens pending
preview, otherwise the composer. A pending badge/action opens preview explicitly,
so a new copy cannot hijack the mascot's result-recall behavior. Tray exposes
`Viết yêu cầu`, `Xem lại kết quả`, `Xem đoạn chờ` and Clipboard controls.
These precedence rules are proposals replacing mode-dependent behavior.

## Layout refinement

Compact is one paper body attached to the remembered corner anchor. The body has
an optional short task/status line, selectable result or pending preview, optional
composer, and contextual actions. Only one primary action appears at a time:
Send, Translate pending, answer clarification, Retry, or the operation's approval.
Copy and Expand remain secondary. Pending and current result are never labelled
as the same content. Folder Apply/Undo keep their existing explicit approvals.

Reuse .23 width tiers 220/380/580 logical px; composer starts at 380. Width may
grow within an invocation and resets its sizing choice only on a new invocation.
Retain the body dimensions across processing and completion; a result that needs
more space scrolls or offers expansion. Avoid a completion-time shrink. Retain
the selected side and grow upward from the fixed foot baseline; clamp to screen.
Compact height stays capped at min(300px, 38% of available work area). When space
is tight, shrink the content viewport before hiding primary controls.

Expanded presents the same task at a larger readable size. Result is the default;
`Nguồn` reveals source alongside it when width permits (existing 700px threshold
is the starting policy), or as a reversible view on narrow screens. OCR edits
and image inspection use existing views. Collapse restores the exact compact
geometry and reading context. Keep the same mascot size and identity; only one
mascot is visible. Expanded placement prefers the same screen and edge, clamping
to available space. If relocation is necessary, remember the compact anchor for
collapse rather than overwriting it.

Scroll offsets from differently wrapped widths cannot simply be copied. Retain
selection by text offsets and reading position by a visible text/block anchor
plus viewport offset. Also preserve per-extent scroll for exact round trips.
Restoration occurs after layout and before reveal where supported. If Qt text
layout cannot restore an anchor precisely, document the fallback rather than
claiming exact continuity. Finder keeps selected hit and keyboard focus separately.

## State and code changes

Current source has `MiniPresentation.workspace_mode`, independent
`LookInteraction.surface`, QML mode branches, and shell placement selected by
mode. `setWorkspaceMode()` can enable listening; recall and tray also branch on
mode. Merely renaming menu labels would retain these conflicting lifecycles.

Introduce one Qt-free interaction owner (extend `MiniPresentation` or a small
adjacent class) with independent fields:

- visibility: hidden / peek / engaged;
- extent: compact / expanded;
- content: task / pending preview / auxiliary view;
- composer visibility and explicit keyboard-focus intent;
- current task identity, draft and retained reader/finder context;
- independent Clipboard listening state and one pending snapshot.

Execution phase remains owned by the session/worker, not copied into a second
UI state machine. Existing source/result/artifact references remain authoritative.
Geometry and view changes cannot call tools, begin a task, clear a pending source
or change listening. Hidden completion updates data only. Accepting new input
uses existing generation guards, cancellation and capture preservation behavior.

| Files | Planned responsibility |
| --- | --- |
| `rat/ui/mini_presentation.py`, `look_interaction.py` | Single interaction transition owner; independent pending/listening; stable task and view memory. Adapt existing structures rather than adding competing state. |
| `rat/ui/mini_quick_controller.py` | Explicit recall/compose/preview/submit/expand/collapse events; snapshot projection; existing tool dispatch and approvals. Audit every `begin_task()` call. |
| `rat/ui/quick/MiniDesk.qml`, `LookSurface.qml` | One compact presentation with optional composer; expanded task projection; remove workspace selection and duplicate mascot ownership. |
| `SpeechSurface.qml`, `SpeechBubble.qml`, `CompanionStatus.qml`, `MascotPose.qml` | Reuse paper, reader, anchor and status components. Extend presentation contracts only as needed. |
| `rat/ui/mini_shell.py`, `mini_placement.py`, `speech_placement.py` | Extent-based fitting, remembered compact geometry, focus and native dismissal; no execution. |
| `rat/ui/mini_quick.py`, `mini_instance.py`, `rat/os/native_menu.py` | Route shortcut/tray/instance intents to unified events. Preserve old launch flags as boundary aliases. |

Old `--look`, `--minimal` and stored workspace values map to recall/compose and
compact/expanded at the boundary. Inspect actual persisted settings before
choosing migration; presentation migration must not silently enable Clipboard.
Remove old mode branches only after all QML, shell, tray, diagnostics and instance
callers use the new snapshot. Keep build/PID diagnostics and recovery material.

## Delivery order

1. Specify the transition table and snapshot fields, including busy, hidden,
   pending preview, clarification and auxiliary-view returns. Inventory current
   ownership and compatibility callers.
2. Consolidate pure interaction state and controller events. Preserve existing
   session dispatch, source references, execution guards and explicit approvals.
3. Compose the unified compact surface and the one seated mascot. Wire optional
   composer, distinct pending preview, reading and recovery actions.
4. Wire expanded reading/source/editor views and round-trip reader memory; then
   align placement, masks, shortcut focus, tray and outside-click behavior.
5. Remove obsolete mode UI/branches and update contracts/handoffs. Finish all
   source work before any separately authorized verification.

Each step should leave a reviewable source diff. Preserve unrelated working-tree
changes. No branch creation, Git publication or main-app integration is part of
this plan. Implementation size spans state, controller, QML and native shell;
avoid treating it as a small visual-only patch.

## Acceptance checklist for a later explicitly requested check

The user operates the intended build. Candidate checks: typed request → result →
expand/collapse; Clipboard pending during reading; pending during busy; OCR edit
and retry; Finder keyboard selection/open; clarification; error recovery; hide and
recall with draft/selection preserved; hidden completion; owned menus; screen-edge
clamping. Verify one mascot, stable baseline/body, full last-line access and exact
build/PID. Native tap/hold, outside-click and multi-display behavior require real
observations. Capture evidence only when requested; no canned model responses.

No tests, smoke, build, launch, screenshots or acceptance run are authorized by
this planning request. Proposed implementation and behavior remain unverified.
Shared reasoning-tool contracts, dispatcher and verifiers are reused; this plan
adds no Agent/model execution evidence. Main UI integration, recipient M3 and
research Stage 0 remain separate gates. Default LLM stays opt-in.
