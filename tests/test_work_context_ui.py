"""Real Qt controls with fixture decisions, not measured assistant quality."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from unittest.mock import patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLabel
from rat.engine.assistant_runtime import AgentResponse, AgentStep
from rat.ui.omnibar import OmnibarWindow


@pytest.fixture(scope='module')
def app():
    instance = QApplication.instance() or QApplication([])
    instance.setProperty('ratReduceMotion', True)
    yield instance
    instance.setProperty('ratReduceMotion', False)


@pytest.fixture
def window(app):
    with patch('rat.ui.omnibar.Database') as db, patch('rat.ui.omnibar.SearchEngine'), \
            patch('rat.ui.feedback.FeedbackLog'), patch('rat.ui.assistant_worker.AssistantWorker.start'):
        db.return_value.get_stats.return_value = {'total_files': 0}
        db.return_value.get_recent_documents.return_value = []
        obj = OmnibarWindow()
        obj.show()
        QTest.qWait(30)
        yield obj
        obj.shutdown()
        obj.close()
        obj.deleteLater()
        app.processEvents()


def create_chart(window):
    pytest.importorskip('swisseph')
    result = window.assistant_runtime.dispatcher.execute_operation('create_natal_chart', {
        'date': '2000-06-15', 'time': '09:30', 'place': 'Hồ Chí Minh', 'latitude': 10.8231,
        'longitude': 106.6297, 'timezone': 'Asia/Ho_Chi_Minh'})
    assert result.status == 'success', result.error
    window._on_artifact_result(window._chat_generation, result)
    QTest.qWait(30)
    return result.artifact


def test_companion_is_present_and_opens_notes_without_mocking_or_submitting(window):
    avatar = window.companion_avatar_btn
    assert avatar.isVisible()
    for _ in range(3):
        QTest.mouseClick(avatar, Qt.MouseButton.LeftButton)
    assert window.notebook_pane.opened
    assert avatar.current_state != 'angry'
    assert window._pending_chat_query is None
    assert window.chat_composer_input.text() == ''


def test_live_companion_motion_keeps_editor_stable_and_sleeps_when_hidden(window, monkeypatch):
    monkeypatch.setattr('rat.ui.live_companion.motion_enabled', lambda: True)
    pet = window.companion_avatar_btn
    pet._sync_timer()
    assert pet.timer.isActive()
    assert pet.parent() is window.container.parent()
    assert pet.geometry().right() < window.container.geometry().left()
    window.chat_composer_input.setText('Bản nháp đang gõ')
    window.chat_composer_input.setFocus()
    QTest.qWait(40)
    geometry = window.chat_composer_input.geometry()
    with patch.object(window.assistant_runtime.dispatcher, 'execute_operation') as execute:
        pet.react('happy')
        QTest.qWait(160)
        assert window.chat_composer_input.geometry() == geometry
        assert window.chat_composer_input.text() == 'Bản nháp đang gõ'
        assert QApplication.focusWidget() is window.chat_composer_input
        execute.assert_not_called()
    window.hide()
    assert not pet.timer.isActive()
    window.show()
    QTest.qWait(20)
    assert pet.timer.isActive()


def test_reduced_motion_keeps_live_character_and_emote_without_animation(window, monkeypatch):
    monkeypatch.setattr('rat.ui.live_companion.motion_enabled', lambda: False)
    pet = window.companion_avatar_btn
    pet.set_state('waiting')
    pet.react('happy')
    assert pet.isVisible() and not pet.timer.isActive()
    assert pet.current_state == 'waiting' and 'dữ kiện' in pet.toolTip()
    assert pet.pose()['reaction'] == 'happy' and not pet.pose()['moving']


def test_note_edit_draft_and_focus_survive_modes_and_apply_reaches_model_context(window):
    note = window.assistant_runtime.notebook.add_user_note('Rảnh sau 3 giờ')
    pane = window.notebook_pane
    pane.refresh()
    pane.set_open(True, animate=False)
    row = pane.rows[note['id']]
    row._edit()
    row.editor.setPlainText('Rảnh sau 4 giờ')
    row.editor.setFocus()
    for mode in (True, False):
        window.set_expanded(mode)
        QTest.qWait(20)
        assert pane.rows[note['id']] is row
        assert row.editor.toPlainText() == 'Rảnh sau 4 giờ'
        assert QApplication.focusWidget() is row.editor
    row.apply.click()
    assert window.assistant_runtime.notebook.model_context()[0]['text'] == 'Rảnh sau 4 giờ'
    assert not row.editing
    row.delete.click()
    assert window.assistant_runtime.notebook.snapshot() == []


def test_mode_shortcut_from_note_editor_preserves_draft_and_focus(window):
    note = window.assistant_runtime.notebook.add_user_note('Ví dụ: có 20 phút')
    pane = window.notebook_pane
    pane.refresh()
    pane.set_open(True, animate=False)
    row = pane.rows[note['id']]
    row._edit()
    row.editor.setPlainText('Ví dụ: có 30 phút')
    window.activateWindow()
    row.editor.setFocus()
    QTest.qWait(20)
    for expected in (True, False):
        QTest.keyClick(row.editor, Qt.Key.Key_L, Qt.KeyboardModifier.MetaModifier)
        QTest.qWait(20)
        assert window.is_expanded is expected
        assert row.editor.toPlainText() == 'Ví dụ: có 30 phút'
        assert QApplication.focusWidget() is row.editor


def test_trace_follows_real_steps_and_never_renders_raw_private_fields(window):
    window._submit_chat_prompt('Tính 3*7')
    handle = window._assistant_handle
    step = AgentStep(1, 'PRIVATE THOUGHT', 'calculate', {'expression': '3*7'},
        {'expression': '3*7', 'result': '21'}, raw_completion='PRIVATE COMPLETION')
    window._on_assistant_step(handle, step)
    trace = handle['work_trace']
    trace.set_open(True, animate=False)
    text = '\n'.join(label.text() for label in trace.findChildren(QLabel))
    assert '3*7 = 21' in text and 'PRIVATE' not in text
    window._on_assistant_response(handle, AgentResponse('21', [step], 5, 1, 0))
    assert len(trace.entries) == 1
    assert trace.status == 'Đã trả lời'
    assert window.companion_avatar_btn.current_state == 'done'


def test_valid_controls_become_notes_and_failure_keeps_notes_and_result(window):
    chart = create_chart(window)
    result = window.assistant_runtime.dispatcher.execute_operation('update_birth_data', {
        'artifact_id': chart.id, 'revision': chart.revision, 'time': '10:00'})
    window._on_artifact_result(window._chat_generation, result,
        note_inputs=(chart.id, {'time': 'Giờ sinh'}, {'time': '10:00'}))
    notes = window.assistant_runtime.notebook.snapshot()
    assert notes[0]['text'] == 'Giờ sinh: 10:00' and notes[0]['confirmed']
    failed = window.assistant_runtime.dispatcher.execute_operation('update_birth_data', {
        'artifact_id': chart.id, 'revision': result.artifact.revision, 'time': '25:99'})
    assert failed.status == 'error'
    window._on_artifact_result(window._chat_generation, failed,
        note_inputs=(chart.id, {'time': 'Giờ sinh'}, {'time': '25:99'}))
    assert window.assistant_runtime.notebook.snapshot() == notes
    assert window.assistant_runtime.artifact_store.get(chart.id).inputs['time'] == '10:00'
    trace = window._latest_assistant_handle['work_trace']
    assert list(trace.entries.values())[-1].status == 'error'


def test_followup_moves_same_result_widget_and_model_can_clear_visible_results(window):
    chart = create_chart(window)
    previous = window._latest_assistant_handle
    host = previous['sources_widget']
    renderer = host.artifact_panel.renderers[chart.id]
    canvas = renderer._wheel_widget
    canvas.select('moon')
    window._submit_chat_prompt('Giải thích Mặt Trăng trên lá số này')
    current = window._assistant_handle
    assert current['sources_widget'] is host
    assert host.artifact_panel.renderers[chart.id] is renderer
    assert renderer._wheel_widget is canvas and canvas.selected == 'moon'
    cleared = window.assistant_runtime.execute_tool('select_work_results', {'artifact_ids': []})
    window._on_assistant_step(current, AgentStep(1, '', 'select_work_results', tool_result=cleared))
    assert current['artifacts'] == {}
    assert 'sources_widget' not in current
    assert window.assistant_runtime.artifact_store.get(chart.id) is not None


def test_reset_clears_notes_and_rejects_late_steps(window):
    window.assistant_runtime.notebook.add_user_note('Chỉ ôn TCP')
    window._submit_chat_prompt('Tìm tài liệu')
    old = window._assistant_handle
    window._reset_chat()
    window._on_assistant_step(old, AgentStep(1, '', 'read_document', tool_result={'filename': 'old.txt'}))
    assert window.assistant_runtime.notebook.snapshot() == []
    assert window.chat_stream.is_empty()
    assert window.companion_avatar_btn.current_state == 'idle'
