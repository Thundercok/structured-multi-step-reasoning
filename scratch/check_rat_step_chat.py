"""Render multi-turn step-by-step chat session with PAL, CoT trace, and ReplyReader turn switching."""

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
    QTest.qWait(300)
    app.processEvents()
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
        # 1. Turn 1: Quantitative reasoning with PAL
        window.set_expanded(True)
        window._submit_chat_prompt("Sinh viên tích lũy 64 tín chỉ có CPA 7.20. Học kỳ này thêm 12 tín chỉ dự kiến điểm 8.5 thì CPA mới là bao nhiêu?")
        capture(window, "step-chat-turn1-expanded")

        # 2. Turn 2: Follow-up question with academic policy
        window._submit_chat_prompt("Điều kiện nhận học bổng khuyến khích học tập loại Giỏi là gì?")
        capture(window, "step-chat-turn2-expanded")

        # Open the first card's details accordion
        cards = [c for c in window.chat_stream.findChildren(object) if getattr(c, "objectName", lambda: "")() == "AssistantCard"]
        if cards:
            details_btn = cards[0].findChild(object, "details_button") or [b for b in cards[0].findChildren(object) if hasattr(b, "text") and b.text() == "Chi tiết"]
            if details_btn:
                btn = details_btn if not isinstance(details_btn, list) else details_btn[0]
                btn.click()
                capture(window, "step-chat-details-open")

        # 3. Compact mode with ReplyReader multi-turn switcher
        window.set_expanded(False)
        window.read_full_reply()
        capture(window, "step-chat-reader-turn2")

        # Switch to Turn 1 in ReplyReader
        if len(window.reply_reader._turns) > 1:
            window.reply_reader._select_turn(0)
            capture(window, "step-chat-reader-turn1")

    finally:
        case.tearDown()


if __name__ == "__main__":
    main()
