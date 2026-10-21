# Handoff Report — Overnight RAT–CoT System Repair (Round 4)

**Date**: 2026-10-19  
**Branch**: `main` (solo Git workflow strictly preserved, zero commits/pushes/resets/branches)  
**Verdict**: **Ready for Review** — Both remaining findings (D1, D2) resolved and verified; **309/309 tests passing** (0 failures, 0 errors, 0 skipped); **0 new real-model requests executed** (historical 12-call ledger byte-identical).

---

## 1. Executive Summary & Verification Metrics

Following the independent review in `audit/rat_overnight_sweep_codex_review_r4_20261019/review.md`, this repair cycle addressed the final two software/offline edge cases:
1. **D1**: Unified rational/fraction conclusion preservation across both marker and fallback extraction paths.
2. **D2**: Request-linked session provenance separation ensuring `--fake-backend --max-budget 12` budget-guard halting on real-model ledger history emits `fake_model_calls_executed: 0` and null warm stats.

| Audit Metric | Status / Value |
|---|---|
| **Consolidated Test Suite** | **309 passed**, 0 failed, 0 errors, 0 skipped (in `regression.xml`) |
| **New Review r4 Probes (`test_final_edges.py`)** | **7/7 passed** (trước: 3 fail / 4 pass) |
| **Review r3 Probes (`test_remaining_probes.py`)** | **13/13 passed** |
| **Parser / Backend / Scoring Checks** | **70 passed**, 0 failed (`test_reasoning_strategies.py`, `test_qwen_mlx_backend_mocked.py`, `tests/test_research_scoring.py`) |
| **Mandatory Research Suite (AGENTS.md)** | **29 passed**, 0 failed (`tests/test_research_study.py`, `test_optimal_stopping.py`, `test_entry_predictor.py`) |
| **New Real-Model Requests** | **0** (strictly zero model calls made; budget gate respected) |
| **12 Real Calls Ledger SHA256** | `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34` (Byte-identical to previous cycles) |
| **QPA Platform** | `offscreen` |
| **Git Working Tree** | Strict solo workflow on `main`; 0 commits, 0 branch creations |

---

## 2. Detailed Technical Fixes (D1, D2)

