# Overnight RAT–CoT Repair Follow-up Handoff (Round 5)

**Date**: 2026-10-19  
**Branch**: `main` (solo Git workflow, 0 commits, 0 pushes, 0 branch creations)  
**System Architecture**: RAT–CoT Unified System (NCKH Student Research Implementation)  
**Directory**: `audit/rat_overnight_sweep_codex_repair_r5_20261019/`  

---

## 1. Executive Summary

This repair cycle directly addresses and resolves all three P2 findings identified in independent review r5 (`audit/rat_overnight_sweep_codex_review_r5_20261019/review.md`):
1. **E1 (Parser)**: Multi-clause expressions with rational conclusions (e.g. `Answer: 2 + 2 = 4; 1 / 4 = 1/4` and `Therefore 2 + 2 = 4; 1 / 4 = 1/4`) now evaluate the terminal conclusion clause first before scalar extraction. When the final conclusion is a rational/expression, the expression is preserved without prematurely extracting intermediate scalar results (`4`).
2. **E2 (Provenance Classification)**: Removed unsafe heuristics in `classify_record_backend` that previously inferred real model inference from non-zero timings or large prompt token counts (`prompt_tokens >= 500`). Unverified legacy records return `"unknown"`; real classification strictly requires verified provenance.
3. **E3 (Current-run Execution Counters & Budget Halt on Fake History)**: `fake_model_calls_executed` strictly reflects requests dispatched during the current process invocation (`new_fake_executed`). When budget guard halts on existing fake history (`fake_history_halt`), `fake_model_calls_executed = 0`, status records `budget_halt_existing_fake_history`, warm generation latency evaluates to `null`, and historical counts are segregated into `historical_ledger_totals`.

### Verification Highlights
- **10/10 probes passed** in `audit/rat_overnight_sweep_codex_review_r5_20261019/test_provenance_and_conclusion.py` (up from 6 pass / 4 fail in review r5).
- **319/319 consolidated test suite passed** in 35.15s (0 failures, 0 errors, 0 skips) recorded in `regression.txt` and `regression.xml`.
- **29/29 mandatory research tests passed** in 3.88s (`test_research_study.py`, `test_optimal_stopping.py`, `test_entry_predictor.py`).
- **44/44 parser and research scoring tests passed** in 2.83s (`test_reasoning_strategies.py`, `tests/test_research_scoring.py`).
- **0 real-model inference calls dispatched**; the locked 12-call historical ledger remains byte-identical with SHA256 `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`.
- **Zero UI regressions, zero Git commits/pushes/branching**. Exactly two production files were modified.

---

## 2. Technical Implementation Details

### E1: Terminal Conclusion Clause Evaluation in `reasoning/reasoning_strategies.py`
- **Root Cause**: `_clean_cand` and `extract_conclusion_number` previously executed regex matches (`EQUALS_RESULT.findall(norm)`) across the entire string before checking if the terminal conclusion was an expression. For strings containing intermediate equations followed by fractions (`2 + 2 = 4; 1 / 4 = 1/4`), the regex matched `= 4` (since `4;` is followed by `;`, not an arithmetic operator) and failed on `= 1/4` (since `1` is followed by `/`), returning `'4'` as the intermediate scalar.
- **Fix**:
  1. Both `_clean_cand` and `extract_conclusion_number` now partition the candidate text into clauses separated by `;` or `\n` (`clauses = [c.strip() for c in re.split(r"[;\n]", norm) if c.strip()]`) and isolate the terminal clause (`target = clauses[-1]`).
  2. Inspect the right-hand side of the target clause: `rhs = target.rsplit("=", 1)[-1].strip()`.
  3. If `rhs` contains arithmetic operators (`+`, `*`, `/`, `×`, `÷`) or non-unary minus, it is recognized as an expression (`is_expr = True`) and preserved directly (`return norm`).
  4. Only when the terminal clause is confirmed not to be an expression does the parser extract scalar numbers via `EQUALS_RESULT`, `TRAILING_NUMERIC_RESULT`, or `extract_conclusion_number`.
