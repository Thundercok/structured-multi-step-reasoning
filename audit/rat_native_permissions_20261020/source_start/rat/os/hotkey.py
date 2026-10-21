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

logger = logging.getLogger("rat.os.hotkey")


def is_accessibility_trusted() -> bool:
    """Check if the process has macOS Accessibility (AX) permission."""
    if sys.platform != "darwin":
        return True
    try:
        from ApplicationServices import AXIsProcessTrusted
        return bool(AXIsProcessTrusted())
    except Exception:
        return False


def request_accessibility_permission() -> None:
    """Trigger the native macOS accessibility permission prompt."""
    if sys.platform == "darwin":
        try:
            from ApplicationServices import AXIsProcessTrustedWithOptions
            from Foundation import NSDictionary
            options = NSDictionary.dictionaryWithObject_forKey_(True, "AXTrustedCheckOptionPrompt")
            AXIsProcessTrustedWithOptions(options)
        except Exception:
            pass


def open_accessibility_settings() -> None:
    """Open macOS System Settings directly to the Accessibility pane."""
    request_accessibility_permission()
    if sys.platform == "darwin":
        import subprocess
        subprocess.run(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])


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
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitor_event = threading.Event()

    def _start_permission_monitor(self) -> None:
        """Start a background monitor that auto-rebinds hotkeys once Accessibility is granted."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        self._stop_monitor_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_permission_loop,
            daemon=True,
            name="rat-hotkey-permission-monitor",
        )
        self._monitor_thread.start()

    def _monitor_permission_loop(self) -> None:
        """Polls every 3s to detect when user grants Accessibility permission in System Settings."""
        while not self._stop_monitor_event.wait(3.0):
            if is_accessibility_trusted():
                logger.info("Accessibility permission newly granted! Auto-reconnecting Global Hotkey Manager...")
                self.restart()
                break

    def start(self) -> bool:
        """Start listening for global hotkeys in a background thread."""
        if self._running and is_accessibility_trusted():
            return True

        if not is_accessibility_trusted():
            logger.warning(
                "macOS Accessibility permission not granted! "
                "Global hotkeys require Accessibility in System Settings -> Privacy & Security -> Accessibility."
            )
            request_accessibility_permission()
            self._start_permission_monitor()
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
            logger.info(
                f"Global Hotkey Manager active with shortcuts: {list(hotkeys.keys())} "
                f"(Accessibility trusted: {is_accessibility_trusted()})"
            )
            return True
        except Exception as e:
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
        logger.info("Global Hotkey Manager stopped.")

    def restart(self) -> bool:
        """Restart listener with updated hotkey from config."""
        self.stop()
        return self.start()
