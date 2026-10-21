"""Independent repair follow-ups; fixtures only, no inference or OS launch."""
import importlib.util
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest
from PyQt6.QtWidgets import QPushButton

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("repair_review_base", ROOT / "tests/test_workbench_scene.py")
base = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = base
spec.loader.exec_module(base)
app, scene_window = base.app, base.scene_window

from rat.crawler.db import Database
from rat.engine.assistant_runtime import AssistantRuntime
from rat.engine.selected_document_qa import answer_selected_document
from rat.kernel.contracts import Artifact
from rat.kernel.view_spec import StandardViewProvider
from rat.timetable.compositor import TimetableCompositor
from rat.ui.view_renderer import QtViewRenderer


@pytest.fixture
def completed_short_qa(scene_window, tmp_path):
    win = scene_window
    db = Database(str(tmp_path / "fixture.db"))
    path = tmp_path / "source.txt"
    path.write_text("Verification code LOTUS-7319.")
    db.upsert_document(dict(file_path=str(path), file_name=path.name, file_ext='.txt',
        file_size=path.stat().st_size, created_at=1, modified_at=1, indexed_at=1,
        content_text=path.read_text(), summary="Synthetic source"))
    client = Mock()
    client.chat_with_meta.return_value = dict(message={"content": "LOTUS-7319"}, done_reason="stop",
        prompt_tokens=20, completion_tokens=4, error=None)
    runtime = AssistantRuntime(db=db, compositor=TimetableCompositor([]), use_live_model=True)
    previous = win.assistant_runtime
    win.assistant_runtime = runtime
    try:
        win._submit_chat_prompt("What code?", selected_document_path=str(path))
        handle = win._assistant_handle
        response = answer_selected_document(runtime, "What code?", str(path), model_client=client,
            turn_ref=handle["turn_ref"], execution_id=handle["execution_id"])
        assert response.error is None and response.reconciliation.all_satisfied
        win._on_assistant_response(handle, response)
        base._pump(6)
        assert "LOTUS-7319" in win.workbench_speech_bubble.dialogue.text()
        assert win.workbench_scene.result_card.isHidden()
        yield win
    finally:
        win.assistant_runtime = previous
        db.get_connection().close()


@pytest.mark.parametrize("action", ["initial", "source-detail-back", "snapshot-refresh"])
def test_v2_answer_stays_visibly_accessible_after_navigation(completed_short_qa, action):
    win = completed_short_qa
    scene = win.workbench_scene
    if action == "source-detail-back":
        src = scene.current_snapshot.primary_sources[0]
        assert scene.select_source(src.node_id)
        base._pump(3)
        scene.show_overview()
    elif action == "snapshot-refresh":
        win._sync_workbench_scene(animate=False)
    base._pump(4)
    assert scene.mode == "overview"
    bubble_text = win.workbench_speech_bubble.dialogue.text()
    visible_card_answer = scene.result_card.isVisible() and "LOTUS-7319" in scene.result_card.answer_lbl.text()
    assert "LOTUS-7319" in bubble_text or visible_card_answer, {
        "visible_bubble": bubble_text,
        "copy_buffer": win.workbench_speech_bubble._copy_text,
        "result_card_hidden": scene.result_card.isHidden(),
        "answer_label": scene.result_card.answer_lbl.text(),
    }


@pytest.mark.parametrize("parents", [
    ("/Applications", "/Users/fixture/Applications"),
    ("/Applications", "/Users/fixture/Riot Games"),
], ids=["same-parent-basename", "different-parent-control"])
def test_v3_installations_with_same_parent_name_remain_distinguishable(app, parents):
    paths = [parent + "/League of Legends.app" for parent in parents]
    choices = [dict(name="League of Legends", path=p, bundle_id="com.fixture.league", version="1.0") for p in paths]
    artifact = Artifact("followup-choice", "input_request", payload=dict(operation_name="open_application",
        missing_fields=[], candidate_choices=choices, supplied_inputs={"name": "Liên Minh"}, prompt="Choose installation"))
    renderer = QtViewRenderer(StandardViewProvider().provide_view(artifact), artifact)
    renderer.setFixedWidth(420)
    renderer.show()
    base._pump(4)
    try:
        buttons = [b for b in renderer.findChildren(QPushButton) if b.objectName() == "CandidateBtn"]
        assert len(buttons) == 2 and all(b.isVisible() for b in buttons)
        assert all(p in b.toolTip() for p, b in zip(paths, buttons))
        assert len(set(b.text() for b in buttons)) == 2, [b.text() for b in buttons]
    finally:
        renderer.close()
        renderer.deleteLater()
        base._pump(2)
