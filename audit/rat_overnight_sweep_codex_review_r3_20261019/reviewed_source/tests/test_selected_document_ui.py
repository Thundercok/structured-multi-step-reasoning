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


def test_native_document_qa_streaming_and_late_chunk_discarded(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv('RAT_REDUCE_MOTION', '1')
    with patch('rat.ui.omnibar.Database') as database, patch('rat.ui.omnibar.SearchEngine'), \
         patch('rat.ui.feedback.FeedbackLog'), patch('rat.ui.assistant_worker.AssistantWorker.start'):
        database.return_value.get_stats.return_value = {'total_files': 0}
        database.return_value.get_recent_documents.return_value = []
        item = SearchResultItem(str(tmp_path / 'doc.txt'), 'doc.txt', '.txt', 10, 1, 1, '', '')
        window = OmnibarWindow()
        window.show()
        app.processEvents()
        try:
            window._select_document_question(item)
            window._submit_chat_prompt('Tìm mã sinh viên')
            handle = window._assistant_handle
            worker = window._current_reasoner
            assert handle is not None
            assert worker is not None

            # Stream first chunk
            worker.text_streamed.emit('Mã sinh viên là ')
            app.processEvents()
            assert 'Mã sinh viên là ' in handle['ans_lbl'].text()

            # Stream second chunk
            worker.text_streamed.emit('20261017.')
            app.processEvents()
            assert 'Mã sinh viên là 20261017.' in handle['ans_lbl'].text()

            # User cancels assistant
            window._cancel_assistant()
            app.processEvents()
            assert 'Đã dừng' in handle['ans_lbl'].text()
            assert window._assistant_handle is None

            # Late chunk arrives after cancel -> must be cleanly ignored
            worker.text_streamed.emit(' LATE CHUNK SHOULD BE DISCARDED')
            app.processEvents()
            assert 'LATE CHUNK SHOULD BE DISCARDED' not in handle['ans_lbl'].text()
            assert 'Đã dừng' in handle['ans_lbl'].text()
        finally:
            window.shutdown()
            window.close()
            window.deleteLater()
            app.processEvents()


def test_invalid_native_model_path_reports_error_without_ollama_fallback(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv('RAT_REDUCE_MOTION', '1')
    invalid_path = str(tmp_path / 'missing_model_dir')
    monkeypatch.setattr('rat.config.config.document_model_path', invalid_path)

    with patch('rat.ui.omnibar.Database') as database, patch('rat.ui.omnibar.SearchEngine'), \
         patch('rat.ui.feedback.FeedbackLog'), patch('rat.ui.assistant_worker.AssistantWorker.start'):
        database.return_value.get_stats.return_value = {'total_files': 0}
        database.return_value.get_recent_documents.return_value = []

        window = OmnibarWindow()
        window.show()
        app.processEvents()
        try:
            from rat.ui.assistant_worker import ErrorDocumentModel
            assert isinstance(window.assistant_runtime.document_model_client, ErrorDocumentModel)
            assert window._document_model_init_error is not None

            # Window and search still work normally
            window.search_input.setText('test')
            app.processEvents()

            # Ask question on a document
            item = SearchResultItem(str(tmp_path / 'file.txt'), 'file.txt', '.txt', 10, 1, 1, '', '')
            window._select_document_question(item)
            window._submit_chat_prompt('Nội dung là gì?')

            handle = window._assistant_handle
            assert handle is not None

            # Simulate worker response with the native init error
            from rat.engine.assistant_runtime import AgentResponse
            err_resp = AgentResponse(
                answer='', steps=[], total_time_ms=50, tool_call_count=1,
                token_estimate=0, error='native_model_requires_complete_local_directory',
            )
            window._on_assistant_response(handle, err_resp)
            app.processEvents()

            # Error must mention local model, NOT Ollama!
            final_text = handle['full_text']
            assert 'Mô hình MLX cục bộ không hợp lệ' in final_text
            assert 'Ollama' not in final_text
        finally:
            window.shutdown()
            window.close()
            window.deleteLater()
            app.processEvents()


def test_preload_document_model_nonblocking_and_queued_signal(tmp_path, monkeypatch):
    from concurrent.futures import Future
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv('RAT_REDUCE_MOTION', '1')
    fake_path = str(tmp_path / 'fake_model')
    monkeypatch.setattr('rat.config.config.document_model_path', fake_path)
    monkeypatch.setattr('rat.config.config.document_model_preload', True)

    future = Future()
    mock_client = patch('rat.engine.document_model_service.ResidentDocumentModel').start()
    mock_client.return_value.preload.return_value = future
    mock_client.return_value.supports_document_callbacks = True

    with patch('rat.ui.omnibar.Database') as database, patch('rat.ui.omnibar.SearchEngine'), \
         patch('rat.ui.feedback.FeedbackLog'):
        database.return_value.get_stats.return_value = {'total_files': 0}
        database.return_value.get_recent_documents.return_value = []

        window = OmnibarWindow()
        window.show()
        app.processEvents()
        try:
            # During preload, window is shown and interactive
            assert window._document_model_status == 'preparing'
            assert window.chat_composer_input.isEnabled()

            # Complete preload future
            future.set_result(True)
            app.processEvents()

            # Queued signal arrived and marked status ready
            assert window._document_model_status == 'ready'
        finally:
            patch.stopall()
            window.shutdown()
            window.close()
            window.deleteLater()
            app.processEvents()


def test_cancel_and_ask_another_question_on_different_file(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv('RAT_REDUCE_MOTION', '1')
    with patch('rat.ui.omnibar.Database') as database, patch('rat.ui.omnibar.SearchEngine'), \
         patch('rat.ui.feedback.FeedbackLog'), patch('rat.ui.assistant_worker.AssistantWorker.start'):
        database.return_value.get_stats.return_value = {'total_files': 0}
        database.return_value.get_recent_documents.return_value = []
        file1 = SearchResultItem(str(tmp_path / 'file1.txt'), 'file1.txt', '.txt', 10, 1, 1, '', '')
        file2 = SearchResultItem(str(tmp_path / 'file2.txt'), 'file2.txt', '.txt', 10, 1, 1, '', '')

        window = OmnibarWindow()
        window.show()
        app.processEvents()
        try:
            # First file question
            window._select_document_question(file1)
            window._submit_chat_prompt('Câu hỏi 1')
            assert window._current_reasoner.document_path == file1.file_path

            # Cancel
            window._cancel_assistant()
            assert window._current_reasoner is None

            # Second file question
            window._select_document_question(file2)
            window._submit_chat_prompt('Câu hỏi 2')
            assert window._current_reasoner.document_path == file2.file_path
        finally:
            window.shutdown()
            window.close()
            window.deleteLater()
            app.processEvents()


def test_shutdown_during_active_qa_waits_for_cleanup_handshake(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv('RAT_REDUCE_MOTION', '1')
    with patch('rat.ui.omnibar.Database') as database, patch('rat.ui.omnibar.SearchEngine'), \
         patch('rat.ui.feedback.FeedbackLog'), patch('rat.ui.assistant_worker.AssistantWorker.start'):
        database.return_value.get_stats.return_value = {'total_files': 0}
        database.return_value.get_recent_documents.return_value = []

        window = OmnibarWindow()
        window.show()
        app.processEvents()
        try:
            item = SearchResultItem(str(tmp_path / 'doc.txt'), 'doc.txt', '.txt', 10, 1, 1, '', '')
            window._select_document_question(item)
            window._submit_chat_prompt('Hỏi điều gì đó')

            # While worker is active, shutdown cleanly
            window.shutdown()
            assert window._shutting_down is True
            assert len(window._reasoning_workers) == 0
        finally:
            window.close()
            window.deleteLater()
            app.processEvents()