- **Verification**: `test_final_conclusion_not_earlier_intermediate_scalar` (4/4 pass, covering marker rational, fallback rational, single rational control, and final integer control).

### E2: Strict Provenance Classification in `scripts/run_native_performance_session.py`
- **Root Cause**: `classify_record_backend` previously inspected whether records had `first_token_ms`, `prefill_ms`, `generation_ms`, or `prompt_tokens >= 500`. However, `FakeMLXDocumentSession` also measures timings and processes document text producing 2031 prompt tokens. In review r3, a genuine fake run emitted those exact fields without a `backend_type` tag, causing the classifier to misclassify it as `real`.
- **Fix**:
  1. Removed timing and prompt token heuristics completely from `classify_record_backend`.
  2. If `backend_type` is present (`"fake"` or `"real"`), return it.
  3. If `model_id` contains `"mock"` or `"fake"`, return `"fake"`.
  4. Only classify as `"real"` if the record possesses verified real-model provenance: explicit real model path (`"qwen3.5"`, `"mlx-community"`) or the authentic 12-call historical ledger provenance signature (`rat_native_perf_f9mhsshs`).
  5. All unverified legacy records return `"unknown"`.
- **Verification**: `test_backend_provenance_never_inferred_real_from_timing_or_token_count` (4/4 pass, verifying `legacy-captured-fake` returns `unknown`, `explicit-fake` returns `fake`, `explicit-real` returns `real`, and `no-provenance` returns `unknown`).

### E3: Process Execution Counters and Halt Statuses in `scripts/run_native_performance_session.py`
- **Root Cause**: When running `--fake-backend` on an existing fake ledger where the budget limit was already reached, `new_fake_executed` was 0, but the fallback branch set `fake_calls_count = len(ledger_fake_records)` (`1`), incorrectly reporting `offline_fake_backend_completed_1_calls`.
- **Fix**:
  1. `fake_calls_count = new_fake_executed`: current-run execution count strictly tracks requests dispatched by the current process invocation.
  2. When `new_fake_executed == 0`:
     - If `len(ledger_real_records) > 0`: status is `"budget_halt_existing_real_history"`.
     - If `len(ledger_fake_records) > 0`: status is `"budget_halt_existing_fake_history"`.
     - Else: status is `"budget_halt_existing_unknown_history"` or `"budget_halt_existing_ledger"`.
  3. Set `relevant_for_warm = []` when halted, ensuring `warm_generation_latency_ms` evaluates to `None` and does not borrow samples from previous process runs.
  4. Segregated historical ledger counts into a dedicated dictionary: `historical_ledger_totals` (`completed_records`, `real_records`, `fake_records`, `unknown_records`).
- **Verification**: `test_executed_fake_count_describes_current_run` (2/2 pass, verifying `fake_session` reports 1 and `fake_history_halt` reports 0).

---

## 3. Session Replay Artifacts & Ledger Preservation

All three session replay cases were executed and captured in `audit/rat_overnight_sweep_codex_repair_r5_20261019/`:

1. **`fake_session/`**:
   - Command: `.venv/bin/python scripts/run_native_performance_session.py --fake-backend --max-budget 1 --output-dir .../fake_session`
   - Outcome: 1 fake request dispatched; `fake_model_calls_executed: 1`, `real_model_calls_executed: 0`, status `offline_fake_backend_completed_1_calls`, `warm_generation_latency_ms: null`.
2. **`fake_history_halt/`**:
   - Command: Copied `fake_session/calls.jsonl`, then executed `.venv/bin/python scripts/run_native_performance_session.py --fake-backend --max-budget 1 --output-dir .../fake_history_halt`
   - Outcome: Budget guard halted immediately (`BUDGET GUARD HALT: Global budget limit reached (1/1). No new requests will be dispatched.`); `fake_model_calls_executed: 0`, `real_model_calls_executed: 0`, status `budget_halt_existing_fake_history`, `warm_generation_latency_ms: null`. `calls.jsonl` verified byte-identical to `fake_session/calls.jsonl`.
