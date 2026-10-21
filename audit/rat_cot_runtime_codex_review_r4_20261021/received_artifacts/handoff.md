# RAT–CoT Runtime Acceptance & Provenance Follow-up Handoff

**Date**: 2026-10-20  
**Branch**: `main` (solo Git workflow: 0 commits, 0 branches created, 0 pushes/pulls/resets)  
**System Architecture**: RAT–CoT Unified System (NCKH Student Research Implementation & Headless Evaluation)  
**Audit Directory**: `audit/rat_cot_runtime_acceptance_20261020/`  

---

## 1. Executive Summary

This cycle resolves all findings across all rounds of independent Codex runtime review:
- Codex Review r1: findings R1–R9.
- Codex Review r2: findings R1–R10 (R1 and R9 closed).
- Codex Review r3: findings R11 [P1], R2 [P1], R3 [P1], R5 [P1], R6 [P1], and R12 [P2].

The online CoT controller and worker now achieve clean, caller-invariant execution contracts within RAT:
- **Universal Pre-dispatch Capability Check (R11 & R2)**: Completely removed all `sys._getframe` / caller-name inspection. Any caller requesting a hard token cap against a backend lacking `max_tokens` support is rejected immediately before dispatch (`NotImplementedError`), without modifying execution paths based on caller name or retroactive token clamping.
- **Generation Boundary Accounting & Decode Exception Handling (R3)**: `qwen_mlx_backend.py` wraps `stream_generate` in `try...finally`. Tokens yielded by the generator are accounted for before cancellation/timeout checks. Decode exceptions preserve yielded token counts in the cost ledger, and cooperative cancellation during stream yield records the correct token count and non-successful outcome status.
- **Approved Policy Bundle Provenance & Live Parameter Binding (R5)**: `reasoning/bundle.py` validates that every declared source and artifact reference exists on disk with a valid 64-character SHA-256 digest matching the file. Backend identity (`model_id`, `model_snapshot`) and strategy settings (`sc_samples`, `tot_branches`) are matched against backend attributes. Live policy parameters (`lambda`, `tau`, `entry_cost_models` coefficients and intercepts) are verified against artifact JSON files.
- **Fail-Closed Selected Document QA (R6)**: `rat/ui/reasoning_worker.py` fails closed immediately if reading the selected document text raises an exception (e.g. `PermissionError`), emitting `status="unresolved"` and `"wait"` signal without falling back to generic query dispatch.
- **Restored R2 Counterexample Fixtures (R12)**: Restored `qwen_failure_case.json` (SHA256: `69553525...`) and `qwen_token_cap_case.json` (SHA256: `a9ef02e9...`) to exact byte-identical hashes matching the r2 manifest.

### Testing & Verification Highlights:
- **372/372 tests passed** in the full consolidated regression suite in 57.47s (0 failures, 0 errors, 0 skips; `regression.txt`, `regression.xml`).
- **19/19 Codex review r3 boundary contract tests passed** in 4.53s (`contract_probes_r3.txt`, `contract_probes_r3.xml`).
- **29/29 mandatory research tests passed** (`test_research_study.py`, `test_optimal_stopping.py`, `test_entry_predictor.py`) in 6.04s (`mandatory_research.txt`, `mandatory_research.xml`).
- **44/44 parser / document intake tests passed** (`test_document_intake.py`, `test_document_intake_robustness.py`) in 2.00s (`parser_affected.txt`, `parser_affected.xml`).
- **3/3 Codex review r2 Qwen AST boundary replay tests passed** in 4.04s (`qwen_boundary_replay.txt`, `qwen_boundary_replay.xml`).
- **4/4 G1 failed request reporting tests passed** in 0.17s (`failed_request_reporting.txt`, `failed_request_reporting.xml`).
- **0 new real-model requests executed**; remaining authorized real-model budget = 0.
- **12 historical calls preserved byte-identically** (SHA256 `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`).

---

## 2. Technical Implementation Details

### Resolution Matrix for Review R3 Findings

