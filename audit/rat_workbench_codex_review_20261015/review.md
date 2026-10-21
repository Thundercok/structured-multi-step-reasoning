# Workbench native handoff review — 2026-10-15

Verdict: **request changes**. The separated composition and persistent editor are
present, but integrated behavior does not yet meet the approved handoff.
No product code was changed during this review.

## Evidence scope

- Reviewed the two supplied Antigravity transcripts, current UI diff, and frozen
  approved design packet. Both transcripts end in the same implementation report.
- Replayed deterministic events through the actual `OmnibarWindow`, with worker
  startup, search and database mocked. Qt used the offscreen platform; this is
  integrated UI fixture evidence, **not a native Cocoa or model-quality test**.
- Used the repository's existing `README.md` as an actual on-disk file, committed
  its typed `document_file` artifact to the existing artifact store, then replayed
  `AgentResponse` through the real presenter. This is not personal-corpus retrieval.
- `observations.json` and `integrated-*.png` contain the resulting measurements
  and images. `reproduce.py` reproduces them from the repository root.

## Confirmed findings

1. **P1 — compact canvas clips usable results.**
   `rat/ui/omnibar.py:1620–1631` retains the previous layout's height budget:
   composer size hint plus 50, without accounting for the complete new canvas,
   speech and actor geometry. With a completed short calculation, the integrated
   content stack receives **0 px height**. With the committed README artifact,
   its `InlineFileCard` exists and points at the correct file, but its visible
   region is only **473 × 2 px**, versus **574 × 48 px** in expanded mode.
   `isVisible()` alone does not establish a usable result. See
   `integrated-file-compact.png` and `integrated-file-expanded.png`.

2. **P1 — production canvas retains synthetic study-plan metadata.**
   `rat/ui/workbench.py:793–796` initializes the demonstration plan.
   `render_content()` at line 945 exits early for the embedded production stack
   without replacing the title, eyebrow or footer metadata. Empty, calculation,
   file and cancelled states all retain “Buổi học tối nay”; expanded mode adds
   “BẢN NHÁP CỦA BẠN”, “Có thể chỉnh tiếp” and “3 phần” for unrelated work.
   Synthetic calculation, file, note and plan renderers are also present in this
   production module. Use real data or neutral empty/unknown metadata.

3. **P2 — each streaming update duplicates its newest token.**
   `rat/ui/omnibar.py:4015–4021` first projects accumulated `handle['full_text']`
   through `_present_compact_reply`, then appends the same token again through
   `stream_token`. Observed: stream `Xin` → bubble `XinXin`; stream `Xin chào`
   → bubble `Xin chào chào`. The hidden compatibility bubble is duplicated too.

4. **P2 — new visible state is not reconciled on stop/reset/completion.**
   `rat/ui/omnibar.py:3426` sets the new lane phase to `working`; no other call
   updates that phase. `_cancel_assistant` updates the old chat card, but leaves
   the new speech bubble showing its previous partial answer and the new footer
   saying “Gõ tiếp · Esc để dừng”. Initial visible speech is blank; `_reset_chat`
   resets only the hidden old speech bubble. Derive all these projections from
   existing execution/session state and retain generation guards.

5. **P2 — integrated narrow layout is unreachable.**
   `rat/ui/omnibar.py:1355–1357` calls both new components with only `expanded`,
   leaving `narrow=False`. `resizeEvent` does not reconcile this. The manual
   narrow specimen directly sets `narrow=True`, bypassing the integration.
   The integrated resize probe returned to the default 620 px overlay; a real
   narrow-display test remains required. Do not cite this as successful 440 px
   integration coverage.

6. **P2 — preserving window bottom does not preserve composer position.**
   Full focused suite: **142 passed, 1 failed, 3 subtests passed** in 32.87 s.
   Failure: `tests/test_rat_one_box_ui.py:209`,
   `test_mode_change_keeps_the_composer_anchor_when_space_allows`.
   The editor moved from screen y=682 to y=676 while expanding. The integrated
   probe independently measured its bottom moving from y=715 to y=709, while
   retaining draft, selection and editor identity. The same existing test with
   `HEAD:rat/ui/omnibar.py` loaded from a temporary file **passed** (2.79 s),
   isolating a regression without changing the working tree.

## Additional inspection concern

The actor paints compact/narrow artwork at `sprite_y = -1 + dy` and hops upward
another 7 px (`rat/ui/workbench.py:360–395`). Extra widget height only reserves
space below. Verify alpha/paint bounds throughout motion before claiming the
actor is unclipped. This review did not capture a deterministic animated frame.

The initial suspicion about visible default action buttons was not reproduced:
the integrated probe showed both speech action buttons invisible. It is not a
confirmed finding and should not drive a product change by itself.

## Exact focused suite

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_rat_magic_ui.py tests/test_rat_one_box_ui.py tests/test_work_context_ui.py tests/test_rat_chat_session.py tests/test_rat_verification_ui.py tests/test_work_context.py tests/test_omnibar.py -q
```

The supplied report omitted `test_rat_one_box_ui.py` and combined UI test counts
with unrelated research checks. Its “zero regressions” conclusion is unsupported.
No research campaign, model inference, network request or Git publication was
performed by this review. The baseline check substitutes only the HEAD Omnibar
module, not an entirely clean historical checkout.
