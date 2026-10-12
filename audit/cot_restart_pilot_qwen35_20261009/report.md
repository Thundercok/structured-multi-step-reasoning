# CoT Restart Development Pilot Report (Qwen3.5-4B 4-bit)

> [!IMPORTANT]
> **Exposed Development Only**: This pilot was executed exclusively on 12 canonical questions from
> the exposed `data/gen02_tune.json` pool. It is an exploratory diagnostic to measure feasibility and
> mechanics on Apple Silicon (Mac 16 GB). It does NOT constitute held-out validation, confirmatory evidence,
> or an amendment to Stage 0.

## Model & Runtime Provenance
- **Model Repository**: `mlx-community/Qwen3.5-4B-MLX-4bit`
- **Base Model**: `Qwen/Qwen3.5-4B`
- **Revision**: `32f3e8ecf65426fc3306969496342d504bfa13f3`
- **Quantization**: `{'bits': 4, 'group_size': 64, 'mode': 'affine'}`
- **Platform**: `macOS-26.5.2-arm64-arm-64bit` (arm64)
- **Python**: `3.12.6 (v3.12.6:a4a2d2b0d85, Sep  6 2024, 16:08:03) [Clang 13.0.0 (clang-1300.0.29.30)]`
- **Total Model Calls**: 136
- **Total Completion Tokens**: 90197

## Base Visible CoT Trace Outcomes (12 Canonical Questions)
- **Initial Accuracy**: 58.3% (7/12)
- **Initially Wrong (Rescue Denominator)**: 5

| ID | Family | Base Outcome | Truncated? | Boundary Count | Distinct Menu Prefixes |
| --- | --- | --- | --- | --- | --- |
| `arith_0023_en_orig` | arith | Correct | No | 6 | 4 |
| `arith_0027_en_orig` | arith | Correct | No | 8 | 4 |
| `arith_0032_en_orig` | arith | Correct | No | 10 | 4 |
| `arith_0039_en_orig` | arith | Wrong | No | 14 | 4 |
| `g24_0014_en_orig` | g24 | Wrong | Yes | 88 | 4 |
| `g24_0018_en_orig` | g24 | Correct | No | 19 | 4 |
| `g24_0023_en_orig` | g24 | Wrong | Yes | 88 | 4 |
| `g24_0028_en_orig` | g24 | Correct | No | 12 | 4 |
| `order_0004_en_orig` | order | Correct | No | 41 | 4 |
| `order_0006_en_orig` | order | Wrong | No | 47 | 4 |
| `order_0012_en_orig` | order | Correct | No | 35 | 4 |
| `order_0027_en_orig` | order | Wrong | Yes | 62 | 4 |

## Restart Configurations & Budgets Comparison

| Config / Arm | Budget | Accuracy | Rescue (den=5) | Harm (den=7) | Trunc | Infeasible | Prompt Tok | Comp Tok | Total Tok | Timing (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `regenerate` | 1024 | 50.0% | 1/5 (20.0%) | 2/7 (28.6%) | 5 | 0 | 130 | 572 | 702 | 100616 |
| `regenerate` | 2048 | 41.7% | 1/5 (20.0%) | 3/7 (42.9%) | 4 | 0 | 130 | 938 | 1068 | 181506 |
| `restart_q025` | 1024 | 41.7% | 1/5 (20.0%) | 3/7 (42.9%) | 5 | 0 | 260 | 441 | 701 | 89356 |
| `restart_q025` | 2048 | 66.7% | 2/5 (40.0%) | 1/7 (14.3%) | 3 | 0 | 260 | 815 | 1075 | 165195 |
| `restart_q050` | 1024 | 50.0% | 2/5 (40.0%) | 3/7 (42.9%) | 4 | 0 | 392 | 311 | 703 | 62100 |
| `restart_q050` | 2048 | 66.7% | 2/5 (40.0%) | 1/7 (14.3%) | 1 | 0 | 392 | 511 | 903 | 90827 |
| `restart_q075` | 1024 | 58.3% | 1/5 (20.0%) | 1/7 (14.3%) | 3 | 0 | 520 | 136 | 656 | 35495 |
| `restart_q075` | 2048 | 66.7% | 1/5 (20.0%) | 0/7 (0.0%) | 2 | 0 | 520 | 421 | 941 | 74618 |
| `thinking_native` | 1024 | 0.0% | 0/5 (0.0%) | 7/7 (100.0%) | 12 | 0 | 110 | 914 | 1024 | 163964 |
| `thinking_native` | 2048 | 8.3% | 1/5 (20.0%) | 7/7 (100.0%) | 11 | 0 | 110 | 1905 | 2015 | 319289 |

## Cost Separation: Collection vs. Hypothetical Selected Path
- **Full Collection Cost**: 136 calls, 90197 completion tokens.
- **Hypothetical Path Cost**: Each item on a standalone policy path executes only its specific prefix call.
  Prefill tokens are accounted for in total budget ceiling.

## Scientific Notes & Limitations
- One draw per cell: exploratory feasibility only, not confirmatory.
- No per-item gold oracle claims.
- Deduplication was strictly applied to identical snapped prefixes.
- Next steps: Full review of pilot findings before running 24-question / 480-call batches.
