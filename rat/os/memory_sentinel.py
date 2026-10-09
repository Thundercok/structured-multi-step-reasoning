"""
rat.os.memory_sentinel — Intelligent macOS Memory Pressure & Idle Eviction Sentinel.
Monitors Darwin kernel memory pressure, system sleep events, and deep inactivity
to gracefully evict heavy ML models (FastEmbed ONNX & tokenizers) and reclaim ~300MB+ RAM.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import logging
import platform
import threading
import time
from typing import Callable, Dict, List, Optional

import psutil

logger = logging.getLogger("rat.os.memory_sentinel")

# Darwin kern.memorystatus_vm_pressure_level constants
PRESSURE_UNKNOWN = 0
PRESSURE_NORMAL = 1
PRESSURE_WARN = 2
PRESSURE_CRITICAL = 4

PRESSURE_NAMES: Dict[int, str] = {
    PRESSURE_UNKNOWN: "UNKNOWN",
    PRESSURE_NORMAL: "NORMAL",
    PRESSURE_WARN: "WARN",
    PRESSURE_CRITICAL: "CRITICAL",
}


def get_darwin_memory_pressure_level() -> int:
    """
    Query Darwin kernel memorystatus VM pressure level via sysctlbyname.
    Returns:
        1: NORMAL
        2: WARN
        4: CRITICAL
        or fallback based on psutil virtual_memory percent.
    """
    if platform.system() == "Darwin":
        try:
            libc = ctypes.CDLL(ctypes.util.find_library("c") or "libSystem.dylib")
            val = ctypes.c_int()
            size = ctypes.c_size_t(ctypes.sizeof(val))
            res = libc.sysctlbyname(
                b"kern.memorystatus_vm_pressure_level",
                ctypes.byref(val),
                ctypes.byref(size),
                None,
                0,
            )
            if res == 0:
                return val.value
        except Exception as e:
            logger.debug(f"sysctlbyname kern.memorystatus_vm_pressure_level failed: {e}")

    # Cross-platform / fallback heuristic via psutil
    try:
        vm = psutil.virtual_memory()
        if vm.percent >= 92.0:
            return PRESSURE_CRITICAL
        elif vm.percent >= 82.0:
            return PRESSURE_WARN
        else:
            return PRESSURE_NORMAL
    except Exception:
        return PRESSURE_NORMAL


class MemorySentinel:
    """
    Resident memory governance service for macOS.
    Monitors:
      1. Darwin memory pressure level (sysctlbyname).
      2. System low-memory notifications (com.apple.system.lowmemory).
      3. Sleep notifications (NSWorkspaceWillSleepNotification).
      4. Extended idle duration (> 45 min by default) when ML models are warmed up.
    """

    def __init__(
        self,
        idle_timeout_seconds: float = 2700.0,  # 45 minutes
        poll_interval_seconds: float = 10.0,
        critical_ram_percent: float = 90.0,
    ) -> None:
        self.idle_timeout_seconds = idle_timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.critical_ram_percent = critical_ram_percent

        self._callbacks: List[Callable[[str], None]] = []
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

        # Darwin notify token
        self._notify_token = ctypes.c_int(-1)
        self._libc = None
        self._sleep_observer = None
        self._nc = None

        # Telemetry / metrics
        self.eviction_count: int = 0
        self.last_eviction_time: float = 0.0
        self.last_eviction_reason: str = ""
        self._last_logged_reason: str = ""
        self._last_logged_time: float = 0.0

    def register_eviction_callback(self, callback: Callable[[str], None]) -> None:
        """Register a function to be invoked when eviction is triggered."""
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def unregister_eviction_callback(self, callback: Callable[[str], None]) -> None:
        """Unregister an eviction callback."""
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def trigger_eviction(self, reason: str) -> int:
        """
        Execute all registered eviction callbacks and run garbage collection.
        Returns the number of callbacks executed.
        """
        executed = 0
        with self._lock:
            self.last_eviction_time = time.time()
            self.last_eviction_reason = reason
            self.eviction_count += 1
            callbacks = list(self._callbacks)

        now = time.time()
        if reason != self._last_logged_reason or (now - self._last_logged_time) >= 60.0:
            logger.info(f"MemorySentinel triggered eviction. Reason: {reason}")
            self._last_logged_reason = reason
            self._last_logged_time = now
        else:
            logger.debug(f"MemorySentinel repeated eviction suppressed. Reason: {reason}")

        for cb in callbacks:
            try:
                try:
                    cb(reason)
                except TypeError:
                    cb()
                executed += 1
            except Exception as e:
                logger.error(f"Error executing eviction callback {cb}: {e}", exc_info=True)

        try:
            import gc
            gc.collect()
        except Exception:
            pass

        return executed

    def _setup_darwin_low_memory_notify(self) -> None:
        """Register for Darwin lowmemory notification token."""
        if platform.system() != "Darwin":
            return
        try:
            self._libc = ctypes.CDLL(ctypes.util.find_library("c") or "libSystem.dylib")
            token = ctypes.c_int(-1)
            res = self._libc.notify_register_check(b"com.apple.system.lowmemory", ctypes.byref(token))
            if res == 0:
                self._notify_token = token
                logger.debug(f"Registered Darwin lowmemory notification (token={token.value})")
        except Exception as e:
            logger.debug(f"Could not register Darwin lowmemory notification: {e}")

    def _check_darwin_low_memory(self) -> bool:
        """Check if com.apple.system.lowmemory has been fired since last check."""
        if self._libc and self._notify_token.value >= 0:
            try:
                check = ctypes.c_int(0)
                res = self._libc.notify_check(self._notify_token, ctypes.byref(check))
                if res == 0 and check.value != 0:
                    return True
            except Exception:
                pass
        return False

    def _setup_sleep_notification(self) -> None:
        """Register for macOS NSWorkspaceWillSleepNotification via PyObjC."""
        if platform.system() != "Darwin":
            return
        try:
            import objc
            from AppKit import NSWorkspace, NSWorkspaceWillSleepNotification
            from Foundation import NSObject

            sentinel_ref = self

            class _SentinelSleepObserver(NSObject):
                def initWithSentinel_(self, sentinel):
                    self = objc.super(_SentinelSleepObserver, self).init()
                    if self is not None:
                        self._sentinel = sentinel
                    return self

                def handleSleep_(self, notification):
                    logger.info("macOS is going to sleep (NSWorkspaceWillSleepNotification). Evicting models.")
                    if self._sentinel:
                        self._sentinel.trigger_eviction("macos_sleep")

            self._sleep_observer = _SentinelSleepObserver.alloc().initWithSentinel_(sentinel_ref)
            self._nc = NSWorkspace.sharedWorkspace().notificationCenter()
            self._nc.addObserver_selector_name_object_(
                self._sleep_observer,
                "handleSleep:",
                NSWorkspaceWillSleepNotification,
                None,
            )
            logger.debug("Registered macOS NSWorkspaceWillSleepNotification observer.")
        except Exception as e:
            logger.debug(f"Could not register NSWorkspace sleep observer: {e}")

    def _teardown_sleep_notification(self) -> None:
        """Remove NSWorkspace sleep observer."""
        if self._nc and self._sleep_observer:
            try:
                self._nc.removeObserver_(self._sleep_observer)
            except Exception:
                pass
            self._sleep_observer = None
            self._nc = None

    def _teardown_darwin_low_memory_notify(self) -> None:
        """Cancel Darwin notification token."""
        if self._libc and self._notify_token.value >= 0:
            try:
                self._libc.notify_cancel(self._notify_token)
            except Exception:
                pass
            self._notify_token = ctypes.c_int(-1)

    def check_memory_pressure_and_evict(self) -> bool:
        """
        Check current memory pressure level or low-memory token.
        If under pressure, triggers eviction and returns True.
        """
        level = get_darwin_memory_pressure_level()
        if level in (PRESSURE_WARN, PRESSURE_CRITICAL):
            reason = f"memory_pressure_{PRESSURE_NAMES.get(level, level)}"
            self.trigger_eviction(reason)
            return True

        if self._check_darwin_low_memory():
            self.trigger_eviction("darwin_lowmemory_notify")
            return True

        try:
            vm = psutil.virtual_memory()
            if vm.percent >= self.critical_ram_percent:
                self.trigger_eviction(f"system_ram_exceeded_{vm.percent:.1f}pct")
                return True
        except Exception:
            pass

        return False

    def check_idle_and_evict(self) -> bool:
        """
        Check if embedder has been idle longer than idle_timeout_seconds.
        If idle and loaded, triggers eviction and returns True.
        """
        try:
            from rat.engine.embedder import embedder

            if embedder.is_loaded:
                idle_sec = time.time() - embedder.last_accessed
                if idle_sec >= self.idle_timeout_seconds:
                    self.trigger_eviction(f"deep_idle_{int(idle_sec)}s")
                    return True
        except Exception as e:
            logger.debug(f"Idle check error: {e}")
        return False

    def _run_worker(self) -> None:
        """Background monitoring loop."""
        logger.info(
            f"MemorySentinel started (idle_timeout={self.idle_timeout_seconds}s, "
            f"poll_interval={self.poll_interval_seconds}s)"
        )
        while not self._stop_event.is_set():
            try:
                # 1. Check memory pressure
                evicted = self.check_memory_pressure_and_evict()
                # 2. Check idle if not already evicted
                if not evicted:
                    self.check_idle_and_evict()
            except Exception as e:
                logger.error(f"Error in MemorySentinel worker cycle: {e}")

            # Sleep in increments so stop() responds immediately
            wait_remaining = self.poll_interval_seconds
            while wait_remaining > 0 and not self._stop_event.is_set():
                sleep_chunk = min(1.0, wait_remaining)
                time.sleep(sleep_chunk)
                wait_remaining -= sleep_chunk

    def start(self) -> None:
        """Start the background sentinel thread and OS listeners."""
        with self._lock:
            if self._worker_thread is not None and self._worker_thread.is_alive():
                return
            self._stop_event.clear()
            self._setup_darwin_low_memory_notify()
            self._setup_sleep_notification()
            self._worker_thread = threading.Thread(
                target=self._run_worker,
                name="rat-memory-sentinel",
                daemon=True,
            )
            self._worker_thread.start()

    def stop(self) -> None:
        """Stop background sentinel and clean up OS hooks."""
        with self._lock:
            self._stop_event.set()
            self._teardown_sleep_notification()
            self._teardown_darwin_low_memory_notify()
            thread = self._worker_thread
            self._worker_thread = None

        if thread and thread.is_alive() and thread != threading.current_thread():
            thread.join(timeout=2.0)
        logger.info("MemorySentinel stopped.")

    @property
    def is_running(self) -> bool:
        return self._worker_thread is not None and self._worker_thread.is_alive()

    def get_status(self) -> Dict[str, object]:
        """Return diagnostic metrics for debugging and telemetry."""
        from rat.engine.embedder import embedder

        level = get_darwin_memory_pressure_level()
        return {
            "is_running": self.is_running,
            "pressure_level": level,
            "pressure_name": PRESSURE_NAMES.get(level, "UNKNOWN"),
            "idle_timeout_seconds": self.idle_timeout_seconds,
            "eviction_count": self.eviction_count,
            "last_eviction_time": self.last_eviction_time,
            "last_eviction_reason": self.last_eviction_reason,
            "is_embedder_loaded": embedder.is_loaded,
            "embedder_last_accessed": embedder.last_accessed,
        }


# Global singleton instance
sentinel = MemorySentinel()
