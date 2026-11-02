"""
tests/test_spider_adapter.py — Behavioral unit & contract tests for Spider adapter,
including network gates, pipe streaming deadlock prevention, byte cap enforcement,
truthful schema validation, pre-request version checks, and RAT kernel integration.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

from rat.crawler.spider_adapter import (
    SpiderAdapter,
    SpiderBinaryNotFoundError,
    SpiderEmptyContentError,
    SpiderHTTPError,
    SpiderParseError,
    SpiderProcessError,
    SpiderSecurityGateError,
    SpiderSSRFBlockedError,
    SpiderTimeoutError,
    SpiderVersionMismatchError,
    get_sanitized_env,
)
from rat.kernel.capabilities import build_default_registry
from rat.kernel.capabilities.views import view_web_page_snapshot
from rat.kernel.capabilities.web import create_web_capability
from rat.kernel.contracts import Artifact, ArtifactStore
from rat.kernel.dispatcher import ActionDispatcher


def create_fake_spider(
    tmp_path: Path,
    script_content: str,
    version: str = "spider_cli 2.51.208",
) -> Path:
    """Create a temporary executable fake Spider script."""
    bin_path = tmp_path / f"fake_spider_{hashlib.md5(script_content.encode()).hexdigest()[:8]}"
    header = f"""#!{sys.executable} -S
import sys
if "--version" in sys.argv:
    print({repr(version)})
    sys.exit(0)
"""
    bin_path.write_text(header + script_content + "\n")
    bin_path.chmod(bin_path.stat().st_mode | stat.S_IEXEC)
    return bin_path


# =============================================================================
# 1. Binary Resolution & Detection
# =============================================================================

def test_resolve_binary_custom_path(tmp_path):
    fake_bin = create_fake_spider(tmp_path, "pass")
    adapter = SpiderAdapter(binary_path=fake_bin)
    assert adapter.resolve_binary() == fake_bin.resolve()
    assert adapter.is_available() is True


def test_resolve_binary_env_var(tmp_path, monkeypatch):
    fake_bin = create_fake_spider(tmp_path, "pass")
    monkeypatch.setenv("RAT_SPIDER_BIN", str(fake_bin))
    adapter = SpiderAdapter()
    assert adapter.resolve_binary() == fake_bin.resolve()


def test_resolve_binary_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("RAT_SPIDER_BIN", str(tmp_path / "nonexistent"))
    monkeypatch.setenv("SPIDER_BIN", str(tmp_path / "nonexistent"))
    monkeypatch.setenv("PATH", str(tmp_path))

    adapter = SpiderAdapter(binary_path=tmp_path / "does_not_exist")
    assert adapter.is_available() is False
    with pytest.raises(SpiderBinaryNotFoundError):
        adapter.resolve_binary()


# =============================================================================
# 2. Version Verification & Identity
# =============================================================================

def test_version_verification_success(tmp_path):
    fake_bin = create_fake_spider(tmp_path, "pass", version="spider_cli 2.51.208")
    adapter = SpiderAdapter(binary_path=fake_bin)
    ver, bin_hash, p = adapter.verify_backend()
    assert ver == "spider_cli 2.51.208"
    assert len(bin_hash) == 64
    assert p == fake_bin.resolve()
    assert adapter.get_version() == "spider_cli 2.51.208"


def test_version_mismatch_rejected(tmp_path):
    fake_bin = create_fake_spider(tmp_path, "pass", version="spider_cli 99.0.0")
    adapter = SpiderAdapter(binary_path=fake_bin)
    with pytest.raises(SpiderVersionMismatchError, match="mismatch"):
        adapter.verify_backend()


def test_version_broken_rejected(tmp_path):
    fake_bin = create_fake_spider(tmp_path, "pass", version="broken-version")
    adapter = SpiderAdapter(binary_path=fake_bin)
    with pytest.raises(SpiderVersionMismatchError):
        adapter.verify_backend()


def test_version_uses_sanitized_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SPIDER_CLOUD_KEY", "SECRET_KEY")
    script = """
