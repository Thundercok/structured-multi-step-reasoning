# Look / Minimal / Single / Full — Mini source, 2026-10-27

The user approved these four names and implementation, requested minimal weight,
and rejected Option-Shift-L as unergonomic. Preserve Option-Shift-Space for
Minimal. The source default pair is now Option-Space for Look and
Option-Shift-Space for Minimal: the same base chord, without a far letter key.
This is not a measured ergonomics claim or verified shortcut acceptance.

## One session, four projections

- Look: summon a surface to supply an image/region via explicit screenshot/drop/
  paste. OCR creates a captured_text artifact. With no instruction, retain/show
  that observation and wait; an explicit instruction goes through MiniSession.
- Minimal: hide the paper and show one compact result/status line by the composer.
- Single: the restored production-style composer and one result paper.
- Full: wider workbench with source beside the result when screen width permits;
  narrow screens keep the existing source/image/Back controls.

Mode selection only changes presentation. It does not cancel work, clear draft,
corrected OCR, source or result, or make a tool call. Full accepts legacy `multi`
as an input alias. MiniPresentation owns the canonical mode value and projects
workspaceMode; UI has one composer and one submit path, no find/translate mode
selector. The full Mini layout is a source/result comparison surface, not a
claim that all main RAT capabilities have been integrated into Mini.

Look image ingress reuses run_capture_translation in observation-only mode.
A subsequent explicit translation of the observed source binds its source_ref
through the existing translation tool; other unresolved instructions enter the
bounded shared Agent loop. Corrected OCR is committed with correct_captured_text
before a Look follow-up, preserving provenance instead of silently re-OCRing.
Other mode changes retain this source context. No new OCR/translation/vision
engine, business executor, model or dependency was added. Non-text visual
understanding is not implemented by this OCR slice.

## Shortcuts and capture boundary

The Carbon helper now has a versioned READY MODES1 protocol and distinct LOOK /
MINIMAL events. Both registrations must succeed; stale Option-Shift-D helper
binaries are rejected and closed. Source startup tolerates missing/conflicting
helpers, exposing the error in the secondary menu. Offscreen sessions do not
register global keys. Future explicit app builds compile/package the helper in
the build's temporary directory; this turn did not compile it.

These shortcuts only summon the appropriate view. They do not capture the
screen, start monitoring, read Clipboard automatically or request permissions.
Use macOS Cmd-Shift-4 then drop the image, or explicit paste/picker. This keeps
the existing capture-hotkey backlog decision; Option-Shift-D remains deferred.
Only explicit invocation presents/activates Mini. Background completion stays
quiet through MiniShell, as before.

Main RAT currently also has an Option-Space summon alias in rat/os/hotkey.py.
That main binding/composition was not altered: migrating its alias to Look and
renaming its existing Multi UI to Full remain behind Mini acceptance. Concurrent
old main/new Mini shortcut handling has not been checked. Do not claim a global
conflict-free pair from successful source edits or helper registration alone.

## State of delivery

Source edits only. No tests, syntax/smoke check, app launch, screenshot, helper
compile, app build or ZIP in this iteration. The existing M5.16 bundle predates
Look and the bounded Agent follow-up. Its earlier 17 checks are not evidence for
this change. Actual hotkeys, image ingress, source retention, four-mode sizing
and configured-model operation remain unverified. Main integration, recipient M3
and Stage 0 are unchanged. User operates the app when explicitly opened later;
do not automatically run acceptance or build after this handoff.

## User-selected visual variants — 2026-10-27

User selected C (floating head) for translating one or two words/a short phrase
or a short sentence, and B (edge-peeking head/hand) for a paragraph. These are
content-responsive Look variants, not additional modes or business routes.
Look has no composer/input or permanent toolbar and must occupy less space than
Minimal. Mascot identity and anatomical scale stay consistent; do not enlarge the
head to fill a longer result. Exact length/wrapping thresholds remain to be set;
do not treat sentence count alone as sufficient to classify short content.
A (seated full body) has potential but is deferred, including as an idle pose.
The earlier suggestion to use A while waiting was not accepted.

