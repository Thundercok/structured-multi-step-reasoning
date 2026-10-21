# Handoff B1 Repair (Round 2): Complete Invariant Closure for Codex Review

**Date:** 2026-10-14, Asia/Saigon  
**Author:** Antigravity (Anti)  
**Recipient:** Codex  
**Package:** Package B — Step B1 Repair (Final Closure of Findings R2-1 to R2-4)  
**Status:** `ready_for_codex_review` (Codex decides acceptance)  
**Monitored Compiler Baseline:** `8dea28d860d5cb207afb952dfef727628c963442ffc3eaf0d1513aa0d86ab598` (matching Codex Review Round 2)  
**Monitored Test Baseline:** `d1903fdfb891dfcc3c5246fe6f7e3f9355466845f299b968ba52884face5f666`  

---

## 1. Executive Summary & Verification Matrix

In this implementation turn, Antigravity has comprehensively addressed all 4 review findings (R2-1, R2-2, R2-3, R2-4) from Codex Review Round 2 (`audit/rat_context_B1_codex_review_round2_20261014_151324/review.md`). 

All invariant classes have been closed within a unified, typed projector boundary:
1. **Deliverable 1 (Typed Edge Boundary):** Established `iter_projector_edges(snapshot)` as the single shared projector graph definition used across pointer resolution, closure validation, and cycle checking. Raw artifact payloads and unknown plugin results remain completely isolated and never emit projector edges.
2. **Deliverable 2 (Exact Lossless Projection):** Implemented `exact_json_equal(a, b)` enforcing strict recursive type matching (`type(a) is type(b)` distinguishing `bool` vs `int`/`float`, `1 != True`), dict key-set equality, and whitespace preservation across all adapter paths. Checked `quote` and `source_ref.quote` independently, validated replacement text equality before emitting version pointers, and preserved receipt event bodies verbatim on conflicts.
3. **Deliverable 3 (Scope & Proof Eligibility):** Aligned current proof scope with core `completion._in_execution` semantics (`(generation is None or receipt.generation == generation)`). Preserved native receipt headers honestly without synthetic fallback defaults; excluded proofs with missing/foreign generation from current `proof_refs`.
4. **Deliverable 4 (Adversarial Regressions):** Verified against both immutable independent probe files unchanged, and expanded `tests/test_rat_context_snapshot.py` with 9 adversarial matrix tests covering deeply nested raw wrappers, raw literal cycles, escaped RFC 6901 tokens, type invariants, isolated scope dimensions, and input immutability.
5. **Deliverable 5 (B2 Preparation):** Documented complete model-call boundary mapping, retry policies, failure paths, and native message constraints in `b2_preparation.md`. **Zero runtime wiring was performed.**

### Comprehensive Verification Results: 384/384 Tests Passed

All suites executed via `/Library/Frameworks/Python.framework/Versions/3.12/bin/python3` (`PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`):

| Test Suite | Path / Invocation | Tests | Duration | Result |
| :--- | :--- | :---: | :---: | :---: |
| **B1 Unit & Regressions** | `tests/test_rat_context_snapshot.py` | 38 | 0.94s | **100% PASSED** |
| **Codex Round 1 Probes** | `audit/rat_context_B1_codex_review_20261014_123157/review_probes.py` | 15 | 1.16s | **100% PASSED** |
| **Codex Round 2 Probes** | `audit/rat_context_B1_codex_review_round2_20261014_151324/provenance_probes.py` | 14 | 0.94s | **100% PASSED** |
| **Context Audit Suite** | `tests/test_rat_context_audit.py` | 6 | 0.82s | **100% PASSED** |
| **ArtifactStore Lifecycle** | `tests/test_artifact_store_lifecycle.py` | 19 | 0.65s | **100% PASSED** |
| **Core Reconciler Suite** | Exact argv from `audit/rat_core_reconciliation_fix_20261013/test_run.json` | 292 | 7.21s | **100% PASSED** |
| **TOTAL** | **All 6 Test Suites Combined** | **384** | **11.72s** | **100% PASSED** |

---

## 2. Before / After Source Hashes & Drift Audit

