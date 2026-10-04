"""Real UI, explicit sample text; no live session, inference or personal-file IO."""

from PyQt6.QtTest import QTest

from check_rat_surface_v2 import TestOmnibarWindow, capture


def main():
    case = TestOmnibarWindow()
    case.setUp()
    window = case.window
    window.search_requested.disconnect(window.worker.do_search)
    window.show()
    try:
        window.chat_stream.add_user_message("Mình nên viết dàn ý trước hay đọc tài liệu trước?")
        answer = (
            "## Phác dàn ý trước\n\n"
            "Một câu hỏi nhỏ giúp bạn biết cần tìm bằng chứng gì. Dàn ý vẫn sửa được; "
            "chưa cần ký hợp đồng với nó.\n\n"
            "### Thử trong 30 phút\n\n"
            "1. **10 phút:** viết luận điểm và ba ý chính.\n"
            "2. **15 phút:** tìm một nguồn hỗ trợ và một điểm phản bác.\n"
            "3. **5 phút:** sửa dàn ý theo bằng chứng vừa tìm được.\n\n"
            "Nếu vẫn chưa rõ mình cần đọc gì, thu nhỏ câu hỏi thêm một chút."
        )
        window._deliver_assistant_reply(answer)
        window.set_expanded(True)
        capture(window, "reading-full-side-v5")
        window.chat_composer_input.setText("Mình đang cân nhắc:\nHướng A hay hướng B?\nPhản biện từng hướng giúp mình.")
        capture(window, "reading-full-draft-v5")
        window.chat_composer_input.clear()
        window.chat_stream.add_user_message("Nếu đọc xong mà ý ban đầu không ổn thì sao?")
        window._deliver_assistant_reply(
            "Thì sửa ý. **Đổi kết luận vì bằng chứng tốt hơn là tiến bộ**, không phải làm lại từ đầu."
        )
        window.chat_stream.add_user_message("Cùng nghĩ tiếp một hướng kiểm chứng được nhé.")
        handle = window.chat_stream.create_streaming_message(badge="Mô hình mẫu")
        window._on_reasoning_token(handle, "\n\n".join(
            f"Ý mẫu {index}: đặt một câu hỏi nhỏ, ghi điều gì sẽ khiến mình đổi kết luận."
            for index in range(12)
        ))
        QTest.qWait(200)
        window.chat_stream.verticalScrollBar().setValue(28)
        window._on_reasoning_token(handle, "\n\nMột ý mới đang được bổ sung ở cuối.")
        capture(window, "reading-history-new-reply-v5")
        window.chat_stream.jump_button.click()
        capture(window, "reading-following-latest-v5")
        window._reset_chat()
        window._deliver_assistant_reply(answer)
        capture(window, "reading-quick-v5")
        window.read_full_reply()
        capture(window, "reading-reader-v5")
    finally:
        case.tearDown()


if __name__ == "__main__":
    main()
