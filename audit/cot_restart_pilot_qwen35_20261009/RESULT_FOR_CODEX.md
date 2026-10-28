# RESULT_FOR_CODEX.md — Pilot CoT Restart Qwen3.5-4B

- **Execution Date**: 2026-10-09T12:01:51.604147+00:00
- **Status**: `complete`
- **Artifact Directory**: `/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/cot_restart_pilot_qwen35_20261009`
- **Model**: `mlx-community/Qwen3.5-4B-MLX-4bit` (revision `32f3e8ecf6`)
- **Runtime**: macOS Apple Silicon 16 GB, MLX 4-bit affine

## Quantitative Inventory
- **Total Model Calls**: 136 (ceiling: 136)
- **Total Completion Tokens**: 90197 (ceiling: 250000)
- **Canonical Questions**: 12 (4 arith, 4 order, 4 g24)
- **Initial Base CoT Accuracy**: 58.3% (7/12)
- **Rescue Denominator**: 5 initially wrong questions

## Arm Summary Across Budgets

| Arm | Budget | Accuracy | Rescued | Harmed | Trunc | Mean Total Tok |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `regenerate` | 1024 | 50.0% | 1/5 | 2/7 | 5 | 702 |
| `regenerate` | 2048 | 41.7% | 1/5 | 3/7 | 4 | 1068 |
| `restart_q025` | 1024 | 41.7% | 1/5 | 3/7 | 5 | 701 |
| `restart_q025` | 2048 | 66.7% | 2/5 | 1/7 | 3 | 1075 |
| `restart_q050` | 1024 | 50.0% | 2/5 | 3/7 | 4 | 703 |
| `restart_q050` | 2048 | 66.7% | 2/5 | 1/7 | 1 | 903 |
| `restart_q075` | 1024 | 58.3% | 1/5 | 1/7 | 3 | 656 |
| `restart_q075` | 2048 | 66.7% | 1/5 | 0/7 | 2 | 941 |
| `thinking_native` | 1024 | 0.0% | 0/5 | 7/7 | 12 | 1024 |
| `thinking_native` | 2048 | 8.3% | 1/5 | 7/7 | 11 | 2015 |

## Key Findings & Checkpoint Fidelity
1. Real assistant prefill continuation operates seamlessly via MLX and ChatML.
2. Conservative sentence boundary snapping successfully isolates partial rationale prefixes.
3. Token accounting strictly enforces budget = prompt + prefix + completion.
4. No confirmatory claims or Stage 0 amendments are made from this small sample.
5. Larger 24-question / 480-call batches remain on hold pending review.