| File Path | SHA-256 Before (Start of Turn) | SHA-256 After (Finish of Turn) | Drift / Status |
| :--- | :--- | :--- | :--- |
| `rat/engine/context_snapshot.py` | `8dea28d860d5cb207afb952dfef727628c963442ffc3eaf0d1513aa0d86ab598` | `301476a7d6eeb8e0a0c21da378affaa29f513a8259f9e6af8e96781a389e309e` | Modified (Fixes R2-1..R2-4) |
| `tests/test_rat_context_snapshot.py` | `d1903fdfb891dfcc3c5246fe6f7e3f9355466845f299b968ba52884face5f666` | `a0f32c8b5f78e5d447b2ddd75380c88ad38bf07066ee95bc135d0172641591cf` | Modified (+9 Adversarial Tests) |
| `rat/engine/completion.py` | `d7b974b2862f08144eb69b82e792bdccb8943737d13cdae3665aea20218f9e3c` | `d7b974b2862f08144eb69b82e792bdccb8943737d13cdae3665aea20218f9e3c` | **0 drift (Protected)** |
| `rat/engine/assistant_runtime.py` | `f8a48ad4fb3cb93288d0ed538c07ba08d2701deafb8bf958a77ad351c9dfa5d0` | `f8a48ad4fb3cb93288d0ed538c07ba08d2701deafb8bf958a77ad351c9dfa5d0` | **0 drift (Protected)** |
| `tests/test_rat_completion_boundaries.py` | `8123e6b704edefd3fccafd4af1d48940e437e9a132624382c2ec21f28dcb1286` | `8123e6b704edefd3fccafd4af1d48940e437e9a132624382c2ec21f28dcb1286` | **0 drift (Protected)** |
| `tests/test_rat_context_audit.py` | `39439434c66c64ac3afbdfa71ebb5751c0b345b97da329542a6006ec336afef6` | `39439434c66c64ac3afbdfa71ebb5751c0b345b97da329542a6006ec336afef6` | **0 drift (Protected)** |
| `tests/test_artifact_store_lifecycle.py` | `f38847182e18158504c086e34c47f5492dd3f3dba60ef1d9cea8b94b726e7ecf` | `f38847182e18158504c086e34c47f5492dd3f3dba60ef1d9cea8b94b726e7ecf` | **0 drift (Protected)** |
| `snapshot.schema.json` | `8a168a7aaff57e41d43eca956e49e583702bb6ff9285b2f75bcdc135a47da667` | `8a168a7aaff57e41d43eca956e49e583702bb6ff9285b2f75bcdc135a47da667` | **0 drift (Protected)** |
| `after.snapshot.json` | `19eaedd349194fc139b65121fabdf5ceaf13a79d37d1da22491d9c0fd4edf0e1` | `19eaedd349194fc139b65121fabdf5ceaf13a79d37d1da22491d9c0fd4edf0e1` | **0 drift (Protected)** |
| `declared_args.snapshot.json` | `6215f2c78defe0b8b22ff5d0fe97324559e892c34d3197645e03ad3551e39e1b` | `6215f2c78defe0b8b22ff5d0fe97324559e892c34d3197645e03ad3551e39e1b` | **0 drift (Protected)** |
| `adr-004-rat-context-snapshot.md` | `17ab81dd1248de03858158b9f769f936f834316b05140d4778aca09db88af711` | `17ab81dd1248de03858158b9f769f936f834316b05140d4778aca09db88af711` | **0 drift (Protected)** |
| `review_probes.py` (Round 1) | `6efea8afad295d0e692ff0199469ff26573c7e28cc082324a675527ac206eab8` | `6efea8afad295d0e692ff0199469ff26573c7e28cc082324a675527ac206eab8` | **0 drift (Immutable Probe)** |
| `provenance_probes.py` (Round 2) | `26fd2f957c0a3129917994dbaf6af864ff1c268571192fa08217b9af1515a61f` | `26fd2f957c0a3129917994dbaf6af864ff1c268571192fa08217b9af1515a61f` | **0 drift (Immutable Probe)** |

---

## 3. Finding-to-Change-to-Test Mapping

### Finding R2-1 [P1]: A resolved payload reauthorizes familiar raw keys; validation also treats raw data as graph edges
- **Problem:**
  1. When decoding an outer `operation_result` envelope, resetting `current_path = k` in recursive traversal re-authorized raw descendants if they happened to have familiar names like `quote`, `note`, `snapshot`, or `verification_report`.
  2. The validator inspected every `$value_ref` in every entity body, treating literal `$value_ref` objects inside raw artifact payloads or unknown plugin results as structural graph edges, triggering false dangling pointer or cycle errors.
