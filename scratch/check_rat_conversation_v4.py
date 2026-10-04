"""Render real conversation widgets with sample replies, without a live LLM."""

from check_rat_surface_v2 import TestOmnibarWindow, capture


def main():
    case = TestOmnibarWindow()
    case.setUp()
    window = case.window
    window.search_requested.disconnect(window.worker.do_search)
    window.show()
    try:
        window.set_expanded(True)
        capture(window, "conversation-empty-v4")
        window.chat_stream.add_user_message("Mình nên viết dàn ý trước hay đọc tài liệu trước?")
        handle = window.chat_stream.create_streaming_message(badge="Mô hình mẫu")
        answer = (
            "**Phác dàn ý trước, rồi đọc đúng chỗ còn thiếu.**\n\n"
            "Một câu hỏi nhỏ giúp bạn biết cần tìm bằng chứng gì. Dàn ý vẫn sửa được; "
            "chưa cần ký hợp đồng với nó.\n\n"
            "1. Viết luận điểm và ba ý chính.\n"
            "2. Với mỗi ý, ghi một câu hỏi cần bằng chứng.\n"
            "3. Đọc theo các câu hỏi đó, rồi sửa dàn ý."
        )
        window._on_reasoning_token(handle, answer)
        window._on_reasoning_finished(
            handle, answer, ["Ngữ cảnh mẫu: viết dàn ý", "Dữ liệu giả để kiểm tra giao diện"],
            125, "Direct", "Mô hình mẫu",
        )
        window.chat_stream.add_user_message("Nếu đọc xong mà ý ban đầu không ổn thì sao?")
        window._deliver_assistant_reply(
            "Thì sửa ý. **Đổi kết luận vì bằng chứng tốt hơn là tiến bộ**, không phải làm lại từ đầu."
        )
        capture(window, "conversation-refined-v4")
        window.chat_composer_input.setText(
            "Mình đang cân nhắc:\nA: câu hỏi nhỏ, kiểm chứng được.\n"
            "B: tổng quan rộng hơn.\nPhản biện giúp mình từng hướng."
        )
        capture(window, "conversation-multiline-v4")
        window.chat_composer_input.clear()
        handle["details_button"].click()
        capture(window, "conversation-details-v4")
        handle["details_button"].click()
        window.set_expanded(False)
        capture(window, "quick-answer-v4")
        window.read_full_reply()
        capture(window, "answer-reader-v4")
        window.set_reply_reader_open(False)
        window._reset_chat()
        window.chat_stream.add_user_message("tìm file slides tích phân")
        window._deliver_assistant_reply(
            "Tìm thấy 4 tệp phù hợp với 'slides tích phân'.", strategy="Search",
            inline_files=case._compact_files(), reasoning_steps=["Dữ liệu tệp mẫu"], latency_ms=42,
        )
        window.set_expanded(True)
        capture(window, "conversation-files-v4")
    finally:
        case.tearDown()


if __name__ == "__main__":
    main()
