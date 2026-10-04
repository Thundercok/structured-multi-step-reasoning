"""Render the existing RAT widgets with canned replies and mocked file services."""

import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo))
sys.path.insert(0, str(repo / "tests"))

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtTest import QTest
from test_omnibar import TestOmnibarWindow, app


def check_layout(window):
    bubble = window.speech_bubble
    label = bubble.dialogue
    rect = label.fontMetrics().boundingRect(
        QRect(0, 0, label.width(), 10000), Qt.TextFlag.TextWordWrap, label.text()
    )
    assert rect.height() <= label.height(), (rect.height(), label.height())
    assert rect.width() <= label.width(), (rect.width(), label.width())
    assert bubble.y() + bubble.height() <= window.container.y(), (
        bubble.geometry(), window.container.geometry()
    )
    for button in (bubble.btn_copy, bubble.btn_hist):
        if not button.isHidden():
            pos = button.mapTo(bubble, QPoint(0, 0))
            assert pos.x() + button.width() <= bubble.width()
            assert pos.y() + button.height() <= bubble.height()
    print("Geometry OK:", "bubble", bubble.size(), "label", label.size())


def main():
    output = repo / "scratch" / "rat_reply_validation"
    output.mkdir(exist_ok=True)
    case = TestOmnibarWindow()
    case.setUp()
    try:
        window = case.window
        window.show()
        QTest.qWait(250)
        for name, reply in (
            ("short", "Ừ. Phác ba ý chính trước, rồi đọc tài liệu cho chỗ còn thiếu."),
            ("long", "\n\n".join([
                "Phác dàn ý trước, rồi đọc đúng chỗ còn thiếu.",
                "Nếu mục tiêu là có một bản nháp hôm nay, dành 15 phút viết luận điểm và ba ý chính.",
                "Sau đó tìm tài liệu cho những phần chưa chắc. Đánh dấu rõ chỗ thiếu bằng chứng.",
                "Dành phần thời gian còn lại để viết. Dàn ý vẫn sửa được; đừng coi nó là hợp đồng.",
            ])),
        ):
            window._deliver_assistant_reply(reply)
            QTest.qWait(450)
            app.processEvents()
            check_layout(window)
            path = output / f"compact-{name}.png"
            assert window.grab().save(str(path))
            print("Rendered:", path)
    finally:
        case.tearDown()


if __name__ == "__main__":
    main()
