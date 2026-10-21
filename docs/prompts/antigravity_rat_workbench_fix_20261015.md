# Antigravity — repair integrated RAT Workbench before declaring completion

Continue the native PyQt6 implementation already in this working tree. Preserve
the user-approved design: separate compact work canvas, prominent mouse outside
it, RAT speech, green user speech input below. The user approved its appearance;
this round repairs integration and polish without redesigning the product.

## Read first

1. `AGENTS.md` and `docs/prompts/antigravity_rat_workbench_20261015.md`.
   The original scope, privacy, native acceptance and Git constraints still apply.
2. `audit/rat_workbench_codex_review_20261015/review.md` and `observations.json`.
3. Inspect `integrated-empty.png`, `integrated-file-compact.png`,
   `integrated-file-expanded.png`, and `integrated-cancelled.png` in that folder.
4. Revisit `docs/design/rat_workbench_20261015/approved-desktop.png`.
   Keep the frozen reference packet unchanged.

Use the current source and take scoped hashes before editing. The existing
implementation is in `rat/ui/workbench.py` and `rat/ui/omnibar.py`. Preserve
unrelated changes and recovery material. Work on `main`; no commit, push, pull,
reset, new branch or repository migration is authorized. Do not touch research,
model settings, runtime routing, DocAI integration, saved user data or indexing.

## Verified failures to fix

### A. Make actual results accessible in the compact canvas — first priority

The current compact height calculation still budgets the old layout. In the
actual integrated window a completed calculation gives `content_stack` height
0; a real README file card exists but exposes only 2 px of its height. Standalone
component specimens hide this failure.

Calculate height from the new layout's actual width-dependent requirements:
canvas chrome, useful current content, speech, composer, footer, gaps, margins
and the actor's paint space. Reserve a usable result viewport before capping to
available screen height. Use bounded internal scrolling when needed. Keep the
default approximately 520 logical px wide, fit a short result naturally, and
grow upward from the editor. Do not solve clipping by always expanding, adding
huge padding, increasing the default width or requiring an extra user command
before any file can be reached.

Replay a committed typed file artifact backed by a real harmless file through
the existing store/response/presenter path. In compact mode its visible region
must contain the whole usable file row or a deliberately usable scroll viewport.
Click/Enter must target that exact observed file. `isVisible()` on a widget whose
ancestors clip it to 2 px is insufficient. Keep trusted paths, revision ownership,
deduplication and no-auto-open behavior intact.

### B. Remove demonstration content from production projections

An empty app and unrelated file/math answers currently sit under “Buổi học tối
nay”. Expanded view also claims “3 phần” and “Có thể chỉnh tiếp”.
`WorkbenchCanvas.render_content()` returns early for `embedded_stack` before
replacing these demo values.

Move fixed sample plans/calculations/file names and numeric examples into test
or screenshot fixtures. Production widgets must accept existing real typed data
or neutral metadata when the current work has no title/duration/count. Hide
unavailable fields. Do not infer fake durations or manufacture a plan from prose.
Reuse the current artifact/session state; do not add a second task store or
redesign the backend. Initialize the visible RAT bubble with a short welcome.

### C. Project streaming text once, and reconcile execution state everywhere

`_on_reasoning_token()` first passes accumulated text to
`_present_compact_reply()` and then appends the same token again. Verified:
`Xin` → `XinXin`; `Xin chào` → `Xin chào chào`.
Choose one projection path for each bubble. Keep the canonical text untouched.

The new user lane is set to `working` at submission and never leaves it. Stop
updates the existing history card but leaves the new bubble showing a partial
answer, and the footer still offers to stop an execution that has ended. Reset
only resets the hidden old bubble. Wire complete, clarification, error, stop,
reset and reopen to truthful visible states using the existing guards. Late
callbacks must not change the bubble, title, footer, files or actor after stop.
Preserve typed drafts and the same editor. Do not implement fake progress timers
or claim the blocking HTTP request was terminated when only UI ownership stopped.