Selected concept reference (generated design exploration, not runtime evidence):
`docs/design/rat-look-bc-options-20261027.png`.

This visual decision supersedes the input-bearing Look source prototype above.
The existing source still shares a composer and is not the accepted Look visual
implementation. B/C assets, adaptive bubble geometry and a no-input Look surface
remain to be implemented. No source UI change, tests, launch or build in this
visual-decision update. Main integration and M3 remain gated.

## Standby + C/B implementation — source only, 2026-10-27

User authorized: original standing sprite, stationary standby; C for very short
translations / one short sentence, B for a paragraph; no A. This supersedes the
input-bearing prototype and the earlier suggestion of a seated idle pose.

Implemented source:

- LookSurface.qml is a separate projection with no composer/header/permanent
  toolbar. Standby shows only the original 122×128 cutout, without sprite
  animation. C clips a head viewport; B adds a hand viewport from the same
  original pixels, at the same scale. These are original-sprite crops, not newly
  drawn versions of the generated pose board. Exact crop appearance is unverified.
- mini_presentation.look_projection chooses C for one line/sentence up to 100
  characters/18 whitespace words; multi-sentence, newline or longer text uses B.
  These are conservative layout heuristics, not semantic intent classification.
  Busy/empty states use standby. Errors use real status; partial results visibly
  say incomplete. Font wrapping still determines the bounded bubble height.
- C bubble 168–244 logical pixels; B requests 320; height capped at 216 with
  scrolling. Original character scale remains fixed. place_look keeps a separate
  remembered anchor near the screen edge, clamps the bubble into usable bounds
  and preserves the normal workbench home. A window-level minimum no longer
  inflates the 122×128 standby. Window/input masks follow the visible crop/bubble.
- Look can remain alongside the reader as a passive top-level window; it does
  not auto-hide on app change like the other modes. Explicit Hide/Esc when
  focused/copy completion still dismiss. Window-level changes never show or
  activate a hidden result; completion retains the existing quiet behavior.
- An image dropped/pasted/chosen in Look now follows the user's quick-translation
  case: shared capture_text → pinned source_ref → translate_text → verification.
  No instruction is taken from the hidden composer's independent draft, and that
  draft is not consumed. Explicit text paste uses the same capture/translation
  workflow. Non-image file references are not silently translated as paths.
- Original source / edited OCR / explicit follow-ups retain the existing shared
  operations and provenance. Double-click opens Minimal for typing; the secondary
  menu exposes OCR edit/image inspection, which temporarily use the existing
  workbench and Back path. No new business logic runs inside LookSurface.qml.
- Future packaging includes LookSurface.qml. Window/tray/menu identifier is
  'RAT Mini · Look source' to distinguish it from the existing M5.16 package.

No pytest, syntax/compile/smoke, UI launch/tour, screenshot, native helper build,
app build or ZIP was run for this implementation. All visual sizing, clipping,
right-click menu behavior, double-click/drag, native floating-window behavior,
shortcuts and actual OCR/translation remain unverified for this source revision.
The known local-translation error is not diagnosed/fixed by this UI work.
The existing M5.16 app/ZIP does not include this implementation. Main binding/UI
integration and recipient M3 remain gated; live Agent planning and research
quality are not established; Stage 0 is unchanged.

Implementation notes from final source reading: Look's secondary menu uses a
separate Qt 6.8 popup window so it is not clipped to the small mascot window
(installed package metadata reads PyQt6 6.8.1; no runtime check was run). New task
speech scroll resets while hide/recall retains it. Edited-but-untranslated OCR
marks the displayed translation as predating the edit. Explicit text paste also
pins the captured source for later requests and removes a stale image preview;
the separate text draft remains unchanged. All of these behaviors await the
same later user-requested verification; source reading is not acceptance.

## Requested build and bounded checks — 2026-10-28

