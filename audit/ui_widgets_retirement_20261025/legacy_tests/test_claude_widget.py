"""
tests.test_claude_widget — Unit & UI tests for ClaudeTimetableWidget & ClaudeTimetableWindow.
"""

import os
import sys
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from rat.ui.claude_widget import (
    ClaudeTimetableWidget,
    ClaudeTimetableWindow,
    parse_natural_query,
)


class TestClaudeTimetableWidget(unittest.TestCase):
    def setUp(self):
        self.widget = ClaudeTimetableWidget()
        self.widget.show()

    def tearDown(self):
        if hasattr(self.widget, "timer") and self.widget.timer.isActive():
            self.widget.timer.stop()
        self.widget.close()
        self.widget.deleteLater()
        app.processEvents()

    def test_natural_query_parser(self):
        # 1. Today intent
        p1 = parse_natural_query("hôm nay học gì")
        self.assertEqual(p1["intent"], "today")

        # 2. Room lookup intent
        p2 = parse_natural_query("phòng C302 ở đâu")
        self.assertEqual(p2["intent"], "room")
        self.assertEqual(p2["room"], "C302")

        # 3. Whos free intent
        p3 = parse_natural_query("ai rảnh bây giờ")
        self.assertEqual(p3["intent"], "whos_free")

        # 4. Conflict detection intent
        p4 = parse_natural_query("kiểm tra xung đột lịch")
        self.assertEqual(p4["intent"], "conflicts")

        # 5. Workload intent
        p5 = parse_natural_query("xem tải môn học và áp lực")
        self.assertEqual(p5["intent"], "workload")

        # 6. Combined day, shift, degree
        p6 = parse_natural_query("thạc sĩ tối thứ 2 học gì")
        self.assertEqual(p6["degree"], "master")
        self.assertEqual(p6["day"], "T2")
        self.assertEqual(p6["shift"], "ca5")
        self.assertEqual(p6["intent"], "schedule")

    def test_ui_initialization(self):
        self.assertGreater(self.widget.member_combo.count(), 0)
        self.assertEqual(len(self.widget.intent_buttons), 7)
        self.assertEqual(self.widget.current_intent, "today")
        self.assertGreater(self.widget.results_layout.count(), 0)

    def test_dynamic_intent_switching(self):
        intents = ["today", "schedule", "whos_free", "conflicts", "room", "workload", "notes"]
        for intent in intents:
            self.widget._apply_intent(intent)
            app.processEvents()
            self.assertEqual(self.widget.current_intent, intent)
            self.assertGreater(
                self.widget.results_layout.count(),
                0,
                f"Intent {intent} resulted in empty results layout"
            )

    def test_natural_query_live_updates(self):
        # Type search query
        self.widget._on_query_text_changed("Giải tích")
        app.processEvents()
        self.assertEqual(self.widget.current_intent, "search")
        self.assertGreater(self.widget.results_layout.count(), 0)

        # Type room query
        self.widget._on_query_text_changed("phòng A608")
        app.processEvents()
        self.assertEqual(self.widget.current_intent, "room")
        self.assertGreater(self.widget.results_layout.count(), 0)

        # Type club free query
        self.widget._on_query_text_changed("ai rảnh")
        app.processEvents()
        self.assertEqual(self.widget.current_intent, "whos_free")
        self.assertGreater(self.widget.results_layout.count(), 0)

    def test_note_saving_and_copy_actions(self):
        # Save note
        test_note = "Hạn nộp báo cáo đồ án: 30/10"
        self.widget._save_note_text("m1", test_note)
        self.assertIn("Hạn nộp", self.widget.course_notes.get("m1", ""))

        # Copy view action
        self.widget._copy_current_view()
        self.assertIn("Đã sao chép", self.widget.footer_status.text())

    def test_floating_window_container(self):
        win = ClaudeTimetableWindow()
        win.show()
        app.processEvents()

        self.assertIn("Claude Timetable", win.windowTitle())
        win.toggle_pin()
        self.assertTrue(win.is_pinned)
        win.toggle_pin()
        self.assertFalse(win.is_pinned)

        if hasattr(win.widget, "timer") and win.widget.timer.isActive():
            win.widget.timer.stop()
        win.close()
        win.deleteLater()
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
