# OCR soft wraps — shared capture contract, M5.13 source

Implementation only, 2026-10-27. No tests or app execution in this iteration.
No measured quality claim. This changes the OCR source representation; it does
not implement Agent planning or change research claims/Stage 0.

`capture_text` uses `rat.engine.ocr_paragraphs.prepare_ocr_text` after the existing
Apple Vision reader. Consecutive prose lines are joined only with nearby,
similarly sized, aligned bounding boxes. Paragraph gaps, columns, short headings,
sentence endings, list markers and obvious code/URLs retain their breaks.
Characters/order are preserved: selected newline characters become spaces.
No spell correction, dehyphenation, arbitrary reordering or guessed text.
This conservative heuristic is not general document layout analysis.

The captured artifact holds:

- `text`, `source_sha256`: prepared text and hash used by translation.
- `ocr_raw_text`: original OCR lines.
- `ocr_normalization`: `policy=aligned-soft-wrap-v1`, selected newline indexes,
  original hash and prepared hash.

CaptureVerifier reproduces the newline replacements and checks both hashes.
Translation still pins the same observed capture artifact/revision; segment
coverage is measured against its prepared text. Original OCR stays available in
the editor's “Xem chữ ban đầu”. Local translation gets its own larger chunk
budget instead of the unrelated MyMemory fallback byte limit.

User correction creates a new artifact via `correct_captured_text`. It removes
the parent's preparation descriptor because that descriptor does not describe
the edited text. The parent/root refs, original OCR and original artifact remain
available. Translation uses the edited artifact's hash, never a parallel UI-only
normalization path. Structural verification does not certify OCR/translation
semantics.

Future bounded acceptance: actual wrapped prose screenshot; paragraph/list or
column boundaries; edit then retry. Newline/hash derivation, source refs and
repeated corrections need contract coverage before release. None was run here.
