"""
Offline backend identity / deadline probes and read-only recovery verification for Round 2.
"""
import hashlib
import json
from pathlib import Path
import socket
import sys
import tarfile
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from rat.crawler.spider_adapter import (
    SpiderAdapter,
    SpiderTimeoutError,
    SpiderVersionMismatchError,
    PINNED_SPIDER_VERSION,
)

results = {}

with tempfile.TemporaryDirectory() as folder:
    path = Path(folder) / "spider"

    def write(version, content):
        path.write_text(
            f"#!{sys.executable} -S\nimport sys,json\nif '--version' in sys.argv:\n print({repr(version)})\nelse:\n print(json.dumps({{'url':'https://example.com','status_code':200,'content':{repr(content)}}}))\n"
        )
        path.chmod(0o755)

    # -------------------------------------------------------------------------
    # Case 1: Binary replaced after verification
    # -------------------------------------------------------------------------
    write("spider_cli 2.51.208", "first")
    adapter = SpiderAdapter(binary_path=path)
    old_version, old_hash, _ = adapter.verify_backend()

    # Overwrite file on disk at the exact same path
    write("spider_cli 99.0.0", "second backend")
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()

    rejection_outcome = "accepted"
    error_message = ""
    with patch.object(SpiderAdapter, "validate_url", return_value=None):
        try:
            result = adapter.scrape_page("https://example.com")
            accepted_content = result.content
            reported_version = result.engine_version
            reported_hash = result.binary_hash
        except Exception as exc:
            rejection_outcome = type(exc).__name__
            error_message = str(exc)
            accepted_content = None
            reported_version = None
            reported_hash = None

    results["binary_replaced_after_verification"] = {
        "outcome": rejection_outcome,
        "error": error_message,
        "accepted_content": accepted_content,
        "reported_version": reported_version,
        "reported_hash": reported_hash,
        "actual_hash": actual_hash,
        "rejected_on_modification": rejection_outcome == "SpiderVersionMismatchError",
    }

    # -------------------------------------------------------------------------
    # Case 2: Slow DNS bounded by deadline without mutating global socket default
    # -------------------------------------------------------------------------
    write("spider_cli 2.51.208", "ok")
    adapter_dns = SpiderAdapter(binary_path=path, timeout_seconds=0.05)

    orig_global = socket.getdefaulttimeout()
    observed_globals = []

    def slow_dns(*args):
        observed_globals.append(socket.getdefaulttimeout())
        time.sleep(0.3)
        return [(2, 1, 6, "", ("93.184.216.34", 443))]

    start = time.monotonic()
    dns_outcome = "accepted"
    dns_error = ""
    with patch("socket.getaddrinfo", side_effect=slow_dns), patch.object(
        adapter_dns, "verify_backend", return_value=("spider_cli 2.51.208", "fake", path)
    ), patch.object(
        adapter_dns,
        "_execute_subprocess",
        return_value=(json.dumps({"url": "https://example.com", "status_code": 200, "content": "ok"}), "", 0),
    ):
        try:
            result = adapter_dns.scrape_page("https://example.com")
        except Exception as exc:
            dns_outcome = type(exc).__name__
            dns_error = str(exc)

    elapsed_dns = round(time.monotonic() - start, 3)
    results["dns_bounded_without_global_timeout"] = {
        "configured_timeout_seconds": 0.05,
        "elapsed_seconds": elapsed_dns,
        "global_socket_timeout_before": orig_global,
        "global_socket_timeout_during_dns": observed_globals,
        "global_socket_timeout_after": socket.getdefaulttimeout(),
        "global_timeout_untouched": (
            socket.getdefaulttimeout() == orig_global
            and all(g == orig_global for g in observed_globals)
        ),
        "outcome": dns_outcome,
        "error": dns_error,
        "timed_out_properly": dns_outcome == "SpiderTimeoutError" and elapsed_dns < 0.25,
    }

# -------------------------------------------------------------------------
# Case 3: Read-only recovery archive verification
# -------------------------------------------------------------------------
archive = Path("scratch/spider_migration_bundle.tar.gz")
with tarfile.open(archive, "r:gz") as tar:
    mismatches = []
    members = {}
    for m in tar.getmembers():
        if m.isfile():
            members[m.name.removeprefix("./")] = m
    current = {str(p) for p in Path("spider").rglob("*") if p.is_file()}
    for name in current:
        if name not in members:
            mismatches.append("missing:" + name)
            continue
        if (
            hashlib.sha256(Path(name).read_bytes()).digest()
            != hashlib.sha256(tar.extractfile(members[name]).read()).digest()
        ):
            mismatches.append("changed:" + name)
    results["recovery_archive"] = {
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "current_files": len(current),
        "archive_regular_files": len(members),
        "mismatches": mismatches,
        "archive_extra_files": sorted(set(members) - current),
    }

out_dir = Path("audit/spider_rat_adapter_codex_repair_round2_20261016")
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "probe_results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
print(json.dumps(results, indent=2, ensure_ascii=False))
