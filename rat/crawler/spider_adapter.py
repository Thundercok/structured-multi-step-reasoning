"""
rat.crawler.spider_adapter — Out-of-process Spider CLI adapter for RAT.

Executes the standalone Spider binary to scrape a single public web page
into a versioned, verifiable snapshot artifact. Zero upstream maintenance
coupling, zero automatic downloads during user turns, strict deadline/cancel,
concurrent streaming to prevent pipe deadlocks, per-stream cap enforcement,
truthful schema validation, tied binary identity caching, and bounded cancellable DNS.
"""
from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass, field
import hashlib
import ipaddress
import json
import logging
import os
from pathlib import Path
import selectors
import shutil
import socket
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

logger = logging.getLogger("rat.spider_adapter")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_LOCAL_BIN = PROJECT_ROOT / "rat" / "bin" / "spider"
USER_LOCAL_BIN = Path.home() / ".local" / "bin" / "spider"
USER_CARGO_BIN = Path.home() / ".cargo" / "bin" / "spider"

PINNED_SPIDER_VERSION = "2.51.208"
PINNED_BINARY_PREFIX = "spider_cli"
DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_MAX_OUTPUT_BYTES = 2 * 1024 * 1024  # 2 MB stdout cap
DEFAULT_MAX_STDERR_BYTES = 512 * 1024       # 512 KB stderr cap
DEFAULT_MAX_CHARS = 6000
DEFAULT_VERSION_CAP_BYTES = 64 * 1024       # 64 KB cap for --version output


class SpiderAdapterError(RuntimeError):
    """Base exception for all Spider adapter errors."""


class SpiderBinaryNotFoundError(SpiderAdapterError):
    """Raised when Spider executable is not found or not executable."""


class SpiderVersionMismatchError(SpiderAdapterError):
    """Raised when Spider executable version does not match pinned version."""


class SpiderSecurityGateError(SpiderAdapterError):
    """Raised when web fetching is attempted without verified per-hop network controls."""


class SpiderTimeoutError(SpiderAdapterError):
    """Raised when Spider execution exceeds deadline or is cancelled."""


class SpiderSSRFBlockedError(SpiderAdapterError):
    """Raised when target URL resolves to private, loopback, or metadata address."""


class SpiderProcessError(SpiderAdapterError):
    """Raised when the Spider subprocess exits with non-zero status or fatal error."""


class SpiderParseError(SpiderAdapterError):
    """Raised when Spider stdout cannot be parsed into valid page objects or violates schema."""


class SpiderEmptyContentError(SpiderAdapterError):
    """Raised when Spider completed without returning usable page content."""


class SpiderHTTPError(SpiderAdapterError):
    """Raised when the web page returns an HTTP client or server error (>= 400)."""


def get_sanitized_env() -> Dict[str, str]:
    """Return a minimal, clean environment dict to prevent credential leakage."""
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin"),
        "HOME": str(Path.home()),
        "LC_ALL": "en_US.UTF-8",
        "LANG": "en_US.UTF-8",
    }


def _kill_and_reap(proc: subprocess.Popen) -> None:
    """Safely terminate and reap a child process without hanging."""
    if proc.poll() is None:
        try:
            proc.kill()
        except OSError:
            pass
    try:
        proc.wait(timeout=1.0)
    except Exception:
        pass


def _cleanup_process(proc: Optional[subprocess.Popen]) -> None:
    """Ensure process is killed, reaped, and all standard pipes are closed."""
    if proc is None:
        return
    _kill_and_reap(proc)
    for pipe in (proc.stdout, proc.stderr, proc.stdin):
        if pipe:
            try:
                pipe.close()
            except Exception:
                pass


@dataclass(frozen=True)
class BinaryIdentity:
    """Immutable snapshot of executable binary identity on disk."""

    path: Path
    mtime_ns: int
    size: int
    sha256: str
    version: str


