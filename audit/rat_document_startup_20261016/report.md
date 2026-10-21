# Native document startup preparation — 2026-10-16

Implemented while Antigravity owns the finder/UI revision. No GUI files or
research harness were edited for this slice.

- Optional saved settings: `document_model_path`, `document_model_preload`.
  Defaults leave native startup disabled. Explicit launch environment overrides
  take precedence; saved preload requires a real JSON boolean.
- `AssistantRuntime.preload_document_model()` / `ResidentDocumentModel.preload()`
  return a Future without waiting for model loading. Pending warmups coalesce;
  native load, generation and cleanup still share one service-owned thread.
- Warmup only prepares weights/tokenizer. Failures remain visible on the Future;
  no provider fallback or generation is introduced. Unload permits later reload.
- Shutdown cancels pending preparation and waits for an already-started load
  before cleanup. Future cancellation callbacks run outside the service lock.

Verification:

```sh
.venv/bin/python -m pytest tests/test_document_model_startup.py \
  tests/test_mlx_document_session.py tests/test_selected_document_qa.py \
  tests/test_assistant_runtime.py tests/test_rat_headless_cli.py -q \
  --junitxml=audit/rat_document_startup_20261016/tests.xml
```

**90 passed in 3.77s.** Native startup tests use the scripted backend already
used by the document integration tests. They validate nonblocking preparation,
load reuse, no generation during warmup, error delivery, unload/reload, cleanup
after a running warmup and cancellation of warmup queued behind inference.
Config tests use a temporary file and clear API-key environment values.
Scoped Git whitespace checks passed.

This is backend preparation, not completed GUI integration or a measured
speedup. No new real-model run was performed. The UI must still consume the
settings, handle invalid local paths without breaking finder, queue completion
signals with ownership checks, and close the runtime off the GUI thread.
Existing real-model measurements remain in `docs/rat_document_service_20261016.md`;
none are replaced by these software tests. General agent backend, research
selection and Stage 0 remain unchanged.
