"""
tests/test_compact_cot.py — Unit tests for Min Mode Chain-of-Thought (CoT) Ribbon.
"""

import sys
import unittest
from PyQt6.QtWidgets import QApplication

# Ensure headless Qt application
app = QApplication.instance() or QApplication(sys.argv)

from rat.ui.compact_cot import CompactCoTBar


class TestCompactCoT(unittest.TestCase):

    def setUp(self) -> None:
        self.cot_bar = CompactCoTBar()

    def tearDown(self) -> None:
        self.cot_bar.deleteLater()

    def test_initial_state(self) -> None:
        """Verify initial CoT bar is hidden and clean."""
        self.assertFalse(self.cot_bar.isVisible())
        self.assertFalse(self.cot_bar.is_details_expanded)

    def test_thinking_state(self) -> None:
        """Verify thinking state displays pulsing message."""
        self.cot_bar.set_thinking_state("Kiểm chứng đa tầng...")
        self.assertTrue(self.cot_bar.isVisible())
        self.assertIn("⚡ CoT", self.cot_bar.conf_badge.text())

    def test_set_steps_and_phase_mapping(self) -> None:
        """Verify steps are parsed into phase pills and confidence badge."""
        steps = [
            "Phân rã: Mã môn 501043 -> CO2003",
            "Truy xuất: Khai thác FTS5 và Dense chunks",
            "Kiểm chứng: Đạt ngưỡng VGC (p=0.98)",
        ]
        self.cot_bar.set_steps(steps, latency_ms=18.5, confidence=0.98)
        self.assertTrue(self.cot_bar.isVisible())
        self.assertEqual(len(self.cot_bar._current_steps), 3)
        self.assertIn("98% tin cậy", self.cot_bar.conf_badge.text())

    def test_toggle_details_drawer(self) -> None:
        """Verify clicking toggle button expands and collapses micro-ladder."""
        steps = ["Phân rã: Query", "Truy xuất: Cache"]
        self.cot_bar.set_steps(steps)
        self.assertFalse(self.cot_bar.is_details_expanded)

        self.cot_bar.toggle_details()
        self.assertTrue(self.cot_bar.is_details_expanded)
        self.assertTrue(self.cot_bar.details_box.isVisible())

        self.cot_bar.toggle_details()
        self.assertFalse(self.cot_bar.is_details_expanded)
        self.assertFalse(self.cot_bar.details_box.isVisible())

    def test_clear_state(self) -> None:
        """Verify clearing resets steps and hides the ribbon."""
        self.cot_bar.set_steps(["Bước 1: Phân tích"])
        self.assertTrue(self.cot_bar.isVisible())

        self.cot_bar.clear()
        self.assertFalse(self.cot_bar.isVisible())
        self.assertEqual(len(self.cot_bar._current_steps), 0)


if __name__ == "__main__":
    unittest.main()
