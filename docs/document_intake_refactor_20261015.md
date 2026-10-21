# Shared PDF/OCR intake — 2026-10-15

`document_intake/` now owns digital PDF extraction, optional PDFKit rendering,
Apple Vision OCR and Tesseract TSV/text fallback. It imports neither RAT nor
DocAI, Qt or Z3. Engines load on demand. RAT retains classification, metadata
formatting and its string APIs. DocAI retains its invoice facade, raw OCR tokens,
page limits and review-required output. Its PDF path still reads digital text
only; no invoice capability was added to RAT.

DocAI intake modules remain small compatibility facades. Its separate Swift OCR
implementation and the stale identical Swift file in its generated build tree
were removed; their source is preserved in the audit's `before/` directory.
Other compatibility assets, run artifacts and migration backups are unchanged.
Tesseract now preserves line boundaries using page/block/paragraph/line IDs.
A live synthetic smoke exposed an existing PDFKit selector typo, corrected to
`thumbnailOfSize_forBox_` and exercised through scanned PDF OCR.

## Size

The seven original implementation files contained 1,127 physical / 958 nonblank
lines. Including all four new shared Python files, the same scope now contains
980 physical / 838 nonblank lines: **147 physical lines removed net (13.0%),
or 120 nonblank lines (12.5%)**. This excludes tests, documentation, build copies
and the recoverable audit snapshots. Disk usage can increase due to these
verification artifacts; this is a source-maintenance reduction, not disk cleanup.
No claim is made that this percentage applies to the entire repository.

## Validation

- Shared contracts, standalone DocAI (including compatibility), separation,
  local-file and book tests: 89 passed, 1 skipped.
- Index integrity/link repair/consistency: 31 passed.
- Actual Apple Vision OCR returned 3 observations for a synthetic image and its
  bytes; Tesseract returned 6 tokens. PDFKit rendered and OCR-read the synthetic 
  scanned PDF; digital PDF extraction correctly returned no text for the scan.
- Both packages built as wheels without the removed Swift source. Extracted
  wheels imported outside the checkout and performed a real Z3 consistency check
  without importing RAT. Original wheel ZIP-import probing was replaced with
  extracted installation semantics, since DocAI has namespace subpackages.
- Research harness, model experiments and Stage 0 gate were not changed.

From repository root, standalone installation is:

```sh
python -m pip install "./document_intake[pdf,vision]" ./modules/docai
```

The live checks use generated fixtures only, not personal files, and do not
measure corpus accuracy. Counts, original sources, tests, build and smoke
artifacts are under `audit/document_intake_refactor_20261015/`.
