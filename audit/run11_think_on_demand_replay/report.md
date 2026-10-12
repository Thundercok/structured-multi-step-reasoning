# Run 11 think-on-demand replay (development only)

**Evidence status:** exposed development, post-hoc replay only. This is not a held-out result, a confirmatory run, or evidence that Stage 0 passed.

The replay covers 71 arithmetic/ordering items. Game-of-24 is excluded from the reconstructed policy. `CoT` means a prompt-elicited visible rationale with `enable_thinking=false`; it is not hidden chain-of-thought access.

| Method | Correct | Accuracy [group-bootstrap 95% CI] | Logged token proxy | Utility | Escalations | Rescue / harm vs CoT |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `fixed_direct` | 12/71 | 0.169 [0.085, 0.268] | 113.0 | 0.167 | 0 | 2 / 34 |
| `fixed_cot` | 44/71 | 0.620 [0.507, 0.732] | 483.1 | 0.610 | 0 | 0 / 0 |
| `fixed_tot` | 51/71 | 0.718 [0.606, 0.817] | 1214.9 | 0.694 | 0 | 9 / 2 |
| `posthoc_metadata_pal_tot` | 61/71 | 0.859 [0.775, 0.930] | 936.3 | 0.840 | 0 | 19 / 2 |
| `frozen_policy_v_recorded` | 54/71 | 0.761 [0.662, 0.859] | 1498.3 | 0.731 | 30 | 12 / 2 |
| `frozen_policy_v_checker_rescore` | 56/71 | 0.789 [0.690, 0.873] | 1498.3 | 0.759 | 30 | 14 / 2 |
| `posthoc_think_on_demand_fail_open` | 62/71 | 0.873 [0.789, 0.944] | 1021.1 | 0.853 | 20 | 19 / 1 |
| `posthoc_think_on_demand_fail_closed` | 61/71 | 0.859 [0.775, 0.930] | 1100.2 | 0.837 | 23 | 19 / 2 |

## What the 87.3% number means

The tracked reconstruction reproduces **62/71 = 87.324%**, 1021.1 logged tokens/item, utility 0.853, and 19 rescues with 1 harm. It routes arithmetic directly to PAL and routes ordering through CoT, escalating to the legacy `TOT` arm when the legacy verifier flags or CoT hits its cap.

That rule was reconstructed after inspecting Run 11. It differs from frozen Policy V, which uses PAL for arithmetic and SC for ordering after a CoT flag. It also uses dataset family labels and canonical structured ordering metadata, so routing/parsing errors are not measured.

The fail-closed tri-state variant counts unextractable ordering rationales as escalation-worthy and obtains **61/71 = 85.915%** with a logged proxy of 1100.2 tokens/item. This is a safety-oriented exploratory replay, not a newly validated policy.

## Measurement limitations

- The trace was generated in one warm model session, not as 571 independent cold starts.
- SC and the legacy `TOT` arm used nonzero-temperature sampling without a recorded generation seed. Raw replay is deterministic; identical regeneration is not guaranteed.
- `prompt_tokens` is recorded once for SC (five calls) and legacy `TOT` (three candidates plus a selector). Therefore the table's prompt+completion quantity is an **incomplete logged token proxy**, not full inference cost. Selector input tokens cannot be reconstructed from the trace.
- `wall_ms` values are saved arm timings replayed from the historical run. Their sums are not measured online controller latency.
- Frozen checker rescoring disagrees with 8 SC rows because the runner invalidated the whole SC result when any branch hit length. Both recorded and rescored Policy V variants are shown; neither is confirmatory.
- A symbolic verifier checks consistency of a visible trace. It does not establish causal rationale faithfulness.

## Provenance

- Run 11 trace SHA-256: `3d57df7f4e81c71513a30b46a190c2d848ea020dac78adf88776620b6e67e632`
- Exposed dataset SHA-256: `f3bfa9750038ecce95f31dcdd7362082c4d85487d37ff091282442874a12041c`
- Cascade preregistration SHA-256: `8b8cd86c19c6b843a80d643211761ea6afa5edf59b801236f105f6ccd60ed3c4`
- Model recorded by every row: `mlx-community/Qwen3-8B-4bit`
- Historical source commit recorded by every row: `d6f7d32`

Next evidence step: freeze a prospective policy and corrected telemetry before collecting a fresh, non-overlapping development replication. Do not promote this replay into a paper claim.
