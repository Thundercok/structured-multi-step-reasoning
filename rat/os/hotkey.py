"""
rat.os.hotkey — System-Wide Global Hotkey Listener for macOS.
Supports native Carbon RegisterEventHotKey helpers (zero Accessibility permissions needed)
with legacy pynput fallbacks.
"""

from __future__ import annotations

import logging
from pathlib import Path
import re
import sys
import threading
import time
from typing import Any, Callable, Optional

from rat.config import config
from rat.os.permissions import (
    is_accessibility_trusted,
    request_accessibility_permission,
    open_accessibility_settings,
)

logger = logging.getLogger("rat.os.hotkey")

_active_hotkey_manager: Optional[GlobalHotkeyManager] = None


def get_active_hotkey_manager() -> Optional[GlobalHotkeyManager]:
    return _active_hotkey_manager


def restart_global_hotkey() -> bool:
    """Restarts the active global hotkey listener to apply new hotkeys from config."""
    global _active_hotkey_manager
    if _active_hotkey_manager:
        return _active_hotkey_manager.restart()
    return False


class CarbonHotkeyRegistration:
    """Zero-permission native Carbon hotkey registration backed by rat/bin/rat-hotkey."""

    def __init__(
        self,
        chord_name: str,
        callback: Callable[[], None],
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.chord_name = chord_name
        self.callback = callback
        self.on_error = on_error
        self.process: Optional[Any] = None
        self.buffer = bytearray()
        self.ready = False
        self.closed = False
        self.last_fire = 0.0
        self.ready_line = b""

    def start(self) -> bool:
        if sys.platform != "darwin":
            logger.info("Carbon hotkey helper is macOS only.")
            return False

        try:
            from rat.os.hotkey_chords import chord
            from rat.engine.mini_version import BUILD
            key, modifiers, _ = chord(self.chord_name)
            self.ready_line = f"READY SELECT2 {BUILD} {key} {modifiers}".encode()
        except Exception as exc:
            logger.warning("Invalid hotkey chord %s: %s", self.chord_name, exc)
            return False

        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
        helper = base / "rat/bin/rat-hotkey"
        if not helper.is_file():
            logger.warning("rat-hotkey helper binary not found at %s", helper)
            return False

        try:
            from PyQt6.QtCore import QCoreApplication, QProcess
            app = QCoreApplication.instance()
            if app is None:
                logger.warning("QCoreApplication instance required for Carbon hotkey process.")
                return False

            self.process = QProcess(app)
            self.process.setProgram(str(helper))
            self.process.setArguments([str(key), str(modifiers)])
            self.process.readyReadStandardOutput.connect(self._read)
            self.process.finished.connect(self._finished)
            self.process.errorOccurred.connect(self._process_error)
            self.process.start()

            if not self.process.waitForStarted(3000):
                logger.warning("Failed to start rat-hotkey process: %s", self.process.errorString())
                return False

            # Wait briefly for READY notification from helper
            if not self.ready:
                self.process.waitForReadyRead(1500)
                self._read()

            return True
        except Exception as exc:
            logger.warning("Exception starting Carbon hotkey %s: %s", self.chord_name, exc)
            if self.on_error:
                self.on_error(str(exc))
            return False

    def _read(self) -> None:
        if not self.process:
            return
        self.buffer.extend(bytes(self.process.readAllStandardOutput()))
        while b"\n" in self.buffer:
            line, _, rest = self.buffer.partition(b"\n")
            self.buffer = bytearray(rest)
            line_clean = line.strip()
            if line_clean == self.ready_line or line_clean.startswith(b"READY"):
                self.ready = True
                logger.info("Carbon hotkey registered: chord=%s", self.chord_name)
            elif line_clean == b"SELECTION" and self.ready and not self.closed:
                now = time.monotonic()
                if now - self.last_fire >= 0.25:
                    self.last_fire = now
                    logger.info("Carbon hotkey triggered: chord=%s", self.chord_name)
                    if self.callback:
                        try:
                            self.callback()
                        except Exception as exc:
                            logger.warning("Carbon hotkey callback failed: %s", exc)
                            if self.on_error:
                                self.on_error(str(exc))

    def _finished(self, code: int, status: Any) -> None:
        self.ready = False
        if not self.closed:
            logger.warning("Carbon hotkey helper exited with code %s (%s)", code, status)

    def _process_error(self, error: Any) -> None:
        self.ready = False
        if not self.closed:
            logger.warning("Carbon hotkey helper process error: %s", error)

    def close(self) -> bool:
        self.closed = True
        self.ready = False
        if self.process:
            try:
                self.process.closeWriteChannel()
                self.process.terminate()
                if not self.process.waitForFinished(1000):
                    self.process.kill()
                    self.process.waitForFinished(1000)
            except Exception:
                pass
            self.process = None
        return True


class GlobalHotkeyManager:
    """
    Manages system-wide global shortcuts.
    Defaults to native Carbon RegisterEventHotKey helpers which require ZERO accessibility permissions.
    """

    def __init__(
        self,
        on_trigger: Optional[Callable[[], None]] = None,
        on_quicklook: Optional[Callable[[], None]] = None,
        toggle_chord: str = "control_option_space",
        quicklook_chord: str = "option_shift_r",
        backend: Optional[str] = None,
    ) -> None:
        global _active_hotkey_manager
        _active_hotkey_manager = self
        self.on_trigger = on_trigger
        self.on_quicklook = on_quicklook
        self.toggle_chord = toggle_chord
        self.quicklook_chord = quicklook_chord
        self.backend = backend

        self._toggle_reg: Optional[CarbonHotkeyRegistration] = None
        self._quicklook_reg: Optional[CarbonHotkeyRegistration] = None
        self._listener = None
        self._running = False
        self.status = "stopped"
        self.last_error: Optional[str] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitor_event = threading.Event()

    def _start_permission_monitor(self) -> None:
        """Start a background monitor that auto-rebinds hotkeys once Accessibility is granted."""
        if self._monitor_thread and self._monitor_thread.is_alive() and not self._stop_monitor_event.is_set():
            return
        self._stop_monitor_event = threading.Event()
        self._monitor_thread = threading.Thread(
            target=self._monitor_permission_loop,
            args=(self._stop_monitor_event,),
            daemon=True,
            name="rat-hotkey-permission-monitor",
        )
        self._monitor_thread.start()

    def _monitor_permission_loop(self, stop_event) -> None:
        """Polls every 3s to detect when user grants Accessibility permission in System Settings."""
        while not stop_event.wait(3.0):
            if is_accessibility_trusted():
                logger.info("Accessibility permission newly granted! Auto-reconnecting Global Hotkey Manager...")
                self.restart()
                break

    def start(self) -> bool:
        """Start listening for global hotkeys."""
        backend = self.backend
        if backend is None:
            from types import SimpleNamespace
            pynput_mod = sys.modules.get("pynput")
            if isinstance(pynput_mod, SimpleNamespace):
                backend = "pynput"
            else:
                backend = "carbon"

        if backend == "carbon":
            # Carbon-based native hotkeys (exempt from macOS Accessibility permissions)
            base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
            helper = base / "rat/bin/rat-hotkey"
            if sys.platform != "darwin" or not helper.is_file():
                self.status = "unavailable"
                self._running = False
                logger.info("Carbon hotkey helper unavailable on this platform/environment.")
                return False

            ok = True
            if self.on_trigger:
                self._toggle_reg = CarbonHotkeyRegistration(self.toggle_chord, self.on_trigger)
                if not self._toggle_reg.start():
                    ok = False
            if self.on_quicklook:
                self._quicklook_reg = CarbonHotkeyRegistration(self.quicklook_chord, self.on_quicklook)
                if not self._quicklook_reg.start():
                    ok = False

            self._running = ok
            self.status = "started" if ok else "error"
            logger.info("GlobalHotkeyManager active via Carbon native helper (no accessibility permission required).")
            return ok

        # Legacy pynput backend (requires Accessibility)
        if self._running and is_accessibility_trusted():
            return True

        if not is_accessibility_trusted():
            if self._listener is not None:
                self._listener.stop()
                self._listener = None
            self._running = False
            outcome = request_accessibility_permission()
            self.status = "permission_error" if outcome.error else "waiting_permission"
            self.last_error = outcome.error
            self._start_permission_monitor()
            return False
        else:
            self._stop_monitor_event.set()

        try:
            from pynput import keyboard

            def _handle_activate() -> None:
                try:
                    logger.info("Global hotkey triggered!")
                    if self.on_trigger:
                        self.on_trigger()
                except Exception as trigger_err:
                    logger.error(f"Error in global hotkey trigger callback: {trigger_err}", exc_info=True)

            primary = config.global_hotkey.strip()
            hotkeys = {
                "<cmd>+<shift>+<space>": _handle_activate,
                "<alt>+<space>": _handle_activate,
                "<alt>+r": _handle_activate,
            }
            if primary and primary not in hotkeys:
                hotkeys[primary] = _handle_activate

            self._listener = keyboard.GlobalHotKeys(hotkeys)
            self._listener.start()
            self._running = True
            self.status = "listener_started"
            self.last_error = None
            return True
        except Exception as e:
            if self._listener is not None:
                try:
                    self._listener.stop()
                except Exception:
                    pass
                self._listener = None
            self._running = False
            self.status = "listener_error"
            self.last_error = f"{type(e).__name__}: {e}"
            logger.warning(f"Failed to start GlobalHotKeys listener: {e}")
            self._start_permission_monitor()
            return False

    def stop(self) -> None:
        """Stop listening for global shortcuts."""
        self._stop_monitor_event.set()
        if self._toggle_reg:
            self._toggle_reg.close()
            self._toggle_reg = None
        if self._quicklook_reg:
            self._quicklook_reg.close()
            self._quicklook_reg = None
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
        self._running = False
        self.status = "stopped"
        logger.info("Global Hotkey Manager stopped.")

    def restart(self) -> bool:
        """Restart listener with updated hotkey from config."""
        self.stop()
        return self.start()
