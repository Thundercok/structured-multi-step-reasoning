"""Offscreen acceptance probes; no model, personal index, or OS app launch."""
import importlib.util
from pathlib import Path
import sys
from unittest.mock import Mock, patch

import pytest
from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('milestone_review_base', ROOT / 'tests/test_workbench_scene.py')
base = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = base
spec.loader.exec_module(base)
app, scene_window = base.app, base.scene_window

from rat.engine.assistant_runtime import AssistantRuntime
from rat.engine.progressive_search import SearchHit, SearchSnapshot
from rat.engine.selected_document_qa import answer_selected_document
from rat.engine.app_resolver import ApplicationCatalog
from rat.timetable.compositor import TimetableCompositor
from test_review_probes import make_app, index, dispatcher
from rat.crawler.db import Database


def test_app_disambiguation_replaces_prior_qa_trace(scene_window, tmp_path):
    win = scene_window
    db = Database(str(tmp_path / 'index.db'))
    selected = tmp_path / 'selected.txt'
    index(db, selected, content='Verification code LOTUS-7319.')
    client = Mock()
    client.chat_with_meta.return_value = dict(message={'content': 'LOTUS-7319'},
        done_reason='stop', prompt_tokens=20, completion_tokens=4, error=None)
    runtime = AssistantRuntime(db=db, compositor=TimetableCompositor([]), use_live_model=True)
    previous_runtime = win.assistant_runtime
    win.assistant_runtime = runtime
    try:
        win._submit_chat_prompt('What code?', selected_document_path=str(selected))
        handle = win._assistant_handle
        answer = answer_selected_document(runtime, 'What code?', str(selected), model_client=client,
            turn_ref=handle['turn_ref'], execution_id=handle['execution_id'])
        assert answer.error is None
        win._on_assistant_response(handle, answer)
        a = make_app(tmp_path / 'A', 'League of Legends')
        b = make_app(tmp_path / 'B', 'League of Legends')
        catalog = ApplicationCatalog.scan([a.parent, b.parent])
        win._finder_catalog = catalog
        win._app_launcher = lambda _: pytest.fail('Ambiguous request cannot launch')
        # Exercise the actual Omnibar submit/direct-action delivery path, with the
        # worker start patched so the dispatch result is delivered synchronously.
        with patch('rat.ui.assistant_worker.ArtifactWorker.start'):
            win._submit_chat_prompt('mở Liên Minh')
            worker = win._artifact_worker
            assert worker is not None
            result = worker.callback()
            win._on_artifact_result(win._chat_generation, result)
        assert result.status == 'needs_input'
        snapshot = win.workbench_scene.current_snapshot
        assert snapshot.phase == 'waiting'
        flow = snapshot.reasoning_flow
        assert any(e.status == 'waiting' and e.artifact_id == result.artifact.id for e in flow), [
            (e.status, e.title, e.evidence_ref) for e in flow]
    finally:
        win.assistant_runtime = previous_runtime
        db.get_connection().close()


class PaintCounter(QObject):
    def __init__(self):
        super().__init__()
        self.count = 0

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Paint:
            self.count += 1
        return False


def test_delivery_to_paint_metric_waits_for_a_paint_event(scene_window, tmp_path):
    win = scene_window
    selected = tmp_path / 'fixture.txt'
    selected.write_text('Synthetic file.')
    hit = SearchHit('file:fixture', 'file', selected.name, str(selected), 'lexical_index')
    snapshot = SearchSnapshot(1, 'fixture', 'lexical', (hit,), hit.resource_id, True, 1.0)
    win._finder_coordinator = None
    win.workbench_finder_enabled = True
    counter = PaintCounter()
    win.workbench_scene.installEventFilter(counter)
    win.setUpdatesEnabled(False)
    win.last_delivery_to_paint_ms = None
    try:
        win._on_finder_snapshot_delivered(snapshot)
        QApplication.processEvents()
        assert counter.count == 0
        assert win.last_delivery_to_paint_ms is None, (
            'Reported delivery-to-paint latency even though painting is disabled: '
            f'{win.last_delivery_to_paint_ms}')
    finally:
        win.setUpdatesEnabled(True)
        win.workbench_scene.removeEventFilter(counter)


def test_streaming_preserves_selection_on_existing_answer_prefix(scene_window):
    scene = scene_window.workbench_scene
    scene.begin_turn('Synthetic QA', generation=1, execution_id='stream-1')
    assert scene.on_text_streamed('Source-backed answer', generation=1, execution_id='stream-1')
    label = scene.result_card.answer_lbl
    label.setSelection(0, 6)
    assert label.selectedText() == 'Source'
    assert scene.on_text_streamed(' continues.', generation=1, execution_id='stream-1')
    assert label.selectedText() == 'Source'
