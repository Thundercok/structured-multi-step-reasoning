# RAT–CoT Runtime Acceptance & Provenance Follow-up Handoff

**Date**: 2026-10-20  
**Branch**: `main` (solo Git workflow: 0 commits, 0 branches created, 0 pushes/pulls/resets)  
**System Architecture**: RAT–CoT Unified System (NCKH Student Research Implementation & Headless Evaluation)  
**Audit Directory**: `audit/rat_cot_runtime_acceptance_20261020/`  

---

## 1. Executive Summary

This cycle resolves all findings from both rounds of independent Codex runtime review:
- Codex Review r1: findings R1–R9.
- Codex Review r2: findings R1–R10 (5 P1s: R2, R3, R4, R5, R6; 3 P2s: R7, R8, R10; R1 and R9 confirmed closed in r2).

The online CoT controller now achieves rigorous execution contracts within RAT:
- True token budgets without post-generation clamping or subcall budget multiplication.
- Complete attempt ledger preservation across backend failures, exceptions, and invalid observations.
- Proper classification of cooperative cancellation and deadline timeouts.
- Fail-closed bundle validation against live backend identity, source file hashes, and artifact files on disk.
- Robust document QA routing and unconditional document content hash verification.
- Accurately scoped native acceptance claims (C4, C6, C8 clearly bounded with pending live UI notes).
- Synchronized raw test artifacts and complete patch evidence.

### Testing & Verification Highlights:
- **372/372 tests passed** in the full consolidated regression suite in 44.40s (0 failures, 0 errors, 0 skips; `regression.txt`, `regression.xml`).
- **29/29 mandatory research tests passed** (`test_research_study.py`, `test_optimal_stopping.py`, `test_entry_predictor.py`) in 3.32s (`mandatory_research.txt`, `mandatory_research.xml`).
- **44/44 parser / document intake tests passed** (`test_document_intake.py`, `test_document_intake_robustness.py`) in 0.47s (`parser_affected.txt`, `parser_affected.xml`).
- **26/26 Codex review r1 contract & replay probes passed** in 2.24s (`contract_probes_r1.txt`, `contract_probes_r1.xml`).
- **25/25 Codex review r2 general contract & Qwen boundary probes passed** in 2.06s (`contract_probes_r2.txt`, `contract_probes_r2.xml`).
- **Total probes: 51/51 passed** across both independent review suites.
- **4/4 G1 failed request reporting tests passed** in 0.15s (`failed_request_reporting.txt`, `failed_request_reporting.xml`).
- **0 new real-model requests executed**; remaining authorized real-model budget = 0.
- **12 historical calls preserved byte-identically** (SHA256 `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`).

---

## 2. Technical Implementation Details

### A. Resolution Matrix for Findings R1–R10

