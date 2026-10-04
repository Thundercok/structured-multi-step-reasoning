"""Render real RAT widgets with explicit sample data, without touching a live session."""

import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo))
sys.path.insert(0, str(repo / "tests"))

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtTest import QTest
from test_omnibar import TestOmnibarWindow, app


def capture(window, name):
    QTest.qWait(400)
    app.processEvents()
    if not window.is_expanded and not window.speech_bubble.isHidden():
        bubble = window.speech_bubble
        rect = bubble.dialogue.fontMetrics().boundingRect(
            QRect(0, 0, bubble.dialogue.width(), 10000), Qt.TextFlag.TextWordWrap, bubble.dialogue.text()
        )
        assert rect.height() <= bubble.dialogue.height(), (rect, bubble.dialogue.geometry())
        assert bubble.y() + bubble.height() <= window.container.y()
    for i in range(window.compact_file_list.count()):
        row = window.compact_file_list.itemWidget(window.compact_file_list.item(i))
        if window.compact_file_list.isVisible():
            for button in (row.btn_open, row.btn_preview, row.btn_reveal):
                point = button.mapTo(row, QPoint(0, 0))
                assert point.x() + button.width() <= row.width(), (point, row.size())
    pixmap = QPixmap(window.width() * 2, window.height() * 2)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(QColor("#F3F0E9"))
    window.render(pixmap)
    path = repo / "scratch" / "rat_reply_validation" / f"{name}.png"
    path.parent.mkdir(exist_ok=True)
    assert pixmap.save(str(path))
    print(name, window.size(), str(path), flush=True)


def main():
    case = TestOmnibarWindow()
    case.setUp()
    window = case.window
    window.search_requested.disconnect(window.worker.do_search)
    window.show()
    try:
        capture(window, "quick-idle-v2")
        window._submit_chat_prompt("tìm file slides tích phân")
        request_id = window._chat_file_request["request_id"]
        files = case._compact_files()
        for item, title in zip(files, (
            "Tích phân — Bài giảng tuần 4.pdf",
            "Đổi biến và tích phân từng phần.pptx",
            "Bài tập tích phân có lời giải.pdf",
            "Ghi chú tích phân — bản ôn tập.md",
        )):
            item.file_name = title
            item.file_ext = Path(title).suffix
            item.file_path = "/tmp/rat-ui-fixtures/Giải tích/" + title
        window._on_search_completed(request_id, {"results": files, "latency_ms": 1719})
        capture(window, "quick-files-v2")
        window.set_expanded(True)
        capture(window, "expanded-files-v2")
        window._reset_chat()
        window.chat_stream.add_user_message("Mình nên viết dàn ý trước hay đọc tài liệu trước?")
        window._deliver_assistant_reply(
            "Phác ba ý chính trước, rồi đọc đúng chỗ còn thiếu. Dàn ý vẫn sửa được; chưa cần ký hợp đồng với nó."
        )
        capture(window, "quick-answer-v2")
        window._deliver_assistant_reply("\n\n".join([
            "Bắt đầu bằng một dàn ý nháp, rồi đọc tài liệu cho những chỗ chưa chắc.",
            "Dành 15 phút viết luận điểm và ba ý chính. Với mỗi ý, ghi một câu hỏi cần tìm bằng chứng.",
            "Đọc theo các câu hỏi đó, ghi rõ nguồn và điều gì tài liệu thực sự hỗ trợ. Sửa dàn ý khi cần.",
            "Sau đó viết bản nháp. Dàn ý là dụng cụ, chưa phải hợp đồng.",
        ]))
        capture(window, "quick-long-answer-v2")
        window.set_expanded(True)
        capture(window, "expanded-answer-v2")
    finally:
        case.tearDown()


if __name__ == "__main__":
    main()
