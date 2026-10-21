# Shared document intake

PDF and OCR primitives used by RAT. Importing the package
loads no OCR engine, Qt, RAT, invoice logic or solver. Optional engines are loaded
on demand. Digital PDF reading does not silently invoke OCR.

From repository root:

```sh
python -m pip install "./document_intake[pdf,vision]"
```

RAT uses `read_pdf_native` for PDFKit rendering of scanned pages on macOS, with
`read_pdf` as its digital fallback. The removed DocAI module is not an install
target; recovery material remains available separately. Apple Vision tokens retain text,
confidence and top-left pixel bounding boxes. Tesseract needs its external binary
and `vie+eng` language data. Missing engines retain the callers' empty/failure
contracts. RAT retains its own image classification and metadata formatting.

`read_pdf(path, max_pages=None, max_chars=None, password=None)` returns the
existing pages/text/metadata fields plus `status`: `ok`, `empty` (zero pages),
or `no_text` (no digital text returned). Check `extraction_truncated` alongside
status: a zero character/page budget can also yield no returned text. Blank
pages and image-only pages cannot be distinguished by text absence alone.
Digital reading never renders pages or invokes OCR. `max_chars` is a hard
limit on `full_text`, including page separators; metadata is separate.
Limits accept nonnegative integers or `None`; invalid values raise `ValueError`.

Expected failures raise `PDFReadError`, a `ValueError` with a stable `.code`:
`file_not_found`, `file_unreadable`, `invalid_pdf`, `encrypted_pdf`, or
`pdf_engine_unavailable`. Supply a password explicitly for locked PDFs; an
empty-password encrypted PDF remains readable. The RAT indexing adapter
returns empty text on intake failures or absent body text, retaining its
existing nonthrowing contract. Metadata alone is not extracted body content.

`read_pdf_native` returns text, empty text when no body was extracted, or `None`
when the native engine/document cannot be opened or unlocked without a password.
It keeps short digital text and invokes OCR only for pages without digital text.
Both PDF paths close their file resources and cap returned text. The native
path has no structured status/truncation report; use the digital reader for
that contract. Mixed raster/text within a single page is not fully diagnosed.

`TesseractOCREngine.run_ocr` retains `full_text`, `lines`, and `tokens`; absent
inputs, unavailable engines, timeouts and failed OCR return empty fields.
TSV and plain-text fallback share one finite timeout budget; a timed-out or
missing executable is not retried. Invalid TSV scores/boxes are skipped.
Apple Vision returns an empty token list for corrupt images and failed requests,
including PyObjC `(False, error)` outcomes. Optional OCR failures do not become
document text. Tesseract's binary and language packs are external prerequisites.

Fixture validation:

```sh
python -m pytest tests/test_document_intake.py tests/test_document_intake_robustness.py -q
```

A successful read is not evidence of OCR accuracy or invoice validity.
