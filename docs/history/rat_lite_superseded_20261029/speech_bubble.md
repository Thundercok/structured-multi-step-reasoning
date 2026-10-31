# Shared speech presentation — source contract, 2026-10-28

Mini is the proof of concept/reusable vertical slice of main RAT. This contract
is shared presentation infrastructure, not a new business capability or evidence
of model reasoning. Source revision 20261028.10 is unbuilt and untested.

## Existing pieces reused

Look's plain-text selection, scrolling, copy/dismiss/retry behavior, palette and
DeskIcon symbols were extracted/adapted. No existing general speech-bubble QML
component was found in the inspected RAT UI. QuietButton still takes its theme
from an outer `desk`; the standalone bubble therefore uses Qt ToolButton with
the existing DeskIcon and explicitly supplied colors rather than depending on
Mini's outer object. Shared Rect geometry was moved without changing the main
panel placement algorithm; mini_placement re-exports Rect for existing imports.

## SpeechBubble.qml

| Input | Contract |
| --- | --- |
| text | Plain text, selectable, no HTML interpretation. Copy action emits the rendered string. |
| stateLabel | Optional accessible status prefix. User-facing task state remains the caller's responsibility. |
| actions | Array of `{id, label, icon, role, enabled}`; zero or more utility icon actions and at most one primary text action. IDs are opaque; no tools are invoked by the component. |
| minimumWidth / maximumWidth / maximumHeight | Natural content sizing policy in logical pixels; caller supplies its screen-constrained limits. |
| placedWidth / placedHeight | Final constraints from placement. Requested sizes remain separate so a previously small/clamped body can expand for new content. |
| anchorPoint | Speech target in bubble-local coordinates. Tail chooses the corresponding edge, points toward the target and clamps the base away from rounded corners. |
| taskKey / scrollOffset | Caller-owned context and retained scroll. Changing the key restores that context's offset; text changes alone do not discard reading position. |
| paperColor / edgeColor / inkColor / selectionColor | Explicit theme inputs. No `desk`, Mini controller, provider, filesystem or model dependency. |

Outputs are `preferredWidth`, `preferredHeight`, `occupiedRect` (including tail),
`engaged`, `actionTriggered(id, displayedText)`, `scrollChanged(offset)` and
`readingRequested()`. `implicitWidth/Height` support future layout consumers.
The caller owns timers, visibility, focus, placement, task changes and execution.
Keep the occupied rect in native masks; the body rect alone clips the tail.

## MascotPose.qml

Receives `source`, normalized `inkBounds`, normalized `mouth`, `opticalHeight`
and bottom padding. Fits the visible ink inside its host while preserving aspect
ratio; returns `visualBounds` and `speechAnchor` in local coordinates. Source
metadata is explicit and adjustable; the current Look values are manual initial
estimates, not measured or accepted optical alignment. No image regeneration or
pixel editing was performed in this source revision.

## Shared placement

`place_speech(available, anchor, width, height, preferred_side, gap, margin)` is a
pure geometry function with no Qt or business execution dependency. It keeps a
fitting preferred side, tries left/right/top/bottom, and constrains size to the
available side if no natural-size placement fits. It returns body, combined
bounds and selected side. Its host owns anchor placement and side memory.

Mini's `place_look` is the profile adapter: 96×100 mascot host, remembered screen
position, gap/margin and shared placement. It no longer has separate short/long
positioning algorithms. Native multi-display, tiny-area and mask behavior remain
unverified. Source intent is not a guarantee that every screen configuration fits.

Later user-requested size revision uses a seated optical target of 86 instead
of 70, retaining the floating head target of 36. Python profile constants supply
the initial QML host dimensions and seated target. Native .13 idle evidence and
the later .15 recall repair are documented in
`audit/rat_mini_speech_20261028/large-corner/README.md`.

## Mini projection and main handoff

- Look uses one SpeechBubble for idle, working, short/long output, clarification,
  local notices and errors. The seated character has a speech bubble as requested.
- Selected idle/head/error assets and manual optical metadata remain in Look's
  profile adapter. Fixed screen-edge home and side memory replace cursor-relative
  speech. A new display resets to its lower-right home; dragging adjusts home.
