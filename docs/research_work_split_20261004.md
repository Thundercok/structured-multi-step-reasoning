# Việc của chúng ta từ đây — 2026-10-04

Còn hơn một năm, nên mục tiêu gần nhất là tìm một câu hỏi nghiên cứu có giá trị
và đo được. Không cần ép kết quả phải thắng; một kết quả âm rõ ràng, có đối chứng
và tái lập được cũng có ích. Giai đoạn hiện tại là pilot, chưa chốt bài báo.

| Bạn | Mình |
| --- | --- |
| Đọc 5 câu đầu và các ghi chú cách hiểu ở câu 10, 15, 22, 24 trong [gói duyệt](../data/gsm8k_development_reviewed_v1/review.md). Ghi ID câu nào mơ hồ hoặc phép tính chưa thuyết phục. | Chuẩn bị dữ liệu có nguồn/phiên bản, kiểm tra đáp án, ghi riêng phần đã kiểm tra bằng code và phần cần con người duyệt. |
| Khi có yêu cầu của giảng viên, gửi đề cương mẫu, tiêu chí đánh giá và mốc cần nộp. | Giữ phạm vi phù hợp với NCKH; làm bảng so sánh trước khi thêm controller hoặc mở rộng app. |
| Đọc tóm tắt các nghiên cứu liên quan cùng mình; tham gia chọn câu hỏi mà bạn muốn hiểu và giải thích được. | Tóm tắt prior work theo bài toán, tín hiệu đầu vào, hành động và cách đo; chỉ ra phần trùng và phần còn phải kiểm chứng. |
| Trước khi dùng kết quả trong bài báo, cùng giảng viên/người duyệt xác nhận toàn bộ dữ liệu, giả định và cách diễn giải. | Chạy headless, lưu raw outputs, kiểm tra score/cost, phân tích lỗi và dựng bảng/đồ thị có liên kết artifact. |

## Việc gần nhất

Mình đã hoàn thành pilot GSM8K: ba chiến lược cố định trên 23 câu development đã
qua kiểm tra của agent, seed 42, cap 1.024, chỉ dẫn tiếng Anh. [Bảng kết quả](gsm8k_development_results_20261004.md)
ghi DIRECT 20/23, CoT 19/23 và PAL 21/23. Một câu trong mẫu
24 câu ban đầu đã bị loại vì mơ hồ trước khi xem đầu ra model. Xác nhận của con
người vẫn đang chờ; tập test chưa dùng.

Bạn bắt đầu ở gói duyệt, chỉ cần gửi ghi chú theo dạng `ID câu — chỗ chưa rõ`.
Mình trả một bảng accuracy/token, các lỗi tiêu biểu và khuyến nghị tiếp tục hay
thu hẹp. Sau đó mới chọn phép đo cho controller. Bạn không cần tự cài môi trường
hoặc chạy các lệnh thí nghiệm.

Sau phần duyệt câu hỏi, bắt đầu đọc abstract của ba bài này:

- [PAL](https://arxiv.org/abs/2211.10435): dùng model viết chương trình rồi giao việc tính cho interpreter. Đây là đối chứng có trước; adapter zero-shot hiện tại chưa tái lập toàn bộ thí nghiệm few-shot của bài.
- [Route to Reason](https://arxiv.org/abs/2505.19435): chọn cả model và chiến lược dưới ràng buộc ngân sách. Cần đối chiếu với phạm vi một model cố định của mình.
- [BEST-Route](https://arxiv.org/abs/2506.22716): chọn model cùng số lần lấy mẫu. Cần đọc kỹ để phân biệt phân bổ tính toán với quyết định dừng của policy trong repo.

Mỗi bài chỉ cần ghi trước ba dòng: **họ chọn gì; dùng thông tin gì để chọn;
đo với baseline nào**. Đây là bước đọc ban đầu, không thay thế việc đọc phương
pháp/thí nghiệm và không xác nhận tính mới của đề tài.

## Lộ trình dự kiến

1. **Vài tuần đầu:** đối chứng đáng tin, đọc prior work, chốt câu hỏi với giảng viên.
2. **Sau khi pilot đủ rõ:** duyệt và cố định dữ liệu/splits, metric, budget và baseline; thiết kế thí nghiệm chính.
3. **Phần giữa thời gian còn lại:** thực nghiệm chính, ablation, phân tích lỗi và các lần kiểm tra tái lập.
4. **Phần cuối:** viết, nhận phản biện, sửa và chuẩn bị artifact/demo tối thiểu.

Đây là thứ tự làm việc, chưa phải lịch nộp cố định. Mỗi giai đoạn cần một sản
phẩm kiểm chứng được; hiện chưa có bằng chứng controller tốt hơn baseline.
