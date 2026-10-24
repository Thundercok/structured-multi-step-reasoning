# Build .9 review — 2026-10-24

Reviewed current source and handoff through builds .4–.9; no Antigravity or
desktop interaction, model calls, or product edits during this review.

The build .3 hidden-selection issue has explicit collapse guards and regression
coverage now. Other substantial changes: Enter sends chat/PDF QA; PDF keyword
search moved to a dedicated popup / Cmd-F; page snapshots; answer formatting;
latent Finder suggestions that preserve an active completed Answer.

## P2: returning from suggestions hides cancelled/empty Answer

`rat/ui/quick_pdf_controller.py:1003` computes the return view from the truthiness
of `_last_assistant_answer`, ignoring `_pre_finder_view`. With a cancelled turn
and empty answer, opening suggestions saves prior view=answer, but dismissing
returns to none and replaces its status with the ready message. The cancelled
conversation record remains; the problem is loss of the current workbench/status.

A headless controller probe reproduced: before=answer/cancelled; open=True;
after=none/cancelled; recorded prior view=answer. No model or live acceptance
fixture was used. Restore actual prior view/mode, including cancelled/failed
Answer states, and cover empty-answer cases. Related truthiness-based return
branches for zero/cleared search queries need the same consideration.

## Tests and acceptance limits

The broad eight-file suite did not pass locally: it printed failures in the
Answer group then segfaulted (exit 139). Isolated
`test_quick_answer_presentation.py -q -x --tb=short` yielded 8 passed / 1 failed:
`test_answer_copy_and_source_page_journey[520-False]` cannot click copyCitation
because it is hidden while the workbench is folded. The test currently expects
full mode after completing its fixture; production preserves min mode. Align
test setup with intended mode before diagnosing this as a product copy failure.
Do not describe the full eight-file suite as green from this review.

Isolated seven-file PDF/Finder/observer/selected-document suite subsequently
passed: 49 passed in 18.03s. No further test expansion or model runs performed.

Run 27 manifest: calls=[], closed=true, QML warnings=[], reload preserved=true,
seven captures with clear_frame=true. Viewed r01-04-finder-full.png: real app
suggestions and Build .9 render clearly. This supports the rendered state;
it does not establish a real-model chat. The handoff correctly labels Answer
light/dark images as software test outputs and walkthroughs as PNG montages.

Verdict: previous P2 resolved; request changes for empty-answer return state
and reconcile the failing Answer tests. Preserve research gates and the scoped
file/app assistance backlog; no launcher expansion.
