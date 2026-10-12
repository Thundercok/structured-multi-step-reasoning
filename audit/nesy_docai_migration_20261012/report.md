# NeSy-DocAI migration validation — 2026-10-12

Source commit: `8e5533b6f376d32481dcfbc1762daf21bf260c65`.
55 tracked source/assets files were imported; the original worktree remained
clean. All imported destinations exist and have source/destination SHA-256
hashes in `integrations/nesy_docai/migration_manifest.json`.

- DocAI compatibility, supported inspection and RAT kernel checks:
  **80 passed, 2 skipped**. Streamlit was unavailable; inherited live OCR batch
  on generated images is opt-in. New inspection tests use fixtures/mock OCR
  with actual Z3, including missing/ambiguous XML totals and product mismatch.
- Required research regression checks: **29 passed**.
- Package/registry lazy import and CLI help work without loading Z3/Qt/models.
- One synthetic rendered image passed through **real Tesseract OCR**, then Z3:
  subtotal 100000, tax 10000, total 110000. The saved raw tokens/text and witness
  retain `review_required=true`. Native Apple Vision was attempted through the
  inherited engine and did not supply the selected result; it is unverified.

Z3 was installed in a temporary validation directory. The desktop runtime still
needs `requirements-docai.txt` to run the solver. No Streamlit/API server,
foundation-model inference, personal-file crawl or deployment ran. The app
bundle has not been rebuilt/verified.

Evidence scope is **software validation plus one synthetic OCR smoke**. Passing
tests and this one readable image do not establish general OCR accuracy,
fraud detection, fiscal compliance, automatic approval or NCKH effectiveness.
The main research protocol and Stage 0 remain unchanged.

Machine-readable details: [validation.json](validation.json).
Raw smoke output: [synthetic_ocr_result.json](synthetic_ocr_result.json).
Input fixture: [synthetic_invoice.png](synthetic_invoice.png).
