# RAT: measured latency follow-up — 2026-10-15

The first optimization is implemented in source. On one exposed document task,
the 4B model completed the work before and after the change; observed wall time
was 85.85 s before and 78.58 s after. This is a small local observation, not an
established general speedup. The configured 1.5B model failed the task both
times. RAT has not reached acceptable everyday responsiveness or overall task
acceptance through this change.

## What was measured

The live model had to find `latency_probe.txt`, read it, and report the code
`LOTUS-7319` contained only in its contents. The short document is artificial;
the operations, SQLite index, filesystem read and local Ollama inference are
real. The fixture uses an isolated database, not the personal index. Success
requires an observed successful read of that exact file and the correct code
in the final answer, in addition to no runtime error. This narrow check does
not assess unrelated response claims or broader assistant quality.

The runner uses the native app's `plan_tasks=False`, `discover_tools=True`,
`structured_context=False`, 8K context, temperature 0.1 and `think=false`.
It is bounded to five model calls/steps and 60 seconds per HTTP call, rather
than the app's larger execution limits. Each configuration ran once. No model
was downloaded and no saved configuration or personal index was changed.

Hardware preflight reported Apple M1 and 16 GiB RAM; Ollama reported version
0.34.3. Valid processor observations showed the measured model at 100% GPU.
This establishes residency, not utilization or absence of contention.

| Configuration | Task result | Calls | Wall seconds | Prompt tokens, summed over calls | Completion tokens |
| --- | --- | ---: | ---: | ---: | ---: |
| Original, qwen2.5:1.5b | Failed: invented `/path/to/...`, then stopped | 2 | 16.03 | 2,713 | 48 |
| Candidate, qwen2.5:1.5b | Failed: found file but did not read it | 2 | 20.01 | 2,505 | 108 |
| Original, qwen3:4b-instruct | Passed this fixture | 3 | 85.85 | 5,571 | 118 |
| Candidate, qwen3:4b-instruct | Passed this fixture | 3 | 78.58 | 4,866 | 105 |

The 1.5B observation did **not** get faster overall. Its longer incomplete
answer consumed more generation time. Failed tasks are retained in the table.
The 4B model used the same search/read/final sequence; no call reduction was
achieved. The 4B wall difference is 7.27 s (8.5%), and summed prompt tokens fell
12.7%. First-call prompt counts fell from 1,484 to 1,271 for 4B and from 1,293
to 1,080 for 1.5B. These describe the saved requests, not a population estimate.

| Reported server phase, 4B | Original seconds | Candidate seconds |
| --- | ---: | ---: |
| Model load | 3.66 | 3.36 |
| Prompt evaluation | 60.74 | 52.74 |
| Generation | 21.02 | 21.60 |

Prompt evaluation remains the largest measured phase. Swap was already in use
before profiling. It stayed near 2.4 GiB during the original 1.5B observation;
the first 4B observation ended near 4.5 GiB. Other processes were not controlled,
so this does not establish that the model alone caused swap growth or that
swap explains the observed latency.

## Changes

- Shorter actor/tool descriptions, with an explicit instruction to search for
  a filename before using a path. The seven initial tool names and all input
  constraints remain identical; the offline analyzer checks this after removing
  description annotations. Handlers, receipts and source checks are unchanged.
- A single request timestamp for actor calls and tools, instead of a newly
  generated timestamp on every actor call.
- The changing compact context projection follows the native tool history,
  preserving its stable prefix. All projected facts remain present. Full typed
  snapshots retain their existing placement. This preserves an opportunity for
  prefix reuse; the run does not isolate its causal contribution to speed.
- The normal SLM transport retains the raw server response and a usage-known
  flag for profiling. It adds no extra inference call or automatic prompt log.
- A bounded reusable runner, `scripts/profile_rat_latency.py`, records source
  copies/hashes, raw requests/responses, resource observations and task outcome.
  The candidate profiles use the normal production transport. The baseline
  profiles used the existing instrumented transport with equivalent request
  values; the JSON wire escaping differs. Source copies preserve both versions.

## Validation and limits

The focused and broader checks culminated in **230 passing software tests**:
transport, runtime, canonical context, completion reconciliation, cancellation,
notes, worker, document delivery and PDF page handling. The sandbox aborted on
the Qt import; the same broader set passed outside the sandbox with Qt offscreen.
See `tests.xml`. These are software regressions, not measured model quality.

The four runs made ten model calls total, with no timeouts. All counts were
reported by the server. Prompt counts include cached tokens and repeated input
across calls; completion counts are reported separately. Neither token count
alone is a full inference cost. Wall times are measured online headless task
times, not replay times, TTFT, native UI latency or app cold-start time.

Models/configurations were run sequentially, without randomized order,
counterbalancing or repeated seeds. Target models were not resident before
their respective task runs, but another model was resident before the original
4B run and was evicted during loading; no model was resident before candidate
4B. Memory pressure/background load were not matched. Paths and sampled tool
arguments/output lengths also differ. Do not attribute the 8.5% difference
entirely to the code change or extrapolate it to other tasks.

The two 4B answers were reviewed against the actual fixture and reads. The
1.5B failure remains unresolved. The model default is unchanged. Streaming,
transport cancellation, UI packaging and the unrelated in-progress changes
were not part of this slice. Source changes require a restart of a source-run
RAT; an existing packaged app has not been rebuilt or updated.

The next useful implementation work is reducing unnecessary context and round
trips on representative successful tasks, while separately validating a model
that reliably executes them. A smaller model cannot be selected for speed
using failed tasks, and a larger model cannot be declared usable from this one
success. AirLLM was not installed; these observations do not identify a reason
to add layer streaming to the interactive path.

## Reproduction

Offline verification, with zero inference calls:

```bash
.venv/bin/python audit/rat_latency_20261015/analyze.py
```

New live development observation (fresh output directory required):

```bash
.venv/bin/python scripts/profile_rat_latency.py --output audit/NEW_LATENCY_RUN
```

Each run directory includes `manifest.json`, `fixture.json`, `calls.jsonl`,
`response.json`, `resources.json`, `summary.json` and the exact `source/` copies.
`analysis.json` is derived by the offline analyzer. No NCKH evidence claim,
research harness, held-out data, Stage 0 gate, DocAI integration or Git push was
changed.
