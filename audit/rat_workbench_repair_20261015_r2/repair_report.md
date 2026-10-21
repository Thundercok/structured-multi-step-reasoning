# RAT Workbench Repair Verification Report (Round 2)
**Date**: 2026-10-16  
**Baseline Review**: `audit/rat_workbench_codex_acceptance_20261015/review.md`  
**Execution Context**: Scoped on `main`, zero repository mutations, pure native PyQt6 implementation.

---

## 1. Summary of Verified Fixes

### A. Empty State Synthetic Metadata Elimination
- **Defect**: Initial empty launch of `WorkbenchCanvas` still displayed a synthetic `90 phút` duration badge because sample minutes `[20, 55, 15]` were initialized in production and `render_content()` computed their sum.
- **Resolution**:
  - Removed all hardcoded synthetic plan/duration arrays from production initialization in `WorkbenchCanvas.__init__()`.
  - Initialized `minutes = []`, `plan_rows = []`, clean title `"Không gian làm việc"`, with `duration_badge`, `eyebrow_lbl`, `status_lbl`, `context_lbl`, and `foot_row` hidden.
  - Reset (`reset_work()`) preserves this clean empty state without synthetic metadata.
  - Test fixture plans are exclusively populated via dedicated `set_fixture_plan()` method for tests/specimens.
- **Evidence**:
  - Offscreen Replay: `observations.json['integrated-empty']['badge']`: `{text: "", visible: false}`.
  - Native Cocoa Smoke: `native_cocoa_smoke.json['canvas']`: `{badge_text: "", badge_visible: false}`.
  - Visual verification: `integrated-empty.png` and `native-cocoa-spotlight.png` confirm zero duration badge.

### B. Usable Footer Bounds Across All States
- **Defect**: `input_state_lbl` and `kbd_hint_lbl` used horizontal `QSizePolicy.Policy.Ignored` alongside a layout stretch, collapsing their widths to 0 px across compact, expanded, working, and narrow states, hiding presentation hints, character counts, and keyboard shortcuts.
- **Resolution**:
  - Changed both footer labels to `QSizePolicy.Policy.Preferred`.
  - Placed `f_layout.addStretch(1)` between the left input state hint and the right keyboard hint label, allowing both labels to naturalize to their content width without forcing window expansion.
  - Preserved deliberate narrow-mode hiding of `kbd_hint_lbl`.
- **Evidence**:
  - Offscreen Replay:
    - Desktop compact: `input_state_lbl` width = 94 px, `kbd_hint_lbl` width = 34 px (visible = true).
    - Working state: `input_state_lbl` width = 117 px (`"Gõ tiếp · Esc để dừng"`).
    - 1750 char counter: `width` = 99 px (`"1750 / 2.000 ký tự"`).
    - Narrow mode (440 px): `input_state_lbl` width = 94 px, `kbd_hint_lbl` hidden as intended.
  - Native Cocoa Smoke:
    - `input_state_lbl`: width = 94 px (`"Nói “xem chi tiết”"`).
    - `kbd_hint_lbl`: width = 34 px (`"↵ gửi"`).

### C. Content-Width Responsive Breakpoint
- **Defect**: Responsive breakpoint compared outer window width to 450 px instead of usable content width. On constrained screens (e.g. `QRect(0, 0, 490, 800)`), the window resized to outer 466 px with content 450 px, failing to trigger narrow mode reflow.
- **Resolution**:
  - Introduced `_is_narrow(outer_w)` computing `(outer_w - 16) <= 450` (matching the 520 px desktop / 450 px narrow content width specification).
  - Applied consistently across `_resize_overlay()`, `resizeEvent()`, and `set_expanded()`.
  - Content width <= 450 px correctly switches to the 80 px actor sprite, full-width user lane, and compact footers.
- **Evidence**:
  - Regression test `test_responsive_breakpoint_uses_content_width_on_constrained_screens` passes.
  - Constrained screen probe (outer 466 px, content 450 px) yields `is_narrow: true`, `actor_w: 80`.

---

## 2. Test Suite Status

Executed full 7-module test suite:
```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_rat_magic_ui.py tests/test_rat_one_box_ui.py tests/test_work_context_ui.py tests/test_rat_chat_session.py tests/test_rat_verification_ui.py tests/test_work_context.py tests/test_omnibar.py -q
```
**Results**:
- **146 passed, 3 subtests passed in 32.82s** (0 failures, 0 regressions).

---

## 3. Native Cocoa Smoke Verification

Executed fresh source process using `python -m rat.main spotlight` with real macOS Cocoa platform:
- **Command**: `PYTHONPATH="scratch/smoke:$PYTHONPATH" RAT_NATIVE_SMOKE=1 .venv/bin/python -m rat.main spotlight`
- **Platform**: `cocoa` (native macOS AppKit Window Server)
- **Geometry**: Window = 620 × 254 px, Canvas = 520 × 90 px, Dialogue = 520 × 132 px, Actor = 112 × 120 px (`actor_w = 104`)
- **Metadata**: Badge is hidden (`badge_text: ""`, `badge_visible: false`)
- **Footers**: `input_state_lbl` width = 94 px, `kbd_hint_lbl` width = 34 px
- **Visual Artifact**: `native-cocoa-spotlight.png` confirms crystal-clear typography, San Francisco font family rendering, proper Vietnamese diacritics, and approved separated-compartment composition.
