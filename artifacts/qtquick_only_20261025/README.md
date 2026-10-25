# Qt Quick-only runtime migration — 2026-10-25

Production Python under rat/ no longer imports QtWidgets. Windows use QML/Qt Quick;
macOS status item/menu use AppKit, with QtGui QAction as the action model.
QGuiApplication owns the event loop; QAbstractFileIconProvider supplies file icons.
Packaging spec excludes PyQt6.QtWidgets and retired window hidden imports. No new
standalone bundle was built or installed in this session.

## Evidence

- boundary-regression.txt: 23 passed (runtime import guard, lifecycle, packaging).
- qml-regression.txt: 40 passed (PDF, answer rendering, clipboard and unified flow).
- research-regression.txt: 29 passed; no research scope/gate change.
- native-menu-smoke.json: actual Cocoa status item and QAction bridge, no QtWidgets.
- live/startup.log and live2/startup.log: Cocoa, GraphicsApi.MetalRhi, widgets_loaded=false.
- live/exit.json: observed first isolated session exit 0, clean=true, widgets_loaded=false.
- live2/model-calls.json: one recorded real qwen3:4b-instruct call, including actual
  messages and public response. No canned assistant response or model download.
- pdf-provenance.json: genuine arXiv PDF origin and SHA-256.
- live2/screenshots/03-live-answer-full.png and 04-live-answer-compact.png: actual
  production UI operated through native accessibility/keyboard interactions.
- live2/screenshots/05-source-page-gap.png: retained observed page-source display gap.
- final-source-hashes.json: final source snapshot, not a claim that every earlier
  diagnostic was run against this exact snapshot. Other workspace edits were preserved.

## Limits / failures retained

Initial .venv Qt imports inside sandbox aborted on CPU feature neon; Qt tests ran
outside sandbox. An initial combined run segfaulted between GUI modules; the GUI
test application lifetime was fixed. A later broad run stalled and was stopped;
the focused successful suites above are the final verification scope. QtTest itself
imports QtWidgets; the production subprocess import guard and Cocoa live sessions
run without QtTest and do not load QtWidgets.

Earlier broader runs also exposed Reading/auditor/Finder failures; their logs are
retained, not counted as passing. Workspace domain/lifecycle sources changed during
the session; this migration does not certify all domain tests or Agent integration.
Native notification delivery depends on macOS policy; messages remain in status tooltip
when notification delivery is unavailable. Non-macOS status menu is not implemented;
Qt Quick Desk remains the app surface there, with a logged warning rather than a
QtWidgets tray fallback.

The live title answer was BEST-Route: Adaptive LLM Routing with Test-Time Optimal
Compute. Its verification remained UNKNOWN. The page-source view showed no excerpt,
although answer evidence included the extracted text; the failure screenshot is
retained. live2 did not produce an exit.json; no clean-quit claim is made for it.
No idle CPU, 120 Hz, memory saving, general model quality or Stage 0 claim is made.
All-business-functions-through-Agent remains the separate execution redesign task.
