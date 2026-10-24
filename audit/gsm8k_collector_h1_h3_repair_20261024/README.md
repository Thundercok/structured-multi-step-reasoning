# GSM8K Collector & Routing Baseline H1–H3 Repair Dossier — 2026-10-24

**Verdict: H1, H2, and H3 resolved within the offline fixture and software contract scope.**
All repairs have been verified with 0 model/embedding calls, 0 VND spent, no candidate GSM8K 48/48 content inspected or opened, no bridge changes, and Stage 0 Gate unchanged.

---

## 1. Summary of Verified Repairs

| Finding | Severity | Description | Verification Evidence |
| :--- | :--- | :--- | :--- |
| **H1** | **[P1]** | **Bind dispatch arguments to checkpoint identity**: `run_staged_collection` previously allowed caller argument overrides (e.g., mismatched `token_budget`, `master_seed`, `strategies`, or dataset) to dispatch runners or mutate journals under a different declared identity. Fixed by binding all dispatch parameters to `checkpoint.identity` before any dispatch or journal append. Checkpoint creation also validates identity completeness and types. | `test_h1_dispatch_arguments_mismatch_rejected_before_dispatches`, `test_h1_identity_completeness_at_checkpoint_creation`, `verification.json` (`h1_dispatch_binding`: 0 runner dispatches, 0 journal events, 0 manifest mutations). |
| **H2** | **[P1]** | **Explicit evidence allowlist & deferred measured staged path**: `write_fitting_seal` previously permitted non-synthetic labels without validation. Fixed by introducing `ALLOWED_LEGACY_EVIDENCE` and `ALLOWED_STAGED_EVIDENCE`. Staged schema rejects non-synthetic evidence (e.g. `measured_development_pilot`) as deferred until a real model backend adapter is implemented and reviewed. Validates all source hashes are 64-char hex strings and include `experiments/research_study.py`. | `test_h2_staged_measured_evidence_rejected_as_deferred`, `test_h2_staged_invalid_source_hashes_rejected`, `verification.json` (`h2_measured_gate_enforcement`: non-synthetic rejected, seal prevented). |
| **H3** | **[P2]** | **Report full collection cost across all arms and roles**: `write_validation_evaluation` previously computed `full_collection` exclusively from validation records (`val_records`), under-reporting the 6-call collection investment as 3 calls. Fixed by loading the complete bank from `run / "records.json"` and separately reporting `full_collection` (all arms and roles), `validation_only_collection`, and `fitting_only_collection` with accurate generation calls, generated tokens, prompt tokens, and budget charged tokens. | `test_h3_full_collection_cost_reported_across_fitting_and_validation`, `verification.json` (`h3_collection_cost_reporting`: 6 calls / 1500 tokens full vs 3 calls / 450 tokens validation-only). |

---

## 2. Technical Implementation Details

### H1 — Dispatch Argument Binding & Checkpoint Identity Validation
- Added `_validate_initial_contract()` to `GSM8KCollectorCheckpoint.__init__`:
  - Validates all `REQUIRED_IDENTITY_KEYS` (`dataset_name`, `dataset_sha256`, `split_counts`, `prompt_profile_hash`, `source_hashes`, `seed`, `max_tokens`) are present.
  - Ensures `max_tokens` is a positive `int` (strictly `not isinstance(max_tokens, bool)`).
  - Ensures `seed` is an `int` (not bool).
  - Ensures `source_hashes` is a mapping of valid 64-char hexadecimal SHA-256 strings.
  - Validates `dataset_sha256` matches the provided dataset content.
  - Validates dataset items for unique identifiers.
- In `run_staged_collection`:
  - Enforces `require(token_budget == checkpoint.identity["max_tokens"])`.
  - Enforces `require(master_seed == checkpoint.identity["seed"])`.
  - Enforces `require(list(strategies) == list(ACTIONS))`.
  - Enforces `require(hash_dataset_items(dataset) == checkpoint.identity["dataset_sha256"])`.
  - All checks occur before entering the event loop, before invoking `runner.dispatch_item`, and before appending to `journal.jsonl`.

### H2 — Provenance & Evidence Verification on Staged Schema
- Defined explicit allowlists in `experiments/gsm8k_routing_baseline.py`:
  - `ALLOWED_LEGACY_EVIDENCE = {"synthetic_development_pilot", "synthetic_dry_run", "legacy_heuristic"}`
  - `ALLOWED_STAGED_EVIDENCE = {"synthetic_staged_collection", "synthetic_development_pilot"}`
- In `write_fitting_seal`:
  - Validates `manifest["evidence_type"]` against the appropriate allowlist.
  - Specifically intercepts non-synthetic evidence on staged manifests:
    ```python
    if is_staged and manifest.get("evidence_type") not in {"synthetic_staged_collection"}:
        raise ValueError(
            "Measured staged collection is deferred; non-synthetic evidence is not "
            "permitted on staged schema until real model adapter is implemented and reviewed."
        )
    ```
  - Enforces that all `source_hashes` values are 64-char hex strings and that `experiments/research_study.py` is present.

### H3 — Full Collection Cost Reporting
- In `write_validation_evaluation`:
  - Reads `records_file = run / "records.json"` containing all assembled records across fitting and validation splits.
  - Computes `full_collection` from all assembled records in the bank:
    - `generation_calls`: Total generation dispatches across all arms.
    - `generated_tokens`: Total generated tokens produced.
    - `prompt_tokens`: Total prompt tokens ingested.
    - `budget_charged_tokens`: Total tokens charged against budget.
  - Separately computes `validation_only_collection` from `val_records`.
  - Separately computes `fitting_only_collection` from fitting records.
  - Updates summary metrics:
    ```python
    summary["full_collection"] = full_coll
    summary["validation_only_collection"] = val_coll
    summary["fitting_only_collection"] = fit_coll
    ```

---

## 3. Verification & Evidence

### Test Suite Execution
1. **Collector & Routing Suite**:
   - `tests/test_gsm8k_collector.py`: **29 passed** in 2.67s.
2. **Full Regression Suite** (`regression.txt`):
   ```bash
   .venv/bin/python -m pytest tests/test_gsm8k_collector.py tests/test_gsm8k_routing_baseline.py tests/test_checker_dry_run.py tests/test_research_pilot.py tests/test_gsm8k_development.py tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py tests/test_verifiers.py -q
   ```
   - **Result**: **170 passed in 9.37s**, exit 0.

### Standalone Probes (`verification.py` -> `verification.json`)
- Verified that mismatched `token_budget` or `master_seed` raises `ValueError` before dispatches or journal writes (`dispatches: 0, journal_writes: 0`).
- Verified that staged manifests with measured evidence (`measured_development_pilot`) are rejected as deferred before sealing.
- Verified that `write_validation_evaluation` reports 6 calls and 1500 tokens under `full_collection`, 3 calls and 450 tokens under `validation_only_collection`, and 3 calls and 1050 tokens under `fitting_only_collection`.

---

## 4. Integrity and Boundaries Maintained

- **Model Budget**: Strictly 0 real model calls, 0 embedding calls, 0 VND expended.
- **Data Blinding**: Candidate GSM8K 48/48 data remains strictly unread, unopened, and unparsed.
- **Protocol & Gate**: Research bridge and Stage 0 gate unchanged.
- **Git Working Tree**: Preserved uncommitted UI and test session files.
