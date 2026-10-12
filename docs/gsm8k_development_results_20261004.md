# Kết quả pilot GSM8K — 2026-10-04

Đã chạy xong **69/69 lượt**: ba chỉ dẫn DIRECT, CoT và PAL trên cùng 23 câu
development. Model Qwen3-8B-4bit được ghim phiên bản; chỉ dẫn tiếng Anh, seed 42,
greedy, tắt thinking, cap 1.024 token/lượt. Không huấn luyện hay đánh giá controller.

| Điều kiện prompt | Đúng / số câu | Accuracy | Token sinh trung bình |
| --- | ---: | ---: | ---: |
| DIRECT | 20/23 | 87,0% | 93,4 |
| CoT | 19/23 | 82,6% | 96,8 |
| PAL | 21/23 | 91,3% | 87,0 |

PAL sửa được cả **4 câu CoT sai**, nhưng sai **2 câu CoT làm đúng**. Cả 23 đoạn
Python chạy thành công; hai lỗi PAL là lỗi hiểu đề: xem bà là trẻ em trong bài
vé xem diễn, và bỏ qua vòi đầu vẫn chạy trong bài bơm nước. Vì vậy, chạy code
thành công chưa đủ để xác định một đáp án đúng.

Các lỗi bổ sung cho nhau: DIRECT và CoT riêng đã có ít nhất một đáp án đúng
cho mỗi câu trong mẫu này. Nếu biết gold để chọn đầu ra, mức trần là 23/23;
đây không phải controller có thể triển khai. So với PAL luôn chạy (21/23),
còn hai câu có thể cứu trong các đầu ra đã lưu. Lợi ích thực tế chưa được đo.

## Giới hạn cần giữ khi diễn giải

- Mẫu ban đầu gồm 24 câu từ **train** của GSM8K; loại một câu bước đi mơ hồ trước khi model sinh đáp án. Còn 11 nhóm development train và 12 calibration. Tập test chính thức chưa tải/chưa dùng; xác nhận của con người đang chờ.
- Đây là kết quả mô tả trên mẫu nhỏ đã xem, không phải điểm benchmark GSM8K test, so sánh với pilot ba family trước, hay bằng chứng chiến lược/controller thắng tổng quát.
- DIRECT có văn bản trước dòng đáp án ở **19/23 câu**, dù prompt yêu cầu không trình bày bước. Bảng đo điều kiện prompt và đầu ra thực tế, chưa chứng minh DIRECT không suy luận.
- Cả chín lượt sai đều có heuristic confidence trên 0,8. Ngưỡng đó không loại được lỗi nào; confidence chưa là xác suất đúng đã hiệu chỉnh.
- Token ở bảng là token sinh, không gồm prefill/toàn bộ inference. PAL có prompt dài hơn. Thực thi Python trung bình khoảng 50 ms, đã gồm trong thời gian chiến lược; replay giữ thời gian đo cũ, không đo latency controller online.

## Quyết định tiếp theo

Bản kiểm duyệt bổ sung ngày 04/10/2026 do người dùng gửi đã được
[lưu riêng](../audit/gsm8k-review-submission-20261004/manifest.json): 22 câu đạt,
câu 10 đạt với cách hiểu “8 times less” là 1/8, câu 15 tiếp tục bị loại. Tên
người duyệt được ghi là “AI Expert Auditor / Review Team”; đây là nguồn kiểm
duyệt bổ sung, chưa xác minh được human sign-off. Dataset/gold và các artifact
đo cũ giữ nguyên hash và trạng thái tại thời điểm collection.

Tiếp tục bằng một phép đo development validation riêng: đối chiếu ba baseline
cố định với một quy tắc chọn từ thông tin câu hỏi đơn giản. Cần chốt nhóm
fitting/validation và budget trước khi có đầu ra mới. Không fit trên 23 câu này
rồi gọi kết quả là held out. Song song, đọc prior work để quyết định phạm vi
đóng góp của entry routing và stopping; hiện chưa chứng minh được tính mới.

[Protocol development tiếp theo](gsm8k_development_validation_protocol_20261004.md)
đã ghi trước mẫu 96 nhóm mới, loại toàn bộ 24 câu cũ, chia 48 nhóm cho chọn quy
tắc và 48 nhóm để kiểm tra quy tắc đã chốt. Đây là candidate và thiết kế, chưa
có model outputs hay kết quả fit/validation mới.

Bạn bắt đầu ở [gói duyệt câu hỏi](../data/gsm8k_development_reviewed_v1/review.md).
Phân công và bước đọc paper nằm trong [bảng việc](research_work_split_20261004.md).

## Bằng chứng

- [Raw run](../audit/gsm8k-fixed-baseline-measured-20261004/manifest.json): commit sạch `3dcd2c9bf17c7a451463c3fe4835bd70f8ae14a2`, model snapshot `545dc4251c05440727734bcd94334791f6ab0192` được xác minh nội dung upstream.
- [Audit](../audit/gsm8k-fixed-baseline-review-20261004/manifest.json), [bảng đầy đủ](../audit/gsm8k-fixed-baseline-review-20261004/report.md), [kiểm chứng](../audit/gsm8k-fixed-baseline-review-20261004/verification.json): 69 record khớp log flushed, prompt/đáp án/score/token/tool được kiểm tra lại.
- [Replay](../audit/gsm8k-fixed-baseline-replay-20261004/manifest.json): sáu artifact khớp từng byte. Audit/replay không gọi model mới.
- [Protocol đã chốt cho pilot](gsm8k_development_protocol_20261004.md), [nguồn có license và hash](../audit/gsm8k-source-20261004/manifest.json), [duyệt và loại câu trước generation](../data/gsm8k_development_reviewed_v1/manifest.json).

74 kiểm tra phần mềm qua trước collection, gồm bộ research bắt buộc và MLX
native. Kết quả đó xác nhận pipeline hoạt động, không thay thế số đo model hoặc
human review. Stage 0 giữ nguyên; chưa chốt cấu hình thực nghiệm chính hay claim
cho bài báo.
