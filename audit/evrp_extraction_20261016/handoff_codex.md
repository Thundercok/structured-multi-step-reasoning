# EVRP Extraction Handoff & Decoupling Verification

## 1. Executive Summary

- **Task**: Prepare extraction and decoupling of the embedded EVRP / SaigonRide module (`modules/evrp/`) from the RAT repository into a self-contained unit.
- **Safety Boundary**: This round performs **preparation and verification only**. Zero git commits, pushes, pulls, or resets performed in RAT repo. `modules/evrp/` remains untouched in place until the user specifies the destination repository.
- **Reuse Assessment for RAT–CoT**: **Zero immediate reuse value**. SaigonRide is an ASP.NET vehicle rental web application with Stripe/SePay payments, SignalR kiosks, and EVRP heuristics (`EvrpSolverService.cs`). RAT is a structured reasoning/CoT system with document QA and assistant capabilities. There is no existing or requested routing requirement in RAT; integrating EVRP would create unnecessary maintenance bloat.

---

## 2. Inventory & Provenance Verification

- **Total Regular Files on Disk**: 448 files (41,379,543 bytes, ~41.4 MB).
- **Git Tracking Status**: 447 tracked files, 1 untracked bytecode file (`modules/evrp/scripts/__pycache__/run_benchmark.cpython-312.pyc`, 64,459 bytes).
- **Symlinks**: Exactly 0.
- **Lines of Code (Denominators)**:
  - All text files: 214,349 total lines, **191,214 non-empty lines**.
  - C# source (`.cs`): 160 files, 17,794 non-empty lines.
  - Razor templates (`.cshtml`): 62 files, 4,765 non-empty lines.
  - Scanner-visible source (per `docs/evrp_reuse_audit_20261016.md`): 247 files, **26,903 non-empty lines** (with 10,974 exact-duplicate lines across student submissions).
- **7 Provenance Local Extras**: Verified 100% exact byte-for-byte and size match against `IMPORT_PROVENANCE.json`:
  1. `data/vietnam_charging_stations.csv` (41,774 bytes, SHA256: `06a1097d...`)
  2. `data/vietnam_charging_stations.json` (143,801 bytes, SHA256: `7bf5ccc4...`)
  3. `data/vietnam_charging_stations_raw.json` (132,381 bytes, SHA256: `2aeb7676...`)
  4. `results/benchmark_results.json` (3,681 bytes, SHA256: `93ff48c7...`)
  5. `results/benchmark_table.md` (1,795 bytes, SHA256: `7531125b...`)
  6. `scripts/fetch_charging_stations.py` (3,384 bytes, SHA256: `05ce24ac...`)
  7. `scripts/run_benchmark.py` (45,426 bytes, SHA256: `ded95575...`)

---

## 3. Candidate Destination Repositories

1. **Origin Provenance**: `https://github.com/Thundercok/evrp-optimizer.git` (recorded in `IMPORT_PROVENANCE.json` from subtree import at commit `2c8fa69f8f3cfeae475792159ff0ebcf20529044`).
2. **README Destination Link**: `https://github.com/Thundercok/SaigonRide` (referenced in `modules/evrp/README.md`).
3. **Remote Accessibility**: Both URLs currently return `Repository not found` on unauthenticated queries (likely private or renamed).
4. **Git History Preservation**: All 104 original commits are completely preserved in `.migration-backups/20261013_evrp/evrp-optimizer.bundle` (verified healthy with `git bundle verify`, head commit `2c8fa69f8f3cfeae475792159ff0ebcf20529044`). No history rewriting or squashing has been applied.

---

## 4. Preservation & Restore Verification

- **Pristine Staging**: `work/evrp-extraction-20261016/pristine/` contains all 448 files with identical bytes, permissions, and directory structure.
- **Recovery Bundle**: `scratch/evrp_migration_bundle.tar.gz` (21,619,585 bytes, SHA256: `dd043b68c7f6cfef14503da0efc2962be2b4954e8c63864fc794a2e6a444fe37`).
- **Archive Restore Test (`restore_verification.json`)**: Extracted into an isolated temporary directory: **PASS** (448/448 files matched, 0 content mismatches, 0 permission mismatches).

---

## 5. Decoupling & Isolation Test Verification

- **Dependency Scan (`dependency_reference_report.json`)**: 0 references to `modules/evrp` across `rat/`, `tests/`, `main.py`, or `rat.spec`.
- **Isolated Absence Test (`tests.log`)**:
  - `modules/evrp` was temporarily unmounted from the tree.
  - `rat.kernel.build_default_registry()` initialized cleanly with all 17 registered tool operations.
  - Test suite `.venv/bin/python -m pytest tests/test_spider_adapter.py tests/test_assistant_runtime.py tests/test_work_context.py -q`: **93 passed in 14.08s**.
  - `modules/evrp` restored safely without side effects.

---

## 6. Footprint Accounting (Same-Denominator)

- **Disk Source**: 448 files / 41,379,543 bytes / 191,214 non-empty lines.
- **Current Claimed Reduction**: **0 files / 0 bytes / 0 lines** (truthful accounting: `modules/evrp/` is still in place; staging and archive reside in `work/` and `scratch/`).
- **Projected Reduction upon Deletion**: 448 files, 41.4 MB, 191,214 non-empty lines (or 26,903 scanner-visible lines).

---

## 7. Migration Next Steps (Upon User Destination Input)

1. User specifies target remote URL or local path.
2. Unbundle `.migration-backups/20261013_evrp/evrp-optimizer.bundle` (104 commits) or push pristine staging to target repository.
3. Verify remote repository health.
4. Execute physical removal of `modules/evrp/` in the RAT repository.
