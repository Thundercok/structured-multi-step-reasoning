# Mini shared speech — handoff 2026-10-28

Latest continuation: [larger-corner report](../audit/rat_mini_speech_20261028/large-corner/README.md).
User requested a slightly larger seated rat and continuation of the acceptance
plan. Host 96×100, seated optical target 86; head stays 36. .13 native idle and
real Clipboard receipts obtained; .14 queue scenario not accepted. Explicit
recall reading intent now includes busy work in final .15. Relevant tests passed;
native .15 queue/long-reading acceptance still pending. Original .8 preserved.

Latest continuation after user-authorized autonomous tests: see
[native report](../audit/rat_mini_speech_20261028/live/README.md). Real .10 QA UI
translated Hello world to Xin chào thế giới with zero LLM calls and screenshot;
.11 QA showed seated Look with a speech tail. Fixed same-app bundle aliasing and
short-text measurement; 20 related and then 6 changed-area checks passed. Planned
latest build is .12 under `dist/mini-speech-20261028-fix2/`. Mac relocked during
the real Clipboard attempt; .12 native acceptance and other flows remain open.

Later user-requested verification/build: 55 software checks passed, 1 semantic
check deselected. .10 app/ZIP built with valid ad-hoc signature; shared QML files
found in the bundle. Native observation remained blocked by locked Mac and then
CUA timeout after “go on”; no screenshot or .10 native acceptance obtained. Old
.8 process preserved. Full evidence and ten-point next plan:
[bounded report](../audit/rat_mini_speech_20261028/README.md). Earlier unbuilt and
no-test statements below describe the implementation stage.

Latest source: 0.5.17 / planned build 20261028.10, visible identifier
`RAT Mini · Speech source`. No .9/.10 app or ZIP built; the .8 clipboard bundle
remains the last build/open from this chat. No tests, smoke, runtime inspection,
UI acceptance, screenshots or model requests in this implementation turn.

User authorized the ten-point shared speech plan with “go”. Work is Mini as a
proof of concept for main RAT, with maximum reuse. No default LLM dependency.

| Plan | Source result |
| --- | --- |
| 1. Reuse inventory | Extracted Look text/scroll/actions; reused DeskIcon, palette and Rect; no existing general speech component found in inspected UI. |
| 2. Shared contract | SpeechBubble has plain text, state label, actions, geometry/theme/scroll inputs and public interaction signals; no Mini dependency. |
| 3. Speech shape | Rounded body with tail pointing to per-sprite speech anchor; occupied bounds include tail for native masks. |
| 4. Content sizing | Natural text width, bounded wrapping/scroll, utility rail and optional primary footer; preferred and placed sizes separated. |
| 5. Placement | Pure shared place_speech tries four sides, retains a fitting side and constrains geometry to available bounds. |
| 6. Window versus bubble | Look owns remembered corner home; body placement reuses shared policy. Copy selects the display, not a location under the copied text. |
| 7. Sprite sizing | Shared MascotPose maps normalized ink/mouth metadata to optical sizing/anchor; metadata still needs native visual review. |
| 8. States/actions | Look maps standby/work/results/questions/errors and existing copy/retry/reply to the same component. |
| 9. Lifetime/reading | Shell owns auto-hide. Explicit reading stays open; latest copy queues with Mở đoạn mới; speech scroll retained separately. |
| 10. Mini handoff | Build script includes shared QML. Main can consume the contract but is not integrated; no runtime or model-quality acceptance claimed. |

Contract and file boundaries: [Shared speech](contracts/speech_bubble.md).
Earlier clipboard/compact behavior history: [Look flow](rat_mini_look_clipboard_20261028.md).
User-operated native review remains necessary after an explicitly requested
build/open. Do not run tests or acceptance automatically in a later continuation.
Research scope, recipient M3, main UI integration and Stage 0 remain unchanged.

## 20261028.16 — quiet clipboard iteration

User approved source implementation and bounded final verification. Clipboard
now only queues the latest source; explicit opening runs the same capture and
translation contracts. Added pure LookInteraction; shell lifetime and QML
speech actions project it. Hidden/peek/reading are separate from busy and
monitoring. No popup on copy, no cancellation, no automatic dispatch after a
previous job completes. Single click opens pending or recalls result; dragging
only moves. Double-click navigation removed. Corner and task pose retained.
Seated optical size remains 86. Peek hides after 5 seconds; explicit reading
retains task and pending across close/Esc/Copy/outside. Tray has pending recall.

