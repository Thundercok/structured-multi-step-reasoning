# RAT Qt Quick: chọn PDF → tìm trang → đọc → chép trích dẫn

2026-10-22, Asia/Saigon. Người dùng đã chọn luồng PDF offline làm công năng
đầu tiên cho bước chuyển Qt Quick. Đây là lát cắt ứng dụng chạy với tệp thật;
không phải dữ liệu trả lời cố định của bản thiết kế. Cửa sổ chính Widgets và
bản `rat.app` đã đóng gói chưa được thay thế.

## Mở và dùng

Từ root repo:

```bash
.venv/bin/python main.py quick-pdf
```

Hoặc chỉ định đúng một PDF:

```bash
.venv/bin/python main.py quick-pdf --document "/đường/dẫn/tài liệu.pdf"
```

- Chọn **Chọn PDF** hoặc thả một tệp vào cửa sổ. Không quét thư mục và không
  thêm tệp vào chỉ mục. Luồng này không cần Ollama/model.
- Nhập từ hoặc cụm từ rồi Enter. Tìm mọi từ cùng xuất hiện, không phân biệt
  hoa/thường và dấu tiếng Việt; không coi đây là trả lời AI hay semantic search.
- Kết quả ghi trang PDF từ 1, nhãn PDF và đoạn trích thực sự lấy từ trang đó.
  **Đọc trang** mở văn bản cùng nguồn; **Kết quả tìm** quay lại danh sách đã có.
  Bấm tên PDF trong chatbar để nhập số trang hoặc mở tệp gốc.
- Bôi chọn đoạn muốn lấy rồi **Chép trích dẫn**. Nếu chưa chọn, dùng tối đa
  500 ký tự đầu trang. Nội dung chép gồm đoạn gốc, tên tệp, trang PDF, nhãn PDF
  nếu khác số trang, và đường dẫn. Số trang PDF không khẳng định số in trên sách.
- **Mở PDF gốc** gửi yêu cầu mở tệp cho hệ điều hành; không hứa mở đúng trang
  trong một ứng dụng bên ngoài. Đọc đúng trang diễn ra trong RAT.

## Trạng thái thực

Loading theo công việc worker, không chạy timer giả để tạo câu trả lời. Chỉ có
một worker và một slot chờ có thể thay thế. Chọn tệp mới hủy quyền công bố của
yêu cầu cũ; callback đến muộn không được ghi đè tài liệu mới.

Simple giữ workbench thu gọn. Tìm/đọc xong hoặc có lỗi cần xem thì `!` báo một
lần. Mở kết quả xác nhận đã xem; thu lại không dựng lại dấu `!` cho cùng kết quả.
Thông tin số trang khi mới chọn tệp không được coi là đã đọc nội dung. Draft và
đoạn văn đang chọn giữ nguyên khi thu/mở. Nhật ký lấy từ thao tác đã chạy,
không hiển thị private chain of thought.

Nút dừng thu hồi quyền công bố kết quả ngay. Cancellation ở bước đọc từng trang
là cooperative; một lệnh parse pypdf đang chạy chưa chắc dừng ngay. Đóng cửa sổ
đợi worker trong thời gian ngắn và không báo đã kết thúc thread nếu nó còn chạy.

## Giới hạn và lỗi

PDF tối đa 64 MiB; mỗi lượt tìm tối đa 400 trang, hiện 5 trang khớp. Phạm vi đã
tìm và số trang chưa tìm luôn được giữ rõ; nút **Tìm tiếp** dùng từ khóa cũ cho
phần kế tiếp. Đọc một trang giới hạn 8.000 ký tự và báo khi cắt văn bản.

Tái sử dụng `document_intake.pdf.read_pdf` và `rat.engine.book_pages`;
`BookPageError` bổ sung mã lỗi ổn định và vẫn kế thừa `ValueError`.

- PDF hỏng, mất tệp, không có quyền đọc, thiếu engine/crypto, có mật khẩu và
  không có trang trả thông báo riêng.
- Trang không có text có thể là trang trắng hoặc scan/ảnh. Luồng này báo
  `no_text_page`; **chưa chạy OCR trong giao diện này**. Không biến ảnh/metadata
  thành nội dung giả. PDF có mật khẩu cần bản đã mở khóa.
- Kiểm tra stat stamp trước/sau tác vụ và trước khi chép/mở. Nếu tệp thay đổi
  thông thường, yêu cầu chọn lại. Stamp không phải content hash hoặc durable
  artifact revision.

## Vị trí triển khai và kiểm tra

- `rat/ui/quick/PDFDesk.qml` là surface cho luồng PDF thật. `PaperDesk.qml`
  giữ prototype fixture cũ; launcher thật và Qt journey tests dùng `PDFDesk.qml`.
- Surface thật có nền trong suốt, không titlebar mặc định; cửa sổ ôm nội dung,
  lớn lên trên để giữ đáy chatbar khi còn đủ chỗ trên màn hình. Kéo dòng
  **RAT** trong footer chatbar để di chuyển, dùng **×** để đóng. Nếu chạm mép màn hình,
  vị trí được giới hạn lại trong vùng hiển thị.
- Tệp, chọn PDF và menu đi tới trang nằm trong chatbar. Đọc trang dài giữ nút
  chép/thu bên ngoài vùng cuộn; draft dài cuộn trong chatbar thay vì kéo cửa sổ
  cao vô hạn. Progress mảnh chỉ tạo khi có công việc, tắt chuyển động với
  `--reduced-motion`.
- `rat/ui/quick_pdf_controller.py` giữ selection, ownership, trạng thái và worker.
- `rat/engine/selected_pdf.py` là adapter headless cho tệp được chọn rõ ràng.
- `rat/ui/quick_app.py` và nhánh `quick-pdf` trong `rat/main.py` mở luồng thật.

Kiểm tra bằng PDF tự tạo, gồm trang khớp ở cuối tệp, nhãn trang khác số thứ tự,
PDF rỗng/hỏng/khóa, trang trắng/ảnh, hủy, source thay đổi và callback đến muộn:

```bash
.venv/bin/python -m pytest tests/test_selected_pdf.py tests/test_book_pages.py tests/test_document_intake_robustness.py -q
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_quick_pdf.py -q
.venv/bin/python scripts/preview_rat_quick.py --smoke
```

Qt tests/offscreen captures xác nhận wiring, selection, anchor, copy và nguồn
trên fixtures, không thay acceptance macOS thật (IME, file picker, drag/drop,
hotkey hoặc hiệu năng). Không đo chất lượng model/OCR, không đổi controller,
research harness, Stage 0 hoặc model mặc định. Packaging Qt Quick và migration
toàn bộ default UI vẫn thuộc bước đánh giá riêng của ADR-005.

### UI polish sau phản hồi bản Quick

Bản PDF dùng `PDFDesk.qml` riêng để giữ prototype fixture ổn định. Đã kiểm
tra 6 Qt journeys, các cảnh Simple/!/startup/loading/error, menu trang, draft
và trang dài, theme tối ở 520 px; không có QML warning. Native smoke bằng
Cocoa/Metal xác nhận alpha ngoài surface bằng 0 với alpha buffer 8. Ảnh grab
của software offscreen dùng RGB32 nên không dùng nó để khẳng định alpha OS.
Kết quả và hash nguồn: `prototypes/rat_quick/validation/pdf-ui-polish-20261022.json`.
Native renderer smoke không thay kiểm tra tương tác macOS nêu ở trên.
