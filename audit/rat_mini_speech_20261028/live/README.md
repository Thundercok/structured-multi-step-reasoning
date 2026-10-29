# Native continuation — user-authorized test/fix, 2026-10-28

The user explicitly authorized autonomous UI testing and fixes while away.
This continues the earlier software/build report; it is not a general future
test authorization.

## Actual observations

1. Desktop was initially unlocked. The default .8 process (PID 17705 at initial
   inspection) still held the normal session lock. It was preserved.
2. .10 was launched with isolated state/receipt paths. CUA could initially read
   its real composer, but later interaction/capture attempts timed out.
3. To disambiguate installed bundles, created an ad-hoc QA copy of .10 with a
   unique bundle name/ID and LSEnvironment for separate state. Binary and QML
   were unchanged; only Info.plist identity/environment and signature differed.
   `qa-copy.json` records this distinction. No model answers were injected.
4. In QA .10's real composer entered `Dịch sang tiếng Việt: Hello world.` and
   pressed Return. UI showed translate_text working, then `Xin chào thế giới.`.
   `02-real-translation.png` is the actual window. Receipt in `receipts-qa/`
   records completed, offline_argos, zero LLM calls and structural verifier PASS.
   Structural PASS does not establish semantic translation quality generally.
5. AX-index clicks to open workspace menus timed out; no passing menu result
   was inferred from those attempts. Source review found a fixed bundle-ID alias
   in the focus handler, which could misclassify diagnostic/future bundle recall.
   .11 uses the running frozen bundle's actual ID. It passed 20 related checks
   (`tests-focus-repair.log`) and built successfully (`build-focus-repair.log`).
   This source defect is distinct from proving the cause of every CUA timeout.
6. QA .11 used another isolated identity/state with .11 code. Its window was
   read successfully, although the binding call took approximately five minutes.
   Coordinate clicking the workspace button worked. Home/Return did not choose
   Look; screenshot `04-workspace-menu.png` records the menu still open.
7. Coordinate clicking Look then worked. `05-look-idle.png` is the actual compact
   seated mascot with speech body/tail and status dot. It is .11 native evidence.
   The short status `Copy chữ để dịch` wrapped over two lines.
8. Attempting a real TextEdit select/copy sequence next returned Mac locked.
   No automatic clipboard translation, long-result scroll, latest-copy handling,
   native auto-hide or error recovery acceptance is claimed from that attempt.

## Fixes and delivery

- Same-app recall recognizes the actual packaged bundle ID, rather than a fixed
  production identifier. Source execution still uses process identity.
- .12 measures speech with the TextEdit's exact font and advance width plus
  rounding allowance. A targeted regression checks that the idle phrase fits
  one line; all six Look checks passed (`tests-text-measure.log`). No native
  .12 screenshot has been captured; .11 images must not be labelled .12.
- .12 build path: `dist/mini-speech-20261028-fix2/RAT Mini.app`, ZIP beside it.
  See `build-text-measure.log` and the final delivery metadata in `status.json`.
  .11 is retained under `dist/mini-speech-20261028-fix1/` for recovery.
- .12 build completed and its ad-hoc signature passed strict/deep verification.
  ZIP hash is in `zip-sha256-final.txt`. This is not notarization or native .12
  acceptance. The isolated QA .11 process was also stopped at end of the run;
  the user's .8 process was left intact.
- Initial isolated .10 and QA .10 test processes were stopped after their
  completed observation; the user's original .8 was preserved. QA states and
  receipts remain under this audit directory. A new TextEdit document containing
  only the public test phrase was created; the pre-existing document was not edited.

## Evidence index

| File | Meaning |
| --- | --- |
| 02-real-translation.png | Actual completed .10 QA translation through the composer |
| 03-qa11-ready.png | Actual .11 QA ready composer |
| 04-workspace-menu.png | Actual workspace popup, before Look selection |
| 05-look-idle.png | Actual .11 QA Look seated mascot and speech tail; pre-text-measure fix |
| receipts-qa/mini-*.json | Actual operation/verification receipt for the translation |

Native screenshots are unedited. No source-generated or fixture screenshot is
used as native acceptance. Software checks, packaged binary evidence, native
observations, LLM reasoning, main integration and research Stage 0 remain separate.

## Next scope — ten priorities

1. **Observe .12 once unlocked.** Confirm the exact build and repeat only the
   corrected idle phrase; compare with the pre-fix .11 screenshot.
2. **Finish real Clipboard ingress.** Copy one public phrase in TextEdit and
   retain the automatic capture/translate receipt plus screenshot.
3. **Check copy concurrency.** While a result is explicitly opened for reading,
   copy a second phrase and verify Mở đoạn mới preserves the current source.
4. **Verify own-copy suppression.** Use the result Copy action once and confirm
   that it does not create a new task; do not substitute a controller fixture.
5. **Review passive versus explicit reading.** Observe hide after five seconds,
   then recall/click and verify that reading stays stable until closed.
6. **Review one long passage.** Check scroll restoration and action reachability
   at the actual display scale, with the shared bubble and seated sprite.
7. **Check one real recovery.** Retain an encountered missing-input/backend error
   and inspect the seated error sprite and retained source/retry path.
8. **Resolve input accessibility.** Distinguish unsupported AX activation from
   product focus/menu defects; coordinate interaction worked on QA .11. Avoid
   claiming universal keyboard/AX acceptance from that one successful path.
9. **Evaluate translation quality/cost separately.** Keep actual outputs for
   user-relevant idioms and measure resources in an agreed scenario. This one
   greeting and a process sample do not establish quality or memory efficiency.
10. **Promote accepted shared infrastructure.** Incorporate only the UI behavior
    confirmed in Mini into main after its gate. LLM remains disabled by default;
    no main integration, recipient M3 or Stage 0 result is established here.
