# Overnight RAT–CoT Repair Follow-up Handoff (Round 6)

**Date**: 2026-10-20  
**Branch**: `main` (solo Git workflow, 0 commits, 0 pushes, 0 branch creations)  
**System Architecture**: RAT–CoT Unified System (NCKH Student Research Implementation)  
**Directory**: `audit/rat_overnight_sweep_codex_repair_r6_20261020/`  

---

## 1. Executive Summary

This repair cycle directly resolves both findings (F1 and F2) identified in independent review r6 (`audit/rat_overnight_sweep_codex_review_r6_20261020/review.md`):

1. **F1 (Strict Provenance Classification)**: Removed substring heuristics in `classify_record_backend` (`model_path` contains `"qwen3.5"` / `"mlx-community"`, `document_path` contains `"rat_native_perf_f9mhsshs"`). Records are classified as `"real"` only if they contain explicit `backend_type == "real"` or match verified 12-call historical review signatures `(call_index, timestamp_utc) in VERIFIED_REAL_CALL_SIGNATURES`. Synthetic fixtures derived from fake records that modify only path metadata evaluate to `"unknown"` (or `"fake"`), and replay halts report `historical_ledger_totals.real_records: 0`.
2. **F2 (Current-Run Isolation in Real Mode)**: Replaced fallback logic in the real reporting branch (`real_calls_count = len(ledger_real_records)` and warm sample borrowing from prior sessions). `real_calls_count` now strictly tracks requests dispatched by the current process invocation (`new_real_executed`). When the budget guard halts on existing real history with 0 new requests dispatched, `real_calls_count = 0`, status records `budget_halt_existing_real_history`, and `relevant_for_warm = []` (`warm_generation_latency_ms = None`).

### Verification Highlights
- **8/8 review r6 probes passed** in `audit/rat_overnight_sweep_codex_review_r6_20261020/test_legacy_identity_and_real_history.py` (0.09s, 4 path text variants, 1 end-to-end replay, 3 real mode counting controls).
- **327/327 consolidated test suite passed** in 44.88s (0 failures, 0 errors, 0 skips), recorded in `regression.txt` and `regression.xml`.
- **29/29 mandatory research tests passed** in 3.01s (`test_research_study.py`, `test_optimal_stopping.py`, `test_entry_predictor.py`).
- **44/44 parser and research scoring tests passed** in 3.06s (`test_reasoning_strategies.py`, `tests/test_research_scoring.py`).
- **5 session replays executed cleanly** (`fake_session`, `locked_ledger_replay`, `fake_history_halt`, `legacy_fake_history_halt`, `same_document_legacy_fake`).
- **0 new real-model requests executed**; historical 12-call ledger remains byte-identical with SHA256 `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`.
- **External change preserved**: `rat/ui/omnibar.py` (SHA256 `72d9b746754083662e21982b885c2a910024fcb835eb1f89354f3314fed09d7a`, mtime 00:27:06 UTC) preserved without revert or overwrite.
- **Single production file modified**: `scripts/run_native_performance_session.py`.
- **Zero Git commits/pushes/branching**.

---

## 2. Technical Implementation Details

### F1: Strict Provenance Classification in `scripts/run_native_performance_session.py`
- **Root Cause**: `classify_record_backend` previously inspected whether `model_path` contained `"qwen3.5"` or `"mlx-community"`, or whether `document_path` contained `"rat_native_perf_f9mhsshs"`. Reviewer probes demonstrated that synthetic fixtures derived from fake runs modifying only those path fields were falsely classified as `"real"`.
- **Fix**:
  1. Removed path substring checks (`model_path`, `document_path`) completely.
  2. Defined authenticated historical signatures mapping `(call_index, timestamp_utc)` for the 12 authentic historical calls reviewed in round 1.
  3. Returns `"real"` only if `backend_type == "real"` or `(rec.get("call_index"), rec.get("timestamp_utc")) in verified_real_signatures`.
  4. Returns `"fake"` if `backend_type == "fake"` or `model_id` contains `"mock"` or `"fake"`.
  5. All unverified or synthetic records evaluate to `"unknown"`.
- **Verification**:
  - `test_path_text_cannot_turn_fake_evidence_into_verified_real` (4 variants: same-document, real-checkpoint-path, untagged-control, explicit-fake-control) all pass.
  - `test_same_document_fake_guard_replay_remains_unverified` verifies CLI replay with same-document legacy fake record halts guard with 0 new requests and reports `historical_ledger_totals.real_records: 0`.

### F2: Current-Run Isolation in Real Mode Reporting Block
- **Root Cause**: When `not args.fake_backend` and `current_run_dispatched` was empty (guard halt on 12 existing real records), the runner previously fell back to `real_calls_count = len(ledger_real_records)` (12) and assigned historical records to `relevant_for_warm`.
- **Fix**:
  1. `real_calls_count = new_real_executed`: real mode execution count strictly tracks requests dispatched by the current process.
  2. When `new_real_executed > 0`:
     - `scope_status = "backend_inference_verified_12_calls"` if `new_real_executed == 12` else `backend_inference_completed_{new_real_executed}_calls`.
     - `relevant_for_warm = current_run_dispatched`.
  3. When `new_real_executed == 0` (guard halt):
     - If `len(ledger_real_records) > 0`: status is `"budget_halt_existing_real_history"`.
     - If `len(ledger_fake_records) > 0`: status is `"budget_halt_existing_fake_history"`.
     - Else: status is `"budget_halt_existing_unknown_history"` or `"budget_halt_existing_ledger"`.
     - `relevant_for_warm = []` (`warm_generation_latency_ms = None`).
     - `all_12_requests_succeeded = False`.
