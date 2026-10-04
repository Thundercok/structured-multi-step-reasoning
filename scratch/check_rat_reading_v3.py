"""Render the real in-place reader and growing composer with explicit sample text."""

from check_rat_surface_v2 import TestOmnibarWindow, capture


def main():
    case = TestOmnibarWindow()
    case.setUp()
    window = case.window
    window.show()
    draft = (
        "Mình đang cân nhắc hai hướng:\n"
        "A: tập trung vào một câu hỏi nhỏ, kiểm chứng được.\n"
        "B: làm một bản tổng quan rộng hơn.\n"
        "Phản biện giúp mình từng hướng."
    )
    answer = (
        "## Phác dàn ý trước, rồi đọc đúng chỗ còn thiếu\n\n"
        "**Bắt đầu bằng hướng A.** Một câu hỏi nhỏ giúp bạn biết cần tìm bằng chứng gì; "
        "dàn ý vẫn sửa được khi tài liệu cho thấy điều khác.\n\n"
        "### Thử trong 30 phút\n\n"
        "1. **10 phút:** viết luận điểm và ba ý chính.\n"
        "2. **15 phút:** với mỗi ý, tìm một nguồn hỗ trợ và một điểm có thể phản bác.\n"
        "3. **5 phút:** sửa lại dàn ý theo bằng chứng vừa tìm được.\n\n"
        "### Hai điều cần kiểm chứng\n\n"
        "- Bạn có đủ tài liệu cho câu hỏi này không?\n"
        "- Bạn có thể mô tả rõ điều gì sẽ khiến mình đổi kết luận không?\n\n"
        "Nếu cả hai còn mơ hồ, thu nhỏ câu hỏi thêm một chút. Dàn ý là dụng cụ, chưa phải hợp đồng."
    )
    try:
        capture(window, "quick-idle-v3")
        window.chat_composer_input.setText(draft)
        capture(window, "composer-multiline-v3")
        window.chat_composer_input.clear()
        window.chat_stream.add_user_message("Mình nên viết dàn ý trước hay đọc tài liệu trước?")
        window._deliver_assistant_reply(answer)
        capture(window, "quick-answer-v3")
        window.read_full_reply()
        capture(window, "answer-reader-v3")
        window.chat_composer_input.setText(draft)
        capture(window, "reader-with-draft-v3")
        window.reply_reader.close_button.click()
        capture(window, "compact-with-draft-v3")
    finally:
        case.tearDown()


if __name__ == "__main__":
    main()
