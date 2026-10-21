# Resident offline document Q&A — runtime and CLI

Implemented on 2026-10-16 for the user's local/offline stage. RAT now has an
explicit native document-model path owned by `AssistantRuntime`, and a headless
CLI for repeated questions. This extends the earlier
[MLX session prototype](rat_native_session_20261016.md).

## Use from the checkout

```sh
.venv/bin/python -m rat.main ask-file "/absolute/path/already-indexed.txt" \
  --model-path "/absolute/path/complete-local-mlx-model"
```

The model directory must already contain config, tokenizer and safetensors.
This path uses the installed MLX/MLX LM dependencies; the observed model was
`mlx-community/Qwen3.5-4B-MLX-4bit`, snapshot
`32f3e8ecf65426fc3306969496342d504bfa13f3`, with MLX 0.32.2 and MLX LM 0.31.3
on this Apple Silicon machine. No install or download was performed. Packaging
and Windows/Linux support for this native backend have not been established.

The CLI opens the existing RAT index read-only. It requires an exact indexed
absolute file path and does not search, scan, index or open another file for you.
Use `--db /absolute/path/index.db` to select another existing RAT database.

In interactive mode:

- Type a question to answer from the selected file's excerpt.
- `:file /absolute/path/another-indexed.txt` selects another file.
- `:unload` releases the native model and document context. The next question reloads them.
- Ctrl+C during an answer cancels that question; another question can follow.
- `:quit`, EOF or Ctrl+C at the prompt exits and closes the model service.

For a noninteractive session, repeat `-q`:

```sh
.venv/bin/python -m rat.main ask-file "/absolute/path/already-indexed.txt" \
  --model-path "/absolute/path/complete-local-mlx-model" \
  -q "Mã xác nhận?" -q "Phòng nào?"
```

Each answer prints its source and observed character range. The reader currently
provides at most 3,000 characters; longer files are explicitly labeled as excerpts.
This is not whole-document question answering, retrieval across pages, or an
autonomous tool-calling assistant.

## Runtime contract

```python
from rat.engine.assistant_runtime import AssistantRuntime
from rat.engine.selected_document_qa import answer_selected_document

with AssistantRuntime(db=db, document_model_path=local_model_dir) as runtime:
    runtime.document_model_client.load()  # optional startup preparation
    response = answer_selected_document(runtime, question, selected_absolute_path)
```

`ResidentDocumentModel` owns one inference thread. Model load, inference and
release run on that same thread; construction does not import MLX or load weights.
The first question can load weights automatically, or an owning worker can call
`load()` first. These calls block their caller and must stay off the GUI thread.
`close()` cancels pending work, waits for the owner thread to release native
resources, and shuts it down. Startup weight loading itself is not interruptible
between file reads; close waits for that load to finish.

Every question still goes through the registered indexed-file read, artifact
store and execution receipts. It reads current on-disk text even if index content
is older. Only one exact normalized document prefix is retained. A changed
excerpt invalidates the cache; a repeated question generates a fresh answer from
an isolated copy of the prefix. No answer cache or second model attempt is added.

Cancellation is checked while waiting in the inference queue, between native
prefill chunks and during generation. A cancelled or truncated answer is not a
successful final result. Optional `on_text` callbacks are provisional model text;
they run on the inference thread. UI integration must retain execution/turn
ownership checks and discard stale/cancelled chunks before displaying them.

Context limits include output allowance and reject oversized prompts instead of
silently truncating additional input. Metadata includes full prompt-token counts
including reused tokens; these are not full inference costs. Native
`raw_response.first_text_s` starts inside the loaded native client's generation
request; it excludes service queue/weight-loading time. Service `duration_ms`
includes that time, and the measurements below use complete runtime wall time.

Native model selection is explicit through `document_model_path`; there is no
automatic network/provider fallback when it fails. Existing callers without that
configuration retain their previous behavior. GUI construction/startup and the
general agent backend were not switched. Connecting the UI to this resident
service remains a separate integration step after its current revision is stable.

## Nonblocking startup preparation (backend ready, GUI wiring pending)

`runtime.preload_document_model()` now returns a `concurrent.futures.Future`
immediately, or `None` when no native document model was configured. Direct
service callers can use `ResidentDocumentModel.preload()`. Concurrent preload
requests share the pending future. Loading, answering and release still use the
same inference thread; no new worker pool or daemon is introduced. Preloading
does not read a document, prepare a prefix or generate an answer.

