# B1 Repair Packet: Strict Typed Origin for Receipt Slots (Round 4)

**Status:** `ready_for_codex_review`  
**Timestamp:** `20261014_220531`  
**Review Target:** B1 Compiler Invariants & R4-1 Resolution  
**Baseline Compiler SHA-256:** `5ec3442d3cd1c0f2ee2f52747ffff02ee5992313bd538dce3f93b7f08ebceb14`  
**Current Compiler SHA-256:** `37259475b6a861b483ecc37f35460844cae0e3daf1ad13f1875170fbfd952c28`  

---

## 1. Executive Summary & Defect Closure (R4-1)

In Codex Review Round 3 (`audit/rat_context_B1_codex_review_current_20261014_210330/review.md`), Finding R4-1 identified that unprojected raw receipt values in native receipt slots (`operation_result`, `note_event`, and `verification_report`) containing wrapper shape `{"$value_ref": ...}` were still interpreted as emitted projector links by `iter_projector_edges` and `_expand_receipt`.

### Root Cause Analysis
Three legitimate paths copy raw values into receipt slots:
1. An operation result with artifact pins, where its native value does not match the pinned artifact payload (no payload substitution occurs).
2. A raw note-event value without a matching canonical event entity.
3. A raw verification-report value from a non-verification issuer.

Previous logic inferred projector emission solely from the presence of `{"$value_ref": ...}` within those slots. As proven by `test_literal_matching_real_projector_target_and_pointer_still_stays_raw`, target kind/pointer whitelisting cannot solve this because a raw literal can coincidentally target the exact same pinned artifact ID, revision, and `/payload` pointer as a real link.

### Unified Architectural Solution: `header["projected_slots"]`
Rather than guessing provenance from value equality or slot names, the pure compiler now explicitly records which receipt slots were projected at compilation time:
1. **Compiler Tracking (`context_snapshot.py:967-1055`):**
   - During receipt header projection in `_build_journal_entities_and_receipts`, whenever a slot (`operation_result`, `note_event`, or `verification_report`) is substituted with a compiler-emitted `$value_ref`, the slot name is recorded into `projected_slots: List[str]`.
   - The list is stored directly on the receipt header: `header["projected_slots"] = projected_slots`.
   - Raw copied values do not have their slot recorded in `projected_slots`.
2. **Edge Extraction (`iter_projector_edges`):**
   - When inspecting receipts in `observed_state.receipts`, `iter_projector_edges` checks:
     ```python
     projected_slots = rcpt.get("projected_slots")
     for slot in ("operation_result", "note_event", "verification_report"):
         if projected_slots is not None and slot not in projected_slots:
             continue
         val = rcpt.get(slot)
         if is_value_ref(val):
             ...
     ```
   - Unprojected raw wrappers are completely excluded from the projector graph edges.
3. **Lossless Decoder (`_expand_receipt`):**
   - `_expand_receipt` consults `rcpt.get("projected_slots")`. If present, only slots explicitly marked in `projected_slots` are expanded.
   - Raw literals remain untouched data across all decoding paths.
4. **Draft2020-12 Schema Compliance:**
   - Evaluated against `snapshot.schema.json`.
   - Receipts in `observed_state.receipts` validate with 0 schema errors.
5. **Positive Control Preserved:**
   - A genuine receipt-to-artifact link pointing to `/payload` continues to faithfully restore literal wrappers inside native payloads without recursively expanding descendants.

---

## 2. Monitored Source Hashes

