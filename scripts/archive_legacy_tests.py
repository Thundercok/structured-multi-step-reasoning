import os
from pathlib import Path
import shutil

tests_dir = Path("tests")
archive_dir = Path("audit/ui_widgets_retirement_20261025/legacy_tests")
archive_dir.mkdir(parents=True, exist_ok=True)

retired_tests = [
    "test_rat_one_box_ui.py",
    "test_natal_chart_ui.py",
    "test_vgc_ui_integration.py",
    "test_book_features_ui.py",
    "test_rat_result_presentation.py",
    "test_naming_dialog.py",
    "test_compact_cot.py",
    "test_spotlight_window.py",
    "test_rat_verification_ui.py",
    "test_cot_ui.py",
    "test_onboarding.py",
    "test_dsa_multi_turn_flow.py",
    "test_timetable_chat_cards.py",
    "test_claude_widget.py",
    "test_work_context_ui.py",
    "test_omnibar.py",
    "test_turn_notes_preview.py",
    "test_selected_document_ui.py",
    "test_rat_magic_ui.py",
    "test_interaction_kernel_ui.py",
    "test_flow_interaction.py",
    "test_workbench_scene.py",
    "test_feedback_ui.py",
    "test_quicklook.py",
]

for t in retired_tests:
    src = tests_dir / t
    if src.exists():
        dst = archive_dir / t
        shutil.copy2(src, dst)
        src.unlink()

print("Archived and removed legacy QtWidgets test files.")
