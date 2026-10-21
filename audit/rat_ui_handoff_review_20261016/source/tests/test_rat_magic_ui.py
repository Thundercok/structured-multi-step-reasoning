"""Real Qt and temporary local files; these tests do not assess model ability."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from unittest.mock import patch

import pytest
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLineEdit, QPushButton

from rat.engine.assistant_runtime import AgentResponse
from rat.kernel.contracts import Artifact
from rat.kernel.registry import CapabilityRegistry
from rat.ui.assistant_presenter import source_panel
from rat.ui.chat_stream import InlineFileCard
from rat.ui.omnibar import OmnibarWindow


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, monkeypatch):
    monkeypatch.delenv('RAT_DEBUG_UI', raising=False)
    monkeypatch.setenv('RAT_REDUCE_MOTION', '1')
    with patch('rat.ui.omnibar.Database') as database, patch('rat.ui.omnibar.SearchEngine'), \
         patch('rat.ui.feedback.FeedbackLog'), patch('rat.ui.assistant_worker.AssistantWorker.start'), \
         patch('rat.engine.slm.slm_engine.is_service_running', return_value=False):
        database.return_value.get_stats.return_value = {'total_files': 0}
        database.return_value.get_recent_documents.return_value = []
        obj = OmnibarWindow()
        obj.show()
        obj.activateWindow()
        app.processEvents()
        yield obj
        obj.shutdown()
        obj.close()
        obj.deleteLater()
        app.processEvents()


def file_artifact(path, kind='document_file', **payload):
    return Artifact('file-' + kind, kind, payload={'path': str(path), 'filename': path.name, **payload})


def test_bottom_composer_preserves_editor_and_anchor_across_content_and_modes(window, app):
    composer = window.chat_composer_input
    window._deliver_assistant_reply('Kết quả có thể hỏi tiếp. ' * 35)
    app.processEvents()
    composer.setText('Bản nháp tiếng Việt đang sửa')
    composer.setSelection(4, 8)
    composer.setFocus()
    app.processEvents()
    selection = composer.selectedText()
    bottom = window.geometry().bottom()
    for mode in (True, False):
        window.set_expanded(mode)
        app.processEvents()
        assert window.chat_composer_input is composer is window.full_chat_input
        assert composer.selectedText() == selection
        assert QApplication.focusWidget() is composer
        assert window.geometry().bottom() == bottom
        assert window.main_layout.indexOf(window.workbench_dialogue) > window.main_layout.indexOf(window.workbench_canvas)
        assert window.workbench_dialogue.geometry().top() >= window.workbench_canvas.geometry().bottom()
        assert window.companion_avatar_btn.geometry().right() <= window.workbench_dialogue.user_lane.geometry().left()


def test_default_controls_stay_hidden_across_progress_and_mode_refresh(window, app):
    assert window.assistant_runtime.plan_tasks is False
    assert window.assistant_runtime.discover_tools is True
    assert window.assistant_runtime.structured_context is False
    for mode in (False, True, False):
        window.set_expanded(mode)
        window._sync_compact_surface()
        app.processEvents()
        assert all(widget.isHidden() for widget in (
            window.chat_composer_send, window.btn_expand, window.btn_surface_menu,
            window.quick_suggestions, window.section_bar, window.action_footer,
        ))
    window._submit_chat_prompt('Một việc đang chạy')
    handle = window._assistant_handle
    window._on_assistant_progress(handle, 'Đang đọc nguồn đã chọn…')
    assert handle['status_lbl'].text() == 'Đang đọc nguồn đã chọn…'
    assert handle['work_trace'].isHidden()
    assert window.chat_composer_send.isHidden()


@pytest.mark.parametrize('control', ['dừng', 'stop', 'escape'])
def test_stop_is_available_without_buttons_and_late_response_cannot_replace_result(window, control):
    window._submit_chat_prompt('Đọc tài liệu')
    old = window._assistant_handle
    window.chat_composer_input.setText('Bản nháp giữ lại')
    if control == 'escape':
        QTest.keyClick(window.chat_composer_input, Qt.Key.Key_Escape)
    else:
        window._submit_chat_prompt(control)
    assert window._pending_chat_query is None
    assert window.chat_composer_input.text() == 'Bản nháp giữ lại'
    assert 'Đã dừng' in old['ans_lbl'].text()
    window._on_assistant_response(old, AgentResponse('Kết quả muộn', [], 0, 0, 0))
    assert 'Kết quả muộn' not in old['ans_lbl'].text()


@pytest.mark.parametrize('kind', ['document_search', 'document_content', 'book_page_search', 'book_page_content', 'file_export', 'document_file'])
def test_observed_local_file_is_delivered_without_autoopening_or_button_strip(app, monkeypatch, tmp_path, kind):
    monkeypatch.delenv('RAT_DEBUG_UI', raising=False)
    path = tmp_path / 'Tài liệu <thật>.pdf'
    path.write_bytes(b'%PDF-1.4\nactual local test file\n')
    artifact = file_artifact(path)  # File presentation consumes observed paths, not the filename prose.
    artifact.kind = kind
    artifact.id = 'observed-' + kind
    if kind == 'document_search':
        artifact.payload = {'items': [{'path': str(path), 'filename': path.name}]}
    elif kind == 'file_export':
        artifact.payload = {'exported_path': str(path), 'filename': path.name}
    with patch('rat.ui.chat_stream.open_file_default') as opened:
        panel = source_panel([], artifacts=[artifact], registry=CapabilityRegistry())
        panel.show()
        app.processEvents()
        row = panel.findChild(InlineFileCard)
        assert row is not None and row.item.file_path == str(path)
        assert row.item.file_size == path.stat().st_size
        assert row.name_label.full_text == path.name
        assert row.name_label.textFormat() == Qt.TextFormat.PlainText
        assert not any(button.isVisible() for button in row.findChildren(QPushButton))
        opened.assert_not_called()
        row.setFocus()
        QTest.keyClick(row, Qt.Key.Key_Return)
        opened.assert_called_once_with(str(path))
        QTest.mouseClick(row.name_label, Qt.MouseButton.LeftButton)
        assert opened.call_count == 2
        opened.assert_called_with(str(path))
        panel.close()
        panel.deleteLater()
        app.processEvents()


def test_file_attachment_deduplicates_search_read_and_survives_modes(window, app, tmp_path):
    path = tmp_path / 'book.pdf'
    path.write_bytes(b'%PDF-1.4\nlocal fixture\n')
    found = Artifact('found', 'document_search', payload={'items': [{'path': str(path)}]})
    read = file_artifact(path)
    panel = source_panel([], artifacts=[found], registry=CapabilityRegistry())
    handle = window.chat_stream.create_streaming_message()
    window.chat_stream.update_source_cards(handle, custom_widget=panel)
    row = panel.findChild(InlineFileCard)
    panel.update_artifacts([found, read])
    assert panel.findChildren(InlineFileCard) == [row]
    for mode in (True, False):
        window.set_expanded(mode)
        app.processEvents()
        assert panel.findChildren(InlineFileCard) == [row]


def test_missing_observed_file_is_honest_and_plain_prose_never_becomes_attachment(app, monkeypatch, tmp_path):
    monkeypatch.delenv('RAT_DEBUG_UI', raising=False)
    path = tmp_path / 'missing.pdf'
    panel = source_panel([], artifacts=[file_artifact(path)], registry=CapabilityRegistry())
    row = panel.findChild(InlineFileCard)
    assert 'không còn' in row.detail_label.full_text
    with patch('rat.ui.chat_stream.open_file_default') as opened:
        QTest.keyClick(row, Qt.Key.Key_Return)
        opened.assert_not_called()
    invented = Artifact('prose', 'sample', payload={'text': f'Đã tạo {path}'})
    prose_panel = source_panel([], artifacts=[invented], registry=CapabilityRegistry())
    assert not prose_panel.findChildren(InlineFileCard)
    panel.close()
    prose_panel.close()
    panel.deleteLater()
    prose_panel.deleteLater()
    app.processEvents()


def test_pending_question_is_visible_without_backend_form(window):
    window._submit_chat_prompt('Lập lá số')
    pending = window.assistant_runtime.dispatcher.execute_operation('create_natal_chart', {})
    response = AgentResponse('Bạn sinh ngày nào, khoảng mấy giờ và ở đâu?', [], 0, 1, 0,
                             pending_input_request=pending.input_request, artifacts=[pending.artifact])
    handle = window._assistant_handle
    window._on_assistant_response(handle, response)
    assert handle['ans_lbl'].text() == response.answer
    assert not handle['card'].findChildren(QLineEdit)
    assert not any(button.isVisible() for button in handle['card'].findChildren(QPushButton))


def test_fresh_empty_workbench_and_reset_have_no_duration_or_plan_metadata(window, app):
    canvas = window.workbench_canvas
    assert not canvas.duration_badge.isVisible()
    assert canvas.duration_badge.text() == ""
    assert not canvas.eyebrow_lbl.isVisible()
    assert canvas.eyebrow_lbl.text() == ""
    assert not canvas.status_lbl.isVisible()
    assert not canvas.context_lbl.isVisible()
    assert not canvas.foot_row.isVisible()
    assert canvas.minutes == []

    # Verify reset also stays clean of synthetic metadata
    window._reset_chat()
    app.processEvents()
    assert not canvas.duration_badge.isVisible()
    assert canvas.duration_badge.text() == ""
    assert not canvas.eyebrow_lbl.isVisible()
    assert not canvas.status_lbl.isVisible()
    assert not canvas.context_lbl.isVisible()
    assert not canvas.foot_row.isVisible()


def test_footer_hints_have_usable_positive_bounds_across_states(window, app):
    lane = window.workbench_user_lane
    window.show()
    app.processEvents()

    # 1. Desktop compact state
    assert lane.input_state_lbl.isVisible()
    assert lane.input_state_lbl.width() > 40
    assert lane.kbd_hint_lbl.isVisible()
    assert lane.kbd_hint_lbl.width() > 20

    # 2. Busy / working state
    lane.set_phase("working")
    app.processEvents()
    assert lane.input_state_lbl.text() == "Gõ tiếp · Esc để dừng"
    assert lane.input_state_lbl.width() > 60

    # 3. 1700+ character counter state
    long_text = "a" * 1750
    window.chat_composer_input.setText(long_text)
    app.processEvents()
    assert "1.750" in lane.input_state_lbl.text() or "1750" in lane.input_state_lbl.text()
    assert lane.input_state_lbl.width() > 60
    window.chat_composer_input.clear()
    lane.set_phase("done")
    app.processEvents()

    # 4. Narrow mode: kbd hint hidden, input state label has usable positive width
    window._resize_overlay(440, 360)
    app.processEvents()
    assert lane.is_narrow
    assert lane.kbd_hint_lbl.isHidden()
    assert lane.input_state_lbl.isVisible()
    assert lane.input_state_lbl.width() > 40


def test_responsive_breakpoint_uses_content_width_on_constrained_screens(window, app):
    from unittest.mock import MagicMock
    mock_screen = MagicMock()
    mock_screen.availableGeometry.return_value = QRect(0, 0, 490, 800)
    window.screen = MagicMock(return_value=mock_screen)

    # Calling resize with standard 620 produces outer 466 (490 - 24) and content 450 (466 - 16)
    window._resize_overlay(620, 240)
    app.processEvents()

    assert window.width() == 466
    assert window.workbench_dialogue.is_narrow is True
    assert window.workbench_canvas.is_narrow is True
    assert window.companion_avatar_btn.width() == 84
    assert window.companion_avatar_btn.actor_w == 80
    assert window.workbench_user_lane.kbd_hint_lbl.isHidden()

