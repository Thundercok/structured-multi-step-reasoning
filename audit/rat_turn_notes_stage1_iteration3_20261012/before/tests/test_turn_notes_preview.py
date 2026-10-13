"""
Tests for RAT Stage 1 Turn Notes UX Preview.
Verifies turn-level note rendering, revision linking, inline editing,
companion mascot interaction, compact/full disclosure, and fixes for the 4 review findings:
1. Compact toggle preserves active editor, draft, and focus.
2. 'Sửa bản mới' on predecessor note opens the active replacement note editor.
3. Predecessor forward link text dynamically updates when successor is edited.
4. Reduced motion setting is strictly respected (static cue, no QPropertyAnimation).
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

    # Turn 1 note is marked replaced, legible text, and links to Turn 2
    row_t1 = t1.notes_pane.rows["note-tcp-time"]
    assert row_t1.note.status == "replaced"
    assert row_t1.note.replaced_by_turn_id == 2
    assert row_t1.btn_nav_link.isVisible()
    assert "30 phút" in row_t1.btn_nav_link.text()
    assert "line-through" not in row_t1.text_label.styleSheet()  # Legible, not struck through

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


def test_navigation_link_triggers_highlight(window, monkeypatch):
    t1 = window.turn_widgets[1]
    row_t1 = t1.notes_pane.rows["note-tcp-time"]
    t2 = window.turn_widgets[2]
    row_t2 = t2.notes_pane.rows["note-tcp-time-v2"]

    # When motion is enabled
    monkeypatch.setattr("rat.ui.surface_layout.motion_enabled", lambda: True)
    QTest.mouseClick(row_t1.btn_nav_link, Qt.MouseButton.LeftButton)
    QTest.qWait(20)
    assert row_t2.anim.state() == row_t2.anim.State.Running

    # When motion is disabled
    monkeypatch.setattr("rat.ui.surface_layout.motion_enabled", lambda: False)
    row_t2.anim.stop()
    row_t2.set_highlight_ratio(0.0)
    QTest.mouseClick(row_t1.btn_nav_link, Qt.MouseButton.LeftButton)
    QTest.qWait(20)
    assert row_t2.anim.state() == row_t2.anim.State.Stopped
    assert row_t2.is_highlighted() is True


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


def test_companion_click_emotes_and_targets_active_note_with_natural_text(window):
    companion = window.companion
    assert companion.isVisible()

    QTest.mouseClick(companion, Qt.MouseButton.LeftButton)
    QTest.qWait(20)

    # Companion reacts
    assert companion.pose()["reaction"] == "happy"

    # Hint text uses friendly text, not technical IDs
    hint_text = window.composer_hint.text()
    assert "note-tcp-time-v2" not in hint_text
    assert "Ghi chép đang dùng" in hint_text


def test_compact_and_full_mode_toggle_with_local_disclosure(window):
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


# ==============================================================================
# Tests specifically targeting the 4 reviewer findings:
# ==============================================================================

def test_compact_toggle_preserves_active_editor_and_focus(window):
    """Finding 1: Toggling compact preserves active editor in-place with its draft and focus."""
    t2 = window.turn_widgets[2]
    row = t2.notes_pane.rows["note-tcp-time-v2"]

    row._start_edit()
    row.editor.setPlainText("Bản nháp đang gõ tại lượt 2")
    row.editor.setFocus()
    assert QApplication.focusWidget() is row.editor

    # Toggle to compact
    window.toggle_expanded()
    assert not window.is_expanded

    # Turn 2 MUST stay visible because it has the active editor
    assert t2.isVisible()
    assert row.editing is True
    assert row.editor_section.isVisible()
    assert row.editor.toPlainText() == "Bản nháp đang gõ tại lượt 2"
    assert QApplication.focusWidget() is row.editor


def test_edit_replacement_opens_target_editor(window):
    """Finding 2: Clicking 'Sửa bản mới' on old note navigates AND opens target editor."""
    t1 = window.turn_widgets[1]
    row_t1 = t1.notes_pane.rows["note-tcp-time"]

    t2 = window.turn_widgets[2]
    row_t2 = t2.notes_pane.rows["note-tcp-time-v2"]
    assert not row_t2.editing

    # Click 'Sửa bản mới' on Turn 1 note
    QTest.mouseClick(row_t1.btn_edit, Qt.MouseButton.LeftButton)
    QTest.qWait(20)

    # Turn 2 note editor MUST now be open and focused
    assert t2.isVisible()
    assert row_t2.editing is True
    assert row_t2.editor_section.isVisible()
    assert QApplication.focusWidget() is row_t2.editor


def test_predecessor_link_updates_when_successor_edited(window):
    """Finding 3: When successor note is edited, predecessor forward link updates to match."""
    t1 = window.turn_widgets[1]
    row_t1 = t1.notes_pane.rows["note-tcp-time"]
    assert "30 phút" in row_t1.btn_nav_link.text()

    # Edit Turn 2 note to a new string
    t2 = window.turn_widgets[2]
    row_t2 = t2.notes_pane.rows["note-tcp-time-v2"]
    row_t2._start_edit()
    row_t2.editor.setPlainText("Có 45 phút · Ôn BGP.")
    row_t2._save_edit()

    # Turn 1 note forward link MUST dynamically update
    row_t1_updated = t1.notes_pane.rows["note-tcp-time"]
    assert "45 phút" in row_t1_updated.btn_nav_link.text()
    assert "BGP" in row_t1_updated.btn_nav_link.text()


def test_reduced_motion_avoids_animation(window, monkeypatch):
    """Finding 4: When ratReduceMotion=True, highlight does NOT run QPropertyAnimation."""
    monkeypatch.setattr("rat.ui.surface_layout.motion_enabled", lambda: False)
    t2 = window.turn_widgets[2]
    row = t2.notes_pane.rows["note-tcp-time-v2"]
    row.anim.stop()
    row.set_highlight_ratio(0.0)

    row.trigger_highlight()

    # Animation MUST NOT be running
    assert row.anim.state() == row.anim.State.Stopped
    # Static cue MUST be visible
    assert row.is_highlighted() is True
    assert row.get_highlight_ratio() >= 0.7
