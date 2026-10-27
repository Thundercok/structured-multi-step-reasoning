# Backlog: global capture hotkey của RAT Mini

Quyết định người dùng 2026-10-26: hoãn ⌥⇧D, ưu tiên screenshot do macOS tạo
rồi kéo thả vào RAT. Không tiếp tục yêu cầu người dùng cấp quyền/chạy lại M5.3.

## Hiện trạng được ghi nhận

- M5.2: từng có callback Carbon thật, nhưng lần bấm sau khi restart không có
  callback. Không coi đăng ký thành công là bằng chứng hotkey ổn định.
- Sau khi người dùng cấp quyền, menu đã chụp ảnh, OCR 22 ký tự tiếng Việt và
  trả `same_language`. Chưa chứng minh dịch Anh→Việt từ screenshot.
- M5.3: helper Carbon độc lập đã báo READY; đóng stdin thoát 0. GUI M5.3 đã
  mở và đăng ký helper. Chưa xác nhận global shortcut vật lý, dịch Anh→Việt
  hay Esc. Một build lỗi Cocoa plugin được giữ bằng chứng, build lại đã mở UI.
- Bằng chứng: `audit/rat_mini_hotkey_20261026/`. Không xóa raw logs/build cũ.

## Khi mở lại backlog

1. Kiểm tra helper nhận phím thật khi RAT ở nền, nhiều lần khởi động lại.
2. Xác định policy ký/phân phối ổn định để quyền Screen Recording không bị
   gắn vào cdhash cũ sau mỗi build ad-hoc.
3. Kiểm chứng riêng vùng chọn, Esc hủy, OCR rồi dịch thật qua tool contracts.
4. Chỉ đưa shortcut trở lại UI sau khi có bằng chứng end-to-end.

## Hướng hiện hành M5.4

`⌘⇧4 → file screenshot → DropArea → bounded image ingress → capture_text(image)
→ captured_text/source_ref → translate_text → verification/observation → UI`.

Helper và adapter chụp trực tiếp được giữ để nghiên cứu sau, nhưng không khởi
động helper, đăng ký phím hay quảng bá menu chụp trực tiếp trong runtime M5.4.
Mọi OCR/dịch vẫn dùng service/dispatcher chung; không tạo nghiệp vụ riêng cho QML.

M5.4 cần kiểm chứng sau khi được người dùng cho phép: thả PNG thật từ Desktop,
dịch Anh→Việt, chỉ dẫn ngôn ngữ trong composer, ảnh hỏng/quá lớn, nhiều ảnh,
ảnh không có chữ, hủy/thay tác vụ đang chạy và bảo toàn file gốc sau drop.
Chưa chạy các kiểm chứng này trong lượt triển khai M5.4.

Tham chiếu adapter kéo thả: [Qt DropArea](https://doc.qt.io/qt-6/qml-qtquick-droparea.html)
và [Qt DragEvent](https://doc.qt.io/qt-6/qml-qtquick-dragevent.html), gồm URL đầu
vào và `accept(Qt.CopyAction)`. Đối chiếu API không thay thế kiểm chứng live UI.

## 2026-10-27 — Look invocation, source only

User approved Look / Minimal / Single / Full and requested an ergonomic chord.
New Mini source defaults: ⌥Space summons Look, ⌥⇧Space summons Minimal. These
keys only open the corresponding projection; they do not capture the screen.
The earlier ⌥⇧D capture hotkey stays deferred. Screenshot/drop/paste still feeds
shared capture tools. Native helper protocol changed; old binaries are rejected.
No helper compile, test, launch or build was run. Main's existing ⌥Space alias
is unchanged pending Mini acceptance. See docs/rat_mini_look_modes.md.