import os, sys
if "--version" in sys.argv:
    if "SPIDER_CLOUD_KEY" in os.environ:
        print("LEAKED_ENV")
        sys.exit(1)
    print("spider_cli 2.51.208")
    sys.exit(0)
"""
    bin_path = tmp_path / "env_spider"
    bin_path.write_text(f"#!{sys.executable} -S\n{script}\n")
    bin_path.chmod(bin_path.stat().st_mode | stat.S_IEXEC)

    adapter = SpiderAdapter(binary_path=bin_path)
    ver, _, _ = adapter.verify_backend()
    assert ver == "spider_cli 2.51.208"


# =============================================================================
# 3. URL Preflight & Syntax Validation
# =============================================================================

def test_validate_url_valid_schemes():
    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 80))]
        SpiderAdapter.validate_url("https://example.com/test")
        SpiderAdapter.validate_url("http://example.org:8080/path?query=1")


def test_validate_url_invalid_schemes():
    for bad_url in (
        "ftp://example.com/file",
        "file:///etc/passwd",
        "gopher://example.com",
        "javascript:alert(1)",
        "data:text/html,<h1>Hello</h1>",
        "",
        "not_a_url",
    ):
        with pytest.raises(SpiderSSRFBlockedError):
            SpiderAdapter.validate_url(bad_url)


def test_validate_url_blocks_localhost_and_internal_names():
    for bad_url in (
        "http://localhost:8080",
        "https://localhost/admin",
        "http://test.local",
        "http://myhost.internal",
        "http://metadata.google.internal/computeMetadata/v1/",
    ):
        with pytest.raises(SpiderSSRFBlockedError):
            SpiderAdapter.validate_url(bad_url)


def test_validate_url_blocks_loopback_ips():
    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("127.0.0.1", 80))]
        with pytest.raises(SpiderSSRFBlockedError, match="loopback"):
            SpiderAdapter.validate_url("http://spoofed.domain.com")


def test_validate_url_blocks_private_ips():
    private_ips = ["10.0.0.5", "172.16.50.1", "192.168.1.100", "fc00::1"]
    for ip in private_ips:
        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [(2, 1, 6, "", (ip, 80))]
            with pytest.raises(SpiderSSRFBlockedError, match="mạng nội bộ"):
                SpiderAdapter.validate_url("http://internal.company.com")


def test_validate_url_blocks_link_local_and_cloud_metadata():
    for ip in ("169.254.169.254", "169.254.10.1", "fe80::1"):
        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [(2, 1, 6, "", (ip, 80))]
            with pytest.raises(SpiderSSRFBlockedError, match="(link-local|Metadata)"):
                SpiderAdapter.validate_url("http://cloud-metadata.evil.com")


def test_validate_url_blocks_unspecified_and_multicast():
    for ip in ("0.0.0.0", "224.0.0.1", "::"):
        with patch("socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [(2, 1, 6, "", (ip, 80))]
            with pytest.raises(SpiderSSRFBlockedError):
                SpiderAdapter.validate_url("http://invalid.ip.com")


# =============================================================================
# 4. JSON Output Parsing
# =============================================================================

def test_parse_output_pretty_json():
    pretty_json = """{
  "url": "https://example.com",
  "content": "# Example Domain\\n\\nThis domain is for use in illustrative examples.",
  "links": [
    "https://www.iana.org/domains/example"
  ],
  "headers": {
    "content-type": "text/html; charset=UTF-8"
  },
  "status": 200
}
"""
    pages = SpiderAdapter.parse_output(pretty_json)
    assert len(pages) == 1
    assert pages[0]["url"] == "https://example.com"
    assert pages[0]["status"] == 200
    assert "Example Domain" in pages[0]["content"]
    assert len(pages[0]["links"]) == 1


def test_parse_output_multiple_pages():
    multi_json = """{
  "url": "https://example.com/page1",
  "content": "Page 1",
  "status": 200
}
{
  "url": "https://example.com/page2",
  "content": "Page 2",
  "status": 200
}"""
    pages = SpiderAdapter.parse_output(multi_json)
    assert len(pages) == 2
    assert pages[0]["url"] == "https://example.com/page1"
    assert pages[1]["url"] == "https://example.com/page2"


def test_parse_output_malformed():
    with pytest.raises(SpiderParseError):
        SpiderAdapter.parse_output("Not JSON output at all!")


def test_parse_output_non_dict_rejected():
    with pytest.raises(SpiderParseError, match="không phải là JSON object"):
        SpiderAdapter.parse_output('["array_item"]')


# =============================================================================
# 5. Pipe Streaming Deadlock Prevention & Stream Caps
# =============================================================================

def test_scrape_large_output_no_deadlock(tmp_path):
    """
    Fake binary emits 200,000 chars of valid JSON (> 64 KB OS pipe buffer).
    Must stream without deadlock and succeed well under timeout.
    """
    payload = {
        "url": "https://example.com/large",
        "status_code": 200,
        "content": "x" * 200000,
    }
    script = f"import json; print(json.dumps({json.dumps(payload)}))"
    fake_bin = create_fake_spider(tmp_path, script)
    adapter = SpiderAdapter(binary_path=fake_bin, timeout_seconds=5.0)

    started = time.monotonic()
    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 80))]
        res = adapter.scrape_page("https://example.com/large", max_chars=250000)

    elapsed = time.monotonic() - started
    assert res.status_code == 200
    assert len(res.content) == 200000
    assert elapsed < 2.0


def test_scrape_large_stderr_no_deadlock(tmp_path):
    """Fake binary emits 100 KB on stderr while writing valid stdout."""
    payload = {"url": "https://example.com/ok", "status_code": 200, "content": "valid"}
    script = f"""
