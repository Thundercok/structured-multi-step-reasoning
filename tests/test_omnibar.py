"""
tests/test_omnibar.py — Unit tests for OmnibarWindow (Unified Casual Surface).
Validates zero-crash guarantees on startup, section switching, agenda rendering,
and search result injection.
"""

import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from rat.engine.reranker import SearchResultItem
from rat.ui.omnibar import OmnibarWindow


class TestOmnibarWindow(unittest.TestCase):
    def setUp(self):
        with patch("rat.ui.omnibar.Database") as mock_db, \
             patch("rat.ui.omnibar.SearchEngine") as mock_engine:
            mock_db_inst = MagicMock()
            mock_db_inst.get_stats.return_value = {"total_files": 88}
            mock_db_inst.get_recent_documents.return_value = [
                {
                    "file_path": "/Users/thundercock2/Documents/DSA_HW1.pdf",
                    "file_name": "DSA_HW1.pdf",
                    "file_ext": ".pdf",
                    "file_size": 2048,
                    "modified_at": time.time(),
                    "category": "docs",
                }
            ]
            mock_db.return_value = mock_db_inst

            mock_eng_inst = MagicMock()
            mock_eng_inst.search.return_value = {"results": [], "latency_ms": 5, "reasoning_trace": None, "plan": None}
            mock_engine.return_value = mock_eng_inst

            self.window = OmnibarWindow()
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

    def test_initial_attributes_and_sections(self):
        """Verify Omnibar initialized with 4 sections and defaults to Home (0)."""
        self.assertIsNotNone(self.window.search_input)
        self.assertEqual(len(self.window.section_buttons), 4)
        self.assertEqual(self.window.current_section_idx, 0)
        self.assertEqual(self.window.content_stack.currentIndex(), 0)
        self.assertIn("Huy", self.window.current_member.name)

    def test_switch_sections(self):
        """Verify switching through all sections (Home, Files, Schedule, Club) works smoothly."""
        for idx in range(4):
            self.window.switch_section(idx)
            app.processEvents()
            self.assertEqual(self.window.current_section_idx, idx)
            self.assertEqual(self.window.content_stack.currentIndex(), idx)

    def test_home_agenda_rendered(self):
        """Verify Home section live agenda rendered without error."""
        self.window.switch_section(0)
        app.processEvents()
        self.assertIsNotNone(self.window.today_date_label.text())
        self.assertIsNotNone(self.window.live_banner_text.text())

    def test_recent_files_in_home_view(self):
        """Verify recent files populated in the Home view."""
        self.window.switch_section(0)
        app.processEvents()
        self.assertGreaterEqual(self.window.recent_list.count(), 1)
        item = self.window.recent_list.item(0)
        data = item.data(Qt.ItemDataRole.UserRole)
        self.assertIn("DSA_HW1.pdf", data.file_name)

    def test_search_injection_math_card(self):
        """Verify quick calculation produces a math card at index 0."""
        self.window.current_query = "tính 120 * 4"
        mock_response = {
            "results": [],
            "latency_ms": 2,
            "reasoning_trace": None,
            "plan": None,
        }
        req_id = self.window._request_counter
        self.window._on_search_completed(req_id, mock_response)
        app.processEvents()

        self.assertGreaterEqual(self.window.result_list.count(), 1)
        top_item = self.window.result_list.item(0).data(Qt.ItemDataRole.UserRole)
        self.assertIn("480", top_item.file_name)
        self.assertTrue(top_item.file_path.startswith("rat://calc_copy/480"))

    def test_search_injection_room_card(self):
        """Verify room query injects campus navigation card."""
        self.window.current_query = "phòng C302"
        mock_response = {
            "results": [],
            "latency_ms": 2,
            "reasoning_trace": None,
            "plan": None,
        }
        req_id = self.window._request_counter
        self.window._on_search_completed(req_id, mock_response)
        app.processEvents()

        self.assertGreaterEqual(self.window.result_list.count(), 1)
        top_item = self.window.result_list.item(0).data(Qt.ItemDataRole.UserRole)
        self.assertIn("C302", top_item.file_name)
        self.assertIn("Tòa C", top_item.snippet)

    def test_search_injection_agenda_card(self):
        """Verify query 'hôm nay' injects live agenda card."""
        self.window.current_query = "hôm nay có học gì không"
        mock_response = {
            "results": [],
            "latency_ms": 3,
            "reasoning_trace": None,
            "plan": None,
        }
        req_id = self.window._request_counter
        self.window._on_search_completed(req_id, mock_response)
        app.processEvents()

        self.assertGreaterEqual(self.window.result_list.count(), 1)
        top_item = self.window.result_list.item(0).data(Qt.ItemDataRole.UserRole)
        self.assertTrue("hôm nay" in top_item.file_name.lower())

    def test_clear_search_auto_returns_to_home(self):
        """Verify clearing search text in Files view automatically returns user to Chatbot view."""
        self.window.switch_section(1)
        self.assertEqual(self.window.current_section_idx, 1)

        self.window.search_input.setText("some query")
        self.window.search_input.clear()
        app.processEvents()
        self.assertEqual(self.window.current_section_idx, 0)

    def test_search_injection_reasoning_card(self):
        """Verify academic reasoning query injects the RL Meta-Controller card."""
        self.window.current_query = "quy chế học vụ: sinh viên song bằng thạc sĩ có bị đình chỉ không"
        mock_response = {
            "results": [],
            "latency_ms": 5,
            "reasoning_trace": None,
            "plan": None,
        }
        req_id = self.window._request_counter
        self.window._on_search_completed(req_id, mock_response)
        app.processEvents()

        self.assertGreaterEqual(self.window.result_list.count(), 1)
        top_item = self.window.result_list.item(0).data(Qt.ItemDataRole.UserRole)
        self.assertIn("Suy luận", top_item.file_name)
        self.assertIn("Meta-Controller", top_item.explanation)
        self.assertIsNotNone(self.window.preview_panel.current_trace)
        self.assertGreater(len(self.window.preview_panel.current_trace.steps), 0)

    def test_mascot_idle_state_and_geometry(self):
        """Verify mascot starts in IDLE (núp) state with 0 deg rotation and hidden bubble."""
        mascot = self.window.mascot_peeking
        self.assertIsNotNone(mascot)
        self.assertFalse(mascot.is_speaking)
        self.assertEqual(mascot.rotation, 0.0)
        self.assertEqual(mascot.rot_idle, 0.0)
        self.assertTrue(self.window.speech_bubble.isHidden())

        # Verify mascot is anchored properly relative to container
        self.assertEqual(mascot.x(), mascot.x_idle)
        self.assertEqual(mascot.y(), mascot.y_idle)

    def test_mascot_diagonal_popout_and_speech_bubble(self):
        """Verify diagonal pop-out combines X-shift, Y-slide, and 10 deg rotation with OutBack easing."""
        from PyQt6.QtCore import QEasingCurve
        mascot = self.window.mascot_peeking

        # Trigger speaking
        self.window.set_mascot_speaking("Xin chào bạn học!")
        self.assertTrue(mascot.is_speaking)

        # Check animation specs: ~350ms duration, OutBack easing
        self.assertEqual(mascot._pos_anim.duration(), 350)
        self.assertEqual(mascot._rot_anim.duration(), 350)
        self.assertEqual(mascot._pos_anim.easingCurve().type(), QEasingCurve.Type.OutBack)
        self.assertEqual(mascot._rot_anim.easingCurve().type(), QEasingCurve.Type.OutBack)

        # Check target values: Y slides up, X shifts 15-25px (+20px), rotation tilts to 10 deg
        self.assertEqual(mascot._pos_anim.endValue().x(), mascot.x_speaking)
        self.assertEqual(mascot._pos_anim.endValue().y(), mascot.y_speaking)
        self.assertEqual(mascot.x_speaking - mascot.x_idle, 20)
        self.assertLess(mascot.y_speaking, mascot.y_idle)
        self.assertEqual(mascot._rot_anim.endValue(), 10.0)

        # Simulate completion of pop-out animation
        mascot._anim_group.stop()
        mascot.move(mascot.x_speaking, mascot.y_speaking)
        mascot.rotation = mascot.rot_speaking
        mascot.speaking_popped_out.emit()
        app.processEvents()

        # Speech bubble appears right after pop-out completes
        self.assertFalse(self.window.speech_bubble.isHidden())
        self.assertIn("Xin chào bạn học!", self.window.speech_bubble.text())
        self.assertEqual(self.window.speech_bubble.tail_y, 46)

        # Retreat back to idle
        self.window.set_mascot_idle()
        self.assertFalse(mascot.is_speaking)
        self.assertEqual(mascot._rot_anim.endValue(), 0.0)
        self.assertEqual(mascot._pos_anim.endValue().x(), mascot.x_idle)
        self.assertEqual(mascot._pos_anim.endValue().y(), mascot.y_idle)


if __name__ == "__main__":
    unittest.main()

