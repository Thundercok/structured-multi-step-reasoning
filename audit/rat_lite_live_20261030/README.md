# RAT Lite live check — 2026-10-30

Build `20261030.4`, source commit `8fe8050b`, app in `dist/rat-lite-verified`. Real UI and actual tools, no canned assistant outputs.

- The previously shipped app rendered a one-pixel-high window. A visibility/height cycle in MiniDesk was removed. Source UI then visibly showed the Hello sheet and the main input.
- On the packaged app, `Dịch: The little rat is reading a book.` produced `Con chuột nhỏ đang đọc sách.` through `translate_text`.
- On the packaged app, `Tìm file project_scope.md` produced eight hits including this repository's actual `docs/project_scope.md`. Selecting that hit enabled Mở file and invoked the open operation; user application handling the file was not independently inspected.
- The source UI originally clipped Finder results; after enlarging the results surface, the list displayed multiple readable entries and selection worked. The packaged version also displayed selectable entries.
- The native hotkey helper registered for this build. In a disposable TextEdit document, the computer-use simulated Option–Shift–Space inserted a nonbreaking space instead of triggering the helper; the journal contained no invocation. This does not establish the result of a physical keypress. Accessibility permission for this ad-hoc signed build is not established, and selected-text capture remains unverified.
- `tests/test_rat_lite_visible_panel.py`, `tests/test_goal_routing.py`, `tests/test_rat_mini_tools.py`: 21 passed, 1 failed. The failing composition assertion expects the old capability set and does not include the existing source_analysis capability. It was not changed to hide the failure.
- Earlier pre-fix combined UI suite: 10 passed, 6 failed. Some refer to removed layout components or old interaction expectations; they are not acceptance evidence and were not all diagnosed.

The UI observations do not establish a live model-driven Agent loop, recipient-machine acceptance, or research Stage 0. Finder and translation continue through the shared service/tool contracts.
