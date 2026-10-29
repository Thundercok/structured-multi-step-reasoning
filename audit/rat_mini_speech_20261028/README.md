# RAT Mini speech — bounded verification/build report, 2026-10-28

User explicitly requested tests, build, screenshots, report and further planning.
This authorization covers this bounded turn, not automatic future tests.

## Verified software/package results

- 55 checks passed, 1 semantic check deselected, 13.22 s; raw output in
  `tests-initial.log`. Scope: shared speech geometry, default LLM disabled before
  key access, existing Mini tools/Quick/Look/panel checks, QML message checks and
  real offline translation through an offscreen source app. Contract fixtures
  are software evidence only. The offscreen run is not native UI acceptance.
- Updated old fixture expectations for the intentional 80×84 Look canvas,
  passive focus, status bubble and explicit LLM opt-in. Offscreen has no native
  clipboard watcher, so its standby check explicitly pauses that adapter.
- Build completed: `dist/mini-speech-20261028/RAT Mini.app`, 0.5.17 /
  20261028.10, and ZIP beside it. Raw `build.log`, `signature.log`, ZIP SHA-256
  and exact byte size/QML inventory in `status.json`. ZIP approximately 209 MiB.
- Ad-hoc signature verification passed. Not notarized. Shared SpeechBubble,
  MascotPose and LookSurface files were found in the built app.

## Native UI/screenshot limitation

CUA inventory twice reported that the Mac was locked and automatic unlocking
was unavailable. Asked the user to unlock while continuing independent work.
After the user replied “go on”, binding the existing Mini bundle timed out with
`-10005: timeoutReached`. No screenshot was obtained. No screenshot or successful
UI conversation was fabricated or substituted with an offscreen render.

The old .8 process (PID 17705 at inspection) was preserved. Its default-session
lock must not silently turn a .10 launch into recalling .8. This turn did not
verify a .10 native window or physical shortcut/clipboard operation.

## Findings and limits

The bounded software group found no failing check. That does not establish
optical alignment, tail quality, native focus/masks, actual Clipboard polling,
auto-hide, keyboard ergonomics or stability on the recipient machine. The
user-observed idiom mistranslation remains unresolved. No CPU/RAM/energy profile
was measured. No new live Agent model reasoning claim; LLM remains default-off.
Main integration/M3 and research Stage 0 remain unchanged.

## Next iteration — ten priorities

1. **Unblock native observation.** Resume only when CUA can observe the unlocked
   desktop. Confirm the exact .10 bundle/window before interpreting screenshots;
   preserve or explicitly close the old session using actual UI observations.
2. **Capture one short-result exchange.** Use a real phrase through the UI and
   actual backend. Retain source, public result and screenshot, so wording and
   compact geometry can be assessed together.
3. **Inspect the universal bubble/anchor.** Check idle, head and seated poses at
   the fixed edge, including dark/light presentation where requested. Correct
   normalized ink/mouth metadata or shared tail drawing based on real pixels;
   avoid another mode-specific bubble implementation.
4. **Exercise long reading once.** Translate a real longer passage, scroll,
   close and recall. Verify the body stays inside the display, actions remain
   reachable and the speech scroll returns to its previous position.
5. **Confirm quiet lifetime.** Observe the five-second passive hide and explicit
   reading lock. Check that a hidden result stays hidden on completion and that
   explicit Turn off stops monitoring rather than only concealing the window.
6. **Check clipboard contention.** Copy a second phrase while reading, then use
   Mở đoạn mới; include RAT's own Copy action. Verify one latest pending source,
   no self-trigger loop and no old result overwriting the chosen source.
7. **Inspect real recovery.** Use an actual missing-input or recoverable provider
   failure only if encountered/explicitly scoped. Preserve source and diagnostic
   evidence; check reply/retry and seated error sprite without fake success.
8. **Review translation separately.** Retain a small set of user-relevant phrases
   including the observed idiom error, with actual outputs. Establish limitations
   of the existing specialist MT provider before deciding a remedy; do not
   re-enable LLM automatically or patch a single phrase to mimic quality.
9. **Measure costs before optimizing.** With a known bundle and agreed bounded
   scenario, measure idle/working CPU and memory plus copy-to-result timing.
   Report environment and warm/cold conditions. Package size alone is not RAM
   or energy use; deferred optimization requires a separate scope decision.
10. **Promote only accepted shared pieces.** Summarize Mini findings against the
    speech contract, fix observed issues, and obtain Mini acceptance before
    main UI migration. Contracts, UI projection, deterministic execution and
    actual model-loop evidence must remain separately reported.