| Finding | Severity | Status | Component | Key Resolution | Verified By |
|---|---|---|---|---|---|
| **R1** | P1 | CLOSED | `reasoning/runtime.py` | Distinguish `0` from `None`; block dispatch when limit is 0; never fall back to default | 6 zero-quota probes in r1 & r2 (PASS) |
| **R2** | P1 | CLOSED | `reasoning/runtime.py` | Allocate per-subcall cap so SC/ToT multiple generations do not multiply cap; preserve raw tokens actually generated in ledger without retroactive clamping; reject unsupported hard cap before generation | `test_token_ledger_preserves_tokens_actually_generated`, `test_unsupported_hard_cap_rejected_before_generation`, `test_remaining_cap_not_multiplied_across_sc_generations` (PASS) |
| **R3** | P1 | CLOSED | `reasoning/runtime.py` | Compatible with actual Qwen trace schema (`tokens` key, no status); preserve attempt ledger on observation validation failure and strategy failure | `test_actual_qwen_strategy_failure_preserves_generation_costs`, `test_failure_accounting_accepts_actual_qwen_trace_schema`, `test_invalid_observation_preserves_dispatched_request_ledger` (PASS) |
| **R4** | P1 | CLOSED | `qwen_mlx_backend.py`, `rat/ui/reasoning_worker.py` | Expose execution controls (`should_cancel`, `deadline_monotonic`, `max_tokens`) in Qwen backend AST; classify worker stop exceptions into `cancelled` and `timeout` with preserved cost ledger | `test_qwen_strategy_entrypoint_exposes_claimed_execution_controls`, `test_worker_classifies_cooperative_stop_exception[cancel/deadline]` (PASS) |
| **R5** | P1 | CLOSED | `reasoning/bundle.py` | Check approved bundle metadata against backend identity (`model_id`, `model_snapshot`, `prompt_profile`); verify source file hashes on disk; verify artifact file existence; enforce strategy settings bounds; verify predictor kind; verify budget token semantics | 8/8 parametrized mismatch cases in `test_approved_metadata_mismatch_is_not_just_a_literal_blacklist` + control (PASS) |
| **R6** | P1 | CLOSED | `rat/ui/reasoning_worker.py` | Forward document context into query; unconditionally check SHA256 of document content after execution to detect mutations preserving size and mtime | `test_existing_document_is_used_or_explicitly_rejected`, `test_same_size_and_mtime_document_mutation_is_still_detected` (PASS) |
| **R7** | P2 | CLOSED | `native_acceptance_matrix.md` | Accurately scope claims: C4 bounded as cold pre-cancel re-ask (in-flight cleanup pending); C6 bounded as PAL fallback (document outside-excerpt pending); C8 bounded as result ID binding (UI stale suppression pending) | `native_acceptance_matrix.md`, `test_native_acceptance_readiness.py` |
| **R8** | P2 | CLOSED | `scripts/calculate_power_sensitivity.py`, `data_review_checklist.md`, `unauthorized_real_execution_plan.md` | Dynamically solve sample sizes for $\ge 80\%$ power: $N=236$ for $\delta=0.10$ and $N=942$ for $\delta=0.05$; align Arm F to canonical partial prefix continuation ($q^*=0.50$, fresh per-call cache) | `test_claimed_power_sample_size_reaches_its_own_target` (PASS) |
| **R9** | P2 | CLOSED | `same_document_legacy_fake/calls.jsonl` | Use authentic 1-line JSONL record; match `unknown_records=1` and `budget_halt_existing_unknown_history` | `test_replay_fixture_probe.py` (PASS) |
| **R10** | P2 | CLOSED | `audit/rat_cot_runtime_acceptance_20261020/*` | Synchronize raw logs and JUnit XMLs (`regression.txt` 44.40s matches `regression.xml` 44.38s); capture separate raw logs and XMLs for all test subsets; generate complete multi-file `repair_diff.patch` (118 KB); pin `scripts/calculate_power_sensitivity.py` in `source_end.json` | `commands.json`, `artifact_manifest.json`, `source_end.json` |

---

## 3. Test Suite & Replay Execution Summary

| Suite / Probe Group | Command / Script | Tests | Pass | Fail | Error | Duration | Raw Log / XML |
|---|---|---|---|---|---|---|---|
| **Full Consolidated Suite** | `python audit/.../run_consolidated.py` | **372** | **372** | **0** | **0** | 44.40s | `regression.txt`, `regression.xml` |
| **Mandatory Research Suite** | `pytest test_research_study.py test_optimal_stopping.py test_entry_predictor.py` | **29** | **29** | **0** | **0** | 3.32s | `mandatory_research.txt`, `mandatory_research.xml` |
| **Parser / Document Intake Suite** | `pytest test_document_intake.py test_document_intake_robustness.py` | **44** | **44** | **0** | **0** | 0.47s | `parser_affected.txt`, `parser_affected.xml` |
| **Codex Review r1 Probes** | `pytest test_contract_probes.py test_replay_fixture_probe.py` | **26** | **26** | **0** | **0** | 2.24s | `contract_probes_r1.txt`, `contract_probes_r1.xml` |
| **Codex Review r2 Probes** | `pytest test_general_contracts.py test_qwen_boundary_replay.py` | **25** | **25** | **0** | **0** | 2.06s | `contract_probes_r2.txt`, `contract_probes_r2.xml` |
| **Failed Request Reporting (r7)** | `pytest test_failed_request_reporting.py` | **4** | **4** | **0** | **0** | 0.15s | `failed_request_reporting.txt`, `failed_request_reporting.xml` |
| **Native Readiness Matrix** | `pytest tests/test_native_acceptance_readiness.py` | **8** | **8** | **0** | **0** | 2.62s | Subset in `regression.xml` |
| **Policy Bundle Provenance** | `pytest tests/test_policy_bundle.py` | **11** | **11** | **0** | **0** | 2.52s | Subset in `regression.xml` |
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
