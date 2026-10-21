# Review Reconciliation: Spider Adapter Repair after Codex Review Round 2

**Date**: 2026-10-16  
**Branch**: `main`  
**Working Directory**: `/Users/thundercock2/Documents/Github/multi-step-structured-reasoning`  
**Audit Bundle**: `audit/spider_rat_adapter_codex_repair_round2_20261016/`  
**Verdict**: BOTH REMAINING P2 FINDINGS RESOLVED (Tied binary identity cache & Bounded cancellable DNS)

---

## 1. Summary of Actions Taken on Round 2 Findings

| Finding | Severity | Root Cause Identified | Repair Implementation | Verification Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **Cached Binary Identity Not Tied to Execution Target** | **P2** | `verify_backend()` cached `(version, hash)` without checking current file metadata or content on disk; `scrape_page` called `resolve_binary()` a second time after verify. | **Tied BinaryIdentity Caching**: Defined immutable `BinaryIdentity(path, mtime_ns, size, sha256, version)`. Verifies stat and SHA256 before reusing cache; any disk modification or path change invalidates cache immediately (`self._verified_identity = None`). `verify_backend()` returns `(version, hash, verified_bin_path)` and `scrape_page` uses this exact path for execution. Pre-exec check immediately before `Popen` verifies disk hash and mtime match. Documented TOCTOU micro-window limit transparently. | `probe_results.json` (`rejected_on_modification: true`)<br>`test_binary_replaced_on_disk_reverifies_and_rejects`<br>`test_binary_unchanged_reuses_verified_cache` |
| **DNS Not Bounded by Budget & Global Socket Timeout Mutation** | **P2** | `socket.setdefaulttimeout(2.0)` mutated global process state affecting other threads; DNS resolution ran outside monotonic deadline and was not cancellable; `--version` output had no byte cap. | **Bounded Cancellable DNS & Unified Deadline**: Completely removed `socket.setdefaulttimeout()`. Implemented `resolve_dns_bounded()` using `ThreadPoolExecutor(max_workers=1)` polled every 1–5ms against monotonic deadline and `should_cancel()`. Unified monotonic deadline established at start of `scrape_page` and threaded through Phase 1 (DNS), Phase 2 (version verify), Phase 3 (scrape subprocess), and Phase 4 (schema). `--version` output capped at 64 KB using streaming reader. | `probe_results.json` (`elapsed: 0.053s`, `global_timeout_untouched: true`)<br>`test_dns_timeout_bounded_and_global_socket_untouched`<br>`test_dns_cancellation`<br>`test_version_output_over_cap_raises_process_error` |

---

## 2. Technical Implementation Details

### 2.1 Tied Binary Identity & Race Limit (TOCTOU)
1. **`BinaryIdentity` Representation**:
   ```python
   @dataclass(frozen=True)
   class BinaryIdentity:
       path: Path
       mtime_ns: int
       size: int
       sha256: str
       version: str
   ```
2. **Strict Cache Invalidation**:
   Before reusing any cached version, `verify_backend` inspects `bin_path.stat().st_mtime_ns`, `st_size`, and re-computes `sha256`. If the file was edited, replaced, or path resolved differently, cache is invalidated and `--version` is re-executed against the new binary.
3. **Execution Target Consistency**:
   `verify_backend()` returns `(version, bin_hash, verified_bin_path)`. `scrape_page` passes `verified_bin_path` directly to `cmd`, preventing resolver drift between verification and execution.
4. **TOCTOU Micro-Window Boundary**:
   On standard POSIX systems without atomic `fexecve(2)` from an open file descriptor, an unavoidable micro-window exists between file inspection and `execve`. By validating `mtime_ns` and content hash immediately prior to `Popen`, any modification between calls or before the request is reliably detected and rejected.

### 2.2 Bounded Cancellable DNS & Unified Deadline
1. **Zero Global State Mutation**:
   `socket.setdefaulttimeout()` was completely purged. Global socket default is preserved (`None` or initial system default).
