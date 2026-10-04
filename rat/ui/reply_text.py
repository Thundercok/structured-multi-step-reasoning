"""Shared, text-only Markdown spacing and a self-sizing conversation body."""

from __future__ import annotations

import math

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QTextBlockFormat, QTextCursor, QTextDocument, QTextOption
from PyQt6.QtWidgets import QFrame, QSizePolicy, QTextBrowser

from rat.ui.theme import CHAT_COLORS

MARKDOWN_FEATURES = QTextDocument.MarkdownFeature.MarkdownDialectGitHub | QTextDocument.MarkdownFeature.MarkdownNoHTML


def reply_plain_text(text: str) -> str:
    document = QTextDocument()
    document.setMarkdown(text, MARKDOWN_FEATURES)
    return document.toPlainText()


def space_reply_document(document: QTextDocument) -> None:
    """Use real paragraph spacing, shared by quick reading and full conversation."""
    block = document.begin()
    while block.isValid():
        cursor = QTextCursor(block)
        block_format = block.blockFormat()
        block_format.setLineHeight(140, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        block_format.setNonBreakableLines(False)
        block_format.setTopMargin(8 if block_format.headingLevel() and block.previous().isValid() else 0)
        block_format.setBottomMargin(3 if block.textList() else 8)
        cursor.setBlockFormat(block_format)
        block = block.next()


class ReplyTextBrowser(QTextBrowser):
    def loadResource(self, resource_type, name):
        # Model output is text, not permission to fetch an image or read a file.
        return None


class ConversationReplyBody(ReplyTextBrowser):
    """All content is in the outer stream: no nested scrolling or HTML resources."""
    wheel_scrolled = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._raw_text = ""
        self._rendered_text = ""
        self.setObjectName("ConversationReplyBody")
        self.setAccessibleName("Câu trả lời của Chuột")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setReadOnly(True)
        self.setTabChangesFocus(True)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.anchorClicked.connect(self._open_link)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(f"""
            QTextBrowser#ConversationReplyBody {{ background: transparent; border: none;
                padding: 0; color: {CHAT_COLORS['ink']}; font-size: 13px;
                selection-background-color: #E8DABC; }}
        """)
        font = self.font()
        font.setPixelSize(13)
        self.setFont(font)
        self.document().setDocumentMargin(0)
        self.setFixedHeight(24)
        self._height_timer = QTimer(self)
        self._height_timer.setSingleShot(True)
        self._height_timer.timeout.connect(self._sync_height)
        self.document().documentLayout().documentSizeChanged.connect(self._schedule_height)

    def text(self) -> str:
        # Keep the stream handle's raw-text API, including exact copy content.
        return self._raw_text

    def setText(self, text: str) -> None:
        if text == self._raw_text:
            return
        self._raw_text = text
        if self.isVisible():
            self._render_text()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._render_text()
        self._schedule_height()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_height_timer"):
            self._schedule_height()

    def _render_text(self) -> None:
        if self._raw_text == self._rendered_text:
            return
        previous = self._rendered_text
        cursor = self.textCursor()
        selection = (cursor.anchor(), cursor.position())
        self.document().setMarkdown(self._raw_text, MARKDOWN_FEATURES)
        space_reply_document(self.document())
        self._rendered_text = self._raw_text
        cursor = self.textCursor()
        if previous and self._raw_text.startswith(previous):
            end = self.document().characterCount() - 1
            cursor.setPosition(min(selection[0], end))
            cursor.setPosition(min(selection[1], end), QTextCursor.MoveMode.KeepAnchor)
        else:
            cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.setTextCursor(cursor)
        self._schedule_height()

    def _schedule_height(self, *args) -> None:
        self._height_timer.start(0)

    def _sync_height(self) -> None:
        self.document().setTextWidth(max(1, self.viewport().width()))
        height = max(20, math.ceil(self.document().size().height()) + 2)
        if self.height() != height:
            self.setFixedHeight(height)

    def wheelEvent(self, event) -> None:
        # QAbstractScrollArea does not bubble wheel events through another one.
        # Forward synchronously to the outer stream; never create an inner scroll.
        event.ignore()
        self.wheel_scrolled.emit(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_PageUp, Qt.Key.Key_PageDown) and not event.modifiers():
            event.ignore()
            return
        super().keyPressEvent(event)

    @staticmethod
    def _open_link(url) -> None:
        if url.scheme().lower() in ("http", "https"):
            QDesktopServices.openUrl(url)
