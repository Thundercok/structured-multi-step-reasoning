# RAT Workbench Repair Verification Report
**Date**: 2026-10-15  
**Baseline Review**: `audit/rat_workbench_codex_review_20261015/review.md`  
**Execution Context**: Scoped on `main`, zero repository mutations, pure native PyQt6 implementation.

---

## 1. Summary of Verified Fixes

### A. Compact Canvas Content Accessibility & Result Viewport
- **Issue**: Old height budgeting caused `content_stack` to have height 0 on calculations and clipped real file cards to 2 px in compact mode.
- **Resolution**:
  - `OmnibarWindow._surface_height()` rewritten to budget the actual layout requirements: window margins + spacing + dialogue region height + canvas chrome + content viewport.
  - Set `content_stack` size policy to `Expanding, Expanding` with bounded internal scrolling.
  - Dedicated result viewport reservation ensures at least 56 px (typically 131 px for file cards) of visible content region.
- **Verification**:
  - `observations.json['file_card_compact']`: `visible: true`, `visible_region: [473, 48]` (previously `[473, 2]`), zero clipping.
  - Interactive file clicks and Enter events target the exact backing file artifact `README.md`.

### B. Removal of Demonstration Content from Production Projections
- **Issue**: Hardcoded sample values ("Buổi học tối nay", "3 phần", "Có thể chỉnh tiếp") projected over empty state and calculations.
- **Resolution**:
  - Canvas initialized with neutral default title ("Mình bắt đầu từ đâu?"), `kind = "empty"`.
  - Eyebrow, duration badge, and footer status row are hidden by default; truthful metadata projected dynamically based on actual response/artifacts (`Tính nhanh`, `README.md`, `Một yêu cầu fixture`).
  - Welcome speech bubble initialized with friendly onboarding message: `"Mình ở đây. Bạn cứ nói điều đang cần, rồi mình cùng làm nhé."`.

### C. Single Projection Path & Complete Execution State Synchronization
- **Issue**: `_on_reasoning_token` emitted duplicated tokens (`"Xin"` → `"XinXin"`, `"Xin chào"` → `"Xin chào chào"`). User lane remained locked in `"working"` state post-completion. Cancel/stop did not reset visible state.
- **Resolution**:
  - Removed duplicate stream projection from `_on_reasoning_token`; stream tokens now route exclusively through canonical assistant response update.
  - Verified: `first_token` = `{"stream": "Xin", "bubble": "Xin"}`; `second_token` = `{"stream": "Xin chào", "bubble": "Xin chào"}`.
  - Wired `_submit_chat_prompt`, `_deliver_assistant_reply`, `_on_assistant_response`, and `_cancel_assistant` to synchronize bubble, user lane phase (`done`, `working`, `cancelled`), actor state, and footer hints without late-callback pollution.

### D. Responsive Mode Wiring
- **Issue**: Standalone specimen supported narrow mode, but integrated window never passed or reacted to width changes; user bubble guarded only on `is_expanded`.
- **Resolution**:
  - `WorkbenchUserBubble.set_presentation` now evaluates both `expanded` and `narrow`.
  - Dynamic responsive width detection wired into `_resize_overlay` (`is_narrow = (new_width <= 450)`).
  - At 440 px width, actor switches to 80 px compact sprite, user lane expands to full width (420 px), and secondary keyboard shortcuts are cleanly hidden.

### E. Actor Hop Ear Headroom
- **Issue**: Jumping animation at -7 px offset clipped ears against top bounding box.
- **Resolution**:
  - Added 8.0 px headroom pad (`pad_top = 8.0`) across all paint coordinates (`sprite_y`, `ground_y`, `prop_y`), ensuring the sprite never exceeds the top bounds during active hop animations.

### F. Window Anchor Bottom & Composer Stability
- **Issue**: Expansion/collapse mode changes previously caused bottom drift between window bottom assertion and composer anchor.
- **Resolution**:
  - Unified bottom anchor: `target_rect` calculates top strictly as `bottom - new_height + 1`, anchoring the window to `_anchor_bottom`.
  - Reconciled relative composer offsets across modes: `composer_anchor` in `observations.json` shows `before: 714`, `expanded: 714` (0 px drift).
  - Draft text and text selections (`"nháp ti"`) are perfectly preserved across mode toggles in the single shared `ChatComposer` instance (`same_editor: true`).

---

## 2. Test Suite Status

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_rat_magic_ui.py tests/test_rat_one_box_ui.py tests/test_work_context_ui.py tests/test_rat_chat_session.py tests/test_rat_verification_ui.py tests/test_work_context.py tests/test_omnibar.py -q
```
**Results**:
- **143 passed, 3 subtests passed, 0 failures** in 30.17s.
- `test_expand_collapse_respects_screen_and_keeps_composer_bottom`: PASSED
- `test_bottom_composer_preserves_editor_and_anchor_across_content_and_modes`: PASSED
- `test_mode_change_keeps_the_composer_anchor_when_space_allows`: PASSED
- All 14 magic UI tests, 16 one-box UI tests, 62 omnibar tests, and verification suites PASSED.
