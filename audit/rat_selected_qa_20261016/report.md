# Selected-file Q&A — 16 October 2026

Implemented in source: choose **Hỏi** on an existing file card, then type the
question into the existing bottom composer. The selection is consumed by that
one submitted question. Normal chat continues through its original path.
The existing selected-file preview question signal also reaches this path.

## Behavior

The runtime mechanically reads the exact selected indexed path, retaining its
normal artifact, read receipt, turn/execution ownership and cancellation guards.
It then uses `qwen3:4b-instruct` for at most one answering call with a short
document prompt and no tools. This does not change the saved model default.

The first 3,000 extracted characters are in scope. Truncation and total length
are supplied to the model; source cards say **Đã đọc đoạn trích** for a partial
read. A missing, unindexed or textless source makes no inference call. Oversize
requests are rejected instead of silently clipping more facts. Model errors,
truncations or tool requests do not trigger a fallback or second generation.

This path answers a question about the selected excerpt. It does not execute
arbitrary follow-up actions, search the whole book, or claim semantic answer
verification merely because the source was read. A model answer may still be
wrong; the UI does not mark it as verified.

## Live development observation

Three artificial documents were copied from the completed overnight benchmark.
The same provided-text questions and confirmation-code labels were used. Each
target model started unloaded, and was unloaded again after the check. No
personal file or personal index was used or changed.

| Document | Online headless read + answer | Inference calls | Exact code + correct read |
| --- | ---: | ---: | --- |
| Short | 13.14 s | 1 | Passed |
| Medium | 14.84 s | 1 | Passed |
| Long | 17.01 s | 1 | Passed |

The median is 14.84 s over three exposed development documents and one observed
draw each. The original full agent workflow had a 70.58 s median over 18 trials,
but required finding the file too. These are different workflows: manual file
selection and a fixed read remove model decisions. Do not report their ratio
as a controlled app-wide speedup, or three successes as general model quality.
Native UI timings, arbitrary real documents, long documents and accuracy beyond
this narrow code check remain unmeasured. These are online wall times, not
replay estimates. Prompt/completion usage and raw server phases are saved in
`trials.jsonl`; token counts are not full inference costs.

`manifest.json` records model digest/version, the source hashes and copies,
unchanged source during the observation, and empty model residency after cleanup.

## Software validation

`tests/test_selected_document_qa.py` covers indexed reads, one-call enforcement,
missing/unindexed/empty inputs, partial-read disclosure, model truncation/tool
requests/errors and cancellation during inference. The UI check verifies that
the file action reuses the current composer, passes the exact path to the
worker and consumes the selection once. Core and Qt regression results are
saved in `core-tests.xml` and `ui-tests.xml`.

Final results: **145 core tests and 29 Qt tests passed (174 total)**. The scoped
diff whitespace check and Python compilation also passed.

An initial UI fixture omitted required SearchResultItem fields; it failed before
cleanup and the combined Qt process subsequently crashed. The fixture was fixed
and the UI checks rerun. This was not a live-model observation.

Restart a source-run RAT to load the changes. The packaging specification now
includes the new helper, but no packaged app was built or updated by this slice.
Unrelated working changes, research harness, Stage 0 and DocAI scope were preserved.
