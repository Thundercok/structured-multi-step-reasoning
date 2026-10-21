# DocAI removal — 2026-10-17

User explicitly requested removing remaining DocAI after reuse. Removed only modules/docai/ after verifying all 191 regular files by SHA256 and mode against scratch/docai_removal_20261017.tar.gz (0600). Archive includes ignored local state, build copies, compatibility, fixtures, dependencies and tests; preserve it privately as recovery. No destination repository import, commit or push. Earlier export also remains intact.

## Reused implementation retained

- document_intake/pdf.py: digital PDF and optional native scan reader.
- document_intake/vision.py: Apple Vision text, pixel coordinates and confidence.
- document_intake/tesseract.py: OCR TSV/text reader.
- RAT wrappers continue calling these shared readers.

Invoice XML parsing, Z3 candidate generation, old APIs/UIs, fixtures and duplicate build source are no longer active source in this repository. No root runtime dependency or registry entry referenced the removed module in scoped searches.

Updated separation regression to require the invoice module absent while keeping the guarded default-registry import check. Shared PDF/OCR behavior is exercised by tests/test_document_intake.py. See tests.log for software regression; this is not OCR accuracy or model-quality evidence.

Current scope/handoff notes updated in AGENTS.md, README.md, docs/project_scope.md, docs/rat_backlog.md and docs/prompts/antigravity_debloat_next_20261017.md. Earlier inventories remain historical. Preserve unrelated dirty work and all recovery archives.
