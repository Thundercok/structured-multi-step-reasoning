# RAT–CoT Runtime Acceptance & Provenance Follow-up Handoff

**Date**: 2026-10-21  
**Branch**: `main` (solo Git workflow: 0 commits, 0 branches created, 0 pushes/pulls/resets)  
**System Architecture**: RAT–CoT Unified System (NCKH Student Research Implementation & Headless Evaluation)  
**Audit Directory**: `audit/rat_cot_runtime_acceptance_20261020/`  

---

## 1. Executive Summary

This handoff packages the full resolution of findings from **Independent Codex review r4** (`audit/rat_cot_runtime_codex_review_r4_20261021/review.md`), closing all remaining runtime and evidence items:
- **R2 [P1, Closed] — Sample Configuration & Strategy Loop Enforcement**: Backend attributes `sc_samples` and `tot_branches` are dynamically forwarded by `run()` to the respective strategy loops (`_self_consistency(k=...)` and `_tot(branches=...)`). In the controller (`reasoning/runtime.py`), `estimate_underlying_requests` uses the backend's configured parameters and divides remaining token quota accurately (`remaining // est_reqs`), preventing subcall request budget and token cap overruns.
- **R3 [P1, Closed] — Structured Dispatch Accounting & In-Flight Tracking**: Eliminated fragile error message string matching (`"after dispatch"` removed). Added explicit structured in-flight tracking (`last_trace["in_flight"] = True/False`) inside `qwen_mlx_backend.py._chat`. The runtime exception handler accurately distinguishes pre-dispatch cancellation (which records 0 dispatched requests and 0 tokens) from in-flight faults. Failed attempts already captured in `last_trace["generations"]` are accounted truthfully without double-counting.
- **R5 [P1, Closed] — Strict Fitted Policy Artifact Validation**: `reasoning/bundle.py` now enforces rigorous schema validation on approved policy artifacts: malformed JSON immediately raises `BundleValidationError`, required parameters (`lambda`, `tau`, `mean_cost`, `entry_cost_models`) must be present, empty cost models are rejected, parameter vector shapes and numerical values are verified against live policy objects, and performance predictor constants and coefficients are validated.
- **R12 [P2, Closed] — Historical Counterexample Evidence Preservation**: Restored all 8 historical counterexample files across `audit/rat_cot_runtime_codex_review_r2_20261020/` (2 files: `qwen_failure_case.json`, `qwen_token_cap_case.json`) and `audit/rat_cot_runtime_codex_review_r3_20261020/` (6 files: `caller_name_*.json`, `decode_exception_case.json`, `cancel_stream_*.json`, `between_sc_cancel_case.json`) to exact byte-identical hashes matching their respective original manifests. Implemented `redirect_plugin.py` to redirect all future probe test fixture writers to `prior_probe_outputs/`, guaranteeing that review directories remain 100% immutable during testing.

### Testing & Verification Highlights:
- **372/372 tests passed** in the full consolidated regression suite in 37.51s (0 failures, 0 errors, 0 skips; `regression.txt`, `regression.xml`).
- **14/14 Codex review r4 remaining contract tests passed** in 4.25s (`contract_probes_r4.txt`, `contract_probes_r4.xml`).
- **19/19 Codex review r3 boundary contract tests passed** in 3.84s (`contract_probes_r3.txt`, `contract_probes_r3.xml`).
- **29/29 mandatory research tests passed** (`test_research_study.py`, `test_optimal_stopping.py`, `test_entry_predictor.py`) in 4.41s (`mandatory_research.txt`, `mandatory_research.xml`).
- **44/44 parser / document intake tests passed** (`test_document_intake.py`, `test_document_intake_robustness.py`) in 1.10s (`parser_affected.txt`, `parser_affected.xml`).
- **3/3 Codex review r2 Qwen AST boundary replay tests passed** in 2.97s (`qwen_boundary_replay.txt`, `qwen_boundary_replay.xml`).
- **4/4 G1 failed request reporting tests passed** in 0.14s (`failed_request_reporting.txt`, `failed_request_reporting.xml`).
- **Total: 408 tests passing** with 0 failures across all suites.
- **0 new real-model requests executed**; remaining authorized real-model budget = 0.
- **12 historical calls preserved byte-identically** (SHA256: `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`).
- **Immutable review directory manifests**: r2 (102 files) and r3 (115 files) match 100% with 0 mismatches.

---

## 2. Technical Implementation Details

### Resolution Matrix for Review R4 Findings

