"""
tests/test_quicklook.py — Unit tests for macOS Native QuickLook Preview.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from rat.ui.preview_panel import trigger_quicklook, close_quicklook


class TestQuickLook(unittest.TestCase):

    def tearDown(self) -> None:
        close_quicklook()

    def test_nonexistent_file_returns_false(self) -> None:
        """trigger_quicklook returns False when file does not exist."""
        result = trigger_quicklook("/nonexistent/file/path/here.pdf")
        self.assertFalse(result)

    @patch("platform.system", return_value="Darwin")
    @patch("subprocess.Popen")
    def test_quicklook_toggle(self, mock_popen: MagicMock, mock_platform: MagicMock) -> None:
        """Verify QuickLook launches on first press and toggles off on second press of same file."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # Process is running
        mock_popen.return_value = mock_proc

        dummy_file = __file__  # Existing file
        self.assertTrue(os.path.exists(dummy_file))

        # First press: should launch
        res1 = trigger_quicklook(dummy_file)
        self.assertTrue(res1)
        mock_popen.assert_called_once()

        # Second press on SAME file: should terminate and return False (toggle off)
        res2 = trigger_quicklook(dummy_file)
        self.assertFalse(res2)
        mock_proc.terminate.assert_called_once()

    @patch("platform.system", return_value="Darwin")
    @patch("subprocess.Popen")
    def test_close_quicklook(self, mock_popen: MagicMock, mock_platform: MagicMock) -> None:
        """close_quicklook cleanly terminates active preview process."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        dummy_file = __file__
        trigger_quicklook(dummy_file)
        close_quicklook()
        mock_proc.terminate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
