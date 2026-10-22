# RAT–CoT Runtime Acceptance & Provenance Follow-up Handoff

**Date**: 2026-10-22  
**Branch**: `main` (solo Git workflow: 0 commits, 0 branches created, 0 pushes/pulls/resets)  
**System Architecture**: RAT–CoT Unified System (NCKH Student Research Implementation & Headless Evaluation)  
**Audit Directory**: `audit/rat_cot_runtime_acceptance_20261020/`  

---

## 1. Executive Summary

This handoff packages the full resolution of findings from **Independent Codex review r6** (`audit/rat_cot_runtime_codex_review_r6_20261021/review.md`), closing all remaining runtime, evidence, and manifest items:
- **R3 [P1, Closed] — Structured Generation Boundary & Non-Generation Stage Accounting**:
  Eliminated heuristic `extra_failed = 1` calculation from successful generation traces (`len(gens) > 0 and stop_status == "failed"`). Accounting at the generation boundary relies exclusively on structured facts: `last_trace["in_flight"]` flag and recorded generation statuses in `last_trace["generations"]`. Stage errors occurring outside stream generation (e.g. prompt preprocessing in `apply_chat_template` or post-generation `_record_status`) do not invent phantom dispatched or failed requests.
- **R5 [P1, Closed] — Complete Live State Finiteness and Active Calibrator Binding**:
  Enforced finiteness of both artifact and live state: checked `np.isfinite` on live performance constants before comparison, preventing live NaN values from bypassing validation via `abs(c_val - live_val) > 1e-5` (which evaluates to False when `live_val` is NaN). Enforced calibrator state binding: when a bundle declares an uncalibrated policy (`calibrator_type is None` or `calibrator_semantics == "raw_confidence_uncalibrated"`), any active calibrator in `policy.calibrators` triggers fail-closed rejection. Also verified parameter finiteness for Platt calibrator parameters (`a`, `b`).
- **R10 [P2, Closed] — Audit Lineage, Durations, and Incident Digest Alignment**:
  1. Corrected `actual_sha256` in `r4_baseline_xml_incident.json` to `548a8a33352b56f41aa85d06b5e7c17a6818aa637e33f9fde317bbae295125bb` matching the disk file.
  2. Clearly distinguished historical baseline regression suite (`regression.xml` 372 pass, 37.51s, pinned to early r5 snapshot `de13ebdb...`) from fresh source-pinned contract suites.
  3. Accurately reported units: 504 total test executions across 9 XML suites represent 471 distinct `(classname, name)` test identities with 33 repeated executions (29 mandatory research + 4 G1).
  4. Synchronized all reported durations in `commands.json` and `handoff.md` with raw stdout and JUnit XML times.
  5. Disclosed full checkout scope boundaries honestly: uncommitted parallel UI flow changes in `rat/ui/` do not regress core runtime contracts.

### Testing & Verification Highlights:
- **372/372 tests passed** in the historical consolidated baseline regression suite in 37.51s (`regression.txt`, `regression.xml`).
- **7/7 Codex review r6 trace facts and calibrator binding tests passed** in 3.04s (`contract_probes_r6.txt`, `contract_probes_r6.xml`).
- **12/12 Codex review r5 binding and dispatch tests passed** in 2.89s (`contract_probes_r5.txt`, `contract_probes_r5.xml`).
- **14/14 Codex review r4 remaining contract tests passed** in 2.96s (`contract_probes_r4.txt`, `contract_probes_r4.xml`).
- **19/19 Codex review r3 boundary contract tests passed** in 2.49s (`contract_probes_r3.txt`, `contract_probes_r3.xml`).
- **3/3 Codex review r2 Qwen AST boundary replay tests passed** in 2.05s (`qwen_boundary_replay.txt`, `qwen_boundary_replay.xml`).
- **29/29 mandatory research tests passed** (`test_research_study.py`, `test_optimal_stopping.py`, `test_entry_predictor.py`) in 5.15s (`mandatory_research.txt`, `mandatory_research.xml`).
- **44/44 parser / document intake tests passed** (`test_document_intake.py`, `test_document_intake_robustness.py`) in 0.57s (`parser_affected.txt`, `parser_affected.xml`).
- **4/4 G1 failed request reporting tests passed** in 0.13s (`failed_request_reporting.txt`, `failed_request_reporting.xml`).
- **Total: 504 test executions across 9 suites (471 distinct test identities, 33 repeated executions)**, 100% green.
- **0 new real-model requests executed**; remaining authorized real-model budget = 0.
- **12 historical calls preserved byte-identically** (SHA256: `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`).
- **Comprehensive patch generated**: `repair_diff.patch` captures unified diffs across `qwen_mlx_backend.py`, `reasoning/runtime.py`, and `reasoning/bundle.py`.

---

## 2. Technical Implementation Details

### Resolution Matrix for Review R6 Findings

| Finding | Severity | Status | Component | Key Resolution | Verified By |
| --- | --- | --- | --- | --- | --- |
| **R3** | P1 | **Closed** | `reasoning/runtime.py` | Removed heuristic `extra_failed = 1` from successful trace (`len(gens) > 0 and stop_status == "failed"`). Accounting at generation boundary strictly uses `in_flight` and recorded generations. Stage errors outside stream generation (prompt formatting before stream or `_record_status` after stream) do not fabricate phantom requests. | `test_trace_and_calibrator.py` (2 stage-error cases) |
| **R5** | P1 | **Closed** | `reasoning/bundle.py` | Enforced finiteness on both artifact and live state: added `np.isfinite` check on live performance constants before comparison. Enforced calibrator state binding: uncalibrated bundles reject live active calibrators. Verified parameter finiteness for Platt calibrator. | `test_trace_and_calibrator.py` (2 live-state mutation cases) |
| **R10** | P2 | **Closed** | `commands.json`, `handoff.md`, `r4_baseline_xml_incident.json` | Fixed actual SHA-256 digest in `r4_baseline_xml_incident.json` to `548a8a33352b56f41aa85d06b5e7c17a6818aa637e33f9fde317bbae295125bb`. Distinguishes historical baseline run from fresh source-pinned runs. Accurately reports 504 executions / 471 distinct identities. Synchronized declared durations with raw stdout / XML times. | Evidence crosscheck, manifest verification |

