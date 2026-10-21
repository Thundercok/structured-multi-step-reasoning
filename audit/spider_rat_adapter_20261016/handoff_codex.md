# Handoff & Codex Review: Spider Web Scraping Integration for RAT

**Date**: 2026-10-16  
**Branch**: `main`  
**Working Directory**: `/Users/thundercock2/Documents/Github/multi-step-structured-reasoning`  
**Status**: COMPLETE (Thin slice verified, separation manifest generated, embedded source tree preserved)

---

## 1. Executive Summary

This handoff documents the implementation and verification of the minimal, robust web scraping slice integrating Spider into RAT prior to debloating:
- **User workflow**: User provides a public HTTP/HTTPS URL $\rightarrow$ RAT executes an out-of-process Spider binary (`rat/bin/spider`) $\rightarrow$ generates a verified `web_page_snapshot` artifact (URL, HTTP status, timestamp, SHA256 content hash) $\rightarrow$ assistant runtime tracks observed source and answers based on captured content.
- **Debloating preparation**: The 321-file embedded `spider/` source tree (139,745 non-empty lines) has been inventoried in `separation_manifest.json` with license notices and SHA256 hashes. The source tree remains physically intact pending user confirmation of a target external repository.
- **Zero regressions**: Existing uncommitted files and recovery materials across the repository were strictly preserved. RAT startup and local-file indexing are completely unaffected.

---

## 2. Spider Binary & Adapter Architecture

### 2.1 Pinned Standalone Binary (`rat/bin/spider`)
- **Upstream Crate**: `spider_cli` v2.51.208.
- **Compilation Flags**: Built with minimal HTTP features:
  ```bash
  cargo build --release --no-default-features --features "status_code,headers"
  ```
- **Excluded Features**: Headless Chrome, WARC archival, and `spider_cloud` networking were deliberately excluded to eliminate C++ / Chromium runtime dependencies and minimize binary footprint.
- **Binary Footprint**: 20.7 MB standalone Mach-O executable placed at `rat/bin/spider`. It operates independently of `spider/target/`.

### 2.2 Security & Isolation Guardrails
- **No Shell Interpolation**: Subprocess execution uses explicit argument lists (`argv`), avoiding `shell=True`.
- **Environment Isolation**: Subprocess runs with a sanitized, empty environment (`env={}`) to prevent leakage of cloud tokens, session cookies, or proxy credentials.
- **Strict SSRF Defense**: Comprehensive IP resolution check prior to socket invocation. Blocks:
  - Loopback (`127.0.0.0/8`, `::1`)
  - Private networks (RFC 1918: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`)
  - Link-local addresses (`169.254.0.0/16`, `fe80::/10`)
  - Cloud metadata endpoints (`169.254.169.254`)
  - Multicast / broadcast addresses (`224.0.0.0/4`)
- **Execution Limits**: 15-second process timeout, 2MB stdout capture cap to prevent memory exhaustion, and cooperative cancellation callbacks via `threading.Event`.

### 2.3 Subprocess CLI Order & Stream Parsing
- **Clap Argument Order**: Global arguments (`--url`, `--limit`, `--budget`, `--http`, `--return-format raw`) are passed *before* the `scrape` subcommand. (Placing `--url` after `scrape` causes `spider_cli` to abort with exit code 2).
- **JSON Streaming Parser**: `spider_cli` formats output with `serde_json::to_string_pretty`. The adapter employs `json.JSONDecoder().raw_decode` to reliably parse multi-line indented JSON objects sequentially rather than relying on brittle line-splitting.

---

## 3. Product & Test Changes

### 3.1 Added Files
1. [`rat/crawler/spider_adapter.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/crawler/spider_adapter.py): Subprocess adapter managing binary discovery, SSRF checks, process execution, timeout/cancellation, and stdout parsing.
2. [`rat/kernel/capabilities/web.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/kernel/capabilities/web.py): Web capability definition (`read_web_page`), argument validation, execution contract, and artifact emission (`web_page_snapshot`).
3. [`rat/bin/spider`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/bin/spider): Pinned standalone executable (v2.51.208).
4. [`tests/test_spider_adapter.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/tests/test_spider_adapter.py): 26 contract, unit, and security regression tests.
5. [`audit/spider_rat_adapter_20261016/`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/spider_rat_adapter_20261016/): Complete review audit bundle including manifests, smoke outputs, separation manifest, and footprint metrics.

