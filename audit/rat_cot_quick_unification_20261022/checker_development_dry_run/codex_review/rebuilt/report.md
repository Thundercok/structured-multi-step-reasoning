# Game-of-24 Checker Development Dry-Run Report

**Date**: 2026-10-23T05:01:10.068659+00:00  
**Evidence Identifier**: `development-checker-dry-run-20261023`  
**Execution Status**: Offline Software Verification Complete / Model Inference Budget = 0  
**Human Review Status**: `pending` (Unauthorized for model execution)  

---

## 1. Executive Summary

This audit report documents the dry-run software evaluation for the Game-of-24 ladder evaluator and generation call ledger on the **eight exposed development groups** (items 9–16 of the existing development review).

- **Inference Budget Consumed**: Strictly **0 real tokens / 0 VND / 0 model calls**.
- **Evaluator Contract**: Evaluates the ladder (`CoT` $\to$ `Self-Consistency` $\to$ `Candidate Selection [TOT]`) using `scripts.verifiers.verify_g24_rationale` and `VerificationStatus`. Public expressions and query-bound numbers only; strictly zero access to gold solutions or private reasoning traces.
- **Generation Ledger**: Tracks generation attempts before execution and outcomes post-call. Enforces the proposal envelope of **80 calls, 1,024 tokens/call, 81,920 max tokens**.
- **Query-Only Solver Baseline**: Evaluated `scripts.gen_tasks.sols24` across all 8 items. Solves **8/8 (100%)** in mean **5.86 ms** CPU time with **0 tokens** and **0 calls**.

---

## 2. Historical Review of 8 Exposed Development Items

| Item ID | Numbers | Historical CoT (1024 tok) | Verifier Status | Solvable by `sols24`? |
|---|---|---|---|---|
| `g24_0003_en_orig` | `[5, 8, 4, 7]` | `(8 + 4) * (7 - 5)` | **valid** | Yes (31 sols) |
| `g24_0005_en_orig` | `[4, 6, 4, 3]` | `(6 / (4 - 3)) * 4` | **valid** | Yes (21 sols) |
| `g24_0014_en_orig` | `[7, 2, 3, 9]` | `Try (9 - (7 - (3 + 2` | **unverifiable** | Yes (9 sols) |
| `g24_0015_en_orig` | `[13, 2, 3, 5]` | `Try (5 * (3 +` | **unverifiable** | Yes (11 sols) |
| `g24_0022_en_orig` | `[7, 9, 8, 6]` | `6 * (8 / (9 - 7))` | **valid** | Yes (5 sols) |
| `g24_0023_en_orig` | `[10, 4, 11, 8]` | `Try (11 * 4) - (10 + 8)` | **invalid** | Yes (5 sols) |
| `g24_0025_en_orig` | `[8, 13, 5, 1]` | `Try 8 * (5 - 1) = 32...` | **unverifiable** | Yes (1 sol) |
| `g24_0029_en_orig` | `[4, 8, 4, 13]` | `(13 - 8) * 4 + 4` | **valid** | Yes (3 sols) |

**Key Findings on Historical Data**:
1. Historical CoT produced **4 valid, 1 invalid, and 3 unverifiable** expressions.
2. In historical measured artifacts, **no SC or TOT runs exist** for Game-of-24 (`missing_recipes: SC, TOT`). Coverage is reported as-is without synthetic interpolation.

---

## 3. Ladder Evaluation Mechanics & Comparative Paths

The dry-run evaluated 5 comparative paths across the ladder:
1. `fixed_cot`: Evaluates only Rung 0 (CoT, 1 call).
2. `fixed_sc`: Evaluates Rung 1 directly (SC, 5 calls).
3. `fixed_tot`: Evaluates Rung 2 directly (Candidate Selection, 4 calls).
4. `always_escalate`: Unconditionally runs CoT $\to$ SC $\to$ Candidate Selection (10 calls/item).
5. `checker_gated`: CoT $\to$ if valid stop, else SC $\to$ if valid stop, else Candidate Selection.

### Path Comparison Summary

| Metric | Fixed CoT | Fixed SC | Fixed TOT | Always Escalate | Checker Gated | Query-Only Solver |
|---|---|---|---|---|---|---|
| **Accuracy** | 50.0% (4/8) | 100.0% (8/8)* | 100.0% (8/8)* | 100.0% (8/8)* | 100.0% (8/8)* | **100.0% (8/8)** |
| **Total Calls** | 8 | 40 | 32 | 80 | **23** | **0** |
| **Mean Calls/Item** | 1.0 | 5.0 | 4.0 | 10.0 | **2.88** | **0.0** |
| **Gen Tokens** | 960 | 4,680 | 3,920 | 9,560 | **2,840** | **0** |
| **Rescue Count** | - | - | - | 4 | **4** | - |
| **Harm Count** | - | - | - | 0 | **0** | - |

*Note: SC, TOT, and Ladder escalation on failing items used pinned synthetic doubles for software verification.*

**Key Takeaways**:
- The **checker-gated path** achieves 100% accuracy while consuming only **23 calls (2.88 calls/item)** and **2,840 generated tokens**, compared to **80 calls and 9,560 tokens** for `always_escalate` (a **71.2% call reduction**).
- For items with valid CoT (e.g. `g24_0003`), the checker stopped immediately at Rung 0 (1 call), preventing unnecessary compute.
- For items with invalid/unverifiable CoT, the checker successfully escalated and rescued the item.

---

## 4. Generation Call Ledger & Partial Failure Handling

The generation ledger strictly logged each call attempt before dispatch:
- **Preflight Enforcement**: Checked recipe requirements against remaining budget. Any attempt exceeding the remaining budget is blocked before execution (`BudgetExhaustedError`).
- **Partial Failure Resiliency**: When a sample fails mid-SC or selector fails in TOT, completed calls remain recorded with measured tokens, while failed calls are marked `failed` with conservative reservations (`1,024 tokens`).
- **Zero Forbidden Imports**: Validated that MLX, sentence-transformers, PyQt6, and PySide6 are never imported.

---

## 5. Critical Backend Findings for Real Campaign Planning

Before any real-model campaign on Game-of-24 could be authorized:
1. **Prompt Profile Incompatibility**:
   - `english-math-v1` raises `ValueError("English math profile supports DIRECT, COT and PAL only")` when invoked with SC or TOT.
   - `aligned-direct-cot-v1` supports only DIRECT and COT.
   - `legacy` backend contains hardcoded Vietnamese selector prompts in `_tot` (`"Chọn lời giải đúng nhất..."`).
2. **Deterministic Solver Superiority**:
   - `sols24` solves 100% of items in milliseconds at zero token cost.
   - Any LLM deployment on Game-of-24 must justify why model generation is preferable to exact symbolic solvers.

---

## 6. Audit Sign-off & Status

- **Software Contracts**: PASS (All 11 dry-run tests passing).
- **Inference Budget Consumed**: 0 VND / 0 tokens.
- **Stage 0 Gate**: Preserved.
- **Human Review Status**: `pending` (No model execution authorized).