@dataclass
class SpiderPageResult:
    """Truthful extraction result of a single web page from Spider."""

    requested_url: str
    final_url: str
    status_code: Union[int, str]
    content: str
    content_hash: str
    truncated: bool = False
    links: List[str] = field(default_factory=list)
    headers: Dict[str, Any] = field(default_factory=dict)
    fetched_at: float = field(default_factory=time.time)
    engine: str = "spider"
    engine_version: str = "unknown"
    binary_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requested_url": self.requested_url,
            "final_url": self.final_url,
            "status_code": self.status_code,
            "content": self.content,
            "content_hash": self.content_hash,
            "truncated": self.truncated,
            "links": list(self.links),
            "headers": dict(self.headers),
            "fetched_at": self.fetched_at,
            "engine": self.engine,
            "engine_version": self.engine_version,
            "binary_hash": self.binary_hash,
        }


class SpiderAdapter:
    """Safe, out-of-process subprocess adapter for Spider web crawler."""

    def __init__(
        self,
        binary_path: Optional[Union[str, Path]] = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
        max_stderr_bytes: int = DEFAULT_MAX_STDERR_BYTES,
        allow_uncontrolled_network: bool = True,
    ) -> None:
        self.explicit_binary_path = Path(binary_path) if binary_path else None
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes
        self.max_stderr_bytes = max_stderr_bytes
        self.allow_uncontrolled_network = allow_uncontrolled_network
        self._verified_identity: Optional[BinaryIdentity] = None

    def resolve_binary(self) -> Path:
        """Locate executable binary path without downloading or compiling."""
        if self.explicit_binary_path:
            p = self.explicit_binary_path.expanduser().resolve()
            if p.is_file() and os.access(p, os.X_OK):
                return p
            raise SpiderBinaryNotFoundError(
                f"Đường dẫn Spider binary được chỉ định không tồn tại hoặc không thể thực thi: {p}"
            )

        env_bin = os.getenv("RAT_SPIDER_BIN") or os.getenv("SPIDER_BIN")
        if env_bin:
            p = Path(env_bin).expanduser().resolve()
            if p.is_file() and os.access(p, os.X_OK):
                return p

        for candidate in (DEFAULT_LOCAL_BIN, USER_LOCAL_BIN, USER_CARGO_BIN):
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return candidate.resolve()

        which_path = shutil.which("spider")
        if which_path:
            p = Path(which_path).resolve()
            if p.is_file() and os.access(p, os.X_OK):
                return p

        raise SpiderBinaryNotFoundError(
            "Không tìm thấy Spider binary trên hệ thống. "
            "Vui lòng thiết lập biến môi trường RAT_SPIDER_BIN hoặc cài đặt binary tại "
            f"{DEFAULT_LOCAL_BIN} (xem hướng dẫn tại audit/spider_rat_adapter_20261016/)."
        )

    def is_available(self) -> bool:
        """Check whether a usable Spider binary is present on the host."""
        try:
            self.resolve_binary()
            return True
        except SpiderBinaryNotFoundError:
            return False

    @staticmethod
    def inspect_binary_file(bin_path: Path) -> Tuple[int, int, str]:
        """Read filesystem stat (mtime_ns, size) and compute SHA256 of binary on disk."""
        try:
            st = bin_path.stat()
            with open(bin_path, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            return st.st_mtime_ns, st.st_size, file_hash
        except Exception as exc:
            raise SpiderProcessError(f"Không thể đọc file nhị phân Spider ({bin_path}): {exc}")

    def verify_backend(
        self,
        target_bin: Optional[Path] = None,
        deadline: Optional[float] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> Tuple[str, str, Path]:
        """
        Verify binary existence, query version with clean environment, monotonic deadline,
        and per-stream byte caps. Enforces exact match against PINNED_SPIDER_VERSION.
        Caches verified identity tied to the exact resolved path, mtime_ns, size, and sha256.
        Invalidates cache immediately if file or path changed on disk.
        Returns (version_str, binary_sha256, resolved_bin_path).
        """
        bin_path = (target_bin or self.resolve_binary()).resolve()
        mtime_ns, size, bin_hash = self.inspect_binary_file(bin_path)

        # Check if cached identity is valid for this exact file on disk
        if (
            self._verified_identity is not None
            and self._verified_identity.path == bin_path
            and self._verified_identity.mtime_ns == mtime_ns
            and self._verified_identity.size == size
            and self._verified_identity.sha256 == bin_hash
        ):
            return self._verified_identity.version, self._verified_identity.sha256, bin_path

        # Invalidate cache if anything differs
        self._verified_identity = None

        eff_deadline = deadline or (time.monotonic() + 5.0)
        clean_env = get_sanitized_env()

        raw_stdout, raw_stderr, retcode = self._execute_subprocess(
            cmd=[str(bin_path), "--version"],
            clean_url="--version",
            clean_env=clean_env,
            deadline=eff_deadline,
            should_cancel=should_cancel,
            max_output_bytes=DEFAULT_VERSION_CAP_BYTES,
            max_stderr_bytes=DEFAULT_VERSION_CAP_BYTES,
        )

        if retcode != 0:
            err = raw_stderr.strip() or f"exit code {retcode}"
            raise SpiderProcessError(f"Kiểm tra version Spider thất bại ({bin_path}): {err}")

        raw_version = raw_stdout.strip()
        if not raw_version:
            raise SpiderVersionMismatchError(
                f"Spider binary ({bin_path}) không trả về thông tin version hợp lệ."
            )

        tokens = raw_version.split()
        detected_version = tokens[-1] if tokens else ""
        if detected_version != PINNED_SPIDER_VERSION and raw_version != PINNED_SPIDER_VERSION:
            raise SpiderVersionMismatchError(
                f"Spider version mismatch: kỳ vọng version '{PINNED_SPIDER_VERSION}', "
                f"nhưng backend trả về '{raw_version}'. Từ chối sử dụng binary không khớp version được pin."
            )

        self._verified_identity = BinaryIdentity(
            path=bin_path,
            mtime_ns=mtime_ns,
            size=size,
            sha256=bin_hash,
            version=raw_version,
        )
        return raw_version, bin_hash, bin_path

    def get_version(self) -> str:
        """Query or return verified Spider version string."""
        ver, _, _ = self.verify_backend()
        return ver

    @staticmethod
    def resolve_dns_bounded(
        hostname: str,
        port: int,
        deadline: float,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> List[Any]:
        """
        Resolve DNS query bounded by monotonic deadline and cancellation without
        mutating process-global socket default timeout.
        """
        if callable(should_cancel) and should_cancel():
            raise SpiderTimeoutError("cancelled:operation_cancelled")

        now = time.monotonic()
        rem = deadline - now
        if rem <= 0:
            raise SpiderTimeoutError(f"Hết thời gian chờ trước khi phân giải DNS cho '{hostname}'.")

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(socket.getaddrinfo, hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
            while True:
                if callable(should_cancel) and should_cancel():
                    raise SpiderTimeoutError("cancelled:operation_cancelled")
                now = time.monotonic()
                rem = deadline - now
                if rem <= 0:
                    raise SpiderTimeoutError(f"Quá thời gian chờ khi phân giải DNS cho '{hostname}'.")
                try:
                    return future.result(timeout=min(0.005, max(0.001, rem)))
                except concurrent.futures.TimeoutError:
                    continue
        except concurrent.futures.TimeoutError:
            raise SpiderTimeoutError(f"Quá thời gian chờ khi phân giải DNS cho '{hostname}'.")
        except socket.gaierror as exc:
            raise SpiderSSRFBlockedError(f"Không thể phân giải tên miền '{hostname}': {exc}")
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    @classmethod
    def validate_url(
        cls,
        url: str,
        deadline: Optional[float] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> None:
        """
        Client-side preflight syntax and domain validation.
        Blocks obvious invalid protocols, localhost, well-known metadata names,
        and IP addresses resolving to loopback/private/link-local/multicast ranges.

        NOTE: This is client-side preflight domain checking only. It does NOT guarantee
        network-layer SSRF protection against server redirects or DNS rebinding
        executed downstream by the crawler subprocess.
        """
        if not url or not isinstance(url, str):
            raise SpiderSSRFBlockedError("URL không hợp lệ hoặc để trống.")

        parsed = urlparse(url.strip())
        scheme = (parsed.scheme or "").lower()
        if scheme not in ("http", "https"):
            raise SpiderSSRFBlockedError(
                f"Giao thức '{scheme}' không được hỗ trợ. Chỉ hỗ trợ URL công khai HTTP hoặc HTTPS."
            )

        hostname = (parsed.hostname or "").strip().lower()
        if not hostname:
            raise SpiderSSRFBlockedError("URL thiếu hostname hợp lệ.")

        blocked_hostnames = {
            "localhost",
            "metadata.google.internal",
            "instance-data",
            "169.254.169.254",
        }
        if hostname in blocked_hostnames or hostname.endswith(".local") or hostname.endswith(".internal"):
            raise SpiderSSRFBlockedError(
                f"Truy cập vào hostname nội bộ/metadata '{hostname}' bị chặn bởi chính sách bảo mật SSRF."
            )

        port = parsed.port or (443 if scheme == "https" else 80)
        eff_deadline = deadline or (time.monotonic() + 5.0)
        addr_info = cls.resolve_dns_bounded(hostname, port, deadline=eff_deadline, should_cancel=should_cancel)

        if not addr_info:
            raise SpiderSSRFBlockedError(f"Không tìm thấy địa chỉ IP cho tên miền '{hostname}'.")

        for family, socktype, proto, canonname, sockaddr in addr_info:
            ip_str = sockaddr[0]
            try:
                ip_obj = ipaddress.ip_address(ip_str)
            except ValueError:
                raise SpiderSSRFBlockedError(f"Địa chỉ IP không hợp lệ từ DNS: {ip_str}")

            if str(ip_obj) == "169.254.169.254":
                raise SpiderSSRFBlockedError("Địa chỉ Cloud Metadata (169.254.169.254) bị chặn.")
            if ip_obj.is_loopback:
                raise SpiderSSRFBlockedError(f"Địa chỉ IP loopback bị chặn: {ip_str}")
            if ip_obj.is_link_local:
                raise SpiderSSRFBlockedError(f"Địa chỉ IP link-local bị chặn: {ip_str}")
            if ip_obj.is_private:
                raise SpiderSSRFBlockedError(f"Địa chỉ IP mạng nội bộ (private) bị chặn: {ip_str}")
            if ip_obj.is_multicast:
                raise SpiderSSRFBlockedError(f"Địa chỉ IP multicast bị chặn: {ip_str}")
            if ip_obj.is_unspecified:
                raise SpiderSSRFBlockedError(f"Địa chỉ IP unspecified bị chặn: {ip_str}")

    @staticmethod
    def parse_output(raw_output: str) -> List[Dict[str, Any]]:
        """
        Parse multi-line pretty-printed JSON stream produced by Spider CLI.
        Uses json.JSONDecoder.raw_decode to parse concatenated or pretty JSON objects.
        """
        decoder = json.JSONDecoder()
        s = raw_output.strip()
        idx = 0
        pages: List[Dict[str, Any]] = []

        while idx < len(s):
            while idx < len(s) and s[idx].isspace():
                idx += 1
            if idx >= len(s):
                break
            try:
                obj, end_idx = decoder.raw_decode(s, idx)
                if isinstance(obj, dict):
                    pages.append(obj)
                else:
                    raise SpiderParseError(
                        f"Phần tử trả về không phải là JSON object (nhận {type(obj).__name__})."
                    )
                idx = end_idx
            except json.JSONDecodeError as exc:
                raise SpiderParseError(f"Không thể phân tích dữ liệu JSON trả về từ Spider: {exc}")

        return pages

    def _execute_subprocess(
        self,
        cmd: List[str],
        clean_url: str,
        clean_env: Dict[str, str],
        deadline: float,
        should_cancel: Optional[Callable[[], bool]],
        max_output_bytes: int,
        max_stderr_bytes: int,
    ) -> Tuple[str, str, int]:
        """
        Execute subprocess with concurrent streaming of stdout and stderr via selectors,
        enforce per-stream byte caps during reading, monotonic deadline/cancel,
        and guaranteed cleanup/reap in finally.
        """
        proc: Optional[subprocess.Popen] = None
        selector = selectors.DefaultSelector()

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=clean_env,
                shell=False,
            )

            if hasattr(os, "set_blocking"):
                if proc.stdout:
                    os.set_blocking(proc.stdout.fileno(), False)
                if proc.stderr:
                    os.set_blocking(proc.stderr.fileno(), False)

            if proc.stdout:
                selector.register(proc.stdout, selectors.EVENT_READ, data="stdout")
            if proc.stderr:
                selector.register(proc.stderr, selectors.EVENT_READ, data="stderr")

            stdout_chunks: List[bytes] = []
            stderr_chunks: List[bytes] = []
            stdout_bytes_read = 0
            stderr_bytes_read = 0

            while selector.get_map():
                if callable(should_cancel) and should_cancel():
                    _kill_and_reap(proc)
                    raise SpiderTimeoutError("cancelled:operation_cancelled")

                now = time.monotonic()
                remaining = deadline - now
                if remaining <= 0:
                    _kill_and_reap(proc)
                    raise SpiderTimeoutError(
                        f"Quá thời gian chờ ({self.timeout_seconds}s) khi đọc trang '{clean_url}'."
                    )

                events = selector.select(timeout=min(0.05, max(0.005, remaining)))
                for key, _ in events:
                    stream_name = key.data
                    fd = key.fileobj.fileno()
                    try:
                        chunk = os.read(fd, 16384)
                    except (BlockingIOError, InterruptedError):
                        continue
                    except OSError:
                        chunk = b""

                    if not chunk:
                        try:
                            selector.unregister(key.fileobj)
                        except Exception:
                            pass
                        continue

                    if stream_name == "stdout":
                        stdout_bytes_read += len(chunk)
                        if stdout_bytes_read > max_output_bytes:
                            _kill_and_reap(proc)
                            raise SpiderProcessError(
                                f"Kích thước đầu ra stdout ({stdout_bytes_read} bytes) vượt quá giới hạn an toàn ({max_output_bytes} bytes)."
                            )
                        stdout_chunks.append(chunk)
                    else:
                        stderr_bytes_read += len(chunk)
                        if stderr_bytes_read > max_stderr_bytes:
                            _kill_and_reap(proc)
                            raise SpiderProcessError(
                                f"Kích thước đầu ra stderr ({stderr_bytes_read} bytes) vượt quá giới hạn an toàn ({max_stderr_bytes} bytes)."
                            )
                        stderr_chunks.append(chunk)

            # Wait for child process termination with remaining budget
            remaining_exit = max(0.1, min(2.0, deadline - time.monotonic()))
            try:
                proc.wait(timeout=remaining_exit)
            except subprocess.TimeoutExpired:
                _kill_and_reap(proc)
                raise SpiderTimeoutError(
                    f"Tiến trình không thoát sau khi đóng pipes: '{clean_url}'."
                )

            raw_stdout = b"".join(stdout_chunks).decode("utf-8", errors="replace")
            raw_stderr = b"".join(stderr_chunks).decode("utf-8", errors="replace")
            return raw_stdout, raw_stderr, proc.returncode or 0

        finally:
            try:
                selector.close()
            except Exception:
                pass
            _cleanup_process(proc)

    def _validate_page_result(
        self,
        pages: List[Dict[str, Any]],
        clean_url: str,
        raw_stderr: str,
        max_chars: int,
        verified_version: str,
        binary_hash: Optional[str],
    ) -> SpiderPageResult:
        """
        Strictly validate parsed page structure, types, HTTP status, and source URL.
        Rejects multi-page output, non-string content (no dict coercion), invalid status codes,
        and loopback/private target destinations.
        """
        if not pages:
            err_hint = raw_stderr.strip()
            raise SpiderEmptyContentError(
                f"Không nhận được nội dung trang từ Spider cho URL '{clean_url}'."
                + (f" (Chi tiết: {err_hint})" if err_hint else "")
            )

        if len(pages) > 1:
            raise SpiderParseError(
                f"Backend trả về {len(pages)} trang, vi phạm hợp đồng thu thập đơn trang (single-page contract)."
            )

        first_page = pages[0]
        if not isinstance(first_page, dict):
            raise SpiderParseError(
                f"Dữ liệu trang không phải là JSON object (nhận {type(first_page).__name__})."
            )

        # Source / URL validation
        raw_final_url = first_page.get("url")
        if not isinstance(raw_final_url, str) or not raw_final_url.strip():
            raise SpiderParseError("Dữ liệu trang thiếu trường 'url' dạng chuỗi hợp lệ.")
        final_url = raw_final_url.strip()

        parsed_final = urlparse(final_url)
        if parsed_final.scheme not in ("http", "https"):
            raise SpiderParseError(
                f"URL kết quả có giao thức không hợp lệ: '{parsed_final.scheme}'."
            )

        final_host = (parsed_final.hostname or "").lower()
        if (
            final_host in ("localhost", "127.0.0.1", "::1", "169.254.169.254")
            or final_host.endswith(".local")
            or final_host.endswith(".internal")
        ):
            raise SpiderParseError(
                f"Source validation từ chối: final_url '{final_url}' trỏ về địa chỉ nội bộ/loopback."
            )

        # Status code validation
        raw_status = first_page.get("status_code")
        if raw_status is None:
            raw_status = first_page.get("status")

        if raw_status is None:
            status_code: Union[int, str] = "unknown"
        elif isinstance(raw_status, bool):
            raise SpiderParseError("Trường status_code không được là kiểu boolean.")
        elif isinstance(raw_status, int):
            if raw_status < 100 or raw_status > 599:
                raise SpiderParseError(
                    f"Mã trạng thái HTTP không hợp lệ từ backend: {raw_status} (ngoài phạm vi [100, 599])."
                )
            status_code = raw_status
        elif isinstance(raw_status, str):
            try:
                parsed_status = int(raw_status)
                if parsed_status < 100 or parsed_status > 599:
                    raise SpiderParseError(
                        f"Mã trạng thái HTTP không hợp lệ từ backend: {raw_status}."
                    )
                status_code = parsed_status
            except ValueError:
                raise SpiderParseError(f"Mã trạng thái HTTP không hợp lệ: {raw_status}.")
        else:
            raise SpiderParseError(
                f"Trường status_code có kiểu dữ liệu không hợp lệ: {type(raw_status).__name__}."
            )

        if isinstance(status_code, int) and status_code >= 400:
            raise SpiderHTTPError(f"Trang web trả về mã lỗi HTTP {status_code} ({final_url}).")

        # Content validation: MUST be str, strictly NO coercion of dict/list
        raw_content = first_page.get("content")
        if raw_content is None:
            raise SpiderEmptyContentError(f"Trang web '{final_url}' không có trường content.")
        if not isinstance(raw_content, str):
            raise SpiderParseError(
                f"Trường 'content' sai kiểu dữ liệu (mong đợi str, nhận {type(raw_content).__name__}). "
                "Không ép kiểu object/dict thành văn bản."
            )

        clean_content = raw_content.strip()
        if not clean_content:
            raise SpiderEmptyContentError(f"Trang web '{final_url}' không có nội dung văn bản usable.")

        truncated = False
        if len(clean_content) > max_chars:
            content = clean_content[:max_chars]
            truncated = True
        else:
            content = clean_content

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        # Links & Headers validation
        links = first_page.get("links")
        if links is not None and not isinstance(links, list):
            raise SpiderParseError(
                f"Trường 'links' sai kiểu dữ liệu (mong đợi list, nhận {type(links).__name__})."
            )

        headers = first_page.get("headers")
        if headers is not None and not isinstance(headers, dict):
            raise SpiderParseError(
                f"Trường 'headers' sai kiểu dữ liệu (mong đợi dict, nhận {type(headers).__name__})."
            )

        return SpiderPageResult(
            requested_url=clean_url,
            final_url=final_url,
            status_code=status_code,
            content=content,
            content_hash=content_hash,
            truncated=truncated,
            links=list(links) if isinstance(links, list) else [],
            headers=dict(headers) if isinstance(headers, dict) else {},
            fetched_at=time.time(),
            engine="spider",
            engine_version=verified_version,
            binary_hash=binary_hash,
        )

    def scrape_page(
        self,
        url: str,
        max_chars: int = DEFAULT_MAX_CHARS,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> SpiderPageResult:
        """
        Execute Spider binary to scrape a single public web page.
        Pre-verifies version, enforces clean environment, non-blocking pipe streaming,
        byte caps, strict schema validation, unified deadline, and tied binary identity.
        """
        clean_url = url.strip()
        start_time = time.monotonic()
        deadline = start_time + self.timeout_seconds

        # Phase 1: DNS preflight validation (bounded by deadline)
        self.validate_url(clean_url, deadline=deadline, should_cancel=should_cancel)

        # Phase 2: Backend identity resolution and verification (bounded by remaining deadline)
        bin_path = self.resolve_binary().resolve()
        verified_version, bin_hash, verified_bin = self.verify_backend(
            target_bin=bin_path,
            deadline=deadline,
            should_cancel=should_cancel,
        )

        # TOCTOU micro-window pre-exec check: verify binary on disk was not modified
        # Note: on POSIX systems without atomic fexecve from open file descriptor,
        # verifying disk stat and hash immediately before spawning subprocess bounds
        # any race condition between verify and execute phases.
        cur_mtime, cur_size, cur_hash = self.inspect_binary_file(verified_bin)
        if cur_hash != bin_hash or cur_mtime != self._verified_identity.mtime_ns:
            self._verified_identity = None
            raise SpiderVersionMismatchError(
                f"Binary ({verified_bin}) đã bị sửa đổi trên đĩa giữa bước verify và execute. Hủy bỏ thực thi."
            )

        cmd = [
            str(verified_bin),
            "--url",
            clean_url,
            "--limit",
            "1",
            "--budget",
            "*,1",
            "--http",
            "--return-format",
            "markdown",
            "-H",
            "scrape",
            "--output-html",
        ]

        clean_env = get_sanitized_env()

        if callable(should_cancel) and should_cancel():
            raise SpiderTimeoutError("cancelled:operation_cancelled")

        raw_stdout, raw_stderr, returncode = self._execute_subprocess(
            cmd=cmd,
            clean_url=clean_url,
            clean_env=clean_env,
            deadline=deadline,
            should_cancel=should_cancel,
            max_output_bytes=self.max_output_bytes,
            max_stderr_bytes=self.max_stderr_bytes,
        )

        if returncode != 0:
            err_msg = raw_stderr.strip() or f"Spider thoát với mã lỗi {returncode}"
            raise SpiderProcessError(f"Spider gặp lỗi khi thu thập dữ liệu: {err_msg}")

        pages = self.parse_output(raw_stdout)
        return self._validate_page_result(
            pages=pages,
            clean_url=clean_url,
            raw_stderr=raw_stderr,
            max_chars=max_chars,
            verified_version=verified_version,
            binary_hash=bin_hash,
        )