| File | Baseline Start Hash | Finish Hash | Status |
| --- | --- | --- | --- |
| `rat/engine/context_snapshot.py` | `5ec3442d3cd1c0f2ee2f52747ffff02ee5992313bd538dce3f93b7f08ebceb14` | `37259475b6a861b483ecc37f35460844cae0e3daf1ad13f1875170fbfd952c28` | Modified (R4-1 Fix) |
| `tests/test_rat_context_snapshot.py` | `a0f32c8b5f78e5d447b2ddd75380c88ad38bf07066ee95bc135d0172641591cf` | `2319ea4a9bff02e72af8231aa01a9915d1e89534a8ce46b3790b4bb1c329f043` | Modified (New Regressions) |
| `rat/engine/runtime_context.py` | `99735f064729a469665082ef868530218d24459c12905aeb1d414866874b6bfa` | `a4bbfa94550f75120794e457ee84b0f636467bf1be519e800e157c3444c11328` | Concurrent Runtime Edit |
| `rat/engine/assistant_runtime.py` | `725a2cbe0efc9ae32112e60106d689ea90cd9a3097f876ef0816067bb6fb74e5` | `3bc121160e7845f3408a2fc1bebf2951f478a2eefbfcf8e843232eb21a123eb4` | Concurrent Runtime Edit |
| `rat/engine/completion.py` | `d7b974b2862f08144eb69b82e792bdccb8943737d13cdae3665aea20218f9e3c` | `d7b974b2862f08144eb69b82e792bdccb8943737d13cdae3665aea20218f9e3c` | Unchanged |
| `rat/kernel/contracts.py` | `784fd28626dbd2174574139dfc1de2c73f979f9fe53faddc2bc1a5739bff2972` | `784fd28626dbd2174574139dfc1de2c73f979f9fe53faddc2bc1a5739bff2972` | Unchanged |
| `rat/kernel/dispatcher.py` | `2db4021fa29af75b8dc7b03420e5924c182e18d7b5b22ebd298e28cf454ab6a6` | `2db4021fa29af75b8dc7b03420e5924c182e18d7b5b22ebd298e28cf454ab6a6` | Unchanged |
| `tests/test_rat_context_audit.py` | `39439434c66c64ac3afbdfa71ebb5751c0b345b97da329542a6006ec336afef6` | `39439434c66c64ac3afbdfa71ebb5751c0b345b97da329542a6006ec336afef6` | Unchanged |
| `tests/test_artifact_store_lifecycle.py` | `f38847182e18158504c086e34c47f5492dd3f3dba60ef1d9cea8b94b726e7ecf` | `f38847182e18158504c086e34c47f5492dd3f3dba60ef1d9cea8b94b726e7ecf` | Unchanged |
| `audit/rat_context_B1_codex_review_20261014_123157/review_probes.py` | `6efea8afad295d0e692ff0199469ff26573c7e28cc082324a675527ac206eab8` | `6efea8afad295d0e692ff0199469ff26573c7e28cc082324a675527ac206eab8` | Unchanged (Preserved) |
| `audit/rat_context_B1_codex_review_round2_20261014_151324/provenance_probes.py` | `26fd2f957c0a3129917994dbaf6af864ff1c268571192fa08217b9af1515a61f` | `26fd2f957c0a3129917994dbaf6af864ff1c268571192fa08217b9af1515a61f` | Unchanged (Preserved) |
| `audit/rat_context_B1_independent_20261014_084657/origin_scope_probes.py` | `d2a2aa69d0e09d79caf2c05b98c438956e09f37abb323cd23ee84271d2d2c6d8` | `d2a2aa69d0e09d79caf2c05b98c438956e09f37abb323cd23ee84271d2d2c6d8` | Unchanged (Preserved) |
| `audit/rat_context_B1_codex_review_current_20261014_210330/raw_receipt_probes.py` | `547d94428976feb1d978576866717dd0aceb0c83e4bc57730849be4d84c0b0f1` | `547d94428976feb1d978576866717dd0aceb0c83e4bc57730849be4d84c0b0f1` | Unchanged (Preserved) |
| `audit/rat_context_B_assignment_20261014/snapshot.schema.json` | `8a168a7aaff57e41d43eca956e49e583702bb6ff9285b2f75bcdc135a47da667` | `8a168a7aaff57e41d43eca956e49e583702bb6ff9285b2f75bcdc135a47da667` | Unchanged (Preserved) |

---

## 3. Test Results

### Focused Test Suites: 151 / 151 PASSED (100%)
Command:
```bash
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m pytest \
  tests/test_rat_context_snapshot.py \
  tests/test_rat_context_audit.py \
  tests/test_artifact_store_lifecycle.py \
  audit/rat_context_B1_codex_review_20261014_123157/review_probes.py \
  audit/rat_context_B1_codex_review_round2_20261014_151324/provenance_probes.py \
  audit/rat_context_B1_independent_20261014_084657/origin_scope_probes.py \
  audit/rat_context_B1_codex_review_current_20261014_210330/raw_receipt_probes.py \
  -p no:cacheprovider -q
```
- `raw_receipt_probes.py`: **8 / 8 PASSED** (previously 1 pass, 7 fail).
- `test_rat_context_snapshot.py`: **88 / 88 PASSED** (including 23 new regression cases).
- `test_rat_context_audit.py`: **10 / 10 PASSED**.
- `test_artifact_store_lifecycle.py`: **15 / 15 PASSED**.
- `review_probes.py`: **15 / 15 PASSED**.
- `provenance_probes.py`: **14 / 14 PASSED**.
- `origin_scope_probes.py`: **1 / 1 PASSED**.
- Total: **151 passed in 8.61s**.