- Unengaged passive output retains the shell's five-second hide policy. Explicit
  text click/selection, mascot click or result recall locks reading until close.
  Timers are absent from the shared component.
- While reading is locked, latest eligible clipboard text queues without changing
  the source/result being read. `Mở đoạn mới` accepts it. Close preserves queued
  text until recall/new choice; leaving Look/pausing drops it. Only one queued
  snapshot is kept. Native clipboard count changes invalidate older queued input.
- Speech scroll uses `{task_id}:speech`, separate from the existing workbench
  scroll. Session, tool contracts, dispatcher, verifiers and retry paths are reused.
- Main can supply another anchor, theme, actions and lifetime using these same
  components. Main's UI/composition has not been switched to them; Mini/native
  acceptance and recipient M3 still gate that integration.

No tests, QML/syntax smoke, launch, screenshots, build or actual model run were
performed for this revision. Current translation quality and Stage 0 are unchanged.

## Revision 20261028.16 — explicit clipboard opening

Supersedes the earlier automatic-output lifetime policy above. `LookInteraction`
is the reusable pure interaction state, separate from execution. Monitoring is
on/paused/off; surface is hidden/peek/reading. Clipboard ingress only replaces
one pending snapshot, regardless of visibility. It never invokes tools, shows a
window, cancels a running job or changes the current result, pose or scroll.
An explicit mascot click or `Mở đoạn này / Mở đoạn mới` accepts pending input via
the existing capture→translate service/dispatcher. Tray exposes pending and result
recall separately. Opening a notice does not submit text. Result recall does not
consume pending input. Pause/leaving Look clears pending; closing preserves it.

A peek hides after five unengaged seconds. Explicit reading remains until close,
Esc, Copy or switching away from the app; these retain the result and monitoring.
Closing does not cancel execution, and completion cannot reopen the window.
Copy does not reset the peek timeout or select another display. The remembered
corner anchor stays fixed. Source length selects head/seated pose once when the
user opens a task; progress/result length does not change it. Errors may use the
seated error pose. Shared bubble sizing, placement and optical sprite metadata
are reused. No model planning or main UI integration is added by this change.
Validation and native acceptance for .16 are recorded separately from .13–.15.

## Revision 20261028.17 — discoverable overflow

The supplied 22:44 screenshot exposed clipped final text without an obvious
scroll affordance. The shared bubble now reserves an 8px text gutter, keeps its
thumb visible whenever content overflows, and fades the lower edge only while
more text remains below. A fully visible short response has neither thumb nor
fade. No execution, input, pose or lifetime contract changes. Native scroll to
the final line was observed on .16; .17 indicator verification is separate.

## Revision 20261028.18 — shared large scale (user stylistic choice)

Supersedes shrinking Minimal: the user explicitly wants BOTH large, using the
same scale. Mini's standing and Look seated/error sprites share a 176×152 host
and 134px visible-height target through MascotPose. The wide error pose can now
reach that height without width clamping. Floating head scales proportionally.
Text uses the same 16px base size; Minimal width and speech maximum width share
580px. Short speech still sizes naturally, rather than padding every answer to
580px. Corners use 18px. Minimal and Look use the same remembered corner and
place_look/shared placement; selecting Minimal no longer moves the composer to
the bottom center. Single/Full retain their existing workbench placement policy.
Only Mini uses this profile; main UI integration is still gated.

## Revision 20261028.19 — shared surface and interaction completion

SpeechSurface owns background/border/radius/tail/occupied mask; SpeechBubble and
Mini's existing composer compose it. CompanionStatus presents text + symbol and
pending cue under the character. Body optical height remains 134, text 16 and
shared width 580. Host height becomes 176 to reserve 24px status space without
covering feet. MascotPose uses bottomPadding 30. Optical ink bounds and mouth
anchor feed the same placement service; the transparent canvas no longer sets
the body gap alone. No new business execution path is introduced.

Reader scroll and selection are kept by task separately from peek/status text.
Closing, peeking or changing display does not overwrite reading position or
pending input. A new copy changes only badge/menu while reading; it cannot grow
the action footer. Selection Copy suppresses RAT's own clipboard write and keeps
the reader open. Full Copy retains existing dismiss-and-recall behavior. Reading
restoration is scheduled before revealing text; no new motion is required.

