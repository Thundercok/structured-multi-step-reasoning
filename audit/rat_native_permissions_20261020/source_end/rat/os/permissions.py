"""macOS Accessibility checks with explicit outcomes and no implicit settings changes."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import logging
import os
from pathlib import Path
import plistlib
import subprocess
import sys

logger = logging.getLogger("rat.permissions")


@dataclass(frozen=True)
class AccessibilityStatus:
    trusted: bool
    state: str
    prompt_requested: bool = False
    error: str | None = None

    def to_dict(self):
        return asdict(self)


def runtime_identity():
    executable = Path(sys.executable).resolve()
    info_path = executable.parent.parent / "Info.plist"
    info = {}
    if getattr(sys, "frozen", False) and info_path.is_file():
        try:
            info = plistlib.loads(info_path.read_bytes())
        except (OSError, ValueError):
            logger.exception("Cannot read running bundle identity")
    return {"pid": os.getpid(), "executable": str(executable),
            "mode": "frozen" if getattr(sys, "frozen", False) else "source",
            "bundle_id": info.get("CFBundleIdentifier"),
            "bundle_path": str(info_path.parent.parent) if info else None,
            "version": info.get("CFBundleShortVersionString")}


def accessibility_status(*, prompt=False):
    if sys.platform != "darwin":
        return AccessibilityStatus(True, "not_required")
    try:
        from ApplicationServices import AXIsProcessTrusted, AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt
        trusted = bool(AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})
                       if prompt else AXIsProcessTrusted())
        status = AccessibilityStatus(trusted, "granted" if trusted else "not_granted", prompt)
        if prompt:
            logger.info("Accessibility request dispatched: state=%s identity=%s", status.state, runtime_identity())
        return status
    except Exception as exc:
        logger.warning("Accessibility %s failed: %s", "request" if prompt else "check", exc, exc_info=True)
        return AccessibilityStatus(False, "unavailable", error=f"{type(exc).__name__}: {exc}")


def is_accessibility_trusted():
    return accessibility_status().trusted


def request_accessibility_permission():
    """Request asynchronously; a dispatched prompt is not a permission grant."""
    return accessibility_status(prompt=True)


def open_accessibility_settings():
    request_accessibility_permission()
    if sys.platform != "darwin":
        return False
    try:
        result = subprocess.run(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"],
                                capture_output=True, text=True, timeout=5)
        if result.returncode:
            logger.error("Opening Accessibility settings failed: %s", result.stderr.strip())
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        logger.exception("Opening Accessibility settings failed")
        return False
