# RAT overnight development benchmark — 15–16 October 2026

Authorized in chat on 15 October. The user selected a hard stop at **06:00 on
16 October 2026, Asia/Ho_Chi_Minh**. The fixed matrix finishes earlier if complete.
This is an application latency/capability diagnosis, not an NCKH campaign or a
publication dataset. Research Stage 0 and DocAI scope do not change.

## Frozen scope

- Installed `qwen3:4b-instruct`, Q4_K_M; expected Ollama model digest
  `0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`.
- Three artificial TXT files, approximately 200, 1,400 and 2,600 characters plus
  a unique confirmation-code line. Contents remain below the default read cap.
  Exact text, paths and hashes are frozen in the run, outside the personal index.
- Three observed repetitions, two initial model states, three arms: **54 trials**.
  Arm positions rotate by repetition; case/state order also rotates. There is
  no fixed generation seed. Repetitions are not independent new questions.
- Temperature 0.1, thinking disabled, 8,192-token context, 640 output tokens per
  call, at most 90 seconds per HTTP call and **126 generation calls in total**.
  The timeout shrinks near the deadline, reserving time for cleanup. No new call
  starts in the final 20 seconds. A transport error stops the run rather than
  queueing more work behind an uncertain backend request.

| Arm | Input and behavior | Per-trial call cap |
| --- | --- | ---: |
| `bare` | Short system prompt, provided document text, exact-code question | 1 |
| `rat_prompt` | Same provided text/question, native RAT actor prompt and initial seven tool schemas; one model call, tools are not executed | 1 |
| `rat_e2e` | Native RAT finds and reads the artificial indexed file, then answers | 5 |

`bare` versus `rat_prompt` diagnoses the cost/behavior of prompt and schema
packaging on the same supplied evidence. `rat_e2e` measures a different, complete
workflow; do not call its entire difference Python overhead. Unexpected tool
requests in the provided-text arm are recorded as failures, not silently executed.
The end-to-end arm executes only document search/read, artifact inspection and
schema discovery; other proposed actions stop at a checkpoint and fail the task.

Both residency conditions first unload only the target benchmark model. `cold`
then starts the task; `resident` preloads it with an empty API request before
starting the task. Preload/control costs are retained separately. This is
Ollama-model residency, not an OS disk-cache experiment. KV starts fresh for
each trial; prefix reuse within the end-to-end workflow is retained.

## Execution and evidence

The prepared run is at `audit/rat_overnight_20261015/`. Its `plan.json` records
the full order, caps, deadline and hashes. `source/` holds a copy of the current
RAT package and runner; execution uses that copy so ongoing work in the main
checkout cannot change this benchmark. No Git branch, push or reset is needed.

The process runs locally under `caffeinate -is`, which lasts only as long as
the child process. It requires AC power and stops starting work if AC is lost.
The computer must remain on with its lid open; keep Codex running for the chat
monitor. No app defaults, system sleep settings, personal files/index, models
or packages are changed/downloaded. Existing unrelated overnight scripts are
not invoked.

Files are checkpointed after each call/trial:

- `calls.jsonl`: start/input/settings and end/raw response, including incomplete
  usage and transport failures.
- `controls.jsonl`: target model unload/preload requests, responses and costs.
- `trials.jsonl`: complete runtime responses and a narrow fixture outcome check.
- `resources.jsonl`: memory/swap and model-residency observations every five seconds.
- `status.json`: process ID, progress, stop reason and final completion timestamp.
- `summary.json` / `report.md`: regenerated from saved observations after trials.

A pass requires the exact requested code. End-to-end additionally requires a
successful actual read of the correct file containing that code. Expected-code
presence and exact-format compliance are separately visible in raw trial checks.
This does not verify every statement a model could make or general assistant
quality. Truncations, tool errors, wrong answers and timeouts remain in latency
statistics. Missing token usage remains unknown in aggregate totals.

The report gives descriptive medians/p95, successes/attempts and call counts by
arm/residency. Three cases and nine observations per arm/state do not estimate
a reliable production tail or general model quality. Raw server load/prompt/
generation phases remain available; wall times are online headless task times,
not TTFT, UI latency or replay estimates. Input and output tokens are not full
inference costs. Background load and thermal/memory changes remain confounders.

## Monitoring and stopping

A thread heartbeat checks this run only, remains quiet while it progresses,
and reports completion, failure or required action. It must not launch another
collector, change frozen settings, retry an uncertain call, or tune against
results. Once the report is reviewed, it pauses itself.

To request a stop, create `audit/rat_overnight_20261015/STOP`. The runner stops
before the next call, preserves all data and requests target-model unloading;
an in-flight blocking request may take up to its remaining timeout. A failed
unload is recorded and does not establish that backend inference has stopped.
There is no automatic resume/retry of an existing journal.

Offline report regeneration (zero model calls):

```bash oka
```

Do not change app/model defaults overnight. Any follow-up implementation needs
the saved timing and outcome evidence first.