- **Root Cause Fix:**
  1. Implemented `iter_projector_edges(snapshot)`: an explicit, typed generator yielding only authorized projector origin slots:
     - `note_version` entity bodies: `quote`, `source_ref.quote`, `replaces_text`, `replaced_by_text`.
     - `note_event` entity bodies: `snapshot`.
     - `receipt` bodies: `operation_result` (if pointing to `operation_result` entity), `note_event` (if pointing to `note_event` entity), and `verification_report` (if pointing to `verification_report` entity).
     - Registered `record_work_note` operation results: `note` or `note_event`.
  2. Raw `artifact` and raw `verification_report` bodies are terminal nodes: they never emit edges, and their internal keys never authorize decoding.
  3. Replaced generic tree-walking in `expand_value_refs` with specialized expanders (`_expand_note_version_body`, `_expand_note_event_body`, `_expand_operation_result_body`, `_expand_receipt`). Raw payloads remain completely untouched.
  4. Shared `iter_projector_edges` between `validate_value_refs` and cycle detection so closure and cycle checks traverse the exact same typed graph.
- **Verification:**
  - `provenance_probes.py::test_raw_unknown_result_familiar_key_does_not_authorize_decode[quote/note/snapshot/verification_report]` (PASSED)
  - `provenance_probes.py::test_raw_unknown_result_dangling_literal_ref_is_not_structural_reference` (PASSED)
  - `provenance_probes.py::test_raw_artifact_literal_cycle_is_not_projector_graph_edge` (PASSED)
  - `test_adversarial_raw_wrappers_in_unknown_results_deep_nested` (PASSED)
  - `test_adversarial_raw_artifact_indirect_literal_cycle` (PASSED)

### Finding R2-2 [P1]: Four projection paths still fail exact roundtrip
- **Problem:**
  1. Note `quote` and `source_ref.quote` were coupled: matching the first caused both to be rewritten to the same value, overwriting differing literals.
  2. `replaces_text` and `replaced_by_text` were unconditionally substituted with version pointers without checking if the target note's text actually matched.
  3. Registered note result comparison used Python dict equality, where `True == 1`, mutating integer `1` into boolean `True`.
  4. Receipt `note_event` replaced the event solely by `event_id`, silently overwriting differing event bodies (such as extra fields or custom kinds).
- **Root Cause Fix:**
  1. Implemented recursive `exact_json_equal(a, b)`:
     - Strict type checking: `type(a) is type(b)` (`type(True) is not int`, `1 != 1.0`).
     - Strict key-set equality: `set(a.keys()) == set(b.keys())`.
     - Exact string equality without stripping, coercion, or truncation.
  2. In `_build_note_entities`:
     - Evaluated `raw_quote` and `raw_sref_quote` independently. If `raw_quote` matches source text, it emits `$value_ref`; if `raw_sref_quote` differs, it remains literal string.
     - Checked `replaces_text` against target note text with `exact_json_equal`. If differing, kept verbatim literal string.
     - Escaped RFC 6901 pointer tokens (`~` -> `~0`, `/` -> `~1`) for all path segments.
  3. In `_build_journal_entities_and_receipts`:
     - Used `exact_json_equal` to compare `operation_result.note` with canonical notes, preserving exact numeric/boolean types.
     - Used `exact_json_equal` to compare receipt `note_event` with canonical events; if bodies differ, preserved the literal receipt event intact.
- **Verification:**
  - `provenance_probes.py::test_note_and_source_ref_quote_preserve_independent_exact_values` (PASSED)
  - `provenance_probes.py::test_replacement_text_is_not_rewritten_without_exact_value_match` (PASSED)
  - `provenance_probes.py::test_trusted_note_result_equality_must_distinguish_bool_from_number` (PASSED)
  - `provenance_probes.py::test_receipt_event_same_id_different_body_is_not_silently_replaced` (PASSED)
  - `test_adversarial_exact_json_equal_type_invariants` (PASSED)
  - `test_adversarial_independent_source_quotes_and_replacements` (PASSED)
  - `test_adversarial_rfc6901_escaped_pointer_tokens` (PASSED)

### Finding R2-3 [P2]: Missing generation becomes current proof eligibility
- **Problem:**
  Receipts with `generation = None` matching conversation and execution IDs were added to `observed_state.proof_refs` when boundary generation was 0, violating core `completion._in_execution` which excludes `generation = None` when boundary has a generation. Furthermore, receipt headers filled missing generation with 0.
