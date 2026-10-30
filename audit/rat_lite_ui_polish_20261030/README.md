# RAT Lite UI polish — 2026-10-30

User chose a compact, usable UI retaining the rat as a visual accent. The input now includes the existing rat asset, Finder results use distinguishable selectable cards, and opening an already-running instance requests the composer. UI continues to submit through the existing controller and shared service.

Source UI was inspected live: the input and rat rendered, and a real search for `project_scope.md` returned eight results, displayed as separate cards. `tests/test_rat_lite_visible_panel.py tests/test_goal_routing.py` passed (4 tests). Source mode lacked the native hotkey helper, so the physical shortcut and packaged-app permissions were not checked in this pass. No live model-driven Agent run is claimed. The prior packaged-app evidence and other test failures remain in `audit/rat_lite_live_20261030/`.
