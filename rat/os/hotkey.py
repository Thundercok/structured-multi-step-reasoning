"""
rat.os.hotkey — System-Wide Global Hotkey Listener for macOS.
Hooks directly into macOS input events to summon the floating search HUD anywhere.
"""

from __future__ import annotations

import logging
import sys
import threading
from typing import Callable, Optional

from rat.config import config
from rat.os.permissions import (
    is_accessibility_trusted, request_accessibility_permission, open_accessibility_settings,
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


class GlobalHotkeyManager:
    """Manages system-wide global shortcuts without conflicting with macOS or third-party apps."""

    def __init__(self, on_trigger: Optional[Callable[[], None]] = None) -> None:
        global _active_hotkey_manager
        _active_hotkey_manager = self
        self.on_trigger = on_trigger
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
        # A stopped monitor keeps its own event while a replacement starts.
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
        """Start listening for global hotkeys in a background thread."""
        if self._running and is_accessibility_trusted():
            return True

        if not is_accessibility_trusted():
            if self._listener is not None:
                self._listener.stop()
                self._listener = None
            self._running = False
            logger.warning(
                "macOS Accessibility permission not granted! "
                "Global hotkeys require Accessibility in System Settings -> Privacy & Security -> Accessibility."
            )
            outcome = request_accessibility_permission()
            self.status = "permission_error" if outcome.error else "waiting_permission"
            self.last_error = outcome.error
            self._start_permission_monitor()
            # Do not claim a working listener or start an event tap without trust.
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

            # Command+Shift+Space as primary requested shortcut, with Option+Space & Option+R fallbacks
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
            logger.info(
                f"Global hotkey listener thread started with shortcuts: {list(hotkeys.keys())} "
                f"(Accessibility trusted: {is_accessibility_trusted()})"
            )
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
