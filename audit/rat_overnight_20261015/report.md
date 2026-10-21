# RAT overnight development benchmark

Partial or completed observations; check status.json. Failed trials remain in latency statistics.

| Arm | Model state | Completed | Exact task passes | Median s | Descriptive p95 s | Calls |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| bare | cold | 9 | 9 | 13.84 | 16.06 | 9 |
| bare | resident | 9 | 9 | 10.73 | 14.26 | 9 |
| rat_e2e | cold | 9 | 9 | 69.46 | 101.25 | 27 |
| rat_e2e | resident | 9 | 9 | 71.71 | 74.94 | 27 |
| rat_prompt | cold | 9 | 0 | 38.75 | 47.86 | 9 |
| rat_prompt | resident | 9 | 0 | 37.64 | 44.37 | 9 |

| Arm | Model state | Median load s | Median prompt s | Median generation s |
| --- | --- | ---: | ---: | ---: |
| bare | cold | 2.82 | 7.73 | 1.16 |
| bare | resident | 0.01 | 9.43 | 1.15 |
| rat_e2e | cold | 2.83 | 52.83 | 13.79 |
| rat_e2e | resident | 0.02 | 53.53 | 13.82 |
| rat_prompt | cold | 2.32 | 32.20 | 4.22 |
| rat_prompt | resident | 0.00 | 33.17 | 4.39 |

bare and rat_prompt receive the identical document and question. rat_prompt includes the native RAT prompt/tools but executes one generation only.
rat_e2e must actually find/read the artificial local file. Its time is a separate workflow measurement; do not interpret the entire difference as Python/app overhead.
Cold includes model loading. Resident uses an empty preload outside the measured task, with fresh KV in both states. OS disk caches are not controlled. Within-workflow prefix reuse is retained.
Server phase medians use only trials with complete phase fields; known-trial denominators are in summary.json. All wall-time rows retain failed tasks.
Prompt/completion counts include repeated/cached input and are not full inference costs. Load/control costs are saved separately in controls.jsonl.
Three documents and three observed repetitions do not establish general quality or a stable tail percentile. Case is the unit; repetitions are not new questions.
Arm order rotates by repetition. Background load, memory pressure and thermal effects remain potential confounders. No generation seed is fixed.
The app default, research pipeline and Stage 0 gate are unchanged. Raw per-call server phase timings and all errors remain in calls.jsonl.
