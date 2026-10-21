"""Keyboard checks for the newly wired finder filter, with actions mocked."""
import importlib.util
import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location(
    "finder_prior_review", ROOT / "audit/rat_finder_codex_review_20261016/test_finder_integration_probes.py"
)
prior = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = prior
spec.loader.exec_module(prior)
app, scene_window = prior.app, prior.scene_window


@pytest.mark.parametrize('key', [Qt.Key.Key_Return, Qt.Key.Key_Space])
def test_keyboard_ask_activates_ask_instead_of_opening_file(scene_window, tmp_path, key):
    win = scene_window
    box, snapshot, _ = prior.install_hits(win, tmp_path)
    hit = snapshot.hits[1]
    box._on_row_selected(hit.resource_id)
    button = box._rows[hit.resource_id].btn_ask
    button.setFocus()
    prior.original._pump(2)
    assert button.hasFocus()
    with patch('rat.ui.omnibar.open_file_default') as opened:
        QTest.keyClick(button, key)
        prior.original._pump(2)
        assert opened.call_count == 0, f'Focused Hỏi unexpectedly opened a file: {opened.call_args_list!r}'
        assert win._selected_document_path == hit.path, 'Focused Hỏi must activate the document question action'
    assert win._pending_chat_query is None


def test_tabbed_row_shortcut_targets_focused_row(scene_window, tmp_path):
    box, snapshot, _ = prior.install_hits(scene_window, tmp_path)
    first, second = snapshot.hits
    first_ask = box._rows[first.resource_id].btn_ask
    second_ask = box._rows[second.resource_id].btn_ask
    first_ask.setFocus()
    prior.original._pump(2)
    for _ in range(10):
        focused = QApplication.focusWidget()
        if focused is second_ask:
            break
        assert focused is not None
        QTest.keyClick(focused, Qt.Key.Key_Tab)
        prior.original._pump(1)
    assert second_ask.hasFocus(), 'Second row actions must be reachable with Tab'
    with patch('rat.ui.omnibar.reveal_in_finder') as reveal:
        QTest.keyClick(second_ask, Qt.Key.Key_Return, Qt.KeyboardModifier.MetaModifier)
        reveal.assert_called_once_with(second.path)


def test_shift_down_keeps_native_text_selection_and_focus(scene_window, tmp_path):
    win = scene_window
    prior.install_hits(win, tmp_path)
    reference = prior.original.ChatComposer()
    reference.setText('fixture')
    reference.setCursorPosition(2)
    reference.show()
    QTest.keyClick(reference, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
    expected = reference.textCursor().position(), reference.textCursor().anchor()
    try:
        reference.close()
        win.activateWindow()
        win.chat_composer_input.setCursorPosition(2)
        win.chat_composer_input.setFocus()
        prior.original._pump(2)
        assert win.chat_composer_input.hasFocus()
        QTest.keyClick(win.chat_composer_input, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
        actual = win.chat_composer_input.textCursor().position(), win.chat_composer_input.textCursor().anchor()
        assert actual == expected, 'Finder shortcut changed Shift+Down text selection'
        assert win.chat_composer_input.hasFocus(), 'Shift+Down must remain an editing shortcut'
    finally:
        reference.close()


def test_plain_down_still_edits_within_multiline_draft(scene_window, tmp_path):
    win = scene_window
    prior.install_hits(win, tmp_path)
    win.chat_composer_input.setText('first line\nsecond line')
    win.chat_composer_input.setCursorPosition(2)
    win.chat_composer_input.setFocus()
    prior.original._pump(2)
    assert win.chat_composer_input.hasFocus()
    QTest.keyClick(win.chat_composer_input, Qt.Key.Key_Down)
    assert win.chat_composer_input.hasFocus()
    assert win.chat_composer_input.textCursor().blockNumber() == 1


def test_progressive_update_preserves_focused_action(scene_window, tmp_path):
    box, snapshot, _ = prior.install_hits(scene_window, tmp_path)
    hit = snapshot.hits[1]
    box._on_row_selected(hit.resource_id)
    button = box._rows[hit.resource_id].btn_ask
    button.setFocus()
    prior.original._pump(2)
    assert button.hasFocus()
    scene_window._on_finder_snapshot_delivered(replace(snapshot, phase='semantic', complete=True))
    QTest.qWait(10)
    assert box._rows[hit.resource_id].btn_ask.hasFocus(), 'Rebuilding rows lost focused action on same-query update'
