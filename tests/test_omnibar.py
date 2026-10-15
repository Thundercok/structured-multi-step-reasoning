"""
tests/test_omnibar.py — Unit tests for OmnibarWindow (Unified Casual Surface).
Validates zero-crash guarantees on startup, section switching, agenda rendering,
and search result injection.
"""

import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtWidgets import QApplication

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from rat.engine.reranker import SearchResultItem
from rat.ui.omnibar import OmnibarWindow, StreamReasoningWorker, lower_overlay_geometry


class TestOmnibarWindow(unittest.TestCase):
    def setUp(self):
        # Legacy capability controls remain available in the explicit developer UI.
        debug = patch.dict(os.environ, {'RAT_DEBUG_UI': '1'})
        debug.start()
        self.addCleanup(debug.stop)
        patcher = patch("rat.ui.assistant_worker.AssistantWorker.start")
        self.agent_start = patcher.start()
        self.addCleanup(patcher.stop)
        with patch("rat.ui.omnibar.Database") as mock_db, \
             patch("rat.ui.omnibar.SearchEngine") as mock_engine, \
             patch("rat.ui.feedback.FeedbackLog"):
            mock_db_inst = MagicMock()
            mock_db_inst.get_stats.return_value = {"total_files": 88}
            mock_db_inst.get_recent_documents.return_value = [
                {
                    "file_path": "/Users/thundercock2/Documents/DSA_HW1.pdf",
                    "file_name": "DSA_HW1.pdf",
                    "file_ext": ".pdf",
                    "file_size": 2048,
                    "modified_at": time.time(),
                    "category": "docs",
                }
            ]
            mock_db.return_value = mock_db_inst

            mock_eng_inst = MagicMock()
            mock_eng_inst.search.return_value = {"results": [], "latency_ms": 5, "reasoning_trace": None, "plan": None}
            mock_engine.return_value = mock_eng_inst

            self.window = OmnibarWindow()
            try:
                self.window.worker.search_completed.disconnect(self.window._on_search_completed)
            except Exception:
                pass

    def tearDown(self):
        if hasattr(self, "window") and self.window is not None:
            self.window.shutdown()
            self.window.close()
            self.window.deleteLater()
            app.processEvents()

    def test_initial_attributes_and_sections(self):
        """Verify Omnibar initialized with 5 sections and defaults to Home (0)."""
        self.assertIsNotNone(self.window.search_input)
        self.assertEqual(len(self.window.section_buttons), 5)
        self.assertEqual(self.window.current_section_idx, 0)
        self.assertEqual(self.window.content_stack.currentIndex(), 0)
        self.assertIn("Huy", self.window.current_member.name)

    def test_natal_navigation_can_be_opened_twice_and_reset_clears_task_state(self):
        import importlib.util
        self.window.show()
        self.window.btn_natal.click()
        self.assertEqual(self.window.current_section_idx, 0)
        artifacts = self.window.assistant_runtime.artifact_store.list()
        self.assertTrue(len(artifacts) > 0)
        self.assertEqual(artifacts[0].kind, "input_request")
        # Direct entry does not open a standalone QMainWindow or hide the main RAT surface
        self.assertFalse(self.window.isHidden())
        self.assertIsNone(getattr(self.window, "_natal_window", None))
        self.window.btn_natal.click()
        self.assertEqual(len(self.window.assistant_runtime.artifact_store.list()), 1)
        self.window._assistant_task_state = {'goal': 'previous goal'}
        self.window._reset_chat()
        self.assertEqual(self.window._assistant_task_state, {})
        self.assertEqual(len(self.window.assistant_runtime.artifact_store.list()), 0)

    def test_inline_natal_form_finishes_through_worker_without_feature_window(self):
        import time
        from PyQt6.QtTest import QTest
        self.window.open_natal_chart()
        pending = self.window.assistant_runtime.dispatcher.state.pending_input_request
        self.assertIsNotNone(pending)
        self.window._on_input_submitted(pending.id, dict(name='Ví dụ kiểm thử', date='2000-06-15',
            time='09:30', place='Hồ Chí Minh', latitude=10.8231, longitude=106.6297, timezone='Asia/Ho_Chi_Minh'))
        deadline = time.monotonic() + 10
        while self.window._artifact_worker is not None and time.monotonic() < deadline:
            QTest.qWait(10)
        charts = self.window.assistant_runtime.artifact_store.find_by_kind('natal_chart')
        self.assertEqual(len(charts), 1)
        self.assertIsNone(self.window.assistant_runtime.artifact_store.get(pending.id))
        self.assertFalse(hasattr(self.window, '_natal_window'))
        self.assertTrue(self.window._interaction_surface_active)
        self.assertTrue(self.window.section_bar.isHidden())
        handle = self.window._latest_assistant_handle
        self.assertIn(charts[0].id, handle['artifacts'])
        self.assertNotIn(pending.id, handle['artifacts'])

    def test_assistant_model_choice_does_not_change_document_model(self):
        from rat.config import config
        from rat.engine.slm import slm_engine
        before = slm_engine.model
        with patch.object(config, 'assistant_model', 'qwen3:4b'):
            self.window._apply_assistant_model()
            self.assertEqual(self.window.assistant_runtime.model_client.model, 'qwen3:4b')
            self.assertEqual(slm_engine.model, before)

    def test_switch_sections(self):
        """Verify switching through all sections (Home, Files, Schedule, Club, Settings) works smoothly."""
        for idx in range(5):
            self.window.switch_section(idx)
            app.processEvents()
            self.assertEqual(self.window.current_section_idx, idx)
            self.assertEqual(self.window.content_stack.currentIndex(), idx)

    def test_home_agenda_rendered(self):
        """Verify Home section live agenda rendered without error."""
        self.window.switch_section(0)
        app.processEvents()
        self.assertIsNotNone(self.window.today_date_label.text())
        self.assertIsNotNone(self.window.live_banner_text.text())

    def test_recent_files_in_home_view(self):
        """Verify recent files populated in the Home view."""
        self.window.switch_section(0)
        app.processEvents()
        self.assertGreaterEqual(self.window.recent_list.count(), 1)
        item = self.window.recent_list.item(0)
        data = item.data(Qt.ItemDataRole.UserRole)
        self.assertIn("DSA_HW1.pdf", data.file_name)

    def test_search_injection_math_card(self):
        """Verify quick calculation produces a math card at index 0."""
        self.window.current_query = "tính 120 * 4"
        mock_response = {
            "results": [],
            "latency_ms": 2,
            "reasoning_trace": None,
            "plan": None,
        }
        req_id = self.window._request_counter
        self.window._on_search_completed(req_id, mock_response)
        app.processEvents()

        self.assertGreaterEqual(self.window.result_list.count(), 1)
        top_item = self.window.result_list.item(0).data(Qt.ItemDataRole.UserRole)
        self.assertIn("480", top_item.file_name)
        self.assertTrue(top_item.file_path.startswith("rat://calc_copy/480"))

    def test_search_injection_room_card(self):
        """Verify room query injects campus navigation card."""
        self.window.current_query = "phòng C302"
        mock_response = {
            "results": [],
            "latency_ms": 2,
            "reasoning_trace": None,
            "plan": None,
        }
        req_id = self.window._request_counter
        self.window._on_search_completed(req_id, mock_response)
        app.processEvents()

        self.assertGreaterEqual(self.window.result_list.count(), 1)
        top_item = self.window.result_list.item(0).data(Qt.ItemDataRole.UserRole)
        self.assertIn("C302", top_item.file_name)
        self.assertIn("Tòa C", top_item.snippet)

    def test_search_injection_agenda_card(self):
        """Verify query 'hôm nay' injects live agenda card."""
        self.window.current_query = "hôm nay có học gì không"
        mock_response = {
            "results": [],
            "latency_ms": 3,
            "reasoning_trace": None,
            "plan": None,
        }
        req_id = self.window._request_counter
        self.window._on_search_completed(req_id, mock_response)
        app.processEvents()

        self.assertGreaterEqual(self.window.result_list.count(), 1)
        top_item = self.window.result_list.item(0).data(Qt.ItemDataRole.UserRole)
        self.assertTrue("hôm nay" in top_item.file_name.lower())

    def test_clear_search_auto_returns_to_home(self):
        """Verify clearing search text in Files view automatically returns user to Chatbot view."""
        self.window.switch_section(1)
        self.assertEqual(self.window.current_section_idx, 1)

        self.window.search_input.setText("some query")
        self.window.search_input.clear()
        app.processEvents()
        self.assertEqual(self.window.current_section_idx, 0)

    def test_search_injection_reasoning_card(self):
        """Verify academic reasoning query injects the RL Meta-Controller card."""
        self.window.current_query = "quy chế học vụ: sinh viên song bằng thạc sĩ có bị đình chỉ không"
        mock_response = {
            "results": [],
            "latency_ms": 5,
            "reasoning_trace": None,
            "plan": None,
        }
        req_id = self.window._request_counter
        self.window._on_search_completed(req_id, mock_response)
        app.processEvents()

        self.assertGreaterEqual(self.window.result_list.count(), 1)
        top_item = self.window.result_list.item(0).data(Qt.ItemDataRole.UserRole)
        self.assertIn("Suy luận", top_item.file_name)
        self.assertIn("Meta-Controller", top_item.explanation)
        self.assertIsNotNone(self.window.preview_panel.current_trace)
        self.assertGreater(len(self.window.preview_panel.current_trace.steps), 0)

    def test_mascot_idle_state_and_geometry(self):
        """Verify mascot starts in IDLE (núp) state with 0 deg rotation and hidden bubble."""
        mascot = self.window.mascot_peeking
        self.assertIsNotNone(mascot)
        self.assertFalse(mascot.is_speaking)
        self.assertEqual(mascot.rotation, 0.0)
        self.assertEqual(mascot.rot_idle, 0.0)
        self.assertTrue(self.window.speech_bubble.isHidden())

        # Verify mascot is anchored properly relative to container
        self.assertEqual(mascot.x(), mascot.x_idle)
        self.assertEqual(mascot.y(), mascot.y_idle)

    def test_reply_stays_in_conversation_without_mascot_popout(self):
        self.window.show()
        self.window._deliver_assistant_reply("Xin chào bạn học!")
        app.processEvents()
        self.assertTrue(self.window.mascot_peeking.isHidden())
        self.assertTrue(self.window.speech_bubble.isHidden())
        self.assertTrue(self.window.chat_stream.isVisible())
        self.assertIn("Xin chào", self.window._latest_assistant_handle['ans_lbl'].text())

    def test_streaming_reply_reaches_same_compact_viewport(self):
        self.window.show()
        handle = self.window.chat_stream.create_streaming_message()
        self.window._on_reasoning_token(handle, "Đầu tiên, ")
        self.window._on_reasoning_token(handle, "xác định mục tiêu.")
        self.assertEqual(handle['ans_lbl'].text(), "Đầu tiên, xác định mục tiêu.")
        self.assertTrue(self.window.speech_bubble.isHidden())
        self.assertTrue(self.window.chat_stream.isVisible())
        self.assertTrue(handle['status_lbl'].isHidden())

    def test_final_reply_without_tokens_is_displayed_and_copyable(self):
        from PyQt6.QtWidgets import QPushButton
        self.window.show()
        handle = self.window.chat_stream.create_streaming_message()
        answer = "Một câu trả lời **hoàn chỉnh** không có token streaming."
        self.window._on_reasoning_finished(handle, answer, [], 10, "Fallback", "Direct")
        self.assertEqual(handle['full_text'], answer)
        self.assertEqual(handle['ans_lbl'].text(), answer)
        self.assertTrue(handle['ans_lbl'].isVisible())
        copy = next(b for b in handle['card'].findChildren(QPushButton) if b.text() == 'Sao chép')
        copy.click()
        self.assertEqual(QApplication.clipboard().text(), answer)
        self.assertTrue(handle['status_lbl'].isHidden())

    def test_final_reply_replaces_partial_stream(self):
        handle = self.window.chat_stream.create_streaming_message()
        self.window._on_reasoning_token(handle, "Bản chưa hoàn chỉnh")
        answer = "Bản cuối đã sửa và có đủ nội dung."
        self.window._on_reasoning_finished(handle, answer, [], 10, "Direct", "Direct")
        self.assertEqual(handle["ans_lbl"].text(), answer)
        self.assertEqual(self.window.speech_bubble.text(), answer)

    def test_empty_final_reply_keeps_received_tokens(self):
        handle = self.window.chat_stream.create_streaming_message()
        self.window._on_reasoning_token(handle, "Nội dung đã nhận")
        self.window._on_reasoning_finished(handle, "", [], 10, "Direct", "Direct")
        self.assertEqual(handle["ans_lbl"].text(), "Nội dung đã nhận")
        self.assertEqual(self.window.speech_bubble.text(), "Nội dung đã nhận")

    def test_long_reply_preview_keeps_full_copy_and_read_action(self):
        answer = "\n".join(f"Dòng {i}: một ý cần giữ để đọc đầy đủ." for i in range(30))
        self.window._deliver_assistant_reply(answer)
        bubble = self.window.speech_bubble
        self.assertTrue(bubble.dialogue.text().endswith("…"))
        self.assertLess(len(bubble.dialogue.text()), len(answer))
        self.assertEqual(bubble.text(), answer)
        self.assertFalse(bubble.btn_hist.isHidden())
        self.assertEqual(bubble.btn_hist.text(), "Đọc hết")
        self.assertLessEqual(bubble.height(), 112)
        bubble.btn_copy.click()
        self.assertEqual(QApplication.clipboard().text(), answer)

    def test_expand_then_collapse_keeps_same_complete_answer(self):
        self.window.show()
        answer = "Một đáp án dài. " * 100
        self.window._deliver_assistant_reply(answer)
        label = self.window._latest_assistant_handle['ans_lbl']
        for mode in (True, False):
            self.window.set_expanded(mode)
            app.processEvents()
            self.assertEqual(self.window.is_expanded, mode)
            self.assertTrue(self.window.btn_expand.isVisible())
            self.assertTrue(self.window.chat_stream.isVisible())
            self.assertIs(self.window._latest_assistant_handle['ans_lbl'], label)
            self.assertEqual(label.text(), answer)
            self.assertTrue(self.window.speech_bubble.isHidden())

    def test_short_reply_does_not_add_read_full_action(self):
        self.window._deliver_assistant_reply("Bắt đầu từ một ý.")
        bubble = self.window.speech_bubble
        self.assertEqual(bubble.dialogue.text(), "Bắt đầu từ một ý.")
        self.assertTrue(bubble.btn_hist.isHidden())
        self.assertFalse(bubble.btn_copy.isHidden())

    def test_reply_preview_treats_angle_brackets_as_text(self):
        answer = "Giữ nguyên <mục tiêu> và <b>ví dụ</b>."
        self.window._deliver_assistant_reply(answer)
        self.assertEqual(self.window.speech_bubble.dialogue.textFormat(), Qt.TextFormat.PlainText)
        self.assertEqual(self.window.speech_bubble.text(), answer)

    def test_welcome_and_pending_reply_cannot_be_copied(self):
        bubble = self.window.speech_bubble
        QApplication.clipboard().setText("Không thay clipboard")
        bubble.reset_welcome()
        bubble._on_copy_clicked()
        self.assertFalse(bubble.has_reply)
        bubble.set_reply("Đang suy nghĩ…", "Đang nghĩ", copy_text="")
        bubble._on_copy_clicked()
        self.assertFalse(bubble.has_reply)
        self.assertTrue(bubble.btn_copy.isHidden())
        self.assertEqual(QApplication.clipboard().text(), "Không thay clipboard")

    def test_stream_token_does_not_append_to_truncated_preview(self):
        bubble = self.window.speech_bubble
        answer = "Một ý dài cần đọc hết. " * 50
        bubble.set_reply(answer)
        bubble.stream_token("Kết luận.")
        self.assertEqual(bubble.text(), answer + "Kết luận.")
        self.assertNotIn("…", bubble.text())

    def test_stream_token_preserves_spaces_between_words(self):
        bubble = self.window.speech_bubble
        bubble.reset_welcome()
        for token in ("Xin", " ", "chào"):
            bubble.stream_token(token)
        self.assertEqual(bubble.text(), "Xin chào")
        bubble.btn_copy.click()
        self.assertEqual(QApplication.clipboard().text(), "Xin chào")

    def test_unbroken_long_reply_fits_bubble_width(self):
        bubble = self.window.speech_bubble
        answer = "x" * 1000
        bubble.set_reply(answer)
        from PyQt6.QtCore import QRect
        rect = bubble.dialogue.fontMetrics().boundingRect(
            QRect(0, 0, 420, 10000), Qt.TextFlag.TextWordWrap, bubble.dialogue.text()
        )
        self.assertLessEqual(rect.width(), 420)
        self.assertEqual(bubble.text(), answer)

    def test_hide_and_reopen_preserves_answer_and_draft(self):
        answer = "Giữ lại điều đang trao đổi."
        self.window._deliver_assistant_reply(answer)
        self.window.chat_composer_input.setText("Câu đang viết dở")
        with patch("rat.os.app.activate_macos_app"), patch("rat.ui.omnibar.configure_macos_fullscreen_overlay"):
            self.window.show_omnibar()
            self.window.hide()
            self.window.show_omnibar()
        self.assertEqual(self.window.speech_bubble.text(), answer)
        self.assertEqual(self.window.chat_composer_input.text(), "Câu đang viết dở")

    def test_expanded_stream_does_not_duplicate_reply_when_collapsed(self):
        self.window.show()
        self.window.set_expanded(True)
        handle = self.window.chat_stream.create_streaming_message()
        self.window._on_reasoning_token(handle, "Đáp án trong vùng đọc đầy đủ")
        self.window._on_reasoning_finished(handle, handle['full_text'], [], 10, "Direct", "Direct")
        self.window.set_expanded(False)
        self.assertTrue(self.window.speech_bubble.isHidden())
        self.assertTrue(handle['ans_lbl'].isVisible())
        self.assertEqual(handle['ans_lbl'].text(), "Đáp án trong vùng đọc đầy đủ")

    def test_polite_math_requests_reach_same_assistant_without_forcing_full(self):
        for query in ("Giúp tôi tính 2+2", "Chuột ơi, 2+2 bằng bao nhiêu?", "chào chuột tính 2^3"):
            self.window._reset_chat()
            self.window._submit_chat_prompt(query)
            self.assertEqual(self.window._current_reasoner.query, query)
            self.assertFalse(self.window.is_expanded)

    def test_model_failure_is_actionable_and_not_saved_as_an_answer(self):
        from rat.engine.assistant_runtime import AgentResponse
        self.window._submit_chat_prompt("1/0")
        handle = self.window._assistant_handle
        response = AgentResponse("", [], 10, 0, 0, error="invalid_model_output")
        self.window._on_assistant_response(handle, response)
        self.assertIn("thử lại", handle["full_text"])
        self.assertNotIn("invalid_model_output", handle["full_text"])
        self.assertEqual(self.window._conversation.messages(), [])
        context = self.window._conversation.context_messages()
        self.assertEqual(context[0]['content'], '1/0')
        self.assertIn('successful_answer_produced', context[1]['content'])
        self.assertIsNone(self.window._pending_chat_query)

    def test_unfamiliar_phrasing_and_followups_use_the_same_worker(self):
        for query in ("Chào, tìm tài liệu cho buổi kế tiếp", "Cái đó có nói về TCP không?", "Mình kẹt ở phần này", "Lên ý tưởng cho CLB"):
            self.window._reset_chat()
            self.window._submit_chat_prompt(query)
            self.assertEqual(self.window._current_reasoner.query, query)
            self.assertEqual(self.window._pending_chat_query, query)

    def test_greetings_and_help_are_model_authored(self):
        for query in ("Chào chuột!", "help", "Chuột làm được gì?", "cảm ơn"):
            self.window._reset_chat()
            self.window._submit_chat_prompt(query)
            self.assertEqual(self.window._current_reasoner.query, query)
            self.assertFalse(self.window.speech_bubble.has_reply)

    def test_local_data_is_available_to_worker_without_gui_thread_search(self):
        self.window._submit_chat_prompt("Tìm giúp slide mình cần cho buổi học tới")
        worker = self.window._current_reasoner
        self.assertIs(worker.runtime.db, self.window.db)
        self.assertEqual(worker.context["member_id"], self.window.current_member.id)
        self.window.engine.search.assert_not_called()

    def test_ai_followup_receives_conversation_and_observed_sources(self):
        from rat.engine.assistant_runtime import AgentResponse
        query, answer = "Tìm tài liệu Networks", "Mình tìm được ghi chú TCP."
        self.window._submit_chat_prompt(query)
        sources = [{"type": "document", "path": "/tmp/networks.txt", "filename": "networks.txt"}]
        self.window._on_assistant_response(self.window._assistant_handle, AgentResponse(answer, [], 10, 0, 0, sources=sources))
        self.window._submit_chat_prompt("Tóm tắt cái đó")
        context = self.window._current_reasoner.context
        self.assertEqual(context["history"], [{"role": "user", "content": query, "turn_id": "turn-1"},
                                             {"role": "assistant", "content": answer, "turn_id": "turn-1"}])
        self.assertEqual(context["previous_sources"], sources)

    def test_natal_interpretation_passes_chart_as_source_not_chat_json(self):
        chart = {'birth': {'name': 'Example'}, 'positions': [{'longitude': 84.3}]}
        with patch.object(self.window, 'show_omnibar'):
            self.window._ask_about_natal_chart('Diễn giải lá số gốc', chart)
        worker = self.window._current_reasoner
        self.assertEqual(worker.query, 'Diễn giải lá số gốc')
        self.assertEqual(worker.context['previous_sources'], [{'type': 'natal_chart', 'chart': chart}])
        self.assertNotIn('longitude', worker.query)
        with patch.object(self.window, 'show_omnibar') as show:
            self.window._ask_about_natal_chart('A second chart request', {'birth': {}})
        show.assert_not_called()
        self.assertIs(self.window._current_reasoner, worker)

    def test_completed_answers_are_also_in_followup_context(self):
        self.window._pending_chat_query = "2+2"
        self.window._deliver_assistant_reply("2+2 = 4")
        self.window._submit_chat_prompt("Giải thích kết quả vừa rồi")
        self.assertEqual(self.window._current_reasoner.context["history"][-1]["content"], "2+2 = 4")

    def test_pending_reply_preserves_second_draft_and_stop_is_available(self):
        self.window._submit_chat_prompt("Giúp mình một việc")
        worker = self.window._current_reasoner
        self.window.chat_composer_input.setText("Câu tiếp theo đang viết")
        self.window._submit_chat_prompt(self.window.chat_composer_input.text())
        self.assertIs(self.window._current_reasoner, worker)
        self.assertEqual(self.window.chat_composer_input.text(), "Câu tiếp theo đang viết")
        self.assertTrue(self.window.full_chat_send.isEnabled())
        self.assertEqual(self.window.full_chat_send.text(), "■")

    def test_reset_clears_sources_and_ignores_old_worker_callbacks(self):
        from rat.engine.assistant_runtime import AgentResponse
        self.window._submit_chat_prompt("Giúp mình")
        old = self.window._assistant_handle
        self.window._assistant_sources = [{"path": "/old"}]
        self.window._reset_chat()
        self.window._on_assistant_response(old, AgentResponse("Đáp án cũ", [], 0, 0, 0))
        self.assertEqual(self.window._assistant_sources, [])
        self.assertEqual(self.window._conversation.messages(), [])
        self.assertFalse(self.window.speech_bubble.has_reply)

    def test_hide_and_reopen_keeps_semantic_context(self):
        self.window._pending_chat_query = "2+2"
        self.window._deliver_assistant_reply("2+2 = 4")
        with patch("rat.os.app.activate_macos_app"), patch("rat.ui.omnibar.configure_macos_fullscreen_overlay"):
            self.window.show_omnibar()
            self.window.hide()
            self.window.show_omnibar()
        self.window._submit_chat_prompt("Giải thích kết quả vừa rồi")
        self.assertEqual(self.window._current_reasoner.context["history"][-1]["content"], "2+2 = 4")

    def test_completed_reply_does_not_show_thinking_status_when_expanded(self):
        handle = self.window.chat_stream.create_streaming_message(badge="Đang kết nối")
        self.window._on_reasoning_finished(handle, "Đáp án cuối", [], 10, "AI cục bộ", "Model thực tế")
        self.window.set_expanded(True)
        self.assertTrue(handle["status_lbl"].isHidden())
        self.assertEqual(handle["badge_lbl"].text(), "· Model thực tế")

    def test_connection_error_is_displayed_but_not_saved_as_a_model_answer(self):
        from rat.engine.assistant_runtime import AgentResponse
        self.window._submit_chat_prompt("Cùng nghĩ về bài viết")
        self.window._on_assistant_response(self.window._assistant_handle,
            AgentResponse("", [], 10, 0, 0, error="connection_refused"))
        self.assertIn("Ollama", self.window.speech_bubble.text())
        self.assertEqual(self.window._conversation.messages(), [])
        self.assertIsNone(self.window._pending_chat_query)

    def test_lower_placement_works_with_multiple_screen_origins(self):
        for available in (QRect(0, 25, 1440, 875), QRect(-1920, -400, 1920, 1080), QRect(1440, 100, 1280, 720)):
            with self.subTest(available=available):
                compact = lower_overlay_geometry(available, 652, 238)
                expanded = lower_overlay_geometry(available, 652, 580)
                self.assertGreaterEqual(compact.top(), available.y() + available.height() // 2)
                self.assertEqual(compact.bottom(), expanded.bottom())
                self.assertTrue(available.contains(compact))
                self.assertTrue(available.contains(expanded))

    def test_small_screen_target_does_not_extend_outside_available_area(self):
        available = QRect(-300, 100, 600, 500)
        self.assertTrue(available.contains(lower_overlay_geometry(available, 652, 580)))

    def test_expand_collapse_respects_screen_and_keeps_composer_bottom(self):
        from PyQt6.QtTest import QTest
        self.window.show()
        app.processEvents()
        bottom = self.window.geometry().bottom()
        for expanded in (True, False):
            self.window.set_expanded(expanded)
            QTest.qWait(250)
            self.assertEqual(self.window.geometry().bottom(), bottom)
            self.assertTrue(self.window.screen().availableGeometry().contains(self.window.geometry()))
        self.assertLess(self.window.height(), 260)

    def test_hidden_summon_places_composer_low_with_room_above_on_selected_screen(self):
        screen = MagicMock()
        available = QRect(-1440, 40, 1440, 860)
        screen.availableGeometry.return_value = available
        with patch('rat.ui.omnibar.QGuiApplication.screenAt', return_value=screen):
            self.window._resize_overlay(620, 128)
        actual = self.window.geometry()
        self.assertTrue(available.contains(actual))
        self.assertEqual(actual, lower_overlay_geometry(available, actual.width(), actual.height()))
        self.assertEqual(actual.center().x(), available.center().x())

    @staticmethod
    def _compact_files(count=4):
        return [SearchResultItem(
            file_path=f"/tmp/rat-ui-fixtures/Tich_phan/Slide_tich_phan_{i + 1}.pdf",
            file_name=f"Slide_tich_phan_{i + 1}.pdf", file_ext=".pdf", file_size=1048576,
            modified_at=time.time() - 86400, score=90 - i, explanation="Tệp mẫu", snippet="",
        ) for i in range(count)]

    def test_file_results_are_actionable_in_same_compact_chat(self):
        from rat.ui.chat_stream import InlineFileCard
        files = self._compact_files()
        self.window.show()
        self.window._deliver_assistant_reply('Mình tìm thấy 4 tệp.', inline_files=files)
        app.processEvents()
        self.assertFalse(self.window.is_expanded)
        self.assertTrue(self.window.compact_file_list.isHidden())
        rows = self.window.chat_stream.findChildren(InlineFileCard)
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row.isVisible() for row in rows))
        self.assertTrue(self.window.quick_suggestions.isHidden())
        with patch('rat.ui.chat_stream.open_file_default') as opened, patch('rat.ui.chat_stream.trigger_quicklook') as preview, patch('rat.ui.chat_stream.reveal_in_finder') as reveal:
            rows[0].btn_open.click()
            rows[0].btn_preview.click()
            rows[0].btn_reveal.click()
            opened.assert_called_once_with(files[0].file_path)
            preview.assert_called_once_with(files[0].file_path)
            reveal.assert_called_once_with(files[0].file_path)

    def test_assistant_dispatch_does_not_run_tools_on_gui_thread(self):
        self.window.assistant_runtime.run = MagicMock()
        self.window._submit_chat_prompt("Tìm slides tích phân")
        self.window.assistant_runtime.run.assert_not_called()
        self.assertEqual(self.window._current_reasoner.query, "Tìm slides tích phân")
        self.assertIn("đang", self.window._assistant_handle["status_lbl"].text().lower())

    def test_full_composer_enables_send_and_enter_submits_the_followup(self):
        from PyQt6.QtTest import QTest
        from rat.engine.assistant_runtime import AgentResponse
        self.window._submit_chat_prompt("Find Networks")
        self.window._on_assistant_response(self.window._assistant_handle, AgentResponse("Found.", [], 10, 0, 0))
        self.assertFalse(self.window.full_chat_send.isEnabled())
        self.window.full_chat_input.setText("Tóm tắt cái đó")
        self.assertTrue(self.window.full_chat_send.isEnabled())
        QTest.keyClick(self.window.full_chat_input, Qt.Key.Key_Return)
        self.assertEqual(self.window._current_reasoner.query, "Tóm tắt cái đó")
        self.assertEqual(self.window._current_reasoner.context["history"][-1]["content"], "Found.")

    def test_enter_preserves_pending_full_draft_and_stop_button_cancels(self):
        from PyQt6.QtTest import QTest
        self.window._submit_chat_prompt("Find Networks")
        worker = self.window._current_reasoner
        self.window.full_chat_input.setText("Một yêu cầu khác")
        QTest.keyClick(self.window.full_chat_input, Qt.Key.Key_Return)
        self.assertIs(self.window._current_reasoner, worker)
        self.assertEqual(self.window.full_chat_input.text(), "Một yêu cầu khác")
        self.window.full_chat_send.click()
        self.assertIsNone(self.window._current_reasoner)
        self.assertEqual(self.window.full_chat_input.text(), "Một yêu cầu khác")

    def test_observed_documents_are_actionable_before_final_answer_and_survive_stop(self):
        from rat.engine.assistant_runtime import AgentStep
        from rat.ui.chat_stream import InlineFileCard
        self.window._submit_chat_prompt("Tìm và đọc tài liệu")
        handle = self.window._assistant_handle
        found = AgentStep(1, "", tool_name="search_documents", tool_result=[
            {"path": "/tmp/fixture.txt", "filename": "fixture.txt", "snippet": "TCP"}])
        self.window._on_assistant_step(handle, found)
        self.assertIsNotNone(handle["card"].findChild(InlineFileCard))
        self.assertEqual(handle["observed_sources"][0]["read"], False)
        read = AgentStep(2, "", tool_name="read_document", tool_result={
            "found": True, "path": "/tmp/fixture.txt", "filename": "fixture.txt", "content": "TCP retransmits."})
        self.window._on_assistant_step(handle, read)
        self.assertEqual(len(handle["observed_sources"]), 1)
        self.assertTrue(handle["observed_sources"][0]["read"])
        self.window._cancel_assistant()
        self.assertTrue(self.window._assistant_sources[0]["read"])
        self.assertIsNotNone(handle["card"].findChild(InlineFileCard))
        self.assertEqual(self.window._conversation.messages(), [])

    def test_inline_file_keyboard_activates_focused_result(self):
        from PyQt6.QtTest import QTest
        from rat.ui.chat_stream import InlineFileCard
        files = self._compact_files()
        self.window.show()
        self.window._deliver_assistant_reply('4 tệp', inline_files=files)
        app.processEvents()
        row = self.window.chat_stream.findChildren(InlineFileCard)[1]
        with patch('rat.ui.chat_stream.open_file_default') as opened, patch('rat.ui.chat_stream.trigger_quicklook') as preview:
            row.btn_open.setFocus()
            QTest.keyClick(row.btn_open, Qt.Key.Key_Space)
            row.btn_preview.setFocus()
            QTest.keyClick(row.btn_preview, Qt.Key.Key_Space)
            opened.assert_called_once_with(files[1].file_path)
            preview.assert_called_once_with(files[1].file_path)

    def test_inline_files_keep_same_widgets_across_reopen_and_modes(self):
        from rat.ui.chat_stream import InlineFileCard
        self.window._deliver_assistant_reply('4 tệp', inline_files=self._compact_files())
        rows = self.window.chat_stream.findChildren(InlineFileCard)
        with patch('rat.os.app.activate_macos_app'), patch('rat.ui.omnibar.configure_macos_fullscreen_overlay'):
            self.window.show_omnibar()
            self.window.hide()
            self.window.show_omnibar()
        for mode in (True, False):
            self.window.set_expanded(mode)
            self.assertEqual(self.window.chat_stream.findChildren(InlineFileCard), rows)
            self.assertTrue(all(row.isVisible() for row in rows))
        self.assertTrue(self.window.quick_suggestions.isHidden())

    def test_cancel_ignores_late_response_and_keeps_draft(self):
        from rat.engine.assistant_runtime import AgentResponse
        self.window._submit_chat_prompt("Tìm giúp slide")
        old = self.window._assistant_handle
        self.window.chat_composer_input.setText("Yêu cầu mới đang viết")
        self.window._cancel_assistant()
        self.window._on_assistant_response(old, AgentResponse("Đáp án đến muộn", [], 0, 0, 0))
        self.assertIn("Đã dừng", old["full_text"])
        self.assertEqual(self.window.chat_composer_input.text(), "Yêu cầu mới đang viết")
        self.assertEqual(self.window._conversation.messages(), [])

    def test_next_prompt_clears_old_results_without_bringing_onboarding_back(self):
        self.window._deliver_assistant_reply("4 tệp", inline_files=self._compact_files())
        self.window._submit_chat_prompt("Mình cần một ý tưởng")
        self.assertEqual(self.window.compact_file_list.count(), 0)
        self.assertTrue(self.window.quick_suggestions.isHidden())

    def test_starter_chips_prefill_user_goal_without_running_an_example(self):
        self.window.chip_buttons[1].click()
        self.assertEqual(self.window.chat_composer_input.text(), "Mình đang tìm tài liệu về ")
        self.assertIsNone(self.window._pending_chat_query)
        self.agent_start.assert_not_called()

    def test_bare_file_prefix_can_receive_a_model_clarification(self):
        from rat.engine.assistant_runtime import AgentResponse
        self.window._submit_chat_prompt("tìm file")
        handle = self.window._assistant_handle
        self.window._on_assistant_response(handle, AgentResponse("Bạn đang tìm tài liệu về chủ đề nào?", [], 0, 0, 0))
        self.assertIn("chủ đề nào", handle["full_text"])
        self.assertIsNone(self.window._pending_chat_query)

    def test_failure_preserves_observed_files_as_actionable_sources(self):
        from rat.engine.assistant_runtime import AgentResponse
        self.window._submit_chat_prompt("Tìm slide")
        handle = self.window._assistant_handle
        response = AgentResponse("", [], 10, 1, 0, error="step_budget_exhausted", sources=[
            {"type": "document", "path": "/tmp/notes.txt", "filename": "notes.txt", "read": False}])
        self.window._on_assistant_response(handle, response)
        self.assertIn("chưa hoàn tất", handle["full_text"])
        self.assertEqual(self.window.compact_file_list.count(), 1)
        self.assertEqual(self.window._conversation.messages(), [])

    def test_long_inline_file_names_fit_compact_width(self):
        from PyQt6.QtTest import QTest
        from rat.ui.chat_stream import InlineFileCard
        files = self._compact_files(1)
        files[0].file_name = 'Tích_phân_' * 60 + '.pdf'
        self.window.show()
        self.window._deliver_assistant_reply('Một tệp', inline_files=files)
        QTest.qWait(300)
        row = self.window.chat_stream.findChild(InlineFileCard)
        self.assertEqual(self.window.width(), 620)
        self.assertEqual(row.name_label.full_text, files[0].file_name)
        self.assertIn('…', row.name_label.text())
        self.assertLessEqual(row.name_label.fontMetrics().horizontalAdvance(row.name_label.text()), row.name_label.width())

    def test_growing_reply_stays_above_bottom_composer_in_same_box(self):
        from PyQt6.QtTest import QTest
        self.window.show()
        self.window._deliver_assistant_reply('Ừ.')
        QTest.qWait(250)
        bottom = self.window.geometry().bottom()
        self.window._deliver_assistant_reply('Một ý cần đọc cho rõ, không đè lên ô nhập. ' * 100)
        QTest.qWait(250)
        composer = self.window.chat_composer_input
        stream = self.window.chat_stream
        self.assertLessEqual(stream.mapTo(self.window, stream.rect().bottomLeft()).y(), composer.mapTo(self.window, composer.rect().topLeft()).y())
        self.assertEqual(self.window.geometry().bottom(), bottom)