| Finding | Severity | Status | Component | Key Resolution | Verified By |
|---|---|---|---|---|---|
| **R11** | P1 | CLOSED | `reasoning/runtime.py` | Removed all `sys._getframe` and `caller_name` hackery; universal fail-closed capability check on `tok_limit is not None and not run_accepts_max_tokens` treats all callers identically | `test_caller_name_does_not_change_identical_execution`, `test_capable_backend_is_not_rejected_by_caller_name` (PASS) |
| **R2** | P1 | CLOSED | `reasoning/runtime.py` | Universal pre-dispatch rejection before generation for backends lacking `max_tokens`; no retroactive clamping; allocated subcall caps prevent budget multiplication | `test_ordinary_unsupported_cap_fails_before_any_dispatch`, `test_capable_backend_is_not_rejected_by_caller_name` (PASS) |
| **R3** | P1 | CLOSED | `qwen_mlx_backend.py`, `reasoning/runtime.py` | Wrapped `stream_generate` in `try...finally`; accounted for yielded tokens before checking cancellation/timeout; appended generation trace with `status` and `finish_reason` on decode exception; controller correctly charges partial generation tokens and avoids extra dispatch count between SC samples | `test_decode_exception_preserves_already_yielded_token_cost`, `test_cancel_after_stream_yield_accounts_for_generation_and_outcome`, `test_inter_sample_cancel_does_not_invent_new_dispatch` (PASS) |
| **R5** | P1 | CLOSED | `reasoning/bundle.py`, `qwen_mlx_backend.py` | Strict approved bundle validation: rejects missing source files, malformed 64-char digests, or disk hash mismatches; requires backend `model_id` and `model_snapshot` matching bundle; verifies `sc_samples` and `tot_branches`; verifies artifact JSON fitted parameters (`lambda`, `tau`, `entry_cost_models`) against live policy | `test_approved_provenance_rejects_unverifiable_references`, `test_approved_execution_requires_backend_identity`, `test_approved_strategy_settings_match_actual_backend`, `test_approved_artifact_binds_live_fitted_parameters` (PASS) |
| **R6** | P1 | CLOSED | `rat/ui/reasoning_worker.py` | Document read/stat failure immediately fails closed with `status="unresolved"` and `"wait"` signal, without falling back to query-only execution | `test_document_read_failure_does_not_fall_back_to_generic_answer` (PASS) |
| **R12** | P2 | CLOSED | `audit/rat_cot_runtime_codex_review_r2_20261020/` | Restored `qwen_failure_case.json` and `qwen_token_cap_case.json` from verified recovery directory to restore byte-identical SHA256 hashes matching r2 manifest | Byte comparison and SHA256 checksums (PASS) |

---

## 3. Test Suite & Replay Execution Summary

| Suite / Probe Group | Command / Script | Tests | Pass | Fail | Error | Duration | Raw Log / XML |
|---|---|---|---|---|---|---|---|
| **Full Consolidated Suite** | `python audit/.../run_consolidated.py` | **372** | **372** | **0** | **0** | 57.47s | `regression.txt`, `regression.xml` |
| **Codex Review r3 Boundary Probes** | `pytest test_boundary_contracts.py` | **19** | **19** | **0** | **0** | 4.53s | `contract_probes_r3.txt`, `contract_probes_r3.xml` |
| **Mandatory Research Suite** | `pytest test_research_study.py test_optimal_stopping.py test_entry_predictor.py` | **29** | **29** | **0** | **0** | 6.04s | `mandatory_research.txt`, `mandatory_research.xml` |
| **Parser / Document Intake Suite** | `pytest test_document_intake.py test_document_intake_robustness.py` | **44** | **44** | **0** | **0** | 2.00s | `parser_affected.txt`, `parser_affected.xml` |
| **Codex Review r2 Qwen Replay** | `pytest test_qwen_boundary_replay.py` | **3** | **3** | **0** | **0** | 4.04s | `qwen_boundary_replay.txt`, `qwen_boundary_replay.xml` |
| **Failed Request Reporting (r7)** | `pytest test_failed_request_reporting.py` | **4** | **4** | **0** | **0** | 0.17s | `failed_request_reporting.txt`, `failed_request_reporting.xml` |

---

## 4. Source Files & Integrity

| File Path | Status | Role |
|---|---|---|
| `reasoning/runtime.py` | Modified | Universal caller-invariant capability check, pre-dispatch hard cap rejection, observation and exception cost ledger preservation |
| `qwen_mlx_backend.py` | Modified | Identity attributes (`model_id`, `model_snapshot`, `sc_samples`, `tot_branches`), `stream_generate` try...finally loop preserving partial tokens and status |
| `reasoning/bundle.py` | Modified | Strict provenance verification for approved bundles (sources, artifacts, backend identity, strategy settings, fitted parameter binding) |
| `rat/ui/reasoning_worker.py` | Modified | Fail-closed document snapshot/read handling, document content hash checking, execution ID binding |
| `rat/engine/meta_reasoner.py` | Modified | Parameter forwarding (`on_step`, limits), composition factory |
| `scripts/calculate_power_sensitivity.py` | Tracked | Reproducible McNemar power sensitivity generator |

---

## 5. Codex Review Instructions

Codex reviewer can independently verify this handoff using the artifacts in `audit/rat_cot_runtime_acceptance_20261020/`:
1. Verify 12-call ledger hash:
   `shasum -a 256 audit/rat_cot_runtime_acceptance_20261020/calls.jsonl`
   Expected: `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`.
2. Verify all 19 boundary contract probes:
   `.venv/bin/python -m pytest audit/rat_cot_runtime_codex_review_r3_20261020/test_boundary_contracts.py -v`
3. Run mandatory research harness suite:
   `.venv/bin/python -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q`
4. Run consolidated suite:
   `.venv/bin/python audit/rat_cot_runtime_acceptance_20261020/run_consolidated.py`
5. Inspect `validation.json`, `repair_diff.patch`, `source_end.json`, `commands.json`, and `artifact_manifest.json`.
