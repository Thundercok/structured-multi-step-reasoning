# B1 Repair Handoff: Nested Registered Result Origin & Boundary Reconciliation

**Date:** 2026-10-15  
**Review Target:** Package B1 Final Acceptance  
**Status:** `ready_for_codex_review` (Codex decides acceptance)  
**Baseline Tested Compiler Hash:** `37259475b6a861b483ecc37f35460844cae0e3daf1ad13f1875170fbfd952c28`  
**Current Repaired Compiler Hash:** `cca488dea3fabb814c6187d8980b69fbc5eaf7d8c8cef0552eb0cad4f2b86b1f`  
**Repository Working Directory:** `/Users/thundercock2/Documents/Github/multi-step-structured-reasoning`  

---

## 1. Summary of Defect R5-1 & Architectural Resolution

### The Defect (R5-1)
In previous rounds, `projected_slots` recorded outer receipt-level substitutions (`operation_result`, `note_event`, `verification_report`). However, for registered operations like `record_work_note`, nested child slots (`note` and `note_event`) inside `operation_result` were decoded by `_expand_operation_result_body` and enumerated by `iter_projector_edges` based solely on the operation name `record_work_note`, without verifying whether the compiler had actually substituted those child slots.

As exposed by `registered_result_probes.py`:
- When a native operation result contained a literal wrapper in `note` or `note_event` that was **not** emitted by the compiler (e.g., did not match a canonical note/event), the compiler preserved it as literal in the snapshot.
- However, during validation, if the target entity was absent, it was flagged as a broken link; or if present, receipt expansion silently replaced the literal wrapper with the canonical entity body!

### The Complete Emitted-Edge Solution
We extended explicit emitted-edge provenance to nested result subslots without altering the schema or polluting entity bodies:

1. **Subslot Origin Tracking in Header:**
   During compilation in `_build_journal_entities_and_receipts`:
   - When `record_work_note` successfully matches and substitutes `res_body["note"]` with a canonical note version reference, `"operation_result.note"` is recorded in `receipt_envelope["header"]["projected_slots"]`.
   - When it successfully matches and substitutes `res_body["note_event"]`, `"operation_result.note_event"` is recorded in `receipt_envelope["header"]["projected_slots"]`.
   - If no substitution occurred (e.g. raw wrapper was in caller result), neither tag is added.

2. **Full Receipt Association for Entities:**
   `_find_receipt_for_operation_result(snapshot, entity_ref)` resolves an `operation_result` entity reference back to its owning receipt matching full identity (`receipt_id`, `execution_id`, `conversation_id`, `turn_id`).

3. **Consistent Edge Extraction (`iter_projector_edges`):**
   - For `observed_state.receipts`: child slots `operation_result.note` and `operation_result.note_event` are only yielded if explicitly listed in `projected_slots`.
   - For `entities` (`operation_result`): the owning receipt is resolved; child slots are only yielded if listed in the owning receipt's `projected_slots`.

4. **Guarded Expansion Across All Entry Points:**
   - `_expand_operation_result_body(res, snapshot, projected_slots=...)` only expands `note` if `"operation_result.note"` (or `"note"`) is in `projected_slots`, and only expands `note_event` if `"operation_result.note_event"` (or `"note_event"`) is in `projected_slots`.
   - `_expand_receipt` passes `projected_slots` to `_expand_operation_result_body`.
   - `expand_value_refs` (when resolving an outer result link, an entity envelope, or the whole snapshot) resolves the owning receipt and passes its `projected_slots`.
   - Literal wrappers in unprojected subslots stay raw data and are never decoded or treated as graph links.

5. **Entity Immutability & Schema Compliance:**
   - `entity["body"]` is not polluted with ad-hoc metadata, preserving strict `additionalProperties: false` conformance in `snapshot.schema.json`.
   - Caller input data structures (`ExecutionJournal`, notes, events, contracts) remain strictly immutable.

---

## 2. Test Execution & Evidence

### A. Focused Test Suites: 166 / 166 Passed (100%)
Executed command:
```bash
PYTHONDONTWRITEBYTECODE=1 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m pytest \
  tests/test_rat_context_snapshot.py \
  tests/test_rat_context_audit.py \
  tests/test_artifact_store_lifecycle.py \
  audit/rat_context_B1_codex_review_20261014_123157/review_probes.py \
  audit/rat_context_B1_codex_review_round2_20261014_151324/provenance_probes.py \
  audit/rat_context_B1_independent_20261014_084657/origin_scope_probes.py \
  audit/rat_context_B1_codex_review_current_20261014_210330/raw_receipt_probes.py \
  audit/rat_context_B1_codex_acceptance_20261015_095446/registered_result_probes.py \
  -p no:cacheprovider -q --tb=short
```

