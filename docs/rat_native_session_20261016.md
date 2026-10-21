# Native offline document session — 16 October 2026

Follow-up: the [resident runtime/CLI integration](rat_document_service_20261016.md)
is now implemented and separately tested. The observations below remain the
original prototype run; its default-UI limitations still apply.

The user's requirement for this stage is 100% local/offline inference, with
startup loading acceptable. The useful architectural change is a resident model
plus a prepared active-document context. Keeping model weights resident alone
does not remove the cost of reading new prompt text.

## Implemented backend

`rat.engine.mlx_document_session.MLXDocumentSession` loads a complete local model
directory explicitly, then retains one prepared document prefix. It uses native
MLX directly, without an Ollama service, downloads or provider fallback.
Inference imports remain lazy. `load()` and `prepare_context()` are blocking
preparation operations intended for an app-owned inference worker.

Each question uses a copy of the prepared cache and generates a fresh answer.
Changed prompt tokens invalidate the document context; answers are not cached.
Cancellation checks run at prefill chunk boundaries and generation steps. The
context budget includes the complete prompt plus output allowance; input is
rejected rather than silently clipped. Agent tools, thinking and structured
agent-output protocols are explicitly unsupported by this document session.
`close()` drops the model/context references and clears unused MLX allocations.

The existing selected-document path accepts the session through its
`model_client` argument. Its exact indexed-file read, artifacts and committed
read receipts remain authoritative. Prompt construction is now shared through
`selected_document_messages()` so preparation and answering use identical
extraction/truncation normalization. The answering prompt itself is unchanged.

Default RAT backend/model settings, app startup, UI files and packaging were
not switched. This is a tested headless backend, not a complete native assistant
or an already-integrated UI feature. Normal agent chat still uses its existing
backend. The research backends, harness and Stage 0 are unchanged.

## Real offline observations

Used the already-cached `mlx-community/Qwen3.5-4B-MLX-4bit` snapshot
`32f3e8ecf65426fc3306969496342d504bfa13f3`, with MLX 0.32.2 / MLX LM 0.31.3.
No dependencies or model weights were downloaded. Both probe processes enabled
offline library modes and installed an audit hook that rejects socket connects.
Every recorded run reports zero network attempts. All model sessions were
closed, and their processes exited after the bounded observations.

The document and two short confirmation-code questions are artificial,
previously exposed development fixtures. They do not establish general quality.

| Direct native probe | Question 1 complete | Question 2 complete |
| --- | ---: | ---: |
| Model resident, document uncached | 15.57 s | 13.50 s |
| Model resident, document prefix prepared | 2.69 s | 2.48 s |

The prepared prefix in that probe took 9.37 s to build. Library imports took
18.07 s and the subsequent weight/tokenizer load 5.76 s. These preparation
costs are outside the cached-question timings and must not be omitted from
end-to-end cost accounting. Uncached runs preceded cached runs; compilation,
OS caches, thermal state and other development work were uncontrolled. This is
not a controlled app-wide speedup or a comparison with the prior Qwen3/Ollama
stack, which uses a different model and workflow state.

The final **RAT runtime** check used a fresh real indexed read for each question
and the production session class:

| Question | Read + answer | First nonempty model text | Exact code / source / receipt |
| --- | ---: | ---: | --- |
| Vietnamese | 1.88 s | 1.04 s | Passed |
| English | 1.93 s | 1.00 s | Passed |

For that final process, session load took 16.65 s (including native imports),
and preparing the normalized 470-token document prefix took 9.52 s. The two
requests then submitted only 27 and 26 new prompt tokens. First model text is
a headless metric; it is not measured native-UI time to first visible text.
The full prompt count still includes reused tokens; these counts are not full
inference costs.

The direct native probe reported about 2.37 GB of active MLX allocation after
load, about 2.51 GB with the document cache, and a 2.98 GB peak (decimal units).
CPU process RSS alone does not describe this unified-memory footprint. The
prototype trades preparation time and resident memory for faster subsequent
questions; it does not make the model memory-free. A new document still needs
its own prefill. Long answers also require additional generation time.

An initial runtime rehearsal prepared raw text with a trailing newline, while
the registered reader returns a stripped excerpt. Its cache correctly missed;
the answer was right but took 18.85 s. That failed rehearsal is preserved in
`runtime_first_*` artifacts. Canonical reader output and shared prompt
construction resolved the mismatch. Total work across the direct probe,
failed rehearsal and corrected runtime check was seven generations.

## Validation and next integration boundary

```sh
.venv/bin/python -m pytest tests/test_mlx_document_session.py tests/test_selected_document_qa.py tests/test_assistant_runtime.py tests/test_rat_headless_cli.py -q
```

**68 passed.** Fixtures cover exact cache reuse, invalidation, separate answer
generation, cache isolation after cancellation, failed preparation, local-path
requirements, budgets, unsupported protocols and real indexed-read integration.
The explicit-preparation test includes a trailing newline to protect the
normalization fix. Python compilation and scoped whitespace checks pass.

Raw probes, input token IDs, request/response metadata, source snapshots and
test results are saved in `audit/rat_native_session_20261016/`. No personal
document was read or indexed.

When UI work is stable, integration should give one worker ownership of the
resident session, prepare the active file while presenting its reading state,
forward streamed text through existing execution-ownership guards, and close
the session on app exit or an explicit resource-management decision. General
agent tool calling requires separate implementation and quality checks. No
cloud fallback belongs in that offline path.

The cache-copy approach follows the installed MLX LM implementation; see also
the project's [prompt-caching documentation](https://github.com/ml-explore/mlx-lm#long-prompts-and-generations).
