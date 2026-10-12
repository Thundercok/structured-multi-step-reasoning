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
| RAT-UX-01 | Một box chat cho mọi chức năng, co giãn theo nội dung; compact/full dùng cùng bề mặt và cách thao tác. | Đã triển khai trong source và app chạy từ source | [Brief UI](rat_ui_fluidity.md). Bỏ khung lồng nhau và màn hình chức năng riêng; cần thử nội dung ngắn, hình và chi tiết ở cả hai mức. |
| RAT-UX-02 | Chuyển trạng thái và compact ↔ full liên tục, giữ draft/caret, focus, vị trí đọc, lựa chọn và task đang chạy. | Đã triển khai; có kiểm tra trạng thái Qt | Cùng brief; một nguồn trạng thái/composer. Toggle không submit, gọi model hoặc thực thi lại. |
| RAT-UX-03 | Kiểm tra trải nghiệm hai mục trên với người dùng qua một prototype tương tác. | Có prototype Qt và kiểm tra native; chờ phản hồi người dùng | Prototype ghi rõ dữ liệu mẫu; thử sửa/hủy/lỗi, toggle khi đang gõ/stream và reduced motion trước rollout. |
| RAT-UX-04 | Chuột là người bạn nhận việc, ghi chép và đưa kết quả; personality xuyên suốt một box chat. | Đã triển khai trong source; chờ phản hồi trải nghiệm | [Hướng companion trong brief](rat_ui_fluidity.md). Chuột lớn bên trái, chuyển động vui vừa được người dùng chọn, trạng thái thực, ghi chép có nguồn/sửa/xóa; khả năng model ghi/sửa đúng còn hạn chế. |
| RAT-UX-05 | Thể hiện luồng suy luận và thực thi bên cạnh kết quả, có thể mở chi tiết. | Đã triển khai trong source | [Ngữ cảnh và trace](rat_companion_work_context.md). Phân biệt dự định với thao tác đã chạy, lỗi/dừng/thiếu dữ kiện; không hiển thị raw/private reasoning. |

Không gán deadline hoặc effort chưa được ước lượng. Source đã cập nhật ngày 2026-10-12; chưa build lại bản đóng gói. Bằng chứng và giới hạn: [audit UI](../audit/rat_one_box_ui_20261012/REPORT.md) và [audit companion](../audit/rat_companion_reasoning_20261012/REPORT.md).

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
trò nền tảng. Đợt UI đã cập nhật app chạy từ source. Cấu hình model, các mục RAT-AI và pipeline nghiên cứu chưa thay đổi.

Người dùng đã cho triển khai persona, ngữ cảnh công việc và luồng các bước.
Ghi chép theo phiên, continuation giữ kết quả và chọn tập kết quả thật đã có
contract và Qt kiểm tra. Đây là nền tảng nối với RAT-AI-01/02/03; presentation
vẫn dùng renderer đã đăng ký, chưa sinh UI tùy ý. Các mục kiến trúc vẫn ở backlog,
cần model thật xử lý yêu cầu mới và review kết quả. Thử phát triển 1.5B cho thấy
model có thể nói đã ghi/sửa mà chưa thực thi; không coi software tests là bằng
chứng năng lực. Cấu hình model mặc định, pipeline NCKH và Stage 0 giữ nguyên.
