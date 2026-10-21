# RAT–CoT Runtime Acceptance & Provenance Follow-up Handoff

**Date**: 2026-10-20  
**Branch**: `main` (solo Git workflow: 0 commits, 0 branches created, 0 pushes/pulls/resets)  
**System Architecture**: RAT–CoT Unified System (NCKH Student Research Implementation & Headless Evaluation)  
**Audit Directory**: `audit/rat_cot_runtime_acceptance_20261020/`  

---

## 1. Executive Summary

This cycle resolves all 6 P1 findings (R1–R6) and 3 P2 findings (R7–R9) raised in the independent Codex runtime review (`audit/rat_cot_runtime_codex_review_20261020/review.md`), bringing the online CoT controller into a fully verified RAT workflow with strict provenance, multi-call budget accounting, execution limits, and verifiable result states, while preparing data and protocol conditions for the NCKH research publication under strict blind review.

Key outcomes delivered across all four sections:

1. **Resolution of Codex Findings R1–R9**:
   - **R1 (Zero-quota override)**: Distinctly separated `None` from `0` in `reasoning/runtime.py`. Overrides of `0` strictly block dispatches (0 calls dispatched, status `budget_exceeded`), preventing fallback to positive defaults.
   - **R2 (Token ceiling enforcement)**: Implemented hard ceiling clamping effective tokens so total generated tokens never exceeds `max_generated_tokens`, setting status `budget_exceeded` when reached. Forwarded `max_tokens` kwargs to backend where supported.
   - **R3 (Exception ledger preservation)**: Partial dispatches and generated tokens from `last_trace["generations"]` are captured in an `ExecutionCostLedger` attached directly to caught exceptions (`exc.cost_ledger`). Callers and workers retain attempt counters even when backend calls fail.
   - **R4 (Cancellation & deadline enforcement)**: Cooperative cancellation callback (`should_cancel`) and deadline (`deadline_monotonic`) are inspected and forwarded to `backend.run`. Interruption and timeout conditions are verified immediately upon strategy completion before loop break, ensuring terminal strategies never report `completed` after a stop event.
   - **R5 (Bundle validation & compatibility)**: Hardened `validate_policy_bundle` in `reasoning/bundle.py`: rejects non-finite numbers (NaN/Inf) in lambda, thresholds, and costs; rejects empty provenance dictionaries; rejects unsupported backend protocols and feature versions; validates fitted regressor input dimensions against bundle feature schema (schema v1=3 complexity vs v2=6 complexity); rejects invalid prompt profiles and model identity mismatches.
   - **R6 (Mid-turn document integrity)**: `OnlineReasoningWorker` hashes document content and captures mtime before execution, and rechecks after execution. If the document file changes mid-turn, status is set to `unresolved`, `confidence_kind="not_estimated"`, and `verification_status="unverified"`.
   - **R7 (Native acceptance matrix alignment)**: Aligned `native_acceptance_matrix.md` and `tests/test_native_acceptance_readiness.py`: downgraded unmeasured telemetry fields (`queue_latency_ms`, `first_ui_token_ms`, prefill/decode) to `null` in headless fixtures; step progress is verified via `OnlineReasoningWorker.step_completed` and `on_step`; cooperative cancellation during prefill and decode verified via double hooks; singleton remains controller-free.
   - **R8 (Protocol separation & power sensitivity)**: Formulated reproducible power sensitivity analysis (`scripts/calculate_power_sensitivity.py` outputting `power_sensitivity.json`) showing $N=70$ pairs achieves 80% power only for medium-to-large effects ($\Delta \ge 0.15 - 0.18$). Decoupled Study 1 (single-call Fresh Restart manipulation: 70 items $\times$ 4 arms = 280 generation calls max) from Study 2 (multi-call adaptive routing ladder: up to 10 subcalls/query).
   - **R9 (Same-document replay fixture)**: Replaced malformed 7-line metadata fixture in `same_document_legacy_fake/calls.jsonl` with authentic 1-line JSONL completed record from `corrected_same_document_replay/`, verifying `unknown_records=1` and `budget_halt_existing_unknown_history`.

