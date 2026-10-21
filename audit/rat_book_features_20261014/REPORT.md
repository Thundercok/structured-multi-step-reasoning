# RAT book features: software validation

Date: 2026-10-14, Asia/Ho_Chi_Minh.

Implemented: indexed PDF page keyword search, exact-page text/citation reading,
and the source-bound table slice of RAT-AI-02. See
[feature scope](../../docs/rat_book_features.md) for commands and user examples.

## Evidence

- [Headless run](headless_tests.txt): **165 passed**. Includes 24 new cases
  covering actual 30-page PDFs, late-page discovery, accent-insensitive matching,
  PDF labels, bounded continuation and result truncation, page read actions,
  blank/password-protected/unindexed/malformed PDFs, cancellation, source
  references, old/deleted revisions, invalid table cells and scripted runtime
  search → read → sourced note → table.
- [New-feature Qt run](ui_tests.txt): **3 passed**, in a separate process.
  Real Qt widgets check the exact-page menu dispatch, source display, plain-text
  table headings and retained disclosure state across compact/full changes.
  Qt required execution outside the sandbox because its CPU detection aborted
  inside the sandbox.
- Existing `tests/test_interaction_kernel_ui.py` alone: **7 passed**.
  Combined new and existing UI tests excluding `inline_export_worker`:
  **8 passed, 2 deselected**.
- The unrestricted combined UI run repeatedly exited **139** in
  `rat/astrology/export.py:48` (`QSvgRenderer` in the export worker), after the
  new feature tests had passed. It also occurred with a session-scoped Qt app.
  The export implementation and existing UI test file were not modified.
  Running only the old export tests passed (2 cases), and the old module alone
  passed (7 cases). The interaction/order-dependent crash remains unresolved;
  this report does **not** certify the entire combined GUI suite.
- Whitespace checking of this change's tracked files passed. A repository-wide
  check also reported pre-existing trailing blank lines in the already-modified
  `tests/test_rat_conversation_lifecycle.py` and `tests/test_work_context.py`;
  those files were left untouched.

## Interpretation limits

These are software regressions with generated PDF fixtures and scripted model
decisions. No real-model calls, model-quality measurement, live conversation
acceptance or application package rebuild were performed. The PDF fixtures are
synthetic test data, not research observations. There are no measured inference
cost or latency claims.

Search is literal word matching, not semantic retrieval; scanned pages need OCR.
Table copying validates source references, not the meaning of model-written
labels or comparisons. The broader RAT-AI-02 backlog remains open. Research
experiments, the default model, Stage 0 and deferred DocAI integration are
unchanged by this work.
