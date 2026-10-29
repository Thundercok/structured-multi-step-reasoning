# RAT Lite — next update plan after .25 feedback

2026-10-29. User requested a careful plan for the next update. This is the current
plan; earlier broad UI/result-summary proposals remain deferred where conflicting.
Planning does not authorize tests, build, launch, screenshots or a UI tour.

## Starting evidence and release scope

.25 was packaged/opened. The user's screenshots show an oversized seated mascot,
blank reader space, duplicate Close, clipped input and an unhelpful menu item.
The user also reported no response to highlight → ⌥⇧Space. Subsequent read-only
inventory showed .25 alive, helper absent, and last metadata stuck at ready.
No actual selection/translation receipt established a successful invocation.

.26 source repairs those visible entry defects, changes helper parent monitoring,
records helper failures and exposes explicit reconnect. It is pushed but unbuilt
and unverified. Stdin EOF was a possible helper exit path removed in source;
its role in the observed failure has not been established. Do not label the
hotkey fixed from source review or READY alone.

The next delivery is a repaired .26 candidate, with version increased if another
candidate is already distributed. Keep the scope to usable Quick Look and clean
compact entry. No new capabilities, new model, auto-Clipboard fallback, animations,
or main integration. The large expanded layout remains available, but its full
single-reader consolidation is a later change unless it blocks this flow.

## 1. Finish source behavior before packaging

### Hotkey lifecycle and observability

Maintain one helper owner and explicit states: starting, registered, stopped,
failed, intentionally closing. Include app build/PID, helper PID, monotonic event
order and close reason. Record intentional close as well as unexpected exit;
the current close path can otherwise leave old ready metadata behind. Keep a
bounded recent transition history and current summary so registration cannot
erase the failure immediately preceding it. No selected text, Clipboard text,
image, path to the source document or pointer position goes into default metadata.

Reconnect is explicit, disables its action while starting, closes the old owner
before replacement, and leaves exactly one live registration. Normal shutdown
cleans up; helper exit leaves typing/menus usable. No infinite restart loop.
Treat registered, helper-alive and physical-key-received as different evidence.
Do not replace Carbon with another transport unless recorded failures justify it.

### One invocation has one visible outcome

| Situation | Required behavior |
| --- | --- |
| Free + source app frontmost | Pin source PID; capture through existing selection tool before RAT activation. |
| Existing task/capture busy | Preserve it. Show a short busy acknowledgement without taking focus or overwriting the result; no silent return, cancellation or queued execution. |
| RAT frontmost | Recall/compose; never capture RAT's own input as external selection. |
| Accessibility missing | Show the specific permission explanation/action; preserve source/result/draft. Granting does not auto-submit. |
| Empty/unsupported selection | Say what could not be read; offer explicit paste/image alternatives. Never substitute stale Clipboard. |
| Source changed or capture timed out | Stop that invocation and explain; retain the previous task. |
| Capture succeeds | Commit the actual artifact/session, then show processing/result using the same small head. |
| Translation fails | Keep captured source and relevant explicit recovery. Do not recapture a now-unrelated selection during translation retry. |
| User dismisses during capture/execution | Invalidate presentation intent; later completion cannot reopen RAT. |

Give the invocation an ID shared by helper-received metadata, controller decision,
capture, dispatch and presentation. Record sanitized stage/outcome, including
ignored-busy, capture-error and presented; callback exceptions must become a
visible failure with a diagnostic code. Reuse existing execution IDs/artifact
references once available rather than inventing a second execution state machine.

For source context, preserve not only old tool data but old extent/view/reader
context until capture succeeds. Confirm that failure notices have a route back
to the old task, and that permission notices still appear when there was no old
task. Keep user-owned draft separate throughout. Never infer AX trust from a
separate Python process: permission belongs to the actual running app identity.

### Clean compact UI from first invocation

Keep one small floating-head silhouette at entry, processing, result and error.
Keep source .26's 64×64 host, approximately44px optical target and font16 as the
starting candidate. Do not vary pose by text length. Menu/dialog views cannot
silently reset the compact anchor. Expanded work is an explicit user gesture.

