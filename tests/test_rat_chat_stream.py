"""Presentation-only conversation regressions; no model, index or personal files."""

import os
import sys
import unittest
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, Qt, QUrl
from PyQt6.QtGui import QTextCursor, QWheelEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QFrame, QLabel, QPushButton

from rat.ui.chat_stream import ChatStreamWidget, MessageDetails, UserMessageRow
from rat.ui.reply_text import ConversationReplyBody
from rat.ui.theme import CHAT_ACTION_QSS, CHAT_CARD_QSS

app = QApplication.instance() or QApplication(sys.argv)


class TestChatStreamPresentation(unittest.TestCase):
    def setUp(self):
        self.stream = ChatStreamWidget()
        self.stream.resize(580, 320)
        self.stream.show()
        app.processEvents()

    def tearDown(self):
        self.stream.close()
        self.stream.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()

    def test_stream_model_and_processing_details_are_collapsed_not_removed(self):
        handle = self.stream.create_streaming_message(badge="model-mẫu")
        self.assertTrue(handle["badge_lbl"].isHidden())
        self.assertTrue(handle["details_button"].isHidden())
        self.assertFalse(handle["copy_button"].isEnabled())
        self.stream.append_stream_token(handle, "Một câu trả lời.")
        self.stream.finalize_stream(handle, ["Ngữ cảnh mẫu", "Không phải CoT"], 125)
        panel = handle["details_panel"]
        self.assertTrue(panel.isHidden())
        self.assertFalse(handle["details_button"].isHidden())
        self.assertTrue(handle["status_lbl"].isHidden())
        text = "\n".join(label.text() for label in panel.findChildren(QLabel))
        self.assertIn("Mô hình: model-mẫu", text)
        self.assertIn("125 ms", text)
        self.assertIn("Không phải CoT", text)
        handle["details_button"].setFocus()
        QTest.keyClick(handle["details_button"], Qt.Key.Key_Space)
        self.assertFalse(panel.isHidden())
        self.assertTrue(handle["details_button"].isChecked())
        handle["details_button"].click()
        self.assertTrue(panel.isHidden())

    def test_direct_and_streaming_cards_share_style_and_small_header_actions(self):
        self.stream.add_assistant_message("Một câu trực tiếp.")
        handle = self.stream.create_streaming_message()
        self.stream.append_stream_token(handle, "Một câu streaming.")
        self.stream.finalize_stream(handle)
        QTest.qWait(30)
        cards = [card for card in self.stream.findChildren(QFrame) if card.objectName() == "AssistantCard"]
        self.assertEqual(len(cards), 2)
        for card in cards:
            self.assertEqual(card.styleSheet(), CHAT_CARD_QSS)
            self.assertLessEqual(card.height(), 85)
            buttons = card.findChildren(QPushButton)
            for button in buttons:
                self.assertEqual(button.styleSheet(), CHAT_ACTION_QSS)
            copies = [button for button in buttons if button.text() == "Sao chép"]
            self.assertEqual(len(copies), 1)
            answer = handle["ans_lbl"] if card is handle["card"] else card.layout().itemAt(1).widget()
            self.assertLess(copies[0].y(), answer.y())
        self.assertTrue(cards[0].findChild(MessageDetails) is None)
        self.assertFalse(hasattr(self.stream, "_mascot_pixmap"))

    def test_finalization_is_idempotent_and_copies_final_raw_markdown(self):
        handle = self.stream.create_streaming_message(badge="modèle")
        self.stream.append_stream_token(handle, "Bản nháp")
        answer = "## Tiếng Việt 🐀\n\n**Bản cuối**\n- Một\n- Hai"
        handle["full_text"] = answer
        self.stream.finalize_stream(handle, ["mẫu"], 20)
        self.stream.finalize_stream(handle, ["mẫu"], 20)
        self.assertEqual(len(handle["card"].findChildren(MessageDetails)), 1)
        self.assertEqual(len(handle["card"].findChildren(QPushButton)), 2)
        handle["copy_button"].click()
        self.assertEqual(QApplication.clipboard().text(), answer)
        self.assertEqual(handle["copy_timer"].parent(), handle["copy_button"])
        self.assertTrue(handle["copy_timer"].isActive())

    def test_reset_removes_user_rows_and_cancels_owned_copy_and_scroll_timers(self):
        self.stream.add_user_message("<b>Không phải HTML</b>\nÝ tiếp 🐀")
        bubble = self.stream.findChild(QFrame, "UserBubble")
        label = bubble.findChild(QLabel)
        self.assertEqual(label.textFormat(), Qt.TextFormat.PlainText)
        self.assertIn("<b>", label.text())
        handle = self.stream.create_streaming_message()
        self.stream.append_stream_token(handle, "Một câu.")
        self.stream.finalize_stream(handle)
        handle["copy_button"].click()
        self.stream.clear_chat()
        self.assertEqual(self.stream.layout.count(), 1)
        self.assertTrue(self.stream.is_empty())
        self.assertFalse(self.stream._scroll_timer.isActive())
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertTrue(sip.isdeleted(bubble))
        self.assertTrue(sip.isdeleted(handle["copy_timer"]))
        self.assertEqual(len(self.stream.findChildren(QFrame, "UserBubble")), 0)
        self.assertEqual(len(self.stream.findChildren(QFrame, "AssistantCard")), 0)

    def test_metadata_is_literal_text_and_never_html(self):
        self.stream.add_assistant_message("Réponse", ["<b>mẫu</b> & 🐀"], 3)
        panel = self.stream.findChild(MessageDetails)
        self.assertTrue(panel.isHidden())
        for label in panel.findChildren(QLabel):
            self.assertEqual(label.textFormat(), Qt.TextFormat.PlainText)
        self.assertIn("<b>mẫu</b>", panel.findChildren(QLabel)[-1].text())

    def test_new_message_scroll_waits_for_layout_and_resize_keeps_current_bottom(self):
        for index in range(8):
            self.stream.add_user_message(f"Câu hỏi {index}")
            self.stream.add_assistant_message("Một câu trả lời để đọc tiếp. " * 4)
        QTest.qWait(200)
        scrollbar = self.stream.verticalScrollBar()
        self.assertGreater(scrollbar.maximum(), 0)
        self.assertEqual(scrollbar.value(), scrollbar.maximum())
        self.stream.resize(580, 250)
        QTest.qWait(200)
        self.assertEqual(scrollbar.value(), scrollbar.maximum())
        # Resizing alone must not yank a reader back down from older messages.
        scrollbar.setValue(25)
        self.stream.resize(580, 230)
        QTest.qWait(200)
        self.assertLess(scrollbar.value(), scrollbar.maximum())

    def _long_reply(self):
        handle = self.stream.create_streaming_message()
        self.stream.append_stream_token(handle, "\n\n".join(
            f"Đoạn {index}: một ý cần đọc cho rõ, không phải nội dung của model thật."
            for index in range(24)
        ))
        QTest.qWait(200)
        return handle

    def test_reading_history_is_not_yanked_by_tokens_or_finalization_and_jump_resumes(self):
        handle = self._long_reply()
        scrollbar = self.stream.verticalScrollBar()
        scrollbar.setValue(45)
        value = scrollbar.value()
        self.assertFalse(self.stream._follow_latest)
        self.assertFalse(self.stream.jump_button.isHidden())
        for token in ("\n\nÝ mới", " được bổ sung."):
            self.stream.append_stream_token(handle, token)
        self.stream.finalize_stream(handle, ["metadata mẫu"], 5)
        QTest.qWait(200)
        self.assertEqual(scrollbar.value(), value)
        self.assertIn("Phản hồi mới", self.stream.jump_button.text())
        self.assertTrue(self.stream.viewport().rect().contains(self.stream.jump_button.geometry()))
        self.stream.jump_button.setFocus()
        QTest.keyClick(self.stream.jump_button, Qt.Key.Key_Space)
        QTest.qWait(200)
        self.assertEqual(scrollbar.value(), scrollbar.maximum())
        self.assertTrue(self.stream.jump_button.isHidden())
        self.stream.append_stream_token(handle, "\n\nĐọc tiếp từ đây.")
        QTest.qWait(200)
        self.assertEqual(scrollbar.value(), scrollbar.maximum())

    def test_wheel_up_cancels_an_already_scheduled_follow_and_new_prompt_returns_to_bottom(self):
        handle = self._long_reply()
        self.stream.append_stream_token(handle, "\n\nToken mới.")
        event = QWheelEvent(QPointF(100, 100), QPointF(100, 100), QPoint(), QPoint(0, 120),
                            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                            Qt.ScrollPhase.NoScrollPhase, False)
        QApplication.sendEvent(self.stream.viewport(), event)
        value = self.stream.verticalScrollBar().value()
        self.assertFalse(self.stream._follow_latest)
        QTest.qWait(200)
        self.assertEqual(self.stream.verticalScrollBar().value(), value)
        self.stream.add_user_message("Giờ nghĩ tiếp ý này.")
        QTest.qWait(200)
        self.assertTrue(self.stream._follow_latest)
        self.assertEqual(self.stream.verticalScrollBar().value(), self.stream.verticalScrollBar().maximum())

    def test_reply_document_has_headings_lists_code_spacing_and_keeps_selection(self):
        handle = self.stream.create_streaming_message()
        text = "## Một hướng thử\n\nĐoạn đầu.\n\n- Ý A\n- Ý B\n\n```python\nx = 1\n```"
        self.stream.append_stream_token(handle, text)
        QTest.qWait(100)
        body = handle["ans_lbl"]
        self.assertIsInstance(body, ConversationReplyBody)
        self.assertEqual(body.text(), text)
        self.assertIn("x = 1", body.toPlainText())
        blocks = []
        block = body.document().begin()
        while block.isValid():
            blocks.append((block.text(), block.blockFormat(), block.textList()))
            self.assertGreaterEqual(block.blockFormat().lineHeight(), 140)
            block = block.next()
        self.assertTrue(any(fmt.headingLevel() for _, fmt, _ in blocks))
        self.assertEqual([text for text, _, listing in blocks if listing], ["Ý A", "Ý B"])
        cursor = body.textCursor()
        cursor.setPosition(0)
        cursor.setPosition(6, QTextCursor.MoveMode.KeepAnchor)
        body.setTextCursor(cursor)
        selected = body.textCursor().selectedText()
        self.stream.append_stream_token(handle, "\n\nMột kết luận nữa.")
        self.assertEqual(body.textCursor().selectedText(), selected)
        self.assertEqual(body.verticalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.assertIsNone(body.loadResource(2, QUrl("file:///tmp/private.png")))
        with patch("rat.ui.reply_text.QDesktopServices.openUrl") as open_url:
            body._open_link(QUrl("file:///tmp/private.txt"))
            body._open_link(QUrl("javascript:alert(1)"))
            open_url.assert_not_called()
            body._open_link(QUrl("https://example.com/reference"))
            open_url.assert_called_once()

    def test_user_bubbles_use_natural_width_and_wrap_at_available_width(self):
        texts = ["Ừ.", "Mình nên viết dàn ý trước hay đọc tài liệu trước?", "Dòng đầu 🐀\nDòng tiếp"]
        for text in texts:
            self.stream.add_user_message(text)
        QTest.qWait(100)
        rows = self.stream.findChildren(UserMessageRow)
        self.assertEqual(len(rows), len(texts))
        widths = [row.bubble.width() for row in rows]
        self.assertLess(widths[0], 70)
        self.assertGreater(widths[1], 260)
        for row, text in zip(rows, texts):
            self.assertEqual(row.label.text(), text)
            self.assertLessEqual(row.bubble.width(), 460)
            self.assertTrue(row.rect().contains(row.bubble.geometry()))
        self.stream.resize(300, 320)
        QTest.qWait(100)
        for row in rows:
            self.assertLessEqual(row.bubble.width(), row.width() - 24)
            self.assertTrue(row.rect().contains(row.bubble.geometry()))

    def test_reset_clears_unseen_reply_button_and_releases_reply_height_timer(self):
        handle = self._long_reply()
        self.stream.verticalScrollBar().setValue(30)
        self.stream.append_stream_token(handle, "\n\nThêm một ý.")
        body = handle["ans_lbl"]
        self.assertFalse(self.stream.jump_button.isHidden())
        self.stream.clear_chat()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertTrue(sip.isdeleted(body))
        self.assertTrue(self.stream._follow_latest)
        self.assertFalse(self.stream._has_unseen_reply)
        self.assertTrue(self.stream.jump_button.isHidden())

    def test_long_words_and_code_wrap_without_horizontal_clipping_or_nested_scroll(self):
        handle = self.stream.create_streaming_message()
        text = "x" * 600 + "\n\n```python\n" + "y" * 400 + "\n```"
        self.stream.append_stream_token(handle, text)
        QTest.qWait(100)
        body = handle["ans_lbl"]
        block = body.document().begin()
        while block.isValid():
            layout = block.layout()
            for index in range(layout.lineCount()):
                self.assertLessEqual(layout.lineAt(index).naturalTextWidth(), body.viewport().width())
            block = block.next()
        self.assertLessEqual(body.verticalScrollBar().maximum(), 2)
        self.assertEqual(body.text(), text)

    def test_reply_wheel_and_page_up_reach_outer_stream_without_changing_selected_text(self):
        handle = self._long_reply()
        body = handle["ans_lbl"]
        body.setFocus()
        self.stream._scroll_to_bottom(force=True)
        QTest.qWait(200)
        scrollbar = self.stream.verticalScrollBar()
        before = scrollbar.value()
        QTest.keyClick(body, Qt.Key.Key_PageUp)
        QTest.qWait(50)
        self.assertLess(scrollbar.value(), before)
        self.assertFalse(self.stream._follow_latest)
        self.stream._scroll_to_bottom(force=True)
        QTest.qWait(200)
        before = scrollbar.value()
        event = QWheelEvent(QPointF(100, 100), QPointF(100, 100), QPoint(), QPoint(0, 120),
                            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                            Qt.ScrollPhase.NoScrollPhase, False)
        QApplication.sendEvent(body.viewport(), event)
        QTest.qWait(50)
        self.assertLess(scrollbar.value(), before)
        self.assertFalse(self.stream._follow_latest)

    def test_wheel_up_on_a_short_conversation_does_not_disable_following(self):
        self.stream.add_assistant_message("Một câu ngắn.")
        QTest.qWait(100)
        self.assertEqual(self.stream.verticalScrollBar().maximum(), 0)
        event = QWheelEvent(QPointF(100, 100), QPointF(100, 100), QPoint(), QPoint(0, 120),
                            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                            Qt.ScrollPhase.NoScrollPhase, False)
        QApplication.sendEvent(self.stream.viewport(), event)
        self.assertTrue(self.stream._follow_latest)


if __name__ == "__main__":
    unittest.main()
