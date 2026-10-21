"""Default desktop journeys on authored DB/catalog fixtures, no models or launches."""
import time
import threading
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from rat.engine.app_resolver import ApplicationCatalog
from rat.engine.progressive_search import SearchHit, SearchSnapshot
from rat.ui.omnibar import OmnibarWindow
from rat.ui.workbench_scene import workbench_finder_enabled, workbench_scene_enabled


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def until(app, predicate):
    deadline = time.monotonic() + 5
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert predicate()


@pytest.fixture
def window(app, tmp_path, monkeypatch):
    from rat.config import config
    from rat.ui import omnibar
    monkeypatch.delenv("RAT_WORKBENCH_SCENE", raising=False)
    monkeypatch.delenv("RAT_WORKBENCH_FINDER", raising=False)
    monkeypatch.setenv("RAT_REDUCE_MOTION", "1")
    monkeypatch.setattr(config, "db_path", str(tmp_path / "fixture.db"))
    monkeypatch.setattr(config, "document_model_path", "")
    monkeypatch.setattr(config, "document_model_preload", False)
    monkeypatch.setattr(omnibar, "load_club_members", lambda: [])
    monkeypatch.setattr(omnibar, "SearchEngine", Mock())
    monkeypatch.setattr("rat.ui.feedback.FeedbackLog", Mock())
    monkeypatch.setattr(ApplicationCatalog, "scan", classmethod(lambda cls, *a, **k: cls()))
    monkeypatch.setattr("rat.engine.slm.slm_engine.is_service_running", lambda: pytest.fail("GUI probed model service"))
    monkeypatch.setattr("rat.engine.slm.slm_engine.list_installed_models", lambda: [])
    obj = OmnibarWindow()
    obj.show_omnibar()
    until(app, lambda: obj.isVisible())
    yield obj
    obj.shutdown()
    obj.hide()
    obj.deleteLater()
    app.processEvents()


def test_standard_surface_and_explicit_compatibility_opt_out(app, monkeypatch):
    for name, check in (("RAT_WORKBENCH_SCENE", workbench_scene_enabled),
                        ("RAT_WORKBENCH_FINDER", workbench_finder_enabled)):
        monkeypatch.delenv(name, raising=False)
        assert check()
        monkeypatch.setenv(name, "0")
        assert not check()


def test_hidden_pages_are_lazy_and_reused(window):
    stack = window.content_stack
    assert set(stack._page_factories) == {2, 3, 4}
    assert not hasattr(window, "settings_assistant_combo")
    window.switch_section(4)
    page = window.settings_view
    assert 4 not in stack._page_factories
    assert hasattr(window, "settings_assistant_combo")
    window.switch_section(0)
    window.switch_section(4)
    assert window.settings_view is page


