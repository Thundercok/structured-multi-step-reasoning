# Cleanup after phase 0 — 2026-10-25

This is cleanup of an already implemented phase, not a second phase-0 delivery.
Earlier phase-0 logs/hashes remain unchanged in the parent folder.

- Removed the unused canned synthesis helper/archetypes from production
  `reading_session.py`; the module now only parses supplied cards and loads
  recalculated profiles. Production synthesis continues to fail observably with
  `model_unavailable` through the existing dispatcher operation.
- Removed template-only boundary/dialogue/CoT drawers from ReadingDesk, retaining
  input presentation and generic draft editing controls for the later migration.
  The draft editor has no successful synthesis producer today.
- Updated the Reading smoke script to expect no draft when model synthesis is
  unavailable. It no longer declares a full reasoning loop or six successful
  CoT steps. Each invocation writes a new output folder to preserve old evidence.
- Made `rat.ui` exports lazy: presentation helpers no longer import the Qt
  controller/application. A subprocess import probe blocks all PyQt6 imports;
  the profile recalculation/rendering test can now run headlessly.
- Reconciled current-status documentation; historical snapshots remain in audit.

Recovery: `before_cleanup.tar.gz`, verified byte-for-byte before source edits;
`recovery.json` records member hashes and the archive hash. This is recovery
material, not a runnable alternative implementation.

Validation command:

```sh
.venv/bin/python -m pytest tests/test_selected_document_qa.py tests/test_selected_document_read_scope.py tests/test_reading_session.py -k 'not quick_pdf_controller_reading_draft_flow' -q --tb=short --junitxml=audit/rat_agentic_phase0_20261025/cleanup/headless.xml
```

See `headless.txt`/`headless.xml` for results and `source_sha256.json` for the
checked sources. The single excluded controller test was run separately with
`QT_QPA_PLATFORM=offscreen` and still aborted (exit 134) importing PyQt6 at
`quick_pdf_controller.py:18`; its raw traceback is `controller.txt`.
No live UI/model acceptance or screenshots are claimed. The visible cleanup
removes the template-only CoT drawer; the existing “chờ Agent/model” label stays.
Research harness, inference budget, Stage 0 and unrelated workspace edits are
outside this cleanup. No Git commit/push.
