# Chốt pilot CoT restart — 15/10/2026

**Pilot đã hoàn thành thu thập và kiểm tra kỹ thuật. F có tín hiệu mô tả tốt hơn
chạy lại từ đầu; ưu thế so với continuation và giá trị triển khai chưa xác lập.**
Review con người trước khi đưa kết quả vào bài báo vẫn còn chờ. Stage 0 không đổi.

Đã chạy **72 calls thật trên 12 câu development đã lộ**, hai draw cho mỗi arm
A/F/CONT, bằng Qwen3.5-4B-MLX-4bit. F dùng prefix tại q yêu cầu = 0,50 đã được
chọn trước; base lịch sử giữ cố định. Pipeline lưu token IDs, EOS, cấu hình và
journal để cắt lại cùng trace, chấm lại và kiểm tra nguồn gốc. Các lượt sau đó
là phân tích CPU. Tổng thu thập mới: **69.141 token prompt + completion**,
trong đó 40.891 token completion gồm EOS.

| Cách làm | Ý nghĩa | Accuracy trung bình hai draw |
| --- | --- | ---: |
| A | Chạy lại từ đầu | 45,8% tại M |
| F | Giữ prefix rồi sinh tiếp từ đó | 70,8% tại M |
| CONT | Giữ toàn bộ rationale cũ rồi tiếp tục | 66,7% tại M |
| O | Giữ đáp án cũ, không gọi thêm | 58,3% cố định |

M cho A/F/CONT cùng số token completion mới theo từng câu; tổng chi phí prompt
khác nhau. O được dùng chung giữa hai draw, không phải hai baseline độc lập.
Nguồn: [aggregate](../audit/cot_restart_matched_aggregate_20261013/report.md)
và [đối chiếu O](../audit/cot_restart_reporting_review_20261014/report.md).

F−A tại M là **+25,0 điểm phần trăm**, CI bootstrap mô tả [4,2; 45,8], nhưng
sign-flip cấp câu cho p = 0,109. F−CONT chỉ **+4,2 điểm phần trăm**, CI
[−8,3; 16,7]. Các phương pháp có giả định khác nhau; sign-flip cần tính trao đổi
dấu ở cấp nhóm. Những số này chưa tạo kết luận xác nhận hay trạng thái GO.

Khi tăng ngân sách sang D(w=0), A hoàn tất thêm các đáp án bị cắt và F−A giảm
còn **+12,5 điểm phần trăm**; correctness của F giữ nguyên từng câu. Vì vậy lợi
thế tại M gồm cả việc trả đáp án kịp trong cửa sổ token ngắn. Kết quả 0/12 câu
đổi ở M±8 chỉ nói về ổn định cục bộ. A/F/CONT đổi đúng–sai giữa hai draw ở
7/3/0 câu; hai draw chưa đủ xác định lợi thế ổn định theo từng câu.
Xem [audit ngân sách](../audit/cot_restart_budget_review_20261014/report.md).

Mẫu vẫn chỉ có **12 câu độc lập**, không tăng nhờ draw hay replay. CI bootstrap
điều kiện trên các draw và base đã quan sát. Quy tắc tổng hợp có trong plan đã
hash; code aggregator được viết sau khi đọc báo cáo draw 2, và các phân tích bổ
sung được ghi là sau khi xem kết quả. Toàn bộ kết quả là exploratory. Chi phí
là số token; phần base lịch sử trong D chưa xác minh quy ước EOS. Chưa đo
latency online hay toàn bộ chi phí suy luận.

**Bước tiếp theo: soạn một protocol tối giản cho câu mới đã duyệt, trước khi
thu thêm model output.** Đề xuất dùng một draw chính trên mỗi câu; so F với
CONT để kiểm giá trị restart, và với O để kiểm việc trả thêm một call có đáng
không. A là ablation phụ. Nếu cần đo nhiễu seed, chọn trước một tập con để lặp
draw và giữ phần đó ngoài thống kê quyết định chính.

Trước call đầu tiên của study mới, cần chốt dữ liệu/split, điểm ngân sách và
phạm vi chi phí, mức lợi ích thực tế (và λ nếu dùng utility), cỡ mẫu/power cho
các contrast chính, rồi freeze code phân tích cùng luật quyết định. Đây là đề
xuất thiết kế, chưa phải preregistration hay phê duyệt chạy. Pilot hiện tại đã
đủ cho phần kết quả thăm dò và phân tích giới hạn trong bản thảo NCKH.
