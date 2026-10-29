# RAT Lite .26 — continuous panel and Quick Look reliability handoff

User acceptance update after opening: **.26 is rejected as unusable**. User
reports all three groups: input/click/dismissal problems, layout/clipping or
placement problems, and no usable shortcut/result. Do not call .26 stable or
infer acceptance from its startup record. Read-only inspection found app63687
and helper63717 alive with only starting/started/ready metadata; no key-received
or capture event was recorded at that read. A one-second process sample showed
the main thread waiting in the native event loop, not proof of interactive health.
Direct UI observation failed: app-name/exact-path reads timed out; bundle lookup
was ambiguous among retained builds; observation of the Codex host was denied
by the computer-use tool. No input, selection or translation was injected.
No additional source fix is claimed from this diagnosis. A short user-provided
recording of the failing transition is needed to resolve the current visual/input
ambiguity before another speculative layout rewrite.

Latest delivery: user requested a real preview. .26 app+ZIP built successfully
at `dist/rat-lite-20261029-continuous-panel/` and the exact app opened, PID63687.
Helper63717 was observed alive with parent63687 and registered .26 metadata.
See [package/open record](../audit/rat_lite_continuous_panel_20261029/README.md).
Earlier unbuilt statements below describe the source implementation turn.
Physical keypress, actual selection/translation and visual acceptance remain
unverified; no automated UI flow or screenshots were run for this delivery.

2026-10-29. User approved the next-update plan, then explicitly expanded this
turn to a large implementation batch while away. Source .26 was never packaged,
so the same unbuilt version identifies this completed source revision. .25 is
the last app launched in this chat. No tests, smoke, build, launch, screenshots,
UI tours, actual selection captures or model runs were performed in this turn.

## What changed relative to the approved-plan baseline

Review baseline: 633b5edf. Earlier .25 screenshot repair is already in that
baseline; current work completes the deeper continuity and diagnostic changes.

| Concern | Source implementation |
| --- | --- |
| Split compact/expanded UI | One mounted task panel, one reader tree, one editor, one small mascot. MiniDesk no longer instantiates a separate LookSurface or reparents its editor. |
| Composer disappears after Send | Typed submissions keep the same composer below result/progress. Draft edits stay independent; Send remains Send and is disabled while busy. Stop is a distinct task control. |
| Resize changes the character/window behavior | Same64×64 head host and44px optical target across extents and auxiliary views. One speech placement policy and one initial window-level policy replace geometry/flag switching. |
| Empty input is a large blank paper | Result body exists only for a task/notice/preview; no reader space is reserved at empty entry. One Close lives in composer or header, according to state. |
| Long result/read position | One scrollable reader, visible overflow bar, task/extent scroll and UTF-16 reading anchor/selection restoration after width changes. Text and footer have bounded space. |
| Source/OCR/image | Existing task views stay within the same panel. Source can be beside result when wide or stacked when narrow. Back retains the task and draft. |
| Preview interrupted by new Clipboard | Preview pins the exact input object being displayed. Translate consumes that input; a newer pending snapshot stays queued. Preview selection-copy suppresses the app's own Clipboard observation. |
| Preview/error loses original view | Return tokens pin task identity plus extent/view/composer/source state. Stale tokens cannot restore an older task. Pending preview and selection failure have explicit return paths. |
| Shortcut silently ignored while busy | Existing task is retained, no queue/cancel is created; acknowledgement uses a short-lived tray/compact cue and a rate-limited native notification with tooltip fallback. |
| Unknown point of failure | One invocation ID follows helper receipt, controller acceptance, worker capture, artifact, existing execution ID and programmatic presentation. Callback/no-response errors get visible recovery codes. |
| Stale ready metadata | Bounded32-event journal retains lifecycle, helper PID, stop/close reasons, native OSStatus where available, intentional shutdown/reconnect and current helper registration state. |
| Competing reconnects/helpers | Explicit starting guard; close all owned registrations before one replacement. Failed startup ownership is retained for cleanup. If closure fails, no replacement is created. |
| Folder approval in a tiny surface | Compact shows actual existing group/result data and opens full plan/receipt review. Apply/Undo controls remain explicit and artifact-pinned in expanded presentation. |

The shared SpeechSurface, existing tool-result views, controller/session and native
adapters are reused. Standalone LookSurface/SpeechBubble sources remain available
as shared/recovery components; they are not a second active Lite business path.
Build packaging still includes existing resources; this turn did not optimize
bundle size or rename distribution identifiers.

## Diagnostic and privacy contract

`rat/ui/quick_look_journal.py` writes the app's existing last-hotkey.json location.
The history is bounded within an app process and survives reconnect in that
process; this is not a durable cross-launch audit archive. It uses serialized
atomic replacement, whitelist metadata and best-effort recording. Metadata-write
failure cannot replace a valid tool result or break the shortcut.

Default fields are build/app PID, helper PID, monotonic order/time, stage, reason,
exit code/status, invocation ID and generated artifact/execution IDs. No selected
text, Clipboard contents, images, document paths, pointer position or raw/private
model reasoning are added. Existing explicitly opt-in acceptance receipts retain
their prior separate behavior. Registration metadata does not prove a physical
keypress or helper liveness indefinitely; programmatic `presented` records mean
the window reports visible, not that a human accepted its rendered content.

## Evidence boundary and outstanding risks

This implementation was reviewed as source/diff only. No old test result is
claimed as validation. Physical Carbon event delivery, helper survival/cleanup,
actual Accessibility permission for the app identity, source-app coverage,
single-panel QML loading, text-wrap/layout, menu masks, very small screens,
native focus and visual continuity all remain unverified.

The observed .25 helper disappearance remains a real failure with an unknown
original exit cause. Parent-PID monitoring removes the former stdin-EOF exit
path, and this turn adds the records needed to distinguish future causes. It
does not establish that the original report is solved. A physically undelivered
hotkey cannot be acknowledged by a callback that never ran; the next requested
manual check must establish that boundary first.

All domain operations still use the shared router/session/service/dispatcher,
artifact source references and verifiers. No new provider, model behavior or
live Agent-loop evidence was introduced. Main integration, recipient M3 and
research Stage0 remain gated. Clipboard listening remains explicit and starts
off; selection capture does not simulate Copy or fall back to stale Clipboard.

## Next requested delivery

Show the user the diff against633b5edf (or .25 delivery8da75c8a for the full repair).
Only when requested: package one versioned app+ZIP, close the old app gracefully,
open the exact candidate, and let the user operate it. Suggested first check is
empty entry, followed by one real highlight/shortcut and its actual outcome.
Stop on a blocker and preserve its stage trace. Do not infer automatic test or
UI-tour authorization from the large source implementation request.

Unrelated .23 audit README edits, the old QA lock removal and Gemini prompt edits
seen in the working tree were left outside this work's commits.
