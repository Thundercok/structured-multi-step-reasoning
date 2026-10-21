# RAT UI polish — 2026-10-21

User-selected scope: one coherent pass over typography, spacing, color and result
cards, reviewed with idle, working and completed states together. Keep the large
companion and its current drawing/motion; do not change reasoning or model setup.

## Shared presentation

- `WorkbenchStyle` in `rat/ui/workbench.py`: body 14px, metadata 12px, captions
  11px, task titles 16px, input 15px; 8px gaps, 16px panel padding and 12px cards.
- Warm paper, muted sage and the same semantic colors in both themes. Finder
  badges, source/excerpt cards, buttons and declarative artifact renderers share
  this scale. Selection colors and keyboard focus remain explicit.
- Compact idle shows the companion and composer. The work canvas appears for
  actual work, search, expanded mode and secondary pages. The same live editor,
  result objects and source actions remain in use.
- The source request remains in the task heading. Remove its duplicate floating
  labels above the composer. Keep the face exposed in every state; masked props
  do not poke through the composer in expanded mode.

## Reading and layout fixes

- Fit the desk to active content and its actual wrapping width. Hidden detail
  pages do not set the overview height; the companion/composer have their own
  minimum space. Returning results does not change compact width.
- Fit speech previews to their actual width. Long answers use a short excerpt
  beside the companion and retain the full result on the desk. Copy preserves
  the full original answer. Copy/read-full buttons are visible when available.
- Reconcile result visibility when previews resize or the theme changes, so a
  short answer remains single and a truncated answer remains available in full.

## Review artifacts and limits

`work/rat_ui_polish_20261021/` contains source-before copies, scoped patch, raw
test commands/results and the real Qt capture script. `index.html` shows the
three states together, with light/dark and compact/narrow/expanded selections;
`three-states.png` is a static comparison.

All preview content is authored fixture/synthetic content. No real model was
called, no personal documents were indexed and no model-quality claim follows.
Offscreen rendering and interaction tests do not establish native macOS motion
acceptance. The packaged/installed app is unchanged. Live movement and separate
facial artwork remain outside this polish pass.
