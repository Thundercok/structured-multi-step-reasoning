"""Default desktop journeys on authored DB/catalog fixtures, no models or launches."""
import time
import threading
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from rat.engine.app_resolver import ApplicationCatalog
from rat.engine.progressive_search import SearchHit, SearchSnapshot
from rat.ui.omnibar import OmnibarWindow
from rat.ui.workbench_scene import workbench_finder_enabled, workbench_scene_enabled


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def until(app, predicate):
    deadline = time.monotonic() + 5
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert predicate()


@pytest.fixture
def window(app, tmp_path, monkeypatch):
    from rat.config import config
    from rat.ui import omnibar
    monkeypatch.delenv("RAT_WORKBENCH_SCENE", raising=False)
    monkeypatch.delenv("RAT_WORKBENCH_FINDER", raising=False)
    monkeypatch.setenv("RAT_REDUCE_MOTION", "1")
    monkeypatch.setattr(config, "db_path", str(tmp_path / "fixture.db"))
    monkeypatch.setattr(config, "document_model_path", "")
    monkeypatch.setattr(config, "document_model_preload", False)
    monkeypatch.setattr(omnibar, "load_club_members", lambda: [])
    monkeypatch.setattr(omnibar, "SearchEngine", Mock())
    monkeypatch.setattr("rat.ui.feedback.FeedbackLog", Mock())
    monkeypatch.setattr(ApplicationCatalog, "scan", classmethod(lambda cls, *a, **k: cls()))
    monkeypatch.setattr("rat.engine.slm.slm_engine.is_service_running", lambda: pytest.fail("GUI probed model service"))
    monkeypatch.setattr("rat.engine.slm.slm_engine.list_installed_models", lambda: [])
    obj = OmnibarWindow()
    obj.show_omnibar()
    until(app, lambda: obj.isVisible())
    yield obj
    obj.shutdown()
    obj.hide()
    obj.deleteLater()
    app.processEvents()


def test_standard_surface_and_explicit_compatibility_opt_out(app, monkeypatch):
    for name, check in (("RAT_WORKBENCH_SCENE", workbench_scene_enabled),
                        ("RAT_WORKBENCH_FINDER", workbench_finder_enabled)):
        monkeypatch.delenv(name, raising=False)
        assert check()
        monkeypatch.setenv(name, "0")
        assert not check()


def test_hidden_pages_are_lazy_and_reused(window):
    stack = window.content_stack
    assert set(stack._page_factories) == {2, 3, 4}
    assert not hasattr(window, "settings_assistant_combo")
    window.switch_section(4)
    page = window.settings_view
    assert 4 not in stack._page_factories
    assert hasattr(window, "settings_assistant_combo")
    window.switch_section(0)
    window.switch_section(4)
    assert window.settings_view is page