Built an initial candidate, then found a real Agent journal issue: a successful
Mini Finder result with domain status `complete` and structural verifier PASS
was recorded as uncommitted, causing `completion_unresolved`. Scoped the fix to
Mini registered operations and require a real artifact plus PASS verification;
partial, errors and failed/unknown verification do not establish completion.
Existing main-profile status handling is unchanged. Fixture tests now include
the planner contract and check both partial and failed verification.

The corrected app is `dist/mini-look-20261028-fix1/RAT Mini.app`, with ZIP beside
it, version 0.5.17 / 20261028.2. Build log, raw failures, test outputs and ZIP
SHA-256 are in `audit/rat_mini_look_20261028/`. The previous first build remains
in `dist/mini-look-20261028/`. Ad-hoc codesign verification passed; not notarized.

26 initial Look/Quick/placement/router checks passed. The OCR/translation subset
had 3 passed and one Agent fixture failed; after diagnosis/fix, that fixture and
2 negative cases passed. A separate offscreen Qt standby check passed for the
original 122×128 mascot, hidden composer and retained draft. These are software
checks, not native or recipient UI acceptance. A real source-backend English →
Vietnamese request returned 'Xin chào thế giới.' via offline_argos with a PASS
structural report and zero Agent model requests. It does not validate the bundled
backend, native OCR, physical shortcuts or live model-driven reasoning.

Native app launch/acceptance remains blocked: an existing M5.16 process (PID
34618 at inspection) owns the default RAT Mini lock; its potentially unsaved
session was preserved. Computer-use attempts to bind both bundles timed out;
Terminal UI control was denied by the computer-use policy. The user was asked to
exit the old instance if its draft can be discarded, then allow a fresh attempt.
No screenshot or fabricated conversation was used. Main/M3/Stage 0 remain open.

### Live continuation and focus revision — 2026-10-28

User exited the old instance. Opened the real corrected bundle and selected Look
through its menu: accessibility showed one Look mascot and no composer. Injected
Option-Space in the previous build inserted whitespace into the empty composer;
automated paste/double-click in Look caused no observed UI change. This does not
establish physical shortcut or pointer behavior. The text was removed.

Prepared 0.5.17 / 20261028.3 in `dist/mini-look-20261028-fix2/`: selecting Look
from the mode menu now uses the summon/present/focus path, and mascot dragging
starts only after pointer movement so an ordinary double-click can be delivered.
Qt offscreen standby/focus/draft check passed. Attempts to exercise pointer input
offscreen did not reach the MouseArea even though hit-testing identified it;
raw failing logs are retained. Do not count those attempts as a successful click.

Opened the .3 app and selected Look. Automated paste, double-click and right-click
still produced no observed accessibility change; no fabricated response or
screenshot was substituted. User was asked to physically paste a public phrase
into Look. User response is pending. SHA-256 and all logs are in
`audit/rat_mini_look_20261028/status.json`. Live model planning and physical
shortcut/UI acceptance remain unverified. The original source-backend translation
is not evidence that the bundled UI translation succeeded.

### Shortcut and focus correction — 2026-10-28

User confirmed Option-Space invokes Spotlight on their Mac. Do not bind it for
Look. User chose: tap Option-Shift-Space for Minimal; hold the same chord for
0.5 seconds and release for Look. Native helper source now registers only that
single chord, distinguishes press/release duration, and uses READY HOLD1 so older
helpers are rejected. This does not change the main RAT binding or enable main
UI integration. Real physical hotkey delivery still requires user verification.

User physically tried copying 'Hello world.', clicking the Look mascot and
pressing Cmd-V in .3: no response. A separate Qt offscreen diagnostic with actual
clipboard input and offline model returned 'Xin chào thế giới.' (no canned model
result); it does not establish macOS focus. Source now requests application and
window focus on an explicit mascot press/accessibility action; hidden windows and
background completion do not activate themselves. Five related software checks
passed after this change. Build and physical user verification remain distinct.

### Current hold/focus build

