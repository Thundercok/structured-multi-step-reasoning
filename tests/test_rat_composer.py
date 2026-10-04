"""Plain-text input and in-place answer reading, without indexing or model calls."""

import os
import sys
import unittest
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import QMimeData, Qt, QUrl
from PyQt6.QtGui import QInputMethodEvent, QTextCursor
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import QApplication

from rat.ui.chat_composer import ChatComposer
from rat.ui.reply_reader import ReplyReader

app = QApplication.instance() or QApplication(sys.argv)


class TestChatComposer(unittest.TestCase):
    def setUp(self):
        self.composer = ChatComposer()
        self.composer.resize(400, self.composer.height())
        self.composer.show()
        app.processEvents()

    def tearDown(self):
        self.composer.close()
        self.composer.deleteLater()
        app.processEvents()

    def test_shift_enter_inserts_a_newline_and_plain_enter_submits_once(self):
        spy = QSignalSpy(self.composer.submit_requested)
        self.composer.setText("Ý đầu")
        self.composer.setCursorPosition(len(self.composer.text()))
        QTest.keyClick(self.composer, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
        self.composer.insertPlainText("Ý tiếp")
        self.assertEqual(self.composer.text(), "Ý đầu\nÝ tiếp")
        self.assertEqual(len(spy), 0)
        QTest.keyClick(self.composer, Qt.Key.Key_Return)
        self.assertEqual(len(spy), 1)
        self.assertEqual(self.composer.text(), "Ý đầu\nÝ tiếp")

    def test_grows_to_four_lines_then_scrolls_and_shrinks_after_clear(self):
        self.composer.setText("Một\nHai\nBa\nBốn")
        app.processEvents()
        four_lines = self.composer.height()
        self.assertGreater(four_lines, self.composer.MIN_HEIGHT)
        self.assertEqual(self.composer.verticalScrollBar().maximum(), 0)
        self.composer.setText("\n".join(str(i) for i in range(25)))
        app.processEvents()
        self.assertEqual(self.composer.height(), four_lines)
        self.assertGreater(self.composer.verticalScrollBar().maximum(), 0)
        self.composer.clear()
        self.assertEqual(self.composer.height(), self.composer.MIN_HEIGHT)

    def test_wrapped_text_grows_without_explicit_line_breaks(self):
        self.composer.resize(220, self.composer.height())
        self.composer.setText("Cùng nghĩ về một hướng nghiên cứu dễ kiểm chứng. " * 5)
        app.processEvents()
        self.assertGreater(self.composer.height(), self.composer.MIN_HEIGHT)
        self.assertLessEqual(self.composer.height(), self.composer.fontMetrics().lineSpacing() * 4 + 16)
        self.assertEqual(self.composer.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Qt adds cursor overhang to its horizontal range even when every glyph fits.
        layout = self.composer.document().begin().layout()
        for i in range(layout.lineCount()):
            self.assertLessEqual(layout.lineAt(i).naturalTextWidth(), self.composer.viewport().width())

    def test_paste_keeps_unicode_and_newlines_without_html(self):
        mime = QMimeData()
        text = "Mình đang phân vân:\n• hướng A 🐀\n• hướng B"
        mime.setText(text)
        mime.setHtml("<b>Không lấy HTML này</b>")
        self.composer.insertFromMimeData(mime)
        self.assertEqual(self.composer.text(), text)
        self.composer.setCursorPosition(len(text))
        self.composer.insertPlainText("\nPhản biện giúp mình.")
        self.assertTrue(self.composer.text().endswith("\nPhản biện giúp mình."))

    def test_enter_during_ime_composition_does_not_send(self):
        spy = QSignalSpy(self.composer.submit_requested)
        self.composer.setText("Ý ")
        self.composer.setCursorPosition(len(self.composer.text()))
        app.sendEvent(self.composer, QInputMethodEvent("tưởng", []))
        QTest.keyClick(self.composer, Qt.Key.Key_Return)
        self.assertEqual(len(spy), 0)
        commit = QInputMethodEvent()
        commit.setCommitString("tưởng")
        app.sendEvent(self.composer, commit)
        QTest.keyClick(self.composer, Qt.Key.Key_Return)
        self.assertEqual(len(spy), 1)
        self.assertEqual(self.composer.text(), "Ý tưởng")


class TestReplyReader(unittest.TestCase):
    def setUp(self):
        self.reader = ReplyReader()
        self.reader.resize(580, self.reader.height())
        self.reader.show()
        app.processEvents()

    def tearDown(self):
        self.reader.close()
        self.reader.deleteLater()
        app.processEvents()

    def test_markdown_has_real_headings_lists_and_spaced_paragraphs(self):
        answer = "## Một hướng thử\n\nĐặt câu hỏi trước.\n\n- Viết luận điểm.\n- Tìm bằng chứng.\n\nRồi sửa dàn ý."
        self.reader.set_reply(answer)
        document = self.reader.body.document()
        block = document.begin()
        headings, list_items = [], []
        while block.isValid():
            if block.blockFormat().headingLevel():
                headings.append(block.text())
            if block.textList():
                list_items.append(block.text())
            self.assertGreaterEqual(block.blockFormat().lineHeight(), 140)
            block = block.next()
        self.assertEqual(headings, ["Một hướng thử"])
        self.assertEqual(list_items, ["Viết luận điểm.", "Tìm bằng chứng."])
        self.assertIn("Rồi sửa dàn ý.", self.reader.body.toPlainText())
        self.assertNotIn("##", self.reader.body.toPlainText())
        self.reader.copy_button.click()
        self.assertEqual(QApplication.clipboard().text(), answer)
        self.assertEqual(self.reader._copy_timer.parent(), self.reader)

    def test_stream_update_keeps_selected_text_and_reading_position(self):
        answer = "\n\n".join(f"Đoạn {i}: một ý cần đọc cho rõ." for i in range(30))
        self.reader.set_reply(answer)
        app.processEvents()
        scrollbar = self.reader.body.verticalScrollBar()
        self.assertGreater(scrollbar.maximum(), 0)
        scrollbar.setValue(30)
        cursor = self.reader.body.textCursor()
        cursor.setPosition(0)
        cursor.setPosition(6, QTextCursor.MoveMode.KeepAnchor)
        self.reader.body.setTextCursor(cursor)
        selected = self.reader.body.textCursor().selectedText()
        value = scrollbar.value()
        self.reader.set_reply(answer + "\n\nKết luận mới.")
        self.assertEqual(self.reader.body.textCursor().selectedText(), selected)
        self.assertEqual(scrollbar.value(), value)

    def test_answer_cannot_load_local_resources_or_navigate_file_links(self):
        self.assertIsNone(self.reader.body.loadResource(2, QUrl("file:///tmp/private.png")))
        with patch("rat.ui.reply_reader.QDesktopServices.openUrl") as open_url:
            self.reader._open_link(QUrl("file:///tmp/private.txt"))
            self.reader._open_link(QUrl("javascript:alert(1)"))
            open_url.assert_not_called()
            self.reader._open_link(QUrl("https://example.com/reference"))
            open_url.assert_called_once()

    def test_reset_removes_copyable_answer(self):
        self.reader.set_reply("Một câu trả lời.")
        self.reader.copy_button.click()
        self.reader.set_reply("")
        self.assertEqual(self.reader.full_reply, "")
        self.assertEqual(self.reader.body.toPlainText(), "")
        self.assertFalse(self.reader.copy_button.isEnabled())
        self.assertFalse(self.reader._copy_timer.isActive())

    def test_hidden_reader_does_not_reparse_every_stream_token(self):
        self.reader.hide()
        self.reader.set_reply("Một ý ")
        self.reader.set_reply("Một ý đang viết.")
        self.assertEqual(self.reader.full_reply, "Một ý đang viết.")
        self.assertEqual(self.reader.body.toPlainText(), "")
        self.reader.show()
        app.processEvents()
        self.assertEqual(self.reader.body.toPlainText(), "Một ý đang viết.")
