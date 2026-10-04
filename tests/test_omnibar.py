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
        """Verify Omnibar initialized with 4 sections and defaults to Home (0)."""
        self.assertIsNotNone(self.window.search_input)
        self.assertEqual(len(self.window.section_buttons), 4)
        self.assertEqual(self.window.current_section_idx, 0)
        self.assertEqual(self.window.content_stack.currentIndex(), 0)
        self.assertIn("Huy", self.window.current_member.name)

    def test_switch_sections(self):
        """Verify switching through all sections (Home, Files, Schedule, Club) works smoothly."""
        for idx in range(4):
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

    def test_mascot_diagonal_popout_and_speech_bubble(self):
        """Verify diagonal pop-out combines X-shift, Y-slide, and 10 deg rotation with OutBack easing."""
        from PyQt6.QtCore import QEasingCurve
        mascot = self.window.mascot_peeking

        # Trigger speaking
        self.window.set_mascot_speaking("Xin chào bạn học!")
        self.assertTrue(mascot.is_speaking)

        # Check animation specs: ~350ms duration, OutBack easing
        self.assertEqual(mascot._pos_anim.duration(), 350)
        self.assertEqual(mascot._rot_anim.duration(), 350)
        self.assertEqual(mascot._pos_anim.easingCurve().type(), QEasingCurve.Type.OutBack)
        self.assertEqual(mascot._rot_anim.easingCurve().type(), QEasingCurve.Type.OutBack)

        # Check target values: Y slides up, X shifts 15-25px (+20px), rotation tilts to 10 deg
        self.assertEqual(mascot._pos_anim.endValue().x(), mascot.x_speaking)
        self.assertEqual(mascot._pos_anim.endValue().y(), mascot.y_speaking)
        self.assertEqual(mascot.x_speaking - mascot.x_idle, 20)
        self.assertLess(mascot.y_speaking, mascot.y_idle)
        self.assertEqual(mascot._rot_anim.endValue(), 10.0)

        # Simulate completion of pop-out animation
        mascot._anim_group.stop()
        mascot.move(mascot.x_speaking, mascot.y_speaking)
        mascot.rotation = mascot.rot_speaking
        mascot.speaking_popped_out.emit()
        app.processEvents()

        # Speech bubble appears right after pop-out completes
        self.assertFalse(self.window.speech_bubble.isHidden())
        self.assertIn("Xin chào bạn học!", self.window.speech_bubble.text())
        self.assertEqual(self.window.speech_bubble.tail_y, 46)

        # Retreat back to idle
        self.window.set_mascot_idle()
        self.assertFalse(mascot.is_speaking)
        self.assertEqual(mascot._rot_anim.endValue(), 0.0)
        self.assertEqual(mascot._pos_anim.endValue().x(), mascot.x_idle)
        self.assertEqual(mascot._pos_anim.endValue().y(), mascot.y_idle)

    def test_streaming_reply_reaches_compact_bubble(self):
        handle = self.window.chat_stream.create_streaming_message()
        self.window._on_reasoning_token(handle, "Đầu tiên, ")
        self.window._on_reasoning_token(handle, "xác định mục tiêu.")
        self.assertEqual(self.window.speech_bubble.text(), "Đầu tiên, xác định mục tiêu.")
        self.assertFalse(self.window.speech_bubble.isHidden())
        self.assertTrue(self.window.chat_stream.isHidden())
        self.assertEqual(self.window.speech_bubble.context_pill.text(), "Đang gõ")

    def test_final_reply_without_tokens_is_displayed(self):
        handle = self.window.chat_stream.create_streaming_message()
        answer = "Một câu trả lời **hoàn chỉnh** không có token streaming."
        self.window._on_reasoning_finished(handle, answer, [], 10, "Fallback", "Direct")
        self.assertEqual(handle["full_text"], answer)
        self.assertEqual(handle["ans_lbl"].text(), answer)
        self.assertIn("hoàn chỉnh", self.window.speech_bubble.dialogue.text())
        self.assertFalse(self.window.speech_bubble.isHidden())
        self.window.speech_bubble.btn_copy.click()
        self.assertEqual(QApplication.clipboard().text(), answer)
        self.assertTrue(handle["status_lbl"].isHidden())
        self.assertEqual(handle["badge_lbl"].text(), "· Direct")

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

    def test_read_full_reply_then_collapse_preserves_answer(self):
        answer = "Một đáp án dài. " * 100
        self.window._deliver_assistant_reply(answer)
        bubble = self.window.speech_bubble
        bubble.btn_hist.click()
        app.processEvents()
        self.assertFalse(self.window.is_expanded)
        self.assertTrue(self.window.is_reading_reply)
        self.assertFalse(self.window.reply_reader.isHidden())
        self.assertTrue(self.window.chat_stream.isHidden())
        self.assertTrue(bubble.isHidden())  # No duplicate answer above the reader.
        self.window.reply_reader.close_button.click()
        app.processEvents()
        self.assertFalse(self.window.is_expanded)
        self.assertFalse(self.window.is_reading_reply)
        self.assertFalse(bubble.isHidden())
        self.assertEqual(bubble.text(), answer.strip())

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

    def test_expanded_stream_does_not_duplicate_reply_in_bubble(self):
        self.window.set_expanded(True)
        handle = self.window.chat_stream.create_streaming_message()
        self.window._on_reasoning_token(handle, "Đáp án trong vùng đọc đầy đủ")
        self.window._on_reasoning_finished(handle, handle["full_text"], [], 10, "Direct", "Direct")
        self.assertTrue(self.window.speech_bubble.isHidden())
        self.window.set_expanded(False)
        self.assertFalse(self.window.speech_bubble.isHidden())
        self.assertEqual(self.window.speech_bubble.text(), "Đáp án trong vùng đọc đầy đủ")

    def test_polite_math_requests_are_calculated_not_hijacked(self):
        with patch("rat.ui.omnibar.StreamReasoningWorker") as worker:
            for query in ("Giúp tôi tính 2+2", "Chuột ơi, 2+2 bằng bao nhiêu?", "chào chuột tính 2^3"):
                with self.subTest(query=query):
                    self.window._submit_chat_prompt(query)
                    self.assertIn("= " + ("8" if "^" in query else "4"), self.window.speech_bubble.text())
                    self.assertNotIn("error:", self.window.speech_bubble.text())
                    self.assertIsNone(self.window._pending_chat_query)
            worker.assert_not_called()

    def test_invalid_arithmetic_has_actionable_feedback_not_a_raw_python_error(self):
        with patch("rat.ui.omnibar.StreamReasoningWorker") as worker:
            for query in ("1/0", "2 + * 3"):
                self.window._submit_chat_prompt(query)
                self.assertNotIn("error:", self.window.speech_bubble.text())
                self.assertNotIn("syntax", self.window.speech_bubble.text())
                self.assertIsNone(self.window._pending_chat_query)
            worker.assert_not_called()

    def test_questions_with_greeting_help_thanks_or_frustration_reach_ai(self):
        queries = (
            "Giúp tôi tìm hướng cho bài viết",
            "Chuột ơi, mình nên chọn hướng nào?",
            "Chào chuột giúp tôi nghĩ mở bài",
            "Cảm ơn, giờ phản biện hướng vừa rồi",
            "Tôi đang bực mình vì chưa nghĩ ra mở bài",
            "Chuột ngu, giúp tôi sửa mở bài",
            "Tôi có 2 ý tưởng + 3 phương án, giúp chọn hướng",
            "Hôm nay tôi muốn suy nghĩ về bài viết",
            "Lên ý tưởng cho CLB",
        )
        for query in queries:
            with self.subTest(query=query), patch("rat.ui.omnibar.StreamReasoningWorker") as worker:
                self.window._reset_chat()
                self.window._submit_chat_prompt(query)
                worker.assert_called_once_with(query, history=[])
                worker.return_value.start.assert_called_once()
                self.assertNotEqual(self.window._mascot_state, "angry")

    def test_standalone_shortcuts_still_work_without_model(self):
        with patch("rat.ui.omnibar.StreamReasoningWorker") as worker:
            for query in ("Chào chuột!", "help", "Chuột làm được gì?", "cảm ơn", "bye", "chuột ngốc"):
                with self.subTest(query=query):
                    self.window._submit_chat_prompt(query)
                    self.assertTrue(self.window.speech_bubble.has_reply)
                    self.assertIsNone(self.window._pending_chat_query)
            worker.assert_not_called()

    def test_actual_tool_requests_still_use_local_data(self):
        with patch("rat.ui.omnibar.StreamReasoningWorker") as worker:
            self.window._submit_chat_prompt("Chuột ơi, phòng C302 ở đâu?")
            self.assertIn("Tòa C", self.window.speech_bubble.text())
            self.window._submit_chat_prompt("Giúp tôi xem lịch học hôm nay")
            self.assertIn("Lịch", self.window.speech_bubble.text())
            self.window._submit_chat_prompt("Giúp tôi tìm file báo cáo")
            request = self.window._chat_file_request
            self.assertEqual(request["target"], "báo cáo")
            self.window._on_search_completed(request["request_id"], {"results": [], "latency_ms": 5})
            self.assertIn("chỉ mục", self.window.speech_bubble.text())
            self.assertNotIn("nhầm", self.window.speech_bubble.text())
            self.assertNotEqual(self.window._mascot_state, "angry")
            worker.assert_not_called()

    def test_ai_followup_receives_completed_user_and_assistant_turns(self):
        first_query = "Mình đang chọn hướng cho bài viết."
        answer = "Hướng B tập trung vào một luận điểm rõ hơn."
        with patch("rat.ui.omnibar.StreamReasoningWorker") as worker:
            self.window._submit_chat_prompt(first_query)
            worker.assert_called_once_with(first_query, history=[])
            finish = worker.return_value.reasoning_finished.connect.call_args.args[0]
            finish(answer, [], 10, "AI cục bộ", "Model thử nghiệm")
            followup = "Phản biện hướng vừa rồi."
            self.window._submit_chat_prompt(followup)
            self.assertEqual(worker.call_args.args, (followup,))
            self.assertEqual(worker.call_args.kwargs["history"], [
                {"role": "user", "content": first_query},
                {"role": "assistant", "content": answer},
            ])

    def test_direct_answers_are_also_in_followup_context(self):
        self.window._submit_chat_prompt("2+2")
        with patch("rat.ui.omnibar.StreamReasoningWorker") as worker:
            self.window._submit_chat_prompt("Giải thích kết quả vừa rồi")
            self.assertEqual(worker.call_args.kwargs["history"], [
                {"role": "user", "content": "2+2"},
                {"role": "assistant", "content": "2+2 = 4"},
            ])

    def test_pending_reply_preserves_second_draft_without_starting_another_worker(self):
        with patch("rat.ui.omnibar.StreamReasoningWorker") as worker:
            self.window._submit_chat_prompt("Mình đang chọn hướng cho bài viết.")
            self.window.chat_composer_input.setText("Câu tiếp theo đang viết")
            self.window._submit_chat_prompt(self.window.chat_composer_input.text())
            self.assertEqual(worker.call_count, 1)
            self.assertEqual(self.window.chat_composer_input.text(), "Câu tiếp theo đang viết")

    def test_reset_clears_context_and_ignores_old_worker_callbacks(self):
        self.window._submit_chat_prompt("2+2")
        with patch("rat.ui.omnibar.StreamReasoningWorker") as worker:
            self.window._submit_chat_prompt("Giải thích kết quả vừa rồi")
            token = worker.return_value.token_received.connect.call_args.args[0]
            finish = worker.return_value.reasoning_finished.connect.call_args.args[0]
            self.window._reset_chat()
            token("Token cũ")
            finish("Đáp án phiên cũ", [], 10, "AI cục bộ", "Model")
            self.assertFalse(self.window.speech_bubble.has_reply)
            self.assertEqual(self.window._conversation.messages(), [])
            self.window._submit_chat_prompt("Bắt đầu một ý mới")
            self.assertEqual(worker.call_args.kwargs["history"], [])

    def test_hide_and_reopen_keeps_semantic_context(self):
        self.window._submit_chat_prompt("2+2")
        with patch("rat.os.app.activate_macos_app"), patch("rat.ui.omnibar.configure_macos_fullscreen_overlay"):
            self.window.show_omnibar()
            self.window.hide()
            self.window.show_omnibar()
        with patch("rat.ui.omnibar.StreamReasoningWorker") as worker:
            self.window._submit_chat_prompt("Giải thích kết quả vừa rồi")
            self.assertEqual(worker.call_args.kwargs["history"][-1]["content"], "2+2 = 4")

    def test_completed_reply_does_not_show_thinking_status_when_expanded(self):
        handle = self.window.chat_stream.create_streaming_message(badge="Đang kết nối")
        self.window._on_reasoning_finished(handle, "Đáp án cuối", [], 10, "AI cục bộ", "Model thực tế")
        self.window.set_expanded(True)
        self.assertTrue(handle["status_lbl"].isHidden())
        self.assertEqual(handle["badge_lbl"].text(), "· Model thực tế")

    def test_connection_error_is_displayed_but_not_saved_as_a_model_answer(self):
        with patch("rat.ui.omnibar.StreamReasoningWorker") as worker:
            self.window._submit_chat_prompt("Cùng nghĩ về bài viết")
            finish = worker.return_value.reasoning_finished.connect.call_args.args[0]
            finish("Kiểm tra Ollama rồi thử lại.", [], 10, "AI chưa sẵn sàng", "Chưa kết nối")
            self.assertIn("Ollama", self.window.speech_bubble.text())
            self.assertEqual(self.window.speech_bubble.context_pill.text(), "Chưa kết nối")
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

    def test_actual_expand_collapse_respects_layout_minimum_and_bottom_anchor(self):
        from PyQt6.QtTest import QTest
        self.window.show()
        app.processEvents()
        for expanded in (False, True, False):
            self.window.set_expanded(expanded)
            QTest.qWait(200)
            actual = self.window.geometry()
            available = self.window.screen().availableGeometry()
            self.assertEqual(actual, lower_overlay_geometry(available, actual.width(), actual.height()))
            self.assertTrue(available.contains(actual))
        self.assertLess(self.window.height(), 260)

    def test_summon_uses_lower_screen_geometry_instead_of_old_top_anchor(self):
        screen = MagicMock()
        available = QRect(-1440, 40, 1440, 860)
        screen.availableGeometry.return_value = available
        with patch("rat.ui.omnibar.QGuiApplication.screenAt", return_value=screen), \
             patch("rat.os.app.activate_macos_app"), \
             patch("rat.ui.omnibar.configure_macos_fullscreen_overlay"):
            self.window.show_omnibar()
        self.assertEqual(self.window.geometry(), lower_overlay_geometry(available, self.window.width(), self.window.height()))

    @staticmethod
    def _compact_files(count=4):
        return [SearchResultItem(
            file_path=f"/tmp/rat-ui-fixtures/Tich_phan/Slide_tich_phan_{i + 1}.pdf",
            file_name=f"Slide_tich_phan_{i + 1}.pdf", file_ext=".pdf", file_size=1048576,
            modified_at=time.time() - 86400, score=90 - i, explanation="Tệp mẫu", snippet="",
        ) for i in range(count)]

    def test_file_results_are_visible_and_actionable_without_expanding_chat(self):
        files = self._compact_files()
        self.window.show()
        self.window._deliver_assistant_reply("4 tệp khớp ‘slides tích phân’.", strategy="Search", inline_files=files)
        app.processEvents()
        self.assertFalse(self.window.is_expanded)
        self.assertTrue(self.window.compact_file_list.isVisible())
        self.assertEqual(self.window.compact_file_list.count(), 4)
        self.assertTrue(self.window.quick_suggestions.isHidden())
        self.assertTrue(self.window.speech_bubble.btn_hist.isHidden())
        self.assertTrue(self.window.speech_bubble.btn_copy.isHidden())
        row = self.window.compact_file_list.itemWidget(self.window.compact_file_list.item(0))
        self.assertEqual(row.name_label.full_text, files[0].file_name)
        with patch("rat.ui.omnibar.open_file_default") as open_file, \
             patch("rat.ui.omnibar.trigger_quicklook") as preview, \
             patch("rat.ui.omnibar.reveal_in_finder") as reveal:
            row.btn_open.click()
            row.btn_preview.click()
            row.btn_reveal.click()
            open_file.assert_called_once_with(files[0].file_path)
            preview.assert_called_once_with(files[0].file_path)
            reveal.assert_called_once_with(files[0].file_path)

    def test_async_file_search_shows_loading_and_does_not_call_engine_on_gui_thread(self):
        from PyQt6.QtTest import QSignalSpy
        self.window.search_requested.disconnect(self.window.worker.do_search)
        spy = QSignalSpy(self.window.search_requested)
        self.window.engine.search.reset_mock()
        self.window._submit_chat_prompt("tìm file slides tích phân")
        self.assertEqual(len(spy), 1)
        self.assertEqual(spy[0][1], "slides tích phân")
        self.window.engine.search.assert_not_called()
        self.assertFalse(self.window.speech_bubble.has_reply)
        self.assertIn("Đang tìm", self.window.speech_bubble.text())
        self.window._on_search_completed(spy[0][0], {"results": self._compact_files(), "latency_ms": 1719})
        self.assertEqual(self.window.compact_file_list.count(), 4)
        self.assertEqual(self.window.speech_bubble.context_pill.text(), "Tìm tệp")
        self.assertNotIn("1719", self.window.speech_bubble.context_pill.text())
        self.assertIsNone(self.window._pending_chat_query)

    def test_compact_results_keyboard_opens_selected_file_not_a_recent_file(self):
        from PyQt6.QtTest import QTest
        files = self._compact_files()
        self.window.show()
        self.window._deliver_assistant_reply("4 tệp", inline_files=files)
        app.processEvents()
        self.window.chat_composer_input.setFocus()
        QTest.keyClick(self.window.chat_composer_input, Qt.Key.Key_Down)
        self.assertTrue(self.window.compact_file_list.hasFocus())
        QTest.keyClick(self.window.compact_file_list, Qt.Key.Key_Down)
        self.assertEqual(self.window.compact_file_list.currentRow(), 1)
        with patch("rat.ui.omnibar.open_file_default") as open_file, patch("rat.ui.omnibar.trigger_quicklook") as preview:
            QTest.keyClick(self.window.compact_file_list, Qt.Key.Key_Return)
            QTest.keyClick(self.window.compact_file_list, Qt.Key.Key_Space)
            open_file.assert_called_once_with(files[1].file_path)
            preview.assert_called_once_with(files[1].file_path)
        QTest.keyClick(self.window.compact_file_list, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(QApplication.clipboard().text(), files[1].file_path)

    def test_files_survive_hide_reopen_and_expanded_round_trip(self):
        files = self._compact_files()
        self.window._deliver_assistant_reply("4 tệp", inline_files=files)
        with patch("rat.os.app.activate_macos_app"), patch("rat.ui.omnibar.configure_macos_fullscreen_overlay"):
            self.window.show_omnibar()
            self.window.hide()
            self.window.show_omnibar()
        self.window.set_expanded(True)
        self.assertTrue(self.window.compact_file_list.isHidden())
        self.window.set_expanded(False)
        self.assertFalse(self.window.compact_file_list.isHidden())
        self.assertEqual(self.window.compact_file_list.count(), 4)
        self.assertTrue(self.window.quick_suggestions.isHidden())
        self.assertTrue(self.window.speech_bubble.btn_hist.isHidden())

    def test_reset_ignores_an_old_async_file_search_response(self):
        self.window.search_requested.disconnect(self.window.worker.do_search)
        self.window._submit_chat_prompt("tìm file slides")
        request_id = self.window._chat_file_request["request_id"]
        self.window._reset_chat()
        self.window._on_search_completed(request_id, {"results": self._compact_files()})
        self.assertEqual(self.window.compact_file_list.count(), 0)
        self.assertFalse(self.window.speech_bubble.has_reply)
        self.assertEqual(self.window._conversation.messages(), [])

    def test_next_prompt_clears_old_results_without_bringing_onboarding_back(self):
        self.window._deliver_assistant_reply("4 tệp", inline_files=self._compact_files())
        with patch("rat.ui.omnibar.StreamReasoningWorker"):
            self.window._submit_chat_prompt("Cùng nghĩ hướng mở bài")
        self.assertEqual(self.window.compact_file_list.count(), 0)
        self.assertTrue(self.window.compact_file_list.isHidden())
        self.assertTrue(self.window.quick_suggestions.isHidden())

    def test_starter_chips_prefill_actual_intent_instead_of_searching_an_unrelated_example(self):
        with patch("rat.ui.omnibar.StreamReasoningWorker") as worker:
            self.window.chip_buttons[1].click()
            self.assertEqual(self.window.chat_composer_input.text(), "tìm file ")
            self.assertIsNone(self.window._pending_chat_query)
            self.window.chat_stream.prompt_clicked.emit("Phản biện giúp mình ý này: ")
            self.assertEqual(self.window.chat_composer_input.text(), "Phản biện giúp mình ý này: ")
            self.assertTrue(self.window.chat_composer_send.isEnabled())
            worker.assert_not_called()

    def test_bare_file_prefix_asks_for_a_target_without_starting_search(self):
        from PyQt6.QtTest import QSignalSpy
        spy = QSignalSpy(self.window.search_requested)
        self.window._submit_chat_prompt("tìm file")
        self.assertEqual(len(spy), 0)
        self.assertIn("tệp nào", self.window.speech_bubble.text())
        self.assertIsNone(self.window._pending_chat_query)

    def test_search_failure_is_not_reported_as_a_definitive_empty_result(self):
        self.window.search_requested.disconnect(self.window.worker.do_search)
        self.window._submit_chat_prompt("tìm file slides")
        request_id = self.window._chat_file_request["request_id"]
        self.window._on_search_completed(request_id, {"results": [], "error": True})
        self.assertIn("chưa hoàn tất", self.window.speech_bubble.text())
        self.assertIsNone(self.window._pending_chat_query)

    def test_long_file_names_are_elided_without_widening_the_overlay(self):
        from PyQt6.QtTest import QTest
        files = self._compact_files(1)
        files[0].file_name = "Tích_phân_" * 60 + ".pdf"
        self.window.show()
        self.window._deliver_assistant_reply("Một tệp", inline_files=files)
        QTest.qWait(200)
        row = self.window.compact_file_list.itemWidget(self.window.compact_file_list.item(0))
        self.assertEqual(self.window.width(), 652)
        self.assertEqual(row.name_label.full_text, files[0].file_name)
        self.assertIn("…", row.name_label.text())
        self.assertLessEqual(row.name_label.fontMetrics().horizontalAdvance(row.name_label.text()), row.name_label.width())

    def test_growing_reply_bubble_stays_above_the_composer(self):
        from PyQt6.QtTest import QTest
        self.window.show()
        self.window._deliver_assistant_reply("Ừ.")
        QTest.qWait(150)
        self.window._deliver_assistant_reply("Một ý cần đọc cho rõ, không đè lên ô nhập. " * 100)
        QTest.qWait(200)
        bubble = self.window.speech_bubble
        self.assertLessEqual(bubble.y() + bubble.height(), self.window.container.y())

    def test_read_full_shows_only_latest_answer_without_losing_multiline_draft(self):
        answer = "## Hướng B\n\nMột luận điểm rõ.\n\n- Điểm mạnh.\n- Điểm cần kiểm chứng."
        self.window._deliver_assistant_reply("Câu trả lời trước không nằm trong vùng đọc này.")
        self.window._deliver_assistant_reply(answer)
        draft = "Phản biện giúp mình:\nĐiểm nào còn yếu?"
        self.window.chat_composer_input.setText(draft)
        self.window.show()
        self.window.speech_bubble.btn_hist.click()
        app.processEvents()
        self.assertTrue(self.window.is_reading_reply)
        self.assertFalse(self.window.is_expanded)
        self.assertTrue(self.window.chat_stream.isHidden())
        self.assertTrue(self.window.speech_bubble.isHidden())
        self.assertFalse(self.window.mascot_peeking.isHidden())
        self.assertEqual(self.window.reply_reader.full_reply, answer)
        self.assertNotIn("Câu trả lời trước", self.window.reply_reader.body.toPlainText())
        self.assertEqual(self.window.chat_composer_input.text(), draft)
        reader_bottom = self.window.reply_reader.mapTo(self.window.container, self.window.reply_reader.rect().bottomLeft()).y()
        self.assertLess(reader_bottom, self.window.quick_bar.y())
        self.window.reply_reader.copy_button.click()
        self.assertEqual(QApplication.clipboard().text(), answer)

    def test_escape_closes_reader_before_hiding_and_preserves_draft(self):
        from PyQt6.QtTest import QTest
        self.window.show()
        self.window._deliver_assistant_reply("Một câu cần đọc. " * 60)
        self.window.read_full_reply()
        self.window.chat_composer_input.setText("Câu tiếp\nĐang viết")
        self.window.activateWindow()
        self.window.reply_reader.body.setFocus()
        app.processEvents()
        QTest.keyClick(self.window.reply_reader.body, Qt.Key.Key_Escape)
        app.processEvents()
        self.assertFalse(self.window.is_reading_reply)
        self.assertFalse(self.window.isHidden())
        self.assertEqual(self.window.chat_composer_input.text(), "Câu tiếp\nĐang viết")
        self.assertTrue(self.window.chat_composer_input.hasFocus())

    def test_hide_reopen_preserves_in_place_reader_and_multiline_draft(self):
        self.window._deliver_assistant_reply("Một câu cần đọc. " * 60)
        self.window.read_full_reply()
        self.window.chat_composer_input.setText("Ý đầu\nÝ tiếp 🐀")
        with patch("rat.os.app.activate_macos_app"), patch("rat.ui.omnibar.configure_macos_fullscreen_overlay"):
            self.window.hide()
            self.window.show_omnibar()
        self.assertTrue(self.window.is_reading_reply)
        self.assertFalse(self.window.reply_reader.isHidden())
        self.assertTrue(self.window.speech_bubble.isHidden())
        self.assertEqual(self.window.chat_composer_input.text(), "Ý đầu\nÝ tiếp 🐀")

    def test_full_conversation_toggle_closes_reader_without_losing_answer(self):
        answer = "Một câu cần đọc. " * 60
        self.window._deliver_assistant_reply(answer)
        self.window.read_full_reply()
        self.window.toggle_expand()
        self.assertTrue(self.window.is_expanded)
        self.assertFalse(self.window.is_reading_reply)
        self.assertTrue(self.window.reply_reader.isHidden())
        self.assertEqual(self.window.reply_reader.full_reply, answer)

    def test_composer_shift_enter_then_enter_sends_exact_multiline_prompt_once(self):
        from PyQt6.QtTest import QTest
        composer = self.window.chat_composer_input
        composer.setText("Cùng nghĩ về hai hướng:")
        composer.setCursorPosition(len(composer.text()))
        with patch("rat.ui.omnibar.StreamReasoningWorker") as worker:
            QTest.keyClick(composer, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
            composer.insertPlainText("A hay B 🐀?")
            worker.assert_not_called()
            query = "Cùng nghĩ về hai hướng:\nA hay B 🐀?"
            self.assertEqual(composer.text(), query)
            QTest.keyClick(composer, Qt.Key.Key_Return)
            worker.assert_called_once_with(query, history=[])
            self.assertEqual(composer.text(), "")
            self.assertEqual(composer.height(), composer.MIN_HEIGHT)

    def test_composer_arrows_edit_draft_instead_of_navigating_file_results(self):
        from PyQt6.QtTest import QTest
        self.window.show()
        self.window._deliver_assistant_reply("4 tệp", inline_files=self._compact_files())
        composer = self.window.chat_composer_input
        composer.setText("Dòng đầu\nDòng cuối")
        composer.setCursorPosition(len(composer.text()))
        composer.setFocus()
        app.processEvents()
        QTest.keyClick(composer, Qt.Key.Key_Up)
        self.assertLess(composer.textCursor().position(), len(composer.text()))
        self.assertEqual(self.window.compact_file_list.currentRow(), 0)
        self.assertTrue(composer.hasFocus())

    def test_multiline_growth_keeps_bottom_anchor_and_resets_height(self):
        from PyQt6.QtTest import QTest
        self.window.show()
        QTest.qWait(200)
        bottom = self.window.geometry().bottom()
        composer = self.window.chat_composer_input
        composer.setText("Một\nHai\nBa\nBốn")
        app.processEvents()
        self.assertEqual(self.window.geometry().bottom(), bottom)
        self.assertEqual(self.window.quick_bar.height(), composer.height())
        self.assertGreater(self.window.height(), 238)
        composer.clear()
        app.processEvents()
        self.assertEqual(self.window.geometry().bottom(), bottom)
        self.assertEqual(self.window.height(), 238)

    def test_busy_enter_keeps_multiline_second_draft_and_does_not_start_another_worker(self):
        from PyQt6.QtTest import QTest
        with patch("rat.ui.omnibar.StreamReasoningWorker") as worker:
            self.window._submit_chat_prompt("Cùng nghĩ một hướng")
            self.window.chat_composer_input.setText("Một câu nữa:\nGiữ câu này lại.")
            QTest.keyClick(self.window.chat_composer_input, Qt.Key.Key_Return)
            self.assertEqual(worker.call_count, 1)
            self.assertEqual(self.window.chat_composer_input.text(), "Một câu nữa:\nGiữ câu này lại.")

    def test_next_prompt_closes_old_reader_and_reset_clears_its_contents(self):
        self.window._deliver_assistant_reply("Một câu cần đọc. " * 60)
        self.window.read_full_reply()
        with patch("rat.ui.omnibar.StreamReasoningWorker"):
            self.window._submit_chat_prompt("Cùng nghĩ một hướng tiếp")
        self.assertFalse(self.window.is_reading_reply)
        self.assertEqual(self.window.reply_reader.full_reply, "")
        self.window._reset_chat()
        self.assertTrue(self.window.reply_reader.isHidden())
        self.assertEqual(self.window.chat_composer_input.height(), self.window.chat_composer_input.MIN_HEIGHT)

    def test_compact_preview_is_at_most_three_lines_and_keeps_structured_read_action(self):
        answer = "## Ba bước\n\n- Phác dàn ý.\n- Tìm bằng chứng.\n- Viết bản nháp."
        self.window._deliver_assistant_reply(answer)
        bubble = self.window.speech_bubble
        bounds = bubble.dialogue.fontMetrics().boundingRect(
            QRect(0, 0, 420, 10000), Qt.TextFlag.TextWordWrap, bubble.dialogue.text()
        )
        self.assertLessEqual(bounds.height(), bubble.dialogue.fontMetrics().lineSpacing() * 3)
        self.assertNotIn("##", bubble.dialogue.text())
        self.assertFalse(bubble.btn_hist.isHidden())

    def test_reader_expansion_and_multiline_composer_stay_inside_screen(self):
        from PyQt6.QtTest import QTest
        self.window.show()
        self.window._deliver_assistant_reply("Một câu cần đọc. " * 60)
        self.window.read_full_reply()
        self.window.chat_composer_input.setText("Một\nHai\nBa\nBốn")
        QTest.qWait(200)
        geometry = self.window.geometry()
        available = self.window.screen().availableGeometry()
        self.assertTrue(available.contains(geometry))
        self.assertEqual(geometry, lower_overlay_geometry(available, geometry.width(), geometry.height()))
        self.assertEqual(self.window.width(), 652)

    def test_full_chat_places_composer_and_hint_below_conversation(self):
        from PyQt6.QtCore import QPoint
        from PyQt6.QtTest import QTest
        self.window.show()
        self.window._deliver_assistant_reply("Một câu để nghĩ tiếp.")
        self.window.set_expanded(True)
        self.window.chat_composer_input.setText("Một\nHai\nBa\nBốn 🐀")
        QTest.qWait(250)
        layout = self.window.container_layout
        self.assertLess(layout.indexOf(self.window.content_stack), layout.indexOf(self.window.hairline_divider))
        self.assertLess(layout.indexOf(self.window.hairline_divider), layout.indexOf(self.window.quick_bar))
        self.assertLess(layout.indexOf(self.window.quick_bar), layout.indexOf(self.window.compact_footer))
        chat_bottom = self.window.content_stack.mapTo(self.window, QPoint(0, self.window.content_stack.height())).y()
        composer_top = self.window.quick_bar.mapTo(self.window, QPoint(0, 0)).y()
        self.assertLess(chat_bottom, composer_top)
        self.assertEqual(self.window.size().width(), 788)
        self.assertEqual(self.window.size().height(), 580)
        self.assertTrue(self.window.action_footer.isHidden())
        self.assertFalse(self.window.compact_footer.isHidden())
        self.assertFalse(self.window.hairline_divider.isHidden())
        self.assertIn("Shift+↵", self.window.compact_hint.text())
        self.assertFalse(self.window.mascot_peeking.isHidden())
        self.assertEqual(self.window.mascot_peeking.size().width(), 146)

    def test_conversation_layout_roundtrip_preserves_reader_files_and_draft(self):
        answer = "## Une idée\n\nMột câu cần đọc tiếp. " * 30
        draft = "Một ý\nHai ý 🐀"
        self.window._deliver_assistant_reply(answer, inline_files=self._compact_files())
        self.window.chat_composer_input.setText(draft)
        for _ in range(3):
            self.window.set_expanded(True)
            self.window.set_expanded(False)
            self.window.read_full_reply()
            layout = self.window.container_layout
            self.assertLess(layout.indexOf(self.window.reply_reader), layout.indexOf(self.window.quick_bar))
            self.assertLess(layout.indexOf(self.window.quick_bar), layout.indexOf(self.window.compact_file_list))
            self.assertTrue(self.window.hairline_divider.isHidden())
            self.assertTrue(self.window.action_footer.isHidden())
            self.assertEqual(self.window.reply_reader.full_reply, answer)
            self.assertEqual(self.window.chat_composer_input.text(), draft)
        self.window.set_reply_reader_open(False)
        self.assertFalse(self.window.compact_file_list.isHidden())

    def test_other_sections_keep_their_footer_without_chat_chrome(self):
        self.window.set_expanded(True)
        for idx in (1, 2, 3):
            self.window.switch_section(idx)
            self.assertFalse(self.window.action_footer.isHidden())
            self.assertTrue(self.window.compact_footer.isHidden())
            self.assertTrue(self.window.hairline_divider.isHidden())
            self.assertTrue(self.window.quick_bar.isHidden())
        self.window.switch_section(0)
        self.assertTrue(self.window.action_footer.isHidden())
        self.assertFalse(self.window.compact_footer.isHidden())

    def test_full_mode_mascot_hops_to_own_side_space_and_returns_to_quick_rim(self):
        from PyQt6.QtTest import QTest
        self.window.show()
        answer = "Giữ nguyên câu trả lời và câu đang gõ."
        self.window._deliver_assistant_reply(answer)
        draft = "Một câu tiếp\nHai ý 🐀"
        self.window.chat_composer_input.setText(draft)
        self.window.set_expanded(True)
        QTest.qWait(450)
        mascot = self.window.mascot_peeking
        self.assertTrue(mascot.side_docked)
        self.assertLess(mascot.geometry().right(), self.window.container.x())
        self.assertTrue(self.window.centralWidget().rect().contains(mascot.geometry()))
        self.assertFalse(mascot.geometry().intersects(self.window.container.geometry()))
        self.assertEqual(mascot.width(), 146)
        self.assertEqual(mascot._mascot_pixmap.cacheKey(), mascot._mascot_full_pixmap.cacheKey())
        self.assertEqual(self.window.container.width(), 620)
        self.assertEqual(self.window.container.y(), 16)
        self.assertTrue(self.window.screen().availableGeometry().contains(self.window.geometry()))
        self.assertTrue(self.window.speech_bubble.isHidden())
        for state in ("thinking", "searching", "angry", "idle"):
            self.window.set_mascot_state(state)
            self.assertLess(mascot.geometry().right(), self.window.container.x())
        self.window.set_expanded(False)
        QTest.qWait(450)
        self.assertFalse(mascot.side_docked)
        self.assertEqual(mascot._mascot_pixmap.cacheKey(), mascot._mascot_bust_pixmap.cacheKey())
        self.assertEqual(mascot.x_speaking - mascot.x_idle, 20)
        self.assertEqual(mascot.rot_speaking, 10.0)
        self.assertEqual(self.window.width(), 652)
        self.assertEqual(self.window.container.y(), 120)
        self.assertEqual(self.window.chat_composer_input.text(), draft)
        self.assertEqual(self.window.reply_reader.full_reply, answer)

    def test_full_reply_native_selection_and_escape_after_keyboard_jump_still_work(self):
        from PyQt6.QtGui import QTextCursor
        from PyQt6.QtTest import QTest
        self.window.show()
        self.window.set_expanded(True)
        handle = self.window.chat_stream.create_streaming_message()
        self.window._on_reasoning_token(handle, "\n\n".join(f"Đoạn {i}: một ý cần đọc." for i in range(40)))
        QTest.qWait(250)
        body = handle["ans_lbl"]
        body.setFocus()
        cursor = body.textCursor()
        cursor.setPosition(0)
        cursor.setPosition(6, QTextCursor.MoveMode.KeepAnchor)
        body.setTextCursor(cursor)
        QTest.keyClick(body, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(QApplication.clipboard().text(), body.textCursor().selectedText())
        stream = self.window.chat_stream
        stream.verticalScrollBar().setValue(25)
        stream.jump_button.setFocus()
        QTest.keyClick(stream.jump_button, Qt.Key.Key_Space)
        QTest.qWait(200)
        self.assertEqual(stream.verticalScrollBar().value(), stream.verticalScrollBar().maximum())
        self.window.chat_composer_input.setText("Giữ draft này 🐀")
        QTest.keyClick(stream, Qt.Key.Key_Escape)
        self.assertFalse(self.window.is_expanded)
        self.assertEqual(self.window.chat_composer_input.text(), "Giữ draft này 🐀")

    def test_preview_panel_ask_requested_connected(self):
        panel = self.window.preview_panel
        calls = []
        panel.ask_requested.connect(lambda p, n, q: calls.append((p, n, q)))
        panel.ask_requested.emit("/tmp/test.txt", "test.txt", "Tóm tắt?")
        self.assertEqual(calls, [("/tmp/test.txt", "test.txt", "Tóm tắt?")])
        # Verify qa_finished is wired to set_qa_answer
        self.window.qa_worker.qa_finished.emit({"answer": "Nội dung tóm tắt mẫu.", "engine": "AI Test"})
        self.assertIn("Nội dung tóm tắt mẫu", panel.qa_response_box.text())

    def test_action_menu_ask_ai_and_reindex_handlers(self):
        from rat.engine.reranker import SearchResultItem
        dummy_item = SearchResultItem(
            file_path="/tmp/fixture.pdf",
            file_name="fixture.pdf",
            file_ext=".pdf",
            file_size=1024,
            modified_at=1000.0,
            score=10.0,
            snippet="dummy content",
            explanation="Tệp PDF",
        )
        self.window._current_action_item = dummy_item
        # Test ask_ai
        self.window.switch_section(1)
        self.window._handle_action("ask_ai")
        self.assertEqual(self.window.current_section_idx, 0)
        self.assertIn("fixture.pdf", self.window.chat_composer_input.text())

        # Test reindex_file with mock
        with patch("rat.crawler.indexer.Indexer.index_single_file", return_value=True) as mock_idx, \
             patch("os.path.exists", return_value=True):
            self.window._handle_action("reindex_file")
            mock_idx.assert_called_once_with("/tmp/fixture.pdf", force=True)
            self.assertIn("Đã cập nhật chỉ mục", self.window.footer_status.text())


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