def test_hide_reopen_and_resize_keep_draft_selection_and_focus(window, app):
    editor = window.chat_composer_input
    editor.setText("Bản nháp tiếng Việt đang gõ")
    cursor = editor.textCursor()
    cursor.setPosition(4)
    cursor.setPosition(12, cursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    selection = cursor.selectedText()
    window.hide()
    window.show_omnibar()
    window.activateWindow()
    for expanded in (True, False, True, False):
        window.set_expanded(expanded)
        app.processEvents()
        assert editor.text() == "Bản nháp tiếng Việt đang gõ"
        assert editor.textCursor().selectedText() == selection
    assert QApplication.focusWidget() is editor


def add_file(window, tmp_path, name):
    path = tmp_path / name
    path.write_text("authored fixture")
    window.db.upsert_document(dict(file_path=str(path), file_name=name, file_ext=path.suffix,
        file_size=path.stat().st_size, created_at=1, modified_at=1, indexed_at=1,
        content_text="authored fixture", summary="fixture"))
    return path


def test_type_select_preview_open_and_return_to_composer(window, app, tmp_path, monkeypatch):
    from rat.ui import omnibar
    first = add_file(window, tmp_path, "flow-first.txt")
    add_file(window, tmp_path, "flow-second.txt")
    opened, preview = Mock(), Mock()
    monkeypatch.setattr(omnibar, "open_file_default", opened)
    monkeypatch.setattr(omnibar, "trigger_quicklook", preview)
    editor = window.chat_composer_input
    editor.setText("flow")
    box = window.workbench_scene.finder_box
    until(app, lambda: len(box._row_order) == 2)
    window.activateWindow()
    editor.setFocus()
    QTest.keyClick(editor, Qt.Key.Key_Tab)
    assert QApplication.focusWidget() is box
    chosen = box.current_hit()
    assert chosen.path in {str(first), str(tmp_path / "flow-second.txt")}
    QTest.keyClick(box, Qt.Key.Key_Space)
    preview.assert_called_once_with(chosen.path)
    QTest.keyClick(box, Qt.Key.Key_Return)
    opened.assert_called_once_with(chosen.path)
    QTest.keyClick(box, Qt.Key.Key_Escape)
    assert QApplication.focusWidget() is editor
    assert editor.text() == "flow"


def test_enter_in_composer_submits_request_without_opening_selection(window, app, tmp_path, monkeypatch):
    from rat.ui import omnibar
    add_file(window, tmp_path, "flow-item.txt")
    monkeypatch.setattr("rat.ui.assistant_worker.AssistantWorker.start", Mock())
    opened = Mock()
    monkeypatch.setattr(omnibar, "open_file_default", opened)
    editor = window.chat_composer_input
    editor.setText("flow")
    until(app, lambda: bool(window.workbench_scene.finder_box._row_order))
    editor.setFocus()
    QTest.keyClick(editor, Qt.Key.Key_Return)
    assert window._pending_chat_query == "flow"
    assert window._assistant_handle["execution_request"].execution_id
    opened.assert_not_called()


def test_old_snapshot_cannot_replace_new_query_selection(window, app, tmp_path):
    path = add_file(window, tmp_path, "flow-current.txt")
    editor = window.chat_composer_input
    editor.setText("flow")
    until(app, lambda: bool(window.workbench_scene.finder_box._row_order))
    current_id = window._finder_selected_id
    editor.setText("unmatched-new-query")
    until(app, lambda: window.workbench_scene.finder_box.snapshot.query == "unmatched-new-query")
    stale = SearchSnapshot(-1, "flow", "lexical",
        (SearchHit(current_id, "file", "stale", str(path), "metadata"),), current_id, True, 0, ())
    window._on_finder_snapshot_delivered(stale)
    assert window.workbench_scene.finder_box.snapshot.query == "unmatched-new-query"
    assert not window.workbench_scene.finder_box._row_order


def test_catalog_delivery_keeps_query_epoch_and_rejects_queued_old_result(window, app, tmp_path):
    path = add_file(window, tmp_path, "flow-catalog.txt")
    window.chat_composer_input.setText("flow")
    box = window.workbench_scene.finder_box
    until(app, lambda: bool(box._row_order))
    coordinator = window._finder_coordinator
    before = box.snapshot
    selected = box.selected_resource_id
    window._on_finder_catalog_ready(ApplicationCatalog())
    assert window._finder_coordinator is coordinator
    until(app, lambda: box.snapshot.query_id > before.query_id)
    current_id = box.snapshot.query_id
    stale = SearchSnapshot(before.query_id, "stale catalog", "lexical",
        (SearchHit(selected, "file", "stale", str(path), "metadata"),), selected, True, 0, ())
    window._on_finder_snapshot_delivered(stale)
    assert box.snapshot.query_id == current_id
    assert box.snapshot.query == "flow"
    assert box.selected_resource_id == selected


def test_index_metadata_wait_does_not_block_typing(window, app, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    def blocked_stats():
        entered.set()
        assert release.wait(5)
        return {"total_files": 0}
    monkeypatch.setattr(window.db, "get_stats", blocked_stats)
    try:
        window._load_initial_data()
        until(app, entered.is_set)
        editor = window.chat_composer_input
        editor.clear()
        editor.setFocus()
        QTest.keyClicks(editor, "typing while metadata waits")
        assert editor.text() == "typing while metadata waits"
        assert not release.is_set()
    finally:
        release.set()
        QTest.qWait(20)


def test_settings_model_lookup_wait_does_not_block_window(window, app, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    threads = []
    def model_names():
        threads.append(threading.current_thread())
        entered.set()
        assert release.wait(5)
        return ["fixture-model"]
    monkeypatch.setattr("rat.engine.slm.slm_engine.list_installed_models", model_names)
    try:
        window.switch_section(4)
        until(app, entered.is_set)
        window.switch_section(0)
        window.chat_composer_input.setFocus()
        QTest.keyClicks(window.chat_composer_input, "still editable")
        assert window.chat_composer_input.text() == "still editable"
        assert threads[0] is not threading.main_thread()
    finally:
        release.set()
        QTest.qWait(20)


def test_composer_reaches_composed_policy_and_returns_to_same_conversation(window, app):
    import numpy as np
    from rat.engine.meta_reasoner import build_composed_meta_reasoner
    from reasoning.bundle import create_synthetic_specimen_bundle
    class Backend:
        hidden_size = 2
        def embed(self, query):
            return np.zeros(2)
        def run(self, strategy, query):
            return "observed synthetic answer", .9, 7
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    engine = build_composed_meta_reasoner(bundle, Backend(), policy, allow_synthetic=True)
    app.setProperty("ratReasoningEngine", engine)
    app.setProperty("ratAllowSyntheticPolicy", True)
    try:
        window.chat_composer_input.setText("giải thích fixture")
        window._submit_chat_prompt(window.chat_composer_input.text())
        until(app, lambda: window._pending_chat_query is None)
        result = window.workbench_scene.current_snapshot.result_node
        assert result.answer_text == "observed synthetic answer"
        assert window.last_turn_telemetry["execution_lane"] == "reasoning"
        assert window.last_turn_telemetry["cost_ledger"]["generated_tokens"] == 7
    finally:
        app.setProperty("ratReasoningEngine", None)
        app.setProperty("ratAllowSyntheticPolicy", None)