import sys, json
sys.stderr.write("E" * 100000)
print(json.dumps({json.dumps(payload)}))
"""
    fake_bin = create_fake_spider(tmp_path, script)
    adapter = SpiderAdapter(binary_path=fake_bin, timeout_seconds=5.0)

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 80))]
        res = adapter.scrape_page("https://example.com/ok")

    assert res.content == "valid"


def test_scrape_stdout_over_cap_raises_process_error(tmp_path):
    """Fake binary emits stdout exceeding max_output_bytes cap; terminated immediately."""
    script = """
import sys
# Emit 500 KB when cap is 100 KB
sys.stdout.write("x" * 500000)
"""
    fake_bin = create_fake_spider(tmp_path, script)
    adapter = SpiderAdapter(binary_path=fake_bin, max_output_bytes=100000, timeout_seconds=5.0)

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 80))]
        with pytest.raises(SpiderProcessError, match="vượt quá giới hạn an toàn"):
            adapter.scrape_page("https://example.com/huge")


def test_scrape_stderr_over_cap_raises_process_error(tmp_path):
    """Fake binary emits stderr exceeding max_stderr_bytes cap; terminated immediately."""
    script = """
import sys
sys.stderr.write("E" * 200000)
"""
    fake_bin = create_fake_spider(tmp_path, script)
    adapter = SpiderAdapter(binary_path=fake_bin, max_stderr_bytes=50000, timeout_seconds=5.0)

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 80))]
        with pytest.raises(SpiderProcessError, match="vượt quá giới hạn an toàn"):
            adapter.scrape_page("https://example.com/err")


def test_scrape_timeout(tmp_path):
    script = "import time; time.sleep(5)"
    fake_bin = create_fake_spider(tmp_path, script)
    adapter = SpiderAdapter(binary_path=fake_bin, timeout_seconds=0.2)

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 80))]
        with pytest.raises(SpiderTimeoutError, match="Quá thời gian chờ"):
            adapter.scrape_page("https://example.com/slow")


def test_scrape_midflight_cancelled(tmp_path):
    script = "import time; time.sleep(5)"
    fake_bin = create_fake_spider(tmp_path, script)
    adapter = SpiderAdapter(binary_path=fake_bin, timeout_seconds=10.0)

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 80))]
        with pytest.raises(SpiderTimeoutError, match="cancelled:operation_cancelled"):
            adapter.scrape_page("https://example.com/cancel", should_cancel=lambda: True)


def test_scrape_page_isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SPIDER_CLOUD_API_KEY", "SECRET_KEY_12345")
    monkeypatch.setenv("SPIDER_CACHE_NAMESPACE", "SECRET_NS")

    script = """
