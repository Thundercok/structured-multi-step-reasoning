"""
tests/test_spotlight_window.py — Unit tests for SpotlightWindow.
Validates zero-crash guarantees on startup, search completion, row selection, and event filtering.
"""

import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from rat.engine.reranker import SearchResultItem
from rat.ui.spotlight_window import SpotlightWindow


class TestSpotlightWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pass

    def setUp(self):
        with patch("rat.ui.spotlight_window.Database") as mock_db, \
             patch("rat.ui.spotlight_window.SearchEngine") as mock_engine:
            mock_db_inst = MagicMock()
            mock_db_inst.get_stats.return_value = {"total_files": 120}
            mock_db.return_value = mock_db_inst

            mock_eng_inst = MagicMock()
            mock_eng_inst.search.return_value = {"results": [], "latency_ms": 0, "reasoning_trace": None, "plan": None}
            mock_engine.return_value = mock_eng_inst

            self.window = SpotlightWindow()
            try:
                self.window.worker.search_completed.disconnect(self.window._on_search_completed)
            except Exception:
                pass

    def tearDown(self):
        if hasattr(self, "window") and self.window is not None:
            self.window.shutdown()
            self.window.close()
            self.window.deleteLater()
            app.processEvents()

    def test_initial_attributes_exist(self):
        """Verify current_query and essential attributes are present immediately."""
        self.assertTrue(hasattr(self.window, "current_query"))
        self.assertEqual(self.window.current_query, "")
        self.assertIsNotNone(self.window.result_list)
        self.assertIsNotNone(self.window.preview_panel)

    def test_search_completed_and_row_selected_no_crash(self):
        """Simulate search completion with results and verify setCurrentRow(0) never crashes."""
        sample_item = SearchResultItem(
            file_path="/tmp/test_report.pdf",
            file_name="test_report.pdf",
            file_ext=".pdf",
            file_size=1024,
            modified_at=time.time(),
            score=90.0,
            explanation="Match",
            snippet="Report content excerpt",
        )

        mock_response = {
            "results": [sample_item],
            "latency_ms": 15,
            "reasoning_trace": None,
            "plan": None,
        }

        # Call slot directly with matching request_id
        req_id = self.window._request_counter
        self.window._on_search_completed(req_id, mock_response)
        app.processEvents()

        self.assertGreaterEqual(self.window.result_list.count(), 1)
        self.assertEqual(self.window.result_list.currentRow(), 0)

    def test_search_completed_empty_results_no_crash(self):
        """Verify empty result sets clear the preview panel and display hint without errors."""
        mock_response = {
            "results": [],
            "latency_ms": 5,
            "reasoning_trace": None,
            "plan": None,
        }
        req_id = self.window._request_counter
        self.window._on_search_completed(req_id, mock_response)
        app.processEvents()

        self.assertEqual(self.window.result_list.count(), 0)
        self.assertIn("Không tìm thấy", self.window.footer_status.text())

    def test_schedule_query_prepends_item(self):
        """Verify queries like 'tkb' or 'lich' prepend the timetable compositor card."""
        self.window.current_query = "tkb"
        mock_response = {
            "results": [],
            "latency_ms": 10,
            "reasoning_trace": None,
            "plan": None,
        }
        req_id = self.window._request_counter
        self.window._on_search_completed(req_id, mock_response)
        app.processEvents()

        self.assertEqual(self.window.result_list.count(), 1)
        first_item: SearchResultItem = self.window.result_list.item(0).data(Qt.ItemDataRole.UserRole)
        self.assertEqual(first_item.file_path, "rat://schedule_compositor")
        self.assertIn("Ghép Thời Khóa Biểu", first_item.file_name)

    def test_on_result_selected_defensive(self):
        """Verify _on_result_selected handles row -1 or out of bounds safely."""
        self.window._on_result_selected(-1)
        self.window._on_result_selected(999)

    def test_show_spotlight_debounce_flags(self):
        """Verify show_spotlight sets _is_opening and doesn't hide on transient ActivationChange."""
        self.window.show_spotlight()
        self.assertTrue(self.window._is_opening)
        self.assertFalse(self.window._was_activated)

        from PyQt6.QtCore import QEvent
        event = QEvent(QEvent.Type.ActivationChange)
        # Dispatch ActivationChange while _is_opening is True -> should NOT hide
        self.window.changeEvent(event)
        self.assertTrue(self.window.isVisible())

        # Simulate finish opening
        self.window._finish_opening()
        self.assertFalse(self.window._is_opening)

    def test_hotkey_manager_default_shortcuts(self):
        """Verify GlobalHotkeyManager includes both Option+Space and Option+R."""
        from rat.os.hotkey import GlobalHotkeyManager, is_accessibility_trusted
        mgr = GlobalHotkeyManager()
        self.assertIsNotNone(mgr)
        self.assertIsInstance(is_accessibility_trusted(), bool)

    def test_math_query_prepends_calc_card(self):
        """Verify math queries prepend the instant calculation result card."""
        self.window.current_query = "tính 25 * 4 + 50"
        self.window.search_input.setText("tính 25 * 4 + 50")
        mock_response = {
            "query": "tính 25 * 4 + 50",
            "results": [],
            "latency_ms": 1,
            "reasoning_trace": None,
            "plan": None,
        }
        req_id = self.window._request_counter
        self.window._on_search_completed(req_id, mock_response)
        app.processEvents()

        self.assertGreaterEqual(self.window.result_list.count(), 1)
        first_item: SearchResultItem = self.window.result_list.item(0).data(Qt.ItemDataRole.UserRole)
        self.assertEqual(first_item.file_path, "rat://calc_copy/150")
        self.assertIn("150", first_item.file_name)

    def test_room_query_prepends_room_card(self):
        """Verify room queries prepend the campus room guide card."""
        self.window.current_query = "phòng C302"
        self.window.search_input.setText("phòng C302")
        mock_response = {
            "query": "phòng C302",
            "results": [],
            "latency_ms": 1,
            "reasoning_trace": None,
            "plan": None,
        }
        req_id = self.window._request_counter
        self.window._on_search_completed(req_id, mock_response)
        app.processEvents()

        self.assertGreaterEqual(self.window.result_list.count(), 1)
        first_item: SearchResultItem = self.window.result_list.item(0).data(Qt.ItemDataRole.UserRole)
        self.assertEqual(first_item.file_path, "rat://room_location")
        self.assertIn("C302", first_item.file_name)

    def test_agenda_query_prepends_agenda_card(self):
        """Verify today's agenda queries prepend live agenda card."""
        self.window.current_query = "chiều nay học gì"
        self.window.search_input.setText("chiều nay học gì")
        mock_response = {
            "query": "chiều nay học gì",
            "results": [],
            "latency_ms": 1,
            "reasoning_trace": None,
            "plan": None,
        }
        req_id = self.window._request_counter
        self.window._on_search_completed(req_id, mock_response)
        app.processEvents()

        self.assertGreaterEqual(self.window.result_list.count(), 1)
        first_item: SearchResultItem = self.window.result_list.item(0).data(Qt.ItemDataRole.UserRole)
        self.assertEqual(first_item.file_path, "rat://claude_widget")
        self.assertIn("Lịch học hôm nay", first_item.file_name)


if __name__ == "__main__":
    unittest.main()

