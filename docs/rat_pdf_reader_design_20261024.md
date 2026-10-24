# RAT PDF reader — thiết kế đề xuất Build .10

**ĐÃ HOÃN:** người dùng làm rõ cùng ngày: không trực tiếp đọc/duyệt PDF trong
RAT, mà hỏi thông tin, vị trí trang và lấy ảnh đoạn nguồn. Reader đầy đủ chuyển
backlog. Phần dưới giữ thiết kế đề xuất lịch sử, chưa được chốt để triển khai.
Thiết kế hiện hành: `rat_information_evidence_design_20261024.md`.

2026-10-24. Đây là thiết kế của Codex để người dùng xem/chốt và Antigravity triển
khai sau; không phải production UI hoặc evidence live acceptance. Không sửa
source ứng dụng trong lượt thiết kế.

## Bố cục đã thiết kế

- Một tờ reader nằm trên cùng composer hiện có, lùi trái theo trục tập giấy;
  Chuột ở mép trái, không có sidebar hoặc cửa sổ reader riêng.
- Header dòng đầu: quay lại Hội thoại, tên PDF elide kèm tên đầy đủ trong
  tooltip, icon mở PDF gốc, thu gọn. Header và composer luôn còn khi cuộn trang.
- Dòng thao tác: ‹ Trang [1] / 25 ›, chuyển Trang gốc / Văn bản, kính lúp.
  Không trộn phím tìm chữ với hành động gửi chat. Trang gốc mặc định.
- Vùng đọc có cuộn riêng, mặc định khoảng 365px; thu gọn control theo chiều
  rộng 520px và reflow ở cỡ nhỏ hơn. Không cuộn toàn bộ composer theo PDF.
- Footer reader nhẹ: tài liệu gốc và trang đang đọc. Không gán verified hoặc
  ngụ ý model đã đọc trang chỉ vì người dùng mở nó.
- Composer giữ chip tên tài liệu + trang đang đọc + affordance mở lại reader;
  khung gõ vẫn là câu hỏi cho Chuột, góc dưới vẫn build và icon đính kèm.

## Tương tác bắt buộc cho implementation

1. Chọn PDF mới mở Trang 1 trong reader, giữ draft. Không popup trung gian.
2. Prev/next, nhập số trang có validation; vô hiệu khi ngoài biên hoặc đang
   chuyển trang chưa an toàn. Giữ một trang hiển thị nhất quán, không gán trang
   mới lên nội dung cũ trong lúc loading; lỗi hiện tại vùng đọc, không xóa draft.
3. Kính lúp/Cmd-F mở find bar nội tuyến giữa toolbar và nội dung; tìm riêng
   tài liệu đã chọn. Escape chỉ đóng find bar trước. Không sửa composer.
4. Tìm thấy: hiện số trang khớp, điều hướng kết quả, highlight đúng tọa độ gốc;
   giữ mode đang đọc. Trong bản thiết kế, highlight có ở chế độ Văn bản;
   overlay highlight tọa độ trên ảnh gốc thuộc implementation QtPdf.
5. Thu gọn: thẻ nhỏ “Tiếp tục đọc · Trang n / N”, tên tài liệu. Mở lại bằng
   thẻ hoặc chip, giữ trang/mode/vị trí cuộn và draft. Không gọi lại model.
6. Hội thoại: quay về đúng Answer/failed/cancelled và trạng thái đã mở trước
   reader, không suy bằng bool(answerText). Có đường trở lại PDF đã đọc. Không
   làm bộ duyệt toàn bộ lịch sử chat trong .10.
7. Mở PDF gốc giao cho trình đọc hệ điều hành; không thêm external-browser
   route production chỉ vì bản thiết kế liên kết nguồn arXiv để tham khảo.

## Bản xem tương tác

`rat-seamless-reader.html` trong thư mục visualization của chat. Có toàn bộ 25
trang render từ PDF BEST-Route gốc đã lưu, giữ văn bản trích xuất để tìm chữ.
Ảnh preview nén phục vụ thiết kế, không là tiêu chuẩn độ nét production.

Các nút lật trang, nhập trang, đổi mode, tìm chữ, thu gọn/mở lại và quay về
hội thoại là tương tác local. Nút Gửi/đính kèm chỉ phản hồi vị trí/hành vi thiết
kế, không gọi backend. Vùng Hội thoại là placeholder được gắn nhãn, không có
canned model answer. Draft người dùng được giữ khi chuyển trạng thái.

PDF nguồn: work/rat_reading_live_20261024/arxiv_2506.22716_original.pdf;
origin https://arxiv.org/pdf/2506.22716;
SHA256 9746346dc6e6552ccdd20158a0eb4b01e927a3cb46242ebaf3d36a9d3b611d9c.

Triển khai cần regression và native desktop acceptance riêng. Không dùng bản
thiết kế này, việc render PDF hoặc placeholder hội thoại để claim UI/model pass.
Giữ AGENTS, research gates và scope hỗ trợ tìm/mở file/app đã chốt.
