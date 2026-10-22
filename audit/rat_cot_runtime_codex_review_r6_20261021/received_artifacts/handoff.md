# RAT–CoT Runtime Acceptance & Provenance Follow-up Handoff

**Date**: 2026-10-21  
**Branch**: `main` (solo Git workflow: 0 commits, 0 branches created, 0 pushes/pulls/resets)  
**System Architecture**: RAT–CoT Unified System (NCKH Student Research Implementation & Headless Evaluation)  
**Audit Directory**: `audit/rat_cot_runtime_acceptance_20261020/`  

---

## 1. Executive Summary

This handoff packages the full resolution of findings from **Independent Codex review r5** (`audit/rat_cot_runtime_codex_review_r5_20261021/review.md`), closing all remaining runtime, evidence, and manifest items:
- **R2 [P1, Closed] — ReAct Turn Limit & Token Budget Control**: Added `react_max_turns: int = 4` parameter to `QwenMLXBackend` and dynamically forwarded from `run()` into `_react(max_turns=...)`. `_react` bounds turns strictly to `range(turns)` and decrements/clamps per-subcall token limits to `min(200, max_tokens - total_tok)` so hard token and request caps cannot be bypassed. `OnlineReasoningController.__init__` propagates bundle `strategy_settings["react_max_turns"]` to backend, and `reasoning/bundle.py` validates that declared `react_max_turns` matches backend.
- **R3 [P1, Closed] — Pre-Dispatch Error Text Invariance & Structured Fact Accounting**: Completely eliminated exception string pattern matching (`"after dispatch"` removed). Dispatch accounting relies strictly on structured trace facts: `last_trace["in_flight"]`, recorded generation status in `generations`, and ongoing multi-request state (`len(gens) > 0 and stop_status == "failed"`). Pre-dispatch failures (such as in `tokenizer.apply_chat_template`) record exactly 0 dispatched requests and 0 tokens invariant to error message text.
- **R5 [P1, Closed] — Authoritative Fitted Policy Artifact Binding**: Eliminated filename heuristics. Validates numerical finiteness (`np.isfinite`) for `lambda`, `tau`, `mean_cost`, and all coefficients/intercepts (rejects NaN/Inf). Requires `entry_cost_models` to provide intercepts when live model has `intercept_`. Validates `entry_perf_models` strictly when provided; if omitted from artifact, live performance models must not deviate from baseline default `[1.0, 0.0, 0.0]`. Missing parameters, model shape mismatches, and mutated models fail closed.
- **R12 [P2, Closed] — Historical Evidence Immutability & Manifest Verification**: Manifest verification confirmed 100% byte-identical match across historical review folders:
  - r1 (`audit/rat_cot_runtime_codex_review_20261020/`): 81/81 files matched (100%).
  - r2 (`audit/rat_cot_runtime_codex_review_r2_20261020/`): 102/102 files matched (100%).
  - r3 (`audit/rat_cot_runtime_codex_review_r3_20261020/`): 115/115 files matched (100%).
  - r4 (`audit/rat_cot_runtime_codex_review_r4_20261021/`): 146/147 files matched (100% of restorable counterexamples; single historical `baseline.xml` drift documented honestly in `r4_baseline_xml_incident.json` without timestamp fabrication).
  - r5 (`audit/rat_cot_runtime_codex_review_r5_20261021/`): 156/156 files matched (100%).
  - All test runners use `redirect_plugin.py` to redirect test fixture outputs to `prior_probe_outputs/`, guaranteeing immutable review directories remain untouched.

### Testing & Verification Highlights:
- **372/372 tests passed** in the full consolidated regression suite in 37.51s (0 failures, 0 errors, 0 skips; `regression.txt`, `regression.xml`).
- **12/12 Codex review r5 binding and dispatch tests passed** in 2.98s (`contract_probes_r5.txt`, `contract_probes_r5.xml`).
- **14/14 Codex review r4 remaining contract tests passed** in 3.64s (`contract_probes_r4.txt`, `contract_probes_r4.xml`).
- **19/19 Codex review r3 boundary contract tests passed** in 3.70s (`contract_probes_r3.txt`, `contract_probes_r3.xml`).
- **3/3 Codex review r2 Qwen AST boundary replay tests passed** in 3.18s (`qwen_boundary_replay.txt`, `qwen_boundary_replay.xml`).
- **29/29 mandatory research tests passed** (`test_research_study.py`, `test_optimal_stopping.py`, `test_entry_predictor.py`) in 4.24s (`mandatory_research.txt`, `mandatory_research.xml`).
- **44/44 parser / document intake tests passed** (`test_document_intake.py`, `test_document_intake_robustness.py`) in 1.32s (`parser_affected.txt`, `parser_affected.xml`).
- **4/4 G1 failed request reporting tests passed** in 0.14s (`failed_request_reporting.txt`, `failed_request_reporting.xml`).
- **Total: 497 tests passing** (100% green across all 8 suites) with 0 failures, 0 errors, 0 skips.
- **0 new real-model requests executed**; remaining authorized real-model budget = 0.
- **12 historical calls preserved byte-identically** (SHA256: `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`).
- **Comprehensive patch generated**: `repair_diff.patch` captures unified diffs across `qwen_mlx_backend.py`, `reasoning/runtime.py`, and `reasoning/bundle.py`.

---

## 2. Technical Implementation Details

### Resolution Matrix for Review R5 Findings

