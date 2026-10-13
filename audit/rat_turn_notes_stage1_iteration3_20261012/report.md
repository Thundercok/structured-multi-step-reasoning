# RAT notes UI — Stage 1, iteration 3

Ngày: 2026-10-12, Asia/Saigon. Trạng thái: bản xem đã tinh chỉnh, chờ duyệt UI.

Người dùng chọn cải thiện cả bố cục, mật độ điều khiển và chuyển trạng thái,
giữ personality “shitposty” của Chuột. Người dùng cũng chọn tinh chỉnh UI trước
khi triển khai giai đoạn 2. Thay đổi này nằm ở bản xem Qt dùng dữ liệu mẫu.

## Thiết kế được triển khai

- Một bề mặt chat màu giấy ấm, chữ rõ và ít nền/viền cạnh tranh. Câu người dùng
  nằm trong bubble bên phải; kết quả, ghi chú và “Cách Chuột làm” theo thứ tự đọc.
- Chuột nguyên thân đứng bên trái. Giữ emote, thở, nhảy và tương tác hiện có;
  lời thoại ngắn theo tone “đồng phạm chạy deadline”. Lời thoại trong ảnh là fixture.
- Ghi chú là dòng chữ nhẹ. Nguồn và backlink của bản đang dùng nằm sau nút `⋯`
  tại chính dòng đó; bản cũ vẫn hiện nhãn đã thay thế và link tới bản mới.
  Khung editor chỉ mở khi sửa. Điều khiển dùng được bằng bàn phím, không phụ thuộc hover.
- Full và compact dùng cùng composer và các widget ghi chú. Compact rộng 680px,
  chiều cao theo nội dung. Chuyển kích thước có animation 160ms; tôn trọng giảm
  chuyển động. Giữ draft, selection, focus và editor đang mở.
- Tính chiều cao bubble/ghi chú theo chữ để tránh vùng trống và cắt nội dung dài.
  Khi điều hướng hoặc sửa, cuộn đến đúng ghi chú/editor trong cùng viewport.
- Công cụ QA ẩn mặc định, mở bằng nút “Thử”. Badge “Bản xem · dữ liệu mẫu” luôn
  hiển thị. Bấm gửi giữ draft và thông báo chưa gửi tin nhắn thật.
- Phần “Cách Chuột làm” dùng renderer chung nhưng các bước ở bản xem là fixture
  có nhãn. Đây là thao tác/dự định mẫu để duyệt UX, không phải suy luận model đã đo.

## Kiểm chứng

Lệnh kiểm tra:

```bash
QT_QPA_PLATFORM=offscreen /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m pytest tests/test_turn_notes_preview.py tests/test_work_context_ui.py -q
```

**28 passed in 24.56s**: 19 kiểm tra bản xem và 9 kiểm tra work-context UI.
Log gốc: [ui_tests.txt](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_turn_notes_stage1_iteration3_20261012/ui_tests.txt).
Bao gồm các regression iteration 2, mở chi tiết bằng bàn phím, QA drawer,
composer draft/selection, animation thực trong Qt, reduced motion và chiều cao
ghi chú nhiều dòng. `git diff --check` qua.

11 ảnh được chụp từ widget Qt thật bằng `window.grab()` ở chế độ offscreen,
với reduced motion để ổn định ảnh. Đã đọc trực tiếp các ảnh full, compact,
editor, chi tiết và draft. Chưa kiểm tra cửa sổ native hoặc độ mượt trên màn
hình thật; kết quả kiểm tra phần mềm không chứng minh năng lực model.

| Ảnh | Trạng thái |
| --- | --- |
| `01_full_turns_overview.png` | Bố cục full, ba lượt và ghi chú liền phản hồi |
| `02_companion_clicked_highlight.png` | Chạm Chuột, emote và highlight ghi chú |
| `03_inline_editor_open.png` | Editor gọn mở tại dòng ghi chú |
| `04_stale_conflict_warning.png` | Cảnh báo phiên bản mô phỏng, giữ draft |
| `05_predecessor_link_updated.png` | Link bản cũ cập nhật sau chỉnh sửa fixture |
| `06_removed_tombstone_undo.png` | Bỏ/hoàn tác mô phỏng |
| `07_compact_hud_mode.png` | Compact theo nội dung |
| `08_compact_revealed_old_turn.png` | Lượt cũ được mở tại compact |
| `09_qa_dock_visible.png` | Drawer công cụ QA |
| `10_note_details_inline.png` | Nguồn và backlink mở ngay tại dòng |
| `11_compact_composer_draft.png` | Draft và selection sau chuyển compact |

## Phạm vi và bước tiếp theo

Giai đoạn 2 vẫn chờ duyệt: ID lượt ổn định, lịch sử bất biến, event đã commit,
kiểm tra revision thật và bỏ/hoàn tác trong WorkNotebook. Bản xem hiện mô phỏng
các thao tác trên fixture; chưa thay NotebookPane trong cửa sổ RAT chính.

Các thay đổi core NeSy trước đó được giữ lại và có audit riêng. Trong lượt này,
UUID cho phiên verifier được sửa riêng để tránh trùng evidence ID giữa các request;
76 regression qua, ghi tại
[audit core](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_symbolic_core_20261012/report.md).
Không gộp kết quả đó vào 28 kiểm tra UI hoặc diễn giải thành chất lượng AI.

Source trước chỉnh sửa được lưu trong `before/` và `before_sha256.json`.
`validation.json` ghi hash source sau chỉnh sửa, log và 11 ảnh. Các audit iteration
trước được giữ nguyên. Các thay đổi chưa commit sẵn có trong working tree được giữ lại.

Chạy bản xem tương tác:

```bash
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 scripts/preview_turn_notes.py
```

Xuất ảnh mới vào thư mục riêng:

```bash
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 scripts/preview_turn_notes.py --save-screenshots /tmp/rat-turn-notes-preview
```
