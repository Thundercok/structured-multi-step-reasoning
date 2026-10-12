"""
tests/test_timetable_chat_cards.py — Unit tests for In-Chat Timetable Cards & Suggestion Chips.
Verifies Feature A (Session Cards with Action Buttons) and Feature B (Contextual Follow-up Chips).
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication

from rat.timetable.model import ClassSession
from rat.ui.chat_stream import TimetableSessionCard, TimetableDeckWidget
from rat.ui.omnibar import OmnibarWindow


class TestTimetableChatCards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_session_card_rendering_and_actions(self):
        session = ClassSession(
            start_period=1,
            end_period=3,
            course_name="Kiến trúc Máy tính",
            room="B402",
            degree_level="undergrad",
        )
        card = TimetableSessionCard(session)

        # Check action button labels
        self.assertIn("Tìm tài liệu", card.btn_files.text())
        self.assertIn("Vị trí", card.btn_room.text())
        self.assertIn("Chép", card.btn_copy.text())

        # Test prompt signals
        emitted_prompts = []
        card.prompt_requested.connect(emitted_prompts.append)

        card.btn_files.click()
        self.assertEqual(emitted_prompts[-1], "tìm tài liệu Kiến trúc Máy tính")

        card.btn_room.click()
        self.assertEqual(emitted_prompts[-1], "phòng B402")

        # Test copy button
        card.btn_copy.click()
        self.assertEqual(card.btn_copy.text(), "✓ Đã chép")
        clip_text = QApplication.clipboard().text()
        self.assertIn("Kiến trúc Máy tính", clip_text)
        self.assertIn("B402", clip_text)

    def test_session_card_with_course_code_smart_file_bridge(self):
        session = ClassSession(
            start_period=1,
            end_period=3,
            course_name="Kiến trúc Máy tính",
            room="B402",
            course_code="501043",
        )
        card = TimetableSessionCard(session)
        emitted_prompts = []
        card.prompt_requested.connect(emitted_prompts.append)

        card.btn_files.click()
        self.assertEqual(emitted_prompts[-1], "tìm tài liệu 501043 Kiến trúc Máy tính")

        card.btn_copy.click()
        clip_text = QApplication.clipboard().text()
        self.assertIn("501043", clip_text)

    def test_deck_widget_with_sessions_and_followup_chips(self):
        s1 = ClassSession(start_period=1, end_period=3, course_name="Toán rời rạc", room="C201")
        s2 = ClassSession(start_period=4, end_period=6, course_name="Hệ điều hành", room="A601")
        deck = TimetableDeckWidget(sessions=[s1, s2], day_label="hôm nay")

        self.assertEqual(len(deck.session_cards), 2)
        self.assertGreaterEqual(len(deck.follow_up_chips), 3)

        emitted = []
        deck.prompt_requested.connect(emitted.append)

        # First chip should be "Lịch ngày mai"
        tomorrow_chip = deck.follow_up_chips[0]
        self.assertIn("ngày mai", tomorrow_chip.text().lower())
        tomorrow_chip.click()
        self.assertIn("ngày mai", emitted[-1])

        # Second chip should be "Khung giờ rảnh"
        free_chip = deck.follow_up_chips[1]
        self.assertIn("rảnh", free_chip.text().lower())
        free_chip.click()
        self.assertIn("giờ rảnh", emitted[-1])

    def test_deck_widget_empty_schedule(self):
        deck = TimetableDeckWidget(sessions=[], day_label="Chủ Nhật")
        self.assertEqual(len(deck.session_cards), 0)
        self.assertGreaterEqual(len(deck.follow_up_chips), 3)

    @patch("rat.os.app.activate_macos_app")
    @patch("rat.ui.omnibar.configure_macos_fullscreen_overlay")
    def test_omnibar_schedule_chat_delivers_deck_widget(self, _mock_overlay, _mock_act):
        window = OmnibarWindow()
        try:
            window.show_omnibar(initial_section=0)
            window._submit_chat_prompt("hôm nay học gì?")

            # Verify that assistant delivered a message with TimetableDeckWidget
            last_card = window.chat_stream.container.layout().itemAt(
                window.chat_stream.container.layout().count() - 1
            )
            self.assertIsNotNone(last_card)

            # Check footer status
            self.assertIn("Lịch học", window.footer_status.text())
        finally:
            window.shutdown()
            window.close()

    @patch("rat.os.app.activate_macos_app")
    @patch("rat.ui.omnibar.configure_macos_fullscreen_overlay")
    def test_footer_keycaps_and_stationary_mascot(self, _mock_overlay, _mock_act):
        window = OmnibarWindow()
        try:
            window.show_omnibar(initial_section=0)
            # Verify keycaps_box is populated with tactile keycaps
            self.assertTrue(hasattr(window, "keycaps_box"))
            self.assertGreaterEqual(window.keycaps_layout.count(), 3)
            # Click mascot should NOT trigger jumping / speaking
            window.mascot_peeking.mousePressEvent(MagicMock())
            self.assertFalse(window.mascot_peeking.is_speaking)
        finally:
            window.shutdown()
            window.close()


if __name__ == "__main__":
    unittest.main()
