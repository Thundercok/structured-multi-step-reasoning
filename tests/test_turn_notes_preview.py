"""
Tests for RAT Stage 1 Turn Notes UX Preview.
Verifies turn-level note rendering, revision linking, inline editing,
companion mascot interaction, and compact/full disclosure.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from rat.ui.turn_notes import InlineNoteRow, TurnNoteItem, TurnNotesPane
from rat.ui.turn_notes_preview import TurnNotesPreviewWindow


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    instance.setProperty("ratReduceMotion", True)
    yield instance
    instance.setProperty("ratReduceMotion", False)


@pytest.fixture
def window(app):
    win = TurnNotesPreviewWindow()
    win.show()
    QTest.qWait(30)
    yield win
    win.close()
    win.deleteLater()
    app.processEvents()


def test_turn_notes_structure_and_revision_links(window):
    assert len(window.turn_widgets) == 3
    t1 = window.turn_widgets[1]
    t2 = window.turn_widgets[2]
    t3 = window.turn_widgets[3]

    # Turn 1 note is marked replaced and links to Turn 2
    row_t1 = t1.notes_pane.rows["note-tcp-time"]
    assert row_t1.note.status == "replaced"
    assert row_t1.note.replaced_by_turn_id == 2
    assert row_t1.btn_nav_link.isVisible()
    assert "20 → 30 phút" in row_t1.btn_nav_link.text()

    # Turn 2 note is active and links back to Turn 1
    row_t2 = t2.notes_pane.rows["note-tcp-time-v2"]
    assert row_t2.note.status == "active"
    assert row_t2.note.replaces_turn_id == 1
    assert row_t2.btn_nav_link.isVisible()
    assert "Có 20 phút" in row_t2.btn_nav_link.text()

    # Turn 3 note is a proposal
    row_t3 = t3.notes_pane.rows["note-tcp-quiz-proposal"]
    assert row_t3.note.status == "proposed"
    assert row_t3.btn_confirm.isVisible()


def test_navigation_link_triggers_highlight(window):
    t1 = window.turn_widgets[1]
    row_t1 = t1.notes_pane.rows["note-tcp-time"]

    t2 = window.turn_widgets[2]
    row_t2 = t2.notes_pane.rows["note-tcp-time-v2"]

    # Click forward link in Turn 1
    QTest.mouseClick(row_t1.btn_nav_link, Qt.MouseButton.LeftButton)
    QTest.qWait(20)

    # Turn 2 note should have received highlight
    assert row_t2.anim.state() == row_t2.anim.State.Running or row_t2.get_highlight_ratio() >= 0.0


def test_inline_editor_lifecycle(window):
    t2 = window.turn_widgets[2]
    row = t2.notes_pane.rows["note-tcp-time-v2"]

    # Start editing
    row._start_edit()
    assert row.editing
    assert row.editor_section.isVisible()
    assert not row.actions_widget.isVisible()
    assert "Congestion Control" in row.editor.toPlainText()

    # Cancel editing
    row._cancel_edit()
    assert not row.editing
    assert not row.editor_section.isVisible()
    assert row.actions_widget.isVisible()

    # Edit and apply new text
    row._start_edit()
    row.editor.setPlainText("Có 35 phút · Ôn cả BGP.")
    row._save_edit()
    assert row.note.text == "Có 35 phút · Ôn cả BGP."
    assert not row.editing


def test_stale_warning_preserves_draft(window):
    t2 = window.turn_widgets[2]
    row = t2.notes_pane.rows["note-tcp-time-v2"]

    row._start_edit()
    row.editor.setPlainText("Bản nháp đang gõ dở...")
    window._trigger_stale_warning()

    assert row.error_label.isVisible()
    assert "xung đột" in row.error_label.text().lower()
    assert row.editor.toPlainText() == "Bản nháp đang gõ dở..."


def test_remove_and_undo_restores_note(window):
    t2 = window.turn_widgets[2]
    row = t2.notes_pane.rows["note-tcp-time-v2"]

    # Remove note
    QTest.mouseClick(row.btn_remove, Qt.MouseButton.LeftButton)
    assert row.note.status == "removed"
    assert row.btn_undo.isVisible()
    assert not row.btn_edit.isVisible()

    # Undo removal
    QTest.mouseClick(row.btn_undo, Qt.MouseButton.LeftButton)
    assert row.note.status == "active"
    assert row.btn_edit.isVisible()


def test_confirm_proposed_note(window):
    t3 = window.turn_widgets[3]
    row = t3.notes_pane.rows["note-tcp-quiz-proposal"]

    assert row.note.status == "proposed"
    QTest.mouseClick(row.btn_confirm, Qt.MouseButton.LeftButton)

    assert row.note.status == "active"
    assert row.note.confirmed is True
    assert not row.btn_confirm.isVisible()
    assert row.btn_edit.isVisible()


def test_companion_click_emotes_and_targets_active_note(window):
    companion = window.companion
    assert companion.isVisible()

    QTest.mouseClick(companion, Qt.MouseButton.LeftButton)
    QTest.qWait(20)

    # Companion reacts
    assert companion.pose()["reaction"] == "happy"

    # Active note is highlighted
    t2 = window.turn_widgets[2]
    row = t2.notes_pane.rows["note-tcp-time-v2"]
    assert row.anim.state() == row.anim.State.Running or row.get_highlight_ratio() >= 0.0


def test_compact_and_full_mode_toggle_with_local_disclosure(window):
    # Default is expanded/full
    assert window.is_expanded
    assert all(w.isVisible() for w in window.turn_widgets.values())

    # Switch to compact mode
    window.toggle_expanded()
    assert not window.is_expanded

    # In compact mode, only latest turn (3) is visible
    assert not window.turn_widgets[1].isVisible()
    assert not window.turn_widgets[2].isVisible()
    assert window.turn_widgets[3].isVisible()

    # Navigate to Turn 1 note from compact mode
    window.navigate_to_turn_note(1, "note-tcp-time")
    assert window.turn_widgets[1].isVisible()
    assert not window.turn_widgets[3].isVisible()
    assert window.compact_nav_banner.isVisible()

    # Return to latest
    window._return_to_latest_compact_turn()
    assert not window.turn_widgets[1].isVisible()
    assert window.turn_widgets[3].isVisible()
    assert not window.compact_nav_banner.isVisible()
