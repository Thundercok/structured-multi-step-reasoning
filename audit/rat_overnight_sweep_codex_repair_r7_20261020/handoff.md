# Overnight RAT–CoT Repair Follow-up Handoff (Round 7)

**Date**: 2026-10-20  
**Branch**: `main` (solo Git workflow, 0 commits, 0 pushes, 0 branch creations)  
**System Architecture**: RAT–CoT Unified System (NCKH Student Research Implementation)  
**Directory**: `audit/rat_overnight_sweep_codex_repair_r7_20261020/`  

---

## 1. Executive Summary

This repair cycle directly resolves finding G1 identified in independent review r7 (`audit/rat_overnight_sweep_codex_review_r7_20261020/review.md`):

1. **G1 (Evaluation of Current-Run Success/Failure Outcomes)**:
   - Previously in `scripts/run_native_performance_session.py`, `scope_status` and `scope_note` were generated strictly based on `new_real_executed`, claiming `backend_inference_verified_12_calls` and asserting `12 successful backend requests` even when records contained exceptions and `all_12_requests_succeeded` was false.
   - Fixed by partitioning current-run dispatched records into `new_real_successful` (`status == "success"`) and `new_real_failed` (`new_real_executed - new_real_successful`).
   - `scope_status` emits `backend_inference_verified_12_calls` only when `all_12_requests_succeeded` is true (`new_real_executed == 12 and new_real_successful == 12`).
   - When requests fail or raise exceptions, status reflects failure/partial outcome (`backend_inference_failed_{attempts}_attempts` or `backend_inference_partial_{successful}_of_{attempts}_calls`) and the note explicitly describes the attempts dispatched and failure/exception counts without claiming verified or successful inference.
   - Budget and attempt counters remain strictly based on attempts dispatched.
   - Only successful requests are included in `relevant_for_warm`.
2. **Terminology & Identity Whitelist Clarity**:
   - The historical whitelist `(call_index, timestamp_utc)` is explicitly treated and documented as a request identity whitelist/mapping within trusted-local-ledger scope, not a cryptographic digital signature.

### Verification Highlights
- **4/4 review r7 probes passed** in `audit/rat_overnight_sweep_codex_review_r7_20261020/test_failed_request_reporting.py` (0.29s, covering 12-exception failure, 1-exception failure, 12-success control, and 1-success control).
- **331/331 consolidated test suite passed** in 100.56s (0 failures, 0 errors, 0 skips), recorded in `regression.txt` and `regression.xml`.
- **29/29 mandatory research tests passed** in 8.48s (`test_research_study.py`, `test_optimal_stopping.py`, `test_entry_predictor.py`).
- **44/44 parser and research scoring tests passed** in 6.78s (`test_reasoning_strategies.py`, `tests/test_research_scoring.py`).
- **5 session replays executed cleanly** (`fake_session`, `locked_ledger_replay`, `fake_history_halt`, `legacy_fake_history_halt`, `same_document_legacy_fake`).
- **0 new real-model requests executed**; historical 12-call ledger remains byte-identical with SHA256 `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`.
- **External change preserved**: `rat/ui/omnibar.py` (SHA256 `72d9b746754083662e21982b885c2a910024fcb835eb1f89354f3314fed09d7a`, mtime 00:27:06 UTC) preserved without revert or overwrite.
- **Single production file modified**: `scripts/run_native_performance_session.py`.
- **Zero Git commits/pushes/branching**.

---

## 2. Technical Implementation Details

### G1: Current-Run Outcome Scoping in `scripts/run_native_performance_session.py`
- **Root Cause**: `scope_status` and `scope_note` previously formatted output solely from `new_real_executed`, regardless of request outcome, creating a direct contradiction between the claim of "successful backend requests" and `all_12_requests_succeeded = False`.
- **Fix**:
  1. Compute `new_real_successful = len([r for r in current_run_dispatched if r.get("backend_type") == "real" and r.get("status") == "success"])` and `new_real_failed = new_real_executed - new_real_successful`.
  2. Evaluate `all_12_requests_succeeded = (new_real_executed == 12 and new_real_successful == 12)` before formatting status and note.
  3. When `new_real_executed > 0`:
     - If `all_12_requests_succeeded`: `scope_status = "backend_inference_verified_12_calls"`, note reports 12 successful backend requests.
     - If `new_real_failed == 0`: `scope_status = f"backend_inference_completed_{new_real_executed}_calls"`, note reports `{new_real_executed}` successful backend requests.
     - If `new_real_successful == 0`: `scope_status = f"backend_inference_failed_{new_real_executed}_attempts"`, note reports `{new_real_executed} backend request attempts dispatched; 0 succeeded ({new_real_failed} failed/exceptions). Inference not verified.`
     - Else: `scope_status = f"backend_inference_partial_{new_real_successful}_of_{new_real_executed}_calls"`, note reports `{new_real_executed} backend request attempts dispatched; {new_real_successful} succeeded, {new_real_failed} failed/exceptions.`
     - `relevant_for_warm = [r for r in current_run_dispatched if r.get("status") == "success"]`.
