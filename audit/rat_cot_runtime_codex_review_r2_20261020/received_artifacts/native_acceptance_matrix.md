# Native Acceptance Readiness Matrix & Timing Instrumentation

**Date**: 2026-10-20  
**Context**: RAT Application Runtime & Headless Research Harness Integration  
**Directory**: `audit/rat_cot_runtime_acceptance_20261020/`  

---

## 1. Matrix of Native Acceptance Cases

| Case ID | Feature / Condition | Entry Point | Expected Outcome | Verified By | Status |
|---|---|---|---|---|---|
| **C1** | Step Progress Signal Emission | `OnlineReasoningWorker.step_completed` / `on_step` | Step observations emitted incrementally to UI thread without blocking | `test_native_acceptance_readiness.py::test_case_1_token_streaming` | **VERIFIED (Step Progress in Fixture; Live GUI Token Stream Unmeasured)** |
| **C2** | Cancel During Prefill | Controllable backend double / `is_cancelled` check in prefill | Cooperative cancel halts immediately; decode phase is never entered | `test_native_acceptance_readiness.py::test_case_2_cancel_during_prefill` | **VERIFIED (Fixture Double Prefill Cancel)** |
| **C3** | Cancel During Decode | Controllable backend double / `is_cancelled` check during generation | Generation stops cooperatively; decode phase aborted | `test_native_acceptance_readiness.py::test_case_3_cancel_during_decode` | **VERIFIED (Fixture Double Decode Cancel)** |
| **C4** | Re-Ask After Cancel | Consecutive queries through controller / worker | Second turn executes cleanly from cold state without deadlocks or polluted cache | `test_native_acceptance_readiness.py::test_case_4_re_ask_after_cancel` | **VERIFIED (Cold Re-Ask in Fixture)** |
| **C5** | Changed Document / Missing File | `OnlineReasoningWorker` with `document_path` | Modified / deleted document returns `status="unresolved"`, `verification_status="unverified"`; drops prior context | `test_native_acceptance_readiness.py::test_case_5_change_document_mid_turn` | **VERIFIED (Mid-Turn Mutation Invalidation)** |
| **C6** | Outside-Excerpt / Unresolved Query | `MetaReasonerEngine._solve_with_pal` with missing inputs | Returns `verification_status="unverifiable"`, `confidence=0.0`, `confidence_kind="not_estimated"`; never inherits PASS | `test_native_acceptance_readiness.py::test_case_6_outside_excerpt_unresolved` | **VERIFIED (Fallback & No PASS Inheritance)** |
| **C7** | Backend Failure & Deadline Timeout | `OnlineReasoningController(deadline_monotonic=...)` | Exceeded deadline halts before next strategy; failed attempt recorded in ledger; no canned answer | `test_native_acceptance_readiness.py::test_case_7_failure_and_timeout` | **VERIFIED (Error Charges Ledger; Timeout Halts)** |
| **C8** | Query Generation Binding | Worker generation binding (`query_generation`, `execution_id`) | Delayed callback from prior generation is safely discarded; active UI state unchanged | `test_native_acceptance_readiness.py::test_case_8_late_callback_suppression` | **VERIFIED (Worker Result Binding)** |
| **C9** | Real MLX Local Model Inference | Native Metal interactive session | 12 real calls exhausted in prior campaign; 0 real calls permitted | Pinned ledger check (SHA256 `556fadbb...`) | **NOT-RUN: No Remaining Authorized Real-Model Budget** |

---

## 2. Timing Instrumentation & Latency Measurement Semantics

The table below defines how timing phases are instrumented and where values are null:

| Phase | Instrumentation Method | Recorded Field | Unit | Status in Headless Suite | Notes / Semantics |
|---|---|---|---|---|---|
| **Queue Latency** | Time from worker creation to thread start | `queue_latency_ms` | ms | **null** (unmeasured in headless) | Not isolated in current headless worker run() |
| **Prefill Latency** | Time to process input prompt before 1st token | `prefill_latency_ms` | ms | **null** (unmeasured in double) | Requires native MLX profiler or Metal hooks |
| **Decode Latency** | Time spent generating output tokens | `decode_latency_ms` | ms | **null** (unmeasured in double) | Requires native MLX token timer; null in doubles |
| **First Displayed Token (TTFT)** | Elapsed time from submit to 1st streamed UI token | `first_ui_token_ms` | ms | **null** (unmeasured in headless) | Live Omnibar speech bubble rendering not hosted |
| **Submit-to-Done (Wall Time)** | Total elapsed time from query arrival to final response | `latency_ms` | ms | **Measured** | Monotonic duration of solve() / worker execution |

### Critical Accounting & Architectural Boundary Rules:
1. **Scope Boundary**: Default singleton `meta_reasoner` remains controller-free. `OnlineReasoningWorker` and `build_composed_meta_reasoner` represent an opt-in, decoupled component tested under headless doubles, not proof that the native interactive UI session is fully integrated or wired by default.
2. **Generated-token counts** represent only the sum of output tokens returned by model strategies.
3. **Generated-token count is NOT full inference cost** (which must incorporate prompt tokens, memory bandwidth, and GPU compute hours).
4. Prompt tokens, prefill time, and full inference cost are marked `null` / `unmeasured` unless explicit hardware telemetry is captured.
