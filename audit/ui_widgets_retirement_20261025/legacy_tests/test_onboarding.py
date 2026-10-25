"""
tests.test_onboarding — Unit tests for First-Run Onboarding Dialog & Permission checks.
"""

import sys
import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication

from rat.ui.onboarding_dialog import OnboardingDialog, check_accessibility_status


class TestOnboarding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_accessibility_check_returns_bool(self):
        res = check_accessibility_status()
        self.assertIsInstance(res, bool)

    def test_onboarding_dialog_initialization(self):
        dialog = OnboardingDialog()
        self.assertIsNotNone(dialog)
        self.assertEqual(dialog.windowTitle(), "rat — Thiết lập lần đầu")
        self.assertEqual(dialog.width(), 540)
        self.assertEqual(dialog.height(), 520)
        self.assertGreater(len(dialog.dir_checkboxes), 0)

    @patch("rat.ui.onboarding_dialog.config")
    def test_onboarding_finish_flow(self, mock_config):
        mock_config.indexed_directories = []
        mock_config.first_run_completed = False
        mock_config.save = unittest.mock.MagicMock()

        dialog = OnboardingDialog()
        completed_signal_fired = []
        dialog.setup_completed.connect(lambda: completed_signal_fired.append(True))

        dialog._on_finish()

        self.assertTrue(mock_config.first_run_completed)
        mock_config.save.assert_called_once()
        self.assertEqual(len(completed_signal_fired), 1)


if __name__ == "__main__":
    unittest.main()
