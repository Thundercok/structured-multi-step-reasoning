# RAT — đọc trang và chép nguồn với BEST-Route

Ngày 2026-10-24, Asia/Saigon.

Người dùng đổi nguồn kiểm sang [PDF arXiv 2506.22716](https://arxiv.org/pdf/2506.22716).
Dùng nguyên bản tải từ URL đó, 25 trang; trang đầu ghi v1, 2025-06-28.
Không tiếp tục dùng Ensemble Learning hoặc slide Cấu trúc rời rạc đã khảo sát.
Nguồn mới không được dựng lại hay chỉnh nội dung.
[Provenance/hash](../work/rat_reading_live_20261024/document-provenance.json):
SHA256 `9746346dc6e6552ccdd20158a0eb4b01e927a3cb46242ebaf3d36a9d3b611d9c`,
1.183.436 byte. Hash trước/sau trùng nhau.

## Thay đổi đọc trang

Minor UI: bản đọc văn xuôi nối những xuống dòng rõ là phần tiếp của câu,
giúp chiều rộng khung quyết định việc wrap. Helper chỉ đổi newline thành một
dấu cách khi dòng tiếp bắt đầu bằng chữ thường và có đủ dấu hiệu văn xuôi.
Giữ đoạn trắng, đầu bullet, dòng ngắn/tiêu đề và các dòng có dấu hiệu công
thức, bảng hoặc code. Đây là heuristic thận trọng, không tái dựng layout PDF;
vẫn có những chỗ ngắt dòng được giữ lại, nhất là quanh tên riêng và citation.

`pageText` và backend/model vẫn dùng nguyên văn nguồn. UI đọc `pageReadingText`.
Khi chép lựa chọn có whitespace đã đổi, hàm đối chiếu yêu cầu nguyên các từ
và dấu câu phải xuất hiện liên tục trong nguồn; trả lại đúng substring nguồn,
không trả chuỗi hiển thị đã gộp. Nội dung khác chữ/dấu bị từ chối như trước.

`python -m pytest tests/test_pdf_reading_presentation.py -q`: **6 passed**.
Bao phủ gộp dòng, bảo toàn đoạn/bullet, không gộp các dấu hiệu formula/table/code,
chép về nguyên source, và từ chối đoạn lựa chọn không khớp. Không tạo PDF
fixture, gọi model giả hoặc tiêm câu trả lời vào UI. Compile và diff check pass.

## Kiểm qua desktop thật

Mở bản gốc bằng hộp thoại macOS trong RAT QML native, đọc trang 1, cuộn tới
abstract, chọn văn bản và dùng Chép trích dẫn. Thao tác Select All qua bàn phím
đã chọn toàn văn bản trang trong UI. So sánh kết quả: **35 newline nguồn → 23
newline hiển thị**, không đổi chuỗi ký tự khi bỏ whitespace; đoạn chép ra khớp
**nguyên văn nguồn**, có trang PDF 1 và đúng đường dẫn. Đã lưu riêng bản chép.
Chọn một đoạn nhỏ qua AX/drag không thực hiện được; chỉ phần chọn toàn trang
được xác nhận live, còn mapping đoạn nhỏ được kiểm ở hợp đồng.

[Kiểm nguồn/copy](../work/rat_reading_live_20261024/reading-contract-check.json),
[văn bản nguồn đã chép](../work/rat_reading_live_20261024/source-quote-copied.txt),
[ảnh bôi chọn trong trình đọc](../work/rat_reading_live_20261024/live-selected-source.png).

Sau đó hỏi model local thật qua menu Hỏi về PDF. Qwen3 `4b-instruct`, digest
`0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`,
Ollama 0.34.3, `think=false`, context 8192, output cap 640/lượt; không đổi default.

| Lượt | Quan sát |
| --- | --- |
| 1: yêu cầu hai quyết định riêng | Model gộp chọn model và số phản hồi vào ý 1, dùng mục tiêu chi phí làm ý 2. Không đạt đúng cấu trúc/nội dung yêu cầu; giữ nguyên phản hồi và ảnh. |
| 2: yêu cầu tách hai quyết định trong ý 1, bỏ mục tiêu chi phí | Model tách thành chọn mô hình theo độ khó và xác định số lượng phản hồi. Đáp ứng yêu cầu sửa trong ca này. Request có nguyên public reply lượt trước. |

[Hội thoại thật](../work/rat_reading_live_20261024/conversation.md),
[request/public responses](../work/rat_reading_live_20261024/model-calls.json),
[tổng hợp acceptance](../work/rat_reading_live_20261024/acceptance-summary.json).

![Min mode sau yêu cầu sửa](../work/rat_reading_live_20261024/live-turn-turn-2-min.png)

[Full lượt đầu chưa đạt](../work/rat_reading_live_20261024/live-turn-turn-1-full.png),
[full sau yêu cầu sửa](../work/rat_reading_live_20261024/live-turn-turn-2-full.png).
Ảnh min/full cả hai lượt đều lấy từ cửa sổ đang chạy, không dựng câu trả lời.

## Giới hạn và trạng thái

2 model calls báo cáo **2.048 prompt token + 71 generated token**; không phải
toàn bộ chi phí inference. Online latency cả lượt **45,50 s / 13,12 s**, gồm
đọc tài liệu và model. Không diễn giải thành benchmark hay cải thiện latency chung.
QA vẫn chỉ nhận 3.000 ký tự đầu trích xuất, không đọc toàn bộ 25 trang để trả lời.
UI verifier giữ **UNKNOWN**; đối chiếu thủ công không chuyển thành PASS.

Desktop có lỗi `noWindowsAvailable` khi drag và hai timeout trước lượt hỏi tiếp;
AX selectText cũng chưa tạo selection. Khôi phục kết nối và dùng bàn phím chọn
toàn trang thành công; không thay bằng mô phỏng Qt hoặc câu trả lời dựng sẵn.
Cửa sổ vẫn chạy trong lúc timeout, sau đó hoàn tất flow và đóng exit 0.
Không có QML warning; các source trong manifest không đổi trong run.
Daemon do lượt kiểm mở đã được dừng. Không thay research harness hoặc Stage 0.

Bước nhỏ tiếp theo được đề xuất: làm rõ cách người dùng chuyển giữa tìm từ
khóa và hỏi PDF ngay tại ô nhập, vì hành động hỏi hiện cần mở menu tài liệu.