class TestStreamReasoningWorker(unittest.TestCase):
    def test_interrupted_stream_is_not_claimed_as_a_complete_answer(self):
        worker = StreamReasoningWorker("Cùng nghĩ về bài viết")
        self.addCleanup(worker.deleteLater)
        answers = []
        worker.reasoning_finished.connect(lambda *args: answers.append(args))
        with patch("rat.engine.slm.slm_engine.is_service_running", return_value=True), \
             patch("rat.engine.slm.slm_engine.generate_stream", return_value=iter([("Ý chưa hoàn thành", False)])):
            worker.run()
        self.assertIn("Ý chưa hoàn thành", answers[0][0])
        self.assertEqual(answers[0][-2], "Phản hồi bị ngắt")

    def test_worker_sends_context_and_toned_down_persona_to_existing_stream_api(self):
        from rat.ui.chat_session import CHAT_SYSTEM_PROMPT
        history = [{"role": "user", "content": "Chọn hướng?"}, {"role": "assistant", "content": "Hướng B."}]
        worker = StreamReasoningWorker("Phản biện hướng vừa rồi", history=history)
        self.addCleanup(worker.deleteLater)
        answers = []
        worker.reasoning_finished.connect(lambda *args: answers.append(args))
        with patch("rat.engine.slm.slm_engine.is_service_running", return_value=True), \
             patch("rat.engine.slm.slm_engine.generate_stream", return_value=iter([("Một phản biện.", True)])) as stream, \
             patch("rat.engine.slm.slm_engine.model", "test-local-model"):
            worker.run()
        self.assertIn("Hướng B.", stream.call_args.kwargs["prompt"])
        self.assertIn("Phản biện hướng vừa rồi", stream.call_args.kwargs["prompt"])
        self.assertEqual(stream.call_args.kwargs["system_prompt"], CHAT_SYSTEM_PROMPT)
        self.assertEqual(answers[0][0], "Một phản biện.")
        self.assertEqual(answers[0][-1], "test-local-model")

    def test_unavailable_ai_does_not_return_a_canned_meta_reasoner_answer(self):
        worker = StreamReasoningWorker("Giúp tôi viết mở bài")
        self.addCleanup(worker.deleteLater)
        answers = []
        worker.reasoning_finished.connect(lambda *args: answers.append(args))
        with patch("rat.engine.slm.slm_engine.is_service_running", return_value=False), \
             patch("rat.engine.meta_reasoner.meta_reasoner.solve") as solve:
            worker.run()
        solve.assert_not_called()
        self.assertIn("Ollama", answers[0][0])
        self.assertEqual(answers[0][-2], "AI chưa sẵn sàng")


if __name__ == "__main__":
    unittest.main()