2. **ThreadPool DNS Resolution**:
   `resolve_dns_bounded()` runs `socket.getaddrinfo` in a dedicated worker thread, while the main thread monitors the monotonic deadline (`time.monotonic()`) and `should_cancel()` every 1–5 ms. If timeout expires or cancellation is requested, `SpiderTimeoutError` is raised immediately.
3. **End-to-End Monotonic Deadline**:
   `scrape_page` initializes `deadline = start_time + self.timeout_seconds`. Phase 1 (DNS preflight), Phase 2 (version verification), and Phase 3 (scrape execution) share this single budget.
4. **Streaming `--version` with 64 KB Cap**:
   `--version` execution uses `_execute_subprocess` with non-blocking pipes, selector streaming, monotonic deadline, and a 64 KB cap on stdout/stderr, preventing unbounded memory allocation from broken or hostile binaries.

---

## 3. Test Suites & Verification Results

### 3.1 Unit & Contract Tests
- **Command**: `.venv/bin/python -m pytest tests/test_spider_adapter.py -v`
- **Result**: **46 passed in 9.12s** (0 failures).

### 3.2 Kernel & Runtime Regression Tests
- **Command**: `.venv/bin/python -m pytest tests/test_spider_adapter.py tests/test_assistant_runtime.py tests/test_work_context.py -q`
- **Result**: **93 passed in 10.15s** (0 failures).

### 3.3 UI Regression Tests
- **Command**: `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_rat_magic_ui.py -q`
- **Result**: **17 passed in 4.45s** (0 failures).

### 3.4 Round 2 Probes (`audit/spider_rat_adapter_codex_repair_round2_20261016/probe_round2.py`)
```json
{
  "binary_replaced_after_verification": {
    "outcome": "SpiderVersionMismatchError",
    "error": "Spider version mismatch: kỳ vọng version '2.51.208', nhưng backend trả về 'spider_cli 99.0.0'. Từ chối sử dụng binary không khớp version được pin.",
    "accepted_content": null,
    "reported_version": null,
    "reported_hash": null,
    "actual_hash": "843d3a9817fef826cd4b365cf124613a77ea8da01a3c70c834b7fc83018975db",
    "rejected_on_modification": true
  },
  "dns_bounded_without_global_timeout": {
    "configured_timeout_seconds": 0.05,
    "elapsed_seconds": 0.053,
    "global_socket_timeout_before": null,
    "global_socket_timeout_during_dns": [null],
    "global_socket_timeout_after": null,
    "global_timeout_untouched": true,
    "outcome": "SpiderTimeoutError",
    "error": "Quá thời gian chờ khi phân giải DNS cho 'example.com'.",
    "timed_out_properly": true
  },
  "recovery_archive": {
    "archive_sha256": "e883fcfa6f88325d0e80571956f21fb49006bc93855f9a1b6f671536f68ece0f",
    "current_files": 325,
    "archive_regular_files": 325,
    "mismatches": [],
    "archive_extra_files": []
  }
}
```

---

## 4. Debloating & Claims Boundary

1. **Default Gate**:
   `build_default_registry()` sets `enable_web: bool = False`. Web capability is disabled by default and unavailable. RAT does NOT claim that the web capability is safe for general use without per-hop network controls. Per-hop redirect and socket destination enforcement remain in the backlog.
2. **Tree & Footprint Status**:
   - `spider/` source tree remains completely intact (325 regular files, 269 Rust source files, 123,868 non-empty Rust lines, 139,745 non-empty total text lines).
   - Recovery bundle `scratch/spider_migration_bundle.tar.gz` (1.17 MB) has been verified with 100% byte-for-byte parity across all 325 files.
   - **Zero LOC reduction is claimed** at this stage. Physical removal/extraction will occur only after the user designates a target repository.
3. **Repository Cleanliness**:
   No git commits, pushes, pulls, resets, or branch checkouts were performed. Unrelated work from other chats and recovery materials remain preserved.
