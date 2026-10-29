# RAT Mini / future RAT Lite — .19 ten-point UX iteration

Handoff updated 2026-10-29, Asia/Saigon. User explicitly approved all ten items
of docs/rat_mini_ux_plan_20261028_shared_large.md. Source implementation and
software checks completed. Native acceptance remains incomplete; see below.
The later Lite naming decision does not rename identifiers or bundles here.

## Implementation versus evidence

| Item | Implementation | Evidence / remaining acceptance |
| --- | --- | --- |
| 1 Shared surface | SpeechSurface owns body/border/radius/tail/occupied bounds; SpeechBubble and existing composer both consume it. | QML software fixture passes; no new .19 native screenshot. |
| 2 LARGE profile | Body optical target134, text16, width580 retained. Host176×176 reserves status space; bottomPadding30 keeps the body itself the same size. | Geometry/profile + layout checks. |
| 3 Optical connection | Shared placement receives actual ink rectangle and mouth point, gap8, remembered corner for Minimal/Look. | New optical-anchor regression passed; multi-display native not accepted. |
| 4 Continuity | Pending input cannot add a reading footer; source/task remains stable. Reader restores selection/scroll before revealing text. | Fixture proves no pending-induced resizing and close/recall restoration. No fabricated native result. |
| 5 Chrome | Developer footer and permanent mode button removed; display choice in secondary menu; composer reuses bubble surface. | QML layout/import tests; native visual acceptance pending. |
| 6 Quiet Clipboard | Attached text+symbol status and fixed-size pending cue; tray count1 with no snippet text. Copy queues only, no business call/show/cancel. Display change retains pending; explicit Stop clears it. | Actual controller offline-flow contracts + interaction tests. Tray/native badge visual not accepted. |
| 7 Long reading | Persistent overflow thumb, lower continuation fade, task-scoped scroll/selection. Selection Copy ignores own write and keeps reader; existing workbench accessible for longer content. | Scroll/selection fixture passed. Native scroll/keyboard selection not accepted for .19. |
| 8 Recovery | Disabled MyMemory explains cause and opens Settings. Settings preserve store/source; translation-only configuration allows empty file roots. After saving, Retry reuses source through shared workflow. | Actual offline error→save→retry test passed with identical source_ref and 0LLM calls. Native continuous recovery not accepted. |
| 9 Focus/keyboard | Passive Look does not claim keyboard focus; external dismissal requires engagement. Menus own focus temporarily. --look/--minimal and activation bridge route only presentation. Hotkey diagnostics record build/PID, failures point to tray. | UI-only IPC routing passed; physical tap/hold and native right-click/paste remain pending. |
| 10 Verification | One source-complete build, bounded software batch, targeted failed/changed retries, isolated native QA attempts. | Build passed; native control block prevented continuous flow. Do not mark all ten accepted. |

## Software checks

- tests.log: 55passed, 1failed. Failure was a real QML binding loop from the
  long-reader utility action depending on overflowing while utility count fed
  sizing. Removed that cycle by basing the affordance on stable task/text data.
- ui-final.log: 16passed for affected UI/flow checks and the new optical anchor
  case. Includes real local translation error recovery and presentation fixtures.
- bridge-final.log: 1passed for explicit look/minimal/show routing, rejecting
  business operation names.
- All 58 distinct selected checks have passed across the bounded initial batch
  and targeted checks. This is not a single 58-test command and not native/model
  acceptance. Older .16/.17/.18 observations do not establish .19 correctness.
- Existing synthetic layout fixtures remain labeled. Real offline translation
  test uses public Hello world. and actual provider execution; no canned assistant
  response was substituted for a native conversation.

## Build and native attempts

Built .19 at dist/mini-ux-20261028-unified/RAT Mini.app and RAT Mini.zip. Build.log
records packaging. Signature verification and ZIP hash are separate files. The
bundle is ad-hoc signed, not notarized. No research/model inference claim.

QA19 uses the same compiled code and separate state/receipt directories. Bundle
name/id/signature differ for isolation. Process was first PID43452, launched
2026-10-28; user confirmed seeing QA19 despite repeated CUA timeouts. Stack sample
shows the main thread waiting in the normal Cocoa event loop; a 0%CPU observation
is only an instantaneous sample, not an energy/memory benchmark or proof against
all UI defects. The old user .16 PID6897 was preserved.