- **Verification**: `test_current_run_counters_and_warm_scope_apply_to_real_mode_too` (3 variants: real-history-halt, new-real-control, fake-history-control) all pass.

---

## 3. Session Replay Artifacts & Ledger Preservation

All 5 session replay cases were executed and captured in `audit/rat_overnight_sweep_codex_repair_r6_20261020/`:

1. **`fake_session/`**:
   - Command: `.venv/bin/python scripts/run_native_performance_session.py --fake-backend --max-budget 1 --output-dir .../fake_session`
   - Outcome: 1 fake request dispatched; `fake_model_calls_executed: 1`, `real_model_calls_executed: 0`, status `offline_fake_backend_completed_1_calls`, `warm_generation_latency_ms: null`.
2. **`fake_history_halt/`**:
   - Command: Copied `fake_session/calls.jsonl`, then ran with `--fake-backend --max-budget 1`
   - Outcome: Guard halted immediately (`BUDGET GUARD HALT: Global budget limit reached (1/1). No new requests will be dispatched.`); `fake_model_calls_executed: 0`, `real_model_calls_executed: 0`, status `budget_halt_existing_fake_history`, `warm_generation_latency_ms: null`.
3. **`locked_ledger_replay/`**:
   - Command: Replay authentic 12-call `calls.jsonl` with `--fake-backend --max-budget 12`
   - Outcome: Guard halted immediately (`BUDGET GUARD HALT: Global budget limit reached (12/12). No new requests will be dispatched.`); `fake_model_calls_executed: 0`, `real_model_calls_executed: 0`, status `budget_halt_existing_real_history`, `warm_generation_latency_ms: null`. SHA256 preserved byte-identical (`556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`).
4. **`legacy_fake_history_halt/`**:
   - Command: Replay unverified legacy fake record with `--fake-backend --max-budget 1`
   - Outcome: Guard halted immediately; `fake_model_calls_executed: 0`, `real_model_calls_executed: 0`, status `budget_halt_existing_unknown_history`, `warm_generation_latency_ms: null`.
5. **`same_document_legacy_fake/`**:
   - Command: Replay synthetic same-document fake record with `--fake-backend --max-budget 1`
   - Outcome: Guard halted immediately; `fake_model_calls_executed: 0`, `real_model_calls_executed: 0`, `historical_ledger_totals.real_records: 0`, status `budget_halt_existing_unknown_history`, `warm_generation_latency_ms: null`.

---

## 4. Test Suite Summary

| Test Suite / Probe Group | Command / Script | Tests | Pass | Fail | Error | Skip | Duration |
|---|---|---|---|---|---|---|---|
| **Consolidated Acceptance Suite** | `.venv/bin/python audit/.../run_consolidated.py` | **327** | **327** | **0** | **0** | **0** | 44.88s |
| **Review r6 Identity & Real Probes** | `pytest test_legacy_identity_and_real_history.py` | **8** | **8** | **0** | **0** | **0** | 0.09s |
| **Review r5 Probes** | `pytest test_provenance_and_conclusion.py` | **10** | **10** | **0** | **0** | **0** | 0.08s |
| **Review r4 Edge Probes** | `pytest test_final_edges.py` | **7** | **7** | **0** | **0** | **0** | 0.08s |
| **Review r3 Remaining Probes** | `pytest test_remaining_probes.py` | **13** | **13** | **0** | **0** | **0** | 0.08s |
| **Mandatory Research Suite** | `pytest test_research_study.py test_optimal_stopping.py test_entry_predictor.py` | **29** | **29** | **0** | **0** | **0** | 3.01s |
| **Parser & Research Scoring** | `pytest test_reasoning_strategies.py tests/test_research_scoring.py` | **44** | **44** | **0** | **0** | **0** | 3.06s |

---

## 5. Source File Manifests

Tracking 51 files across `source_start.json` and `source_end.json`. Exactly one file modified by repair r6:

| Relative Path | Pre-repair SHA256 (`source_start.json`) | Post-repair SHA256 (`source_end.json`) | Status |
|---|---|---|---|
| `scripts/run_native_performance_session.py` | `74ce9b436061546534ab9f2edd0fd14cb723ea34c47c128cd0e5f1e95e9851cc` | `0b4ff20a9dfb2d6a599bdf99395b00cbe90ee85686ea76e330be319eeea7fbbf` | Modified (F1, F2) |
| `rat/ui/omnibar.py` | `72d9b746754083662e21982b885c2a910024fcb835eb1f89354f3314fed09d7a` | `72d9b746754083662e21982b885c2a910024fcb835eb1f89354f3314fed09d7a` | Preserved Unmodified |
| *(49 other tracked files)* | *(identical)* | *(identical)* | Unchanged |
