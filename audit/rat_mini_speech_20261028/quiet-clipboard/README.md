# Quiet Clipboard — build 20261028.16

Source: Mini interaction/presentation iteration approved 2026-10-28. No main UI
integration, Agent model planning, recipient M3 or Stage 0 claim.

## Changes

Clipboard delivery only replaces one pending snapshot. It cannot show a window,
execute tools, cancel the current job or replace the reading source/result/pose.
Explicit single click or bubble action opens pending input through the existing
capture→translate tool contracts. Result recall is separate. Fixed remembered
corner, task-scoped head/seated pose, shared SpeechBubble and optical size 86.
Hidden/peek/reading are separated from monitoring and execution. Peek hides in
five unengaged seconds. Reading is retained until close/Esc/Copy/outside; closing
preserves current task, pending source and monitoring. Completion cannot reopen.

## Software evidence

- `tests-native-runtime.log`: initial final batch, 39 passed, 2 failed because
  the previous temporary CTranslate2 dependency had disappeared.
- `dependency-restore.log`: restored pinned CTranslate2 4.8.4 into /private/tmp,
  without changing project/environment dependencies or enabling an LLM.
- `look-final.log`: 6 passed, 1 failed. Real queued workflow succeeded; remaining
  paste fixture inherited offscreen-native-clipboard-unavailable notice. Fixture
  now pauses offscreen monitoring explicitly, rather than fabricating native support.
- `paste-final.log`: remaining paste check passed, real local translation.
- Across these bounded checks, all 41 selected tests have passed. Changed Look
  checks were rerun; passing unrelated groups were not repeated. Offscreen tests
  do not establish native macOS acceptance or translation quality.
- `tests.log` / `look-retry.log`: sandbox Qt CPU feature-detection failures
  (`neon`) retained. Qt checks succeeded outside the sandbox.

The new queue integration check simulates adapter delivery only; actual capture
and offline translation run through Mini. It verifies no task start/show on copy,
no cancellation when B arrives during A, no automatic B start on A completion,
retained A across close/recall, and explicit B acceptance. Public source phrases
are Hello world. and Good morning. No canned assistant outputs were injected.

## Native verification

CUA inventory reported the Mac locked. Unlock requested once while independent
checks/build continued. No .16 screenshots or native acceptance claimed at this
point. Older .13/.14 screenshots are not evidence for this interaction revision.
Build/signing/launch outcome is appended below when available.

## Packaging and launch outcome

Build 20261028.16 completed. Strict/deep ad-hoc signature verification passed;
ZIP hash saved in package.sha256. Not notarized. `open` succeeded and process
6897 was observed running from the .16 app path. CUA again reported the Mac
locked; no native screenshots/acceptance were possible. App left running for
the user. No old session was terminated.

## Native follow-up after user unlocked Mac

CUA succeeded after user said go on. Production .16's shared bundle identity
was ambiguous and binding by exact path timed out. A copy named RAT Mini QA16
uses the same .16 code with only display/bundle identity changed and separate
state/receipt directories; ad-hoc re-signed. Production .16 was not modified.

- 01-idle.png: real seated rat and speech bubble. Peek later disappeared.
- A real TextEdit Cmd+C of Hello world. produced no translation receipt before
  explicit opening. Hidden AX lookup timed out; absence of a popup alone is not
  treated as a successful AX visibility assertion.
- 02-pending.png: pending source in real UI; Mở đoạn này clicked through AX.
- 03-result.png: actual offline Xin chào thế giới.; working pose also observed.
- 04-recalled-after-copy.png: Copy then product recall retained the result,
  without showing a new queued source from RAT's own clipboard write.
- Real TextEdit Cmd+C of a library paragraph kept the previous translation;
  05-long-pending.png shows Xin chào thế giới. with Mở đoạn mới. This is native
  evidence that a new copy did not replace the displayed result or start work.
- 06-long-result.png: explicit Mở đoạn mới ran actual offline translation and
  showed the seated rat. It completed before capture; no claim of a captured
  long processing pose. The former working filename was renamed accordingly.
- 07-long-recalled.png: Esc followed by product recall retained the long result.

Exactly two translation receipts, public sources and observed results retained
in native-receipts/ and native-observations.json. No assistant result injection.
Native actions used CUA; the existing product activation bridge was used to
recall hidden Look. A delayed single recall accommodated the five-second peek
window; no visibility/timer policy was changed for acceptance. TextEdit used
only the existing test-owned document (Không có tiêu đề 2.rtf).

No native error, multiple-monitor, long scrolling or general comfort/quality
acceptance claimed. Two phrases do not establish translation quality; the known
idiom error remains unresolved. Main UI, M3 and Stage 0 remain gated. QA16 was
stopped after these bounded checks; production .16 remains running.

## Follow-up: scroll and user screenshot, 22:44