Default LLM remains disabled. This is Mini's reusable presentation/interaction
slice, not main UI integration or proof of a running Agent model loop. Stage 0
and recipient M3 remain unchanged. Native .13/.14 screenshots do not validate
.16. Validation pending at source completion; see subsequent audit record.

.16 outcome: 41 selected software checks passed across the final batch and
targeted retries; real offline translation included. Packaging and strict/deep
ad-hoc signing passed. .16 launched (PID 6897). Native UI remains unverified
because CUA reports Mac locked. Evidence: `audit/rat_mini_speech_20261028/quiet-clipboard/`.

Native follow-up: Mac unlocked; isolated QA16 with identical .16 code ran two
real clipboard translations. Short Copy/recall, retained A while B queued,
explicit long next and Esc/recall observed; screenshots/receipts under the
quiet-clipboard audit. QA stopped, production .16 preserved. Error, multi-display
and extended scrolling remain unverified. See audit README for limits.


## .17 — user screenshot overflow repair

22:44 screenshot preserved in quiet-clipboard audit. Shared SpeechBubble now
shows a persistent overflow thumb, gutter and bottom fade only while more text
remains. Source-only focused component check passed; .17 built and deep/strict
ad-hoc signing verified. Real native long text on QA17 showed top/bottom and
fade disappearing at end. A genuine MyMemory-not-enabled error produced the
seated error sprite and Retry; both attempts used the identical source_ref and
0 LLM calls. Retry remained an error with unchanged settings, not a successful
recovery. Error copy is too generic and should point to the disabled setting.

Synthetic hotkey only left helper at ready; no physical hotkey acceptance.
Recall AX timeouts do not prove a hidden-window bug: the user's image showed
Look visible. Scroll retention, physical shortcut, right-click/paste native
behavior and multi-display need separate confirmation. QA17 cleaned up; user's
.16 session retained. .17 distributable at dist/mini-speech-20261028-overflow/.
Do not use .16's 41-check batch as a fresh full .17 test claim. Evidence and
limits: audit/rat_mini_speech_20261028/quiet-clipboard/README.md.

## .18 — shared LARGE scale, explicit correction from user

User corrected the direction after two screenshots: BOTH should be large and
use the same size as a stylistic choice. Do not shrink Minimal in follow-ups.
Mini profile now supplies common 176×152 host, 134px visible body-height target,
16px base text and 580px panel/speech maximum width. Short speech still hugs
content. The wide seated error pose had been width-clamped; it now reaches the
same 134px metadata height as standing and idle seated. Pixel-perfect subjective
ink alignment remains a visual choice, distinct from equal canvas size.

MiniDesk's standing sprite now reuses MascotPose and alpha bounds from the
original asset. Look head scales proportionally (42% of body height). Look and
Minimal share the same remembered corner via place_look/place_speech; Single and
Full retain workbench placement. Main UI is not integrated by this change.

49 relevant Look/Quick/speech tests passed after source completion. Additional
actual QML pose measurements: standing 134×126.7, idle seated 134×133.2, error
seated 134×166.6 (height×width). See size18-tests.log, check_pose_scale18.py and
pose-scale18.log in quiet-clipboard audit. Build/native outcomes recorded there.

.18 packaging completed. Native Minimal and Look idle captured at the shared
large size; error capture timed out, so only component size verification applies
to .18 error pose. QA18 stopped, production .16 preserved. .18 app/ZIP:
`dist/mini-speech-20261028-shared-large/`. All details in quiet-clipboard audit.

## .19 — ten-point implementation, native acceptance incomplete

Handoff 2026-10-29. User approved all ten UX items. Shared SpeechSurface now
serves both SpeechBubble and existing composer; optical placement uses real
ink/mouth. Common large scale retained (134px body,16px text,580px width);
176px-tall host reserves status below the feet. Attached text/symbol status and
pending cue, tray count, quieter footer/menu, pending preservation, source-stable
settings recovery, task scroll/selection restore and explicit keyboard ownership
implemented. --look/--minimal route presentation through the same instance.

58 selected software checks passed across initial batch + targeted failed/
changed retries; not a single 58-test run. Real offline MyMemory-disabled error
→ provider change → retry succeeded on the same source with 0LLM calls in the
software test. Empty roots no longer block translation-only settings; file
scope remains validated by find_files. Build .19 completed at
`dist/mini-ux-20261028-unified/`.

