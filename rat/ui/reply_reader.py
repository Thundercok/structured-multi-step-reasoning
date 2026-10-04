"""The latest answer, readable in place without opening the entire conversation."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QTextCursor, QTextOption
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rat.ui.reply_text import MARKDOWN_FEATURES, ReplyTextBrowser, reply_plain_text, space_reply_document


class ReplyReader(QFrame):
    close_requested = pyqtSignal()
    copied = pyqtSignal()
    PANEL_HEIGHT = 252

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.full_reply = ""
        self._rendered_reply = ""
        self.setObjectName("ReplyReader")
        self.setFixedHeight(self.PANEL_HEIGHT)
        self.setStyleSheet("""
            QFrame#ReplyReader { background: transparent; border: none; }
            QPushButton { background: transparent; border: none; border-radius: 5px;
                color: #6B6258; font-size: 11px; padding: 4px 7px; }
            QPushButton:hover { background: #F0E8DA; color: #302B24; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 8)
        layout.setSpacing(10)
        header = QHBoxLayout()
        self.title = QLabel("Chuột · Câu trả lời")
        self.title.setStyleSheet("color: #6F6456; font-size: 11px; font-weight: 600;")
        header.addWidget(self.title)

        self.tag_label = QLabel()
        self.tag_label.setStyleSheet(
            "color: #7B6E5F; font-size: 10px; font-weight: 500; background: #F0E8DC; border-radius: 4px; padding: 1px 6px;"
        )
        self.tag_label.hide()
        header.addWidget(self.tag_label)

        self.turn_strip = QWidget()
        self.turn_layout = QHBoxLayout(self.turn_strip)
        self.turn_layout.setContentsMargins(4, 0, 4, 0)
        self.turn_layout.setSpacing(4)
        self.turn_strip.hide()
        header.addWidget(self.turn_strip)

        self._turns: list[tuple[str, str]] = []
        self._active_turn_idx: int = -1

        header.addStretch()
        self.copy_button = QPushButton("Sao chép")
        self.copy_button.setToolTip("Sao chép toàn bộ câu trả lời, giữ nguyên định dạng gốc")
        self.copy_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_button.clicked.connect(self._copy)
        header.addWidget(self.copy_button)
        self.close_button = QPushButton("Thu gọn")
        self.close_button.setToolTip("Quay lại gọi nhanh (Esc)")
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.clicked.connect(self.close_requested)
        header.addWidget(self.close_button)
        layout.addLayout(header)

        self.body = ReplyTextBrowser()
        self.body.setObjectName("ReplyReaderBody")
        self.body.setAccessibleName("Câu trả lời đầy đủ của Chuột")
        self.body.setFrameShape(QFrame.Shape.NoFrame)
        self.body.setReadOnly(True)
        self.body.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        font = self.body.font()
        font.setPixelSize(14)
        self.body.setFont(font)
        self.body.setOpenLinks(False)
        self.body.setOpenExternalLinks(False)
        self.body.anchorClicked.connect(self._open_link)
        self.body.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body.setStyleSheet("""
            QTextBrowser#ReplyReaderBody { border: none; background: transparent;
                color: #302B24; font-size: 14px; selection-background-color: #E8DABC; }
        """)
        self.body.document().setDocumentMargin(0)
        layout.addWidget(self.body, 1)
        self._copy_timer = QTimer(self)
        self._copy_timer.setSingleShot(True)
        self._copy_timer.timeout.connect(lambda: self.copy_button.setText("Sao chép"))

    def set_turns(self, turns: list[tuple[str, str]]) -> None:
        self._turns = list(turns)
        while self.turn_layout.count():
            item = self.turn_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if len(self._turns) > 1:
            self.title.setText("Chuột")
            self.turn_strip.show()
            for idx in range(len(self._turns)):
                pill = QPushButton(f"Bước {idx + 1}")
                pill.setCursor(Qt.CursorShape.PointingHandCursor)
                is_active = (idx == len(self._turns) - 1)
                self._style_turn_pill(pill, is_active)
                pill.clicked.connect(lambda checked=False, i=idx: self._select_turn(i))
                self.turn_layout.addWidget(pill)
            self._active_turn_idx = len(self._turns) - 1
        else:
            self.title.setText("Chuột · Câu trả lời")
            self.turn_strip.hide()
            self._active_turn_idx = 0 if self._turns else -1

    def _select_turn(self, idx: int) -> None:
        if 0 <= idx < len(self._turns):
            self._active_turn_idx = idx
            for i in range(self.turn_layout.count()):
                w = self.turn_layout.itemAt(i).widget()
                if isinstance(w, QPushButton):
                    self._style_turn_pill(w, i == idx)
            q, a = self._turns[idx]
            self.set_reply(a)

    @staticmethod
    def _style_turn_pill(button: QPushButton, active: bool) -> None:
        if active:
            button.setStyleSheet("""
                QPushButton {
                    background: #E8E0D2;
                    border: 1px solid #CFC4B2;
                    border-radius: 4px;
                    color: #2D2720;
                    font-size: 10px;
                    font-weight: 600;
                    padding: 1px 6px;
                }
            """)
        else:
            button.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: 1px solid transparent;
                    border-radius: 4px;
                    color: #7D7264;
                    font-size: 10px;
                    font-weight: 500;
                    padding: 1px 6px;
                }
                QPushButton:hover {
                    background: #F4EFE6;
                    color: #302B24;
                }
            """)

    def set_session_tag(self, tag: str) -> None:
        if tag:
            self.tag_label.setText(tag)
            self.tag_label.show()
        else:
            self.tag_label.hide()

    def set_reply(self, answer: str) -> None:
        if answer == self.full_reply:
            return
        self.full_reply = answer
        self.copy_button.setEnabled(bool(answer.strip()))
        self._copy_timer.stop()
        self.copy_button.setText("Sao chép")
        if not answer:
            self.body.clear()
            self._rendered_reply = ""
        elif self.isVisible():
            self._render_latest_reply()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._render_latest_reply()

    def _render_latest_reply(self) -> None:
        answer = self.full_reply
        previous = self._rendered_reply
        if answer == previous:
            return
        scrollbar = self.body.verticalScrollBar()
        scroll_value = scrollbar.value()
        cursor = self.body.textCursor()
        selection = (cursor.anchor(), cursor.position())
        self.body.document().setMarkdown(answer, MARKDOWN_FEATURES)
        self._rendered_reply = answer
        space_reply_document(self.body.document())
        if previous and answer.startswith(previous):
            cursor = self.body.textCursor()
            end = self.body.document().characterCount() - 1
            cursor.setPosition(min(selection[0], end))
            cursor.setPosition(min(selection[1], end), QTextCursor.MoveMode.KeepAnchor)
            self.body.setTextCursor(cursor)
            scrollbar.setValue(scroll_value)
        else:
            cursor = self.body.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self.body.setTextCursor(cursor)
            scrollbar.setValue(0)

    def _copy(self) -> None:
        if self.full_reply.strip():
            QApplication.clipboard().setText(self.full_reply)
            self.copy_button.setText("Đã sao chép")
            self._copy_timer.start(1500)
            self.copied.emit()

    @staticmethod
    def _open_link(url) -> None:
        if url.scheme().lower() in ("https", "http"):
            QDesktopServices.openUrl(url)
