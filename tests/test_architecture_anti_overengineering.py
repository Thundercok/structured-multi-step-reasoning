"""Permanent architectural guardrails against RAT Lite UI/state-machine overengineering."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_PATHS = (
    "rat/ui/look_interaction.py",
    "rat/ui/mini_clipboard.py",
    "rat/ui/mini_floaty.py",
    "rat/ui/mini_translate.py",
    "rat/kernel/capabilities/source_analysis.py",
    "rat/ui/quick/LookSurface.qml",
    "rat/ui/quick/SpeechBubble.qml",
    "rat/ui/quick/CompanionStatus.qml",
    "rat/ui/quick/PaperDesk.qml",
    "tools/package_rat_translate.sh",
    "tools/build_rat_translate_app.sh",
    "Rat Dich.spec",
    "rat/assets/rat_look_error_seated_v1.png",
    "rat/assets/rat_look_head_v1.png",
    "rat/assets/rat_look_head_v2.png",
    "rat/assets/rat_look_idle_seated_v1.png",
    "rat/assets/rat_look_peek_v1.png",
    "docs/contracts/transient_workbench.md",
    "docs/contracts/speech_bubble.md",
    "docs/rat_mini_look_modes.md",
)


def test_deleted_overengineered_files_are_never_resurrected():
    resurrected = [rel for rel in FORBIDDEN_PATHS if (ROOT / rel).exists()]
    assert not resurrected, f"Forbidden legacy/overengineered files resurrected: {resurrected}"


def test_mini_state_and_placement_stay_single_surface():
    placement = (ROOT / "rat/ui/mini_placement.py").read_text(encoding="utf-8")
    presentation = (ROOT / "rat/ui/mini_presentation.py").read_text(encoding="utf-8")
    desk = (ROOT / "rat/ui/quick/MiniDesk.qml").read_text(encoding="utf-8")

    assert "def place_panel" not in placement
    assert len(placement.splitlines()) <= 60, "mini_placement.py exceeded 60-line simplicity ceiling"

    for banned in ("workbench", "look_projection", "_public_turns", "_public_steps", "lookSource"):
        assert banned not in presentation, f"Banned overengineered symbol {banned!r} in mini_presentation.py"
    assert len(presentation.splitlines()) <= 120, "mini_presentation.py exceeded 120-line simplicity ceiling"

    for banned in ('surface === "workbench"', "setWorkspaceMode", "receiveLookClipboard", "openPendingLook"):
        assert banned not in desk, f"Banned overengineered symbol {banned!r} in MiniDesk.qml"
    assert len(desk.splitlines()) <= 1850, "MiniDesk.qml exceeded 1850-line simplicity ceiling"


def test_floating_head_looking_mode_is_pure_translation_and_anti_jarring():
    mini_py = (ROOT / "rat/mini.py").read_text(encoding="utf-8")
    capture_py = (ROOT / "rat/engine/capture_translation.py").read_text(encoding="utf-8")
    worker_py = (ROOT / "rat/ui/mini_worker.py").read_text(encoding="utf-8")
    controller_py = (ROOT / "rat/ui/mini_quick_controller.py").read_text(encoding="utf-8")

    for banned in ("observe_only", "analyze_captured_text", "revise_observed_result"):
        assert banned not in mini_py, f"Looking mode must only translate, found {banned!r} in rat/mini.py"
        assert banned not in capture_py, f"Looking mode must only translate, found {banned!r} in capture_translation.py"
        assert banned not in worker_py, f"Looking mode must only translate, found {banned!r} in mini_worker.py"
        assert banned not in controller_py, f"Looking mode must only translate, found {banned!r} in mini_quick_controller.py"

    assert "self.state.start_pending(label, expanded=True)" not in controller_py, (
        "start_pending() must not force expanded=True (causes 440px->580px->440px jarring width bounce)"
    )
    assert "if self._ocr_source_ref:" not in controller_py, (
        "Typed composer queries must only route to OCR correction when self.presentation.surface == 'ocr'"
    )
