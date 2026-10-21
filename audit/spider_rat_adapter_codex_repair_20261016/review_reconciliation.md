# Review Reconciliation: Spider Adapter Repair after Codex Review

**Date**: 2026-10-16  
**Branch**: `main`  
**Working Directory**: `/Users/thundercock2/Documents/Github/multi-step-structured-reasoning`  
**Audit Bundle**: `audit/spider_rat_adapter_codex_repair_20261016/`  
**Verdict**: ALL FINDINGS RESOLVED (2x P1, 2x P2, footprint & migration verified)

---

## 1. Summary of Actions Taken on Review Findings

| Finding | Severity | Root Cause Identified | Repair Implementation | Verification Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **Network Destination & Redirect Control** | **P1** | `build_default_registry` registered web tool by default; `Spider CLI` has `RedirectPolicy::Loose` without per-hop socket binding. | **Default registry fail-closed gate**: `enable_web: bool = False` by default. Web capability is NOT registered in default registry. Direct capability instantiation (`enabled=False`) fails closed with `security_gated: True`. Preflight DNS check clearly documented as domain sanity check, not network SSRF proof. | `runtime_evidence.json`<br>`test_default_registry_web_gated_by_default`<br>`test_web_capability_fail_closed_when_disabled` |
| **Pipe Deadlock on Large Output** | **P1** | Parent called `poll()` in a loop without reading pipes; child blocked on write when stdout > 64 KB pipe buffer. | **Concurrent non-blocking streaming**: Replaced blocking poll with `selectors.DefaultSelector` over non-blocking pipes (`os.set_blocking`). Byte caps (2MB stdout, 512KB stderr) enforced during chunk accumulation. Monotonic deadline & cancellation checks every 50ms. Guaranteed cleanup & process reaping in `finally`. | `fake_binary_evidence.json`<br>`test_scrape_large_output_no_deadlock` (200KB in 0.5s)<br>`test_scrape_stdout_over_cap_raises_process_error` |
| **Schema Coercion & Semantic Status** | **P2** | Adapter coerced `dict` to string via `str()`, accepted status 0, and tolerated multiple pages or loopback final URLs. | **Strict type validation**: Content MUST be `str` (strictly no coercion of dict/list; raises `SpiderParseError`). Status code must be integer $\in [100, 599]$; status 0 or negative rejected. Single-page contract enforced ($N=1$). Post-download source validation rejects loopback/private destinations without claiming network-layer SSRF prevention. | `fake_binary_evidence.json`<br>`test_scrape_dict_content_rejected`<br>`test_scrape_status_code_zero_rejected`<br>`test_scrape_multiple_pages_rejected` |
| **Unpinned Version & Fabricated Fallback** | **P2** | Version queried after scrape, accepted any string containing "spider", fell back to hardcoded `PINNED_SPIDER_VERSION`, and used inherited environment. | **Pre-request version verification**: `verify_backend()` executed before any scrape. Runs with sanitized environment (`get_sanitized_env()`) and 5.0s monotonic deadline. Validates exact match with `PINNED_SPIDER_VERSION` ("2.51.208"). Mismatch or error raises `SpiderVersionMismatchError` / `SpiderProcessError`. Never fabricates pinned version. Computes binary SHA256 hash. | `fake_binary_evidence.json`<br>`test_version_verification_success`<br>`test_version_mismatch_rejected`<br>`test_version_uses_sanitized_env` |
| **Footprint Denominators & Migration Manifest** | **Review Note** | Line counts previously compared text lines to Rust source lines; migration manifest lacked untracked files (`release.sh`). | **Uniform denominators & Verified bundle**: Rust source files (269 files, 123,868 non-empty lines) distinguished from all tracked files (321 files, 139,745 non-empty lines). Tracked and untracked files (`spider/release.sh`) inventoried. Recovery archive created at `scratch/spider_migration_bundle.tar.gz` (1.17 MB) and tested with 100% restoration parity. Source tree preserved intact (0% debloat claimed before physical extraction). | `migration_manifest.json`<br>`footprint.json` |

---

## 2. Test Suites & Verification Results

### 2.1 Unit & Contract Tests
- **Command**: `.venv/bin/python -m pytest tests/test_spider_adapter.py -v`
- **Result**: **41 passed in 10.25s** (0 failures).

### 2.2 Kernel & Runtime Regression Tests
- **Command**: `.venv/bin/python -m pytest tests/test_spider_adapter.py tests/test_assistant_runtime.py tests/test_work_context.py -q`
- **Result**: **88 passed in 23.15s** (0 failures).

### 2.3 UI Regression Tests
- **Command**: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_rat_magic_ui.py -q`
- **Result**: **17 passed in 5.97s** (0 failures).

### 2.4 Live Real Binary Smoke Run
- **Target URL**: `https://example.org`
- **Binary Path**: `rat/bin/spider` (v2.51.208, 20.7 MB, SHA256: `bd522395c85cb80df0172066ba8d49dc538dfdec04693dc67455f3a1ee756f54`)
- **HTTP Status**: 200
- **Extracted Content Length**: 171 characters
- **Content Hash**: `cbf3f738cc4646f250e5964ab74741b434912a67e1cce86c798bf71af1cf85c8`
- **Duration**: 1.24s
- **Dispatcher Result**: Success, `web_page_snapshot` revision 1 stored in `ArtifactStore`, 3 ViewSpec blocks rendered.

---

## 3. Evidence Index

All evidence files are located in `audit/spider_rat_adapter_codex_repair_20261016/`:
1. `fake_binary_evidence.json`: Detailed probe results for large outputs, version mismatches, schema errors, and stream caps.
2. `real_binary_evidence.json`: Live real binary execution metrics on `https://example.org`.
3. `runtime_evidence.json`: Verification of default registry gate (`enable_web=False`) and fail-closed capability behavior.
4. `migration_manifest.json`: Full source tree inventory, untracked release scripts, and verified recovery archive.
5. `footprint.json`: Exact line counts and file sizes reported with identical denominators.

---

## 4. Prepared for Next Codex Review Round

The Spider adapter is now verified, safe, and ready for Codex review. Cây nguồn `spider/` và scratch directory tiếp tục được giữ nguyên trạng thái cho đến khi kho lưu trữ đích được chỉ định.
