"""Stateful UI regressions with fixtures, not a model-quality evaluation."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLineEdit, QPushButton

from rat.ui.omnibar import OmnibarWindow
from rat.ui.assistant_presenter import source_panel
from rat.ui.surface_layout import ChatComposer


@pytest.fixture(scope='module')
def app():
    instance = QApplication.instance() or QApplication([])
    instance.setProperty('ratReduceMotion', True)
    yield instance
    instance.setProperty('ratReduceMotion', False)


@pytest.fixture(autouse=True)
def debug_controls(monkeypatch):
    # These regressions exercise optional forms/actions and their draft state.
    # Default button-free interaction is covered by test_rat_magic_ui.py.
    monkeypatch.setenv('RAT_DEBUG_UI', '1')
    monkeypatch.setenv('RAT_WORKBENCH_SCENE', '0')
    monkeypatch.setenv('RAT_WORKBENCH_FINDER', '0')


@pytest.fixture
def window(app):
    with patch('rat.ui.omnibar.Database') as db, patch('rat.ui.omnibar.SearchEngine'), \
            patch('rat.ui.feedback.FeedbackLog'), patch('rat.ui.assistant_worker.AssistantWorker.start'):
        db.return_value.get_stats.return_value = {'total_files': 0}
        db.return_value.get_recent_documents.return_value = []
        obj = OmnibarWindow()
        obj.show()
        QTest.qWait(40)
        yield obj
        obj.shutdown()
        obj.close()
        obj.deleteLater()
        app.processEvents()


def chart(window):
    pytest.importorskip('swisseph')
    result = window.assistant_runtime.dispatcher.execute_operation('create_natal_chart',
        dict(date='2000-06-15', time='09:30', place='Hồ Chí Minh', latitude=10.8231,
             longitude=106.6297, timezone='Asia/Ho_Chi_Minh'))
    assert result.status == 'success', result.error
    window._on_artifact_result(window._chat_generation, result)
    QTest.qWait(40)
    return result.artifact


def panel(window):
    return window._latest_assistant_handle['sources_widget'].artifact_panel


def test_modes_share_the_editor_and_keep_selection_and_focus(window):
    editor = window.chat_composer_input
    editor.setText('Đổi giờ sinh thành 9:30\nVà giữ phần đang chọn')
    editor.setSelection(4, 12)
    editor.setFocus()
    before = (editor.text(), editor.selectedText(), editor.cursorPosition())
    for expanded in [True, False, True, False]:
        window.set_expanded(expanded)
        QTest.qWait(20)
        assert window.full_chat_input is editor
        assert len(window.findChildren(ChatComposer)) == 1
        assert (editor.text(), editor.selectedText(), editor.cursorPosition()) == before
        assert QApplication.focusWidget() is editor
        assert window.quick_bar.isVisible()
        assert window.section_bar.isHidden()


def test_pending_form_reflows_without_recreating_or_losing_draft(window):
    window.open_natal_chart()
    pending = window.assistant_runtime.dispatcher.state.pending_input_request
    renderer = panel(window).renderers[pending.id]
    field = renderer.findChild(QLineEdit, 'input-place')
    field.setText('Đà Lạt')
    field.setSelection(0, 2)
    field.setFocus()
    for expanded in [True, False]:
        window.set_expanded(expanded)
        QTest.qWait(30)
        assert panel(window).renderers[pending.id] is renderer
        assert field.text() == 'Đà Lạt' and field.selectedText() == 'Đà'
        assert field.isVisible()
        assert QApplication.focusWidget() is field


def test_chart_selection_and_revision_survive_mode_changes_without_execution(window):
    artifact = chart(window)
    renderer = panel(window).renderers[artifact.id]
    canvas = renderer._wheel_widget
    canvas.select('moon')
    with patch.object(window.assistant_runtime.dispatcher, 'execute_operation') as execute:
        for expanded in [True, False, True]:
            window.set_expanded(expanded)
            QTest.qWait(30)
            assert renderer._wheel_widget is canvas and canvas.selected == 'moon'
            assert canvas.isVisible()
        execute.assert_not_called()
    assert window.assistant_runtime.artifact_store.get(artifact.id).revision == artifact.revision


def test_revision_update_preserves_detail_selection_and_unsubmitted_edit(window):
    artifact = chart(window)
    first = panel(window).renderers[artifact.id]
    first._wheel_widget.select('sun')
    first.disclosures['Vị trí thiên thể'].set_open(True, animate=False)
    editor, fields = next(iter(first.action_editors.values()))
    editor.show()
    fields['time'].setText('11:20')
    fields['time'].setSelection(0, 2)
    fields['time'].setFocus()
    result = window.assistant_runtime.dispatcher.execute_operation('update_birth_data',
        dict(artifact_id=artifact.id, revision=artifact.revision, time='10:00'))
    assert result.status == 'success', result.error
    window._on_artifact_result(window._chat_generation, result)
    QTest.qWait(30)
    new = panel(window).renderers[artifact.id]
    assert new._wheel_widget.selected == 'sun'
    assert new.disclosures['Vị trí thiên thể'].opened
    _, new_fields = next(iter(new.action_editors.values()))
    assert new_fields['time'].text() == '11:20'
    assert new_fields['time'].selectedText() == '11'
    assert QApplication.focusWidget() is new_fields['time']


def test_shift_enter_is_newline_and_enter_submits_once_without_expanding(window):
    with patch('rat.ui.assistant_worker.AssistantWorker.start') as start:
        window.chat_composer_input.setText('Tìm tài liệu')
        QTest.keyClick(window.chat_composer_input, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
        assert '\n' in window.chat_composer_input.text()
        start.assert_not_called()
        QTest.keyClick(window.chat_composer_input, Qt.Key.Key_Return)
        assert start.call_count == 1
        assert not window.is_expanded
        assert window.chat_stream.isVisible()
        window.chat_composer_input.setText('Câu tiếp theo đang gõ')
        window.set_expanded(True)
        window.set_expanded(False)
        assert window.chat_composer_input.text() == 'Câu tiếp theo đang gõ'
        assert start.call_count == 1


def test_compact_only_changes_history_visibility_and_keeps_old_widgets(window):
    stream = window.chat_stream
    stream.add_user_message('Câu một')
    first = stream.create_streaming_message()
    stream.append_stream_token(first, 'Kết quả thứ nhất')
    stream.add_user_message('Câu hai')
    second = stream.create_streaming_message()
    stream.append_stream_token(second, 'Kết quả thứ hai')
    assert first['card'].isHidden() and second['card'].isVisible()
    window.set_expanded(True)
    assert first['card'].isVisible() and second['card'].isVisible()
    window.set_expanded(False)
    assert first['card'].isHidden()
    assert first['ans_lbl'].text() == 'Kết quả thứ nhất'


def test_streaming_does_not_pull_reader_back_to_bottom(window):
    window.set_expanded(True)
    stream = window.chat_stream
    handle = stream.create_streaming_message()
    stream.append_stream_token(handle, '\n\n'.join(['Một đoạn nội dung dài để đọc.'] * 80))
    QTest.qWait(30)
    bar = stream.verticalScrollBar()
    assert bar.maximum() > 0
    bar.setValue(0)
    assert not stream._follow_latest
    stream.append_stream_token(handle, '\nMột phần mới.')
    QTest.qWait(30)
    assert bar.value() == 0


def test_reopen_keeps_size_choice_and_unsent_draft(window):
    window.set_expanded(True)
    window.chat_composer_input.setText('Chưa gửi')
    window.hide()
    window.show_omnibar()
    assert window.is_expanded
    assert window.chat_composer_input.text() == 'Chưa gửi'


def test_secondary_action_menu_dispatches_the_actual_registered_action(window):
    artifact = chart(window)
    renderer = panel(window).renderers[artifact.id]
    actions = []
    renderer.action_dispatched.connect(lambda action, values: actions.append((action, values)))
    menus = [button.menu() for button in renderer.findChildren(QPushButton) if button.menu()]
    menus[0].actions()[0].trigger()
    assert actions and actions[0][0].operation_name == 'export_natal_chart'
    assert actions[0][1] == {}


def test_mode_change_keeps_the_composer_anchor_when_space_allows(window):
    chart(window)
    top = window.y() + window.chat_composer_input.mapTo(window, window.chat_composer_input.rect().topLeft()).y()
    window.set_expanded(True)
    QTest.qWait(30)
    assert window.y() + window.chat_composer_input.mapTo(window, window.chat_composer_input.rect().topLeft()).y() == top


def test_resized_chart_reserves_space_without_covering_actions(window):
    artifact = chart(window)
    renderer = panel(window).renderers[artifact.id]
    wheel = renderer._resources[0]
    for expanded in [False, True, False]:
        window.set_expanded(expanded)
        QTest.qWait(60)
        assert wheel.canvas.geometry().bottom() < wheel.detail.y()
        assert wheel.geometry().bottom() < renderer.disclosures['Vị trí thiên thể'].y()
        assert renderer.height() >= wheel.geometry().bottom()


def test_result_opens_at_start_instead_of_skipping_form_fields(window):
    window.open_natal_chart()
    QTest.qWait(60)
    handle = window._latest_assistant_handle
    assert window.chat_stream.verticalScrollBar().value() == handle['card'].y()
    pending = window.assistant_runtime.dispatcher.state.pending_input_request
    renderer = panel(window).renderers[pending.id]
    assert renderer.findChild(QLineEdit, 'input-date').isVisible()


def test_new_chat_keeps_user_size_choice_and_clears_task_state(window):
    chart(window)
    window.set_expanded(True)
    window.chat_composer_input.setText('Bản nháp cũ')
    window._reset_chat()
    assert window.is_expanded
    assert window.chat_stream.isVisible()
    assert window.chat_composer_input.text() == ''
    assert window.chat_stream.is_empty()
    assert window.assistant_runtime.artifact_store.list() == []


def test_settings_returns_to_same_conversation_draft_and_mode(window):
    window.set_expanded(True)
    window.chat_composer_input.setText('Bản nháp vẫn đang viết')
    with patch('rat.ui.settings_dialog.SettingsDialog') as dialog:
        window._open_settings()
        dialog.return_value.exec.assert_called_once()
    assert window.current_section_idx == 0
    assert window.is_expanded
    assert window.chat_composer_input.text() == 'Bản nháp vẫn đang viết'
    assert window.chat_composer_input.isVisible()


def test_detail_toggle_works_for_accessibility_state_actions(window):
    artifact = chart(window)
    detail = panel(window).renderers[artifact.id].disclosures['Vị trí thiên thể']
    detail.button.setChecked(True)
    assert detail.opened and detail.body.isVisible()
    detail.button.setChecked(False)
    assert not detail.opened and detail.body.isHidden()


def test_closing_with_queued_scroll_updates_does_not_touch_deleted_widgets(window):
    from PyQt6 import sip
    from PyQt6.QtCore import QCoreApplication, QEvent
    for _ in range(3):
        temporary = OmnibarWindow()
        temporary.show()
        handle = temporary.chat_stream.create_streaming_message()
        temporary.chat_stream.append_stream_token(handle, '\n\n'.join(['Đang cập nhật.'] * 40))
        temporary.chat_stream.restore_reading_position(0)
        temporary.shutdown()
        temporary.close()
        temporary.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QTest.qWait(20)
        assert sip.isdeleted(temporary)
