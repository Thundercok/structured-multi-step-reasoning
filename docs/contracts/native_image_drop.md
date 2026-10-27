# Native image drag/paste ingress — ứng viên M5.8

M5.7 người dùng kéo thumbnail screenshot ở góc màn hình, app báo “Hãy thả file
ảnh trên máy, không phải đường dẫn web.” Đã ghi UI thật và lời báo của người
dùng trong `audit/rat_mini_m57_20261027/`. Chưa có MIME payload của lần đó;
không khẳng định thumbnail đã gửi URL web hoặc đã xác nhận nguyên nhân OS.

## Thay đổi source

- Bỏ chuyển `String(drop.urls[i])` trong QML. Event filter trên QQuickView nhận
  QMimeData trực tiếp, giữ QUrl có kiểu và snapshot trước khi drop kết thúc.
- Adapter dùng chung nhận URL local, file-reference URL macOS, QImage/QPixmap
  và dữ liệu PNG/TIFF/JPEG/...; paste dùng cùng normalization. Không tải URL web.
- `NSFilePromiseReceiver` là nhánh dự phòng khi chưa có ảnh/file đọc được.
  Sau accepted CopyAction mới nhận file vào thư mục tạm riêng; callback native
  chạy queue nền rồi gửi signal về GUI để chuẩn hóa. Không giữ QMimeData cũ.
- Một ảnh/lần; file tạm phải resolve bên trong thư mục nhận; giới hạn bytes và
  pixels hiện có tiếp tục áp dụng. Xóa file tạm sau snapshot/timeout/thoát.
- Pending receive có token/generation và timeout 30 giây. Cancel/new request
  làm callback cũ mất hiệu lực, không dịch ảnh cũ. Không chờ file trên GUI thread.
- QML chỉ chiếu highlight và trạng thái. Khi có ImageInput mới gọi workflow
  `capture_text(image)` → observed artifact → translate_text qua service chung.
- Ghi origin dropped_image cho pixel/promise; không giả định có file gốc với
  ảnh bitmap. Log chỉ metadata khả năng MIME/số URL/promise, không ghi URL,
  đường dẫn, bytes ảnh hay nội dung Clipboard.
- `last-image-drop.json` trong thư mục cấu hình giữ một receipt cục bộ duy nhất:
  version, số URL, có image/MIME encode hay không, nhánh nhận và giai đoạn lỗi.
  Không ghi ảnh, hash ảnh, tên file, đường dẫn hay chữ riêng tư. Hỏng ghi receipt
  không được làm gián đoạn drop. File promise được đăng ký ngay trong accepted
  drop; queue nền chờ file, không hoãn đăng ký đến sau khi native drop kết thúc.

## Trạng thái và phạm vi

Source mới chưa kiểm chứng bằng thumbnail thật. Không dùng bản M5.7 đang mở
để xác nhận code mới. Không tự thao tác UI đang do người dùng giữ. Nghiệm thu
lại chỉ đúng đường drop vừa thất bại sau khi dùng bản M5.8.

Main chưa nối adapter; đây là phần UI ingress dùng lại được, không thêm nghiệp
vụ độc lập hoặc bằng chứng chất lượng model. Shortcut ⌥⇧D vẫn backlog.

Tham chiếu primary: [Qt QMimeData](https://doc.qt.io/qt-6/qmimedata.html),
[Qt QGuiApplication drag delivery](https://github.com/qt/qtbase/blob/6.8/src/gui/kernel/qguiapplication.cpp),
[Apple NSFilePromiseReceiver](https://developer.apple.com/documentation/appkit/nsfilepromisereceiver),
[Apple receivePromisedFiles](https://developer.apple.com/documentation/appkit/nsfilepromisereceiver/receivepromisedfiles(atdestination:options:operationqueue:reader:)).
