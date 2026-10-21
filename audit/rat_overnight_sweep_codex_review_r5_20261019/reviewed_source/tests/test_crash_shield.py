"""
tests/test_crash_shield.py — Enterprise Crash Shield & Lifecycle Hardening Tests.
Validates sys.excepthook, safe_slot, unparented QThread lifecycle, and graceful window shutdowns.
"""

import os
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QApplication

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from rat.os.crash_shield import (
    CRASH_LOG_FILE,
    global_excepthook,
    install_crash_shield,
    safe_slot,
    thread_excepthook,
)
from rat.ui.finder_window import FinderWindow
from rat.ui.settings_dialog import IndexWorker, SettingsDialog
from rat.ui.spotlight_window import SpotlightWindow


class TestCrashShield(unittest.TestCase):
    """Test suite for crash prevention, exception shielding, and thread shutdown safety."""

    def setUp(self):
        install_crash_shield()

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

        self.assertTrue(CRASH_LOG_FILE.exists())
        with open(CRASH_LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Diagnostic crash test for CrashShield", content)
        self.assertIn("RuntimeError", content)

    def test_spotlight_window_unparented_thread_shutdown(self):
        """Verify SpotlightWindow.search_thread is unparented and shuts down cleanly."""
        with patch("rat.ui.spotlight_window.Database") as mock_db, \
             patch("rat.ui.spotlight_window.SearchEngine") as mock_engine:
            mock_db_inst = MagicMock()
            mock_db_inst.get_stats.return_value = {"total_files": 100}
            mock_db.return_value = mock_db_inst

            mock_eng_inst = MagicMock()
            mock_eng_inst.search.return_value = {"results": [], "latency_ms": 0}
            mock_engine.return_value = mock_eng_inst

            window = SpotlightWindow()
            # Critical verification: Thread must NOT have QWidget parent
            self.assertIsNone(window.search_thread.parent())

            # Shutdown must stop thread safely
            window.shutdown()
            self.assertIsNone(window.search_thread)
            window.deleteLater()
            app.processEvents()

    def test_finder_window_unparented_threads_shutdown(self):
        """Verify FinderWindow search and QA threads are unparented and shut down cleanly."""
        with patch("rat.ui.finder_window.Database") as mock_db, \
             patch("rat.ui.finder_window.SearchEngine") as mock_engine:
            mock_db_inst = MagicMock()
            mock_db_inst.get_stats.return_value = {"total_files": 100}
            mock_db.return_value = mock_db_inst

            mock_eng_inst = MagicMock()
            mock_eng_inst.search.return_value = {"results": [], "latency_ms": 0}
            mock_engine.return_value = mock_eng_inst

            window = FinderWindow()
            # Critical verification: Threads must NOT have QWidget parent
            self.assertIsNone(window.search_thread.parent())
            self.assertIsNone(window.qa_thread.parent())

            # Shutdown must terminate both threads safely
            window.shutdown()
            self.assertIsNone(window.search_thread)
            self.assertIsNone(window.qa_thread)
            window.deleteLater()
            app.processEvents()

    def test_settings_dialog_worker_shutdown(self):
        """Verify SettingsDialog safely manages IndexWorker thread lifecycle."""
        with patch("rat.ui.settings_dialog.Database") as mock_db, \
             patch("rat.ui.settings_dialog.Indexer"):
            mock_db_inst = MagicMock()
            mock_db_inst.get_stats.return_value = {"total_files": 50, "total_size_bytes": 1024 * 1024}
            mock_db.return_value = mock_db_inst

            dlg = SettingsDialog()
            # Calling _shutdown_worker when worker is None shouldn't crash
            dlg._shutdown_worker()
            self.assertIsNone(getattr(dlg, "worker", None))

            # Simulate an instantiated IndexWorker
            mock_indexer = MagicMock()
            worker = IndexWorker(mock_indexer)
            self.assertIsNone(worker.parent())
            dlg.worker = worker
            dlg._shutdown_worker()
            self.assertIsNone(dlg.worker)

            dlg.deleteLater()
            app.processEvents()

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

    def test_schedule_window_shutdown_and_close(self):
        """Verify ScheduleCompositorWindow handles hide and shutdown cleanly."""
        from rat.ui.schedule_window import ScheduleCompositorWindow
        with patch("rat.ui.schedule_window.load_club_members", return_value=[]):
            win = ScheduleCompositorWindow()
            win.shutdown()
            win.deleteLater()
            app.processEvents()


if __name__ == "__main__":
    unittest.main()