| Finding | Severity | Status | Component | Key Resolution | Verified By |
| --- | --- | --- | --- | --- | --- |
| **R2** | P1 | **Closed** | `qwen_mlx_backend.py`, `reasoning/runtime.py` | `sc_samples` and `tot_branches` dynamically control execution loops in `_self_consistency` and `_tot`. Runtime controller uses backend attributes for `estimate_underlying_requests` and partitions token caps evenly (`remaining // est_reqs`). | `test_remaining_contracts.py` (cases 1–4 passed) |
| **R3** | P1 | **Closed** | `qwen_mlx_backend.py`, `reasoning/runtime.py` | Replaced `"after dispatch"` exception string check with structured `last_trace["in_flight"] = True/False`. Pre-dispatch cancellation yields 0 requests and 0 tokens. Trace generations already recorded are not double counted. | `test_remaining_contracts.py` (cases 5–6 passed) |
| **R5** | P1 | **Closed** | `reasoning/bundle.py` | Fails closed on malformed JSON; requires `lambda`, `tau`, `mean_cost`, and `entry_cost_models`; validates non-empty model lists; enforces shape and numeric closeness against live policy; validates predictor performance models. | `test_remaining_contracts.py` (cases 7–11 passed) |
| **R12** | P2 | **Closed** | `audit/rat_cot_runtime_acceptance_20261020/redirect_plugin.py`, historical fixtures | Restored 8 historical counterexamples in r2 (2) and r3 (6). Implemented pytest redirect plugin for acceptance runs to prevent test fixture writers from modifying review directories. | `python -c "verify_manifests"` (102/102 in r2, 115/115 in r3 match perfectly) |

---

## 3. Suite Execution Summary

All test suites were executed in the local `.venv` environment without real model weights or network access:

| Suite Name | Command | Tests | Passed | Duration | Logs / XML |
| --- | --- | ---: | ---: | ---: | --- |
| Consolidated Regression | `.venv/bin/python audit/rat_cot_runtime_acceptance_20261020/run_consolidated.py` | 372 | 372 | 37.51s | `regression.txt` / `regression.xml` |
| Mandatory Research | `.venv/bin/python -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q` | 29 | 29 | 4.41s | `mandatory_research.txt` / `mandatory_research.xml` |
| Parser & Document Intake | `.venv/bin/python -m pytest tests/test_document_intake.py tests/test_document_intake_robustness.py -q` | 44 | 44 | 1.10s | `parser_affected.txt` / `parser_affected.xml` |
| Codex Review r3 Boundary Contracts | `.venv/bin/python -m pytest audit/rat_cot_runtime_codex_review_r3_20261020/test_boundary_contracts.py -p audit.rat_cot_runtime_acceptance_20261020.redirect_plugin -q` | 19 | 19 | 3.84s | `contract_probes_r3.txt` / `contract_probes_r3.xml` |
| Codex Review r2 Qwen Replay | `.venv/bin/python -m pytest audit/rat_cot_runtime_codex_review_r2_20261020/test_qwen_boundary_replay.py -p audit.rat_cot_runtime_acceptance_20261020.redirect_plugin -q` | 3 | 3 | 2.97s | `qwen_boundary_replay.txt` / `qwen_boundary_replay.xml` |
| Failed Request Reporting (G1) | `.venv/bin/python -m pytest audit/rat_overnight_sweep_codex_review_r7_20261020/test_failed_request_reporting.py -q` | 4 | 4 | 0.14s | `failed_request_reporting.txt` / `failed_request_reporting.xml` |
| Codex Review r4 Remaining Contracts | `.venv/bin/python -m pytest audit/rat_cot_runtime_codex_review_r4_20261021/test_remaining_contracts.py -p audit.rat_cot_runtime_acceptance_20261020.redirect_plugin -q` | 14 | 14 | 4.25s | `contract_probes_r4.txt` / `contract_probes_r4.xml` |

---

## 4. Preservation & Integrity Verifications

1. **Git State**:
   - Working branch is `main`.
   - 0 git commits created, 0 branches created, 0 git pushes/pulls/resets executed.
   - Unrelated workspace changes (`rat/ui/assistant_worker.py`, `rat/ui/omnibar.py`, `rat/ui/workbench_scene.py`, `rat/engine/execution.py`, `audit/rat_flow_optimization_20261021/`) preserved intact.

2. **Model Call Quota**:
   - Authorized real-model calls: **0**.
   - Executed real-model calls: **0**.
   - Historical 12-call ledger (`calls.jsonl`) SHA256: `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34` (100% byte-identical).

3. **Candidate & Data Review**:
   - Candidate frame (`6c889c3b...`) and evaluation data remain untuned and unprinted to agent context.
   - Stage 0 gate remains unpassed; synthetic development specimens strictly labeled.