Native QA19 repeatedly timed out in CUA despite true recall IPC and user
confirmation of visibility. TextEdit remained readable. QA executable identity
fallback did not resolve binding. Native receipts contain launch metadata only;
no .19 continuous UI conversation or screenshot acceptance is established.
Physical hotkey, native selection/scroll recall and multi-display remain open.
Do not claim all ten accepted or substitute software/layout fixtures for live UI.
Audit and per-item matrix: `audit/rat_mini_ux_20261028_complete/README.md`.

The new name RAT Lite applies to future development, with identifiers unchanged.
Mini/Lite work is paused per updated AGENTS except an explicit user resumption;
no automatic future testing or screenshot loop is authorized by this handoff.
Main UI integration, recipient M3 and Stage0 remain gated.

## 2026-10-29 .20 — follow-up after incomplete native acceptance

User reported a translated greeting after manual opening; QA19 did not record a
corresponding execution. Earlier supplied image showed pending preview, not a
result. Do not treat either observation as an automated successful .19 run.

.20 clarifies pending copy (Chờ dịch / Dịch đoạn này / đoạn chờ) and adds opt-in
metadata-only QA diagnostics. Receipt persistence failure no longer overwrites
a valid tool response; its failure is separately reported. This robustness
change does not establish why .19 had no receipt. Seven targeted software checks
passed, including real offline success with healthy/invalid recording targets
and metadata privacy. Build and artifact paths:
`dist/rat-lite-20261029-observable/`; audit:
`audit/rat_lite_ux_20261029_followup/`.

Native QA20 launched with unique identity and LSEnvironment paths. CUA timed out
before input submission. Metadata showed idle, generation0, no action/operation:
no .20 native business result is claimed. Full ten-point native acceptance remains
incomplete. .16 was closed with explicit user permission after saved/done
confirmation; QA19 was replaced by QA20. Preserve unrelated work and older raw
evidence. No blanket future test permission; Lite remains on hold except explicit
user resumption. Main integration, M3 and Stage0 remain gated.

## 2026-10-29 .21 — focused dismissal repair

On explicit continuation, repaired macOS dismissal to require an actual outside
mouse click rather than foreign application activation. Uses the existing window
mask/Qt coordinates, respects menus/dialogs, removes the native monitor on quit,
and keeps explicit Close/Esc if monitor installation fails. Shared large sizing,
business execution and five-second Look peek timeout remain unchanged.

No new tests, UI acceptance or screenshot retries were run. Build target:
`dist/rat-lite-20261029-outside-click/`; audit:
`audit/rat_lite_ux_20261029_outside_click/`. The code path was repaired; actual
behavior and its relationship to earlier CUA timeouts are unverified. No running
app was replaced. Full ten-point acceptance, main integration, M3 and Stage0
remain incomplete/gated.

## 2026-10-29 .22 — renewed jarring-feedback

Source review found Look still switching to a floating head at 42% optical
height on short replies and side bubbles recentering as their height changed.
Look now stays seated at shared large scale; both corner surfaces opt into
shared bottom-aligned speech placement. Head assets remain available. .21's
outside-click repair is included. Package target is
`dist/rat-lite-20261029-continuity/`; details in
`audit/rat_lite_ux_20261029_visual_continuity/`. No new test/UI capture/acceptance
was run and no running app replaced. Do not claim the jarring experience fixed
from source or packaging alone. Other resizing/transition issues remain open.

## 2026-10-29 .23 — approved stable-layout iteration

User deferred four-mode unification to backlog and authorized the ten-item
stable-layout plan. Source now holds busy dimensions, shares width tiers,
premeasures reading height, limits corner viewport, keeps a stable pose envelope
and side, attaches quiet status at a fixed position and includes selection/focus/
menu in peek engagement. Runtime menu and bundle plist share BUILD identity.
See `docs/rat_lite_stable_layout_20261029.md` for all ten items and limits.

Read-only process inventory found QA20 PID7562 still running; it was not closed
or replaced. No test/smoke/native acceptance/screenshots were run. Do not claim
visual smoothness or reuse historical test counts for this revision. Contracts,
dispatcher and default LLM setting remain unchanged; main/M3/Stage0 remain gated.