def test_hide_reopen_and_resize_keep_draft_selection_and_focus(window, app):
    editor = window.chat_composer_input
    editor.setText("Bản nháp tiếng Việt đang gõ")
    cursor = editor.textCursor()
    cursor.setPosition(4)
    cursor.setPosition(12, cursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    selection = cursor.selectedText()
    window.hide()
    window.show_omnibar()
    window.activateWindow()
    for expanded in (True, False, True, False):
        window.set_expanded(expanded)
        app.processEvents()
        assert editor.text() == "Bản nháp tiếng Việt đang gõ"
        assert editor.textCursor().selectedText() == selection
    assert QApplication.focusWidget() is editor


def test_face_stays_visible_above_composer_across_layout_changes(window, app):
    region = window.workbench_dialogue
    actor = region.actor
    editor = window.chat_composer_input
    editor.setText("Bản nháp vẫn ở đây")
    region.user_lane.set_last_user_query("Câu hỏi dài vẫn đọc được khi Chuột núp sau thanh chat. " * 5)
    for expanded, width in ((False, 620), (True, 820), (False, 440)):
        window.set_expanded(expanded)
        window.resize(width, window.height())
        QTest.qWait(40)  # The window fits its height on a queued Qt layout pass.
        app.processEvents()
        mask = actor.mask().boundingRect()
        assert actor.actor_w * .5 < mask.height() < actor.actor_w * .7
        assert actor.y() >= 0, (expanded, width, actor.geometry(), region.geometry(),
                                region.sizeHint(), region.minimumSizeHint())
        bar_top = region.user_lane.bubble.mapTo(region, QPoint(0, 0)).y()
        head = actor.mapTo(region, QPoint(actor.width() // 2, mask.height() - 8))
        assert region.childAt(head) is actor
        assert region.user_lane.last_text.text() == "Câu hỏi dài vẫn đọc được khi Chuột núp sau thanh chat. " * 5
        assert region.user_lane.last_turn_box.isHidden()
        covered = QPoint(head.x(), bar_top + 20)
        target = region.childAt(covered)
        assert target is not actor and target is not None
        assert region.user_lane.bubble.isAncestorOf(target)
        QTest.mouseClick(target, Qt.MouseButton.LeftButton)
        assert editor.hasFocus()
        assert editor.text() == "Bản nháp vẫn ở đây"
    QTest.mouseClick(actor, Qt.MouseButton.LeftButton,
                     pos=QPoint(actor.width() // 2, actor.mask().boundingRect().height() // 2))
    assert actor.reaction == "happy"


def test_visible_companion_frames_express_state_and_respect_reduced_motion(window, monkeypatch):
    from types import SimpleNamespace
    from rat.ui import workbench
    clock = {"now": 100.0}
    monkeypatch.setattr(workbench, "time", SimpleNamespace(monotonic=lambda: clock["now"]))
    actor = window.workbench_dialogue.actor
    actor.timer.stop()
    actor._motion_allowed = True
    actor._started = 98.8
    actor._reaction_at = 90.0
    actor.reaction = ""
    geometry = window.chat_composer_input.geometry()
    mask = actor.mask()

    def frame(state):
        actor.current_state = state
        return actor.grab().toImage()

    assert frame("thinking") != frame("waiting")
    actor.react("happy")
    actor.timer.stop()
    actor._motion_allowed = True
    clock["now"] = 100.2
    first = frame("idle")
    clock["now"] = 100.6
    assert frame("idle") != first
    assert window.chat_composer_input.geometry() == geometry
    assert actor.mask() == mask
    actor._motion_allowed = False
    assert frame("thinking") == frame("waiting")


def test_long_result_keeps_full_copy_and_visible_actions_across_resize(window, app, monkeypatch):
    from rat.engine.assistant_runtime import AgentResponse
    query = "Tổng hợp quy định đăng ký học phần"
    turn = window._conversation.begin_turn(query)
    handle = window.chat_stream.create_streaming_message(strategy="Assistant", badge="Đang xử lý",
        turn_id=turn.turn_ref.turn_id)
    handle.update(generation=window._chat_generation, turn_ref=turn.turn_ref,
        execution_id=turn.execution_id, observed_sources=[])
    window._assistant_handle = handle
    window._pending_chat_query = query
    window._show_interaction_surface()
    window.workbench_scene.begin_turn(query, generation=window._chat_generation,
        execution_id=turn.execution_id, turn_id=turn.turn_ref.turn_id,
        artifact_store=window.assistant_runtime.artifact_store)
    window._on_assistant_progress(handle, "Đang tổng hợp các quy định đã có…")
    QTest.qWait(40)
    region = window.workbench_dialogue
    assert region.actor.mask().boundingRect().height() == region._face_peek_height()

    answer = "Theo quy định đăng ký học phần.\n\n" + ("Học kỳ chính tối đa 24 tín chỉ; học kỳ hè tối đa 12 tín chỉ. " * 12).strip()
    window._on_assistant_response(handle, AgentResponse(answer, [], 0, 0, 0))
    full_answer = window.workbench_scene.current_snapshot.result_node.answer_text
    assert " ".join(full_answer.split()) == " ".join(answer.split())
    bubble = window.workbench_speech_bubble
    clipboard = Mock()
    monkeypatch.setattr(QApplication, "clipboard", lambda: clipboard)
    editor = window.chat_composer_input
    editor.setText("Bản nháp hỏi tiếp")
    editor.setSelection(0, len("Bản nháp"))
    for expanded, width in ((False, 620), (False, 440), (True, 820)):
        window.set_expanded(expanded)
        window.resize(width, window.height())
        QTest.qWait(40)
        assert bubble.action_row.isVisible()
        assert bubble.btn_copy.isHidden() and bubble.btn_hist.isVisible()
        assert window.workbench_scene.result_card.btn_copy.isVisible()
        assert len(bubble.dialogue.text()) < len(answer)
        assert window.workbench_scene.result_card.isVisible()
        assert window.workbench_scene.result_card.answer_lbl.text() == full_answer.strip()
        assert region.actor.mask().boundingRect().height() == region._face_peek_height()
        assert editor.text() == "Bản nháp hỏi tiếp"
        assert editor.selectedText() == "Bản nháp"
    window.workbench_scene.result_card.btn_copy.click()
    clipboard.setText.assert_called_once_with(answer)


def test_copy_feedback_resets_without_moving_result_actions(window, app, monkeypatch):
    from rat.engine.assistant_runtime import AgentResponse
    scene = window.workbench_scene
    scene.begin_turn('Giới hạn tín chỉ?', generation=0, execution_id='copy-ui')
    scene.on_response(AgentResponse('Học kỳ chính tối đa 24 tín chỉ.', [], 0, 0, 0),
        generation=0, execution_id='copy-ui')
    window._show_interaction_surface()
    window._sync_workbench_scene(animate=False)
    QTest.qWait(50)
    card = scene.result_card
    clipboard = Mock()
    monkeypatch.setattr(QApplication, 'clipboard', lambda: clipboard)
    before = card.btn_copy.geometry()
    card._copy_timer.setInterval(40)
    card.btn_copy.click()
    app.processEvents()
    clipboard.setText.assert_called_once_with('Học kỳ chính tối đa 24 tín chỉ.')
    assert card.btn_copy.text() == 'Đã chép ✓'
    assert card.btn_copy.accessibleName() == 'Đã sao chép kết quả'
    assert card.btn_copy.geometry() == before
    until(app, lambda: card.btn_copy.text() == 'Sao chép')
    assert card.btn_copy.geometry() == before
    card.btn_copy.click()
    scene.begin_turn('Còn học kỳ hè?', generation=0, execution_id='copy-ui-next')
    assert not card._copy_timer.isActive()
    assert card.btn_copy.text() == 'Sao chép'


def test_short_reply_stays_single_when_theme_changes(window, app):
    from rat.engine.assistant_runtime import AgentResponse
    scene = window.workbench_scene
    scene.begin_turn("Giới hạn tín chỉ?", generation=0, execution_id="short-ui")
    scene.on_response(AgentResponse("Học kỳ chính tối đa 24 tín chỉ.", [], 0, 0, 0),
        generation=0, execution_id="short-ui")
    window._show_interaction_surface()
    window._sync_workbench_scene(animate=False)
    previous = app.property("ratDarkMode")
    try:
        for dark in (False, True, False):
            app.setProperty("ratDarkMode", dark)
            window._apply_theme()
            QTest.qWait(20)
            assert scene.result_card.isVisible()
            assert not window.workbench_speech_bubble._truncated
            assert scene.result_card.answer_lbl.text() == "Học kỳ chính tối đa 24 tín chỉ."
            assert "24 tín chỉ" not in window.workbench_speech_bubble.dialogue.text()
    finally:
        app.setProperty("ratDarkMode", previous)


def add_file(window, tmp_path, name):
    path = tmp_path / name
    path.write_text("authored fixture")
    window.db.upsert_document(dict(file_path=str(path), file_name=name, file_ext=path.suffix,
        file_size=path.stat().st_size, created_at=1, modified_at=1, indexed_at=1,
        content_text="authored fixture", summary="fixture"))
    return path


def test_visual_flow_modes_source_navigation_and_result_first(window, app, tmp_path):
    from rat.engine.assistant_runtime import AgentResponse, AgentStep
    path = add_file(window, tmp_path, 'flow-source.txt')
    scene = window.workbench_scene
    scene.begin_turn('Đọc quy định', generation=0, execution_id='flow-ui')
    step = AgentStep(1, 'PRIVATE_THOUGHT_SENTINEL', tool_name='read_document',
        tool_result=dict(path=str(path), filename=path.name, content='Học kỳ chính tối đa 24 tín chỉ.',
                         total_chars=500, found=True, truncated=True))
    step.raw_completion = 'PRIVATE_COMPLETION_SENTINEL'
    step.model_input = 'PRIVATE_INPUT_SENTINEL'
    scene.on_step(step, generation=0, execution_id='flow-ui')
    window._show_interaction_surface()
    window._sync_workbench_scene(animate=False)
    window.set_expanded(True)
    QTest.qWait(40)
    assert scene.trace_expanded and scene.flow_view.isVisible()
    node = next(n for n in scene.flow_view.nodes.values() if n.entry.stage == 'read')
    assert node.status.text() == 'Đã đọc'
    assert 'phần đầu' in node.detail.text()
    assert node.source.isVisible()
    public = scene.trace_detail_lbl.text() + node.title.text() + node.detail.text()
    assert 'PRIVATE_' not in public
    editor = window.chat_composer_input
    editor.setText('Bản nháp hỏi tiếp')
    editor.setSelection(0, len('Bản nháp'))
    selected = editor.selectedText()
    node.source.click()
    assert scene.mode == 'source_detail'
    scene.show_overview()
    assert editor.text() == 'Bản nháp hỏi tiếp' and editor.selectedText() == selected
    assert next(n for n in scene.flow_view.nodes.values() if n.entry.stage == 'read') is node
    window.set_expanded(False)
    assert not scene.trace_expanded and scene.flow_view.isHidden()
    scene.toggle_trace_details()
    assert scene.flow_view.isVisible()

    scene.on_response(AgentResponse('Học kỳ chính tối đa 24 tín chỉ.', [step], 0, 1, 0),
        generation=0, execution_id='flow-ui')
    window._sync_workbench_scene(animate=False)
    assert scene.result_card.isVisible()
    assert scene.overview_layout.indexOf(scene.result_card) < scene.overview_layout.indexOf(scene.evidence_box)
    assert scene.evidence_box.isHidden() and scene.btn_sources_toggle.isVisible()
    scene.btn_sources_toggle.click()
    assert scene.evidence_box.isVisible()
    assert editor.text() == 'Bản nháp hỏi tiếp' and editor.selectedText() == selected


@pytest.mark.parametrize('animated', [False, True])
@pytest.mark.parametrize('mode', ['expanded', 'compact', 'narrow'])
def test_result_disclosures_fit_content_and_keep_chatbar_anchor(window, app, tmp_path, monkeypatch, animated, mode):
    from rat.engine.assistant_runtime import AgentResponse, AgentStep
    monkeypatch.setattr('rat.ui.omnibar.motion_enabled', lambda: animated)
    path = add_file(window, tmp_path, 'anchor-source.txt')
    scene = window.workbench_scene
    if mode == 'expanded':
        window.set_expanded(True)
    elif mode == 'narrow':
        window.resize(440, window.height())
        window._fit_surface()
    QTest.qWait(40)
    until(app, lambda: not hasattr(window, '_geom_anim') or window._geom_anim.state() != window._geom_anim.State.Running)
    QTest.qWait(30)
    editor = window.chat_composer_input
    editor.setText('Bản nháp hỏi tiếp')
    editor.setSelection(0, len('Bản nháp'))
    bar = window.workbench_user_lane.bubble
    anchor = bar.mapToGlobal(QPoint(0, bar.height())).y()

    def settled_height():
        QTest.qWait(30)
        def stopped():
            assert abs(bar.mapToGlobal(QPoint(0, bar.height())).y() - anchor) <= 1
            animation = getattr(window, '_geom_anim', None)
            return animation is None or animation.state() != animation.State.Running
        until(app, stopped)
        QTest.qWait(40)
        assert abs(bar.mapToGlobal(QPoint(0, bar.height())).y() - anchor) <= 1
        assert editor.text() == 'Bản nháp hỏi tiếp' and editor.selectedText() == 'Bản nháp'
        return window.height()

    scene.begin_turn('Đọc giới hạn tín chỉ', generation=0, execution_id='anchor-ui')
    step = AgentStep(1, '', tool_name='read_document', tool_result=dict(path=str(path),
        filename=path.name, content='Học kỳ chính tối đa 24 tín chỉ.', found=True))
    scene.on_step(step, generation=0, execution_id='anchor-ui')
    window._show_interaction_surface()
    window._sync_workbench_scene(animate=False)
    settled_height()
    scene.on_response(AgentResponse('Học kỳ chính tối đa 24 tín chỉ.', [step], 0, 1, 0),
        generation=0, execution_id='anchor-ui')
    window._sync_workbench_scene(animate=False)
    settled_height()
    assert scene.evidence_box.isHidden()
    if scene.trace_expanded:
        scene.toggle_trace_details()
    collapsed = settled_height()
    assert collapsed < window.screen().availableGeometry().height() * .85
    scene.btn_sources_toggle.click()
    assert settled_height() > collapsed
    scene.btn_sources_toggle.click()
    assert abs(settled_height() - collapsed) <= 3
    scene.toggle_trace_details()
    assert settled_height() > collapsed
    scene.toggle_trace_details()
    assert abs(settled_height() - collapsed) <= 3


def test_short_flow_names_the_current_public_step(window):
    from rat.engine.work_trace import TraceEntry
    scene = window.workbench_scene
    title = 'Đang đọc quy chế học vụ'
    scene._sync_trace_ui([], reasoning_flow=[TraceEntry(1, title, status='running', stage='read')])
    assert title in scene.btn_trace_toggle.text()
    assert title in scene.btn_trace_toggle.accessibleName()
    assert scene.flow_view.isHidden()


@pytest.mark.parametrize('mode', ['expanded', 'compact', 'narrow'])
@pytest.mark.parametrize('animated', [False, True])
def test_workbench_badge_restores_same_content_scroll_and_draft(window, app, monkeypatch, mode, animated):
    from rat.engine.assistant_runtime import AgentResponse
    monkeypatch.setattr('rat.ui.omnibar.motion_enabled', lambda: animated)
    scene = window.workbench_scene
    if mode == 'expanded':
        window.set_expanded(True)
    elif mode == 'narrow':
        window.resize(440, window.height())
    answer = '\n'.join(f'{i}. Học kỳ chính tối đa 24 tín chỉ.' for i in range(1, 31))
    scene.begin_turn('Đọc quy định', generation=0, execution_id='badge-ui')
    scene.on_response(AgentResponse(answer, [], 0, 0, 0), generation=0, execution_id='badge-ui')
    window._show_interaction_surface()
    window._sync_workbench_scene(animate=False)
    editor = window.chat_composer_input
    editor.setText('Bản nháp vẫn ở đây')
    editor.setSelection(0, len('Bản nháp'))

    def settle():
        QTest.qWait(30)
        until(app, lambda: not window._surface_fit_pending and
            (not hasattr(window, '_geom_anim') or window._geom_anim.state() != window._geom_anim.State.Running))
        QTest.qWait(30)

    settle()
    desk = window.workbench_canvas
    card = scene.result_card
    bar = window.workbench_user_lane.bubble
    anchor = bar.mapToGlobal(QPoint(0, bar.height())).y()
    opened_height = window.height()
    scroll = scene.overview_scroll.verticalScrollBar()
    assert scroll.maximum() > 48
    scroll.setValue(48)
    desk.btn_fold.click()
    settle()
    badge = window.workbench_dialogue.workbench_badge
    assert badge.isHidden() and badge.text() == '!'
    assert not window._workbench_unread_updates
    assert desk.isHidden() and window.content_stack.isHidden() and window.thought_trail.isHidden()
    assert window.height() < opened_height - 80
    assert abs(bar.mapToGlobal(QPoint(0, bar.height())).y() - anchor) <= 1
    assert editor.text() == 'Bản nháp vẫn ở đây' and editor.selectedText() == 'Bản nháp'
    assert QApplication.focusWidget() is editor
    window.hide()
    window.show_omnibar()
    settle()
    assert window._workbench_folded and badge.isHidden()
    window.workbench_speech_bubble.btn_hist.setFocus()
    QTest.keyClick(window.workbench_speech_bubble.btn_hist, Qt.Key.Key_Space)
    settle()
    assert not window._workbench_folded and badge.isHidden() and desk.isVisible()
    assert window.workbench_canvas is desk and scene.result_card is card
    assert card.answer_lbl.text() == answer
    assert window.is_expanded == (mode == 'expanded')
    assert scroll.value() == 48
    assert abs(bar.mapToGlobal(QPoint(0, bar.height())).y() - anchor) <= 1
    assert editor.text() == 'Bản nháp vẫn ở đây' and editor.selectedText() == 'Bản nháp'
    desk.btn_fold.click()
    window._reset_chat()
    settle()
    assert not window._workbench_folded and badge.isHidden()


@pytest.mark.parametrize('failed', [False, True])
def test_folded_workbench_keeps_live_updates_and_source_detail(window, app, tmp_path, failed):
    from rat.engine.assistant_runtime import AgentResponse, AgentStep
    path = add_file(window, tmp_path, 'badge-source.txt')
    scene = window.workbench_scene
    scene.begin_turn('Đọc quy định', generation=0, execution_id='live-badge')
    step = AgentStep(1, '', tool_name='read_document', tool_result=dict(path=str(path),
        filename=path.name, content='Học kỳ chính tối đa 24 tín chỉ.', found=True))
    scene.on_step(step, generation=0, execution_id='live-badge')
    window._show_interaction_surface()
    window._sync_workbench_scene(animate=False)
    source_id = scene.all_sources()[0].node_id
    scene.select_source(source_id)
    window.set_workbench_folded(True)
    scene.on_response(AgentResponse('Học kỳ chính tối đa 24 tín chỉ.', [step], 0, 1, 0,
        error='authored fixture error' if failed else None),
        generation=0, execution_id='live-badge')
    window._sync_workbench_scene(animate=False)
    QTest.qWait(50)
    assert window._workbench_folded and window.workbench_canvas.isHidden()
    assert scene.mode == 'source_detail' and scene.selected_source_id == source_id
    if not failed:
        assert scene.current_snapshot.result_node.answer_text == 'Học kỳ chính tối đa 24 tín chỉ.'
    assert window.workbench_dialogue.workbench_badge.isVisible()
    if failed:
        assert window.workbench_dialogue._workbench_error
        assert scene.current_snapshot.phase_label in window.workbench_dialogue.workbench_badge.toolTip()
    assert window.workbench_speech_bubble.btn_hist.text() == 'Xem kết quả'
    window.workbench_speech_bubble.btn_hist.click()
    QTest.qWait(50)
    assert not window._workbench_folded and window.workbench_canvas.isVisible()
    assert scene.mode == 'source_detail' and scene.selected_source_id == source_id


def test_workbench_notice_ignores_chatter_and_acknowledges_observed_updates(window, app, tmp_path):
    from rat.engine.assistant_runtime import AgentResponse, AgentStep
    path = add_file(window, tmp_path, 'notice-source.txt')
    scene = window.workbench_scene
    scene.begin_turn('Đọc quy định', generation=0, execution_id='notice-ui')
    window._show_interaction_surface()
    window._sync_workbench_scene(animate=False)
    window.set_workbench_folded(True)
    badge = window.workbench_dialogue.workbench_badge
    QTest.qWait(40)
    bar = window.workbench_user_lane.bubble
    anchor = bar.mapToGlobal(QPoint(0, bar.height())).y()

    def sync():
        window._sync_workbench_scene(animate=False)
        QTest.qWait(40)
        assert abs(bar.mapToGlobal(QPoint(0, bar.height())).y() - anchor) <= 1

    assert badge.isHidden()
    scene.on_progress('Đang tìm tài liệu…', generation=0, execution_id='notice-ui')
    sync()
    assert badge.isHidden()
    search = AgentStep(1, '', tool_name='search_documents',
        tool_result=[dict(path=str(path), filename=path.name, snippet='24 tín chỉ')])
    scene.on_step(search, generation=0, execution_id='notice-ui')
    sync()
    assert badge.isHidden()  # Metadata search hits are not a document read.
    for text in ('Học kỳ', 'Học kỳ chính', 'Học kỳ chính tối đa'):
        scene.on_text_streamed(text, generation=0, execution_id='notice-ui')
        sync()
        assert badge.isHidden()
    read = AgentStep(2, '', tool_name='read_document', tool_result=dict(path=str(path),
        filename=path.name, content='Học kỳ chính tối đa 24 tín chỉ.', found=True))
    scene.on_step(read, generation=0, execution_id='notice-ui')
    sync()
    assert badge.isVisible() and 'Đã đọc thêm' in badge.toolTip()
    pending = dict(window._workbench_unread_updates)
    sync()
    sync()
    assert window._workbench_unread_updates == pending
    badge.setFocus()
    QTest.keyClick(badge, Qt.Key.Key_Space)
    assert not window._workbench_unread_updates and badge.isHidden()
    window.set_workbench_folded(True)
    sync()
    assert badge.isHidden()
    check = AgentStep(3, '', verification=[dict(status='PASS', reason='Authored literal fixture check')])
    scene.on_step(check, generation=0, execution_id='notice-ui')
    sync()
    assert badge.isVisible() and 'đối chiếu' in badge.toolTip()
    badge.click()
    window.set_workbench_folded(True)
    scene.on_response(AgentResponse('Học kỳ chính tối đa 24 tín chỉ.', [search, read, check], 0, 2, 0),
        generation=0, execution_id='notice-ui')
    sync()
    assert badge.isVisible() and 'Có kết quả mới' in badge.toolTip()
    badge.click()
    window.set_workbench_folded(True)
    sync()
    assert badge.isHidden() and not window._workbench_unread_updates


def test_folded_workbench_notifies_when_input_is_needed(window, app):
    from types import SimpleNamespace
    from rat.engine.assistant_runtime import AgentResponse
    scene = window.workbench_scene
    scene.begin_turn('Đọc tài liệu', generation=0, execution_id='waiting-notice')
    window._show_interaction_surface()
    window._sync_workbench_scene(animate=False)
    window.set_workbench_folded(True)
    scene.on_response(AgentResponse('Bạn chọn tài liệu nào?', [], 0, 0, 0,
        pending_input_request=SimpleNamespace(prompt='Bạn chọn tài liệu nào?')),
        generation=0, execution_id='waiting-notice')
    window._sync_workbench_scene(animate=False)
    QTest.qWait(30)
    badge = window.workbench_dialogue.workbench_badge
    assert badge.isVisible() and 'Cần thêm thông tin' in badge.accessibleName()
    assert window._workbench_folded
    assert 'Bạn chọn tài liệu nào?' in window.workbench_speech_bubble.dialogue.text()


def test_empty_folded_workbench_has_a_quiet_reopen_action(window, app):
    window.set_expanded(True)
    window.workbench_canvas.btn_fold.click()
    QTest.qWait(40)
    assert window._workbench_folded
    assert window.workbench_dialogue.workbench_badge.isHidden()
    button = window.workbench_speech_bubble.btn_hist
    assert button.isVisible() and button.text() == 'Mở workbench'
    button.click()
    QTest.qWait(40)
    assert not window._workbench_folded and window.workbench_canvas.isVisible()


def test_visual_flow_keeps_proposed_unchecked_and_failed_checks_distinct(window):
    from rat.engine.work_trace import TraceEntry
    scene = window.workbench_scene
    entries = [TraceEntry(1, 'Dự định đọc nguồn', status='proposed', stage='plan'),
               TraceEntry(2, 'Điều kiện còn thiếu', status='unchecked', stage='verify'),
               TraceEntry(3, 'Kết luận chưa khớp', status='verified_fail', stage='verify')]
    scene._sync_trace_ui([], reasoning_flow=entries)
    assert [n.status.text() for n in scene.flow_view.nodes.values()] == ['Dự định', 'Chưa kiểm tra', 'Chưa đạt']
    assert 'Kiểm tra đạt' not in scene.trace_detail_lbl.text()
    node = scene.flow_view.nodes[(1, 'plan')]
    entries[0] = TraceEntry(1, 'Đã hủy bước chưa chạy', status='cancelled', stage='plan')
    scene._sync_trace_ui([], reasoning_flow=entries)
    assert scene.flow_view.nodes[(1, 'plan')] is node
    assert node.status.text() == 'Đã dừng'


def test_finder_secondary_actions_use_context_menu_without_changing_target(window, app, tmp_path):
    from rat.ui.workbench_scene import FinderHitRow
    path = tmp_path / 'context-source.txt'
    hit = SearchHit('file:context', 'file', path.name, str(path), 'metadata')
    row = FinderHitRow(hit, parent=window)
    row.resize(500, row.sizeHint().height())
    row.show()
    row.setFocus()
    QTest.qWait(20)
    assert row.btn_more.isVisible() and row.btn_open.isVisible()
    assert row.btn_ask.isHidden() and row.btn_preview.isHidden() and row.btn_reveal.isHidden()
    QTest.keyClick(row, Qt.Key.Key_F10, Qt.KeyboardModifier.ShiftModifier)
    assert row.more_menu.isVisible()
    row.more_menu.hide()
    ask, preview, reveal, opened = Mock(), Mock(), Mock(), Mock()
    row.question_requested.connect(ask)
    row.preview_requested.connect(preview)
    row.reveal_requested.connect(reveal)
    row.open_requested.connect(opened)
    for action in row.more_menu.actions():
        action.trigger()
    row.btn_open.click()
    ask.assert_called_once_with(hit)
    preview.assert_called_once_with(str(path))
    reveal.assert_called_once_with(str(path))
    opened.assert_called_once_with(str(path))
    row.hide()
    row.deleteLater()


def test_flow_link_marks_current_revision_when_the_recorded_step_used_an_older_one(window):
    from rat.engine.work_trace import TraceEntry
    from rat.ui.workbench_scene import SceneSourceNode
    scene = window.workbench_scene
    scene.current_snapshot.primary_sources.append(SceneSourceNode('source:revision', 'document',
        'Tài liệu đã cập nhật', artifact_id='artifact:revision', revision=2))
    link = scene._source_for_flow(TraceEntry(1, 'Đã đọc', status='read', stage='read',
        artifact_id='artifact:revision', revision=1))
    assert link[0] == 'source:revision'
    assert 'bản hiện tại 2' in link[1] and 'bước dùng bản 1' in link[1]


def test_idle_canvas_reappears_for_work_and_clears_without_replacing_composer(window, app, tmp_path):
    canvas = window.workbench_canvas
    editor = window.chat_composer_input
    assert canvas.isHidden()
    assert window.thought_trail.isHidden()
    idle_height = window._surface_height()

    window.set_expanded(True)
    until(app, canvas.isVisible)
    window.set_expanded(False)
    until(app, canvas.isHidden)

    add_file(window, tmp_path, "flow-visible.txt")
    editor.setText("flow")
    until(app, lambda: bool(window.workbench_scene.finder_box._row_order))
    assert canvas.isVisible()
    assert window.content_stack.isVisible()
    assert window.thought_trail.isVisible()
    assert window._surface_height() > idle_height
    assert window.chat_composer_input is editor
    assert editor.text() == "flow"

    editor.clear()
    until(app, canvas.isHidden)
    assert window.thought_trail.isHidden()
    assert window._surface_height() == idle_height

    window.switch_section(1)
    assert canvas.isVisible()
    window.switch_section(0)
    assert window.is_expanded
    assert canvas.isVisible()
    window.set_expanded(False)
    assert canvas.isHidden()
    assert window.chat_composer_input is editor
    editor.setFocus()
    assert editor.hasFocus()


def test_finder_results_stay_populated_when_window_is_hidden_and_reopened(window, app, tmp_path):
    add_file(window, tmp_path, 'flow-reopen.txt')
    editor = window.chat_composer_input
    editor.setText('flow')
    scene = window.workbench_scene
    until(app, lambda: bool(scene.finder_box._row_order))
    QTest.qWait(70)
    expected_height = window._surface_height()
    selected = scene.finder_box.selected_resource_id
    window.hide()
    assert not scene.is_empty()
    assert window._surface_height() == expected_height
    window.show_omnibar()
    QTest.qWait(70)
    assert scene.finder_box.isVisible()
    assert not scene.is_empty()
    assert scene.finder_box.selected_resource_id == selected
    assert abs(window.height() - expected_height) <= 3
    assert editor.text() == 'flow'


def test_type_select_preview_open_and_return_to_composer(window, app, tmp_path, monkeypatch):
    from rat.ui import omnibar
    first = add_file(window, tmp_path, "flow-first.txt")
    add_file(window, tmp_path, "flow-second.txt")
    opened, preview = Mock(), Mock()
    monkeypatch.setattr(omnibar, "open_file_default", opened)
    monkeypatch.setattr(omnibar, "trigger_quicklook", preview)
    editor = window.chat_composer_input
    editor.setText("flow")
    box = window.workbench_scene.finder_box
    until(app, lambda: len(box._row_order) == 2)
    window.activateWindow()
    editor.setFocus()
    QTest.keyClick(editor, Qt.Key.Key_Tab)
    assert QApplication.focusWidget() is box
    chosen = box.current_hit()
    assert chosen.path in {str(first), str(tmp_path / "flow-second.txt")}
    QTest.keyClick(box, Qt.Key.Key_Space)
    preview.assert_called_once_with(chosen.path)
    QTest.keyClick(box, Qt.Key.Key_Return)
    opened.assert_called_once_with(chosen.path)
    QTest.keyClick(box, Qt.Key.Key_Escape)
    assert QApplication.focusWidget() is editor
    assert editor.text() == "flow"


def test_enter_in_composer_submits_request_without_opening_selection(window, app, tmp_path, monkeypatch):
    from rat.ui import omnibar
    add_file(window, tmp_path, "flow-item.txt")
    monkeypatch.setattr("rat.ui.assistant_worker.AssistantWorker.start", Mock())
    opened = Mock()
    monkeypatch.setattr(omnibar, "open_file_default", opened)
    editor = window.chat_composer_input
    editor.setText("flow")
    until(app, lambda: bool(window.workbench_scene.finder_box._row_order))
    editor.setFocus()
    QTest.keyClick(editor, Qt.Key.Key_Return)
    assert window._pending_chat_query == "flow"
    assert window._assistant_handle["execution_request"].execution_id
    opened.assert_not_called()


def test_old_snapshot_cannot_replace_new_query_selection(window, app, tmp_path):
    path = add_file(window, tmp_path, "flow-current.txt")
    editor = window.chat_composer_input
    editor.setText("flow")
    until(app, lambda: bool(window.workbench_scene.finder_box._row_order))
    current_id = window._finder_selected_id
    editor.setText("unmatched-new-query")
    until(app, lambda: window.workbench_scene.finder_box.snapshot.query == "unmatched-new-query")
    stale = SearchSnapshot(-1, "flow", "lexical",
        (SearchHit(current_id, "file", "stale", str(path), "metadata"),), current_id, True, 0, ())
    window._on_finder_snapshot_delivered(stale)
    assert window.workbench_scene.finder_box.snapshot.query == "unmatched-new-query"
    assert not window.workbench_scene.finder_box._row_order


def test_catalog_delivery_keeps_query_epoch_and_rejects_queued_old_result(window, app, tmp_path):
    path = add_file(window, tmp_path, "flow-catalog.txt")
    window.chat_composer_input.setText("flow")
    box = window.workbench_scene.finder_box
    until(app, lambda: bool(box._row_order))
    coordinator = window._finder_coordinator
    before = box.snapshot
    selected = box.selected_resource_id
    window._on_finder_catalog_ready(ApplicationCatalog())
    assert window._finder_coordinator is coordinator
    until(app, lambda: box.snapshot.query_id > before.query_id)
    current_id = box.snapshot.query_id
    stale = SearchSnapshot(before.query_id, "stale catalog", "lexical",
        (SearchHit(selected, "file", "stale", str(path), "metadata"),), selected, True, 0, ())
    window._on_finder_snapshot_delivered(stale)
    assert box.snapshot.query_id == current_id
    assert box.snapshot.query == "flow"
    assert box.selected_resource_id == selected


def test_index_metadata_wait_does_not_block_typing(window, app, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    def blocked_stats():
        entered.set()
        assert release.wait(5)
        return {"total_files": 0}
    monkeypatch.setattr(window.db, "get_stats", blocked_stats)
    try:
        window._load_initial_data()
        until(app, entered.is_set)
        editor = window.chat_composer_input
        editor.clear()
        editor.setFocus()
        QTest.keyClicks(editor, "typing while metadata waits")
        assert editor.text() == "typing while metadata waits"
        assert not release.is_set()
    finally:
        release.set()
        QTest.qWait(20)


def test_settings_model_lookup_wait_does_not_block_window(window, app, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    threads = []
    def model_names():
        threads.append(threading.current_thread())
        entered.set()
        assert release.wait(5)
        return ["fixture-model"]
    monkeypatch.setattr("rat.engine.slm.slm_engine.list_installed_models", model_names)
    try:
        window.switch_section(4)
        until(app, entered.is_set)
        window.switch_section(0)
        window.chat_composer_input.setFocus()
        QTest.keyClicks(window.chat_composer_input, "still editable")
        assert window.chat_composer_input.text() == "still editable"
        assert threads[0] is not threading.main_thread()
    finally:
        release.set()
        QTest.qWait(20)


def test_composer_reaches_composed_policy_and_returns_to_same_conversation(window, app):
    import numpy as np
    from rat.engine.meta_reasoner import build_composed_meta_reasoner
    from reasoning.bundle import create_synthetic_specimen_bundle
    class Backend:
        hidden_size = 2
        def embed(self, query):
            return np.zeros(2)
        def run(self, strategy, query):
            return "observed synthetic answer", .9, 7
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    engine = build_composed_meta_reasoner(bundle, Backend(), policy, allow_synthetic=True)
    app.setProperty("ratReasoningEngine", engine)
    app.setProperty("ratAllowSyntheticPolicy", True)
    try:
        window.chat_composer_input.setText("giải thích fixture")
        window._submit_chat_prompt(window.chat_composer_input.text())
        until(app, lambda: window._pending_chat_query is None)
        result = window.workbench_scene.current_snapshot.result_node
        assert result.answer_text == "observed synthetic answer"
        assert window.last_turn_telemetry["execution_lane"] == "reasoning"
        assert window.last_turn_telemetry["cost_ledger"]["generated_tokens"] == 7
    finally:
        app.setProperty("ratReasoningEngine", None)
        app.setProperty("ratAllowSyntheticPolicy", None)