```python
runtime = AssistantRuntime(db=db, document_model_path=local_model_dir)
warmup = runtime.preload_document_model()
# Continue startup; observe warmup.done()/exception() through an owner-controlled
# queued GUI signal. Do not wait on result() or call close() on the GUI thread.
```

Future callbacks may run on the inference thread or immediately on the caller
when already complete. They must not touch widgets directly. Failures remain
on the future and do not select another provider. Explicit unload drops the
model/context; a later preload or question can reload them. Close rejects new
preloads, cancels queued preparation and waits for any load already in progress
before releasing resources on the owner thread.

`Config` now persists `document_model_path` (empty by default) and
`document_model_preload` (false by default). Launch overrides are
`RAT_DOCUMENT_MODEL_PATH` and `RAT_DOCUMENT_MODEL_PRELOAD`; the latter accepts
`1`, `true` or `yes` to enable, case-insensitively. Other values disable it.
Explicit environment values override saved settings; an empty path override
clears native selection. Saved preload values must be JSON booleans.

These settings are available for the forthcoming GUI integration; **setting
them alone does not switch the current GUI backend or start preloading**. The
integration must explicitly pass the configured path to the runtime and call
preload when requested. Invalid model paths still fail validation at runtime
construction, before native imports; the GUI must handle that error while
keeping metadata search available. The CLI continues using `--model-path`.
General agent behavior, research model selection and Stage 0 are unchanged.

Startup preparation/configuration tests use a scripted native backend. They
check lifecycle and thread ownership, not model quality, UI smoothness or a
measured speedup. Prior real-model timings below remain historical measurements.

## Verification

```sh
.venv/bin/python -m pytest tests/test_document_model_startup.py tests/test_mlx_document_session.py \
  tests/test_selected_document_qa.py tests/test_assistant_runtime.py \
  tests/test_rat_headless_cli.py -q
```

The original resident-service check had **76 passed**; the startup/configuration
extension is recorded separately in `audit/rat_document_startup_20261016/`.
Coverage includes real indexed reads with a scripted model,
single-thread ownership, context reuse/invalidation, cancellation during prefill
and generation, queued cancellation, timeout, unload/reload, close, batch and
interactive CLI commands, plus help without Qt/MLX/search imports. These software
checks do not measure model quality.

The bounded native run then made nine requests on three authored synthetic
development fixtures using the installed checkpoint. A socket audit hook rejected
network connects; recorded connection attempts: **0**. All nine scenario checks
passed, including real read receipts. Model startup took **18.02 s** before the
first request. The process closed its session and exited successfully.

| Scenario | Complete read + answer wall time | Observation |
| --- | ---: | --- |
| First short document | 6.26 s | Correct code; new prefix |
| Follow-up on same document | 2.07 s | Correct room; prefix reused |
| Switch document | 5.36 s | Correct code from new document |
| Edit document at same path | 9.24 s | New code read from disk; prefix rebuilt |
| Ask for absent email | 4.86 s | Requested missing-information response |
| Cancel during generation | 1.93 s | Cancelled; no final answer |
| New question after cancellation | 3.77 s | Correct code; prefix reused |
| Long document, 3,000-character excerpt | 26.05 s | Correct code in excerpt; truncation explicit |
| Unload then ask again | 14.61 s | Includes automatic weight reload and new prefill |

MLX active allocation was 2.37 GB after startup and 2.43 GB before final close;
recorded peak was **2.99 GB**, decimal units. These are native allocation values,
not total app RAM. The fixtures, question lengths and runtime conditions differ
from earlier probes; no controlled speedup or general quality claim follows.
New-document preparation and long excerpts still have substantial latency.

Raw requests/responses, source snapshots and hashes, script, manifest and tests
are under `audit/rat_document_service_20261016/`. Full response artifacts preserve
cost/source information and failures; native first-text timings are headless
metrics, not time to first visible text in the app. Research harness, data splits,
controllers, publication claims and Stage 0 were not changed.

The user's requested advanced Spotlight finder in the same chat is recorded as
**RAT-FIND-01** in the [RAT backlog](rat_backlog.md), deferred to a later task.