User chose a short hold of Option-Shift-Space for Look, retaining a quick tap for
Minimal, after reporting that Option-Space opens Spotlight. Latest built/opened
candidate is `dist/mini-look-20261028-hold-focus/RAT Mini.app` (0.5.17 /
20261028.5). The helper was observed alive but physical delivery is not yet
confirmed. Automated synthesized hold produced a whitespace character in the
empty composer; it was removed. Five Look checks passed. Ad-hoc signature
verification passed, not notarized. User was asked to test the physical chord
and then paste the public text; response was pending at this update. Full logs
and ZIP SHA-256 are in `audit/rat_mini_look_20261028/status.json`.

### User-confirmed paste and current candidate — 2026-10-28

Current opened candidate: `dist/mini-look-20261028-inputfix/RAT Mini.app`,
0.5.17 / 20261028.6; ZIP and hash in audit status. Six targeted Look software
checks pass, including a Qt offscreen paste using the real offline translator.
Ad-hoc signature verification passes; not notarized. The app logs only the
registered hotkey stage in `last-hotkey.json`, never typed text or Clipboard.

The user initially reported that holding the chord did not open Look. A later
helper diagnostic recorded the `look` stage, but without an event timestamp, so
this is not an independent physical-shortcut repeatability pass. After Look was
opened, the user reported that copying 'Hello world.', clicking RAT and pressing
Cmd-V produced a translation. We did not independently capture the exact text:
the next accessibility read showed standby only. No screenshot was requested or
captured. The user asked to keep the current shortcut setup; no further key
change was made. Option-Space belongs to Spotlight on this Mac. Current intended
mapping: tap Option-Shift-Space for Minimal; hold it 0.5 s and release for Look;
Cmd-V is the paste action while Look is focused.

This is a single user observation, not full Look/M3 acceptance or proof of live
model-driven reasoning. Physical shortcut repeatability, long B presentation,
real image/OCR ingress, packaged translation coverage and recipient acceptance
remain pending. Main UI/binding integration and Stage 0 remain unchanged.

## Shortcut direction corrected by user — 2026-10-28

User explicitly corrected the intended mapping: **tap Option-Shift-Space to
open Look; hold it to switch to Minimal**. This supersedes the earlier reversed
mapping, including the previous hold-for-Look decision. Option-Space remains
reserved for Spotlight on the user's Mac; Cmd-V remains paste.

This entry records the plan decision only. The existing source and 0.5.17 /
20261028.6 bundle still implement tap → Minimal and hold → Look, and have not
been changed or rebuilt in this planning turn. The implementation must swap the
native helper's outcomes, its protocol/callback labels and user-facing menu text
consistently, then verify physical tap/hold separately when testing is requested.
Do not claim the corrected mapping is active. Preserve the user's draft/session,
the main RAT integration gate and Stage 0.

## Source revision — Look repair, 2026-10-28

User screenshot showed clipped long text, an overlapping tooltip and fragmented
crop sprites. The source now uses separate generated C (floating head) and B
(edge peek) images based on the original character; standby retains the original
standing sprite. Bubble height is bounded and long text scrolls; the mascot
hover tooltip is removed. Copy takes the exact rendered bubble text. The new
sprites and layout still need the user's visual review.

Explicit “Chọn vùng chữ để dịch” in the Look context menu or tray starts macOS
region selection and uses the shared capture/OCR and translation tools. Until
capture succeeds the existing task and independent draft remain intact; cancel
restores the prior presentation. The selected image is held in memory for the
existing image/OCR views; the system may request screen-recording permission.
Background completion does not activate or reopen the window.

The native helper source now emits LOOK on tap and MINIMAL on a hold of at least
0.5 seconds, with protocol HOLD2 to reject an old helper. Physical recognition,
focus, region capture, and the sprites have not been verified in this revision.
The previously packaged 20261028.6 app predates all these edits; no build, test,
or UI session was run for this revision.

The Mini Agent still uses the shared model-driven runtime for compound requests;
no live model turn was run here. Telemetry distinguishes requests from received
model responses and completion events retain the actual completion status. A
response counter alone is not evidence of a successful multi-step plan, semantic
correctness, or user acceptance. Main integration and Stage 0 remain gated.
