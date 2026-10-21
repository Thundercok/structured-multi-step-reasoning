"""Independent finder integration probes; no models, app launch or personal scan."""
import importlib.util
import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location(
    "finder_review_original", ROOT / "tests/test_workbench_scene.py"
)
original = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = original
spec.loader.exec_module(original)
app = original.app
scene_window = original.scene_window

from rat.engine.app_resolver import ApplicationCatalog
from rat.engine.progressive_search import SearchHit, SearchSnapshot


def install_hits(win, tmp_path):
    hits = []
    for name in ("alpha.txt", "beta.txt"):
        path = tmp_path / name
        path.write_text("Synthetic fixture")
        hits.append(SearchHit("file:" + name, "file", name, str(path), "lexical_index"))
    coordinator = MagicMock()
    coordinator.is_current.return_value = True
    win.workbench_finder_enabled = True
    win._finder_coordinator = coordinator
    win.chat_composer_input.setText("fixture")
    snapshot = SearchSnapshot(9, "fixture", "lexical", tuple(hits), None, False, 1.0)
    win._on_finder_snapshot_delivered(snapshot)
    original._pump(4)
    box = win.workbench_scene.finder_box
    assert box.isVisible()
    assert box.current_hit() == hits[0]
    return box, snapshot, coordinator


def test_real_down_key_from_composer_enters_finder(scene_window, tmp_path):
    win = scene_window
    box, _, _ = install_hits(win, tmp_path)
    win.chat_composer_input.setFocus()
    original._pump(2)
    assert win.chat_composer_input.hasFocus()
    QTest.keyClick(win.chat_composer_input, Qt.Key.Key_Down)
    original._pump(2)
    assert box.hasFocus(), "Down key remained in composer instead of entering finder"


def test_real_down_key_inside_finder_changes_selection(scene_window, tmp_path):
    box, snapshot, _ = install_hits(scene_window, tmp_path)
    box.setFocus()
    original._pump(2)
    assert box.hasFocus()
    QTest.keyClick(box, Qt.Key.Key_Down)
    original._pump(2)
    assert box.selected_resource_id == snapshot.hits[1].resource_id, (
        "Finder keyboard filter was not installed on the focused suggestions widget"
    )


def test_user_selection_survives_later_snapshot(scene_window, tmp_path):
    box, snapshot, _ = install_hits(scene_window, tmp_path)
    assert box.navigate(1)
    selected = snapshot.hits[1].resource_id
    assert box.selected_resource_id == selected
    scene_window._on_finder_snapshot_delivered(replace(snapshot, phase="semantic", complete=True))
    assert box.selected_resource_id == selected, "Later snapshot reset user selection to first hit"


def test_first_query_is_replayed_when_catalog_becomes_ready(scene_window):
    win = scene_window
    win.workbench_finder_enabled = True
    win._finder_coordinator = None
    win.chat_composer_input.setText("first query")
    with patch("rat.ui.omnibar.SearchCoordinator") as coordinator_type:
        win._on_finder_catalog_ready(ApplicationCatalog())
        assert coordinator_type.return_value.submit.call_count == 1, (
            "Text entered before catalog readiness is lost until another keystroke"
        )
        assert coordinator_type.return_value.submit.call_args.args[0] == "first query"


def test_late_catalog_delivery_cannot_restart_service_after_shutdown(scene_window):
    win = scene_window
    win.shutdown()
    with patch("rat.ui.omnibar.SearchCoordinator") as coordinator_type:
        win._on_finder_catalog_ready(ApplicationCatalog())
        coordinator_type.assert_not_called()


def test_clearing_finder_query_has_no_unhandled_qt_exception(scene_window, tmp_path, monkeypatch):
    box, snapshot, coordinator = install_hits(scene_window, tmp_path)
    errors = []
    # Capture the Qt slot exception instead of letting PyQt abort this test process.
    # Without this hook the isolated run exited 134 at the following clear().
    monkeypatch.setattr(sys, "excepthook", lambda _type, error, _tb: errors.append(error))
    scene_window.chat_composer_input.clear()
    assert not errors, f"Unhandled exception clearing composer: {errors!r}"
    coordinator.cancel.assert_called()
    coordinator.is_current.return_value = False
    scene_window._on_finder_snapshot_delivered(snapshot)
    assert not box.isVisible()
    assert box.snapshot is None


def test_stale_snapshot_is_ignored_at_gui_delivery(scene_window, tmp_path):
    box, snapshot, coordinator = install_hits(scene_window, tmp_path)
    coordinator.is_current.return_value = False
    stale = replace(snapshot, query_id=8, hits=())
    scene_window._on_finder_snapshot_delivered(stale)
    assert box.snapshot == snapshot


def test_file_buttons_target_their_own_hit(scene_window, tmp_path):
    box, snapshot, _ = install_hits(scene_window, tmp_path)
    row = box._rows[snapshot.hits[1].resource_id]
    opened = MagicMock()
    scene_window.workbench_scene.on_open_file = opened
    with patch("rat.ui.workbench_scene.trigger_quicklook") as preview, patch(
        "rat.ui.workbench_scene.reveal_in_finder"
    ) as reveal:
        row.btn_open.click()
        row.btn_preview.click()
        row.btn_reveal.click()
        opened.assert_called_once_with(snapshot.hits[1].path)
        preview.assert_called_once_with(snapshot.hits[1].path)
        reveal.assert_called_once_with(snapshot.hits[1].path)


def test_ask_button_selects_source_without_submitting_chat(scene_window, tmp_path):
    box, snapshot, _ = install_hits(scene_window, tmp_path)
    row = box._rows[snapshot.hits[1].resource_id]
    draft = scene_window.chat_composer_input.text()
    row.btn_ask.click()
    original._pump(2)
    assert scene_window._selected_document_path == snapshot.hits[1].path
    assert scene_window._pending_chat_query is None
    assert scene_window.chat_composer_input.text() == draft


def test_long_chat_draft_does_not_raise_in_finder_slot(scene_window, tmp_path, monkeypatch):
    from rat.engine.progressive_search import ProgressiveSearch, SearchCoordinator

    errors = []
    monkeypatch.setattr(sys, "excepthook", lambda _type, error, _tb: errors.append(error))
    scene_window.workbench_finder_enabled = True
    coordinator = SearchCoordinator(
        ProgressiveSearch(tmp_path / "absent-fixture-index.db"), on_update=lambda _snapshot: None
    )
    scene_window._finder_coordinator = coordinator
    draft = "x" * 2001
    try:
        scene_window.chat_composer_input.setText(draft)
        assert scene_window.chat_composer_input.text() == draft
        assert not errors, f"Unhandled exception pasting chat draft: {errors!r}"
    finally:
        coordinator.close(timeout=2)


@pytest.mark.parametrize("width", [620, 420])
def test_finder_action_buttons_remain_inside_viewport(scene_window, tmp_path, width):
    box, snapshot, _ = install_hits(scene_window, tmp_path)
    hit = replace(
        snapshot.hits[0], title="so_tay_sinh_vien_2026.txt",
        snippet="Sổ tay sinh viên 2026: Đăng ký học phần theo tiến chỉ và các quy định học vụ",
    )
    scene_window._on_finder_snapshot_delivered(replace(snapshot, hits=(hit,), complete=True))
    scene_window.resize(width, 640)
    original._pump(4)
    assert scene_window.width() == width
    row = box._rows[hit.resource_id]
    for button in (row.btn_ask, row.btn_open, row.btn_preview, row.btn_reveal):
        original.assert_not_clipped(button, scene_window.workbench_scene, label=button.text())
