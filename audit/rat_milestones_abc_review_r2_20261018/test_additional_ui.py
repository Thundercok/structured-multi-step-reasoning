"""Round-two Qt offscreen probes; scripted QA, no actual app launch."""
from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('milestone_round2_base', ROOT / 'tests/test_workbench_scene.py')
base = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = base
spec.loader.exec_module(base)
app, scene_window = base.app, base.scene_window

from rat.crawler.db import Database
from rat.engine.app_resolver import ApplicationCatalog
from rat.engine.assistant_runtime import AssistantRuntime
from rat.engine.progressive_search import SearchHit, SearchSnapshot
from rat.engine.selected_document_qa import answer_selected_document
from rat.timetable.compositor import TimetableCompositor
from rat.ui.omnibar import OmnibarWindow
from test_additional_headless import index, make_app


def test_key_to_editor_measurement_is_not_overwritten_by_slot_duration():
    owner = SimpleNamespace(
        _last_key_press_t0=9.0, _artifact_worker=None, _pending_chat_query=None,
        chat_composer_send=Mock(), workbench_finder_enabled=False,
        chat_composer_input=SimpleNamespace(is_composing=lambda: False))
    # Deterministic clock: key at 9s, text change at 10s, zero slot work time.
    with patch('rat.ui.omnibar.time.perf_counter', return_value=10.0):
        OmnibarWindow._on_composer_text_changed(owner, 'DSA')
    assert owner.last_key_to_editor_ms == 1000.0


def test_first_hit_latency_is_not_overwritten_by_later_same_query_snapshot(scene_window, tmp_path):
    win = scene_window
    path = tmp_path / 'fixture.txt'
    path.write_text('Synthetic file.')
    hit = SearchHit('file:r2', 'file', path.name, str(path), 'lexical_index')
    snapshot = SearchSnapshot(17, 'fixture', 'lexical', (hit,), hit.resource_id, False, 2.0)
    win._finder_coordinator = None
    win._finder_query_submit_t0 = 99.0
    with patch('rat.ui.omnibar.time.perf_counter', return_value=100.0):
        win._on_finder_snapshot_delivered(snapshot)
    assert win.last_query_to_first_hit_ms == 1000.0
    win._on_finder_snapshot_delivered(replace(snapshot, phase='semantic', complete=True, elapsed_ms=7000.0))
    assert win.last_query_to_first_hit_ms == 1000.0


def test_empty_delivery_does_not_claim_a_first_hit_latency(scene_window):
    win = scene_window
    win._finder_coordinator = None
    win._finder_query_submit_t0 = 99.0
    win.last_query_to_first_hit_ms = None
    empty = SearchSnapshot(18, 'fixture', 'lexical', (), None, False, 2.0)
    with patch('rat.ui.omnibar.time.perf_counter', return_value=100.0):
        win._on_finder_snapshot_delivered(empty)
    assert win.last_query_to_first_hit_ms is None


def test_failed_direct_launch_after_qa_has_current_error_trace(scene_window, tmp_path):
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
        assert answer.error is None and answer.reconciliation.all_satisfied
        win._on_assistant_response(handle, answer)
        app_path = make_app(tmp_path / 'Apps')
        win._finder_catalog = ApplicationCatalog.scan([app_path.parent])
        # Revalidation failure after catalog discovery, never call an OS launcher.
        (app_path / 'Contents/MacOS/fixture-bin').unlink()
        win._app_launcher = lambda _: pytest.fail('Invalid app cannot launch')
        with patch('rat.ui.assistant_worker.ArtifactWorker.start'):
            win._submit_chat_prompt('mở Liên Minh')
            result = win._artifact_worker.callback()
            assert result.status == 'error'
            win._on_artifact_result(win._chat_generation, result)
        snap = win.workbench_scene.current_snapshot
        assert snap.phase == 'error'
        assert any(e.status == 'error' for e in snap.reasoning_flow), [
            (e.status, e.title, e.evidence_ref) for e in snap.reasoning_flow]
    finally:
        win.assistant_runtime = previous_runtime
        db.get_connection().close()
