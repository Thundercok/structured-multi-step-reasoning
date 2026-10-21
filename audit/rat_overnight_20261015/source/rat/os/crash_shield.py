"""
rat.os.crash_shield — Enterprise-Grade Crash Protection & Exception Governance for macOS.
Prevents SIGABRT, unhandled slot exceptions, and thread destruction fatal crashes.
"""

from __future__ import annotations

import functools
import logging
import os
import signal
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger("rat.crash_shield")

CRASH_LOG_DIR = Path.home() / ".rat" / "logs"
CRASH_LOG_FILE = CRASH_LOG_DIR / "crash.log"

_SHIELD_INSTALLED = False
_ORIGINAL_EXCEPTHOOK = sys.excepthook


def _write_crash_report(exc_type: Any, exc_value: Any, exc_tb: Any, origin: str = "main") -> None:
    """Safely append crash/exception diagnostics to ~/.rat/logs/crash.log."""
    try:
        CRASH_LOG_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        report = (
            f"\n{'='*70}\n"
            f"💥 UNHANDLED EXCEPTION [{origin.upper()}] at {ts}\n"
            f"Process ID: {os.getpid()} | Thread: {threading.current_thread().name}\n"
            f"Exception: {exc_type.__name__}: {exc_value}\n"
            f"Traceback:\n{tb_str}"
            f"{'='*70}\n"
        )
        with open(CRASH_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(report)
        logger.critical(f"Unhandled exception caught by CrashShield [{origin}]: {exc_type.__name__}: {exc_value}")
    except Exception as io_err:
        sys.stderr.write(f"CrashShield logging failure: {io_err}\n")


def global_excepthook(exc_type: Any, exc_value: Any, exc_tb: Any) -> None:
    """
    Global sys.excepthook replacement.
    Prevents PyQt from calling abort() on unhandled slot exceptions.
    """
    # Allow KeyboardInterrupt to exit normally
    if issubclass(exc_type, KeyboardInterrupt):
        if _ORIGINAL_EXCEPTHOOK:
            _ORIGINAL_EXCEPTHOOK(exc_type, exc_value, exc_tb)
        return

    _write_crash_report(exc_type, exc_value, exc_tb, origin="sys.excepthook")

    # In Qt applications, do not exit; allow UI to stay alive
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            logger.warning("CrashShield intercepted unhandled exception — keeping Qt event loop alive.")
            return
    except Exception:
        pass

    # Fallback to default if no GUI
    if _ORIGINAL_EXCEPTHOOK:
        _ORIGINAL_EXCEPTHOOK(exc_type, exc_value, exc_tb)


def thread_excepthook(args: threading.ExceptHookArgs) -> None:
    """Global threading.excepthook for unhandled exceptions in background threads."""
    _write_crash_report(args.exc_type, args.exc_value, args.exc_traceback, origin=f"thread:{args.thread.name}")


def install_crash_shield() -> None:
    """Install all exception hooks and signal guards across the application."""
    global _SHIELD_INSTALLED
    if _SHIELD_INSTALLED:
        return

    CRASH_LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Sys excepthook
    sys.excepthook = global_excepthook

    # 2. Thread excepthook (Python 3.8+)
    if hasattr(threading, "excepthook"):
        threading.excepthook = thread_excepthook

    # 3. Clean signal termination
    def _handle_signal(signum, frame):
        sig_name = signal.Signals(signum).name
        logger.info(f"CrashShield: Received signal {sig_name} ({signum}). Initiating clean shutdown...")
        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app is not None:
                app.quit()
                return
        except Exception:
            pass
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)
    except Exception as e:
        logger.debug(f"Signal hook note: {e}")

    _SHIELD_INSTALLED = True
    logger.info("🛡️ CrashShield active: Global exception & signal protection engaged.")


def safe_slot(func: Callable) -> Callable:
    """
    Decorator for PyQt slots to trap and log any unexpected exceptions,
    preventing PyQt C++ fatal aborts.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            _write_crash_report(type(e), e, e.__traceback__, origin=f"slot:{func.__name__}")
            logger.error(f"Error in safe_slot [{func.__name__}]: {e}", exc_info=True)
            return None
    return wrapper
