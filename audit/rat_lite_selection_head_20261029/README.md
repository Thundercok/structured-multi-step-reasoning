# RAT Lite .25 — requested package/open for manual trial

2026-10-29. User explicitly requested building .25 to test personally. Source
commit 3a6abb9e. Build completed exit0 using tools/build_rat_mini_app.sh with
existing /private/tmp/rat-mini-offline-mt-deps. Full build.log remains local
(ignored by Git). The script includes native helper compilation and ad-hoc signing.

- App: dist/rat-lite-20261029-selection-head/RAT Mini.app
- ZIP: dist/rat-lite-20261029-selection-head/RAT Mini.zip
- Bundle metadata read back: BUILD20261029.25, vn.rat.mini, executable RAT Mini.
- Graceful Quit for .24 returned AppleScript -128; subsequent process inventory
  confirmed old PID39464 absent. No forced termination was used.
- Exact .25 bundle launched through open -n with --minimal, exit0. PID46807 was
  observed at the new path and remained running on a later startup check.
- Existing runtime last-hotkey.json then identified protocol SELECT1, stage
  ready, BUILD20261029.25, PID46807. This establishes helper readiness, not a
  physical keypress, selection capture or translation result.

No automated tests, smoke, UI tours, screenshots, selection reads, model calls or
translation acceptance were performed. No Accessibility permission was changed.
The user operates the candidate. Source/limits: docs/contracts/rat_lite_selected_text.md.
The continuous typing/reading/expansion repair remains pending. Main/M3/Stage0
gates are unchanged. Existing unrelated audit edits and removed old runtime lock
remain outside these commits.
