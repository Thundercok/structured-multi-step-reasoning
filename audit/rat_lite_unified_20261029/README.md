# RAT Lite .24 — package and manual-trial launch

2026-10-29. User accepted the proposed next step: build .24 and open it for
their own trial. No automated test, smoke, UI tour, screenshot or conversation
acceptance was run.

- Source: ca73e115; runtime/bundle BUILD `20261029.24`.
- Build completed with exit 0 using `tools/build_rat_mini_app.sh` and existing
  `/private/tmp/rat-mini-offline-mt-deps`. Full packaging output: `build.log`.
- App: `dist/rat-lite-20261029-unified/RAT Mini.app`.
- ZIP: `dist/rat-lite-20261029-unified/RAT Mini.zip`.
- Bundle metadata read back as `vn.rat.mini`, executable `RAT Mini`, .24.
  Build script ad-hoc signs; no notarization claim.
- Existing QA20 PID7562 was observed before launch. A graceful AppleScript Quit
  returned -128 (user cancelled); no forced termination followed. Subsequent
  process inventory no longer showed QA20.
- `open -n` on the exact .24 app path with `--minimal` returned exit 0.
  PID39464 was observed running from that path and remained at a later startup
  read. This confirms process startup, not rendered UI quality or acceptance.

The user operates the app next. Unified source limits and planned observations:
`docs/rat_lite_unified_interaction_handoff_20261029.md`. No model-quality,
main-integration, recipient M3 or Stage 0 gate was advanced.
