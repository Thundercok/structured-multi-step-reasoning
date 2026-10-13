# RAT notes UI — Stage 1, iteration 4

Ngày: 2026-10-12, Asia/Saigon. Trạng thái: bản xem, chờ người dùng duyệt.

Người dùng chưa duyệt iteration 3: muốn trải nghiệm liền mạch hơn, Chuột thuộc
màn hình như bố cục trước. Đã đối chiếu ảnh `rat_companion_reasoning_20261012`
(`compact_idle.png`, `full_notes_trace.png`): Chuột đứng trên nền trong suốt bên
trái một ô chat. Iteration này khôi phục cách đặt đó cho bản xem notes theo lượt.

## Thay đổi

- Cửa sổ không có chrome hệ điều hành, nền ngoài ô chat trong suốt thật.
  Bỏ nền kem toàn cửa sổ, logo/header bên ngoài và cột caption dưới Chuột.
- Chuột là widget trực tiếp trên canvas trong suốt, đứng bên trái ô chat.
  Giữ cùng vị trí khi full/compact và giữ sprite/emote/chuyển động hiện có.
- Một khung chứa hội thoại, ghi chú theo lượt và composer. Ô nhập hòa vào nền
  chat với đường phân cách nhẹ; các controls nằm gọn trong khung. Badge dữ liệu
  mẫu vẫn hiển thị để phân biệt bản xem với phiên live.
- Thanh nhỏ trên khung cho phép kéo cửa sổ mà không lấy focus hoặc xóa draft.
  Có nút đóng và shortcut đóng tiêu chuẩn; CLI thêm `--compact` để mở bản gọn.
- Animation đổi kích thước dùng thuộc tính `size`, để thao tác kéo không bị
  kéo ngược về tọa độ cũ. Regression đã tái hiện lỗi với animation `geometry`
  trước khi sửa; log lỗi gốc được giữ trong `drag_animation_reproduction.txt`.
- Khi mở preview, focus vào composer. Người dùng vẫn có thể Tab tới Chuột;
  viền focus bàn phím chỉ hiện khi Chuột thực sự có focus.

Các thao tác notes và câu trả lời tiếp tục dùng fixture. Giai đoạn 2 chưa bắt
đầu: ID lượt ổn định, lịch sử bất biến, revision validation và bỏ/hoàn tác thật
trong core vẫn chờ người dùng duyệt UI.

## Kiểm chứng

```bash
QT_QPA_PLATFORM=offscreen /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m pytest tests/test_turn_notes_preview.py tests/test_work_context_ui.py -q
```

**32 passed in 32.86s**: 23 preview tests và 9 work-context UI tests.
Kiểm tra mới đọc alpha từ ảnh Qt thật ở full/compact, xác nhận sprite vẫn hiện,
giữ tọa độ Chuột, kéo cửa sổ giữ draft/selection/focus, đóng cửa sổ không có
chrome, và kéo trong lúc animation không làm cửa sổ nhảy về tọa độ cũ.
Các regression notes iteration 2/3 vẫn qua. `git diff --check` qua.

11 ảnh trong thư mục này được chụp bằng Qt offscreen, giảm chuyển động:
full, chạm Chuột, editor, cảnh báo phiên bản mô phỏng, link bản mới, bỏ/hoàn tác,
compact, mở lượt cũ, QA drawer, chi tiết nguồn và composer draft. Đã xem ảnh
cuối full, compact và editor. Nền ngoài khung có alpha trong suốt, không phải
một nền đen được thêm vào thiết kế.

Đã thử mở native compact preview. Công cụ CUA chọn cửa sổ RAT cũ tên `rat`
với `NotebookPane`, thay vì cửa sổ preview; không thực hiện thao tác trên cửa
sổ đó. Process preview chạy tới event loop Qt nhưng chưa xác minh được bố cục
native hoặc độ mượt thực trên màn hình. Đã dừng riêng process fixture do mình
khởi chạy (PID 94525, session kết thúc 143); không đóng ứng dụng RAT cũ.

Kết quả này là kiểm tra UI, không phải bằng chứng chất lượng model. Bản xem chưa
thay NotebookPane của RAT chính. Source trước chỉnh sửa và hash được lưu trong
`before/`, `before_sha256.json`; source sau chỉnh sửa, log và ảnh nằm trong
`validation.json`. Audit iteration 3 giữ nguyên để đối chiếu.

## Chạy bản xem

```bash
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 scripts/preview_turn_notes.py --compact
```

`⌘L` đổi full/compact. Kéo vùng trống trên khung để di chuyển; `×` hoặc `⌘W`
đóng bản xem. `⋯` ở góc trên mở công cụ thử fixture. Xuất ảnh vào thư mục mới:

```bash
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 scripts/preview_turn_notes.py --save-screenshots /tmp/rat-turn-notes-preview
```
