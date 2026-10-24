# GSM8K Staged Collector & Sealed Baseline Repair Package — 2026-10-24

This repair package addresses all findings **G1–G5** and the additional integrity hardening requirements raised in the independent review (`audit/gsm8k_collector_implementation_review_20261024/README.md`).

All work is strictly offline: **0 model calls**, **0 inference budget**, **candidate GSM8K 48/48 data uninspected/unopened**, **research bridge preserved**, and **Stage 0 gate unchanged**.

---

## Summary of Verification Evidence

1. **Full Regression Suite**:
   ```bash
   .venv/bin/python -m pytest tests/test_gsm8k_collector.py tests/test_gsm8k_routing_baseline.py tests/test_checker_dry_run.py tests/test_research_pilot.py tests/test_gsm8k_development.py tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py tests/test_verifiers.py -q
   ```
   Result: **165 passed in 7.11s**, exit code 0 (recorded in [regression.txt](regression.txt)).

2. **Automated Verification Probes**:
   ```bash
   .venv/bin/python audit/gsm8k_collector_repair_20261024/verification.py
   ```
   Result: Output recorded in [verification.json](verification.json), verifying that all counterexamples from the review are closed.

---

## Key Repairs Implemented

### G1 — Payload Validation & Strict Conservative Accounting
- **Runtime & Journal Recovery Validation**: Added `validate_staged_generation_result` and `validate_tool_execution_result` in `experiments/gsm8k_collector.py`.
  - Enforces positive, non-boolean integer `generated_tokens` within declared cap `token_budget` (`0 < t <= token_budget`).
  - Enforces non-negative, non-boolean integer `prompt_tokens`.
  - Enforces finite bounded confidence in `[0.0, 1.0]`.
  - Restricts `finish_reason` to supported outcomes (`"stop"`, `"length"`).
  - Enforces non-empty string for `output_text` and non-negative finite duration for `elapsed_ms`.
  - Enforces boolean `ok`, string `output`, and non-negative finite `duration_ms` on tool results.
- **Fail-Closed Accounting**: Invalid payloads (such as `-100`, `2048`, or `True`) immediately raise `ValueError`, log a `generation_outcome` with `status: "failed"` and `cost_status: "unknown_reserved"`, charge the full conservative $1,024$-token reservation to `budget_charged_tokens`, and sync manifest status to `"interrupted"`.
- **Journal Replay Guard**: Replaying a journal containing invalid payload fields fails closed with `ValueError`.

### G2 — Accounting Restoration & Pure Record Reconstruction on Resume
- **Orphan Reservation Restoration**: During `_read_journal`, any attempt with `generation_started` but no terminal outcome restores conservative $1,024$-token reservation to `budget_charge_tokens_total` and marks condition in `unknown_conditions`. Syncing manifest records `status: "quarantined"` with `budget_charged_tokens: 1024`.
- **Pure Record Reconstruction from Durable Evidence**: Implemented `_recover_records_from_terminal_evidence()`. When a process hard-stops after terminal generation (and for PAL, tool) evidence is durably persisted but before `record_assembled` is written:
  - Checkpoint recovery detects that complete terminal evidence exists on disk.
  - Reconstructs the exact assembled record deterministically via `_build_record_from_evidence()`.
  - Appends `record_assembled` event to the journal, marks condition completed, and increments `calls_completed_total`.
  - Resuming collection dispatches only the remaining unstarted conditions (demonstrated: dispatches 5 conditions instead of 6, completing 6/6 records without redispatch or re-execution).

### G3 — Sealed Input Bank & Source Binding
- In `experiments/gsm8k_routing_baseline.py` (`write_validation_evaluation`):
  - **Manifest Hash Check**: Asserts `sha256_file(run / "manifest.json") == manifest["input_manifest_sha256"]`.
  - **Artifact Checksums Check**: Asserts every artifact checksum matches `manifest["input_artifact_sha256"]`.
  - **Source Code & Protocol Binding**: Verifies that `analysis_source_sha256`, `protocol_sha256`, and `atomic_writer_sha256` match sealed values.
  - Any post-seal tampering with input bank outcomes or manifests fails closed immediately.

### G4 — Outcome-Access Isolation & Exposure Ledger
- **Separate Bank Emission**: `run_staged_collection` emits:
  - `records.json`: combined records.
  - `records_fitting.json`: train role records only (`split == "train"`).
  - `records_validation.json`: calibration role records only (`split == "calibration"`).
- **Fitting-Only Reader**: Implemented `load_fitting_bank(run: Path)`. When `records_fitting.json` is present, it loads exclusively from `records_fitting.json` and `dataset.json`. It never opens, reads, or parses `records_validation.json`. Corrupting `records_validation.json` causes zero errors during fitting.
- **Pre-Seal Aggregate Score Suppression**: `summary.json` and `report.md` emitted prior to sealing suppress validation aggregate accuracy and report `validation_accuracy_suppressed: true`.
- **Audit Exposure Ledger**: Maintained `exposure_ledger.json` recording collection, fitting sealing, and validation evaluation events.

### G5 — End-to-End Staged Collection to Analysis Seam
- Updated `write_fitting_seal` to accept `mode: "gsm8k_development_pilot_collection"` manifests from the staged collector.
- Added comprehensive end-to-end integration test (`test_g5_staged_collection_to_fitting_seal_and_validation_e2e`) verifying:
  `staged collect -> fit seal -> validate`, with all 5 methods evaluated, primary comparison computed, and 0 model calls.

### Additional Integrity Hardening
- **Transition State Machine Enforcement**:
  - Enforces `ALLOWED_EVENT_KINDS = {"generation_started", "generation_outcome", "tool_started", "tool_outcome", "record_assembled"}`.
  - Rejects duplicate condition starts across attempts.
  - Enforces proper stage ordering (`tool_started` requires PAL and successful generation; `record_assembled` requires successful generation and terminal tool outcome for PAL).
- **Identity Contract Completeness**:
  - Enforces `REQUIRED_IDENTITY_KEYS` completeness and exact dictionary equality between manifest and run identities.
