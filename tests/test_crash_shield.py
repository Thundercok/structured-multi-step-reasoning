"""
tests/test_crash_shield.py — Enterprise Crash Shield & Lifecycle Hardening Tests.
Validates sys.excepthook, safe_slot, unparented QThread lifecycle, and graceful controller shutdowns.
"""

import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtGui import QGuiApplication

app = QGuiApplication.instance()
if app is None:
    app = QGuiApplication(sys.argv)

from rat.os.crash_shield import (
    CRASH_LOG_FILE,
    global_excepthook,
    install_crash_shield,
    safe_slot,
    thread_excepthook,
)


class TestCrashShield(unittest.TestCase):
    """Test suite for crash prevention, exception shielding, and thread shutdown safety."""

    def setUp(self):
        from rat.os import crash_shield
        self._original_hooks = sys.excepthook, threading.excepthook
        self._temp_logs = tempfile.TemporaryDirectory(prefix='rat-crash-shield-test-')
        self.addCleanup(self._temp_logs.cleanup)
        self.log_file = Path(self._temp_logs.name) / 'crash.log'
        for name, value in [('CRASH_LOG_DIR', self.log_file.parent), ('CRASH_LOG_FILE', self.log_file), ('_SHIELD_INSTALLED', False)]:
            patcher = patch.object(crash_shield, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self._restore_hooks)
        install_crash_shield()

    def _restore_hooks(self):
        sys.excepthook, threading.excepthook = self._original_hooks

    def _dispose_resident(self, resident):
        from PyQt6.QtCore import QCoreApplication, QEvent, QUrl
        app.removeEventFilter(resident)
        app.aboutToQuit.disconnect(resident._on_app_quit)
        if resident._shutdown_timer:
            resident._shutdown_timer.stop()
        if resident.desk_controller:
            resident.desk_controller.close()
        if resident.desk_view:
            view = resident.desk_view
            view._resize_timer.stop()
            view._close_timer.stop()
            view.close()
            view.setSource(QUrl())
            view.deleteLater()
        resident.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_crash_shield_installation(self):
        """Verify that install_crash_shield sets sys.excepthook and threading.excepthook."""
        self.assertEqual(sys.excepthook, global_excepthook)
        if hasattr(threading, "excepthook"):
            self.assertEqual(threading.excepthook, thread_excepthook)

    def test_safe_slot_catches_exception(self):
        """Verify that @safe_slot absorbs exceptions and returns None instead of crashing."""
        @safe_slot
        def buggy_slot():
            raise ValueError("Simulated slot crash error")

        result = buggy_slot()
        self.assertIsNone(result)

    def test_global_excepthook_keeps_qt_alive_and_logs(self):
        """Verify global_excepthook logs to crash.log without terminating Qt process."""
        try:
            raise RuntimeError("Diagnostic crash test for CrashShield")
        except RuntimeError:
            exc_type, exc_val, exc_tb = sys.exc_info()
            global_excepthook(exc_type, exc_val, exc_tb)

        self.assertTrue(self.log_file.exists())
        with open(self.log_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Diagnostic crash test for CrashShield", content)
        self.assertIn("RuntimeError", content)

    def test_system_tray_manager_shutdown(self):
        """Verify SystemTrayManager.shutdown safely terminates any active rescan worker."""
        from rat.os.menu_bar import RescanWorker, SystemTrayManager
        with patch("rat.os.menu_bar.Database") as mock_db:
            mock_db_inst = MagicMock()
            mock_db_inst.get_stats.return_value = {"total_files": 10, "total_size_bytes": 1024}
            mock_db.return_value = mock_db_inst

            tray = SystemTrayManager()
            # Shutdown when worker is None shouldn't crash
            tray.shutdown()
            self.assertIsNone(tray.rescan_worker)

            # Simulate worker
            worker = RescanWorker(mock_db_inst)
            self.assertIsNone(worker.parent())
            tray.rescan_worker = worker
            tray.shutdown()
            self.assertIsNone(tray.rescan_worker)

    def test_quick_desk_controller_clean_shutdown(self):
        """Verify QuickPDFController background thread shuts down without memory leaks."""
        from rat.ui.quick_pdf_controller import QuickPDFController
        ctrl = QuickPDFController(auto_init_finder=False)
        self.assertTrue(ctrl.close())
        app.processEvents()

    def test_menu_bar_quit_triggers_on_quit_callback(self):
        """Verify Menu Bar Quit action routes through on_quit callback rather than direct quit."""
        from rat.os.menu_bar import SystemTrayManager
        quit_called = []
        with patch("rat.os.menu_bar.Database") as mock_db:
            mock_db.return_value.get_stats.return_value = {"total_files": 10, "total_size_bytes": 1024 * 1024}
            tray = SystemTrayManager(on_quit=lambda: quit_called.append(True))
            menu = tray.tray_icon.contextMenu()
            action = next(a for a in menu.actions() if "Thoát" in a.text())
            action.trigger()
            self.assertEqual(quit_called, [True])
            tray.shutdown()

    def test_resident_app_request_quit_with_active_worker(self):
        """Verify request_quit intercepts, cancels active inference workers, and cleanly completes."""
        from rat.os.app import ResidentApplication
        from PyQt6.QtCore import QThread
        import time

        class ActiveWorker(QThread):
            def run(self):
                while not self.isInterruptionRequested():
                    time.sleep(0.01)

        worker = ActiveWorker()
        worker.start()

        res_app = ResidentApplication(mode="daemon")
        self.addCleanup(self._dispose_resident, res_app)
        view, ctrl = res_app._ensure_desk()
        ctrl._execution_workers.add(worker)

        # While worker is active, close() returns False
        self.assertFalse(ctrl.close())

        outcome = []
        res_app.request_quit(timeout=1.5, on_finished=lambda clean: outcome.append(clean))

        # Pump Qt event loop until poll timer finishes
        deadline = time.monotonic() + 2.0
        while not outcome and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.02)

        worker.wait(1000)
        self.assertEqual(outcome, [True])
        self.assertTrue(res_app._clean_shutdown)

    def test_resident_app_request_quit_idempotent(self):
        """Verify calling request_quit multiple times is idempotent and does not recreate timers."""
        from rat.os.app import ResidentApplication
        res_app = ResidentApplication(mode="daemon")
        self.addCleanup(self._dispose_resident, res_app)
        view, ctrl = res_app._ensure_desk()

        outcome = []
        res_app.request_quit(timeout=1.0, on_finished=lambda clean: outcome.append(clean))
        self.assertEqual(res_app._shutdown_state, "terminated")
        self.assertTrue(res_app._teardown_done)
        self.assertEqual(outcome, [True])

        # Duplicate call when terminated should safely call on_finished immediately without state corruption
        dup_outcome = []
        res_app.request_quit(timeout=1.0, on_finished=lambda clean: dup_outcome.append(clean))
        self.assertEqual(dup_outcome, [True])
        self.assertEqual(res_app._shutdown_state, "terminated")

    def test_resident_app_warmup_worker_blocks_clean_quit(self):
        """Verify that a running warmup_thread prevents premature clean quit until it terminates."""
        from rat.os.app import ResidentApplication
        from PyQt6.QtCore import QThread
        import time

        class MockWarmupThread(QThread):
            def __init__(self):
                super().__init__()
                self.running = True

            def run(self):
                while self.running:
                    time.sleep(0.01)

        warmup = MockWarmupThread()
        warmup.start()

        res_app = ResidentApplication(mode="daemon")
        self.addCleanup(self._dispose_resident, res_app)
        res_app.warmup_thread = warmup

        # Warmup worker must be registered as active
        active = res_app.get_active_workers()
        self.assertIn("SemesterWarmupWorker", active)
        self.assertFalse(res_app.all_workers_finished())

        outcome = []
        res_app.request_quit(timeout=0.5, on_finished=lambda clean: outcome.append(clean))

        # While warmup is running, quit must be deferred
        for _ in range(5):
            app.processEvents()
            time.sleep(0.01)
        self.assertEqual(outcome, [])
        self.assertEqual(res_app._shutdown_state, "quitting")

        # Now stop warmup thread
        warmup.running = False
        warmup.wait(1000)

        # Event loop poll must now detect termination and finalize teardown
        deadline = time.monotonic() + 1.0
        while not outcome and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)

        self.assertEqual(outcome, [True])
        self.assertTrue(res_app._clean_shutdown)
        self.assertEqual(res_app._shutdown_state, "terminated")

    def test_resident_app_request_quit_timeout_reports_incomplete(self):
        """Verify that when a worker exceeds timeout, app stays alive, retains ownership, and only exits after worker finishes."""
        from rat.os.app import ResidentApplication
        from PyQt6.QtCore import QThread
        import time

        class StuckWorker(QThread):
            def __init__(self):
                super().__init__()
                self.force_stop = False

            def run(self):
                while not self.force_stop:
                    time.sleep(0.01)

        worker = StuckWorker()
        worker.start()

        res_app = ResidentApplication(mode="daemon")
        self.addCleanup(self._dispose_resident, res_app)
        view, ctrl = res_app._ensure_desk()
        ctrl._execution_workers.add(worker)

        outcome = []
        # Short timeout of 0.05s
        res_app.request_quit(timeout=0.05, on_finished=lambda clean: outcome.append(clean))

        # Spin event loop for 0.12s (well past the 0.05s timeout)
        t_start = time.monotonic()
        while time.monotonic() - t_start < 0.12:
            app.processEvents()
            time.sleep(0.01)

        # 1. Timeout expired: state transitions to 'waiting_past_timeout', clean is False
        self.assertEqual(res_app._shutdown_state, "waiting_past_timeout")
        self.assertFalse(res_app._clean_shutdown)

        # 2. Crucially, the app has NOT terminated yet, and outcome callback has NOT fired
        self.assertEqual(outcome, [])
        self.assertFalse(res_app._teardown_done)
        self.assertTrue(worker.isRunning())
        self.assertIn(worker, ctrl._execution_workers)
        self.assertIn("DeskWorker(StuckWorker)", res_app.get_active_workers())

        # 3. Duplicate request_quit call while in waiting_past_timeout is safely ignored
        timer = res_app._shutdown_timer
        res_app.request_quit(timeout=0.05)
        self.assertIs(res_app._shutdown_timer, timer)
        self.assertEqual(res_app._shutdown_state, "waiting_past_timeout")

        # 4. Now let the worker finally stop
        worker.force_stop = True
        worker.wait(1000)

        # 5. Spin event loop until poll timer detects worker has stopped
        deadline = time.monotonic() + 1.0
        while not outcome and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)

        # 6. Now application teardown completes with clean=False (since it timed out)
        self.assertEqual(outcome, [False])
        self.assertFalse(res_app._clean_shutdown)
        self.assertEqual(res_app._shutdown_state, "terminated")
        self.assertTrue(res_app._teardown_done)


if __name__ == "__main__":
    unittest.main()
