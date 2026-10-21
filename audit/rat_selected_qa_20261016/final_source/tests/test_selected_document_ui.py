"""Explicit file selection reaches the single-call worker; Qt fixture only."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from unittest.mock import patch

from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from rat.engine.reranker import SearchResultItem
from rat.ui.compact_results import CompactFileRow
from rat.ui.omnibar import OmnibarWindow

_app_instance = None


def test_ask_file_uses_same_composer_and_selection_is_consumed_once(tmp_path, monkeypatch):
    global _app_instance
    app = QApplication.instance() or QApplication([])
    _app_instance = app
    monkeypatch.setenv('RAT_REDUCE_MOTION', '1')
    with patch('rat.ui.omnibar.Database') as database, patch('rat.ui.omnibar.SearchEngine'), \
         patch('rat.ui.feedback.FeedbackLog'), patch('rat.ui.assistant_worker.AssistantWorker.start'), \
         patch('rat.engine.slm.slm_engine.is_service_running', return_value=False):
        database.return_value.get_stats.return_value = {'total_files': 0}
        database.return_value.get_recent_documents.return_value = []
        item = SearchResultItem(str(tmp_path / 'source.txt'), 'source.txt', '.txt', 10, 1, 1, '', '')
        row = CompactFileRow(item)
        window = OmnibarWindow()
        window.show()
        row.question_requested.connect(window._select_document_question)
        row.show()
        app.processEvents()
        try:
            composer = window.chat_composer_input
            QTest.mouseClick(row.btn_ask, Qt.MouseButton.LeftButton)
            assert window._selected_document_path == item.file_path
            assert 'source.txt' in composer.placeholderText()
            window._submit_chat_prompt('Mã xác nhận là gì?')
            assert window.chat_composer_input is composer
            assert window._current_reasoner.document_path == item.file_path
            assert window._assistant_handle['selected_document_path'] == item.file_path
            assert window._selected_document_path is None
            window._cancel_assistant()
            window._submit_chat_prompt('Một câu hỏi thông thường')
            assert window._current_reasoner.document_path is None
        finally:
            window.shutdown()
            window.close()
            row.close()
            window.deleteLater()
            row.deleteLater()
            app.processEvents()
