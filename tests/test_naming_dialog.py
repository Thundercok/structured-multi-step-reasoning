"""
tests/test_naming_dialog.py — Unit tests for FilenameSuggestionDialog and UI integration.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from rat.engine.reranker import SearchResultItem
from rat.ui.action_menu import ActionMenuDialog
from rat.ui.naming_dialog import FilenameSuggestionDialog, NamingWorker
from rat.ui.preview_panel import PreviewPanel


class TestNamingDialogUI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_file_path = os.path.join(self.temp_dir.name, "untitled_document.docx")
        with open(self.test_file_path, "w", encoding="utf-8") as f:
            f.write("Kế hoạch chi tiết kinh doanh và doanh thu năm 2026.")

        self.item = SearchResultItem(
            file_path=self.test_file_path,
            file_name="untitled_document.docx",
            file_ext=".docx",
            file_size=1024,
            modified_at=1700000000.0,
            score=95.0,
            explanation="Relevant file",
            snippet="Kế hoạch chi tiết kinh doanh và doanh thu năm 2026.",
        )

    def tearDown(self):
        self.temp_dir.cleanup()
        app.processEvents()

    def test_action_menu_has_suggest_name_action(self):
        dialog = ActionMenuDialog(target_item=self.item)
        action_ids = [dialog.actions[i][0] for i in range(len(dialog.actions))]
        self.assertIn("suggest_name", action_ids)
        dialog.close()

    def test_preview_panel_has_suggest_name_button_and_signal(self):
        panel = PreviewPanel()
        self.assertTrue(hasattr(panel, "btn_suggest_name"))
        self.assertEqual(panel.btn_suggest_name.text(), "🏷️ Đổi tên")

        received = []
        panel.suggest_name_requested.connect(lambda item: received.append(item))

        panel.set_item(self.item)
        panel.btn_suggest_name.click()
        app.processEvents()

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].file_name, "untitled_document.docx")
        panel.close()

    def test_naming_dialog_initialization_and_preselect(self):
        with patch.object(FilenameSuggestionDialog, "_start_generation"):
            dialog = FilenameSuggestionDialog(target_item=self.item)
            self.assertEqual(dialog.title, "untitled_document.docx")
            self.assertEqual(dialog.extension, ".docx")
            self.assertEqual(dialog.target_input.text(), "untitled_document.docx")

            # Simulate suggestions arrived
            mock_names = ["ke_hoach_2026.docx", "kinh_doanh_2026.docx"]
            dialog._on_suggestions_ready(mock_names)
            app.processEvents()

            self.assertEqual(dialog.suggestion_list.count(), 2)
            self.assertEqual(dialog.target_input.text(), "ke_hoach_2026.docx")

            # Click second item
            second_item = dialog.suggestion_list.item(1)
            dialog._on_item_clicked(second_item)
            self.assertEqual(dialog.target_input.text(), "kinh_doanh_2026.docx")

            dialog.close()

    def test_naming_dialog_copy_to_clipboard(self):
        with patch.object(FilenameSuggestionDialog, "_start_generation"):
            dialog = FilenameSuggestionDialog(target_item=self.item)
            dialog.target_input.setText("custom_picked_name.docx")
            dialog._copy_chosen_name()
            app.processEvents()

            clipboard_text = QApplication.clipboard().text()
            self.assertEqual(clipboard_text, "custom_picked_name.docx")
            dialog.close()

    def test_naming_dialog_apply_rename(self):
        with patch.object(FilenameSuggestionDialog, "_start_generation"):
            dialog = FilenameSuggestionDialog(target_item=self.item)
            dialog.target_input.setText("ke_hoach_kinh_doanh_2026.docx")

            renamed_events = []
            dialog.file_renamed.connect(lambda old, new: renamed_events.append((old, new)))

            dialog._apply_rename()
            app.processEvents()

            expected_new_path = os.path.join(self.temp_dir.name, "ke_hoach_kinh_doanh_2026.docx")
            self.assertTrue(os.path.exists(expected_new_path))
            self.assertFalse(os.path.exists(self.test_file_path))

            self.assertEqual(len(renamed_events), 1)
            self.assertEqual(renamed_events[0][0], self.test_file_path)
            self.assertEqual(renamed_events[0][1], expected_new_path)
            self.assertEqual(self.item.file_name, "ke_hoach_kinh_doanh_2026.docx")
            self.assertEqual(self.item.file_path, expected_new_path)

            dialog.close()

    def test_naming_worker_execution(self):
        worker = NamingWorker(
            title="Tài liệu",
            excerpt="Nội dung bài viết",
            extension=".docx",
            instructions="",
            existing_filenames=[],
        )

        results = []
        worker.results_ready.connect(lambda names: results.append(names))

        worker.run()  # Run synchronously in test
        self.assertEqual(len(results), 1)
        self.assertTrue(len(results[0]) > 0)
        self.assertTrue(all(name.endswith(".docx") for name in results[0]))


if __name__ == "__main__":
    unittest.main()