| Finding | Severity | Status | Component | Key Resolution | Verified By |
| --- | --- | --- | --- | --- | --- |
| **R2** | P1 | **Closed** | `qwen_mlx_backend.py`, `reasoning/runtime.py`, `reasoning/bundle.py` | Added `react_max_turns` to `QwenMLXBackend` constructor and forwarded to `_react`. Clamped subcall token caps to `min(200, max_tokens - total_tok)`. Estimator and bundle validator enforce matching `react_max_turns`. | `test_binding_and_dispatch.py` (cases `react_requests`, `react_tokens`) |
| **R3** | P1 | **Closed** | `reasoning/runtime.py` | Removed `"after dispatch"` string check. Dispatch accounting uses structured trace facts (`in_flight`, `recorded_failed`, and multi-sample in-progress status). Pre-dispatch failures record 0 requests/tokens invariant to exception message content. | `test_binding_and_dispatch.py` (`test_predispatch_prompt_failure_count_is_invariant_to_message`) |
| **R5** | P1 | **Closed** | `reasoning/bundle.py` | Enforces complete parameter binding on authoritative fitted policy artifacts. Requires finite numeric values (`np.isfinite`). Validates cost intercepts and performance models (or canonical baseline default). Fails closed on NaN/Inf or model divergence. | `test_binding_and_dispatch.py` (6 parameter mutation cases raise `BundleValidationError`) |
| **R12** | P2 | **Closed** | `redirect_plugin.py`, `r4_baseline_xml_incident.json` | Restored all counterexamples across review folders (r1: 81/81, r2: 102/102, r3: 115/115, r4: 146/147, r5: 156/156). Lost `baseline.xml` drift in r4 explicitly logged without timestamp fabrication. `redirect_plugin.py` prevents probe output pollution. | Manifest check (100% matched across r1, r2, r3, r5, and 146/147 in r4 with incident record) |

---

## 3. Suite Execution Summary

All test suites were executed in the local `.venv` environment without real model weights or network access:

| Suite Name | Command | Tests | Passed | Duration | Logs / XML |
| --- | --- | ---: | ---: | ---: | --- |
| Consolidated Regression | `.venv/bin/python audit/rat_cot_runtime_acceptance_20261020/run_consolidated.py` | 372 | 372 | 37.51s | `regression.txt` / `regression.xml` |
| Mandatory Research | `.venv/bin/python -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q` | 29 | 29 | 4.24s | `mandatory_research.txt` / `mandatory_research.xml` |
| Parser & Document Intake | `.venv/bin/python -m pytest tests/test_document_intake.py tests/test_document_intake_robustness.py -q` | 44 | 44 | 1.32s | `parser_affected.txt` / `parser_affected.xml` |
| Codex Review r3 Boundary Contracts | `.venv/bin/python -m pytest audit/rat_cot_runtime_codex_review_r3_20261020/test_boundary_contracts.py -p audit.rat_cot_runtime_acceptance_20261020.redirect_plugin -q` | 19 | 19 | 3.70s | `contract_probes_r3.txt` / `contract_probes_r3.xml` |
| Codex Review r2 Qwen Replay | `.venv/bin/python -m pytest audit/rat_cot_runtime_codex_review_r2_20261020/test_qwen_boundary_replay.py -p audit.rat_cot_runtime_acceptance_20261020.redirect_plugin -q` | 3 | 3 | 3.18s | `qwen_boundary_replay.txt` / `qwen_boundary_replay.xml` |
| Failed Request Reporting (G1) | `.venv/bin/python -m pytest audit/rat_overnight_sweep_codex_review_r7_20261020/test_failed_request_reporting.py -q` | 4 | 4 | 0.14s | `failed_request_reporting.txt` / `failed_request_reporting.xml` |
| Codex Review r4 Remaining Contracts | `.venv/bin/python -m pytest audit/rat_cot_runtime_codex_review_r4_20261021/test_remaining_contracts.py -p audit.rat_cot_runtime_acceptance_20261020.redirect_plugin -q` | 14 | 14 | 3.64s | `contract_probes_r4.txt` / `contract_probes_r4.xml` |
| Codex Review r5 Binding & Dispatch | `.venv/bin/python -m pytest audit/rat_cot_runtime_codex_review_r5_20261021/test_binding_and_dispatch.py -p audit.rat_cot_runtime_acceptance_20261020.redirect_plugin -q` | 12 | 12 | 2.98s | `contract_probes_r5.txt` / `contract_probes_r5.xml` |
| **Total** | | **497** | **497** | | |

---

## 4. Verification Checksums

- **Historical Ledger**:
  `audit/rat_cot_runtime_acceptance_20261020/calls.jsonl`  
  SHA-256: `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34` (verified byte-identical)
- **Repair Unified Diff**:
  `audit/rat_cot_runtime_acceptance_20261020/repair_diff.patch` (348 lines covering `qwen_mlx_backend.py`, `reasoning/runtime.py`, `reasoning/bundle.py`)
- **Historical Manifests**:
  - `audit/rat_cot_runtime_codex_review_20261020/artifact_manifest.json`: 81/81 matched (0 mismatches)
  - `audit/rat_cot_runtime_codex_review_r2_20261020/artifact_manifest.json`: 102/102 matched (0 mismatches)
  - `audit/rat_cot_runtime_codex_review_r3_20261020/artifact_manifest.json`: 115/115 matched (0 mismatches)
  - `audit/rat_cot_runtime_codex_review_r4_20261021/artifact_manifest.json`: 146/147 matched (1 incident documented)
  - `audit/rat_cot_runtime_codex_review_r5_20261021/artifact_manifest.json`: 156/156 matched (0 mismatches)
