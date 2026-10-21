# Independent review of Workbench repairs — 2026-10-15

The main repairs are verified. Three smaller UI defects remain; the supplied
claim that every reviewed issue is resolved is premature. No product source
was modified during this review.

## Independently verified

Focused suite: **143 passed, 3 subtests passed in 32.54 s**.

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_rat_magic_ui.py tests/test_rat_one_box_ui.py tests/test_work_context_ui.py tests/test_rat_chat_session.py tests/test_rat_verification_ui.py tests/test_work_context.py tests/test_omnibar.py -q
```

The integrated offscreen probe independently confirms:

- Actual repository README artifact: compact file region **473 × 48 px**,
  expanded **574 × 48 px**. Enter and click each target the exact observed file
  (opening function mocked; nothing was opened automatically).
- Streaming `Xin` then ` chào` produces exactly `Xin` then `Xin chào`.
- Editor anchor 714 → 714, same widget, draft and selection preserved.
- Local detail command during work preserves handle, generation and unsent draft.
- Stop changes the visible bubble; late progress/token/response callbacks leave
  the visible bubble, canvas title and lane phase unchanged.
- Reset restores a neutral canvas and welcome, without the previous user query.
- Narrow fixture at 440 outer pixels activates its intended reflow.

## Remaining findings

1. **P2 — initial empty app still shows a synthetic “90 phút” badge.**
   `rat/ui/workbench.py:1033` writes `sum(self.minutes)` into the badge even for
   `kind='empty'`. Production still initializes `[20,55,15]` at line 799.
   The embedded rendering and presentation paths at lines 1021 and 926 show
   any nonempty badge text again. `integrated-empty.png` and
   `observations.json['integrated-empty']['badge']` confirm `{text:'90 phút',
   visible:true}` before any request. Reset clears it, but first launch does not.
   Keep demonstration values in fixtures and initialize production metadata from
   actual data or empty values.

2. **P2 — presentation and keyboard hints are still invisible.**
   `rat/ui/workbench.py:1231` and 1238 give both footer labels horizontal
   `QSizePolicy.Ignored`; the intervening stretch receives their space. Both
   labels measure **0 px width** in compact, expanded, working, cancelled and
   reset states. In narrow mode the keyboard hint is deliberately hidden, but
   the remaining presentation hint still has zero width. This also hides the
   character counter and stop hint. The report's claim that footer hints are
   repaired is not supported by actual rendered bounds.

3. **P2 — narrow breakpoint uses outer window width, not content width.**
   `rat/ui/omnibar.py:1224`, 1292 and 1367 compare the outer width to 450.
   A separate geometry probe with available screen bounds `QRect(0,0,490,800)`
   and the normal `_resize_overlay(620, ...)` yields outer width466, canvas450,
   `narrow=False`, actor width112. At this content width the accepted design
   requires narrow reflow and the 80px sprite. Use one consistent content-width
   calculation across resizing, screen constraints and mode transitions.

## Evidence limits

`reproduce.py`, `observations.json` and `integrated-*.png` are integrated Qt
offscreen fixture evidence; no live model or personal-corpus retrieval occurred.
This review did not launch the normal application entry point or a Cocoa smoke.
The Antigravity screenshots have missing-glyph artifacts, but independent root
captures render text normally, so no product font defect is asserted.

The actor's hop bounds were checked independently and fit; no remaining actor
clipping finding is asserted. The three remaining findings do not negate the
verified file, streaming, cancellation and anchor repairs.