- **Verification**: `test_failed_request_reporting.py` (4/4 pass).

---

## 3. Session Replay Artifacts & Ledger Preservation

All 5 session replay cases were executed and captured in `audit/rat_overnight_sweep_codex_repair_r7_20261020/`:

1. **`fake_session/`**:
   - Command: `.venv/bin/python scripts/run_native_performance_session.py --fake-backend --max-budget 1 --output-dir .../fake_session`
   - Outcome: 1 fake request dispatched; `fake_model_calls_executed: 1`, `real_model_calls_executed: 0`, status `offline_fake_backend_completed_1_calls`, `warm_generation_latency_ms: null`.
2. **`fake_history_halt/`**:
   - Command: Replay `fake_session/calls.jsonl` with `--fake-backend --max-budget 1`
   - Outcome: Guard halted immediately; `fake_model_calls_executed: 0`, `real_model_calls_executed: 0`, status `budget_halt_existing_fake_history`, `warm_generation_latency_ms: null`.
3. **`locked_ledger_replay/`**:
   - Command: Replay authentic 12-call `calls.jsonl` with `--fake-backend --max-budget 12`
   - Outcome: Guard halted immediately; `fake_model_calls_executed: 0`, `real_model_calls_executed: 0`, status `budget_halt_existing_real_history`, `warm_generation_latency_ms: null`. SHA256 preserved byte-identical (`556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`).
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
| **Consolidated Acceptance Suite** | `.venv/bin/python audit/.../run_consolidated.py` | **331** | **331** | **0** | **0** | **0** | 100.56s |
| **Review r7 Failed Request Reporting** | `pytest test_failed_request_reporting.py` | **4** | **4** | **0** | **0** | **0** | 0.29s |
| **Review r6 Identity & Real Probes** | `pytest test_legacy_identity_and_real_history.py` | **8** | **8** | **0** | **0** | **0** | 0.15s |
| **Review r5 Probes** | `pytest test_provenance_and_conclusion.py` | **10** | **10** | **0** | **0** | **0** | 0.08s |
| **Review r4 Edge Probes** | `pytest test_final_edges.py` | **7** | **7** | **0** | **0** | **0** | 0.08s |
| **Review r3 Remaining Probes** | `pytest test_remaining_probes.py` | **13** | **13** | **0** | **0** | **0** | 0.08s |
| **Mandatory Research Suite** | `pytest test_research_study.py test_optimal_stopping.py test_entry_predictor.py` | **29** | **29** | **0** | **0** | **0** | 8.48s |
| **Parser & Research Scoring** | `pytest test_reasoning_strategies.py tests/test_research_scoring.py` | **44** | **44** | **0** | **0** | **0** | 6.78s |

---

## 5. Source File Manifests

Tracking 51 files across `source_start.json` and `source_end.json`. Exactly one file modified by repair r7:

| Relative Path | Pre-repair SHA256 (`source_start.json`) | Post-repair SHA256 (`source_end.json`) | Status |
|---|---|---|---|
| `scripts/run_native_performance_session.py` | `0b4ff20a9dfb2d6a599bdf99395b00cbe90ee85686ea76e330be319eeea7fbbf` | `6b60706b804fe6fe202b21c4314e3e3bdf8a2118355aa21e053f31f94d9ce257` | Modified (G1) |
| `rat/ui/omnibar.py` | `72d9b746754083662e21982b885c2a910024fcb835eb1f89354f3314fed09d7a` | `72d9b746754083662e21982b885c2a910024fcb835eb1f89354f3314fed09d7a` | Preserved Unmodified |
| *(49 other tracked files)* | *(identical)* | *(identical)* | Unchanged |
