# RAT backlog

Updated: 2026-10-12, Asia/Ho_Chi_Minh.

Theo yêu cầu người dùng, hướng kiến trúc trong ADR-002 được đưa vào backlog.
Phản hồi cần ưu tiên tiếp theo trong nhánh RAT là **UI cứng nhắc cả về bố cục
lẫn cách chuyển trạng thái**. Người dùng đã xác nhận **mọi chức năng trong một
box chat; full và compact là hai mức không gian của cùng một trải nghiệm**.
Đây là thứ tự ưu tiên phát triển RAT, không thay
ưu tiên bài báo NCKH, research protocol hoặc Stage 0.

## Ưu tiên hiện tại trong RAT

| ID | Kết quả cần đạt | Trạng thái | Phụ thuộc / điều kiện hoàn thành |
| --- | --- | --- | --- |
| RAT-UX-01 | Một box chat cho mọi chức năng, co giãn theo nội dung; compact/full dùng cùng bề mặt và cách thao tác. | Hướng đã xác nhận; đang thiết kế, app chưa đổi | [Brief UI](rat_ui_fluidity.md). Bỏ khung lồng nhau và màn hình chức năng riêng; cần thử nội dung ngắn, hình và chi tiết ở cả hai mức. |
| RAT-UX-02 | Chuyển trạng thái và compact ↔ full liên tục, giữ draft/caret, focus, vị trí đọc, lựa chọn và task đang chạy. | Chưa triển khai | Cùng brief; một nguồn trạng thái/composer. Toggle không submit, gọi model hoặc thực thi lại. |
| RAT-UX-03 | Kiểm tra trải nghiệm hai mục trên với người dùng qua một prototype tương tác. | Chưa triển khai | Prototype ghi rõ dữ liệu mẫu; thử sửa/hủy/lỗi, toggle khi đang gõ/stream và reduced motion trước rollout. |

Không gán deadline hoặc effort chưa được ước lượng. Người phụ trách triển khai
chưa phân công; không có kế hoạch release cam kết trong cập nhật này.

## Backlog kiến trúc

| ID | Hướng phát triển | Trạng thái | Phụ thuộc / bằng chứng cần có |
| --- | --- | --- | --- |
| RAT-AI-01 | Model điều khiển làm rõ, tiếp tục, đổi ý và tham chiếu công việc. | Backlog | [ADR-002](adr-002-rat-adaptive-interaction.md); cần kiểm tra model thật, không chỉ scripted tool calls. |
| RAT-AI-02 | Model ghép phần kết quả và UI khai báo theo yêu cầu, hỗ trợ nhiều artifact/revision. | Backlog | Contract/validator và review nội dung; cần phân biệt độ đúng quyết định với độ đẹp UI. |
| RAT-AI-03 | Phối hợp lịch, tài liệu và phép biến đổi dữ liệu để xử lý yêu cầu chưa có workflow riêng. | Backlog | Dữ liệu và thao tác thực, đánh giá yêu cầu mới; tránh thêm một màn hình riêng cho mỗi ví dụ. |
| RAT-AI-04 | Model đề xuất recipe, thành phần hoặc logic mới trong môi trường tách biệt. | Xa hơn | Sau nền tảng và evidence phù hợp; chưa chọn runtime/SDK hoặc triển khai code tùy ý. |

## Thay đổi ưu tiên

Trước cập nhật này, ADR-002 đề xuất điều phối hội thoại và presentation do model
làm bước phát triển gần. Người dùng cho biết hướng đó phần nào phù hợp nhưng
muốn backlog và nhấn mạnh UI hiện tại cứng nhắc. Vì vậy, công việc thiết kế RAT
tiếp theo tập trung vào bố cục và tính liên tục của tương tác. Cải thiện này
không tự chứng minh RAT có năng lực AI mới.

Các bộ tính, artifact store, dispatcher và bằng chứng review hiện có giữ vai
trò nền tảng. Chưa thay app đang chạy, cấu hình model hoặc pipeline nghiên cứu
trong cập nhật backlog này.
