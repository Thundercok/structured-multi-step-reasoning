"""
audit/spider_rat_adapter_20261016/smoke_live_spider.py — Real Spider binary smoke verification
on a public allowed URL (https://example.com).
"""
import hashlib
import json
from pathlib import Path
import subprocess
import time

from rat.crawler.spider_adapter import SpiderAdapter, PINNED_SPIDER_VERSION
from rat.kernel.capabilities import build_default_registry
from rat.kernel.capabilities.views import view_web_page_snapshot
from rat.kernel.contracts import ArtifactStore
from rat.kernel.dispatcher import ActionDispatcher

def run_smoke():
    out_dir = Path(__file__).resolve().parent
    binary_path = Path("rat/bin/spider").resolve()
    assert binary_path.exists() and os.access(binary_path, os.X_OK), "Spider binary missing in rat/bin/spider"

    # 1. Query version
    version_res = subprocess.run([str(binary_path), "--version"], capture_output=True, text=True)
    version_str = version_res.stdout.strip()
    print(f"Spider binary version: {version_str}")

    # 2. Raw execution on public domain
    cmd = [
        str(binary_path),
        "--url", "https://example.com",
        "--limit", "1",
        "--budget", "*,1",
        "--http",
        "--return-format", "markdown",
        "-H",
        "scrape",
        "--output-html",
    ]
    t0 = time.time()
    raw_proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    duration = time.time() - t0

    raw_evidence = {
        "command": cmd,
        "version": version_str,
        "exit_code": raw_proc.returncode,
        "duration_seconds": round(duration, 3),
        "stdout": raw_proc.stdout,
        "stderr": raw_proc.stderr,
    }
    (out_dir / "smoke_raw_output.json").write_text(json.dumps(raw_evidence, indent=2, ensure_ascii=False))
    print(f"Raw CLI execution completed in {duration:.2f}s with exit code {raw_proc.returncode}")

    # 3. Execution via SpiderAdapter and RAT ActionDispatcher
    adapter = SpiderAdapter(binary_path=binary_path)
    registry = build_default_registry()
    store = ArtifactStore()
    dispatcher = ActionDispatcher(registry, store)

    res = dispatcher.execute_operation("read_web_page", {"url": "https://example.com"})
    assert res.status == "success", f"Dispatch failed: {res.error}"
    assert res.artifact is not None
    art = res.artifact

    artifact_evidence = {
        "artifact_id": art.id,
        "kind": art.kind,
        "revision": art.revision,
        "title": art.title,
        "payload": art.payload,
        "inputs": art.inputs,
        "provenance": art.provenance,
        "created_at": art.created_at,
    }
    (out_dir / "smoke_artifact.json").write_text(json.dumps(artifact_evidence, indent=2, ensure_ascii=False))

    # 4. ViewSpec verification
    spec = view_web_page_snapshot(art, {})
    assert spec.schema_version == 1
    assert "Trang web · example.com" in spec.title

    summary_data = {
        "status": "PASS",
        "target_url": "https://example.com",
        "http_status": art.payload.get("status_code"),
        "content_length_chars": len(art.payload.get("content", "")),
        "content_hash": art.payload.get("content_hash"),
        "engine": art.payload.get("engine"),
        "engine_version": art.payload.get("engine_version"),
        "artifact_stored": store.get(art.id) is not None,
        "view_spec_blocks": len(spec.blocks),
    }
    (out_dir / "smoke_summary.json").write_text(json.dumps(summary_data, indent=2, ensure_ascii=False))
    print("Smoke verification summary:", json.dumps(summary_data, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    import os
    run_smoke()