2. **Testing & Verification Highlights**:
   - **26/26 Codex contract & replay probes passed** (`audit/rat_cot_runtime_codex_review_20261020/test_contract_probes.py` 25 pass, `test_replay_fixture_probe.py` 1 pass).
   - **372/372 tests passed** in the full consolidated regression suite in 79.97s (0 failures, 0 errors, 0 skips).
   - **29/29 mandatory research tests passed** (`test_research_study.py`, `test_optimal_stopping.py`, `test_entry_predictor.py`) in 8.36s.
   - **69/69 parser & research scoring tests passed** in 19.97s.
   - **4/4 r7 probe tests passed** (`test_failed_request_reporting.py`).
   - **0 new real-model requests executed**; remaining authorized real-model budget = 0.
   - **12 historical calls preserved byte-identically** (SHA256 `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`).

---

## 2. Technical Implementation Details

### A. Resolution Matrix for Findings R1–R9

| Finding | Severity | Component | Key Resolution | Verified By |
|---|---|---|---|---|
| **R1** | P1 | `reasoning/runtime.py` | Distinguish `0` from `None`; block dispatch when limit is 0; never fall back to default | `test_zero_per_call_budget_dispatches_nothing`, `test_zero_override_does_not_restore_positive_default` |
| **R2** | P1 | `reasoning/runtime.py` | Clamp effective tokens to remaining cap; forward `max_tokens` kwargs to backend | `test_generated_token_ceiling_is_enforced_within_final_strategy` |
| **R3** | P1 | `reasoning/runtime.py`, `rat/ui/reasoning_worker.py` | Extract subcalls from `last_trace["generations"]`; attach `cost_ledger` to caught exceptions | `test_backend_error_preserves_attempt_ledger_for_caller`, `test_worker_error_preserves_attempt_ledger` |
| **R4** | P1 | `reasoning/runtime.py` | Forward `should_cancel` and `deadline_monotonic`; check stop events immediately after strategy | `test_final_strategy_cannot_report_completed_after_stop_event`, `test_cancel_hook_reaches_backend_run` |
| **R5** | P1 | `reasoning/bundle.py` | Reject non-finite values (NaN/Inf); reject empty provenance dicts; check fitted dimensions vs schema v1/v2 | `test_incompatible_approved_metadata_fails_closed`, `test_feature_dimension_mismatch_rejected_before_embedding` |
| **R6** | P1 | `rat/ui/reasoning_worker.py` | Snapshot SHA256/mtime of document; detect mid-turn changes; emit `status="unresolved"` | `test_worker_document_change_during_execution_is_unresolved` |
| **R7** | P2 | `native_acceptance_matrix.md`, `tests/test_native_acceptance_readiness.py` | Mark unmeasured telemetry fields as `null`; forward `on_step` to `step_completed`; test through worker boundaries | `test_native_acceptance_readiness.py` (8/8 pass) |
| **R8** | P2 | `data_review_checklist.md`, `unauthorized_real_execution_plan.md` | Decouple 280-call Fresh Restart from multi-call routing ladder; script reproducible power sensitivity (`power_sensitivity.json`) | `scripts/calculate_power_sensitivity.py` |
| **R9** | P2 | `same_document_legacy_fake/calls.jsonl` | Use authentic 1-line JSONL record; match `unknown_records=1` and `budget_halt_existing_unknown_history` | `test_replay_fixture_probe.py` (1/1 pass) |

---

## 3. Test Suite & Replay Execution Summary

