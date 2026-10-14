# Tìm trang sách và ghép bảng trong RAT

Ngày triển khai: 2026-10-14, Asia/Ho_Chi_Minh. Đây là thay đổi ứng dụng RAT;
chưa có đánh giá chất lượng bằng model thật.

## Cách dùng trong ô chat

PDF cần nằm trong thư mục đã được RAT lập chỉ mục. Ví dụ dưới đây là yêu cầu
để thử, không phải hội thoại model đã chạy thành công:

- “Tìm sách DSA, rồi tìm những trang nói về binary search.”
- “Đọc trang PDF 30 trong cuốn đó; lấy trích dẫn có nguồn.”
- “Lưu đoạn trích này vào ghi chú của cuộc trò chuyện.”
- “Ghép các trang vừa tìm thành bảng gồm tên sách, trang PDF và đoạn trích.”
- “So sánh hai kết quả tính vừa rồi trong một bảng gồm biểu thức và kết quả.”

Kết quả xuất hiện trong cùng chat, dùng bề mặt compact/full hiện có. Menu
**Thao tác** của kết quả tìm trang cho phép đọc đúng trang được chọn; nếu còn
phạm vi chưa tìm, có thao tác **Tìm tiếp từ trang PDF …**.

## Ba chức năng

**Tìm trang sách.** `search_book_pages` đọc trực tiếp từng trang của PDF đã
chọn thay vì chỉ tìm phần văn bản đầu tệp đã lưu trong chỉ mục. Mỗi kết quả có
đường dẫn sách, số trang PDF tính từ 1, nhãn trang PDF và đoạn văn bản khớp.
Tìm theo các từ cùng xuất hiện trên một trang, không phân biệt hoa/thường và
dấu tiếng Việt. Cụm từ liền nhau được ưu tiên trước, sau đó số lần xuất hiện.
Đây là tìm từ khóa, chưa phải tìm ngữ nghĩa hoặc suy luận nội dung.

Mặc định mỗi lần đọc tối đa 400 trang và trả 5 trang khớp. Kết quả ghi rõ phạm
vi đã tìm, số trang khớp, việc cắt danh sách và `next_start_page` nếu còn trang.
Không suy ra “sách không có nội dung này” từ một phạm vi chưa tìm hết.

**Đọc một trang và lấy trích dẫn** là chức năng được đề xuất thêm.
`read_book_page` chỉ đọc trang được yêu cầu, tối đa 8.000 ký tự mặc định
(có thể yêu cầu đến 12.000). Kết quả giữ văn bản, số trang, nhãn PDF, nguồn và
trạng thái cắt ngắn. Có thể dùng `record_work_note` hiện có để lưu nguyên văn
từ trường `content` hoặc `citation.snippet`, gắn với ID/phiên bản kết quả thật.
Ghi chú này nằm trong cuộc trò chuyện; không tự lưu thành bookmark lâu dài.

**Ghép bảng từ các kết quả thật** là lát cắt của backlog **RAT-AI-02**.
`compose_result_table` cho trợ lý chọn tiêu đề, cột và các ô cần trình bày từ
một hoặc nhiều artifact/phiên bản. Từng ô phải tham chiếu một trường dữ liệu
đơn thực sự tồn tại; công cụ không nhận literal cells. Bảng giữ bản chụp dữ
liệu và nguồn từng ô, kể cả khi kết quả gốc được cập nhật về sau. Nguồn phiên
bản cũ được ghi nhận rõ ở thời điểm ghép. Giới hạn 12 hàng, 6 cột, 2.000 ký tự
mỗi ô. Bảng cũng dùng được cho lịch, phép tính và kết quả khác; không có
workflow DSA hoặc màn hình riêng.

Đây là phép chọn và sao chép dữ liệu. Tiêu đề/cột do model đề xuất không được
coi là diễn giải đã kiểm chứng. Công cụ không tự tính chênh lệch, kết luận hai
đại lượng so sánh được, hoặc cập nhật bảng khi nguồn đổi. RAT-AI-02 rộng hơn
vẫn cần thử model thật, review nội dung và hợp đồng trình bày phong phú hơn.

## Giới hạn

- Số trang trong tệp và nhãn trang PDF có thể khác số in trên sách; không đoán
  số trang in từ thứ tự vật lý.
- Trang không có văn bản trích xuất được báo riêng; đọc trang trắng/scan trả
  lỗi cần OCR. Chưa thêm OCR vào đường tìm trang này. [Tài liệu pypdf](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)
  mô tả giới hạn trích xuất văn bản từ trang ảnh.
- Tệp chưa được lập chỉ mục, PDF có mật khẩu và trang ngoài phạm vi trả lỗi;
  không đoán đường dẫn hoặc diễn giải dữ liệu lỗi thành nội dung.
- Hủy/reset không công bố kết quả tìm dở. Tìm kiếm không gọi model, không
  tự lập chỉ mục tệp cá nhân và không import Qt.
- DocAI tiếp tục độc lập. Pipeline NCKH, model mặc định và Stage 0 giữ nguyên.

## Kiểm tra phần mềm

PDF kiểm thử có 30 trang thật, nội dung cần tìm ở trang 30, nhãn PDF tùy chỉnh,
trang trắng và bản có mật khẩu. Scripted runtime kiểm tra chuỗi tìm → đọc →
lưu trích dẫn → ghép bảng; đây là kiểm tra phần mềm, không phải bằng chứng
model tự điều phối đúng.

Lệnh headless:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest \
  tests/test_book_pages.py tests/test_result_tables.py \
  tests/test_interaction_kernel.py tests/test_interaction_kernel_regressions.py \
  tests/test_assistant_runtime.py tests/test_rat_task_memory.py \
  tests/test_work_context.py tests/test_rat_completion_boundaries.py \
  tests/test_rat_context_snapshot.py -q -p no:cacheprovider
```

Kiểm tra Qt riêng cho tính năng mới:

```bash
PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=offscreen python -m pytest \
  tests/test_book_features_ui.py -q -p no:cacheprovider
```

Các kiểm tra Qt xác nhận menu đọc đúng trang qua dispatcher, giữ kết quả tìm
khi thêm nội dung trang, render bảng/nguồn dưới dạng văn bản và giữ phần đang
mở khi đổi compact/full. Chưa thử hội thoại mới với model thật hoặc nghiệm
thu trực tiếp với người dùng.

Kết quả cuối: **165 headless tests và 3 Qt tests mới đã qua**. Bộ Qt cũ chạy
riêng qua 7 tests; khi ghép hai module có crash phụ thuộc thứ tự ở worker
xuất lá số, chưa xác định nguyên nhân. Không coi toàn bộ bộ GUI ghép đã qua.
Xem [báo cáo kiểm tra](../audit/rat_book_features_20261014/REPORT.md).