---

## 4. Triage of the 6 Core Regression Failures

The exact core test command recorded in `core_run.json` yields **286 passed, 6 failed**. As noted by Codex in `review.md`, these failures stem from concurrent changes to native planner ingress in `rat/engine/assistant_runtime.py:811-857` and `:1041-1052`.

### Source-to-Test Table

| Failing Test | Source Location | Current Implementation Behavior | Test Requirement & Failure Mode |
| --- | --- | --- | --- |
| `contract_probes.py::test_native_planner_schema_can_express_outcomes` | `assistant_runtime.py:811-817` | `_planning_schema()` emits `{"operations": [...], "respond": bool}`. | Requires `"outcomes"` in `schema["properties"]`. Fails with `AssertionError: Native planning schema excludes the declared contract`. |
| `contract_probes.py::test_native_planner_outcomes_are_not_rejected_as_task_state` | `assistant_runtime.py:1026-1065` | Mocked planner responses in tests return `outcomes`, which are now synthesized or rejected depending on generator mock state. | Fails with `StopIteration` due to mock generator expecting old protocol interaction. |
| `test_rat_completion_boundaries.py::test_planner_schema_advertises_typed_expected_args` | `assistant_runtime.py:811-817` | `_planning_schema()` does not advertise `outcomes` or `expected_args`. | Requires `schema["properties"]["outcomes"]["items"]["properties"]["expected_args"]["type"] == "object"`. Fails with `KeyError: 'outcomes'`. |
| `test_rat_completion_boundaries.py::test_malformed_nested_fields_are_invalid_at_all_contract_ingress[source_ref-bad-planner]` | `assistant_runtime.py:1041-1065` | When an operation list plan is received, outcomes are synthesized without nested field validation; `intent_coverage` defaults to `"unchecked"`. | Requires `reconciliation.intent_coverage == "invalid"`. Fails with `AssertionError: assert 'unchecked' == 'invalid'`. |
| `test_rat_completion_boundaries.py::test_malformed_nested_fields_are_invalid_at_all_contract_ingress[target_ref-value1-planner]` | `assistant_runtime.py:1041-1065` | Same as above. | Requires `reconciliation.intent_coverage == "invalid"`. Fails with `AssertionError: assert 'unchecked' == 'invalid'`. |
| `test_rat_completion_boundaries.py::test_malformed_nested_fields_are_invalid_at_all_contract_ingress[expected_args-bad-planner]` | `assistant_runtime.py:1041-1065` | Same as above. | Requires `reconciliation.intent_coverage == "invalid"`. Fails with `AssertionError: assert 'unchecked' == 'invalid'`. |

### Status & Recommendation
- **B1 Isolation:** The B1 compiler patch in `rat/engine/context_snapshot.py` does not touch or influence the planner schema or runtime ingress.
- **Semantic Decision Needed from Codex:** A formal decision is needed whether the native planner protocol should:
  1. Support dual ingress schemas (`operations/respond` simplified tool planning OR typed `outcomes` contract declaration), or
  2. Restore typed `outcomes` and `expected_args` to `_planning_schema()`.
- To avoid overwriting concurrent work or weakening assertions without authorization, the current implementation in `assistant_runtime.py` was left strictly intact.

---

## 5. Packet Manifest

All audit files are preserved in `audit/rat_context_B1_repair_20261014_220531/`:
- `changes.patch`: Unified diff showing the precise `projected_slots` implementation and test regressions.
- `manifest_start.json`: Monitored file hashes at start of turn.
- `manifest_finish.json`: Monitored file hashes after repair.
- `verify_b1.py`: Deterministic verification script executing all roundtrips and test suites.
- `test_run.json`: Complete execution record for focused and core suites.
- `roundtrips.json`: Programmatic verification of literal wrappers, exact types matrix, and schema compliance.
- `validation.json`: Summary assessment with status `ready_for_codex_review`.
- `b2_preparation.md`: Refreshed B2 architectural document accurately mapping dual runtime model boundaries and the 3-point recopy protocol.
