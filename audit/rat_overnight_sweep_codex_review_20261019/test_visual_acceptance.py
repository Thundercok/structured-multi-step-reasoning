"""Independent V2/V3/V4 acceptance probes. Fixtures only; no real inference/launch."""
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QPushButton, QStyle, QStyleOptionButton

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("overnight_visual_base", ROOT / "tests/test_workbench_scene.py")
base = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = base
spec.loader.exec_module(base)
app, scene_window = base.app, base.scene_window

from rat.crawler.db import Database
from rat.engine.assistant_runtime import AssistantRuntime
from rat.engine.finder_intent import parse_finder_intent
from rat.engine.progressive_search import SearchHit, SearchSnapshot
from rat.engine.selected_document_qa import answer_selected_document
from rat.kernel.contracts import Artifact
from rat.kernel.view_spec import StandardViewProvider
from rat.timetable.compositor import TimetableCompositor
from rat.ui.view_renderer import QtViewRenderer


@pytest.mark.parametrize("long_answer", [False, True], ids=["short-full-bubble", "long-truncated-control"])
def test_v2_result_card_visibility_tracks_bubble(scene_window, tmp_path, long_answer):
    win = scene_window
    db = Database(str(tmp_path / "index.db"))
    path = tmp_path / "fixture.txt"
    path.write_text("Verification code LOTUS-7319.")
    db.upsert_document(dict(file_path=str(path), file_name=path.name, file_ext='.txt',
        file_size=path.stat().st_size, created_at=1, modified_at=1, indexed_at=1,
        content_text=path.read_text(), summary="Synthetic source"))
    answer_text = "LOTUS-7319" if not long_answer else "Code LOTUS-7319. " * 90
    client = Mock()
    client.chat_with_meta.return_value = dict(message={"content": answer_text}, done_reason="stop",
        prompt_tokens=20, completion_tokens=4, error=None)
    runtime = AssistantRuntime(db=db, compositor=TimetableCompositor([]), use_live_model=True)
    previous_runtime = win.assistant_runtime
    win.assistant_runtime = runtime
    try:
        win._submit_chat_prompt("What code?", selected_document_path=str(path))
        handle = win._assistant_handle
        response = answer_selected_document(runtime, "What code?", str(path), model_client=client,
            turn_ref=handle["turn_ref"], execution_id=handle["execution_id"])
        assert response.error is None and response.reconciliation.all_satisfied
        win._on_assistant_response(handle, response)
        base._pump(8)
        scene, bubble = win.workbench_scene, win.workbench_speech_bubble
        assert scene.mode == "overview" and scene.current_snapshot.phase == "done"
        assert scene.result_card.answer_lbl.text() == answer_text.strip()
        assert bubble._copy_text.strip() == answer_text.strip()
        assert bubble._truncated is long_answer
        assert all(a.kind in {"document_content", "book_page_content", "document_search", "book_page_search"}
                   for a in response.artifacts)
        assert not any(not r.isHidden() for r in scene.artifact_panel.renderers.values())
        assert scene.result_card.isHidden() is (not long_answer), (
            f"Full short bubble must not duplicate the answer on the desk: "
            f"truncated={bubble._truncated}, card_hidden={scene.result_card.isHidden()}"
        )
    finally:
        win.assistant_runtime = previous_runtime
        db.get_connection().close()


@pytest.mark.parametrize("query,expect_trace", [
    ("Slide DSA sửa tuần trước", True), ("DSA", False),
], ids=["structured-finder", "bare-query-control"])
def test_v4_structured_finder_shows_quiet_trace(scene_window, tmp_path, query, expect_trace):
    scene_window._show_interaction_surface()
    scene = scene_window.workbench_scene
    scene.reset(generation=21)
    path = tmp_path / "DSA.pptx"
    path.write_text("Synthetic slide.")
    intent = parse_finder_intent(query, now=datetime(2026, 10, 19, 12,
        tzinfo=timezone(timedelta(hours=7))))
    hit = SearchHit("file:visual-probe", "file", path.name, str(path), "metadata")
    scene.set_finder_snapshot(SearchSnapshot(21, query, "lexical", (hit,), hit.resource_id,
        True, 1.0, intent=intent))
    base._pump(4)
    assert scene.current_snapshot.phase == "empty"
    assert scene.finder_box.isVisible()
    assert bool(scene.current_snapshot.reasoning_flow) is expect_trace
    assert not scene.trace_expanded
    assert scene.trace_box.isVisible() is expect_trace, (
        f"Structured Finder flow should expose its collapsed toggle: "
        f"steps={len(scene.current_snapshot.reasoning_flow)}, visible={scene.trace_box.isVisible()}"
    )


@pytest.mark.parametrize("width", [620, 420])
def test_v3_candidate_buttons_have_distinguishable_visible_labels(app, width):
    common = "/private/var/folders/xb/k2ck7tjx0j5gskqznf3ql7480000gn/T/fixture-installations/"
    paths = [common + folder + "/League of Legends.app" for folder in ("Applications", "Riot Games")]
    choices = [dict(name="League of Legends", path=p, bundle_id="com.fixture.league", version="1.0")
               for p in paths]
    artifact = Artifact("visual-choice", "input_request", payload=dict(operation_name="open_application",
        missing_fields=[], candidate_choices=choices, supplied_inputs={"name": "Liên Minh"}, prompt="Choose installation"))
    renderer = QtViewRenderer(StandardViewProvider().provide_view(artifact), artifact)
    renderer.setFixedWidth(width)
    renderer.show()
    base._pump(4)
    try:
        buttons = [b for b in renderer.findChildren(QPushButton) if b.objectName() == "CandidateBtn"]
        assert len(buttons) == 2
        received = []
        renderer.input_submitted.connect(lambda op, values: received.append((op, values)))
        visible_labels = []
        diagnostics = []
        for index, button in enumerate(buttons):
            assert button.isVisible() and not button.visibleRegion().isEmpty()
            assert paths[index] in button.toolTip()
            assert artifact.payload["candidate_choices"][index]["path"] == paths[index]
            button.click()
            option = QStyleOptionButton()
            button.initStyleOption(option)
            contents = button.style().subElementRect(QStyle.SubElement.SE_PushButtonContents, option, button)
            # Native QPushButton paints a single line. Find the readable prefix
            # inside its actual style content rect, before the shared path ends.
            text, fm = button.text(), button.fontMetrics()
            prefix = ""
            for char in text:
                if fm.horizontalAdvance(prefix + char) > contents.width():
                    break
                prefix += char
            visible_labels.append(prefix)
            diagnostics.append(dict(text=text, readable_prefix=prefix, content_width=contents.width(),
                                    text_width=fm.horizontalAdvance(text)))
        assert [v[1]["selected_candidate"] for v in received] == [0, 1]
        assert len(set(visible_labels)) == 2, diagnostics
    finally:
        renderer.close()
        renderer.deleteLater()
        base._pump(2)
