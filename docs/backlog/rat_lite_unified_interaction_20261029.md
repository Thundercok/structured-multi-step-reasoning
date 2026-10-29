# Backlog — hợp nhất bốn cách hiển thị RAT Lite

Quyết định người dùng 2026-10-29: đưa đề xuất này vào backlog; chưa triển khai
trong lượt ổn định bố cục .23.

Minimal / Single / Full / Look đang tạo cảm giác rời rạc. Hướng tương lai:
một Chuột, một cuộc tương tác, mở rộng theo nhu cầu. Minimal là trạng thái nhập;
Look là lối vào từ Clipboard/ngữ cảnh; Single là trạng thái đọc; Full là phần
mở rộng cùng công việc. Người dùng không cần chọn mode trước khi gửi yêu cầu.

Giữ nguồn, kết quả, bản nháp và vị trí đọc khi mở rộng/thu lại. Tái sử dụng
contracts, dispatcher và presentation hiện có; không tạo business path riêng.
Đây là đề xuất UX đã được hoãn, không phải xác nhận đã hợp nhất state machine
hay nối vòng Agent/model. Không tự bật LLM, tích hợp main hoặc chạy nghiệm thu.
