# RAT Lite .26 — requested preview package/open

2026-10-29. User requested seeing the update, authorizing packaging and opening
the real candidate. Source commit52cfdafb, BUILD20261029.26. Build script exited0
using existing /private/tmp/rat-mini-offline-mt-deps and ad-hoc signed the app.
Full build.log is retained locally and ignored by Git.

- App: dist/rat-lite-20261029-continuous-panel/RAT Mini.app
- ZIP: dist/rat-lite-20261029-continuous-panel/RAT Mini.zip
- Info.plist read back as20261029.26, vn.rat.mini, executable RAT Mini.
- No older RAT app was found running before opening; no old app was terminated.
- Exact new bundle launched with open -n and --minimal, exit0.
- App PID63687 observed at the .26 path; native helper PID63717 had parent63687
  and used the new bundle's Frameworks/rat/bin/rat-hotkey path.
- A later startup read observed both processes still alive. The app's metadata
  identified .26/PID63687/helper63717, helper_state registered, stages starting →
  started → ready. This is startup evidence, not a physical keypress result or
  evidence of sustained helper reliability.

No automated tests, smoke, UI tour, screenshot, selection read or translation
flow was performed by the agent. Permission was not changed. Visual layout,
source-app compatibility, key delivery and execution remain for the user's
manual observation. No main/M3/Stage0 gate was advanced.

Source details: docs/rat_lite_continuous_panel_handoff_20261029.md.
