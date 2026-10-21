# Spider Upstream Extraction & Standalone Workspace

## Overview

This directory (`work/spider-extraction-20261016/`) stages the extracted upstream **Spider** crawler codebase for relocation to an independent, dedicated repository.

Prior to this extraction, the Spider source tree was embedded directly inside the RAT (`multi-step-structured-reasoning`) repository under `spider/`. The goal of this decoupling is repository debloating and zero-maintenance isolation: RAT consumes only the standalone compiled CLI binary via `rat/services/spider_adapter.py` and does not compile, link, or maintain any Rust source code.

## Upstream & Version Details

- **Upstream Project**: [spider-rs/spider](https://github.com/spider-rs/spider)
- **License**: MIT License (see `pristine/LICENSE`)
- **Spider CLI Version**: `2.51.208` (`spider_cli/Cargo.toml`)
- **Spider Core Version**: `2.52.0` (`spider/Cargo.toml`)
- **Workspace Crates**:
  - `spider`: Core crawling and scraping engine
  - `spider_cli`: Command-line interface used by RAT
  - `spider_agent`: Web agent automation
  - `spider_agent_html`: HTML parsing and transformation
  - `spider_agent_types`: Shared type definitions
  - `spider_mcp`: Model Context Protocol server implementation
  - `spider_utils`: Utilities and shared helpers
  - `spider_worker`: Distributed crawler worker
- **Inventory Statistics**:
  - Total regular files: 325 (100% byte-matched to `scratch/spider_migration_bundle.tar.gz`)
  - Tracked Rust files: 269 (`.rs` extension, 123,868 non-empty lines)
  - Tracked text files: 321 (139,745 non-empty lines)
  - Executable scripts: `release.sh` (mode `0755`, 38 non-empty lines)

## Directory Structure

```text
work/spider-extraction-20261016/
├── README.md               # This document
├── inventory.json          # Complete 325-file manifest with SHA256 hashes and line metrics
├── patches/
│   └── 0001-fix-workspace-manifest-syntax.patch # Fix for Cargo.toml members syntax error
└── pristine/               # Exact byte-for-byte copy of the 325 files in spider/
```

## Local Modifications & Syntax Patch

The snapshot stored in the RAT repository includes:
1. `release.sh`: Workspace synchronization and publishing shell script.
2. `examples/cv_job_crawler.rs`: Custom recruitment/CV scraping example.
3. Syntax error in root `Cargo.toml`: Lines 11–13 placed an `[[example]]` definition inside the `members = [...]` array, which prevents `cargo` from parsing the root workspace manifest.

To preserve strict byte-for-byte parity with the in-repo snapshot and migration archive, `pristine/` is maintained without modifications.

To build the workspace standalone, apply the provided patch:

```bash
cd pristine
patch -p1 < ../patches/0001-fix-workspace-manifest-syntax.patch
```

This patch moves the `cv_job_crawler` example definition below the `[workspace]` block and removes the invalid member entry.

## Standalone Build Instructions

Prerequisites:
- Rust toolchain (`cargo`, `rustc` 1.80+ recommended)

Build steps:
```bash
# 1. Enter the patched source directory
cd pristine

# 2. Build the spider CLI binary in release mode
cargo build --release -p spider_cli --bin spider

# 3. Verify the binary output
./target/release/spider --version
# Output: spider_cli 2.51.208
```

## Zero-Maintenance Boundary with RAT

RAT integrates with Spider strictly through an external binary boundary:
- **Binary Path**: `rat/bin/spider` (version 2.51.208, SHA256: `bd522395c85cb80df0172066ba8d49dc538dfdec04693dc67455f3a1ee756f54`)
- **Adapter Service**: `rat/services/spider_adapter.py` invokes the binary via `asyncio.subprocess` using standardized CLI flags (`--url`, `--scrape`, `--format json`, `--stealth`, `--return-format raw`).
- **Fail-Closed Default**: RAT's default registry in `rat/work_context/registry.py` specifies `enable_web=False`. Web tools are unavailable by default until per-hop network controls are completed.
- **Packaging Isolation**: `rat.spec` does not bundle `rat/bin/spider`; standalone application packages remain 100% offline.
- **Independence**: RAT has zero build-time, compile-time, or runtime dependencies on the `spider/` source tree.

## Migration to New Repository

When the user specifies the target repository or path:
1. Copy `pristine/` to the destination repository.
2. Apply `patches/0001-fix-workspace-manifest-syntax.patch`.
3. Initialize git (`git init`), create initial commit, and configure upstream remote.
4. Once verified on the remote, delete `spider/` and `scratch/build_spider/` from the RAT repository.