3. **`locked_ledger_replay/`**:
   - Command: Copied authentic 12-call `calls.jsonl`, then executed `.venv/bin/python scripts/run_native_performance_session.py --fake-backend --max-budget 12 --output-dir .../locked_ledger_replay`
   - Outcome: Budget guard halted immediately (`BUDGET GUARD HALT: Global budget limit reached (12/12). No new requests will be dispatched.`); `fake_model_calls_executed: 0`, `real_model_calls_executed: 0`, status `budget_halt_existing_real_history`, `warm_generation_latency_ms: null`. `calls.jsonl` verified byte-identical with SHA256 `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`.

---

## 4. Test Suite Summary

| Test Suite / Probe Group | Command / Script | Tests | Pass | Fail | Error | Skip | Duration |
|---|---|---|---|---|---|---|---|
| **Consolidated Acceptance Suite** | `.venv/bin/python audit/.../run_consolidated.py` | **319** | **319** | **0** | **0** | **0** | 35.15s |
| **Review r5 Probes** | `pytest test_provenance_and_conclusion.py` | **10** | **10** | **0** | **0** | **0** | 0.08s |
| **Review r4 Edge Probes** | `pytest test_final_edges.py` | **7** | **7** | **0** | **0** | **0** | 0.08s |
| **Review r3 Remaining Probes** | `pytest test_remaining_probes.py` | **13** | **13** | **0** | **0** | **0** | 0.08s |
| **Mandatory Research Suite** | `pytest test_research_study.py test_optimal_stopping.py test_entry_predictor.py` | **29** | **29** | **0** | **0** | **0** | 3.88s |
| **Parser & Research Scoring** | `pytest test_reasoning_strategies.py test_research_scoring.py` | **44** | **44** | **0** | **0** | **0** | 2.83s |

---

## 5. Source File Manifests

Exactly 51 files are tracked across `source_start.json` and `source_end.json`. Only two production files were modified:

| Relative Path | Pre-repair SHA256 (`source_start.json`) | Post-repair SHA256 (`source_end.json`) | Status |
|---|---|---|---|
| `reasoning/reasoning_strategies.py` | `99eb8b9a9ce4bfe29eec92fa2c911653b0ac7f30cf5c705f9bce78777734eee8` | `54035407936a5ea976dfbf139049a37703399fc7104b901a520fa169f9e31d4d` | Modified (E1) |
| `scripts/run_native_performance_session.py` | `9bfff44967234927c737d063d5e8525210887b6f9c202314c4df3f9760fef042` | `74ce9b4360e2ce1c27da50493ae070f8b1b9e84fc8654c86a3d132b388b0a99d` | Modified (E2, E3) |
| *(49 other tracked files)* | *(identical)* | *(identical)* | Unchanged |

Full unified diff is preserved in [`repair_diff.patch`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_overnight_sweep_codex_repair_r5_20261019/repair_diff.patch).

---

## 6. Open Items & Research Guardrails

1. **Native Interactive Scenarios**: Full Cocoa display streaming, live NSWindow compositor sync, user cancellation during prefill/decode, and window hotkey toggling remain unmeasured/blocked without a dedicated display server. They are accurately documented in `unverified_native_scenarios` and `unmeasured_fields`.
2. **Real Model Generation Budget**: The 12 authentic real-model requests from the initial overnight sweep remain frozen and preserved byte-for-byte. Zero new real-model generation requests were issued.
3. **Stage 0 Research Gate**: Stage 0 remains active. Offline heuristics and parser improvements uphold rigorous evaluation without altering typed scoring standards or gold benchmark data.
