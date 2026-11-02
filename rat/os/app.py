"""
rat.os.app — Unified macOS Resident Application Controller.
Coordinates the Global Hotkey, Menu Bar Status Item, and the unified hardware-accelerated
QtQuick RAT Desk in a zero-overhead resident loop.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Optional, Tuple

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QGuiApplication

from rat.config import config
from rat.crawler.watcher import Watcher
from rat.os.crash_shield import install_crash_shield
from rat.os.hotkey import GlobalHotkeyManager
from rat.os.menu_bar import SystemTrayManager
from rat.os.single_instance import (
    SingleInstanceServer,
    kill_stale_orphan_instances,
    try_activate_existing_instance,
)

logger = logging.getLogger("rat.os.app")


def activate_macos_app() -> None:
    """Ensure the Python GUI gains active foreground focus on macOS without breaking fullscreen spaces."""
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
        ns_app = NSApplication.sharedApplication()
        ns_app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
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
    """Unified macOS Resident Background System running the hardware-accelerated QtQuick Desk."""

    toggle_spotlight_signal = pyqtSignal()
    open_finder_signal = pyqtSignal()
    open_settings_signal = pyqtSignal()
    open_schedule_signal = pyqtSignal()
    open_widget_signal = pyqtSignal()
    open_natal_signal = pyqtSignal()

    def __init__(self, mode: str = "all", *, reasoning_engine=None, allow_synthetic_policy=False) -> None:
        install_crash_shield()
        self.app = QGuiApplication.instance() or QGuiApplication(sys.argv)
        super().__init__()
        if reasoning_engine is not None:
            from rat.ui.reasoning_host import install_reasoning_engine
            install_reasoning_engine(self.app, reasoning_engine,
                                     allow_synthetic_policy=allow_synthetic_policy)
        self.mode = mode
        self.app.setApplicationName("RAT · Trợ lý thông minh & PDF Desk")
        self.app.setQuitOnLastWindowClosed(False)  # Keep running resident in menu bar

        # Lifecycle State Machine: "idle" -> "quitting" -> ("waiting_past_timeout") -> "terminated"
        self._shutdown_state: str = "idle"
        self.app._is_quitting = False
        self._teardown_done: bool = False
        self._clean_shutdown: Optional[bool] = None
        self._shutdown_timer: Optional[QTimer] = None
        self._shutdown_on_finished: Optional[Any] = None

        self.single_instance_server: Optional[SingleInstanceServer] = None
        self.desk_view: Optional[Any] = None
        self.desk_controller: Optional[Any] = None
        self.tray_manager: Optional[SystemTrayManager] = None
        self.hotkey_manager: Optional[GlobalHotkeyManager] = None
        self.watcher: Optional[Watcher] = None
        self.memory_sentinel: Optional[Any] = None
        self.warmup_worker: Optional[Any] = None
        self.warmup_thread: Optional[Any] = None
        self._index_thread: Optional[Any] = None
        self._index_worker: Optional[Any] = None

        # Cross-thread safe signal dispatching to main event loop
        self.toggle_spotlight_signal.connect(self._do_toggle_spotlight, Qt.ConnectionType.QueuedConnection)
        self.open_finder_signal.connect(self._do_open_finder, Qt.ConnectionType.QueuedConnection)
        self.open_settings_signal.connect(self._do_open_settings, Qt.ConnectionType.QueuedConnection)
        self.open_schedule_signal.connect(self._do_open_schedule, Qt.ConnectionType.QueuedConnection)
        self.open_widget_signal.connect(self._do_open_widget, Qt.ConnectionType.QueuedConnection)
        self.open_natal_signal.connect(self._do_open_natal, Qt.ConnectionType.QueuedConnection)
        self.app.aboutToQuit.connect(self._on_app_quit)
        self.app.installEventFilter(self)

    @property
    def is_quitting(self) -> bool:
        return self._shutdown_state != "idle"

    @property
    def _is_quitting(self) -> bool:
        return self._shutdown_state != "idle"

    def eventFilter(self, watched, event):
        if watched is self.app and event.type() == QEvent.Type.Quit and self._shutdown_state != "terminated":
            self.request_quit()
            return True
        return super().eventFilter(watched, event)

    def get_active_workers(self) -> list[str]:
        """Return human-readable names of all currently running background workers and threads."""
        active = []
        if self.warmup_thread and self.warmup_thread.isRunning():
            active.append("SemesterWarmupWorker")
        if self._index_thread and self._index_thread.isRunning():
            active.append("InitialIndexWorker")
        if self.tray_manager and getattr(self.tray_manager, "rescan_worker", None):
            if self.tray_manager.rescan_worker.isRunning():
                active.append("TrayRescanWorker")
        if self.desk_controller:
            ctrl = self.desk_controller
            if hasattr(ctrl, "_execution_workers"):
                for w in ctrl._execution_workers:
                    if w.isRunning():
                        name = getattr(w, "objectName", lambda: "")() or w.__class__.__name__
                        active.append(f"DeskWorker({name})")
            if hasattr(ctrl, "_worker") and ctrl._worker:
                if hasattr(ctrl._worker, "_thread") and ctrl._worker._thread.is_alive():
                    active.append("PDFWorker")
        return active

    def all_workers_finished(self) -> bool:
        """Return True if and only if all background workers and threads have fully stopped."""
        desk_clean = True
        if self.desk_controller:
            try:
                desk_clean = self.desk_controller.close()
            except Exception as e:
                logger.debug(f"Error checking desk_controller.close: {e}")
                desk_clean = False
        return desk_clean and len(self.get_active_workers()) == 0

    def _ensure_desk(self) -> Tuple[Any, Any]:
        """Lazily initialize the unified QtQuick Desk window and controller."""
        if self.desk_view is None:
            from rat.ui.quick_app import create_quick_desk
            self.desk_view, self.desk_controller = create_quick_desk(
                quit_on_close=False,
            )
        return self.desk_view, self.desk_controller

    def request_quit(self, timeout: float = 3.0, on_finished: Optional[Any] = None) -> None:
        """
        Intercept quit BEFORE Qt's aboutToQuit event.
        Cancels active inference/workers, promptly hides user surfaces, and defers
        application exit until workers cleanly finish.

        If timeout expires before workers finish, transitions to 'waiting_past_timeout',
        retains worker ownership, warns about incomplete shutdown, and keeps the Qt event
        loop alive until all workers fully exit. Only then calls app.quit().
        """
        if self._shutdown_state != "idle":
            logger.debug(
                f"ResidentApplication: request_quit called while state is '{self._shutdown_state}'. Ignoring duplicate request."
            )
            if on_finished and self._shutdown_state == "terminated":
                try:
                    on_finished(bool(self._clean_shutdown))
                except Exception:
                    pass
            return

        self._shutdown_state = "quitting"
        self.app._is_quitting = True
        self._shutdown_on_finished = on_finished
        logger.info("ResidentApplication: Shutdown requested. Cancelling active work and deferring exit...")

        # 1. Hide view immediately for prompt UI response
        if self.desk_view:
            try:
                self.desk_view.hide()
            except Exception:
                pass

        # 2. Cancel active inference and PDF tasks immediately
        if self.desk_controller:
            try:
                self.desk_controller.cancel()
                self.desk_controller.close()
            except Exception as e:
                logger.debug(f"Error cancelling desk_controller: {e}")

        # 3. Stop background system services
        for attr, method in [
            ("hotkey_manager", "stop"),
            ("watcher", "stop"),
            ("memory_sentinel", "stop"),
            ("single_instance_server", "stop"),
            ("warmup_worker", "stop"),
        ]:
            obj = getattr(self, attr, None)
            if obj and hasattr(obj, method):
                try:
                    getattr(obj, method)()
                except Exception as e:
                    logger.debug(f"Error stopping {attr}: {e}")

        if self.warmup_thread and self.warmup_thread.isRunning():
            try:
                self.warmup_thread.quit()
            except Exception as e:
                logger.debug(f"Error requesting warmup_thread quit: {e}")

        if self._index_thread and self._index_thread.isRunning():
            try:
                self._index_thread.quit()
            except Exception as e:
                logger.debug(f"Error requesting _index_thread quit: {e}")

        if self.tray_manager:
            try:
                if hasattr(self.tray_manager, "request_shutdown"):
                    self.tray_manager.request_shutdown()
                else:
                    self.tray_manager.shutdown()
            except Exception as e:
                logger.debug(f"Error requesting tray shutdown: {e}")

        # 4. Check if all workers are already clean/finished
        if self.all_workers_finished():
            self._finish_teardown(clean=True)
            return

        # 5. Controller or background threads have active workers: defer application exit and poll
        import time
        deadline = time.monotonic() + max(0.05, timeout)
        self._shutdown_timer = QTimer(self)
        self._shutdown_timer.setInterval(30)

        def _poll_shutdown():
            if self.all_workers_finished():
                if self._shutdown_timer:
                    self._shutdown_timer.stop()
                clean = (self._shutdown_state == "quitting")
                self._finish_teardown(clean=clean)
                return

            if time.monotonic() >= deadline and self._shutdown_state == "quitting":
                self._shutdown_state = "waiting_past_timeout"
                self._clean_shutdown = False
                active = self.get_active_workers()
                logger.warning(
                    f"ResidentApplication: Shutdown timed out after {timeout:.1f}s with active workers: {active}. "
                    "Keeping application alive and holding worker ownership until all workers finish."
                )
                if self._shutdown_timer:
                    self._shutdown_timer.setInterval(100)
                # DO NOT CALL self.app.quit() OR self._finish_teardown() HERE!
                # The app remains in event loop so background workers can complete safely.

        self._shutdown_timer.timeout.connect(_poll_shutdown)
        self._shutdown_timer.start()

    def _finish_teardown(self, clean: bool) -> None:
        """Finalize teardown and quit app once all workers have finished."""
        if self._shutdown_state == "terminated":
            return
        self._shutdown_state = "terminated"
        self._clean_shutdown = clean
        self._teardown_done = True

        if self._shutdown_timer and self._shutdown_timer.isActive():
            self._shutdown_timer.stop()

        if self.desk_view:
            try:
                self.desk_view.close()
            except Exception as e:
                logger.debug(f"Error closing desk_view: {e}")

        if self.tray_manager:
            try:
                self.tray_manager.shutdown()
            except Exception as e:
                logger.debug(f"Error shutting down tray_manager: {e}")

        if clean:
            logger.info("ResidentApplication: Teardown complete. Exiting cleanly.")
        else:
            logger.warning("ResidentApplication: Teardown complete after timeout delay. Exiting now.")

        cb = self._shutdown_on_finished
        self._shutdown_on_finished = None
        if cb:
            try:
                cb(clean)
            except Exception as e:
                logger.debug(f"Error in on_finished callback: {e}")

        self.app.quit()

    def _on_app_quit(self) -> None:
        """Fallback handler if quit was triggered externally before request_quit finished."""
        if self._shutdown_state == "terminated":
            return

        self._shutdown_state = "quitting"
        self.app._is_quitting = True
        logger.info("ResidentApplication: aboutToQuit received; finalizing teardown...")

        # Cancel active work
        if self.desk_controller:
            try:
                self.desk_controller.cancel()
                self.desk_controller.close()
            except Exception:
                pass

        # Stop services
        for attr, method in [
            ("hotkey_manager", "stop"),
            ("watcher", "stop"),
            ("memory_sentinel", "stop"),
            ("single_instance_server", "stop"),
            ("warmup_worker", "stop"),
        ]:
            obj = getattr(self, attr, None)
            if obj and hasattr(obj, method):
                try:
                    getattr(obj, method)()
                except Exception:
                    pass

        if self.warmup_thread and self.warmup_thread.isRunning():
            try:
                self.warmup_thread.quit()
            except Exception:
                pass

        if self._index_thread and self._index_thread.isRunning():
            try:
                self._index_thread.quit()
            except Exception:
                pass

        if self.tray_manager:
            try:
                if hasattr(self.tray_manager, "request_shutdown"):
                    self.tray_manager.request_shutdown()
            except Exception:
                pass

        # Synchronous bounded check (aboutToQuit cannot defer exit back to event loop)
        import time
        deadline = time.monotonic() + 1.5
        while not self.all_workers_finished() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.02)

        is_clean = self.all_workers_finished()
        self._clean_shutdown = is_clean
        self._shutdown_state = "terminated"
        self._teardown_done = True

        if self.tray_manager:
            try:
                self.tray_manager.shutdown()
            except Exception:
                pass

        if self.desk_view:
            try:
                self.desk_view.close()
            except Exception:
                pass

        if is_clean:
            logger.info("ResidentApplication: Teardown complete. Exiting cleanly.")
        else:
            active = self.get_active_workers()
            logger.warning(
                f"ResidentApplication: aboutToQuit executed with active workers: {active}. Incomplete shutdown."
            )

    def toggle_spotlight(self) -> None:
        """Thread-safe trigger (can be called from background hotkey threads)."""
        self.toggle_spotlight_signal.emit()

    def open_finder(self) -> None:
        """Thread-safe trigger (can be called from any thread)."""
        self.open_finder_signal.emit()

    def open_settings(self) -> None:
        """Thread-safe trigger to open Settings."""
        self.open_settings_signal.emit()

    def open_schedule(self) -> None:
        """Thread-safe trigger for schedule query."""
        self.open_schedule_signal.emit()

    def open_widget(self) -> None:
        """Thread-safe trigger for compact desk."""
        self.open_widget_signal.emit()

    def open_natal(self) -> None:
        self.open_natal_signal.emit()

    @pyqtSlot()
    def _do_open_natal(self) -> None:
        """Open Tarot / Reading view on the unified QtQuick Desk."""
        if self.is_quitting:
            return
        try:
            view, controller = self._ensure_desk()
            if view is None:
                return
            view.show()
            view.raise_()
            view.requestActivate()
            activate_macos_app()
            if controller is not None and hasattr(controller, "openReadingDesk"):
                controller.openReadingDesk()
        except Exception as e:
            logger.error(f"Error opening reading on RAT Desk: {e}", exc_info=True)

    @pyqtSlot()
    def _do_toggle_spotlight(self) -> None:
        """Toggle or summon the unified QtQuick RAT Desk."""
        if self.is_quitting:
            return
        try:
            view, controller = self._ensure_desk()
            if view is None:
                return

            if view.isVisible() and view.isActive():
                view.hide()
            else:
                view.show()
                view.raise_()
                view.requestActivate()
                activate_macos_app()
        except Exception as e:
            logger.error(f"Error toggling RAT Desk: {e}", exc_info=True)

    @pyqtSlot()
    def _do_open_finder(self) -> None:
        """Summon the unified QtQuick Desk for document / file interaction."""
        if self.is_quitting:
            return
        try:
            view, controller = self._ensure_desk()
            if view is None:
                return
            view.show()
            view.raise_()
            view.requestActivate()
            activate_macos_app()
            if controller is not None:
                controller.setExpanded(True)
        except Exception as e:
            logger.error(f"Error opening RAT Desk Finder: {e}", exc_info=True)

    @pyqtSlot()
    def _do_open_settings(self) -> None:
        """Ensure RAT Desk is visible and present configuration status (dedicated QtQuick card pending)."""
        if self.is_quitting:
            return
        try:
            view, controller = self._ensure_desk()
            if view is None:
                return
            view.show()
            view.raise_()
            view.requestActivate()
            activate_macos_app()
            if controller is not None:
                controller._status = "Tùy chọn: Giao diện cấu hình QtQuick chuyên biệt đang được phát triển."
                controller.changed.emit()
        except Exception as e:
            logger.error(f"Error opening settings on RAT Desk: {e}", exc_info=True)

    @pyqtSlot()
    def _do_open_schedule(self) -> None:
        """Ensure RAT Desk is visible for schedule queries (dedicated QtQuick card pending)."""
        if self.is_quitting:
            return
        try:
            view, controller = self._ensure_desk()
            if view is None:
                return
            view.show()
            view.raise_()
            view.requestActivate()
            activate_macos_app()
            if controller is not None:
                controller._status = "Thời khóa biểu: Thẻ sắp xếp lịch CoT trên Desk đang được phát triển."
                controller.changed.emit()
        except Exception as e:
            logger.error(f"Error opening schedule on RAT Desk: {e}", exc_info=True)

    @pyqtSlot()
    def _do_open_widget(self) -> None:
        """Ensure RAT Desk is visible in compact mode."""
        if self.is_quitting:
            return
        try:
            view, controller = self._ensure_desk()
            if view is None:
                return
            view.show()
            view.raise_()
            view.requestActivate()
            activate_macos_app()
            if controller is not None:
                controller.setExpanded(False)
        except Exception as e:
            logger.error(f"Error opening compact desk: {e}", exc_info=True)

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
                    f"RAT — Đang quét lần đầu: {completed}/{total} tệp..."
                )

        def _on_finished(indexed: int, total: int) -> None:
            logger.info(f"Initial index complete: {indexed}/{total} files.")
            if self.tray_manager:
                self.tray_manager.tray_icon.setToolTip("RAT — Sẵn sàng")
                self.tray_manager.tray_icon.showMessage(
                    "RAT — Quét xong! ✅",
                    f"Đã lập chỉ mục {total} tệp tin. Bấm {config.get_hotkey_display()} để mở RAT Desk!",
                    self.tray_manager.tray_icon.MessageIcon.Information,
                    5000,
                )
            self._index_thread.quit()

        self._index_worker.progress.connect(_on_progress, Qt.ConnectionType.QueuedConnection)
        self._index_worker.finished.connect(_on_finished, Qt.ConnectionType.QueuedConnection)
        self._index_thread.start()

    def _start_semester_warmup(self) -> None:
        """Launch background FTS5 document content pre-warming for semester directories."""
        if (getattr(self.app, "_is_quitting", False)
                or not config.auto_watch or not config.indexed_directories):
            return
        if self.warmup_thread and self.warmup_thread.isRunning():
            return
        try:
            from PyQt6.QtCore import QThread
            from rat.crawler.warmup import SemesterWarmupWorker
            self.warmup_thread = QThread()
            self.warmup_worker = SemesterWarmupWorker()
            self.warmup_worker.moveToThread(self.warmup_thread)
            self.warmup_thread.started.connect(self.warmup_worker.run)

            def _on_finished(warmed: int) -> None:
                logger.info(f"Semester warmup completed. Pre-warmed {warmed} academic files.")
                if self.warmup_thread and self.warmup_thread.isRunning():
                    self.warmup_thread.quit()

            self.warmup_worker.finished.connect(_on_finished, Qt.ConnectionType.QueuedConnection)
            self.warmup_thread.start()
        except Exception as e:
            logger.warning(f"Failed to start semester warmup: {e}")

    @pyqtSlot(str)
    def _on_single_instance_command(self, cmd: str) -> None:
        """Handle command relayed from a subsequent rat launch attempt."""
        logger.info(f"ResidentApplication received remote single-instance command: '{cmd}'")
        activate_macos_app()
        if cmd in ("quit", "exit", "--quit", "stop"):
            self.request_quit()
        elif cmd == "finder":
            self.open_finder()
        elif cmd in ("schedule", "tkb", "lich"):
            self.open_schedule()
        elif cmd in ("widget", "mini", "claude"):
            self.open_widget()
        elif cmd in ("astrology", "natal", "la-so", "reading"):
            self.open_natal()
        else:
            self.toggle_spotlight()

    def run(self) -> int:
        """Start resident daemon services and application event loop."""
        logger.info("Initializing macOS Resident AI System (QtQuick Scenegraph)...")

        # 0. Start Single Instance Server to prevent duplicates
        self.single_instance_server = SingleInstanceServer(self)
        self.single_instance_server.command_received.connect(self._on_single_instance_command)
        self.single_instance_server.start()

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
            on_open_natal=self.open_natal,
            on_quit=self.request_quit,
        )
        self.tray_manager.tray_icon.show()

        from rat.os.hotkey import is_accessibility_trusted
        if not is_accessibility_trusted():
            QTimer.singleShot(
                1200,
                lambda: self.tray_manager.tray_icon.showMessage(
                    "RAT — Phím tắt toàn cầu (Global Hotkey)",
                    "Để dùng phím tắt ⌘ ⇧ Space trên mọi app, hãy click icon RAT trên Menu Bar và chọn 'Cấp quyền Phím tắt (Accessibility)'.",
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

        # 4.5. Background Semester Document Warmup (QoS Background)
        if config.auto_watch and config.indexed_directories:
            QTimer.singleShot(2500, self._start_semester_warmup)

        # 5. Open initial window based on mode
        if self.mode == "finder":
            self.open_finder()
        elif self.mode in ("spotlight", "desk", "quick"):
            self.toggle_spotlight()
        elif self.mode == "daemon":
            logger.info("Running in pure background resident daemon mode (Menu Bar & Global Hotkey active).")

        return self.app.exec()


def run_resident_app(mode: str = "finder", *, reasoning_engine=None, allow_synthetic_policy=False) -> None:
    """Launch the resident system with strict single-instance enforcement."""
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)

    # 1. Attempt to delegate to existing running instance
    if try_activate_existing_instance(command=mode):
        logger.info(f"rat: Primary resident instance activated with '{mode}'. Exiting.")
        sys.exit(0)

    # 2. Clean up any stale zombie instances if server was not reachable
    killed = kill_stale_orphan_instances()
    if killed > 0:
        logger.info(f"Cleaned up {killed} stale orphan rat process(es).")

    # 3. Launch the single resident application
    if reasoning_engine is None:
        res_app = ResidentApplication(mode=mode)
    else:
        res_app = ResidentApplication(mode=mode, reasoning_engine=reasoning_engine,
                                      allow_synthetic_policy=allow_synthetic_policy)
    sys.exit(res_app.run())