### 3.2 Modified Files
1. [`rat/kernel/registry.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/kernel/registry.py): Added `get_capability(name)` lookup method.
2. [`rat/kernel/capabilities/__init__.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/kernel/capabilities/__init__.py): Registered `web` capability and `web_page_snapshot` view factory.
3. [`rat/kernel/capabilities/views.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/kernel/capabilities/views.py): Added standard 3-block view renderer (`view_web_page_snapshot`).
4. [`rat/engine/assistant_runtime.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/engine/assistant_runtime.py): Integrated `web_page` into `observed_sources` tracking and added `"Đang đọc trang web…"` progress reporting.
5. [`docs/rat_backlog.md`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/docs/rat_backlog.md): Updated `SPIDER-01` milestone status.
6. [`docs/spider_reuse_audit_20261016.md`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/docs/spider_reuse_audit_20261016.md): Updated with adapter verification results and debloat audit.

---

## 4. Verification & Validation Evidence

### 4.1 Unit & Contract Test Suite
```bash
.venv/bin/python -m pytest tests/test_spider_adapter.py -q
```
- **Result**: **26 passed in 0.99s**.
- **Coverage**: Binary absence detection, non-executable binary handling, SSRF blocks (loopback, RFC 1918, link-local, cloud metadata, multicast), multi-line pretty JSON parsing, truncated output protection, process timeout, process cancellation, isolated environment validation, and kernel capability dispatch.

### 4.2 Kernel & Runtime Regressions
```bash
.venv/bin/python -m pytest tests/test_spider_adapter.py tests/test_assistant_runtime.py tests/test_work_context.py -q
```
- **Result**: **73 passed in 13.05s** (0 regressions).

### 4.3 UI Regressions
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_rat_magic_ui.py -q
```
- **Result**: **17 passed in 7.71s** (0 regressions).

### 4.4 Live Smoke Run
Executed live HTTP scrape against `https://example.com` via [`audit/spider_rat_adapter_20261016/smoke_live_spider.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/spider_rat_adapter_20261016/smoke_live_spider.py):
- **Exit Code**: 0
- **Duration**: 0.614 seconds
- **HTTP Status**: 200
- **Extracted Content Length**: 171 characters
- **Content Hash**: `cbf3f738cc4646f250e5964ab74741b434912a67e1cce86c798bf71af1cf85c8`
- **Artifact**: Successfully created `web_page_snapshot` in `ArtifactStore`.
- **ViewSpec**: Successfully produced 3 visual blocks (summary, text, source metadata).

---

## 5. Graceful Degradation & Preserved Code

- **Binary Missing Scenario**: If `rat/bin/spider` is deleted or unreadable:
  - RAT starts up completely normally.
  - Local file indexing and workspace search are 100% operational.
  - Invoking `web.read_web_page` returns a structured error: `Spider binary not found: rat/bin/spider. Web crawling capability unavailable.`
- **Embedded `spider/` Tree**:
  - The 321 tracked files (139,745 non-empty lines) remain intact in `spider/`.
  - Local changes such as `spider/examples/cv_job_crawler.rs` are preserved.
  - No files were deleted ahead of user instructions.

---

## 6. Known Limitations & Backlog

1. **Redirect Enforcement**: `spider_cli` does not provide CLI flags to configure or forbid HTTP redirects; redirects follow upstream client defaults.
2. **Scrape Scope**: Constrained to single-page retrieval (`budget = 1`, `limit = 1`). Multi-page traversal and domain mapping remain in the backlog.
3. **Headless Chrome**: Excluded to avoid heavy binary bloat. Dynamic SPA JavaScript rendering is deferred to a future headless extension.
4. **Cloud / Distributed Crawling**: `spider_cloud` features are disabled.
5. **Model Invocations**: Passing unit tests confirms kernel and runtime contracts, but does not guarantee an un-finetuned LLM will autonomously invoke the tool without schema prompting or few-shot demonstration.

---

## 7. Debloating & Separation Readiness

All 321 tracked files in `spider/` have been cataloged in `audit/spider_rat_adapter_20261016/separation_manifest.json` with SHA256 checksums, line counts, and license headers.

When the user specifies the target standalone repository (e.g. `Thundercok/spider-crawler`), the embedded `spider/` directory can be safely detached and removed from `Thundercok/nesy-docai` with zero impact on RAT or research pipelines.