#### Actual JUnit Counts by File:
| File | Tests | Passed | Failed | Errors | Notes |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `tests/test_rat_context_snapshot.py` | 94 | 94 | 0 | 0 | 84 baseline + 10 new product regressions |
| `tests/test_rat_context_audit.py` | 6 | 6 | 0 | 0 | Coherence and selection set isolation |
| `tests/test_artifact_store_lifecycle.py` | 19 | 19 | 0 | 0 | Store generations and eviction invariants |
| `audit/rat_context_B1_codex_review_20261014_123157/review_probes.py` | 15 | 15 | 0 | 0 | Immutable R1 probes |
| `audit/rat_context_B1_codex_review_round2_20261014_151324/provenance_probes.py` | 14 | 14 | 0 | 0 | Immutable R2 probes |
| `audit/rat_context_B1_independent_20261014_084657/origin_scope_probes.py` | 5 | 5 | 0 | 0 | Immutable origin scope probes |
| `audit/rat_context_B1_codex_review_current_20261014_210330/raw_receipt_probes.py` | 8 | 8 | 0 | 0 | Immutable R4 raw receipt probes |
| `audit/rat_context_B1_codex_acceptance_20261015_095446/registered_result_probes.py` | 5 | 5 | 0 | 0 | **4 previously failing R5-1 probes now PASS + 1 control** |
| **Total Focused** | **166** | **166** | **0** | **0** | **100% Pass** |

#### New Scenarios Added in this Package:
1. `audit/rat_context_B1_codex_acceptance_20261015_095446/registered_result_probes.py`:
   - `test_registered_result_child_wrapper_not_emitted_by_projector_stays_literal[True-note]`: PASS
   - `test_registered_result_child_wrapper_not_emitted_by_projector_stays_literal[True-note_event]`: PASS
   - `test_registered_result_child_wrapper_not_emitted_by_projector_stays_literal[False-note]`: PASS
   - `test_registered_result_child_wrapper_not_emitted_by_projector_stays_literal[False-note_event]`: PASS
   - `test_canonical_registered_note_and_event_roundtrip_control`: PASS
2. Product regressions in `tests/test_rat_context_snapshot.py`:
   - `test_regression_registered_result_nested_slots_origin_boundary`: 8 executions (available, missing, self-referencing, and matching target but non-matching body for both `note` and `note_event`).
   - `test_regression_registered_result_canonical_subslot_roundtrip_and_serialization`: 1 execution (end-to-end projection, edge validation, JSON dumps/loads, and expansion via receipt, entity envelope, and snapshot).
   - `test_regression_registered_result_input_immutability`: 1 execution (verifying caller journal, notes, and events remain untouched).

### B. Core Regression Suite: 292 Passed, 1 Failed
Executed command against current checkout:
```bash
PYTHONDONTWRITEBYTECODE=1 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m pytest \
  audit/rat_reconciliation_codex_review_20261013/contract_probes.py \
  audit/rat_reconciliation_round2_codex_review_20261013/remaining_contract_probes.py \
  tests/test_rat_completion_boundaries.py \
  tests/test_rat_completion_reconciliation.py \
  tests/test_rat_note_source_verification.py \
  tests/test_rat_smoke_harness.py \
  tests/test_rat_verification_literal_guard.py \
  tests/test_rat_conversation_lifecycle.py \
  tests/test_rat_calculation_conversation.py \
  tests/test_work_context.py \
  tests/test_rat_chat_session.py \
  tests/test_assistant_runtime.py \
  tests/test_rat_task_memory.py \
  tests/test_research_study.py \
  test_optimal_stopping.py \
  test_entry_predictor.py \
  tests/test_interaction_kernel.py \
  tests/test_interaction_kernel_regressions.py \
  tests/test_rat_verification.py \
  tests/test_vgc_verification.py \
  -p no:cacheprovider -q --tb=short
```

