# Icon preparation prompts and provenance

Built-in `image_gen` was used for image editing, followed by native macOS
`sips` resizing and PNG-backed ICNS container compilation (`iconutil` rejected
the local iconsets). Original screenshots are
preserved alongside this file. Generated artwork can differ from those sources.

## Full RAT default

Input: `rat-app-icon-selected-v2-source-screenshot.png`.
Output master: `masters/rat-default.png`.

```text
Use case: background-extraction. Asset type: production macOS app icon master.
Edit the attached screenshot into a clean square app icon asset. The screenshot is the edit target, not loose inspiration. Preserve this exact rat drawing, pose, eyes, pencil, raised paper, yellow folders, scattered paper pile, tail-held magnifying glass, muted sage-green rounded square and black hand-drawn outlines extremely closely. Do not simplify, redesign, add details, or change the composition.
Remove ONLY the off-white screenshot exterior outside the green rounded-square tile. That exterior must be genuinely transparent, including the rounded corners. Retain all illustration inside the green tile. Center the complete tile on a square transparent canvas, using approximately 88% of canvas width and height with balanced outer padding; do not crop the tile or rat. High-quality clean edges, flat illustration, no new shadows, no 3D, no gloss, no additional border. No text. Output one large square icon master.
```

## RAT Lite

Input: generated full RAT master above. Output: `masters/rat-lite.png`.

```text
Use case: precise-object-edit. Edit target: the attached transparent RAT app icon. Create its Mini edition. Preserve the exact drawing, layout, tile, palette, outlines, rat face, papers, folders and transparent exterior. Add only a small clean dark charcoal rounded badge near the bottom-right INSIDE the green tile, with the exact lowercase word "lite" in off-white, simple bold sans-serif lettering. The badge must be modest, roughly one fifth of tile width, readable at Dock size, and must not cover the rat's face. Spell exactly l-i-t-e. No other text, no extra border, no new props, no redesign, no extra shadow. Keep the same square canvas, balanced padding and actual exterior transparency.
```

## Alternatives

The following prompt was applied separately to `rat-app-icon-source-screenshot.png`
and `rat-app-icon-paper-stack-option-source-screenshot.png`, producing
`masters/rat-classic.png` and `masters/rat-paper-stack.png` respectively.

```text
Use case: background-extraction. Asset type: production macOS app icon master. Edit the attached screenshot into a clean square app icon. This image is the exact edit target: preserve its rat, facial expression, pose, every prop, hand-drawn black contours, colors, and muted sage green rounded square extremely closely. Remove ONLY the off-white screenshot exterior OUTSIDE the green rounded tile and make it genuinely transparent including the tile corners. Keep everything inside the tile unchanged. Center the complete tile on a square transparent canvas with balanced outer padding, tile occupying about 88% of canvas dimensions. Do not crop the tile, rat or props. No new text, no badge, no redesign, no extra shadow, gloss, 3D, invented details or additional border. Output one large square icon master.
```

## Notebook candidate — not ready

Original: `rat-app-icon-notebook-option-source-screenshot.png` (user supplied
at 23:49 on 2026-10-28). It shows RAT among papers, holding a spiral notebook.
The same alternative extraction prompt produced an unwanted transparent/dark
patch in the upper-left green interior. Two targeted attempts did not resolve
it. None of those defective cutouts is included in the production catalog.

Last attempted prompt, with the original screenshot as input:

```text
Use case: background-extraction. Produce one clean production app icon from this ORIGINAL screenshot. Preserve the exact illustration of the rat surrounded by papers, holding a spiral notebook, with a tail-held magnifying glass. Keep all lines, pose, eyes, objects, and original muted sage green background closely faithful to the screenshot. Remove only the pale off-white exterior outside the green rounded-square icon. Make the exterior genuinely transparent. The green rounded-square tile must be uniformly opaque everywhere inside, with NO transparent holes, dark blotches, missing patches or gradients. Especially preserve the clean solid green area in the upper-left. Center the tile on a square transparent canvas with 7% padding on all sides. No text, no badge, no redesign. The reference screenshot has no hole or dark patch: do not invent one.
```
