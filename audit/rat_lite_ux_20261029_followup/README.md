# RAT Lite follow-up .20 — 2026-10-29

## Trigger and scope

The .19 acceptance run repeatedly failed to bind/control Look through CUA.
User reported Xin chào thế giới visible after manual opening, but QA19 still
had no translation receipt. The user's supplied 11:47:24 screenshot showed
pending source (Đoạn mới: Hello world / Mở đoạn này), rather than a result.
Do not reject the later user report, or convert it into verified .19 end-to-end
acceptance without the corresponding artifact. The mismatch remains unresolved.

Explicit user authorization allowed closing saved/done .16; PID/path was
verified and .16 closed. No source or recovery files were removed. Only test
QA instances were subsequently replaced. Mini is now named RAT Lite for future
work; existing identifiers/bundle names are retained.

## Changes

1. Pending source now says Chờ dịch; primary action says Dịch đoạn này. Badge
   says đoạn chờ and its accessibility text names translation. This addresses
   the observed preview/result ambiguity without automatic dispatch or a new
   business path.
2. Optional QA metadata records build/PID, mode/surface, phase, pending/busy,
   task/generation, action invocation and actual execution/receipt status.
   These metadata files do not add draft, clipboard or result text.
3. Receipt-write failure cannot replace an already valid service response with
   an unrelated business error. It is reported separately. This is a recording
   robustness repair, NOT a demonstrated cause of the earlier missing receipt.

All business work still uses existing MiniSession/capture/translation service,
dispatcher and artifact validation. Default LLM remains off. No main UI, Agent
model planner, recipient M3, Stage0 or model-quality acceptance is established.

## Bounded verification

- targeted-tests.log: 7 passed after changes completed. Actual offline worker
  translation was run with a writable recording target and a deliberately
  invalid target. Success persists despite recording failure; healthy receipt
  records real artifacts and 0LLM calls. A metadata privacy regression verifies
  that a draft/clipboard marker is absent. Existing interaction contracts are
  included. These are software checks, not native conversation acceptance.
- build.log: .20 packaged in dist/rat-lite-20261029-observable/.
- signature.log / package.sha256: strict/deep ad-hoc verification and ZIP hash.
  Not notarized. Do not reuse .19's 58-check count as a fresh .20 batch claim.

## Native attempt and concrete limit

QA20 has unique bundle/executable identity, same code as .20, and isolated
state/receipt paths in LSEnvironment. It was launched through macOS Launch
Services. .19's QA was closed; unrelated work was preserved.

ui-state.json identifies build20261029.20 / PID7562, workspace minimal, phase
idle, pending=false, busy=false, task_id=0, generation=0. UI-action and execution
metadata were not created in this attempt. CUA timed out before it could set
or submit the public typed request. Thus the native attempt did not reach
dispatch, and no .20 native translation/receipt/screenshot success is claimed.
This observation does not retroactively establish what happened in .19.

No alternate GUI automation, injected assistant answer, fake native screenshot
or hidden business call was used to bypass the control limitation. QA20 is
left available for manual review. No further automatic screenshot/test retry
loop is authorized by this handoff.

## Remaining acceptance

Current .20 native short translation, pending-copy preservation, long scroll /
selection / Copy, close/recall, actionable-settings recovery, global shortcut
and multi-display are unaccepted. Earlier .16–.18 observations and .19 fixtures
remain separately labeled. The full ten-point native acceptance is incomplete.
