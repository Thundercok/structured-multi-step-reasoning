# ADR-005: thử lớp hiển thị RAT bằng Qt Quick/QML

**Status:** Proposed — đã có prototype độc lập, chưa chuyển UI chính.
**Date:** 2026-10-22, Asia/Saigon.
**Deciders:** Người dùng chọn hướng phát triển; migration vào RAT cần acceptance riêng.

**Cập nhật cùng ngày:** người dùng đồng ý thử chuyển từng phần và chọn công năng
PDF offline. Đã nối entry point `python main.py quick-pdf` với tệp thật; xem
[mô tả luồng](rat_quick_pdf_20261022.md). Surface thật ở `rat/ui/quick/PDFDesk.qml`,
có cửa sổ trong suốt co theo nội dung và menu tệp trong chatbar. `PaperDesk.qml`
giữ prototype fixture ban đầu. Các đoạn dưới mô tả prototype ban đầu; chưa
chốt migration toàn bộ default UI hoặc hiệu năng.

## Context

Người dùng yêu cầu tiếp tục hoàn thiện thiết kế và tìm công nghệ nhẹ, hiện đại
hơn. Hướng hình ảnh đã chọn là Chuột lớn, giấy lệch có chiều sâu, chatbar làm
điểm neo, Simple thu gọn và dấu `!` cho cập nhật mới đáng đọc. Loading phải
thuộc cùng cụm giao diện. Luồng thao tác là tóm tắt công khai, không phải raw
private reasoning.

RAT hiện dùng PyQt6 Widgets (`rat/ui/omnibar.py`); `requirements.txt` đã có
PyQt6. Môi trường `.venv` kiểm tra ngày này có PyQt 6.8.1, Qt 6.8.2 và nạp
được QtQuick/QtQml. `rat.spec` chưa được đổi để đóng gói prototype QML.
RAT–CoT vẫn là một hệ theo `project_scope.md`; thay giao diện không xác nhận
bất kỳ cải thiện chất lượng suy luận hoặc hiệu quả model nào.

## Decision being evaluated

Thử **Qt Quick/QML với một QQuickView riêng**, dùng backend Python hiện có
khi tích hợp sau này. Prototype hiện chỉ đọc asset Chuột và chạy fixtures.
Không thêm package, không sửa startup/default UI, không khởi động engine,
indexer, database hay mô hình.

Qt Quick cung cấp scene graph và các cơ chế bố cục/chuyển động cho giao diện
động. Đây là khả năng của công nghệ, chưa phải kết quả đo của RAT.
[Qt UI technologies](https://doc.qt.io/qt-6/topics-ui.html).

Không chọn QQuickWidget làm cách nhúng mặc định trong thử nghiệm: nó thêm
offscreen render pass và vô hiệu threaded render loop. Khi thực sự nhúng vào
app, phải đánh giá stacking/focus của top-level window thay vì giả định hai
cách này có cùng chi phí.
[QQuickWidget performance](https://doc.qt.io/qt-6/qquickwidget.html#performance-considerations).

## Options considered

| Hướng | Lợi ích trong RAT | Chi phí/ràng buộc |
| --- | --- | --- |
| Tiếp tục PyQt6 Widgets | Thay đổi nhỏ nhất; giữ cửa sổ, focus và packaging hiện có | Bố cục và chuyển động tùy biến tiếp tục nằm trong widget/painter code; vẫn có thể làm đẹp, không bắt buộc đổi stack |
| **Qt Quick/QML** | Dùng Python/PyQt6 đang có; prototype khai báo tách khỏi engine; phù hợp thử chuyển trạng thái | Thêm QML/Quick modules vào bản đóng gói; phải nối public events và kiểm tra hành vi cửa sổ/IME; chưa đo RAM hoặc bundle delta |
| Tauri + frontend web | Có thể dùng thiết kế HTML/CSS; macOS dùng WKWebView của hệ điều hành | Thêm Rust, IPC và vòng đời Python sidecar; cần làm lại shell/cửa sổ và đo toàn bộ cây process, không chỉ webview |

Tauri không đóng kèm bản sao webview hệ điều hành trong executable. Với RAT,
Python và dependencies vẫn phải được đóng gói hoặc triển khai riêng; vì vậy
đặc tính này không tự chứng minh toàn bộ ứng dụng nhỏ hơn.
[Tauri process model](https://v2.tauri.app/concept/process-model/),
[Python/external sidecars](https://v2.tauri.app/develop/sidecar/).

## What exists

- `prototypes/rat_quick/PaperDesk.qml`: bảy trạng thái fixture, theme sáng/tối,
  nguồn/nhật ký mẫu, luồng trực quan/gọn, gửi/dừng và giữ bản nháp.
- `scripts/preview_rat_quick.py`: launcher riêng; `--smoke` dùng offscreen
  software rendering, tự thoát và báo lỗi nếu kiểm tra không đạt.
- Chỉ dùng các lớp 2D, asset có sẵn và Qt Quick Controls. Không có blur,
  shader tùy biến, particles hoặc animation lặp khi idle. Progress chỉ được
  tạo trong trạng thái loading; chuyển kích thước/y là animation hữu hạn.
- Màu/viền được làm nhẹ hơn trong bản thiết kế; nhận xét thẩm mỹ vẫn cần
  phản hồi của người dùng, không suy ra từ smoke test.

Chạy thử tương tác từ root repo:

```bash
.venv/bin/python scripts/preview_rat_quick.py
```

Kiểm tra và ghi ảnh/report vào thư mục tự chọn:

```bash
.venv/bin/python scripts/preview_rat_quick.py --smoke --capture-dir /tmp/rat-quick-smoke
```

Trên máy này, Qt cần chạy ngoài sandbox để nhận diện CPU NEON đúng; thử import
trong sandbox từng báo thiếu tính năng CPU. Không cài lại Qt để xử lý thông
báo đó.

## Validation and limits

Smoke đã qua trên Qt 6.8.2, offscreen software, 640/520 px: 14 tổ hợp
trạng thái/kích thước; cùng đáy composer; xem rồi thu không bật lại unread;
Enter gửi yêu cầu và không vô tình dừng; dừng giữ draft; hai mức luồng xử lý;
animation hữu hạn kết thúc; reduced motion không chạy animation; không có
cảnh báo Qt/QML trong lần kiểm tra cuối. Bản ghi nằm tại
`prototypes/rat_quick/validation/smoke-20261022.json`.

Đây là bằng chứng khả thi và hợp đồng UI fixture. **Chưa đo** CPU/RAM idle,
first paint, frame time trên Metal, kích thước `rat.app`, TCC/global shortcut,
IME tiếng Việt hoặc tương tác với engine thật. Ảnh offscreen không thay thế
acceptance trên cửa sổ macOS thật. Prototype chưa thể thay RAT đang dùng.

## Before changing the main UI

1. Chốt hình dáng Simple/`!`/loading với người dùng và giữ một nguồn tokens.
2. Đo cùng baseline Widgets: first paint, idle CPU, memory toàn bộ process,
   frame time và bundle delta. Không công bố là nhẹ hơn khi chưa có số đo.
3. Nối adapter vào public execution/result events hiện có; pending, completed,
   failed và cancelled giữ đúng ý nghĩa của runtime, không dùng timer giả.
4. Kiểm tra focus, nhập tiếng Việt, clipboard, phím tắt, cửa sổ trong suốt,
   nhiều màn hình, reduced motion và quyền macOS trong build thử riêng.
5. Đánh giá QML modules/assets trong PyInstaller và đường lui Widgets trước
   khi đề xuất chuyển default.
