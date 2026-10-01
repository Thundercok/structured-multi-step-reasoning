"""
rat.os.app — Unified macOS Resident Application Controller.
Coordinates the Global Hotkey, Menu Bar Status Item, Floating Spotlight HUD,
Full AI Finder, and Background Filesystem Watcher in a unified zero-overhead loop.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Optional

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QApplication

from rat.config import config
from rat.crawler.watcher import Watcher
from rat.os.crash_shield import install_crash_shield
from rat.os.hotkey import GlobalHotkeyManager
from rat.os.menu_bar import SystemTrayManager
from rat.ui.finder_window import FinderWindow
from rat.ui.omnibar import OmnibarWindow
from rat.ui.spotlight_window import SpotlightWindow

logger = logging.getLogger("rat.os.app")


def activate_macos_app() -> None:
    """Ensure the Python GUI gains active foreground focus on macOS."""
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyRegular
        ns_app = NSApplication.sharedApplication()
        ns_app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        ns_app.activateIgnoringOtherApps_(True)
    except Exception:
        pass


class InitialIndexWorker(QObject):
    """Background worker that runs the first-time full index after onboarding."""
    progress = pyqtSignal(int, int, str)  # (completed, total, current_file_name)
    finished = pyqtSignal(int, int)       # (indexed_count, total)

    def run(self) -> None:
        from rat.crawler.indexer import Indexer
        from rat.config import set_thread_qos_background
        set_thread_qos_background()
        try:
            indexer = Indexer()
            indexed, total = indexer.run_full_index(
                progress_callback=lambda c, t, name: self.progress.emit(c, t, name)
            )
            self.finished.emit(indexed, total)
        except Exception as e:
            logger.error(f"Initial index worker error: {e}", exc_info=True)
            self.finished.emit(0, 0)


class ResidentApplication(QObject):
    """Unified macOS Resident Background System."""

    toggle_spotlight_signal = pyqtSignal()
    open_finder_signal = pyqtSignal()
    open_settings_signal = pyqtSignal()
    open_schedule_signal = pyqtSignal()
    open_widget_signal = pyqtSignal()

    def __init__(self, mode: str = "all") -> None:
        install_crash_shield()
        self.app = QApplication.instance() or QApplication(sys.argv)
        super().__init__()
        self.mode = mode
        self.app.setApplicationName("rat — macOS Smart AI File Finder")
        self.app.setQuitOnLastWindowClosed(False)  # Keep running in menu bar
        self.app._is_quitting = False

        self.omnibar_window: Optional[OmnibarWindow] = None
        self.spotlight_window: Optional[SpotlightWindow] = None
        self.finder_window: Optional[FinderWindow] = None
        self.schedule_window: Optional[Any] = None
        self.claude_widget_window: Optional[Any] = None
        self.tray_manager: Optional[SystemTrayManager] = None
        self.hotkey_manager: Optional[GlobalHotkeyManager] = None
        self.watcher: Optional[Watcher] = None
        self.memory_sentinel: Optional[Any] = None

        # Cross-thread safe signal dispatching to main event loop
        self.toggle_spotlight_signal.connect(self._do_toggle_spotlight, Qt.ConnectionType.QueuedConnection)
        self.open_finder_signal.connect(self._do_open_finder, Qt.ConnectionType.QueuedConnection)
        self.open_settings_signal.connect(self._do_open_settings, Qt.ConnectionType.QueuedConnection)
        self.open_schedule_signal.connect(self._do_open_schedule, Qt.ConnectionType.QueuedConnection)
        self.open_widget_signal.connect(self._do_open_widget, Qt.ConnectionType.QueuedConnection)
        self.app.aboutToQuit.connect(self._on_app_quit)

    def _on_app_quit(self) -> None:
        """Comprehensive zero-crash shutdown of all background services and UI threads."""
        logger.info("ResidentApplication: Initiating zero-crash graceful teardown...")
        self.app._is_quitting = True

        # 1. Stop UI Windows & their background QThreads
        if self.omnibar_window:
            try:
                self.omnibar_window.shutdown()
            except Exception as e:
                logger.debug(f"Error shutting down omnibar_window: {e}")

        if self.spotlight_window:
            try:
                if hasattr(self.spotlight_window, "shutdown"):
                    self.spotlight_window.shutdown()
                elif hasattr(self.spotlight_window, "search_thread") and self.spotlight_window.search_thread:
                    if self.spotlight_window.search_thread.isRunning():
                        self.spotlight_window.search_thread.quit()
                        self.spotlight_window.search_thread.wait(1000)
            except Exception as e:
                logger.debug(f"Error shutting down spotlight_window: {e}")

        if self.finder_window:
            try:
                if hasattr(self.finder_window, "shutdown"):
                    self.finder_window.shutdown()
                else:
                    if hasattr(self.finder_window, "search_thread") and self.finder_window.search_thread and self.finder_window.search_thread.isRunning():
                        self.finder_window.search_thread.quit()
                        self.finder_window.search_thread.wait(1000)
                    if hasattr(self.finder_window, "qa_thread") and self.finder_window.qa_thread and self.finder_window.qa_thread.isRunning():
                        self.finder_window.qa_thread.quit()
                        self.finder_window.qa_thread.wait(1000)
            except Exception as e:
                logger.debug(f"Error shutting down finder_window: {e}")

        if self.schedule_window:
            try:
                if hasattr(self.schedule_window, "shutdown"):
                    self.schedule_window.shutdown()
            except Exception as e:
                logger.debug(f"Error shutting down schedule_window: {e}")

        # 2. Stop Menu Bar Tray & worker
        if self.tray_manager:
            try:
                if hasattr(self.tray_manager, "shutdown"):
                    self.tray_manager.shutdown()
            except Exception as e:
                logger.debug(f"Error shutting down tray_manager: {e}")

        # 3. Stop background system services
        if self.memory_sentinel:
            try:
                self.memory_sentinel.stop()
            except Exception as e:
                logger.debug(f"Error stopping memory_sentinel: {e}")

        if self.watcher:
            try:
                self.watcher.stop()
            except Exception as e:
                logger.debug(f"Error stopping watcher: {e}")

        if self.hotkey_manager:
            try:
                self.hotkey_manager.stop()
            except Exception as e:
                logger.debug(f"Error stopping hotkey_manager: {e}")

        logger.info("ResidentApplication: Teardown complete. Exiting cleanly.")

    def toggle_spotlight(self) -> None:
        """Thread-safe trigger (can be called from background hotkey threads)."""
        self.toggle_spotlight_signal.emit()

    def open_finder(self) -> None:
        """Thread-safe trigger (can be called from any thread)."""
        self.open_finder_signal.emit()

    def open_settings(self) -> None:
        """Thread-safe trigger to open Settings dialog."""
        self.open_settings_signal.emit()

    def open_schedule(self) -> None:
        """Thread-safe trigger to open Club Timetable Compositor window."""
        self.open_schedule_signal.emit()

    def open_widget(self) -> None:
        """Thread-safe trigger to open Claude Timetable Widget."""
        self.open_widget_signal.emit()

    @pyqtSlot()
    def _do_toggle_spotlight(self) -> None:
        """Toggle or summon the unified Omnibar on the main Qt GUI thread."""
        try:
            if not self.omnibar_window:
                self.omnibar_window = OmnibarWindow()

            if self.omnibar_window.isVisible() and self.omnibar_window.isActiveWindow():
                self.omnibar_window.hide()
            else:
                self.omnibar_window.show_omnibar(initial_section=0)
        except Exception as e:
            logger.error(f"Error toggling Omnibar: {e}", exc_info=True)

    @pyqtSlot()
    def _do_open_finder(self) -> None:
        """Open or bring the Omnibar Files section to front."""
        try:
            if not self.omnibar_window:
                self.omnibar_window = OmnibarWindow()

            self.omnibar_window.show_omnibar(initial_section=1)
        except Exception as e:
            logger.error(f"Error opening Omnibar Files: {e}", exc_info=True)

    @pyqtSlot()
    def _do_open_settings(self) -> None:
        """Open Settings dialog on the main Qt GUI thread."""
        try:
            from rat.ui.settings_dialog import SettingsDialog
            activate_macos_app()
            dlg = SettingsDialog()
            dlg.exec()
        except Exception as e:
            logger.error(f"Error opening Settings dialog: {e}", exc_info=True)

    @pyqtSlot()
    def _do_open_schedule(self) -> None:
        """Open the integrated Schedule section on the main Qt GUI thread."""
        try:
            if not self.omnibar_window:
                self.omnibar_window = OmnibarWindow()

            self.omnibar_window.show_omnibar(initial_section=2)
        except Exception as e:
            logger.error(f"Error opening Omnibar Schedule: {e}", exc_info=True)

    @pyqtSlot()
    def _do_open_widget(self) -> None:
        """Open Claude Timetable Widget on the main Qt GUI thread."""
        try:
            from rat.ui.claude_widget import ClaudeTimetableWindow
            activate_macos_app()
            if not self.claude_widget_window:
                self.claude_widget_window = ClaudeTimetableWindow()
            self.claude_widget_window.show()
            self.claude_widget_window.raise_()
            self.claude_widget_window.activateWindow()
        except Exception as e:
            logger.error(f"Error opening Claude Widget: {e}", exc_info=True)

    def _start_initial_index(self) -> None:
        """Launch background initial indexing after first-run onboarding."""
        from PyQt6.QtCore import QThread
        self._index_thread = QThread()
        self._index_worker = InitialIndexWorker()
        self._index_worker.moveToThread(self._index_thread)
        self._index_thread.started.connect(self._index_worker.run)

        def _on_progress(completed: int, total: int, name: str) -> None:
            if self.tray_manager and completed % 100 == 0:
                self.tray_manager.tray_icon.setToolTip(
                    f"rat — Đang quét lần đầu: {completed}/{total} tệp..."
                )

        def _on_finished(indexed: int, total: int) -> None:
            logger.info(f"Initial index complete: {indexed}/{total} files.")
            if self.tray_manager:
                self.tray_manager.tray_icon.setToolTip("rat — Sẵn sàng")
                self.tray_manager.tray_icon.showMessage(
                    "rat — Quét xong! ✅",
                    f"Đã lập chỉ mục {total} tệp tin. Bấm {config.get_hotkey_display()} để tìm kiếm!",
                    self.tray_manager.tray_icon.MessageIcon.Information,
                    5000,
                )
            self._index_thread.quit()

        self._index_worker.progress.connect(_on_progress, Qt.ConnectionType.QueuedConnection)
        self._index_worker.finished.connect(_on_finished, Qt.ConnectionType.QueuedConnection)
        self._index_thread.start()

    def run(self) -> int:
        """Start resident daemon services and application event loop."""
        logger.info("Initializing macOS Resident AI Finder System...")

        # 0. First-run Onboarding & Permissions Wizard
        if not config.first_run_completed:
            try:
                from rat.ui.onboarding_dialog import OnboardingDialog
                activate_macos_app()
                wizard = OnboardingDialog()
                wizard.exec()
            except Exception as e:
                logger.warning(f"Error presenting OnboardingDialog: {e}")

            # 0.5. Auto-index existing files in background after first-run setup
            self._start_initial_index()

        # Pre-initialize unified Omnibar on the main thread
        try:
            self.omnibar_window = OmnibarWindow()
        except Exception as e:
            logger.warning(f"Deferred OmnibarWindow initialization: {e}")

        # 1. Start Global Hotkey Manager IMMEDIATELY
        self.hotkey_manager = GlobalHotkeyManager(on_trigger=self.toggle_spotlight)
        self.hotkey_manager.start()

        # 2. Start System Tray (Menu Bar resident item)
        self.tray_manager = SystemTrayManager(
            on_open_spotlight=self.toggle_spotlight,
            on_open_finder=self.open_finder,
            on_open_settings=self.open_settings,
            on_open_schedule=self.open_schedule,
            on_open_widget=self.open_widget,
        )
        self.tray_manager.tray_icon.show()

        from rat.os.hotkey import is_accessibility_trusted
        if not is_accessibility_trusted():
            QTimer.singleShot(
                1200,
                lambda: self.tray_manager.tray_icon.showMessage(
                    "rat — Phím tắt toàn cầu (Global Hotkey)",
                    "Để dùng phím tắt ⌘ ⇧ Space trên mọi app, hãy click icon rat trên Menu Bar và chọn 'Cấp quyền Phím tắt (Accessibility)'.",
                    self.tray_manager.tray_icon.MessageIcon.Information,
                    6000,
                )
            )

        # 3. Start Background Watcher (FSEvents realtime indexing) asynchronously
        if config.auto_watch:
            try:
                self.watcher = Watcher()
                self.watcher.start(config.indexed_directories)
            except Exception as e:
                logger.warning(f"Failed to start filesystem watcher: {e}")

        # 4. Start Memory Sentinel (macOS memory pressure, sleep, and idle eviction)
        if getattr(config, "memory_sentinel_enabled", True):
            try:
                from rat.os.memory_sentinel import sentinel
                from rat.engine.embedder import embedder
                sentinel.idle_timeout_seconds = getattr(config, "deep_idle_timeout_seconds", 2700.0)
                sentinel.register_eviction_callback(embedder.evict)
                sentinel.start()
                self.memory_sentinel = sentinel
                logger.info("MemorySentinel activated for resident lifecycle governance.")
            except Exception as e:
                logger.warning(f"Failed to start MemorySentinel: {e}")

        # 5. Open initial window based on mode
        if self.mode == "finder":
            self.open_finder()
        elif self.mode == "spotlight":
            self.toggle_spotlight()
        elif self.mode == "schedule":
            self.open_schedule()
        elif self.mode in ("widget", "mini", "claude"):
            self.open_widget()
        elif self.mode == "daemon":
            logger.info("Running in pure background resident daemon mode (Menu Bar & Global Hotkey active).")

        return self.app.exec()


def run_resident_app(mode: str = "finder") -> None:
    """Launch the resident system."""
    res_app = ResidentApplication(mode=mode)
    sys.exit(res_app.run())