### D. Wire responsive mode through the real window

The standalone specimen sets `narrow=True`, but Omnibar never passes this flag.
Derive it from actual available content width at initial show, resize, mode
change and screen change. At <=450 logical px of content, use the approved 80px
mouse and full-width user lane below; desktop keeps 104px mouse and aligned
bubble edges. Avoid resize loops that restore 620 px after a narrow allocation.
Also update styling when only `narrow` changes: `WorkbenchUserBubble` currently
guards solely on `expanded`, so its narrow typography/padding can remain stale.

### E. Preserve the editor's on-screen anchor across presentation changes

The existing test
`test_rat_one_box_ui.py::test_mode_change_keeps_the_composer_anchor_when_space_allows`
fails on the patch and passes with the HEAD Omnibar module. A fixture independently
measured the editor bottom moving upward by 6px on expansion. Keeping the outer
window bottom fixed is insufficient when expanded labels/footer/padding change.

Anchor the actual editor in global logical coordinates when screen room allows,
while retaining its identity, draft, selection, focus and the existing per-mode
reading position. Use available screen geometry, including negative origins.
Handle constrained displays explicitly; do not delete the existing test or
loosen its assertions to bless the regression.

### F. Finish the small visual details on the integrated window

Check that input hints, keyboard hint and character counter receive usable widths
and remain visible; they disappear in the integrated captures. Measure layout
rectangles rather than relying on `isVisible()` alone. Ensure font changes follow
light/dark and narrow modes. Keep default buttons hidden; show optional diagnostic
controls only when `RAT_DEBUG_UI=1`. Preserve text selection/copy access.

Verify the actor's full painted alpha bounds during the hop. Compact/narrow
currently start at y=-1 and hop another 7px upward; extra height below does not
protect the head. Reserve top paint space without inflating the visible default
composition. Respect reduced motion and hidden-window timer suspension. Restore
meaningful motion/timer checks for the new actor instead of removing old checks
because their monkeypatch target changed.

## Verification and deliverables

Add focused integration regressions for A–E. Cover actual visible/clipped bounds,
not only parent existence. Include exactly-once streamed text, truthful stop and
reset, stale callbacks, local view commands during work with no model/task change,
same editor state, and a file card opening the observed path. Adapt geometry
assertions only when the approved design really supersedes them.

Run the complete relevant suite, including the previously omitted file:

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_rat_magic_ui.py tests/test_rat_one_box_ui.py tests/test_work_context_ui.py tests/test_rat_chat_session.py tests/test_rat_verification_ui.py tests/test_work_context.py tests/test_omnibar.py -q
```

Independent reviewed result before repairs: **142 passed, 1 failed, 3 subtests
passed**. The failing anchor test with the HEAD Omnibar module passed separately.
Do not run unrelated research suites or use their counts as UI acceptance.

Reproduce the review probe from the repository root:

```sh
QT_QPA_PLATFORM=offscreen PYTHONPATH=. .venv/bin/python audit/rat_workbench_codex_review_20261015/reproduce.py
```

The probe intentionally uses deterministic response replay and the repository's
README. Its window is integrated Qt offscreen, not Cocoa and not retrieval/model
quality evidence. Preserve the original review evidence; copy/adapt the probe
to a new repair evidence directory before rerunning it.

After tests pass, launch a fresh real native process from edited source
(`python -m rat.main spotlight`) and perform the original native smoke. Verify
compact/detail, actual file delivery, light/dark, Vietnamese multiline input,
busy draft, stop/late callback, reset, narrow screen and reduced motion. Clearly
label fixture replay, component-only render, integrated offscreen and Cocoa
evidence. Never call standalone component captures “live application” validation.

Finish with changed files, exact test output, integrated/native before/after
captures, measured editor/result bounds, and any honest remaining limitation.
No new design exploration or model campaign. Do not declare success while the
actual file result is clipped or production metadata is still synthetic.