- **Root Cause Fix:**
  1. In `_build_journal_entities_and_receipts`, aligned proof eligibility with `completion._in_execution`:
     ```python
     is_current_scope = (
         receipt.conversation_id == boundary.conversation_id
         and receipt.execution_id == boundary.execution_id
         and (boundary.generation is None or receipt.generation == boundary.generation)
     )
     ```
  2. Preserved native receipt headers honestly: `receipt_dict["generation"] = receipt.generation` without synthetic fallback assignments.
- **Verification:**
  - `provenance_probes.py::test_proof_without_generation_is_not_current_generation_proof` (PASSED)
  - `test_adversarial_scope_mismatch_dimensions_isolated` (PASSED)

### Finding R2-4 [P2]: Typed proof refs escape closure validation
- **Problem:**
  `observed_state.proof_refs` was not validated during structural closure in `validate_context_snapshot`, allowing missing typed proof refs to pass without an explicit entity or `unavailable_refs` record.
- **Root Cause Fix:**
  Added closure validation for every entry in `observed_state.proof_refs`: each proof reference must resolve to an existing entity in `entities` or be explicitly declared in `unavailable_refs`.
- **Verification:**
  - `provenance_probes.py::test_missing_typed_proof_ref_requires_explicit_unavailable` (PASSED)
  - `test_adversarial_proof_refs_closure_with_and_without_unavailable` (PASSED)

---

## 4. Independent Self-Review of Invariant Classes

### Invariant Class 1: Provenance and Authorization Graph
- **Assertion:** Equality does not establish origin. A raw payload never gains decoding authority by matching a canonical shape, nor by being nested under a trusted receipt envelope.
- **Verification:** The control test `test_unknown_result_equal_canonical_note_remains_raw_control` and adversarial tests confirm that unknown plugins returning note-shaped dicts remain 100% raw. Literal cycles in raw artifacts remain literal data and do not trigger validator graph errors.

### Invariant Class 2: Lossless Representation and Exact Typing
- **Assertion:** No JSON type coercion occurs. `bool` is distinct from `int`, `int` is distinct from `float`, whitespace is preserved verbatim, and dict keys are order-independent but key-set strict.
- **Verification:** Verified via `test_adversarial_exact_json_equal_type_invariants`. Independent quotes in `note.quote` and `source_ref.quote` are never conflated. RFC 6901 pointers correctly encode `~` as `~0` and `/` as `~1`.

### Invariant Class 3: Scope and Identity Integrity
- **Assertion:** Entities are keyed by full scoped tuples `(kind, conversation_id, id, revision)`. Receipts retain native headers without synthetic defaults. Proofs outside the active execution/generation are excluded from `proof_refs`.
- **Verification:** Verified via `test_same_id_revision_in_distinct_conversations_is_distinct_identity_control` and isolated single-dimension scope mismatch regressions.

### Invariant Class 4: Caller Input Immutability
- **Assertion:** Functional compilation, validation, and expansion never mutate caller data structures in-place.
- **Verification:** Verified via `test_adversarial_input_immutability_across_lifecycle`.

---

## 5. Artifacts in Fresh Audit Packet `rat_context_B1_repair_20261014_154609`

- `manifest_start.json`: SHA-256 start baseline (matching Codex round 2 review).
- `manifest_finish.json`: SHA-256 finish baseline showing `changed_during_turn = ['rat/engine/context_snapshot.py', 'tests/test_rat_context_snapshot.py']`, `unauthorized_drift = []`, and `changed_during_tests = []`.
- `changes.patch`: Pristine unified diff (1098 lines) against start-of-turn frozen files.
- `verify_b1.py`: Checked-in deterministic verification script executing all test suites, asserted roundtrips, and hash validations.
- `test_run.json`: Full stdout, stderr, argv, durations, and exit codes for focused and core test suites.
- `roundtrips.json`: 14 programmatically asserted roundtrips across all R2 findings and invariant classes.
- `validation.json`: Validation manifest with status `ready_for_codex_review` and file signatures.
- `b2_preparation.md`: Comprehensive model-call boundary mapping and runtime wiring plan for B2.
- `handoff_codex.md`: This document.

---

## 6. Status and Submission

**B1 Repair is complete and verified.**  
Status is set to: **`ready_for_codex_review`**.  
Codex retains sole authority for B1 acceptance before step B2 implementation begins.