### D1 — Unified Fallback Fraction & Expression Preservation (`reasoning/reasoning_strategies.py`)
- **Root Cause**:
  1. In `parse_answer_details`, the marker path called `_clean_cand`, but the fallback path called `extract_conclusion_number` directly, bypassing rational preservation rules.
  2. In `extract_conclusion_number`, presence of conclusion cues (e.g. `"therefore"`, `"do đó"`) triggered `extract_number(text)`, which extracted the last numeric token (e.g. denominator `4` from `"Therefore x = 3/4"`).
  3. In regex matching, optional decimal lookaheads permitted regex backtracking to split numbers across decimal points (e.g. matching prefix `3` from `x = 3.25/4` because the decimal point wasn't immediately followed by `/`).
- **Resolution**:
  - In `parse_answer_details`, unified the fallback path to route normalized candidate text through `_clean_cand(norm)`.
  - In `extract_conclusion_number` and `_clean_cand`, inspected the conclusion/RHS: if it contains arithmetic operators (`/`, `*`, `+`, `÷`, `×`) or non-leading minus, the scalar conclusion extractor returns `None` and `_clean_cand` preserves the raw equation/expression.
  - Hardened `EQUALS_RESULT` and `TRAILING_NUMERIC_RESULT` to require `(?!\.?\d)(?!\s*[/÷×*+-])`, preventing backtracking from splitting numbers across decimal points or mistaking numerators for isolated scalars.
- **Verification**: `test_fallback_and_marker_paths_preserve_fraction_value` in `test_final_edges.py` passes all 4 parameterizations (`conclusion-cue-fallback` `Fraction(3, 4)`, `decimal-numerator-fallback` `Fraction(13, 16)`, `answer-marker-control` `Fraction(3, 4)`, and `bare-equation-control` `Fraction(3, 4)`). `test_reasoning_strategies.py` and `tests/test_harness_regressions.py` pass 21/21.

### D2 — Telemetry Provenance & Budget-Halt Classification (`scripts/run_native_performance_session.py`)
- **Root Cause**: The runner previously inferred record backend type solely from `args.fake_backend` of the current process invocation (`fake_calls_count = len(completed_records)`). When running `--fake-backend --max-budget 12` on a copy of the 12-call real ledger, the budget guard halted without dispatching any requests, but the summary falsely reported `fake_model_calls_executed: 12` and attributed the real latencies to mock warm stats.
- **Resolution**:
  - Introduced explicit per-request provenance tagging: `start_entry` and `complete_entry` include `session_id` and `backend_type: "fake" | "real"`.
  - Added `classify_record_backend(rec)` to inspect existing ledger records: legacy records containing MLX generation metrics (`first_token_ms`, `prefill_ms`, `prompt_tokens >= 500`) are verified as `"real"` rather than inheriting the current CLI flag.
  - Separated current session executions from historical ledger totals:
    - If `new_fake_executed > 0`: `fake_model_calls_executed = new_fake_executed`, status `offline_fake_backend_completed_{n}_calls`.
    - If budget guard halts on existing real history (`new_fake_executed == 0`): `fake_model_calls_executed = 0`, status `budget_halt_existing_real_history`, `warm_generation_latency_ms = None`.
    - Real-model metrics and warm latencies are never aggregated into mock simulation summaries.
- **Verification**: `test_cli_mode_does_not_relabel_historical_calls` passes both `fresh-fake-control` (expecting 1 new fake call) and `budget-halt-on-real-history` (expecting 0 new fake calls). The 13 probes in `test_remaining_probes.py` also pass 13/13.

---

## 3. Test & Verification Matrix

### A. Consolidated Test Suite (309/309 Passed)
Run via:
```bash
QT_QPA_PLATFORM=offscreen \
RAT_REVIEW_R4_OUTPUT_DIR=audit/rat_overnight_sweep_codex_repair_r4_20261019 \
RAT_REVIEW_FAKE_OUTPUT_DIR=audit/rat_overnight_sweep_codex_repair_r4_20261019/fake_session \
.venv/bin/python -m pytest \
  tests/test_progressive_search.py \
  tests/test_mlx_document_session.py \
  tests/test_selected_document_qa.py \
  tests/test_selected_document_ui.py \
  tests/test_workbench_scene.py \
  tests/test_rat_completion_reconciliation.py \
  tests/test_rat_completion_boundaries.py \
  tests/test_document_model_startup.py \
  tests/test_rat_magic_ui.py \
  tests/test_research_study.py \
  test_optimal_stopping.py \
  test_entry_predictor.py \
  tests/test_assistant_runtime.py \
  tests/test_rat_headless_cli.py \
  tests/test_resident_warmup.py \
  audit/rat_finder_codex_review_20261016/test_finder_integration_probes.py \
  audit/rat_finder_codex_review_r2_20261017/test_keyboard_followups.py \
  audit/rat_milestones_abc_independent_review_20261018/test_review_probes.py \
  audit/rat_milestones_abc_independent_review_20261018/test_ui_review_probes.py \
  audit/rat_milestones_abc_review_r2_20261018/test_additional_headless.py \
  audit/rat_milestones_abc_review_r2_20261018/test_additional_ui.py \
  audit/rat_milestones_abc_review_r3_20261019/test_slide_summary_projection.py \
  audit/rat_overnight_sweep_codex_review_20261019/test_visual_acceptance.py \
  audit/rat_overnight_sweep_repair_codex_review_20261019/test_followup_acceptance.py \
  tests/test_crash_shield.py \
  tests/test_harness_regressions.py \
  audit/rat_overnight_sweep_codex_review_r3_20261019/test_remaining_probes.py \
  audit/rat_overnight_sweep_codex_review_r4_20261019/test_final_edges.py \
  -q --junitxml=audit/rat_overnight_sweep_codex_repair_r4_20261019/regression.xml
```
**Result**: `309 passed in 43.00s` (0 failures, 0 errors, 0 skipped).

### B. Affected Parser & Scoring Suite (70/70 Passed)
Run unsandboxed:
```bash
.venv/bin/python -m pytest test_reasoning_strategies.py test_qwen_mlx_backend_mocked.py tests/test_research_scoring.py -q
```
**Result**: `70 passed in 6.39s`.

### C. Mandatory Research Suite (29/29 Passed)
Run per `AGENTS.md`:
```bash
.venv/bin/python -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q
```
**Result**: `29 passed in 3.65s`.

---

## 4. Contract-Level Analysis of the 16 Stale Test Failures

As documented in previous rounds, the 16 stale test failures across the full 132-file inventory reflect architectural schema updates and localized string changes:
1. `tests/test_reranker_golden.py` (1 case): Asserts 20 features; production schema incorporates 25 features. All 200 golden score values, additive bounds, and monotonic ranking invariants pass identically under the 25-feature schema (proven by probe).
2. `tests/test_query_compounds.py` (7 keyword cases): `ContextParser.parse_query` invokes `curriculum_mapper.expand()` for student query resolution, injecting course codes into `keywords`. Compound phrase preservation (`"giai tich"`) remains intact.
3. `tests/test_query_compounds.py` (1 score case): Document `.pptx` extension matches slide boost heuristic (+40), yielding 100 rather than legacy asserted 60.
4. `tests/test_vgc_cascade.py` (6 cases):
   - Division by zero evaluates to `UNVERIFIABLE` rather than `INVALID`.
   - Reason strings localized to Vietnamese (lacking English substrings `"verified"`, `"mismatch"`).
   - Strict verifier fails closed with `INVALID` on `10 / 3` with claim `"3.3333"` due to strict floating-point precision.
   - Exact excerpt inclusion contract evaluates to `UNVERIFIABLE` when truncated snippet `source[:50]` does not span the full claim.
   - Fast quantitative resolution evaluates `res.confidence` to `None`.
5. `tests/test_vgc_ui_integration.py` (1 case): Asserts legacy VGC certificate status `"valid"` instead of production `ReconciliationReport` / `WorkSceneSnapshot` semantics.

---

## 5. Artifact Manifest & Directory Layout

All audit records, diffs, telemetry, and manifests are preserved in:
`audit/rat_overnight_sweep_codex_repair_r4_20261019/`

- `command.json`: Complete execution arguments and environment variables for the 309-test consolidated regression.
- `regression.xml`: JUnit XML report confirming **309 passed**, 0 failures, 0 errors, 0 skipped.
- `calls.jsonl`: Locked 12-call ledger of historical real-model inference (`556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`).
- `native_performance.json`: Telemetry metrics preserving historical 12-call measurement baseline with unmeasured fields properly annotated as `null`.
- `rat_cot_evidence_map.md`: Verified AST symbol map citing `QtViewRenderer._render_input_form` and candidate stem disambiguation.
- `source_start.json`: 55-file manifest matching review r4 `source_end.json`.
- `source_end.json`: Actual SHA256 hashes of all files, confirming exactly 2 modified source files during repair:
  - `reasoning/reasoning_strategies.py`
  - `scripts/run_native_performance_session.py`
- `repair_diff.patch`: Unified diff against `reviewed_source/` of review r4.
- `fake_session/`: Dedicated offline simulation output (`--fake-backend --max-budget 1`) confirming `fake_model_calls_executed: 1`, `warm_generation_latency_ms: null`.
- `locked_ledger_replay/`: Dedicated budget-guard replay on 12-call real ledger confirming `fake_model_calls_executed: 0`, `calls.jsonl` unmodified byte-identical, `warm_generation_latency_ms: null`.
- `validation.json`: Summary verdict and findings verification record.

---

## 6. Open Scopes & Boundaries

1. **Interactive GUI Execution**: Live token streaming into a visible Cocoa NSWindow, mid-generation user cancellations via Esc, file modification invalidations, and outside-excerpt queries remain unmeasured in live GUI mode (`not_run / blocked`) due to headless offscreen execution environment.
2. **Research Harness Separation**: `OptimalStoppingPolicy` and `EntryPredictor` are evaluated offline in the headless research harness; they are not wired into live MLX token streaming decode.