Look only dismisses on external activation after explicit keyboard engagement;
a passive invocation does not claim focus ownership. Menus exempt transient
focus and use native popup windows. Global shortcut diagnostics identify .19 and
PID but do not prove physical tap/hold acceptance. Tray exposes a pending count
without snippet text and left click recalls Look rather than disabling it.

online_translation_not_enabled now explains MyMemory and suggests Settings;
Look shares the same settings recovery as the workbench. Saving settings clears
that guidance and offers Retry from the retained source. Empty folder scope is
allowed for translation-only settings; find_files still validates its own scope.
The dispatcher and artifact store are reused across provider changes. LLM stays
off by default. Main UI integration, M3 and Stage 0 remain gated.

## 2026-10-29 .20 — pending/result distinction and QA metadata

The user's supplied .19 image showed pending source while the user reported a
translation visible. This establishes ambiguity between preview and result;
it does not alone establish a dispatcher failure. Pending text now says Chờ
dịch and its action says Dịch đoạn này. Status says đoạn chờ and explicitly
announces the translation action. Same contracts/dispatcher and explicit submit.

Opt-in QA diagnostics (RAT_MINI_ACCEPTANCE_DIR only) record build/PID, UI phase,
mode, pending/busy flags, action/operation/generation and execution IDs. They do
not add draft/clipboard/result text to these metadata files. The existing full
receipt remains the explicitly enabled acceptance record. Receipt-write failure
is reported separately and cannot replace a valid tool result with an unrelated
business failure. Software regression covers real offline success with both a
writable receipt folder and a deliberately invalid recording destination.

This follow-up does not establish why the earlier .19 receipt was missing.
Native acceptance and model/research gates remain separate. RAT Lite is the
future product name; existing Mini identifiers/bundle names remain for now.

## 2026-10-29 .21 — macOS outside-click policy

Supersedes .19's external-activation dismissal rule on macOS. App activation
alone no longer dismisses Minimal or Look. An actual mouse-down outside the
existing masked surface dismisses it, except while an owned menu/dialog is open.
Qt global coordinates are used for the hit check. No input text or pointer
positions are persisted. Close/Esc and five-second Look peek expiry remain.
If the native monitor is unavailable, explicit dismissal remains available
without falling back to focus-loss dismissal. Native behavior is unverified
for this source revision; no new acceptance run was authorized by “tiếp tục”.

## 2026-10-29 .22 — consistent Look silhouette and bubble baseline

The user's renewed jarring-feedback supersedes automatic short-reply head
switching: Look now stays seated at the shared 134px optical height, including
short responses; errors use the seated error pose at the same scale. Head assets
are retained. Side bubbles in both corner Minimal and Look bottom-align to the
character's ink baseline and expand upward. The shared placement helper exposes
this as an option; unrelated callers retain their default centering behavior.
Screen clamping and top/bottom fallback still apply. No animations, business
execution or font/large-scale changes. Native visual improvement is unverified.

## 2026-10-29 .23 — stable layout for one interaction

Shared SpeechSurface owns width tiers220/380/580 and optional retained dimensions.
Look captures its visible bubble dimensions before a busy snapshot replaces
text/actions, then releases them on completion. Reader height measures intended
width before native placement. Minimal begins at380 and grows by the same tiers
within an invocation, without shrinking when submission clears its input.

Corner speech uses a constant optical envelope (168×134,feet at hostY146), not
pose-dependent ink bounds; the tail still follows the actual mouth. Prefer the
current side with constrained wrapping before relocating to another side.
Viewport budget is min(300px,38% available height), with screen clamping. Long
content scrolls and retains its existing explicit workbench action. Status is
fixed under the host and quiet at idle. Peek interaction includes selection,
scroll/drag, keyboard focus and context menu; reading never auto-expires.

Runtime BUILD/PID is available in the secondary menu; package plist and runtime
share one BUILD source. Four-mode unification is deferred in backlog. No native
acceptance/test execution is implied by this source update. Full design notes:
`docs/rat_lite_stable_layout_20261029.md`.