QA16 was relaunched with the same isolated settings. Real TextEdit source was a
four-paragraph library notice. Actual local translation is retained as a third
receipt. 09-scroll-top.png and 10-scroll-bottom.png show native scrolling to the
last line; this is stronger coverage than the earlier three-sentence passage.
No claim that the translation is idiomatically correct; several awkward phrases
remain in the observed output.

The synthetic Option+Shift+Space attempt through CUA left QA's helper stage at
ready and did not change QA to Look. It also left a non-breaking space in the
test-owned TextEdit document, subsequently replaced with the test passage.
Registration is observed; physical global-hotkey acceptance is NOT established.
No app shortcut implementation was changed on this evidence alone.

After Esc, attempts to inspect recall through CUA timed out. The user's actual
22:44:10 screenshot (copied to user-22-44-10.png) shows Look visible. Therefore
those tool timeouts do NOT establish a disappearing-window bug. Scroll position
retention and native error recovery remain unaccepted in this follow-up.

The screenshot exposed clipped final text with an inconspicuous transient scroll
bar. Source .17 adds a persistent scrollbar only for overflow, an 8px text gutter,
and a small bottom fade only while more content remains below. Short-text natural
width includes this gutter; no new business tool, model or capture path. The
shared SpeechBubble owns these indicators. Mini version increments to .17.

check_speech_overflow.py + overflow-final.log check overflow policy, end-of-scroll
fade removal and one-line short text using an offscreen component fixture. It is
not a native screenshot or assistant-response fixture. Initial script type errors
were corrected; only the final script and passing log support this UI change.

## .17 final bounded native check

Built .17, deep/strict ad-hoc signature verified, ZIP hash package17.sha256.
QA17 had a distinct bundle identity and isolated configuration. Code matches
.17. Native receipts17 contains the actual long offline translation. Screens
12-overflow17-top.png and 13-overflow17-bottom.png show the visible scrollbar,
continuation fade before the end, and final lines with no continuation fade.

The error pass restarted only QA17 with a separately prepared configuration:
translation_provider=mymemory, free_fallback=false, llm_enabled=false. This
triggers real online_translation_not_enabled before a network request, rather
than fabricating an assistant output or breaking dependencies. A real TextEdit
copy and UI Mở đoạn này invoked the same workflow. 14-error17-attempt.png and
15-error17-retry.png show the actual failure and seated error sprite. The
initial 14-error17.png is only idle after an unsuccessful synthetic paste.
Both error receipts retain artifact art-9608a7747fc84598a445e814e1ccc243 revision 1;
retry reused the source. Each records llm_calls=0. Configuration unchanged means
retry still fails: successful recovery is NOT accepted. Generic copy is an open
UX issue: a settings problem should explain the required setting, not only retry.

Right-click menu and synthetic paste attempts did not produce their expected
UI transitions through CUA; no main implementation change was inferred from
those actions alone. A fresh copy plus explicit pending action worked. Physical
hotkey and retained scroll recall remain unaccepted. No multi-display run.

QA17 stopped after evidence capture; production .16 PID 6897 was preserved.
.17 is a separate artifact, not silently substituted into the user's live
session. LLM default, main UI gate, recipient M3 and Stage 0 remain unchanged.

## .18 — BOTH large, shared scale (user correction)

The two user size screenshots are preserved as user-size-look.png and
user-size-minimal.png. User explicitly rejected shrinking Minimal: both must
be large as a stylistic choice. No Minimal width reduction was implemented.

Common Mini profile: 176×152 host, 134px visible body height, 16px text, 580px
panel/speech maximum width. Short speech still hugs content. Head scales at
42% body height. Wide seated error used to be width-limited; widened host now
permits the same 134px optical height. Main standing sprite uses MascotPose
with alpha bounds measured from the original image, preserving its proportions.
Minimal and Look reuse the same corner anchor/placement; workbench placement
for Single/Full retains its existing policy. Main UI is not switched.

size18-tests.log: 49 passed after source completion, including actual offline
Look software flows and changed geometry/profile cases. check_pose_scale18.py
uses actual QML/assets: visible standing 134×126.7, idle 134×133.2 and error
134×166.6 (height×width). These values are based on explicit ink metadata, not
pixel-perfect subjective art alignment. Build-size18.log records .18 packaging;
strict/deep ad-hoc signature and ZIP hash recorded separately. Not notarized.

Native QA18 shares code with .18, unique identity and isolated error config
(MyMemory disabled, LLM off). 16-shared-large-minimal18.png and
17-shared-large-look-idle18.png show actual large Minimal/Look. Their raw crops
have different total widths; do not scale each to an equal display width and
mistake the resulting mascot sizes for native optical sizes. Both sprites use
the same 134px target. One .18 error capture attempt timed out; no .18 native
error acceptance claim. .17 real error and .18 QML error pose measurement are
separate evidence. QA18 cleaned up; user's .16 session was preserved.

Known remaining work: actionable settings error copy, physical hotkey and
robust native inspection/scroll recall confirmation. No new LLM/model planning,
main UI, recipient M3 or Stage 0 acceptance is established by this size change.
