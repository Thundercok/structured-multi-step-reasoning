"""
rat.crawler.provenance — macOS File Provenance & Download Origin Extractor.
Extracts source URLs, originating domains, and downloading applications (Safari, Chrome, Telegram, Slack, etc.)
from macOS extended attributes (xattr).
"""

from __future__ import annotations

import logging
import os
import platform
import plistlib
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger("rat.provenance")


class FileProvenanceExtractor:
    """Extracts origin metadata (where from URL, download application) for macOS files."""

    _libc_getxattr = None
    _libc_init_attempted = False

    @classmethod
    def _get_libc_getxattr(cls):
        if not cls._libc_init_attempted:
            cls._libc_init_attempted = True
            if platform.system() == "Darwin":
                try:
                    import ctypes
                    libc = ctypes.cdll.LoadLibrary("libc.dylib")
                    fn = libc.getxattr
                    fn.argtypes = [
                        ctypes.c_char_p,
                        ctypes.c_char_p,
                        ctypes.c_void_p,
                        ctypes.c_size_t,
                        ctypes.c_uint32,
                        ctypes.c_int,
                    ]
                    fn.restype = ctypes.c_ssize_t
                    cls._libc_getxattr = fn
                except Exception as e:
                    logger.debug(f"Could not load libc.getxattr: {e}")
        return cls._libc_getxattr

    @classmethod
    def extract_where_froms(cls, file_path: str) -> List[str]:
        """Extract source URLs from 'com.apple.metadata:kMDItemWhereFroms'."""
        if platform.system() != "Darwin" or not os.path.exists(file_path):
            return []

        # Fast path: libc.getxattr (< 0.01ms, 0 process forks)
        fn = cls._get_libc_getxattr()
        if fn:
            try:
                import ctypes
                p_path = file_path.encode("utf-8")
                p_attr = b"com.apple.metadata:kMDItemWhereFroms"
                size = fn(p_path, p_attr, None, 0, 0, 0)
                if size > 0:
                    buf = ctypes.create_string_buffer(size)
                    bytes_read = fn(p_path, p_attr, buf, size, 0, 0)
                    if bytes_read > 0:
                        parsed = plistlib.loads(buf.raw[:bytes_read])
                        if isinstance(parsed, list):
                            return [str(u).strip() for u in parsed if str(u).strip()]
                        elif isinstance(parsed, str):
                            return [parsed.strip()]
                elif size == -1:
                    # Attribute does not exist on file
                    return []
            except Exception as e:
                logger.debug(f"libc.getxattr where_froms error: {e}")

        # Fallback to subprocess if libc call is unavailable
        try:
            res = subprocess.run(
                ["xattr", "-px", "com.apple.metadata:kMDItemWhereFroms", file_path],
                capture_output=True,
                timeout=1.5
            )
            if res.returncode == 0 and res.stdout:
                hex_data = res.stdout.decode("ascii", errors="ignore").replace(" ", "").replace("\n", "")
                if hex_data:
                    raw_bytes = bytes.fromhex(hex_data)
                    parsed = plistlib.loads(raw_bytes)
                    if isinstance(parsed, list):
                        return [str(u).strip() for u in parsed if str(u).strip()]
                    elif isinstance(parsed, str):
                        return [parsed.strip()]
        except Exception as e:
            logger.debug(f"Failed to extract where_froms for {file_path}: {e}")

        return []

    @classmethod
    def extract_quarantine_app(cls, file_path: str) -> Optional[str]:
        """Extract downloading application name (Safari, Chrome, Telegram, etc.) from quarantine attribute."""
        if platform.system() != "Darwin" or not os.path.exists(file_path):
            return None

        # Fast path: libc.getxattr (< 0.01ms, 0 process forks)
        fn = cls._get_libc_getxattr()
        if fn:
            try:
                import ctypes
                p_path = file_path.encode("utf-8")
                p_attr = b"com.apple.quarantine"
                size = fn(p_path, p_attr, None, 0, 0, 0)
                if size > 0:
                    buf = ctypes.create_string_buffer(size)
                    bytes_read = fn(p_path, p_attr, buf, size, 0, 0)
                    if bytes_read > 0:
                        raw_str = buf.raw[:bytes_read].decode("utf-8", errors="ignore")
                        parts = raw_str.strip().split(";")
                        if len(parts) >= 3 and parts[2].strip():
                            return parts[2].strip()
                elif size == -1:
                    # Attribute does not exist
                    return None
            except Exception as e:
                logger.debug(f"libc.getxattr quarantine error: {e}")

        # Fallback to subprocess if needed
        try:
            res = subprocess.run(
                ["xattr", "-p", "com.apple.quarantine", file_path],
                capture_output=True,
                text=True,
                errors="ignore",
                timeout=1.5
            )
            if res.returncode == 0 and res.stdout:
                parts = res.stdout.strip().split(";")
                if len(parts) >= 3 and parts[2].strip():
                    return parts[2].strip()
        except Exception as e:
            logger.debug(f"Failed to extract quarantine app for {file_path}: {e}")

        return None

    @classmethod
    def get_provenance(cls, file_path: str) -> Dict[str, Any]:
        """
        Extract full provenance metadata for a file.
        Returns:
            {
                "source_urls": [...],
                "source_domains": ["docs.google.com", "github.com"],
                "source_app": "Safari" | "Google Chrome" | "Telegram" | ...,
                "provenance_text": "...searchable summary string..."
            }
        """
        urls = cls.extract_where_froms(file_path)
        app = cls.extract_quarantine_app(file_path)

        domains: List[str] = []
        for u in urls:
            try:
                parsed_url = urlparse(u)
                netloc = parsed_url.netloc.lower()
                # Remove port if present
                if ":" in netloc:
                    netloc = netloc.split(":")[0]
                if netloc and netloc not in domains:
                    domains.append(netloc)
            except Exception:
                continue

        # Build clean searchable text snippet
        provenance_parts = []
        if app:
            provenance_parts.append(f"Tải qua ứng dụng / Ứng dụng tạo: {app}")
        if domains:
            provenance_parts.append(f"Tải từ trang web / Nguồn: {', '.join(domains)}")

        provenance_text = " | ".join(provenance_parts) if provenance_parts else ""

        return {
            "source_urls": urls,
            "source_domains": domains,
            "source_app": app or "",
            "provenance_text": provenance_text,
        }


# Global singleton instance
provenance_extractor = FileProvenanceExtractor()