On 2026-10-29, explicit go on resumed only the pending bounded native flow. QA19
had exited, so it was relaunched with the same isolated profile. Recall IPC
returned true. CUA getApp by id, name and exact path still timed out, including
a fresh CUA session. CUA could read TextEdit immediately. This narrows the block
to observing/controlling this RAT window; it does not establish its root cause.

A QA-only fallback renamed the executable to RAT Mini QA19 and updated its
CFBundleExecutable to avoid multiple processes named RAT Mini. Executable bytes
were identical immediately before re-signing; see qa-executable-identity.json.
After re-signing/registration and restart, CUA still timed out. Product source,
production identity and .19 distributable were not altered for this fallback.

No new .19 native screenshot, clipboard translation, error/recovery receipt or
physical shortcut success was obtained. native-receipts contains launch metadata
only. Do not convert launch, user visibility or IPC delivery into native flow
acceptance. No screenshot substitute, injected model output or alternate native
automation was used to disguise the limitation. No more repetitive UI retries
are authorized automatically by this handoff.

## Boundaries

UI actions continue through existing MiniSession/service/dispatcher/contracts
and artifact store. No new business-only UI execution path. LLM default remains
off; this is reusable Mini/Lite presentation, not main UI integration or proof
of a running Agent model planner. Recipient M3, research Stage0 and study claims
are unchanged. No git push/pull/reset/force or branch creation performed. Preserve
unrelated research edits and existing recovery material.


## 2026-10-29 explicit acceptance resumption

User asked do it then for the pending ten-point native run. No new capability,
software test batch, smoke or source edit was performed. QA19 remained isolated;
production .16 was preserved.

QA launch was corrected to include RAT_MINI_STATE_DIR/RAT_MINI_ACCEPTANCE_DIR
in QA's LSEnvironment, then started through Launch Services. Previous direct
binary launches and tool reopens could target different state; this was a setup
hypothesis, not a demonstrated product defect. The corrected instance PID72974
could be bound immediately through CUA. This changes QA metadata/signature only.
The .19 production artifact and compiled source were not changed.

01-minimal.png is an actual .19 native screenshot: shared speech tail, large
standing character, input/send, three ancillary icons, Sẵn sàng status; no
technical footer. AX data was available. An AX click on Thao tác khác showed no
menu in the returned tree/screenshot, so context menu activation is not accepted
on that observation. Escape subsequently hid the window.

Look was invoked through the UI-only look presentation bridge. Real TextEdit
copy of public Hello world. created no translation receipt before explicit open
(only launch.json). Attempts to bind/read/capture passive Look repeatedly timed
out, including screenshot-only and a rebind after mode change. Do not interpret
these timeouts as proof that the application disappeared or froze.

A single manual opening was requested: use RAT's pending-count menu-bar item,
confirm Hello world., click Mở đoạn này. Further native reading/recovery checks
remain pending that step. No assistant answer, UI result or screenshot fixture
was injected. Historical .16/.17/.18 images remain separate evidence.


### Single-instance correction and lock interruption

User reported a translation appeared after manual opening, but QA19's receipt
folder still contained launch metadata only. Two Mini processes were present;
therefore that result is NOT attributed to .19. User explicitly confirmed work
was done/saved and authorized closing .16. Exact PID6897/path was verified and
SIGTERM sent; no files or recovery material were removed.

With only QA19 retained, CUA read the Minimal window and pending badge (1 đoạn
mới). A known-source refresh was planned before clicking that badge to avoid
submitting an uncontrolled clipboard snapshot. The next TextEdit interaction
was rejected because the Mac was locked. Unlock was requested once. No OS lock
or security setting was changed. Remaining native cases are pending, not passed.


### Public-source refresh and supplied screenshot

After unlock, actual TextEdit still held Hello world. Look was enabled and that
source copied again. Minimal recall succeeded, but the next native action was
blocked by another OS lock. User manually reported translation visible and then
provided screenshot user-20261029-114724-pending.png. The image actually shows
Đoạn mới: Hello world and Mở đoạn này: this is pending-source preview, not a
translation result. The distinction was explained, and a precise click on the
in-bubble Mở đoạn này action was requested. This is evidence of a discoverability
problem; it is not sufficient evidence that dispatch or translation failed.
Cua subsequently timed out and once reset its kernel during a badge action.
No new passing native result or receipt is claimed at this point.
