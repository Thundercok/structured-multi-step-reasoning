"""Actual Qt controls and update lifecycle; fixtures do not measure model quality."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from unittest.mock import patch

import pytest
from PyQt6.QtWidgets import QApplication, QLineEdit, QPushButton, QTableWidget

from rat.kernel import ArtifactStore, ActionDispatcher
from rat.kernel.capabilities import build_default_registry
from rat.kernel.view_spec import StandardViewProvider, ViewSpec, ViewBlock
from rat.ui.view_renderer import QtViewRenderer
from rat.ui.assistant_presenter import source_panel
from rat.ui.chat_stream import ChatStreamWidget


@pytest.fixture(autouse=True)
def developer_controls(monkeypatch):
    monkeypatch.setenv('RAT_DEBUG_UI', '1')


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def environment(app):
    registry = build_default_registry()
    dispatcher = ActionDispatcher(registry, ArtifactStore())
    return registry, dispatcher


def make_chart(dispatcher):
    pytest.importorskip('swisseph')
    result = dispatcher.execute_operation('create_natal_chart', dict(name='Ví dụ kiểm thử', date='2000-06-15',
        time='09:30', place='Hồ Chí Minh', latitude=10.8231, longitude=106.6297, timezone='Asia/Ho_Chi_Minh'))
    assert result.status == 'success', result.error
    return result.artifact


def test_time_edit_control_submits_the_edited_value(environment):
    registry, dispatcher = environment
    artifact = make_chart(dispatcher)
    renderer = QtViewRenderer(StandardViewProvider(registry).provide_view(artifact), artifact)
    captured = []
    renderer.action_dispatched.connect(lambda action, values: captured.append((action, values)))
    button = next(b for b in renderer.findChildren(QPushButton) if b.text() == 'Đổi giờ sinh')
    button.click()
    edit = renderer.findChild(QLineEdit, 'action-input-time')
    edit.setText('10:15')
    next(b for b in renderer.findChildren(QPushButton) if b.text() == 'Áp dụng').click()
    assert captured[0][1] == {'time': '10:15'}
    result = dispatcher.dispatch(*captured[0])
    assert result.artifact.id == artifact.id and result.artifact.revision == 2
    assert result.artifact.payload['chart']['birth']['time'] == '10:15'
    renderer.close()


def test_stream_update_keeps_the_live_input_and_draft(environment):
    registry, dispatcher = environment
    pending = dispatcher.execute_operation('create_natal_chart', {'date': '2000-06-15'}).artifact
    stream = ChatStreamWidget()
    handle = stream.create_streaming_message()
    first = source_panel([], artifacts=[pending], registry=registry)
    stream.update_source_cards(handle, custom_widget=first)
    edit = first.renderers[pending.id].findChild(QLineEdit, 'input-place')
    edit.setText('Đà Lạt')
    stream.update_source_cards(handle, custom_widget=source_panel([], artifacts=[pending], registry=registry))
    assert first.renderers[pending.id].findChild(QLineEdit, 'input-place') is edit
    assert edit.text() == 'Đà Lạt'
    stream.close()


def test_render_uses_observed_chart_and_preserves_all_details(environment):
    registry, dispatcher = environment
    artifact = make_chart(dispatcher)
    with patch('rat.astrology.chart.calculate_chart', side_effect=AssertionError('must not recalculate in UI')):
        renderer = QtViewRenderer(StandardViewProvider(registry).provide_view(artifact), artifact)
    assert renderer._wheel_widget is not None
    tables = renderer.findChildren(QTableWidget)
    assert tables[0].rowCount() == len(artifact.payload['chart']['positions'])
    assert tables[1].rowCount() == 12
    assert tables[2].rowCount() == len(artifact.payload['chart']['aspects'])
    renderer.close()


def test_rejected_provider_uses_real_standard_view_with_visible_reason(environment):
    registry, dispatcher = environment
    artifact = make_chart(dispatcher)
    class InvalidProvider:
        def provide_view(self, artifact, context=None):
            return ViewSpec(1, artifact.id, artifact.revision, blocks=[ViewBlock('actions', {'action_ids': ['export_fake']})])
    panel = source_panel([], artifacts=[artifact], registry=registry, view_provider=InvalidProvider())
    assert panel.renderers[artifact.id]._wheel_widget is not None
    assert 'unregistered_action_id' in panel.renderers[artifact.id].toolTip()
    assert dispatcher.store.get(artifact.id).revision == 1
    panel.close()


@pytest.mark.parametrize('format', ['png', 'pdf'])
def test_inline_export_worker_writes_selected_file_without_changing_chart(environment, tmp_path, format):
    import time
    from PyQt6.QtTest import QTest
    from rat.ui.assistant_worker import ArtifactWorker
    registry, dispatcher = environment
    artifact = make_chart(dispatcher)
    action = next(a for a in registry.actions_for(artifact) if a.params.get('format') == format)
    request = dispatcher.dispatch(action).input_request
    destination = tmp_path / ('la-so.' + format)
    results = []
    worker = ArtifactWorker(lambda: dispatcher.resume_input(request.id, {'output_path': str(destination)}))
    worker.result_ready.connect(results.append)
    worker.start()
    deadline = time.monotonic() + 15
    while (worker.isRunning() or not results) and time.monotonic() < deadline:
        QTest.qWait(10)
    assert worker.wait(1000)
    assert results and results[0].status == 'success', results[0].error if results else 'no callback'
    assert destination.read_bytes().startswith(b'\x89PNG' if format == 'png' else b'%PDF')
    assert dispatcher.store.get(artifact.id).to_dict() == artifact.to_dict()


def test_manual_coordinates_and_repeated_hour_controls_keep_typed_values(environment):
    from PyQt6.QtWidgets import QComboBox
    registry, dispatcher = environment
    with patch('rat.astrology.places.search_places', return_value=()):
        pending = dispatcher.execute_operation('create_natal_chart',
            {'date': '2023-11-05', 'time': '01:30', 'place': 'New York'}).artifact
    renderer = QtViewRenderer(StandardViewProvider(registry).provide_view(pending), pending)
    for name, value in {'latitude': '40.7128', 'longitude': '-74.006', 'timezone': 'America/New_York'}.items():
        renderer.input_fields[name].setText(value)
    values = renderer.draft_values()
    assert isinstance(values['latitude'], float) and isinstance(values['longitude'], float)
    fold = dispatcher.resume_input(pending.id, values)
    assert fold.status == 'needs_input'
    chooser = QtViewRenderer(StandardViewProvider(registry).provide_view(fold.artifact), fold.artifact)
    field = chooser.findChild(QComboBox, 'input-fold')
    field.setCurrentIndex(field.findData(1))
    result = dispatcher.resume_input(fold.input_request.id, chooser.draft_values())
    assert result.status == 'success', result.error
    assert result.artifact.payload['chart']['birth']['fold'] == 1
    renderer.close()
    chooser.close()