import os, json, sys
spider_vars = [k for k in os.environ if 'SPIDER' in k]
if spider_vars:
    sys.stderr.write('LEAKED_ENV: ' + ','.join(spider_vars))
    sys.exit(1)
payload = {'url': 'https://example.com', 'content': 'Secure', 'status': 200}
print(json.dumps(payload))
"""
    fake_bin = create_fake_spider(tmp_path, script)
    adapter = SpiderAdapter(binary_path=fake_bin)

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 80))]
        res = adapter.scrape_page("https://example.com")
        assert res.content == "Secure"


# =============================================================================
# 6. Schema, Type, Status & Source Validation
# =============================================================================

def test_scrape_dict_content_rejected(tmp_path):
    """Payload with content as dict must raise SpiderParseError without coercion."""
    payload = {
        "url": "https://example.com/doc",
        "status_code": 200,
        "content": {"unexpected": "nested_object"},
    }
    script = f"import json; print(json.dumps({json.dumps(payload)}))"
    fake_bin = create_fake_spider(tmp_path, script)
    adapter = SpiderAdapter(binary_path=fake_bin)

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 80))]
        with pytest.raises(SpiderParseError, match="sai kiểu dữ liệu"):
            adapter.scrape_page("https://example.com/doc")


def test_scrape_list_content_rejected(tmp_path):
    payload = {
        "url": "https://example.com/doc",
        "status_code": 200,
        "content": ["item1", "item2"],
    }
    script = f"import json; print(json.dumps({json.dumps(payload)}))"
    fake_bin = create_fake_spider(tmp_path, script)
    adapter = SpiderAdapter(binary_path=fake_bin)

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 80))]
        with pytest.raises(SpiderParseError, match="sai kiểu dữ liệu"):
            adapter.scrape_page("https://example.com/doc")


def test_scrape_status_code_zero_rejected(tmp_path):
    payload = {"url": "https://example.com/doc", "status_code": 0, "content": "text"}
    script = f"import json; print(json.dumps({json.dumps(payload)}))"
    fake_bin = create_fake_spider(tmp_path, script)
    adapter = SpiderAdapter(binary_path=fake_bin)

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 80))]
        with pytest.raises(SpiderParseError, match="Mã trạng thái HTTP không hợp lệ"):
            adapter.scrape_page("https://example.com/doc")


def test_scrape_status_code_negative_rejected(tmp_path):
    payload = {"url": "https://example.com/doc", "status_code": -1, "content": "text"}
    script = f"import json; print(json.dumps({json.dumps(payload)}))"
    fake_bin = create_fake_spider(tmp_path, script)
    adapter = SpiderAdapter(binary_path=fake_bin)

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 80))]
        with pytest.raises(SpiderParseError, match="Mã trạng thái HTTP không hợp lệ"):
            adapter.scrape_page("https://example.com/doc")


def test_scrape_multiple_pages_rejected(tmp_path):
    """Single-page contract: emitting more than 1 page is rejected."""
    p1 = {"url": "https://example.com/p1", "status_code": 200, "content": "text1"}
    p2 = {"url": "https://example.com/p2", "status_code": 200, "content": "text2"}
    script = f"import json; print(json.dumps({json.dumps(p1)})); print(json.dumps({json.dumps(p2)}))"
    fake_bin = create_fake_spider(tmp_path, script)
    adapter = SpiderAdapter(binary_path=fake_bin)

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 80))]
        with pytest.raises(SpiderParseError, match="vi phạm hợp đồng thu thập đơn trang"):
            adapter.scrape_page("https://example.com/p1")


def test_scrape_final_url_loopback_rejected(tmp_path):
    """Source validation: reject final_url returning private/loopback destination."""
    payload = {
        "url": "http://127.0.0.1/private",
        "status_code": 200,
        "content": "secret data",
    }
    script = f"import json; print(json.dumps({json.dumps(payload)}))"
    fake_bin = create_fake_spider(tmp_path, script)
    adapter = SpiderAdapter(binary_path=fake_bin)

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 80))]
        with pytest.raises(SpiderParseError, match="Source validation từ chối"):
            adapter.scrape_page("https://example.com/redirect")


def test_scrape_page_empty_content(tmp_path):
    payload = {"url": "https://example.com/empty", "content": "", "status_code": 200}
    script = f"import json; print(json.dumps({json.dumps(payload)}))"
    fake_bin = create_fake_spider(tmp_path, script)
    adapter = SpiderAdapter(binary_path=fake_bin)

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 80))]
        with pytest.raises(SpiderEmptyContentError, match="không có nội dung"):
            adapter.scrape_page("https://example.com/empty")


def test_scrape_page_http_error(tmp_path):
    payload = {"url": "https://example.com/404", "content": "Not Found", "status_code": 404}
    script = f"import json; print(json.dumps({json.dumps(payload)}))"
    fake_bin = create_fake_spider(tmp_path, script)
    adapter = SpiderAdapter(binary_path=fake_bin)

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 80))]
        with pytest.raises(SpiderHTTPError, match="HTTP 404"):
            adapter.scrape_page("https://example.com/404")


def test_scrape_page_truncation(tmp_path):
    long_text = "A" * 5000
    payload = {
        "url": "https://example.com/long",
        "content": long_text,
        "status_code": 200,
    }
    script = f"import json; print(json.dumps({json.dumps(payload)}))"
    fake_bin = create_fake_spider(tmp_path, script)
    adapter = SpiderAdapter(binary_path=fake_bin)

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 80))]
        res = adapter.scrape_page("https://example.com/long", max_chars=500)

    assert len(res.content) == 500
    assert res.truncated is True
    assert res.content_hash == hashlib.sha256(res.content.encode("utf-8")).hexdigest()


# =============================================================================
# 7. RAT Kernel & Security Gate Integration
# =============================================================================

def test_default_registry_web_gated_by_default():
    """P1 gate: default registry MUST NOT register web capability by default."""
    registry = build_default_registry()
    assert registry.get_capability("web") is None
    assert registry.has_operation("read_web_page") is False


def test_default_registry_web_enabled_explicitly():
    """Explicitly enabling web capability registers it in registry."""
    registry = build_default_registry(enable_web=True)
    assert registry.get_capability("web") is not None
    assert registry.has_operation("read_web_page") is True


def test_web_capability_fail_closed_when_disabled():
    """When enabled=False, invoking read_web_page returns security-gated error."""
    cap = create_web_capability(enabled=False)
    registry = CapabilityRegistry_mock = build_default_registry()
    registry.register_capability(cap)
    store = ArtifactStore()
    dispatcher = ActionDispatcher(registry, store)

    res = dispatcher.execute_operation("read_web_page", {"url": "https://example.com"})
    assert res.status == "error"
    assert "fail-closed default gate" in res.error
    assert res.artifact is None


def test_dispatch_read_web_page_success(tmp_path):
    payload = {
        "url": "https://docs.python.org/3/",
        "content": "# Python Documentation\\nWelcome to Python 3.12 documentation.",
        "links": ["https://docs.python.org/3/tutorial/"],
        "status_code": 200,
    }
    script = f"import json; print(json.dumps({json.dumps(payload)}))"
    fake_bin = create_fake_spider(tmp_path, script)
    adapter = SpiderAdapter(binary_path=fake_bin)

    cap = create_web_capability(adapter=adapter, enabled=True)
    registry = build_default_registry()
    registry.register_capability(cap)
    store = ArtifactStore()
    dispatcher = ActionDispatcher(registry, store)

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("151.101.0.223", 80))]
        res = dispatcher.execute_operation("read_web_page", {"url": "https://docs.python.org/3/"})

    assert res.status == "success"
    assert res.artifact is not None
    art = res.artifact
    assert art.kind == "web_page_snapshot"
    assert art.payload["final_url"] == "https://docs.python.org/3/"
    assert "Python Documentation" in art.payload["content"]
    assert art.payload["status_code"] == 200
    assert art.payload["content_hash"] == hashlib.sha256(art.payload["content"].encode("utf-8")).hexdigest()

    retrieved = store.get(art.id)
    assert retrieved is not None
    assert retrieved.revision == 1

    spec = view_web_page_snapshot(art, {})
    assert spec.schema_version == 1
    assert "Trang web · docs.python.org" in spec.title
    assert len(spec.blocks) == 3


def test_dispatch_read_web_page_missing_binary(tmp_path):
    adapter = SpiderAdapter(binary_path=tmp_path / "nonexistent_spider")
    cap = create_web_capability(adapter=adapter, enabled=True)
    registry = build_default_registry()
    registry.register_capability(cap)
    store = ArtifactStore()
    dispatcher = ActionDispatcher(registry, store)

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 80))]
        res = dispatcher.execute_operation("read_web_page", {"url": "https://example.com"})

    assert res.status == "error"
    assert "Spider binary" in res.error
    assert res.artifact is None


def test_dispatch_read_web_page_version_mismatch(tmp_path):
    fake_bin = create_fake_spider(tmp_path, "pass", version="spider_cli 99.0.0")
    adapter = SpiderAdapter(binary_path=fake_bin)
    cap = create_web_capability(adapter=adapter, enabled=True)
    registry = build_default_registry()
    registry.register_capability(cap)
    store = ArtifactStore()
    dispatcher = ActionDispatcher(registry, store)

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 80))]
        res = dispatcher.execute_operation("read_web_page", {"url": "https://example.com"})

    assert res.status == "error"
    assert "version mismatch" in res.error.lower()


def test_local_file_flow_unaffected_when_spider_missing(tmp_path):
    registry = build_default_registry()
    store = ArtifactStore()
    dispatcher = ActionDispatcher(registry, store)

    sample_file = tmp_path / "hello.txt"
    sample_file.write_text("Hello world from local file")

    with patch("rat.crawler.db.Database.get_document_by_path") as mock_get_doc:
        mock_get_doc.return_value = {
            "file_path": str(sample_file),
            "file_name": "hello.txt",
            "file_ext": "txt",
        }
        res = dispatcher.execute_operation("read_document", {"file_path": str(sample_file)})

    assert res.status == "success"
    assert res.artifact is not None
    assert res.artifact.kind == "document_content"
    assert res.artifact.payload["content"] == "Hello world from local file"


# =============================================================================
# 8. Round 2 Regressions: Binary Identity Cache Invalidation & Bounded DNS
# =============================================================================

def test_binary_replaced_on_disk_reverifies_and_rejects(tmp_path):
    """
    Codex Round 2 Repro:
    1. Verify fake binary v2.51.208.
    2. Overwrite the file on disk at the exact same path with v99.0.0.
    3. Call scrape_page without manual force=True.
    Adapter must detect the changed disk identity, re-verify, and reject with SpiderVersionMismatchError.
    """
    path = tmp_path / "spider"

    def write_bin(ver, text):
        script = f"""#!{sys.executable} -S