| Suite / Probe Group | Command / Script | Tests | Pass | Fail | Error | Duration |
|---|---|---|---|---|---|---|
| **Codex Contract Probes (R1–R7)** | `pytest test_contract_probes.py` | **25** | **25** | **0** | **0** | 3.02s |
| **Codex Replay Probe (R9)** | `pytest test_replay_fixture_probe.py` | **1** | **1** | **0** | **0** | 0.08s |
| **Full Consolidated Suite** | `python audit/.../run_consolidated.py` | **372** | **372** | **0** | **0** | 79.97s |
| **Mandatory Research Suite** | `pytest test_research_study.py test_optimal_stopping.py test_entry_predictor.py` | **29** | **29** | **0** | **0** | 8.36s |
| **Parser & Research Scoring** | `pytest tests/test_harness_regressions.py tests/test_order_selector_contract.py ...` | **69** | **69** | **0** | **0** | 19.97s |
| **Failed Request Reporting (r7)** | `pytest test_failed_request_reporting.py` | **4** | **4** | **0** | **0** | 0.15s |
| **Native Readiness Matrix** | `pytest tests/test_native_acceptance_readiness.py` | **8** | **8** | **0** | **0** | 3.18s |
| **Policy Bundle Provenance** | `pytest tests/test_policy_bundle.py` | **11** | **11** | **0** | **0** | 2.85s |

### Replay Outcomes
1. `fake_session`: 1 fake call dispatched; status `offline_fake_backend_completed_1_calls`.
2. `fake_history_halt`: 0 calls dispatched; status `budget_halt_existing_fake_history`.
3. `locked_ledger_replay`: 0 calls dispatched; status `budget_halt_existing_real_history`. Ledger SHA256 preserved (`556fadbb...`).
4. `legacy_fake_history_halt`: 0 calls dispatched; status `budget_halt_existing_unknown_history`.
5. `same_document_legacy_fake`: 0 calls dispatched; status `budget_halt_existing_unknown_history` (1 completed historical record, 1 unknown record).

---

## 4. Source Files & Integrity

| File Path | Status | Role |
|---|---|---|
| `bundle.py` | New | Backward-compatibility shim for reasoning.bundle |
| `reasoning/bundle.py` | New | Canonical PolicyBundle schema, validator, dimension checking, and safe JSON serialization |
| `reasoning/runtime.py` | Modified | Zero-budget block, token ceiling, exception cost ledger preservation, cancel/deadline forwarding |
| `rat/engine/meta_reasoner.py` | Modified | `solve()` parameter forwarding (`on_step`, limits), composition factory |
| `rat/ui/reasoning_worker.py` | New | Off-thread QThread worker with document SHA256 integrity check and step signal |
| `scripts/calculate_power_sensitivity.py` | New | Reproducible McNemar power sensitivity generator |
| `audit/.../power_sensitivity.json` | New | Power sensitivity profile across N in [30..150] and delta in [0.05..0.25] |
| `tests/test_policy_bundle.py` | New | 11 unit tests for PolicyBundle validation and safe serialization |
| `tests/test_online_reasoning_execution.py` | New | 8 integration tests for budgets, cancel, timeouts, and worker execution |
| `tests/test_native_acceptance_readiness.py` | New | 8 acceptance tests for step progress, cancellation phases, and document change |

---

## 5. Codex Review Instructions

Codex reviewer can independently verify this handoff using the artifacts in `audit/rat_cot_runtime_acceptance_20261020/`:
1. Verify 12-call ledger hash:
   `shasum -a 256 audit/rat_cot_runtime_acceptance_20261020/calls.jsonl`
   Expected: `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`.
2. Verify all 26 contract & replay probes:
   `.venv/bin/python -m pytest audit/rat_cot_runtime_codex_review_20261020/test_contract_probes.py audit/rat_cot_runtime_codex_review_20261020/test_replay_fixture_probe.py -v`
3. Run mandatory research harness suite:
   `.venv/bin/python -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q`
4. Run consolidated suite:
   `.venv/bin/python audit/rat_cot_runtime_acceptance_20261020/run_consolidated.py`
5. Inspect `validation.json`, `data_review_checklist.md`, `native_acceptance_matrix.md`, `power_sensitivity.json`, and `unauthorized_real_execution_plan.md`.