---

## 3. Suite Execution Summary

All test suites were executed in the local `.venv` environment without real model weights or network access:

| Suite Name | Command | Executions | Passed | Stdout (s) | XML (s) | Logs / XML | Lineage |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| Consolidated Regression | `.venv/bin/python audit/rat_cot_runtime_acceptance_20261020/run_consolidated.py` | 372 | 372 | 37.51 | 37.485 | `regression.txt` / `regression.xml` | Historical baseline (r5 snapshot `de13ebdb...`) |
| Mandatory Research | `.venv/bin/python -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q` | 29 | 29 | 5.15 | 5.146 | `mandatory_research.txt` / `mandatory_research.xml` | Fresh source-pinned |
| Parser & Document Intake | `.venv/bin/python -m pytest tests/test_document_intake.py tests/test_document_intake_robustness.py -q` | 44 | 44 | 0.57 | 0.562 | `parser_affected.txt` / `parser_affected.xml` | Fresh source-pinned |
| Failed Request Reporting (G1) | `.venv/bin/python -m pytest audit/rat_overnight_sweep_codex_review_r7_20261020/test_failed_request_reporting.py -q` | 4 | 4 | 0.13 | 0.133 | `failed_request_reporting.txt` / `failed_request_reporting.xml` | Fresh source-pinned |
| Codex Review r2 Qwen Replay | `.venv/bin/python -m pytest audit/rat_cot_runtime_codex_review_r2_20261020/test_qwen_boundary_replay.py -p audit.rat_cot_runtime_acceptance_20261020.redirect_plugin -v` | 3 | 3 | 2.05 | 2.054 | `qwen_boundary_replay.txt` / `qwen_boundary_replay.xml` | Fresh source-pinned |
| Codex Review r3 Boundary Contracts | `.venv/bin/python -m pytest audit/rat_cot_runtime_codex_review_r3_20261020/test_boundary_contracts.py -p audit.rat_cot_runtime_acceptance_20261020.redirect_plugin -v` | 19 | 19 | 2.49 | 2.477 | `contract_probes_r3.txt` / `contract_probes_r3.xml` | Fresh source-pinned |
| Codex Review r4 Remaining Contracts | `.venv/bin/python -m pytest audit/rat_cot_runtime_codex_review_r4_20261021/test_remaining_contracts.py -p audit.rat_cot_runtime_acceptance_20261020.redirect_plugin -v` | 14 | 14 | 2.96 | 2.957 | `contract_probes_r4.txt` / `contract_probes_r4.xml` | Fresh source-pinned |
| Codex Review r5 Binding & Dispatch | `.venv/bin/python -m pytest audit/rat_cot_runtime_codex_review_r5_20261021/test_binding_and_dispatch.py -p audit.rat_cot_runtime_acceptance_20261020.redirect_plugin -v` | 12 | 12 | 2.89 | 2.887 | `contract_probes_r5.txt` / `contract_probes_r5.xml` | Fresh source-pinned |
| Codex Review r6 Trace & Calibrator | `.venv/bin/python -m pytest audit/rat_cot_runtime_codex_review_r6_20261021/test_trace_and_calibrator.py -p audit.rat_cot_runtime_acceptance_20261020.redirect_plugin -v` | 7 | 7 | 3.04 | 3.032 | `contract_probes_r6.txt` / `contract_probes_r6.xml` | Fresh source-pinned |
| **Total** | | **504** | **504** | | | | **471 distinct identities** |

*Note on test accounting*: Across the 9 XML suites, 504 total test executions were run. They represent 471 distinct `(classname, name)` test identities. The 33 repeated executions correspond to mandatory research (29 tests) and failed request reporting (4 tests) which are included in both the fresh source-pinned suites and the historical consolidated baseline suite.

---

## 4. Verification Checksums

- **Historical Ledger**:
  `audit/rat_cot_runtime_acceptance_20261020/calls.jsonl`  
  SHA-256: `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34` (verified byte-identical)
- **Repair Unified Diff**:
  `audit/rat_cot_runtime_acceptance_20261020/repair_diff.patch` (390 lines covering `qwen_mlx_backend.py`, `reasoning/runtime.py`, `reasoning/bundle.py`)
- **Historical Manifests**:
  - `audit/rat_cot_runtime_codex_review_20261020/artifact_manifest.json`: 81/81 matched (100%)
  - `audit/rat_cot_runtime_codex_review_r2_20261020/artifact_manifest.json`: 102/102 matched (100%)
  - `audit/rat_cot_runtime_codex_review_r3_20261020/artifact_manifest.json`: 115/115 matched (100%)
  - `audit/rat_cot_runtime_codex_review_r4_20261021/artifact_manifest.json`: 146/147 matched (single `baseline.xml` drift documented honestly in `r4_baseline_xml_incident.json`)
  - `audit/rat_cot_runtime_codex_review_r5_20261021/artifact_manifest.json`: 156/156 matched (100%)
  - `audit/rat_cot_runtime_codex_review_r6_20261021/artifact_manifest.json`: 160/160 matched (100%)