- **Total Tests Collected:** 293
- **Passed:** 292
- **Failed:** 1
  - `audit/rat_reconciliation_codex_review_20261013/contract_probes.py::test_native_planner_outcomes_are_not_rejected_as_task_state`: Failed with `StopIteration` because mock client `side_effect` had 2 mocked responses while runtime made a 3rd call in current checkout.
  - Note: As noted in Codex's review, core regressions in `contract_probes.py` reflect the current runtime's native planner schema and mock configuration; they are separate from B1 compiler origin verification and are preserved without modification.

### C. Programmatic Roundtrips (`roundtrips.json`)
All 7 asserted roundtrip checks passed:
1. `unprojected_receipt_slots_raw_wrapper_stays_literal`: PASS
2. `genuine_projector_link_restores_literal_payload`: PASS
3. `registered_result_nested_slots_raw_wrapper_stays_literal`: PASS
4. `registered_result_canonical_subslot_roundtrip`: PASS
5. `exact_types_matrix_roundtrip` (12 JSON types including booleans, integers, floats, null, empty strings/lists, nested dicts): PASS
6. `draft202012_schema_compliance`: PASS
7. `input_immutability_strict_check`: PASS

---

## 3. Monitored Source Manifest & Zero Drift

All monitored files match expected hashes; zero unintended drift occurred:

| Path | Start SHA-256 | Finish SHA-256 | Drift |
| :--- | :--- | :--- | :---: |
| `rat/engine/context_snapshot.py` | `37259475b6a861b483ecc37f35460844cae0e3daf1ad13f1875170fbfd952c28` | `cca488dea3fabb814c6187d8980b69fbc5eaf7d8c8cef0552eb0cad4f2b86b1f` | Expected (R5-1 Fix) |
| `tests/test_rat_context_snapshot.py` | `2319ea4a9bff02e72af8231aa01a9915d1e89534a8ce46b3790b4bb1c329f043` | `5ec3d647fa2951b2b19021ed1287d4e5607569efb7d6e54bd15144f34dea9685` | Expected (Regressions) |
| `rat/engine/assistant_runtime.py` | `0518d3732b6e16c454daba78c0c8c8d1d0db00f44a9a9f3799020e35ede87ef6` | `0518d3732b6e16c454daba78c0c8c8d1d0db00f44a9a9f3799020e35ede87ef6` | None |
| `rat/engine/runtime_context.py` | `a4bbfa94550f75120794e457ee84b0f636467bf1be519e800e157c3444c11328` | `a4bbfa94550f75120794e457ee84b0f636467bf1be519e800e157c3444c11328` | None |
| `rat/engine/completion.py` | `d7b974b2862f08144eb69b82e792bdccb8943737d13cdae3665aea20218f9e3c` | `d7b974b2862f08144eb69b82e792bdccb8943737d13cdae3665aea20218f9e3c` | None |
| `rat/kernel/contracts.py` | `784fd28626dbd2174574139dfc1de2c73f979f9fe53faddc2bc1a5739bff2972` | `784fd28626dbd2174574139dfc1de2c73f979f9fe53faddc2bc1a5739bff2972` | None |
| `rat/kernel/dispatcher.py` | `2db4021fa29af75b8dc7b03420e5924c182e18d7b5b22ebd298e28cf454ab6a6` | `2db4021fa29af75b8dc7b03420e5924c182e18d7b5b22ebd298e28cf454ab6a6` | None |
| `audit/rat_context_B_assignment_20261014/snapshot.schema.json` | `8a168a7aaff57e41d43eca956e49e583702bb6ff9285b2f75bcdc135a47da667` | `8a168a7aaff57e41d43eca956e49e583702bb6ff9285b2f75bcdc135a47da667` | None |
| `audit/rat_context_B1_codex_acceptance_20261015_095446/registered_result_probes.py` | `f113a8112c16f38c483c49a6deb550969415784de936fc82f7d67dbde746a399` | `f113a8112c16f38c483c49a6deb550969415784de936fc82f7d67dbde746a399` | None |

Live model calls during verification: **0**.

---

## 4. Accurate B2 Preparation Document

`b2_preparation.md` has been updated to remove any premature claims regarding the Three-Point Verification Protocol:
- Documents the two actual model-call boundaries (`_plan_task` and `_call_model`).
- Precisely states that `runtime_context.py` currently takes three live `boundary()` samples (`before`, `after`, and the post-compilation check).
- Clarifies that `after` is **not** a vector derived from the captured bundle, and explicitly identifies the implementation of a true `copied_vector` (derived from the captured objects) as an upcoming Package B2 acceptance item.
