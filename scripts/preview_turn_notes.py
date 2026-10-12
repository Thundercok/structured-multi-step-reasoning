"""
scripts/preview_turn_notes.py — Launch or export interactive Qt turn notes preview.

Usage:
    # Run interactively:
    python scripts/preview_turn_notes.py

    # Headless export of screenshots:
    python scripts/preview_turn_notes.py --save-screenshots audit/rat_turn_notes_stage1_preview_20261012
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
    args = parser.parse_args()

    if args.save_screenshots:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    app = QApplication.instance() or QApplication(sys.argv)
    window = TurnNotesPreviewWindow()

    if args.save_screenshots:
        out_dir: Path = args.save_screenshots
        out_dir.mkdir(parents=True, exist_ok=True)
        app.setProperty("ratReduceMotion", True)
        window.show()
        QTest.qWait(120)

        # 1. Full view with 3 turns and links
        window.grab().save(str(out_dir / "01_full_turns_overview.png"))

        # 2. Clicking Chuột: happy emote & highlight active note
        window._on_companion_clicked()
        QTest.qWait(120)
        window.grab().save(str(out_dir / "02_companion_clicked_highlight.png"))

        # 3. Inline editor open on Turn 2
        window._trigger_edit_turn2()
        QTest.qWait(120)
        window.grab().save(str(out_dir / "03_inline_editor_open.png"))

        # 4. Stale conflict warning
        window._trigger_stale_warning()
        QTest.qWait(120)
        window.grab().save(str(out_dir / "04_stale_conflict_warning.png"))

        # Cancel edit and restore
        window.turn_widgets[2].notes_pane.rows["note-tcp-time-v2"]._cancel_edit()

        # 5. Tombstone with Undo button
        window._on_note_removed("note-tcp-time-v2", 2)
        QTest.qWait(120)
        window.grab().save(str(out_dir / "05_removed_tombstone_undo.png"))

        # Restore note
        window._on_note_restored("note-tcp-time-v2")

        # 6. Compact HUD mode
        window.toggle_expanded()
        QTest.qWait(120)
        window.grab().save(str(out_dir / "06_compact_hud_mode.png"))

        # 7. In Compact HUD mode, navigate to old Turn 1 (local disclosure)
        window.navigate_to_turn_note(1, "note-tcp-time")
        QTest.qWait(120)
        window.grab().save(str(out_dir / "07_compact_revealed_old_turn.png"))

        print(f"All 7 preview screenshots saved successfully to {out_dir}")
        window.close()
        window.deleteLater()
        return

    # Interactive mode
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
