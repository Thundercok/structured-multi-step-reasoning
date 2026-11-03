"""Permanent architectural guardrails against RAT Lite UI/state-machine overengineering."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_PATHS = (
    "rat/ui/look_interaction.py",
    "rat/ui/mini_clipboard.py",
    "rat/ui/mini_floaty.py",
    "rat/ui/mini_translate.py",
    "rat/engine/mini_semantic.py",
    "rat/kernel/capabilities/source_analysis.py",
    "rat/kernel/capabilities/invoices.py",
    "nesy_docai",
    "modules/docai",
    "rat/ui/quick/LookSurface.qml",
    "rat/ui/quick/SpeechBubble.qml",
    "rat/ui/quick/CompanionStatus.qml",
    "rat/ui/quick/PaperDesk.qml",
    "tools/package_rat_translate.sh",
    "tools/build_rat_translate_app.sh",
    "tools/build_rat_mini_preflight.sh",
    "tools/apple_translation_probe.swift",
    "scripts/check_rat_mini.py",
    "scripts/check_rat_mini_embedding.py",
    "scripts/prepare_rat_mini_embedding.py",
    "Rat Dich.spec",
    "rat/assets/rat_look_error_seated_v1.png",
    "rat/assets/rat_look_head_v1.png",
    "rat/assets/rat_look_head_v2.png",
    "rat/assets/rat_look_idle_seated_v1.png",
    "rat/assets/rat_look_peek_v1.png",
    "docs/contracts/transient_workbench.md",
    "docs/contracts/speech_bubble.md",
    "docs/rat_mini_look_modes.md",
    "docs/design/rat-mascot-backlog-20261028",
    "docs/design/rat-gemini-ui-kit-20261029",
    "docs/design/rat-gemini-ui-kit-20261029.zip",
    "docs/design/rat-app-icon-20261028",
    "rat/assets/app_icons",
    "tools/export_rat_app_icons.py",
)


def test_deleted_overengineered_files_are_never_resurrected():
    resurrected = [rel for rel in FORBIDDEN_PATHS if (ROOT / rel).exists()]
    assert not resurrected, f"Forbidden legacy/overengineered files resurrected: {resurrected}"
    bak_files = [p.name for p in ROOT.glob("*.bak")] + [p.name for p in ROOT.glob("*.pre-task*")]
    assert not bak_files, f"Do not commit root .bak / .pre-task backup files: {bak_files}"
