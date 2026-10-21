"""Tests for the Argon native WorkbenchScene (`RAT_WORKBENCH_SCENE=1`)."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton, QScrollArea, QWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from rat.engine.assistant_runtime import AgentResponse, AgentStep
from rat.kernel.contracts import Artifact
from rat.ui.omnibar import OmnibarWindow
from rat.ui.surface_layout import ChatComposer
from rat.ui.workbench import WorkbenchActorWidget, WorkbenchThoughtTrail, WorkbenchTokens
from rat.ui.workbench_scene import (
    MAX_PRIMARY_DESK_OBJECTS,
    WorkSceneProjector,
    sanitize_error_text,
    sanitize_public_text,
    workbench_scene_enabled,
)

_APP: QApplication | None = None


def _ensure_app() -> QApplication:
    global _APP
    inst = QApplication.instance()
    if inst is None:
        inst = QApplication([])
    _APP = inst
    return inst


@pytest.fixture(scope="module", autouse=True)
def app() -> QApplication:
    return _ensure_app()


def _pump(rounds: int = 4) -> None:
    qapp = _ensure_app()
    for _ in range(rounds):
        qapp.processEvents()


def _find_scroll_area_ancestor(widget: QWidget, stop_at: QWidget | None = None) -> QScrollArea | None:
    cur = widget.parentWidget()
    while cur is not None and cur is not stop_at:
        if isinstance(cur, QScrollArea):
            return cur
        cur = cur.parentWidget()
    return None


def assert_not_clipped(widget: QWidget, container: QWidget, *, label: str = "") -> None:
    """
    Verify widget is visible, not clipped horizontally outside its container or viewport,
    and vertically reachable via scroll area if present with a non-empty visibleRegion.
    """
    _pump(4)
    tag = label or widget.objectName() or type(widget).__name__
    assert widget.isVisible(), f"{tag} should be visible"
    rect = widget.rect()
    assert rect.width() > 0 and rect.height() > 0, f"{tag} has zero geometry: {rect}"

    parent = widget.parentWidget()
    if parent is not None:
        top_left_in_parent = widget.mapToParent(rect.topLeft())
        bottom_right_in_parent = widget.mapToParent(rect.bottomRight())
        assert top_left_in_parent.x() >= -2, f"{tag} clipped on left inside parent: {top_left_in_parent.x()}"
        assert top_left_in_parent.y() >= -2, f"{tag} clipped on top inside parent: {top_left_in_parent.y()}"
        assert bottom_right_in_parent.x() <= parent.width() + 4, (
            f"{tag} overflows parent width ({bottom_right_in_parent.x()} > {parent.width()})"
        )

    scroll_area = _find_scroll_area_ancestor(widget, container)
    bound_target = scroll_area.viewport() if scroll_area is not None else container
    tl = widget.mapTo(bound_target, rect.topLeft())
    br = widget.mapTo(bound_target, rect.bottomRight())
    assert tl.x() >= -2, f"{tag} clipped left of bound target ({tl.x()})"
    assert br.x() <= bound_target.width() + 4, (
        f"{tag} clipped right of bound target ({br.x()} > {bound_target.width()})"
    )

    if scroll_area is not None:
        content_widget = scroll_area.widget()
        if content_widget is not None:
            target_y = widget.mapTo(content_widget, rect.topLeft()).y()
            scroll_area.verticalScrollBar().setValue(target_y)
            _pump(2)
            scrolled_tl = widget.mapTo(scroll_area.viewport(), rect.topLeft())
            assert -4 <= scrolled_tl.y() < scroll_area.viewport().height(), (
                f"{tag} not reachable in viewport: {scrolled_tl.y()}"
            )
            assert not widget.visibleRegion().isEmpty(), f"{tag} visibleRegion is empty after scrolling into view"
    else:
        assert tl.y() >= -2, f"{tag} clipped above bound target ({tl.y()})"
        assert br.y() <= bound_target.height() + 4, (
            f"{tag} clipped below bound target ({br.y()} > {bound_target.height()})"
        )


def _close_window(win: OmnibarWindow) -> None:
    if hasattr(win, "search_thread") and win.search_thread is not None:
        try:
            if win.search_thread.isRunning():
                win.search_thread.quit()
                win.search_thread.wait(600)
        except Exception:
            pass
    win.shutdown()
    win.close()
    win.deleteLater()
    _pump(4)


@pytest.fixture
def scene_window(app, monkeypatch):
    monkeypatch.setenv("RAT_WORKBENCH_SCENE", "1")
    monkeypatch.setenv("RAT_REDUCE_MOTION", "1")
    app.setProperty("ratReduceMotion", True)
    with (
        patch("rat.ui.omnibar.Database") as mock_db,
        patch("rat.ui.omnibar.SearchEngine"),
        patch("rat.ui.feedback.FeedbackLog"),
        patch("rat.ui.assistant_worker.AssistantWorker.start"),
        patch("rat.engine.slm.slm_engine.is_service_running", return_value=False),
    ):
        mock_db.return_value.get_stats.return_value = {"total_files": 0}
        mock_db.return_value.get_recent_documents.return_value = []
        win = OmnibarWindow()
        win._apply_assistant_model = lambda: None
        win.show()
        win.switch_section(0)
        QTest.qWait(25)
        try:
            yield win
        finally:
            _close_window(win)
    app.setProperty("ratReduceMotion", False)


def test_flag_gating_and_no_feature_toggle_in_default_ui(monkeypatch):
    """Default UI keeps workbench_scene off and adds no feature toggle button."""
    _ensure_app()
    monkeypatch.delenv("RAT_WORKBENCH_SCENE", raising=False)
    assert not workbench_scene_enabled()

    with (
        patch("rat.ui.omnibar.Database") as mock_db,
        patch("rat.ui.omnibar.SearchEngine"),
        patch("rat.ui.feedback.FeedbackLog"),
        patch("rat.ui.assistant_worker.AssistantWorker.start"),
        patch("rat.engine.slm.slm_engine.is_service_running", return_value=False),
    ):
        mock_db.return_value.get_stats.return_value = {"total_files": 0}
        mock_db.return_value.get_recent_documents.return_value = []
        win_default = OmnibarWindow()
        try:
            win_default.show()
            win_default._show_interaction_surface()
            _pump(4)
            assert not win_default.workbench_scene_enabled
            assert not win_default.workbench_scene.isVisible()
            assert win_default.chat_stream.isVisible()
            for btn in win_default.findChildren(QPushButton):
                assert "workbench_scene" not in btn.text().lower()
                assert "argon" not in btn.text().lower()
        finally:
            _close_window(win_default)

        monkeypatch.setenv("RAT_WORKBENCH_SCENE", "1")
        assert workbench_scene_enabled()
        win_scene = OmnibarWindow()
        try:
            win_scene.show()
            win_scene._show_interaction_surface()
            _pump(4)
            assert win_scene.workbench_scene_enabled
            assert win_scene.workbench_scene.isVisible()
            assert not win_scene.chat_stream.isVisible()
        finally:
            _close_window(win_scene)


def test_projector_sanitization_progress_and_overflow_grouping():
    """Projector sanitizes private fields, maps progress without fake %/ETA, and caps primary desk objects at <=5."""
    raw = (
        "Thought: secret chain of thought\n"
        '{"tool": "read_document", "arguments": {"path": "/Users/alice/secret.pdf"}}\n'
        "Kết luận công khai: Học phần yêu cầu tối thiểu 15 tín chỉ."
    )
    cleaned = sanitize_public_text(raw)
    assert "secret chain of thought" not in cleaned
    assert '"arguments"' not in cleaned
    assert "/Users/alice/" not in cleaned
    assert "Kết luận công khai" in cleaned

    err_clean = sanitize_error_text("Traceback (most recent call last):\nFile /Users/alice/private/db.py: timeout")
    assert "Traceback" not in err_clean
    assert "/Users/alice/private" not in err_clean

    proj = WorkSceneProjector()
    snap = proj.begin_turn("Kiểm tra 7 nguồn tài liệu", generation=1, execution_id="exec-1", turn_id="1")
    assert snap.phase == "working"
    assert "%" not in snap.phase_label
    assert "ETA" not in snap.phase_label

    # Progress phase must not fabricate tool names, percentages, or ETA
    proj.record_progress("Đang đọc tài liệu...", generation=1, execution_id="exec-1")
    snap_prog = proj.snapshot()
    assert "%" not in snap_prog.phase_label
    assert "ETA" not in snap_prog.phase_label

    # Add 7 document sources in a search step
    docs = [
        {
            "path": f"/tmp/tai_lieu_{i}.pdf",
            "filename": f"tai_lieu_{i}.pdf",
            "snippet": f"Tóm tắt nội dung tài liệu số {i}.",
        }
        for i in range(1, 8)
    ]
    step_search = AgentStep(
        step_number=1,
        thought="INTERNAL SECRET THOUGHT DO NOT SHOW",
        tool_name="search_documents",
        tool_args={"query": "tài liệu", "raw_prompt": "secret"},
        tool_result=docs,
        raw_completion='{"thought": "secret"}',
    )
    proj.record_step(step_search, generation=1, execution_id="exec-1")

    # Add an excerpt step on source 1
    step_read = AgentStep(
        step_number=2,
        thought="ANOTHER SECRET THOUGHT",
        tool_name="read_document",
        tool_args={"path": "/tmp/tai_lieu_1.pdf", "start_line": 10, "end_line": 24},
        tool_result={
            "found": True,
            "path": "/tmp/tai_lieu_1.pdf",
            "filename": "tai_lieu_1.pdf",
            "start_line": 10,
            "end_line": 24,
            "total_chars": 120,
            "content": "Điều 12: Sinh viên đăng ký học phần trước tuần học thứ hai.",
        },
        raw_completion="secret raw completion",
    )
    proj.record_step(step_read, generation=1, execution_id="exec-1")

    snap1 = proj.snapshot()
    total_primary_objects = (
        len(snap1.primary_sources)
        + (1 if snap1.active_excerpt else 0)
        + (1 if snap1.result_node else 0)
    )
    assert total_primary_objects <= MAX_PRIMARY_DESK_OBJECTS
    assert len(snap1.primary_sources) + len(snap1.overflow_sources) == 7
    assert len(snap1.overflow_sources) >= 3

    # Verify positions (order_index) stay stable when another step updates source 2
    before_order = [s.node_id for s in sorted(proj._sources.values(), key=lambda x: x.order_index)]
    step_read_2 = AgentStep(
        step_number=3,
        thought="secret",
        tool_name="read_document",
        tool_args={"path": "/tmp/tai_lieu_2.pdf", "start_line": 1, "end_line": 8},
        tool_result={
            "found": True,
            "path": "/tmp/tai_lieu_2.pdf",
            "filename": "tai_lieu_2.pdf",
            "start_line": 1,
            "end_line": 8,
            "total_chars": 50,
            "content": "Phụ lục A: Biểu mẫu đăng ký.",
        },
    )
    proj.record_step(step_read_2, generation=1, execution_id="exec-1")
    after_order = [s.node_id for s in sorted(proj._sources.values(), key=lambda x: x.order_index)]
    assert before_order == after_order


def test_grounded_edges_only_and_no_cooccurrence_fabrication(scene_window):
    """Relationships are drawn ONLY when backed by real refs; co-occurrence in a turn draws 0 causal edges."""
    win = scene_window
    win._show_interaction_surface()
    store = win.assistant_runtime.artifact_store
    scene = win.workbench_scene

    scene.begin_turn(
        "Tìm tệp và tính toán độc lập",
        generation=1,
        execution_id="exec-co",
        turn_id=1,
        artifact_store=store,
    )

    # Step 1: observed a file via search_documents (no excerpt read yet)
    scene.on_step(
        AgentStep(
            step_number=1,
            thought="secret",
            tool_name="search_documents",
            tool_result=[{"path": "/tmp/hoc_phi.txt", "filename": "hoc_phi.txt", "snippet": "Mức thu học phí"}],
        ),
        generation=1,
        execution_id="exec-co",
        artifact_store=store,
    )
    # Step 2: created a calculation artifact in the same turn, WITHOUT source_refs pointing to hoc_phi.txt
    calc_res = win.assistant_runtime.dispatcher.execute_operation("calculate", {"expression": "15 * 650000"})
    assert calc_res.artifact is not None
    scene.on_step(
        AgentStep(
            step_number=2,
            thought="secret",
            tool_name="calculate",
            tool_result=calc_res.result,
            artifacts=[calc_res.artifact],
        ),
        generation=1,
        execution_id="exec-co",
        artifact_store=store,
    )
    _pump(3)

    # Co-occurrence in the same turn must NOT create any causal/derivation edge
    assert scene.current_snapshot.edges == []
    assert scene.group_caption.isVisible()
    assert not scene.relations_widget.isVisible()


def test_journey_1_real_file_overview_and_source_drilldown(scene_window, tmp_path):
    """
    Journey 1 (Tệp thật):
    - Real file on disk indexed in runtime DB -> search_documents -> read_document -> overview shows source & excerpt
    - Drill into source via click AND via composer command ('xem nguồn 1' / 'quay lại')
    - Preserves composer draft, text selection, cursor position, focus, and overview scroll
    - 0 model calls and 0 extra file reads during drill-down
    - Explicit 'Mở tệp' opens observed path (never auto-opened); missing file disables open & shows clear message
    """
    win = scene_window
    real_doc = tmp_path / "so_tay_hoc_vu_2026.txt"
    doc_lines = [
        "Điều 1: Quy định đăng ký học phần học kỳ chính.",
        "Điều 2: Sinh viên được đăng ký tối đa 24 tín chỉ và tối thiểu 14 tín chỉ mỗi học kỳ.",
        "Điều 3: Thời hạn rút bớt học phần là trước tuần học thứ 6.",
        "Điều 4: Điểm đánh giá quá trình chiếm trọng số từ 30% đến 50%.",
    ]
    real_doc.write_text("\n".join(doc_lines), encoding="utf-8")

    # Configure runtime's db to recognize the real file on disk
    win.assistant_runtime.db = MagicMock()
    win.assistant_runtime.db.get_document_by_path.side_effect = (
        lambda p: {"file_path": str(real_doc), "file_name": real_doc.name} if p == str(real_doc) else None
    )

    # Execute real read_document through OperationDispatcher (creates real document_content Artifact in ArtifactStore!)
    ctx = {"db": win.assistant_runtime.db, "compositor": win.assistant_runtime.compositor}
    read_dispatch = win.assistant_runtime.dispatcher.execute_operation(
        "read_document",
        {"file_path": str(real_doc), "max_chars": 3000},
        context=ctx,
    )
    assert read_dispatch.status == "success"
    assert read_dispatch.artifact is not None

    # Start turn through OmnibarWindow callbacks
    turn_snap = win._conversation.begin_turn("Tối đa bao nhiêu tín chỉ mỗi học kỳ?")
    handle = win.chat_stream.create_streaming_message(
        strategy="Assistant", badge="Đang xử lý", turn_id=turn_snap.turn_ref.turn_id
    )
    handle["generation"] = win._chat_generation
    handle["turn_ref"] = turn_snap.turn_ref
    handle["execution_id"] = turn_snap.execution_id
    handle["observed_sources"] = []
    win._assistant_handle = handle
    win._pending_chat_query = "Tối đa bao nhiêu tín chỉ mỗi học kỳ?"
    win._show_interaction_surface()
    win.workbench_scene.begin_turn(
        win._pending_chat_query,
        generation=win._chat_generation,
        execution_id=turn_snap.execution_id,
        turn_id=turn_snap.turn_ref.turn_id,
        artifact_store=win.assistant_runtime.artifact_store,
    )

    win._on_assistant_progress(handle, "Đang tìm tài liệu trong máy...")
    step1 = AgentStep(
        step_number=1,
        thought="private thought 1",
        tool_name="search_documents",
        tool_result=[{"path": str(real_doc), "filename": real_doc.name, "snippet": doc_lines[1]}],
    )
    win._on_assistant_step(handle, step1)

    step2 = AgentStep(
        step_number=2,
        thought="private thought 2",
        tool_name="read_document",
        tool_result=read_dispatch.result,
        artifacts=[read_dispatch.artifact],
    )
    win._on_assistant_step(handle, step2)
    _pump(4)

    scene = win.workbench_scene
    snap = scene.current_snapshot
    assert scene.mode == "overview"
    assert len(snap.primary_sources) >= 1
    src_node = snap.primary_sources[0]
    assert src_node.file_path == str(real_doc)
    assert "ký tự" in src_node.scope_label
    assert snap.active_excerpt is not None
    assert any(e.kind == "file_contains_excerpt" for e in snap.edges)
    assert_not_clipped(scene._source_cards[src_node.node_id], scene, label="source_card_0")
    assert_not_clipped(scene.excerpt_card, scene, label="excerpt_card")

    # Note on IME: Native OS IME composition sessions are validated separately in native Cocoa
    # acceptance testing. Here we test draft text, selection range, and cursor preservation via setText/setSelection.
    composer = win.chat_composer_input
    composer.setFocus()
    draft_text = "Đang gõ dở câu hỏi: còn học kỳ hè thì sao?"
    composer.setText(draft_text)
    composer.setSelection(5, 13)
    _pump(2)
    sel_start = composer.selectionStart()
    sel_text = composer.selectedText()
    assert sel_text == draft_text[5:18]

    # Guard against model calls, extra disk reads, and auto-opening file during source drill-down
    opened_paths: list[str] = []
    scene.on_open_file = lambda p: opened_paths.append(p)
    with (
        patch.object(win.assistant_runtime, "tool_read_document", side_effect=AssertionError("Must not read disk on drill-down")),
        patch.object(win.assistant_runtime, "run", side_effect=AssertionError("Must not call model on drill-down")),
    ):
        # 1. Real mouse click on source card to drill down
        card = scene._source_cards[src_node.node_id]
        QTest.mouseClick(card, Qt.MouseButton.LeftButton)
        _pump(4)

        assert scene.mode == "source_detail"
        assert opened_paths == [], "Drilling into source must NEVER auto-open the file"
        assert composer.text() == draft_text
        assert composer.selectionStart() == sel_start
        assert composer.selectedText() == sel_text
        assert_not_clipped(scene.detail_header, scene, label="detail_header")
        assert_not_clipped(scene.detail_renderer_host, scene, label="detail_renderer_host")

        # Return to overview via back button
        scene.btn_back_overview.click()
        _pump(4)
        assert scene.mode == "overview"
        assert composer.text() == draft_text
        assert composer.selectedText() == sel_text

        # 2. Real keyboard navigation (Enter key on focused source card)
        card = scene._source_cards[src_node.node_id]
        card.setFocus()
        _pump(2)
        QTest.keyClick(card, Qt.Key.Key_Return)
        _pump(4)
        assert scene.mode == "source_detail"
        assert composer.text() == draft_text

        scene.btn_back_overview.click()
        _pump(4)
        assert scene.mode == "overview"

        # 3. Drill down via composer command submission ('xem nguồn 1') and back ('quay lại')
        composer.setText("xem nguồn 1")
        win._submit_chat_prompt(composer.text())
        _pump(4)
        assert scene.mode == "source_detail"

        composer.setText("quay lại")
        win._submit_chat_prompt(composer.text())
        _pump(4)
        assert scene.mode == "overview"

        # Direct scene command handling without submitting chat
        assert scene.try_handle_scene_command("xem nguồn 1")
        _pump(3)
        assert scene.mode == "source_detail"

        assert scene.try_handle_scene_command("quay lại")
        _pump(3)
        assert scene.mode == "overview"

        # Restore draft text and selection for the rest of the flow
        composer.setText(draft_text)
        composer.setSelection(5, 13)
        _pump(2)

    # Complete the turn with a committed answer -> related source compacts to reference posture
    resp = AgentResponse(
        answer="Theo Điều 2 trong so_tay_hoc_vu_2026.txt, sinh viên được đăng ký tối đa 24 tín chỉ và tối thiểu 14 tín chỉ.",
        steps=[step1, step2],
        total_time_ms=180.0,
        tool_call_count=2,
        token_estimate=42,
        sources=handle["observed_sources"],
        artifacts=[read_dispatch.artifact],
    )
    win._on_assistant_response(handle, resp)
    _pump(8)
    win._fit_surface()
    _pump(4)

    snap_done = scene.current_snapshot
    assert snap_done.phase == "done"
    assert snap_done.result_node is not None
    assert snap_done.result_node.status == "ready"
    assert snap_done.primary_sources[0].is_compact_ref
    # Under Spec V2, full short bubble does not duplicate the answer on the desk
    assert scene.result_card.isHidden(), "ResultDeskCard should be collapsed when speech bubble displays the full short answer"
    assert scene.result_card.answer_lbl.text() == resp.answer
    assert win.workbench_speech_bubble._copy_text.strip() == resp.answer
    assert not win.workbench_speech_bubble._truncated

    # Explicit 'Mở tệp' in source_detail opens the exact observed path
    scene.select_source(src_node.node_id)
    _pump(3)
    scene.btn_detail_open_file.click()
    _pump(2)
    assert opened_paths == [str(real_doc)]

    # Delete the file on disk -> re-entering source_detail marks it missing and disables 'Mở tệp'
    real_doc.unlink()
    scene.show_overview()
    scene.select_source(src_node.node_id)
    _pump(3)
    assert not scene.btn_detail_open_file.isEnabled()
    assert "Tệp không còn trên máy" in scene.btn_detail_open_file.text()
    assert "Tệp không còn trên máy" in scene.detail_scope_lbl.text()


def test_journey_2_derived_result_revision_and_renderer_identity(scene_window):
    """
    Journey 2 (Sửa kết quả):
    - Uses registered operations (calculate -> compose_result_table)
    - Updating input updates the same Artifact ID & revision in-place without duplicating composer or QtViewRenderer
    - Preserves renderer view_state() across revision updates
    - Draws grounded edges (artifact_derived_from_ref, revision_supersedes) and flags stale/missing refs
    """
    win = scene_window
    win._show_interaction_surface()
    dispatcher = win.assistant_runtime.dispatcher
    store = win.assistant_runtime.artifact_store
    scene = win.workbench_scene

    # 1. Create natal chart artifact (v1) and derived result_table (v1)
    natal_v1 = dispatcher.execute_operation(
        "create_natal_chart",
        {
            "name": "Nguyễn Văn A",
            "date": "2000-01-01",
            "time": "08:00",
            "place": "TP Hồ Chí Minh",
            "latitude": 10.8231,
            "longitude": 106.6297,
            "timezone": "Asia/Ho_Chi_Minh",
        },
    )
    assert natal_v1.artifact is not None
    assert natal_v1.artifact.revision == 1

    table_v1 = dispatcher.execute_operation(
        "compose_result_table",
        {
            "title": "Bảng tổng hợp hồ sơ",
            "headers": ["Tiêu đề", "Giờ sinh"],
            "rows": [
                [
                    {"artifact_id": natal_v1.artifact.id, "revision": 1, "field": "title"},
                    {"artifact_id": natal_v1.artifact.id, "revision": 1, "field": "chart.birth.time"},
                ]
            ],
        },
        context={"artifact_store": store},
    )
    assert table_v1.artifact is not None
    assert table_v1.artifact.revision == 1

    win._on_artifact_result(win._chat_generation, natal_v1)
    win._on_artifact_result(win._chat_generation, table_v1)
    _pump(4)

    # Check single composer and single renderer per artifact
    assert table_v1.artifact.id in scene.artifact_panel.renderers
    assert natal_v1.artifact.id in scene.artifact_panel.renderers
    renderer_natal_v1 = scene.artifact_panel.renderers[natal_v1.artifact.id]
    assert renderer_natal_v1.artifact.revision == 1
    natal_renderer_id = id(renderer_natal_v1)
    view_state_v1 = renderer_natal_v1.view_state()
    assert "details" in view_state_v1

    # Grounded edge: artifact_derived_from_ref must exist between natal_v1 and table_v1
    edge_kinds_v1 = {e.kind for e in scene.current_snapshot.edges}
    assert "artifact_derived_from_ref" in edge_kinds_v1

    # Non-revision progress update preserves renderer object identity and disclosure choices
    win._on_assistant_progress(win._latest_assistant_handle, "Đang xử lý đối chiếu...")
    _pump(3)
    assert id(scene.artifact_panel.renderers[natal_v1.artifact.id]) == natal_renderer_id, (
        "Renderer object identity must be preserved across unrelated progress updates"
    )

    # 2. Update natal chart artifact in-place (revision 1 -> 2) via registered action (Đổi giờ sinh)
    actions = win.assistant_runtime.registry.actions_for(natal_v1.artifact)
    edit_action = next(a for a in actions if a.operation_name == "update_birth_data")
    natal_v2 = dispatcher.dispatch(edit_action, {"time": "09:30"}, win._artifact_context())
    assert natal_v2.artifact is not None
    assert natal_v2.artifact.id == natal_v1.artifact.id
    assert natal_v2.artifact.revision == 2

    win._on_artifact_result(win._chat_generation, natal_v2)
    _pump(4)

    # Renderer is updated in-place without duplicating composers or renderers
    assert len([k for k in scene.artifact_panel.renderers if k == natal_v2.artifact.id]) == 1
    renderer_natal_v2 = scene.artifact_panel.renderers[natal_v2.artifact.id]
    assert renderer_natal_v2.artifact.id == natal_v1.artifact.id
    assert renderer_natal_v2.artifact.revision == 2
    view_state_v2 = renderer_natal_v2.view_state()
    assert view_state_v2["details"] == view_state_v1["details"], (
        "Captured view_state (disclosure choices) must survive revision updates"
    )

    # Because table_v1 still references natal@v1 while natal is now at v2, table_v1's ref is flagged stale!
    res_node_stale = scene.current_snapshot.result_node
    assert res_node_stale is not None
    assert any(r.get("stale") for r in res_node_stale.source_refs)
    assert any("bản cũ" in e.label for e in scene.current_snapshot.edges if e.kind == "artifact_derived_from_ref")

    # 3. Create updated table (v2) referencing natal_v2
    table_v2 = dispatcher.execute_operation(
        "compose_result_table",
        {
            "title": "Bảng tổng hợp hồ sơ (cập nhật)",
            "headers": ["Tiêu đề", "Giờ sinh"],
            "rows": [
                [
                    {"artifact_id": natal_v2.artifact.id, "revision": 2, "field": "title"},
                    {"artifact_id": natal_v2.artifact.id, "revision": 2, "field": "chart.birth.time"},
                ]
            ],
        },
        context={"artifact_store": store},
    )
    assert table_v2.artifact is not None

    win._on_artifact_result(win._chat_generation, table_v2)
    _pump(4)

    assert not any(r.get("stale") for r in scene.current_snapshot.result_node.source_refs)
    edge_kinds_v2 = {e.kind for e in scene.current_snapshot.edges}
    assert "artifact_derived_from_ref" in edge_kinds_v2
    assert "revision_supersedes" in edge_kinds_v2

    # 4. Verify missing reference handling: artifact referencing a non-existent source_id
    orphan_art = Artifact(
        id="art_orphan",
        kind="result_table",
        title="Bảng thiếu nguồn",
        payload={"rows": [], "source_refs": [{"artifact_id": "non_existent_999", "revision": 1}]},
        provenance={"operation_name": "compose_result_table", "source_refs": [{"artifact_id": "non_existent_999", "revision": 1}]},
        revision=1,
    )
    store.put(orphan_art)
    win._refresh_latest_assistant_panel(orphan_art)
    _pump(3)
    assert any(r.get("missing") for r in scene.current_snapshot.result_node.source_refs)
    assert not any(
        "non_existent_999" in e.source_id and e.kind == "artifact_derived_from_ref"
        for e in scene.current_snapshot.edges
    )


def test_stop_late_callbacks_partial_error_and_new_turn_isolation(scene_window):
    """
    Verify:
    - Stopping preserves completed sources/excerpts on the desk
    - Late callbacks (progress, step, response) from a stopped execution are rejected
    - Starting a new turn after stop is clean and unaffected by late callbacks from the old turn
    - Partial step error keeps prior observed sources and sanitizes error text
    """
    win = scene_window
    scene = win.workbench_scene

    # Turn 1 starts and completes 1 search step before user stops
    turn1 = win._conversation.begin_turn("Tìm tài liệu quy chế")
    handle1 = win.chat_stream.create_streaming_message(
        strategy="Assistant", badge="Đang xử lý", turn_id=turn1.turn_ref.turn_id
    )
    handle1["generation"] = win._chat_generation
    handle1["turn_ref"] = turn1.turn_ref
    handle1["execution_id"] = turn1.execution_id
    handle1["observed_sources"] = []
    win._assistant_handle = handle1
    win._pending_chat_query = "Tìm tài liệu quy chế"

    class DummyWorker:
        def requestInterruption(self):
            pass

    win._current_reasoner = DummyWorker()
    scene.begin_turn(
        "Tìm tài liệu quy chế",
        generation=handle1["generation"],
        execution_id=handle1["execution_id"],
        turn_id=turn1.turn_ref.turn_id,
    )

    step_ok = AgentStep(
        step_number=1,
        thought="secret",
        tool_name="search_documents",
        tool_result=[{"path": "/tmp/quy_che_a.pdf", "filename": "quy_che_a.pdf", "snippet": "Quy chế A"}],
    )
    win._on_assistant_step(handle1, step_ok)
    assert len(scene.current_snapshot.primary_sources) == 1

    # Partial error step before stop: keeps quy_che_a.pdf and sanitizes error
    step_err = AgentStep(
        step_number=2,
        thought="secret",
        tool_name="read_document",
        tool_result={"found": False, "error": "Traceback (most recent call last):\nFile /Users/private/secret.pdf permission denied"},
        error="Traceback (most recent call last):\nFile /Users/private/secret.pdf permission denied",
    )
    win._on_assistant_step(handle1, step_err)
    assert len(scene.current_snapshot.primary_sources) == 1
    assert "/Users/private" not in scene.current_snapshot.phase_label

    # User stops Turn 1
    win._cancel_assistant()
    _pump(3)
    assert scene.current_snapshot.phase == "cancelled"
    assert len(scene.current_snapshot.primary_sources) == 1, "Completed work must be preserved on stop"

    # Late callbacks from Turn 1 arrive after stop -> must be rejected
    late_step = AgentStep(
        step_number=3,
        thought="late secret",
        tool_name="search_documents",
        tool_result=[{"path": "/tmp/late_ghost.pdf", "filename": "late_ghost.pdf", "snippet": "Ghost"}],
    )
    win._on_assistant_progress(handle1, "Late progress that must be ignored")
    win._on_assistant_step(handle1, late_step)
    win._on_assistant_response(
        handle1,
        AgentResponse(
            answer="Late answer must be ignored",
            steps=[late_step],
            total_time_ms=10.0,
            tool_call_count=1,
            token_estimate=10,
            sources=[{"path": "/tmp/late_ghost.pdf"}],
        ),
    )
    _pump(2)
    assert all("late_ghost" not in s.title for s in scene.all_sources())
    assert scene.current_snapshot.phase == "cancelled"

    # Turn 2 starts after stop -> late callbacks from Turn 1 still rejected and cannot pollute Turn 2
    turn2 = win._conversation.begin_turn("Yêu cầu mới sau khi dừng")
    handle2 = win.chat_stream.create_streaming_message(
        strategy="Assistant", badge="Đang xử lý", turn_id=turn2.turn_ref.turn_id
    )
    handle2["generation"] = win._chat_generation
    handle2["turn_ref"] = turn2.turn_ref
    handle2["execution_id"] = turn2.execution_id
    handle2["observed_sources"] = []
    win._assistant_handle = handle2
    win._pending_chat_query = "Yêu cầu mới sau khi dừng"
    scene.begin_turn(
        "Yêu cầu mới sau khi dừng",
        generation=handle2["generation"],
        execution_id=handle2["execution_id"],
        turn_id=turn2.turn_ref.turn_id,
    )
    win._on_assistant_step(handle1, late_step)
    assert all("late_ghost" not in s.title for s in scene.all_sources())
    assert scene.current_snapshot.query == "Yêu cầu mới sau khi dừng"


def test_narrow_reflow_hide_show_and_reduced_motion(scene_window, monkeypatch):
    """
    Verify:
    - Integrated window resized to actual 420px triggers narrow mode (<= 450px)
    - Essential controls and results remain reachable and visible after scrolling in narrow mode
    - Hiding window stops all animations/timers (0 background animations)
    - Reduced motion completes transitions immediately with 0 running animations
    """
    win = scene_window
    win._show_interaction_surface()
    scene = win.workbench_scene

    # Start a turn with a source and result so we can test narrow scroll reachability
    turn_snap = win._conversation.begin_turn("Kiểm tra giao diện hẹp 420px")
    scene.begin_turn(
        "Kiểm tra giao diện hẹp 420px",
        generation=win._chat_generation,
        execution_id=turn_snap.execution_id,
        turn_id=turn_snap.turn_ref.turn_id,
    )
    step1 = AgentStep(
        step_number=1,
        thought="thinking",
        tool_name="search_documents",
        tool_result=[{"path": "/tmp/tai_lieu_hep.pdf", "filename": "tai_lieu_hep.pdf", "snippet": "Tài liệu hẹp"}],
    )
    win.workbench_scene.on_step(step1, generation=win._chat_generation, execution_id=turn_snap.execution_id)
    resp = AgentResponse(
        answer="Kết quả hiển thị trên màn hình hẹp 420px với đầy đủ các thao tác cần thiết. " * 15,
        steps=[step1],
        total_time_ms=60.0,
        tool_call_count=1,
        token_estimate=20,
        sources=[{"path": "/tmp/tai_lieu_hep.pdf"}],
    )
    win.workbench_speech_bubble.set_reply(resp.answer, "Đã xong", copy_text=resp.answer)
    win.workbench_scene.on_response(resp, generation=win._chat_generation, execution_id=turn_snap.execution_id)
    _pump(4)

    # Physically resize the integrated window to 420px
    win.resize(420, 520)
    _pump(4)

    assert win.width() == 420
    assert win._is_narrow(win.width()) is True
    assert scene.is_narrow is True

    # Verify result card and actions are reachable by scrolling without horizontal overflow
    assert_not_clipped(scene.result_card, scene, label="narrow_result_card")
    scene.overview_scroll.ensureWidgetVisible(scene.result_card)
    _pump(2)
    assert not scene.result_card.visibleRegion().isEmpty()

    # Trigger wide detail layout (~640px)
    win.resize(640, 560)
    scene.set_presentation(expanded=True, narrow=False)
    _pump(3)
    assert scene.is_expanded is True
    assert scene.is_narrow is False

    # Hiding the window must stop any active scene animations
    win.hide()
    _pump(2)
    assert scene.active_animation_count() == 0

    win.show()
    _pump(2)
    monkeypatch.setenv("RAT_REDUCE_MOTION", "1")
    scene.begin_turn("Kiểm tra reduced motion", generation=99, execution_id="exec-rm", turn_id=99)
    assert scene.active_animation_count() == 0


def test_detail_view_state_preserved_during_unrelated_progress(scene_window):
    """
    Regression test for review finding 2:
    - While in source_detail, unrelated progress and step updates must NOT recreate or re-borrow the renderer
    - Preserves renderer object identity
    - Preserves disclosure collapsed/expanded choices
    - Preserves detail scroll position
    - Preserves composer draft, text selection, and focus
    """
    win = scene_window
    win._show_interaction_surface()
    dispatcher = win.assistant_runtime.dispatcher
    scene = win.workbench_scene

    # 1. Create natal chart artifact (v1) and derived result_table (v1)
    natal_v1 = dispatcher.execute_operation(
        "create_natal_chart",
        {
            "name": "Trần Thị B",
            "date": "1998-05-15",
            "time": "14:30",
            "place": "Đà Nẵng",
            "latitude": 16.0544,
            "longitude": 108.2022,
            "timezone": "Asia/Ho_Chi_Minh",
        },
    )
    assert natal_v1.artifact is not None

    table_v1 = dispatcher.execute_operation(
        "compose_result_table",
        {
            "title": "Bảng tổng hợp chi tiết",
            "headers": ["Tiêu đề", "Giờ sinh"],
            "rows": [
                [
                    {"artifact_id": natal_v1.artifact.id, "revision": 1, "field": "title"},
                    {"artifact_id": natal_v1.artifact.id, "revision": 1, "field": "chart.birth.time"},
                ]
            ],
        },
        context={"artifact_store": win.assistant_runtime.artifact_store},
    )
    assert table_v1.artifact is not None

    win._on_artifact_result(win._chat_generation, natal_v1)
    win._on_artifact_result(win._chat_generation, table_v1)
    _pump(4)

    # Start a turn
    turn_snap = win._conversation.begin_turn("Tra cứu hồ sơ tử vi chi tiết")
    handle = win.chat_stream.create_streaming_message(
        strategy="Assistant", badge="Đang xử lý", turn_id=turn_snap.turn_ref.turn_id
    )
    handle["generation"] = win._chat_generation
    handle["turn_ref"] = turn_snap.turn_ref
    handle["execution_id"] = turn_snap.execution_id
    handle["observed_sources"] = []
    handle["artifacts"] = {natal_v1.artifact.id: natal_v1.artifact, table_v1.artifact.id: table_v1.artifact}
    win._assistant_handle = handle

    # Establish matching generation/execution/turn ownership on workbench scene
    scene.begin_turn(
        "Tra cứu hồ sơ tử vi chi tiết",
        generation=win._chat_generation,
        execution_id=turn_snap.execution_id,
        turn_id=turn_snap.turn_ref.turn_id,
        artifact_store=win.assistant_runtime.artifact_store,
    )

    src_node = next(s for s in scene.all_sources() if s.artifact_id == natal_v1.artifact.id)
    assert scene.select_source(src_node.node_id)
    _pump(4)
    assert scene.mode == "source_detail"

    # Identify renderer and disclosures
    ren = scene.artifact_panel.renderers[natal_v1.artifact.id]
    orig_ren_id = id(ren)
    assert len(ren.disclosures) > 0, "Natal chart renderer should have disclosure widgets"

    # Collapse the first disclosure explicitly
    first_disc_key = list(ren.disclosures.keys())[0]
    ren.disclosures[first_disc_key].set_open(False, animate=False)
    _pump(2)
    assert not ren.disclosures[first_disc_key].opened

    # Ensure detail view is genuinely scrollable and set scroll position
    win.resize(600, 360)
    _pump(4)
    max_scroll = scene.detail_scroll.verticalScrollBar().maximum()
    assert max_scroll > 0, "Detail view must be genuinely scrollable"
    scroll_target = min(30, max_scroll)
    scene.detail_scroll.verticalScrollBar().setValue(scroll_target)
    orig_scroll = scene.detail_scroll.verticalScrollBar().value()
    assert orig_scroll == scroll_target and orig_scroll > 0

    # Set composer draft, selection, and focus
    composer = win.chat_composer_input
    composer.setFocus()
    draft_msg = "Câu hỏi tiếp theo: kiểm tra vận hạn 2026"
    composer.setText(draft_msg)
    composer.setSelection(4, 12)
    _pump(2)
    assert composer.hasFocus()
    orig_sel_start = composer.selectionStart()
    orig_sel_len = len(composer.selectedText())
    assert orig_sel_start == 4
    assert orig_sel_len == 12

    # Snapshot disclosure states before unrelated progress
    disc_states_before = {k: d.opened for k, d in ren.disclosures.items()}

    # 2. Deliver unrelated progress update
    win._on_assistant_progress(handle, "Đang đối chiếu dữ kiện khác...")
    _pump(4)
    # Assert progress was accepted with observable scene change
    assert scene.current_snapshot.phase_label == "Đang đối chiếu dữ kiện khác..."
    assert win.workbench_speech_bubble.dialogue.text() == "Đang đối chiếu dữ kiện khác..."

    # 3. Deliver unrelated step (e.g. calculation)
    unrelated_step = AgentStep(
        step_number=2,
        thought="thinking",
        tool_name="calculate",
        tool_result={"expression": "2026 - 1998", "result": "28"},
    )
    win._on_assistant_step(handle, unrelated_step)
    _pump(4)
    # Assert step was accepted with observable trace change
    assert any(e.number == 2 for e in scene.current_snapshot.trace_entries)

    # 4. Assertions:
    assert scene.mode == "source_detail"
    # Renderer object identity must NOT change
    current_ren = scene.artifact_panel.renderers[natal_v1.artifact.id]
    assert id(current_ren) == orig_ren_id, "Renderer object identity must be preserved across unrelated progress"

    # Disclosure state must NOT have been forced open
    assert current_ren.disclosures[first_disc_key].opened is False
    for k, is_opened in disc_states_before.items():
        assert current_ren.disclosures[k].opened == is_opened, f"Disclosure {k} state was altered by progress"

    # Scroll value must survive
    assert scene.detail_scroll.verticalScrollBar().value() == orig_scroll

    # Composer draft, selection, and focus must survive
    assert composer.text() == draft_msg
    assert composer.selectionStart() == orig_sel_start
    assert len(composer.selectedText()) == orig_sel_len
    assert composer.hasFocus()


def test_theme_transition_light_dark_readable(scene_window):
    win = scene_window
    dispatcher = win.assistant_runtime.dispatcher
    store = win.assistant_runtime.artifact_store

    natal_v1 = dispatcher.execute_operation(
        "create_natal_chart",
        {
            "name": "Lê Văn C",
            "date": "1995-12-01",
            "time": "10:15",
            "place": "Hà Nội",
            "latitude": 21.0285,
            "longitude": 105.8542,
            "timezone": "Asia/Ho_Chi_Minh",
        },
    )
    table_v1 = dispatcher.execute_operation(
        "compose_result_table",
        {
            "title": "Bảng tổng hợp hồ sơ",
            "headers": ["Tiêu đề", "Giờ sinh"],
            "rows": [
                [
                    {"artifact_id": natal_v1.artifact.id, "revision": 1, "field": "title"},
                    {"artifact_id": natal_v1.artifact.id, "revision": 1, "field": "chart.birth.time"},
                ]
            ],
        },
        context={"artifact_store": store},
    )
    win._on_artifact_result(win._chat_generation, natal_v1)
    win._on_artifact_result(win._chat_generation, table_v1)
    _pump(4)

    from PyQt6.QtWidgets import QTableWidget
    from PyQt6.QtGui import QColor
    from rat.ui.workbench import WorkbenchTokens

    def luminance(color: QColor) -> float:
        def channel_lum(val: float) -> float:
            c = val / 255.0
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * channel_lum(color.red()) + 0.7152 * channel_lum(color.green()) + 0.0722 * channel_lum(color.blue())

    def contrast_ratio(c1: QColor, c2: QColor) -> float:
        l1, l2 = luminance(c1), luminance(c2)
        top, bot = max(l1, l2), min(l1, l2)
        return (top + 0.05) / (bot + 0.05)

    # 1. Light Mode Verification
    app = QApplication.instance()
    app.setProperty("ratDarkMode", False)
    win._apply_theme()
    _pump(4)

    light_tokens = WorkbenchTokens.get(dark=False)
    assert win.workbench_canvas.title_lbl.styleSheet().find(light_tokens.ink_hex) >= 0

    table_widget = win.findChild(QTableWidget)
    assert table_widget is not None, "A mounted QTableWidget must be present"
    assert table_widget.styleSheet().find(light_tokens.ink_hex) >= 0

    assert contrast_ratio(light_tokens.ink, light_tokens.paper) >= 4.5
    assert contrast_ratio(light_tokens.muted, light_tokens.paper) >= 3.0

    # 2. Transition: Light -> Dark Mode
    app.setProperty("ratDarkMode", True)
    win._apply_theme()
    _pump(4)

    dark_tokens = WorkbenchTokens.get(dark=True)
    assert win.workbench_canvas.title_lbl.styleSheet().find(dark_tokens.ink_hex) >= 0
    assert win.workbench_speech_bubble.dialogue.styleSheet().find(dark_tokens.ink_hex) >= 0
    assert win.chat_composer_input.styleSheet().find(dark_tokens.ink_hex) >= 0
    comp_pal = win.chat_composer_input.palette()
    assert comp_pal.color(comp_pal.ColorRole.Text).name() == dark_tokens.ink.name()

    assert table_widget.styleSheet().find(dark_tokens.ink_hex) >= 0
    assert table_widget.styleSheet().find(dark_tokens.line_hex) >= 0

    assert contrast_ratio(dark_tokens.ink, dark_tokens.paper) >= 4.5
    assert contrast_ratio(dark_tokens.muted, dark_tokens.paper) >= 3.0

    # 3. Transition: Dark -> Light Mode
    app.setProperty("ratDarkMode", False)
    win._apply_theme()
    _pump(4)

    assert win.workbench_speech_bubble.dialogue.styleSheet().find(light_tokens.ink_hex) >= 0
    assert win.chat_composer_input.styleSheet().find(light_tokens.ink_hex) >= 0
    assert table_widget.styleSheet().find(light_tokens.ink_hex) >= 0


def test_actor_thought_bubble_working_motion_and_reduced_motion(app):
    app.setProperty("ratReduceMotion", False)
    actor = WorkbenchActorWidget()
    actor.show()
    trail = WorkbenchThoughtTrail(actor)
    trail.show()
    _pump(3)

    # 1. Scaled sizes (~8-12% increase from 104, 132, 80)
    assert actor.actor_w == 114
    assert actor.slot_w == 118
    actor.set_presentation(expanded=True, narrow=False)
    assert actor.actor_w == 145
    assert actor.slot_w == 154
    actor.set_presentation(expanded=False, narrow=True)
    assert actor.actor_w == 84
    assert actor.slot_w == 88

    actor.set_presentation(expanded=False, narrow=False)
    trail.set_presentation(expanded=False, narrow=False)

    # 2. Idle state: thought trail is static, timer not running
    actor.reaction = ""
    actor.set_state("idle")
    trail.set_state("idle")
    assert actor.current_state == "idle"
    assert trail.current_state == "idle"
    assert not trail.timer.isActive()

    # 3. Working state: thought trail timer is active
    actor.set_state("working")
    trail.set_state("working")
    assert actor.current_state == "working"
    assert trail.current_state == "working"
    assert trail.timer.isActive()

    # Paint event should render without error
    pix = QPixmap(trail.size())
    trail.render(pix)
    assert not pix.isNull()

    # 4. Reduced motion: timer stops, dots remain static
    app = QApplication.instance()
    app.setProperty("ratReduceMotion", True)
    trail._sync_timer()
    assert not trail.timer.isActive()
    trail.render(pix)
    app.setProperty("ratReduceMotion", False)

    # 5. Done state: stops working motion, trail remains visible and static
    trail.set_state("done")
    assert trail.current_state == "done"
    assert not trail.timer.isActive()
    trail.render(pix)
    assert not pix.isNull()

    trail.close()
    actor.close()


def test_composer_ime_composition_skips_intermediate_search():
    from PyQt6.QtGui import QInputMethodEvent

    composer = ChatComposer()
    assert composer.is_composing() is False

    # Simulate IME composition preedit
    ev = QInputMethodEvent("liên minh", [])
    composer.inputMethodEvent(ev)
    assert composer.is_composing() is True

    # Commit event
    ev_commit = QInputMethodEvent("", [])
    ev_commit.setCommitString("liên minh")
    composer.inputMethodEvent(ev_commit)
    assert composer.is_composing() is False
    composer.close()


def test_progressive_finder_composer_integration_flow(scene_window, tmp_path):
    import plistlib
    from rat.crawler.db import Database
    from rat.engine.app_resolver import ApplicationCatalog
    from rat.engine.progressive_search import ProgressiveSearch, SearchCoordinator, SearchSnapshot

    # Create synthetic app bundle
    apps_dir = tmp_path / "Apps"
    apps_dir.mkdir(parents=True)
    app_path = apps_dir / "League of Legends.app"
    (app_path / "Contents" / "MacOS").mkdir(parents=True)
    (app_path / "Contents" / "Info.plist").write_bytes(plistlib.dumps(dict(
        CFBundleIdentifier="com.riot.league",
        CFBundleName="League of Legends",
        CFBundleExecutable="fixture-bin"
    )))
    (app_path / "Contents" / "MacOS" / "fixture-bin").write_text("synthetic")

    catalog = ApplicationCatalog.scan([apps_dir])

    # Create synthetic database
    db_file = tmp_path / "test_finder.db"
    db = Database(str(db_file))
    doc_path = tmp_path / "lien_minh_notes.txt"
    doc_path.write_text("Workshop TCP notes and gameplay documentation")
    db.upsert_document(dict(
        file_path=str(doc_path),
        file_name="lien_minh_notes.txt",
        file_ext=".txt",
        file_size=len(doc_path.read_text()),
        created_at=1,
        modified_at=10,
        indexed_at=1,
        content_text=doc_path.read_text(),
        summary="Synthetic notes summary",
    ))

    win = scene_window
    win.workbench_finder_enabled = True
    win._finder_catalog = catalog
    win._finder_search = ProgressiveSearch(str(db_file), catalog=catalog)
    win._finder_coordinator = SearchCoordinator(
        win._finder_search,
        on_update=lambda snap: win._finder_bridge.snapshot_ready.emit(snap),
    )

    scene = win.workbench_scene
    finder_box = scene.finder_box
    assert not finder_box.isVisible()

    # 1. Type query in composer -> triggers coordinator.submit
    win.chat_composer_input.setText("liên minh")
    for _ in range(40):
        _pump(2)
        if finder_box.isVisible():
            break
        QTest.qWait(25)

    # Suggestions are now visible on the Workbench scene
    assert finder_box.isVisible()
    assert finder_box.snapshot is not None
    assert len(finder_box.snapshot.hits) >= 2  # app + file

    # 2. Check items and selection preservation by resource_id
    initial_sel = finder_box.selected_resource_id
    assert initial_sel is not None
    assert finder_box.current_hit() is not None

    # Simulate arrival of an augmented/refined snapshot
    # Selection should stay on initial_sel
    augmented_hits = list(finder_box.snapshot.hits)
    new_snap = SearchSnapshot(
        query_id=finder_box.snapshot.query_id,
        query="liên minh",
        phase="semantic",
        hits=tuple(augmented_hits),
        selected_id=initial_sel,
        complete=True,
        elapsed_ms=5.0,
    )
    win._on_finder_snapshot_delivered(new_snap)
    assert finder_box.selected_resource_id == initial_sel

    # 3. Keyboard navigation: Down arrow moves selection
    old_id = finder_box.selected_resource_id
    finder_box.navigate(1)
    new_id = finder_box.selected_resource_id
    assert new_id != old_id

    # Up arrow returns to composer if at top
    finder_box.navigate(-1)
    assert finder_box.selected_resource_id == old_id
    can_up = finder_box.navigate(-1)
    assert can_up is False  # signals boundary reached to return focus

    # 4. Action: click "Hỏi" on the file hit
    file_hit = next(h for h in finder_box.snapshot.hits if h.kind == "file")
    row = finder_box._rows[file_hit.resource_id]
    assert hasattr(row, "btn_ask")
    row.btn_ask.click()
    _pump(4)

    # Selected document path is set for question
    assert win._selected_document_path == file_hit.path
    assert win.chat_composer_input.hasFocus()

    # Submitting a question now asks about the file and dismisses suggestions
    win.chat_composer_input.setText("tóm tắt tệp này")
    win._submit_chat_prompt("tóm tắt tệp này")
    _pump(4)

    assert win._pending_chat_query == "tóm tắt tệp này"
    assert not finder_box.isVisible()


def test_milestone_b_compact_workbench_labels_space_reclamation_and_button_geometry(scene_window, tmp_path):
    import plistlib
    from rat.crawler.db import Database
    from rat.engine.app_resolver import ApplicationCatalog
    from rat.engine.progressive_search import ProgressiveSearch, SearchRequest

    win = scene_window
    canvas = win.workbench_canvas
    scene = win.workbench_scene

    # 1. Idle / fresh compact state: redundant hero heading ("Không gian làm việc") is hidden,
    # mode_lbl does not show redundant "Workbench" text, and chrome height is compact.
    assert not canvas.heading_row.isVisible()
    assert canvas.mode_lbl.text() == ""
    assert canvas.chrome_height() <= 42

    # 2. Finder search state: hero heading remains hidden while filter chips & rows are visible
    apps_dir = tmp_path / "Apps"
    apps_dir.mkdir(parents=True)
    app_path = apps_dir / "League of Legends.app"
    (app_path / "Contents" / "MacOS").mkdir(parents=True)
    (app_path / "Contents" / "Info.plist").write_bytes(plistlib.dumps(dict(
        CFBundleIdentifier="com.riotgames.leagueoflegends",
        CFBundleName="League of Legends",
        CFBundleShortVersionString="14.20",
        CFBundleExecutable="lol-bin",
    )))
    (app_path / "Contents" / "MacOS" / "lol-bin").write_text("bin")
    catalog = ApplicationCatalog.scan([apps_dir])

    db_file = tmp_path / "mb.db"
    db = Database(str(db_file))
    slide_path = tmp_path / "DSA_Slide_Week1.pptx"
    slide_path.write_text("DSA lecture slide content")
    db.upsert_document(dict(
        file_path=str(slide_path),
        file_name=slide_path.name,
        file_ext=".pptx",
        file_size=25,
        created_at=100,
        modified_at=200,
        indexed_at=200,
        content_text="DSA lecture slide content",
        summary="Slide bài giảng DSA tuần 1",
    ))

    engine = ProgressiveSearch(str(db_file), catalog=catalog)
    try:
        win.workbench_finder_enabled = True
        snap_app = engine.initial(SearchRequest(1, "liên minh"))
        win._on_finder_snapshot_delivered(snap_app)
        _pump(4)

        assert scene.finder_box.isVisible()
        assert not canvas.heading_row.isVisible(), "Finder search must not show redundant 'Không gian làm việc' hero heading"

        snap_slide = engine.initial(SearchRequest(2, "Slide DSA"))
        win._on_finder_snapshot_delivered(snap_slide)
        _pump(4)
        assert scene.finder_box.intent_lbl.isVisible()
        assert "Slide" in scene.finder_box.intent_lbl.text()

        # Verify all 4 file action buttons (Hỏi, Mở, Xem, ↗) and app buttons (Mở, ↗) have positive unclipped geometry at 620px and 420px
        for width in (620, 420):
            win._resize_overlay(width, 420)
            _pump(4)
            file_hit = next(h for h in scene.finder_box.snapshot.hits if h.kind == "file")
            file_row = scene.finder_box._rows[file_hit.resource_id]
            for btn in (file_row.btn_ask, file_row.btn_open, file_row.btn_preview, file_row.btn_reveal):
                assert btn.isVisible()
                assert btn.width() >= 20 and btn.height() >= 16
                assert not btn.visibleRegion().isEmpty()

            win._on_finder_snapshot_delivered(snap_app)
            _pump(4)
            app_hit = next(h for h in scene.finder_box.snapshot.hits if h.kind == "application")
            app_row = scene.finder_box._rows[app_hit.resource_id]
            for btn in (app_row.btn_open, app_row.btn_reveal):
                assert btn.isVisible()
                assert btn.width() >= 20 and btn.height() >= 16
                assert not btn.visibleRegion().isEmpty()
            win._on_finder_snapshot_delivered(snap_slide)
            _pump(4)

        # 3. Active task/result state: single work title in heading_row, chrome_row hidden in compact mode,
        # and ResultDeskCard.header_row hidden when QtViewRenderer already renders the artifact header.
        scene.clear_finder_snapshot()
        win._resize_overlay(620, 420)
        natal = win.assistant_runtime.dispatcher.execute_operation(
            "create_natal_chart",
            {
                "name": "Nguyễn Văn A",
                "date": "2000-01-01",
                "time": "08:00",
                "place": "TP.HCM",
                "latitude": 10.7769,
                "longitude": 106.7009,
                "timezone": "Asia/Ho_Chi_Minh",
            },
        )
        win._on_artifact_result(win._chat_generation, natal)
        _pump(4)

        assert canvas.heading_row.isVisible()
        assert not canvas.chrome_row.isVisible()
        assert not scene.result_card.header_row.isVisible()
    finally:
        engine.close_connection()
        db.get_connection().close()


def test_milestone_c_composer_natural_finder_and_checked_app_launch_ui(scene_window, tmp_path, monkeypatch):
    import plistlib
    import sys
    from PyQt6.QtWidgets import QPushButton
    from rat.crawler.db import Database
    from rat.engine.app_resolver import ApplicationCatalog
    from rat.engine.progressive_search import ProgressiveSearch, SearchCoordinator

    monkeypatch.setattr(sys, "platform", "darwin")

    def make_app(folder_name, app_name, bundle_id, version="1.0"):
        p = tmp_path / folder_name / f"{app_name}.app"
        (p / "Contents" / "MacOS").mkdir(parents=True, exist_ok=True)
        (p / "Contents" / "Info.plist").write_bytes(plistlib.dumps(dict(
            CFBundleIdentifier=bundle_id,
            CFBundleName=app_name,
            CFBundleShortVersionString=version,
            CFBundleExecutable="app-bin",
        )))
        (p / "Contents" / "MacOS" / "app-bin").write_text("binary")
        return p

    lol_primary = make_app("Apps1", "League of Legends", "com.riotgames.leagueoflegends", "14.21")
    riot_client = make_app("Apps1", "Riot Client", "com.riotgames.RiotClient", "88.0")
    catalog_single = ApplicationCatalog.scan([lol_primary.parent])

    db_file = tmp_path / "mc.db"
    db = Database(str(db_file))
    doc_path = tmp_path / "bao_cao_dsa.pdf"
    doc_path.write_text("Báo cáo DSA tuần trước")
    db.upsert_document(dict(
        file_path=str(doc_path),
        file_name=doc_path.name,
        file_ext=".pdf",
        file_size=24,
        created_at=100,
        modified_at=300,
        indexed_at=300,
        content_text="Báo cáo DSA tuần trước",
        summary="Báo cáo học thuật DSA",
    ))

    launched = []
    def fake_launcher(app):
        launched.append((app.name, app.path, app.bundle_id))
        return True, None

    win = scene_window
    win.workbench_finder_enabled = True
    win._finder_catalog = catalog_single
    win._app_launcher = fake_launcher
    win._finder_search = ProgressiveSearch(str(db_file), catalog=catalog_single)
    win._finder_coordinator = SearchCoordinator(
        win._finder_search,
        on_update=lambda snap: win._finder_bridge.snapshot_ready.emit(snap),
    )

    scene = win.workbench_scene
    finder_box = scene.finder_box

    try:
        # 1. Typing "mở Liên Minh" shows suggestions + intent chip, NEVER launches the app on keystroke
        win.chat_composer_input.setText("mở Liên Minh")
        for _ in range(40):
            _pump(2)
            if finder_box.isVisible():
                break
            QTest.qWait(20)

        assert finder_box.isVisible()
        assert finder_box.intent_lbl.isVisible()
        assert "Mở ứng dụng" in finder_box.intent_lbl.text()
        assert launched == [], "Typing in composer must never launch an application"

        # 2. Negation ("đừng mở Liên Minh") on submit must NOT launch any app
        win._submit_chat_prompt("đừng mở Liên Minh")
        _pump(6)
        assert launched == []
        assert "không mở" in win.workbench_speech_bubble.dialogue.text().lower()

        # 3. Active selected-document QA must not be hijacked by app/finder router
        win._selected_document_path = str(doc_path)
        win._submit_chat_prompt("mở phần kết luận trong tệp này")
        _pump(4)
        assert win._pending_chat_query == "mở phần kết luận trong tệp này"
        assert launched == []
        win._cancel_assistant()
        _pump(4)

        # 4. Explicit submit of "mở Liên Minh" with single verified installation launches League of Legends (not Riot Client)
        win._submit_chat_prompt("mở Liên Minh")
        for _ in range(40):
            _pump(2)
            if launched and win._artifact_worker is None:
                break
            QTest.qWait(20)
        _pump(4)

        assert launched == [("League of Legends", str(lol_primary.resolve()), "com.riotgames.leagueoflegends")]
        assert scene.current_snapshot.result_node is not None
        assert scene.current_snapshot.result_node.kind == "application_launch"
        assert "không đồng nghĩa" in scene.current_snapshot.rat_speech

        # 5. Multiple installations -> disambiguation card in Workbench, clicking candidate launches chosen bundle
        launched.clear()
        lol_secondary = make_app("Apps2", "League of Legends", "com.riotgames.leagueoflegends", "14.22")
        catalog_multi = ApplicationCatalog.scan([lol_primary.parent, lol_secondary.parent])
        win._finder_catalog = catalog_multi

        win._submit_chat_prompt("mở Liên Minh")
        for _ in range(40):
            _pump(2)
            if (
                win._artifact_worker is None
                and scene.current_snapshot.result_node is not None
                and scene.current_snapshot.result_node.kind == "input_request"
            ):
                break
            QTest.qWait(20)
        _pump(4)

        assert launched == []
        assert scene.current_snapshot.phase == "waiting"
        assert scene.current_snapshot.result_node.kind == "input_request"

        cand_btns = [
            b for b in scene.artifact_panel.findChildren(QPushButton)
            if b.objectName() == "CandidateBtn" and b.isVisible()
        ]
        assert len(cand_btns) == 2
        assert len(set(b.text() for b in cand_btns)) == 2
        target_btn = next(b for b in cand_btns if str(lol_secondary.resolve()) in b.toolTip())
        target_btn.click()

        for _ in range(40):
            _pump(2)
            if launched and win._artifact_worker is None:
                break
            QTest.qWait(20)
        _pump(4)

        assert launched == [("League of Legends", str(lol_secondary.resolve()), "com.riotgames.leagueoflegends")]
    finally:
        if win._finder_coordinator is not None:
            win._finder_coordinator.close()
        if win._finder_search is not None:
            win._finder_search.close_connection()
        db.get_connection().close()


def test_milestone_a_grounded_reasoning_flow_and_live_token_streaming(scene_window, tmp_path):
    """
    Milestone A (Section 1 & Section 4):
    - Grounded reasoning flow for:
      1) "mở Liên Minh" with 2 candidates -> found 2 candidates -> waiting ("chờ bạn chọn; chưa mở ứng dụng nào").
      2) "Slide DSA sửa tuần trước" -> deterministic interpretation (Loại: Slide, Sửa: Tuần trước) -> found index hits ("chưa đọc toàn bộ nội dung") with 0 model calls.
      3) Selected-document QA ("Hỏi tệp") -> TurnContract proposed -> read excerpt -> running live token stream -> verified_pass with honest scope note.
    - Never reads or exposes ModelStep.thought, raw_completion, or model_input.
    - Live token streaming updates ResultDeskCard and records first_ui_token_ms, submit_to_done_ms, and qa_telemetry.
    """
    import plistlib
    from rat.crawler.db import Database
    from rat.engine.app_resolver import ApplicationCatalog
    from rat.engine.completion import ExecutionJournal, OutcomeSpec, TurnContract, reconcile_turn
    from rat.engine.progressive_search import ProgressiveSearch

    def make_app(dir_name: str, app_name: str, bundle_id: str, version: str = "1.0") -> Path:
        root = tmp_path / dir_name
        bundle = root / f"{app_name}.app"
        contents = bundle / "Contents"
        macos = contents / "MacOS"
        macos.mkdir(parents=True, exist_ok=True)
        exe = macos / app_name
        exe.write_text("#!/bin/sh\n")
        with (contents / "Info.plist").open("wb") as fh:
            plistlib.dump(
                {
                    "CFBundleName": app_name,
                    "CFBundleDisplayName": app_name,
                    "CFBundleIdentifier": bundle_id,
                    "CFBundleExecutable": app_name,
                    "CFBundleShortVersionString": version,
                },
                fh,
            )
        return bundle

    lol_1 = make_app("A1", "League of Legends", "com.riotgames.leagueoflegends", "14.23")
    lol_2 = make_app("A2", "League of Legends", "com.riotgames.leagueoflegends", "14.22")
    catalog_multi = ApplicationCatalog.scan([lol_1.parent, lol_2.parent])

    db_file = tmp_path / "milestone_a_index.db"
    db = Database(str(db_file))
    slide_path = tmp_path / "DSA_Lecture_03.pptx"
    slide_path.write_text("Cây đỏ đen và bảng băm")
    from datetime import datetime, timedelta
    now_dt = datetime.now().astimezone()
    day_start = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    this_monday = day_start - timedelta(days=day_start.weekday())
    prev_monday = this_monday - timedelta(days=7)
    last_week_ts = int((prev_monday + timedelta(days=2)).timestamp())
    db.upsert_document(
        dict(
            file_path=str(slide_path),
            file_name=slide_path.name,
            file_ext=".pptx",
            file_size=64,
            created_at=last_week_ts - 86400,
            modified_at=last_week_ts,
            indexed_at=int(now_dt.timestamp()),
            content_text="Cây đỏ đen và bảng băm",
            summary="Slide bài giảng DSA tuần trước",
        )
    )

    win = scene_window
    win.workbench_finder_enabled = True
    win._finder_catalog = catalog_multi
    win._app_launcher = lambda app: (True, None)
    win._finder_search = ProgressiveSearch(str(db_file), catalog=catalog_multi)
    scene = win.workbench_scene

    try:
        # Case 1: "mở Liên Minh" with 2 candidates -> found -> waiting
        win._submit_chat_prompt("mở Liên Minh")
        for _ in range(40):
            _pump(2)
            if (
                win._artifact_worker is None
                and scene.current_snapshot.result_node is not None
                and scene.current_snapshot.result_node.kind == "input_request"
            ):
                break
            QTest.qWait(20)
        _pump(4)

        flow_app = scene.current_snapshot.reasoning_flow
        assert any(e.status == "found" and "2 ứng viên" in e.detail for e in flow_app)
        assert any(
            e.status == "waiting" and "Chưa mở ứng dụng nào" in e.detail
            for e in flow_app
        )

        # Case 2: "Slide DSA sửa tuần trước" -> deterministic intent + index hits (0 model calls)
        from rat.engine.progressive_search import SearchRequest
        scene.reset(generation=20)
        intent_snap = win._finder_search.initial(SearchRequest(2, "Slide DSA sửa tuần trước"))
        assert intent_snap is not None
        scene.set_finder_snapshot(intent_snap)
        flow_finder = scene.current_snapshot.reasoning_flow
        assert any(
            e.status == "found"
            and "Loại: Slide" in e.detail
            and "Tuần trước" in e.detail
            for e in flow_finder
        )
        assert any(
            e.status == "found" and "chưa đọc toàn bộ nội dung" in e.detail
            for e in flow_finder
        )

        # Case 3: Selected-document Q&A with forbidden private CoT guard, live streaming, and contract reconciliation
        class ForbiddenCoTStep:
            """Wrapper that raises AssertionError if thought, raw_completion, or model_input is ever read."""

            def __init__(self, inner: AgentStep):
                self._inner = inner

            @property
            def thought(self):
                raise AssertionError("Grounded reasoning flow must NEVER read AgentStep.thought")

            @property
            def raw_completion(self):
                raise AssertionError("Grounded reasoning flow must NEVER read AgentStep.raw_completion")

            @property
            def model_input(self):
                raise AssertionError("Grounded reasoning flow must NEVER read AgentStep.model_input")

            def __getattr__(self, name):
                return getattr(self._inner, name)

        contract = TurnContract(
            conversation_id="conv-qa-1",
            turn_id="turn-qa-1",
            execution_id="exec-qa-1",
            outcomes=[
                OutcomeSpec(
                    outcome_id="read_selected_doc",
                    kind="registered_effect",
                    effect_type="read_document",
                    expected_args={"file_path": str(slide_path)},
                    description=f"Đọc trích đoạn {slide_path.name}",
                ),
                OutcomeSpec(
                    outcome_id="answer_from_excerpt",
                    kind="response",
                    dependency_ids=["read_selected_doc"],
                    description=f"Trả lời câu hỏi từ trích đoạn đã đọc của {slide_path.name}",
                ),
            ],
            proposed_by="selected_document_qa",
        )

        snap_start = scene.begin_turn(
            "Nội dung chính của slide là gì?",
            generation=30,
            execution_id="exec-qa-1",
            turn_id="turn-qa-1",
            turn_contract=contract,
            artifact_store=win.assistant_runtime.artifact_store,
        )
        # Before read_document finishes, step 1 is 'running' and step 2 is 'proposed' ("Dự định: ...")
        assert [e.status for e in snap_start.reasoning_flow] == ["running", "proposed"]
        assert "Dự định:" in snap_start.reasoning_flow[1].title

        # Step 1: read_document completes with real artifact in ArtifactStore
        read_dispatch = win.assistant_runtime.dispatcher.execute_operation(
            "read_document",
            {"file_path": str(slide_path), "max_chars": 4000},
            context={"db": db, "compositor": win.assistant_runtime.compositor},
        )
        assert read_dispatch.status == "success"
        doc_art = read_dispatch.artifact
        assert doc_art is not None

        raw_step = AgentStep(
            step_number=1,
            thought="PRIVATE_CHAIN_OF_THOUGHT_DO_NOT_READ",
            tool_name="read_document",
            tool_args={"file_path": str(slide_path), "max_chars": 4000},
            tool_result=read_dispatch.result,
            raw_completion='{"thought":"PRIVATE_CHAIN_OF_THOUGHT_DO_NOT_READ"}',
            model_input={"messages": ["SECRET_PROMPT"]},
            execution_id="exec-qa-1",
            artifacts=[doc_art],
        )
        guarded_step = ForbiddenCoTStep(raw_step)
        assert scene.on_step(guarded_step, generation=30, execution_id="exec-qa-1")

        # After step 1, step 1 is 'read' with char range and artifact_id@v1; outcome 2 transitions to 'running'
        flow_after_read = scene.current_snapshot.reasoning_flow
        assert flow_after_read[0].status == "read"
        assert "22/22 ký tự" in flow_after_read[0].detail
        assert f"{doc_art.id}@v1" in flow_after_read[0].evidence_ref
        assert flow_after_read[1].status == "running"

        # Live token streaming updates ResultDeskCard and reasoning_flow ('running')
        assert scene.on_text_streamed("Slide trình bày ", generation=30, execution_id="exec-qa-1")
        assert scene.on_text_streamed("cây đỏ đen và bảng băm.", generation=30, execution_id="exec-qa-1")
        _pump(2)

        assert scene.current_snapshot.result_node is not None
        assert scene.current_snapshot.result_node.status == "working"
        assert scene.current_snapshot.result_node.answer_text == "Slide trình bày cây đỏ đen và bảng băm."
        assert scene.result_card.answer_lbl.isVisible()
        assert "cây đỏ đen và bảng băm" in scene.result_card.answer_lbl.text()
        assert any(
            e.status == "running" and "Đang ghi câu trả lời trực tiếp" in e.detail
            for e in scene.current_snapshot.reasoning_flow
        )

        # Reconcile turn contract and deliver final response with qa_telemetry
        journal = ExecutionJournal(
            conversation_id="conv-qa-1",
            turn_id="turn-qa-1",
            execution_id="exec-qa-1",
        )
        journal.record_operation(
            "read_document",
            {"file_path": str(slide_path), "max_chars": 4000},
            read_dispatch.result,
            committed=True,
            artifact_refs=[{"artifact_id": doc_art.id, "revision": doc_art.revision, "kind": doc_art.kind}],
            operation_call_id="step-1",
        )
        final_answer = "Slide trình bày cây đỏ đen và bảng băm."
        raw_final_step = AgentStep(
            step_number=2,
            thought="PRIVATE_FINAL_THOUGHT_DO_NOT_READ",
            raw_completion='{"final_answer":"Slide trình bày cây đỏ đen và bảng băm."}',
            model_input={"messages": ["SECRET_PROMPT_2"]},
            execution_id="exec-qa-1",
        )
        guarded_final_step = ForbiddenCoTStep(raw_final_step)
        recon = reconcile_turn(
            contract,
            journal,
            final_answer=final_answer,
            lifecycle="completed",
        )
        assert recon.all_satisfied

        qa_tel = {
            "read_ms": 2.4,
            "queue_ms": 0.5,
            "load_ms": 0.0,
            "lock_wait_ms": 0.2,
            "tokenize_ms": 1.8,
            "prefill_ms": 0.0,
            "cache_copy_ms": 0.3,
            "generation_ms": 35.0,
            "first_token_ms": 9.5,
            "decode_after_first_token_ms": 25.5,
            "total_ms": 37.4,
            "prompt_tokens": 110,
            "completion_tokens": 9,
            "reused_prefix_tokens": 88,
            "newly_submitted_tokens": 22,
            "prefix_already_prepared": True,
            "model_calls": 1,
        }
        resp = AgentResponse(
            answer=final_answer,
            steps=[guarded_step, guarded_final_step],
            total_time_ms=37.4,
            tool_call_count=1,
            token_estimate=119,
            sources=[
                {
                    "type": "document",
                    "title": slide_path.name,
                    "path": str(slide_path),
                    "read": True,
                    "read_chars": 22,
                    "total_chars": 22,
                    "truncated": False,
                }
            ],
            artifacts=[doc_art],
            turn_id="turn-qa-1",
            execution_id="exec-qa-1",
            turn_contract=contract,
            execution_journal=journal,
            reconciliation=recon,
            qa_telemetry=qa_tel,
        )
        assert scene.on_response(resp, generation=30, execution_id="exec-qa-1")
        _pump(2)

        flow_done = scene.current_snapshot.reasoning_flow
        statuses = [e.status for e in flow_done]
        assert "read" in statuses
        assert "done" in statuses
        assert "verified_pass" in statuses
        verified_entry = next(e for e in flow_done if e.status == "verified_pass")
        assert "không tự chứng minh suy diễn ngoài phần đã đọc" in verified_entry.detail

        # Expand trace details and verify badges + telemetry summary line
        scene.toggle_trace_details()
        _pump(2)
        trace_text = scene.trace_detail_lbl.text()
        assert "[Đã đọc]" in trace_text
        assert "[Đã xong]" in trace_text
        assert "[Kiểm tra đạt]" in trace_text
        assert "Đo lường: token đầu 10 ms · tổng 37 ms · 110→9 token (tái sử dụng 88)" in trace_text
        assert "PRIVATE_CHAIN_OF_THOUGHT_DO_NOT_READ" not in trace_text
        assert "SECRET_PROMPT" not in trace_text

        # Cancellation mid-stream marks active step as 'cancelled'
        scene.begin_turn("Câu hỏi bị hủy", generation=31, execution_id="exec-qa-2", turn_contract=contract)
        scene.on_text_streamed("Đang trả lời dở...", generation=31, execution_id="exec-qa-2")
        snap_cancel = scene.on_cancel(generation=31, execution_id="exec-qa-2")
        assert any(e.status == "cancelled" for e in snap_cancel.reasoning_flow)
    finally:
        if win._finder_search is not None:
            win._finder_search.close_connection()
        db.get_connection().close()




