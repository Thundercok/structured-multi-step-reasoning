# RAT — tìm thông tin, đối chiếu và lấy đoạn nguồn

Thiết kế đề xuất ngày 2026-10-24 theo đính chính mới nhất của người dùng.
Chưa triển khai runtime/UI; không đổi research protocol hoặc model defaults.
Reader đầy đủ hoãn theo RAT-PDF-READER-01, thay hướng Build .10 đọc/lật trang.

## Một luồng chính

Hỏi trong composer → RAT xác định điều cần tìm → lấy đoạn phù hợp → đối chiếu
nội dung và trang → trả lời ngắn + nguồn + ảnh cắt. Người dùng không phải mở
PDF reader, lật trang, chọn mode hoặc tìm lại câu trong văn bản đã trích.

Tờ kết quả giữ phong cách bàn giấy hiện có:

1. Câu hỏi người dùng gọn ở đầu.
2. Câu trả lời đi thẳng vào điều cần biết (vị trí trang hoặc nội dung), không
   ép mọi câu hỏi thành một kết luận kiểu “ở trang N”.
3. Dòng xử lý gọn: Tìm đoạn → Đối chiếu → Trích nguồn. Chi tiết mở theo nhu cầu.
4. Nguồn rõ: tên tài liệu, trang, mục nếu xác định được; trích nguyên văn.
5. Ảnh cắt đúng vùng trên PDF, đủ dòng xung quanh để đọc; có Lưu ảnh và Chép
   trích dẫn. Không cắt một vùng bất kỳ rồi gọi là đoạn hỗ trợ câu trả lời.
6. Thêm ngữ cảnh mở phần lân cận ngay trong tờ kết quả. Mở PDF gốc là đường
   phụ khi cần toàn tài liệu, không dựng một reader khác trong RAT lúc này.
7. Composer giữ draft để hỏi tiếp. Min mode tóm tắt kết quả tìm được, không
   tóm tắt “trang đang đọc”; mở lại giữ nguyên kết quả và nguồn.

## Structured reasoning trong RAT

UI công khai mục tiêu, quyết định/hành động cần thiết, nguồn, kết quả đối
chiếu và giới hạn. Không hiển thị raw/private chain of thought. Không coi một
timeline 3 bước là đã triển khai phương pháp CoT hay đã cải thiện model quality.

- Xác định cần nội dung, vị trí hay cả hai; thiếu dữ kiện thì hỏi ngắn.
- Chọn đoạn/trang cần đọc dựa trên kết quả thật, giữ read scope cụ thể.
- Đối chiếu: đoạn có hỗ trợ nhận định không, trang/path có đúng tài liệu đang
  dùng không; nhãn verifier chỉ theo kết quả verifier thật. Có nguồn không
  đồng nghĩa PASS. Chưa kiểm thì nêu chưa kiểm; giữ UNKNOWN khi thích hợp.
- Chứng cứ chưa đủ: đọc/tìm tiếp trong ngân sách hoặc trả lời thiếu chứng cứ,
  không tô xanh bước, sinh screenshot giả hay diễn giải quá phạm vi đã đọc.
- Đủ chứng cứ cho yêu cầu cụ thể thì dừng và trả lời/cắt nguồn, tránh kéo dài
  suy luận vô ích. Đây là hợp đồng thiết kế cần nối runtime, chưa là trạng thái
  implementation hiện tại được xác nhận.

Các trạng thái phải thiết kế khi triển khai: đang tìm, đang đối chiếu, có kết
quả, nhiều nguồn mâu thuẫn, không tìm thấy, PDF scan không định vị được chữ,
file đã đổi, timeout và cancelled. Giữ bản nháp và trạng thái đã hủy/failed khi
đóng gợi ý Finder; xử lý lỗi review Build .9 trước khi chốt acceptance.

## Bản xem bố cục

`rat-evidence-desk.html` trong thư mục visualization của chat. Mẫu dùng câu về
chi phí triển khai LLM ở Abstract trang 1 của BEST-Route. Nội dung và ảnh cắt
được lấy/đối chiếu thủ công từ PDF thật; không phải kết quả gọi model hoặc
live UI acceptance. Các bước xử lý là minh họa hợp đồng UX, chưa là execution
trace thật của runtime. Khung đã ghi rõ “Thiết kế · nội dung đối chiếu thủ công”.

Có tương tác thu/mở kết quả, chi tiết cách xử lý, ngữ cảnh, phóng ảnh cắt, lưu
ảnh và chép trích dẫn. Nút Gửi không gọi backend. Không có reader hoặc phân
trang. PDF nguồn giữ nguyên như các run đã lưu:
`work/rat_reading_live_20261024/arxiv_2506.22716_original.pdf`,
origin https://arxiv.org/pdf/2506.22716,
SHA256 9746346dc6e6552ccdd20158a0eb4b01e927a3cb46242ebaf3d36a9d3b611d9c.

Sau khi người dùng chốt bố cục mới giao implementation cho Antigravity bằng
prompt; Codex không được điều khiển Antigravity. Không tự tiếp tục reader từ
prompt Build .10 cũ. Native acceptance/model evidence phải thu riêng và ghi
đúng ngân sách trước khi chạy.