import sys, json
if "--version" in sys.argv:
    print({repr(ver)})
else:
    print(json.dumps({{"url": "https://example.com", "status_code": 200, "content": {repr(text)}}}))
"""
        path.write_text(script)
        path.chmod(0o755)

    write_bin("spider_cli 2.51.208", "first content")
    adapter = SpiderAdapter(binary_path=path)
    old_ver, old_hash, _ = adapter.verify_backend()
    assert old_ver == "spider_cli 2.51.208"

    # Replace file content on disk at identical path
    write_bin("spider_cli 99.0.0", "second content")
    new_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    assert new_hash != old_hash

    # scrape_page must detect modification and reject without manual force=True
    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [(2, 1, 6, "", ("93.184.216.34", 80))]
        with pytest.raises(SpiderVersionMismatchError, match="mismatch"):
            adapter.scrape_page("https://example.com")


def test_binary_unchanged_reuses_verified_cache(tmp_path):
    """When binary on disk is unchanged, cached identity is reused."""
    fake_bin = create_fake_spider(tmp_path, "pass", version="spider_cli 2.51.208")
    adapter = SpiderAdapter(binary_path=fake_bin)
    ver1, hash1, p1 = adapter.verify_backend()

    # Second call should reuse cached identity
    ver2, hash2, p2 = adapter.verify_backend()
    assert ver1 == ver2 == "spider_cli 2.51.208"
    assert hash1 == hash2
    assert p1 == p2


def test_dns_timeout_bounded_and_global_socket_untouched(tmp_path):
    """
    Slow DNS resolver must be bounded by timeout_seconds without mutating
    the global socket.setdefaulttimeout setting.
    """
    fake_bin = create_fake_spider(tmp_path, "pass", version="spider_cli 2.51.208")
    adapter = SpiderAdapter(binary_path=fake_bin, timeout_seconds=0.05)

    import socket
    orig_global = socket.getdefaulttimeout()
    observed_globals = []

    def slow_dns(*args):
        observed_globals.append(socket.getdefaulttimeout())
        time.sleep(0.3)
        return [(2, 1, 6, "", ("93.184.216.34", 443))]

    start = time.monotonic()
    with patch("socket.getaddrinfo", side_effect=slow_dns):
        with pytest.raises(SpiderTimeoutError, match="Quá thời gian chờ"):
            adapter.scrape_page("https://example.com")
    elapsed = time.monotonic() - start

    assert elapsed < 0.25, f"DNS resolution took too long: {elapsed}s"
    assert socket.getdefaulttimeout() == orig_global
    for observed in observed_globals:
        assert observed == orig_global, "Global socket timeout was modified during DNS call!"


def test_dns_cancellation(tmp_path):
    """DNS resolution immediately raises SpiderTimeoutError when cancelled."""
    fake_bin = create_fake_spider(tmp_path, "pass", version="spider_cli 2.51.208")
    adapter = SpiderAdapter(binary_path=fake_bin, timeout_seconds=10.0)

    def blocking_dns(*args):
        time.sleep(1.0)
        return [(2, 1, 6, "", ("93.184.216.34", 443))]

    with patch("socket.getaddrinfo", side_effect=blocking_dns):
        with pytest.raises(SpiderTimeoutError, match="cancelled:operation_cancelled"):
            adapter.scrape_page("https://example.com", should_cancel=lambda: True)


def test_version_output_over_cap_raises_process_error(tmp_path):
    """Version query producing > 64 KB output is immediately terminated by streaming cap."""
    script = """
import sys
if "--version" in sys.argv:
    sys.stdout.write("spider_cli " + "x" * 100000)
    sys.exit(0)
"""
    bin_path = tmp_path / "giant_version_spider"
    bin_path.write_text(f"#!{sys.executable} -S\n{script}\n")
    bin_path.chmod(bin_path.stat().st_mode | stat.S_IEXEC)

    adapter = SpiderAdapter(binary_path=bin_path)
    with pytest.raises(SpiderProcessError, match="vượt quá giới hạn an toàn"):
        adapter.verify_backend()

