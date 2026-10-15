# Shared document intake

PDF and OCR primitives used by RAT and standalone DocAI. Importing the package
loads no OCR engine, Qt, RAT, invoice logic or solver. Optional engines are loaded
on demand. Digital PDF reading does not silently invoke OCR.

From repository root:

```sh
python -m pip install "./document_intake[pdf,vision]"
python -m pip install ./modules/docai  # only for standalone invoice work
```

RAT uses `read_pdf_native` for PDFKit rendering of scanned pages on macOS, with
`read_pdf` as its digital fallback. DocAI uses only `read_pdf` for PDFs, retaining
its existing page limit and explicit failure when scanned pages have no text.
Both use the same Apple Vision implementation for image OCR; tokens retain text,
confidence and top-left pixel bounding boxes. Tesseract needs its external binary
and `vie+eng` language data. Missing engines retain the callers' empty/failure
contracts. RAT retains its own image classification and metadata formatting.

A successful read is not evidence of OCR accuracy or invoice validity.
