"""
scripts/preview_turn_notes.py — Launch or export interactive Qt turn notes preview.

Usage:
    # Run interactively:
    python scripts/preview_turn_notes.py
    python scripts/preview_turn_notes.py --compact

    # Headless export to a fresh directory (preserve reviewed audit captures):
    python scripts/preview_turn_notes.py --save-screenshots /tmp/rat-turn-notes-preview
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from rat.ui.turn_notes_preview import TurnNotesPreviewWindow


def main() -> None:
    parser = argparse.ArgumentParser(description="RAT Stage 1 Turn Notes UX Preview")
    parser.add_argument(
        "--save-screenshots",
        type=Path,
        help="Directory to save preview screenshots headlessly and exit.",
    )
    parser.add_argument('--compact', action='store_true', help='Open the interactive preview as a compact desktop chat.')
    args = parser.parse_args()

    if args.save_screenshots:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    app = QApplication.instance() or QApplication(sys.argv)
    window = TurnNotesPreviewWindow()

    if args.save_screenshots:
        out_dir: Path = args.save_screenshots
        out_dir.mkdir(parents=True, exist_ok=True)
        app.setProperty("ratReduceMotion", True)
        # Hide QA dock by default to capture clean user surface
        window.dock.hide()
        window.show()
        QTest.qWait(240)

        # 1. Full view: lightweight note lines, legible replaced text, links, real composer
        window.grab().save(str(out_dir / "01_full_turns_overview.png"))

        # 2. Clicking Chuột: happy emote & natural phrasing hint & active note highlight
        window._on_companion_clicked()
        QTest.qWait(120)
        window.grab().save(str(out_dir / "02_companion_clicked_highlight.png"))

        # 3. Inline editor open on Turn 2
        window._trigger_edit_turn2()
        QTest.qWait(120)
        window.grab().save(str(out_dir / "03_inline_editor_open.png"))

        # 4. Stale conflict warning preserving draft
        window._trigger_stale_warning()
        QTest.qWait(120)
        window.grab().save(str(out_dir / "04_stale_conflict_warning.png"))

        # Save edit with new text to demonstrate predecessor link updating (Bug 3 fix)
        row_t2 = window.turn_widgets[2].notes_pane.rows["note-tcp-time-v2"]
        row_t2.editor.setPlainText("Có 45 phút · Ôn cả BGP.")
        row_t2._save_edit()
        QTest.qWait(120)
        window.grab().save(str(out_dir / "05_predecessor_link_updated.png"))

        # 6. Tombstone with Undo button
        window._on_note_removed("note-tcp-time-v2", 3)
        QTest.qWait(120)
        window.grab().save(str(out_dir / "06_removed_tombstone_undo.png"))

        # Restore note
        window._on_note_restored("note-tcp-time-v2")

        # 7. Authentic Compact HUD mode (snug dimensions, composer)
        window.toggle_expanded()
        QTest.qWait(120)
        window.grab().save(str(out_dir / "07_compact_hud_mode.png"))

        # 8. In Compact HUD mode, navigate to old Turn 1 (local disclosure)
        window.navigate_to_turn_note(1, "note-tcp-time")
        QTest.qWait(120)
        window.grab().save(str(out_dir / "08_compact_revealed_old_turn.png"))

        # 9. Return to full and show toggleable QA tools
        window.toggle_expanded()
        window.dock.show()
        QTest.qWait(120)
        window.grab().save(str(out_dir / "09_qa_dock_visible.png"))

        # Metadata disclosure is inline, with no separate note panel.
        window.dock.hide()
        row_t2.btn_details.setChecked(True)
        QTest.qWait(240)
        window.grab().save(str(out_dir / "10_note_details_inline.png"))

        # Composer selection survives a compact/full transition.
        window.chat_composer.setText("Giữ hộ 30 phút, mình quay lại ngay.")
        window.chat_composer.setSelection(8, 7)
        window.chat_composer.setFocus()
        window.toggle_expanded()
        QTest.qWait(240)
        window.grab().save(str(out_dir / "11_compact_composer_draft.png"))

        print(f"All 11 preview screenshots saved successfully to {out_dir}")
        window.close()
        window.deleteLater()
        return

    # Interactive mode
    if args.compact:
        window.toggle_expanded()
        window._fit_surface()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