Empty composer must measure only its content: short shortcut hint, input,
Send/More/one Close in one row. Initial width300, at most360 in compact reading.
No ghost reader, empty action rail, stacked-paper layer, large status pill or
long truncated placeholder. With a result, render only the useful text viewport
and required actions; long text scrolls, with explicit expansion in the menu.

Audit state changes against actual control heights, not fixed mock dimensions:
empty → typing, submit → working, working → result/error, permission notice,
and preview → recall. Preserve outer position and current dimensions across
processing; avoid moving focus just because content changes. Check that removing
one Close does not remove the only Close in a different state. Shortcut failure
must be visible from tray/compact UI even though the regular status pill is gone.

## 2. Small implementation commits and concrete review

1. Helper lifecycle/intentional-close metadata, bounded history and reconnect
   ownership. Review the helper-owner diff separately.
2. Controller invocation outcomes: busy acknowledgement, callback error handling,
   correlated stages and capture return context. Keep tool schemas/dispatch shared.
3. Remaining compact state/layout corrections only where source review identifies
   a mismatch with the rules above. No speculative restyling.
4. Handoff with exact baseline/diff, remaining uncertainties and release identity.
   Show the user the differences before treating a candidate as accepted.

Commit/push each coherent step under the standing README/AGENTS authorization.
Preserve the two unrelated current audit/lock changes. No history rewrite or
bulk cleanup. If the changes exceed these concerns, defer them to another update.

## 3. Package/open only when requested

After source completion, produce one app+ZIP in a fresh versioned dist folder,
compile helper and collect ApplicationServices together. Read back bundle BUILD;
keep app/helper protocol paired. Keep .25 recoverable. Close the previous app
gracefully, confirm the old instance is gone, then open the exact new path so
single-instance recall cannot masquerade as a new version. Check startup metadata
and process identity only; these do not establish key delivery or UI acceptance.

Show a short before/after list and tell the user the exact visible change: small
head immediately, no empty top region, one Close. Do not promise the hotkey works
until its physical event and resulting tool execution have evidence.

## 4. Bounded manual observations for a later requested check

The user operates the candidate. Suggested order keeps failures local:

1. Open empty input: inspect size, small head, placeholder and exactly one Close.
2. In one chosen source app, highlight a harmless public sentence and press the
   chord once. Correlate key-received → capture → actual result/permission/error.
   The process staying alive and READY alone cannot pass this item.
3. If permission is missing, grant it to the intended app through the explicit
   action; return to source and press again. If unsupported, record that app's
   limitation instead of substituting a successful fixture.
4. For one successful supported source, show actual source provenance and result;
   confirm Clipboard unchanged and no unrelated source read. Distinguish structure
   verification from translation quality.
5. If earlier steps work, observe one busy invocation and one dismiss/recall while
   working. No interruption, lost draft or unsolicited reopen is acceptable.
6. Observe one long result and explicit expand/collapse only if the earlier path
   works. Record focus/reader-position defects rather than broadening the tour.

Stop at the first blocker, repair that piece, then repeat only the failed/changed
transition when requested. No automatic suite, UI tour or screenshot collection
is authorized by this plan. Any separately requested software checks must target
meaningful lifecycle/capture behavior rather than cosmetic implementation copies.

## Acceptance and fallback

Call the candidate usable only for the actual supported path observed: no silent
keypress loss; one clear outcome per gesture; no stale Clipboard; preserved old
task on capture failure; clean entry matching the user's visual intent; no
background activation after dismissal. Track supported source apps individually.
An unsupported app is a documented limitation, not a reason to claim all AX
selection is broken or to enable global key simulation silently.

If helper loss recurs, retain the exit/close record first. If helper survives but
no key event arrives, investigate native delivery/conflicts; if key arrives but
capture fails, inspect source/AX permission; if dispatch succeeds but nothing is
visible, investigate presentation guards. This ordering avoids another round of
unrelated UI changes while the shortcut remains nonfunctional.

Reuse shared capture→artifact/source_ref→translation/service/dispatcher/verifiers.
No model loop, main integration, recipient M3 or research Stage0 acceptance is
established by this work. Current translation-provider/LLM preferences stay under
their existing contracts. Planning changed no application code or running app.
