# Antigravity — finish three remaining Workbench UI defects

The main repair works. Independent review reran the complete seven-module suite:
**143 passed, 3 subtests passed in 32.54 s**. File card height, exact opening target,
streaming, stop/late callbacks, local view commands and the shared editor anchor
were verified. Preserve these repairs and the approved design.

Read `AGENTS.md`, the original Workbench handoff, and
`audit/rat_workbench_codex_acceptance_20261015/review.md`. Inspect its
`integrated-empty.png` and `observations.json`. Stay on main, preserve unrelated
work, and do not commit, push, pull, reset, change models or touch research/DocAI.

Fix only these remaining defects:

1. **Empty app displays “90 phút” before any work.** `WorkbenchCanvas` still
   initializes sample minutes `[20,55,15]`. `render_content()` writes their sum
   into the badge for an empty canvas; later presentation/embedded rendering
   shows nonempty text. Reset clears it, but fresh construction does not.
   Remove demonstration data/renderers from production projection paths; put
   them in fixtures. A fresh empty app and reset app must have no duration,
   count or study-plan metadata. Retain badges supplied by actual typed data.

2. **Footer hints have zero width.** Both `input_state_lbl` and `kbd_hint_lbl`
   use horizontal `QSizePolicy.Ignored` alongside a stretch. Their actual widths
   are 0 in every desktop state, and the surviving hint is also 0 in narrow
   mode. Give the hint and keyboard label usable allocations without forcing
   window growth. Preserve the deliberate narrow keyboard-label hiding.
   Check the rendered presentation hint, busy stop hint and character counter,
   including 1700+ characters. `isVisible()` alone cannot prove usability.

3. **Responsive breakpoint uses the wrong width.** `_resize_overlay`,
   `resizeEvent` and `set_expanded` compare outer width to450. With available
   screen geometry `QRect(0,0,490,800)`, normal resize produces outer466 and
   content450 but keeps desktop mode. Apply the <=450 breakpoint to usable
   content width consistently. Avoid circular margin/resize decisions and keep
   the existing editor identity, draft, selection and screen bounds.

Add focused regression coverage for fresh empty metadata, usable footer bounds
and the constrained-screen breakpoint. Do not weaken existing assertions.
Re-run the original seven-module suite (including `test_rat_one_box_ui.py`):

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_rat_magic_ui.py tests/test_rat_one_box_ui.py tests/test_work_context_ui.py tests/test_rat_chat_session.py tests/test_rat_verification_ui.py tests/test_work_context.py tests/test_omnibar.py -q
```

Save new evidence separately; leave previous review/repair artifacts unchanged.
For independent integrated replay, copy/adapt
`audit/rat_workbench_codex_acceptance_20261015/reproduce.py` with a new output
directory. Assert the bad badge is absent, footer visible regions are nonzero,
and content450 uses narrow mode. Keep the verified 48px file card, exact file
target, exactly-once text and 0px editor anchor drift.

Finish the original native smoke with a fresh source process using
`python -m rat.main spotlight`, without rebuilding the index or running a model
campaign. Verify the same input/result composition in a real Cocoa window and
label this evidence separately from integrated offscreen fixture replay. Fix
missing-glyph screenshot setup before using images as visual acceptance; root
independent renders have normal text, so do not assume a product font defect.

Report the exact checks and any remaining limitation. No redesign, new features
or unrelated refactoring. Do not call the work complete based only on standalone
components or passing tests while visible hints still have zero width.
