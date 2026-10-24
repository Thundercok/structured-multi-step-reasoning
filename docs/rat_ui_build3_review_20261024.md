# Build 2026.10.24.3 review — 2026-10-24

Reviewed the pasted Antigravity handoff against current repository source.
No Antigravity/computer interaction, model calls or product source edits in
this review. Working tree includes unrelated research changes; left intact.

## Confirmed issue: collapsed suggestions retain a hidden selected result (P2)

`rat/ui/quick/PDFDesk.qml:1018` toggles showAllFinderHits but does not clear an
index outside visibleFinderHits. Steps: search with five hits, expand, select
index 4, collapse. Only three cards remain, selectedFinderIndex stays 4. The
action bar and Enter handlers still use all finderHits, so the hidden result
remains actionable. Reset or clamp selection when the visible list shrinks,
and cover collapse with keyboard/action-bar regression.

Reproduced using the existing software QML test plus a temporary assertion:
selectedFinderIndex=4, click collapse, assert index<3. Assertion failed (4<3).
Probe retained at
`work/rat_ui_iteration_sessions_20261024/build3-review/test_collapse_probe.py`.
Synthetic contract probe only; not live UI/model acceptance.

## Acceptance evidence remains incomplete

Manifests for 14-search-suggestions and 16-recording-software both contain
only view=none startup captures and calls=[]. Neither demonstrates the new
suggestion cards, see-more/collapse, opening a real hit, or draft restoration
through desktop input. QTest is useful regression evidence, not user-style
acceptance under AGENTS.md.

`scripts/record_ui.py:render_screenshots` generates a slideshow from PNG files,
not a desktop interaction recording. The MP4/GIF from runs 10/13 contain older
build evidence; do not describe them as live walkthroughs of Build .3. Keep
them, but distinguish screenshot montage from actual desktop-recording.mov.

## Validation

Re-ran the exact reported five-file suite: 27 passed in 13.52s. Initial
sandbox invocation aborted importing Qt; the same command in an approved
native environment passed. Additional collapse probe: 1 failed in 12.82s,
as described above. No broad research tests or experiments were needed.

Next: fix hidden selection with a focused regression, then obtain desktop
acceptance using real app/file hits with cap=0. No launcher expansion. Review
verdict: request changes; do not label Build .3 accepted yet.
