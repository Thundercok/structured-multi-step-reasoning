# RAT Quick — visual review và kế hoạch minor tiếp theo

Trạng thái cập nhật: đã triển khai sau khi người dùng duyệt, gồm selector.
Kết quả/giới hạn kiểm tra xem mục cuối `rat_ui_minor_20261023.md`.
Các phần dưới giữ nội dung đánh giá và kế hoạch tại thời điểm đề xuất.

2026-10-23, Asia/Ho_Chi_Minh. Người dùng: “vẫn xấu, tự nhìn đi, và plan tiếp”.
Lượt này chỉ đánh giá/lập kế hoạch, không sửa thêm product source.

## Mốc đã xem

Đã xem ảnh source hiện tại của Finder, Apps, PDF và answer tại 520/700 px,
light/dark, trong `work/rat_ui_consistency_20261023/`. SHA-256 của
`rat/ui/quick/PDFDesk.qml` vẫn trùng source được capture:
`d4d3f7aeb1912162c01f5e8b7ca41fa45e7a284215a4e88f7cdbe6c7aedfc9e0`.
Đã đối chiếu ảnh Apps dùng native icon trong `docs/screencaps/` và ảnh Finder
showcase ở `work/rat_ui_minor_20261023/after/`. Ảnh native icon đó thuộc mốc
trước đồng nhất, chỉ dùng để phân biệt icon thật với placeholder trong fixture.
Không dùng placeholder Apps để kết luận chất lượng artwork/icon sản phẩm.

Inventory máy hiện không có RAT/Python đang chạy; chưa quan sát cửa sổ native
của source hiện hành. Nhận xét dưới dựa trên captures, không phải native acceptance.
Nền đen ngoài surface của capture không phải palette desktop được đề xuất.

## Những điểm làm hình thức chưa đạt

1. **Nhiều chrome cho ít nội dung.** Header cách nội dung khá xa; sau các kết
   quả còn thanh hành động, đường kẻ, khoảng trống và dòng nhật ký. Hai kết
   quả trông như một bảng công cụ nhỏ nằm trong một tờ giấy lớn.
2. **Thứ bậc Finder sai ở bản hẹp.** Tên tệp đầu tiên bị rút thành “Quy_ch…”
   trong khi badge PDF, gợi ý Enter/Shift+Enter và hai icon cùng chiếm hàng tên.
   Nhãn thư mục, excerpt và các đường bao nhỏ làm mắt phải đổi điểm nhìn nhiều.
3. **Thao tác bị nhắc lại.** Enter/Hỏi xuất hiện trong hàng chọn và thanh phím
   tắt dưới. Apps có nhiều lớp nhắc tên phần, số lượng, hướng dẫn và tên app đã
   chọn. Sửa màu chưa làm giảm mật độ này.
4. **Wrap hết tràn nhưng chưa đẹp.** Ở 520 px, Escape/Quay lại của Apps nằm lẻ
   trên dòng hai. Finder cũng dùng một mảng nền khá lớn cho hướng dẫn thao tác.
5. **Phong cách chi tiết chưa liền.** Lớp giấy/Chuột có tính minh họa; bên trong
   lại dày các ô viền và keycap nhỏ. Cần giảm mức trang trí cạnh tranh trong
   phần dữ liệu, giữ điểm nhấn ở nội dung/selection và composer.

Gói token trước có ích cho bảo trì và consistency nhưng chưa xử lý được các
vấn đề thị giác ở trên. Tests đạt không xác nhận giao diện đẹp.

## Kế hoạch theo thứ tự

### 1. Gọn phần đầu/cuối tờ giấy

- Tinh chỉnh khoảng cách header → nội dung và nội dung → dòng chi tiết.
  Đo theo nội dung thật, tránh padding cố định tạo khoảng trống lớn.
- Rút các nhãn/hướng dẫn trùng ý, đặc biệt số lượng Apps được nhắc nhiều lần.
- Dòng “Chi tiết & nhật ký” vẫn có thể mở, với khoảng cách/đường phân cách nhẹ
  hơn. Giữ nội dung, copy/source/error/status cần thiết đọc được.
- Giữ nguyên vị trí chatbar, inset tờ giấy, lớp giấy lệch và Chuột.

Đạt khi hai kết quả ngắn không bị bao quanh bởi chrome nổi bật hơn nội dung;
không cắt nội dung, không làm đáy composer dịch khi mở/thu chi tiết.

### 2. Trả chỗ cho tên tệp và tên ứng dụng

- Cho tên tệp ưu tiên hàng đầu; chuyển metadata/phím gợi ý khỏi vùng tranh chỗ
  với tên. Giữ thao tác của hàng, không che tên bằng icon.
- Bỏ gợi ý Enter/Hỏi trùng trong hàng nếu thanh thao tác đã hướng dẫn cùng lệnh.
- Giảm nhãn phụ dạng badge khi có thể biểu diễn bằng text nhẹ.
- Thử với tên Việt có dấu, tên dài, đường dẫn dài và nhiều kết quả; giữ target
  và selection đúng khi chuyển hàng.

Đạt khi tên `Quy_che_hoc_vu_2026.pdf` đọc được ở bản 520 px mà không cần hover;
chỉ elide khi tên thực sự dài quá vùng dành riêng. Không đánh giá bằng tên ngắn.

### 3. Chỉnh thanh thao tác hẹp có chủ đích

- Rút nhãn thao tác theo độ rộng: “Mở ứng dụng” → “Mở”, “Đọc trực tiếp” →
  “Đọc”, “Hỏi về PDF” → “Hỏi”. Giữ đủ accessible name/tooltip và phím thật.
- Phân bố tên app và thao tác để bản 520 px không còn riêng một dòng Escape.
- Giữ các hành động hiện có, ưu tiên một thao tác chính; nền và keycap phụ ít
  nổi hơn nội dung. Không thêm navigation hoặc menu chức năng mới.

Đạt khi toolbar không tràn, không có một phím đứng lẻ, thao tác chuột/phím
vẫn hoạt động đúng và tên app không biến mất để nhường chỗ cho hướng dẫn.

### 4. Review tổng thể rồi mới chốt

- So cùng một bộ nội dung giữa trước/sau: idle, Finder, Apps đầy/lọc/rỗng,
  answer ngắn/dài và PDF, 520/700 px, light/dark.
- Giữ icon native trong ảnh review Apps cuối; fixture không dùng native icon
  phải ghi rõ. Xem surface trên nền desktop thực để đánh giá lớp giấy.
- Kiểm source còn nguyên trong suốt capture; giữ draft/selection, copy, mở/
  thu, cuộn và keyboard. Chỉ chạy checks liên quan đến phần thực sự đổi.
- Mở source native với dữ liệu tự soạn để kiểm bố cục; không tự mở bản bundle
  cũ rồi coi là bằng chứng cho source mới. Không gọi model thật chỉ để review UI.

## Ranh giới

Tiếp tục UI hiện tại. Không redesign, không thay palette/thang chữ toàn bộ,
không đổi artwork/size Chuột, không chuyển composer hoặc thêm surface. Không
đổi runtime, research, launcher hoặc packaged app trong một gói thẩm mỹ. Mỗi
bước sửa phải có lý do thị giác và ảnh cùng nội dung để đối chiếu. Chưa triển
khai các mục kế hoạch trong lượt review này.
