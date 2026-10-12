# RAT: Báo cáo Tinh chỉnh Giao diện Ghi chép theo Lượt (Giai đoạn 1 - Iteration 2)

Ngày: 2026-10-12, Asia/Saigon.
Trạng thái: Đã hoàn thành Iteration 2 theo phản hồi thẩm định [review.md](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_turn_notes_stage1_codex_review_20261012/review.md).

---

## 1. Ranh giới Kỹ thuật & Bảo toàn Hệ thống

- **Dữ liệu mẫu (Test Fixture)**: Toàn bộ dữ liệu hiển thị là kịch bản kiểm thử cố định (`FIXTURE_TURNS`), không kết nối live model AI, không suy luận thực.
- **NCKH & Stage 0**: Không thay đổi pipeline `experiments.research_study`, không đổi model mặc định, không tác động đến Stage 0. 29/29 tests nghiên cứu NCKH đều chạy và đạt 100%.
- **Working Tree & Git**: Giữ nguyên toàn bộ các thay đổi chưa commit trước đó. Không push/pull/reset/force git.

---

## 2. Các Thay đổi Thiết kế Đã Triển khai theo Quyết định Chốt

1. **Ghi chú là dòng chữ nhẹ liền với phản hồi**:
   - Loại bỏ toàn bộ viền hộp và nền riêng của ghi chú thông thường.
   - Ghi chú hòa vào nền chat stream chung, nằm ngay dưới câu trả lời và phía trên khối *Cách Chuột làm* (`WorkTracePane`).
   - Khung viền và hộp nhập (`NoteEditor`) **chỉ xuất hiện tại chỗ khi bấm Sửa**.

2. **Bản cũ giữ nguyên nội dung & không gạch ngang**:
   - Chữ ghi chú ở bản cũ giữ nguyên trạng thái đọc được bình thường (loại bỏ `line-through`), gắn nhãn nhẹ `Đã thay thế:`.
   - Có nút dẫn tiến `[Xem bản mới (…)]` và nút hành động `[Sửa bản mới]`.

3. **Shell Preview chân thực & Compact HUD gọn gàng**:
   - Tích hợp ô nhập `ChatComposer` thật và nút `Gửi` ở đáy giao diện chat.
   - Kích thước Compact HUD được tinh chỉnh chuẩn xác (rộng 680px, cao 410px), ôm sát nội dung và không còn khoảng trống thừa.
   - Toàn bộ thanh cuộn ngang bị vô hiệu hóa hoàn toàn; nội dung dài được co/rút gọn bằng dấu ba chấm `…` tinh tế.
   - Dock kiểm thử QA được đưa vào drawer ẩn/hiện (`🛠 Công cụ thử nghiệm`), giữ cho bề mặt duyệt UX ban đầu hoàn toàn sạch sẽ.

4. **Chuột đứng bên trái & Lời thoại tự nhiên**:
   - Chuột (`LiveCompanion`) đứng cố định bên trái, thở nhẹ và chuyển động nhịp nhàng.
   - Khi bấm vào Chuột: Chuột phản ứng vui (`happy` emote, tim `♡`), cuộn đến và làm nổi bật (highlight glow) ghi chú active gần nhất.
   - Lời nhắc của Chuột hiển thị văn bản tự nhiên (ví dụ: `🐭 Chuột: 'Ghi chép đang dùng: “Có 30 phút · Chỉ ôn TCP…”'`), loại bỏ hoàn toàn các ID kỹ thuật nội bộ (như `note-tcp-time-v2`).

---

## 3. Khắc phục 4 Lỗi đã Tái hiện trong Review

| Lỗi đã nêu trong Review | Nguyên nhân gốc | Giải pháp đã triển khai & kiểm chứng |
| --- | --- | --- |
| **1. Chuyển compact làm editor đang sửa bị ẩn và mất focus** | Hàm `toggle_expanded` trước đó reset `_revealed_compact_turn = None` và chỉ hiện lượt cuối. | Kiểm tra xem lượt nào đang có editor mở (`row.editing == True`); nếu có, giữ nguyên lượt đó làm `_revealed_compact_turn`, bảo toàn visibility, text draft và khôi phục focus (`setFocus()`). Đã thêm test `test_compact_toggle_preserves_active_editor_and_focus`. |
| **2. “Sửa bản mới” chưa mở editor** | Nút trên note cũ chỉ emit navigate mà không kích hoạt chế độ edit của note mới. | Tách link `Xem bản mới` (chỉ điều hướng) và nút `Sửa bản mới` (emit `edit_replacement_requested`). Preview window điều hướng đến note mới và gọi ngay `row._start_edit()`, đưa focus vào ô soạn thảo. Đã thêm test `test_edit_replacement_opens_target_editor`. |
| **3. Link bản cũ không cập nhật sau khi sửa** | `_on_note_edit_saved` chỉ cập nhật note đích, chưa quét các note tiền nhiệm có `replaced_by_note_id`. | Thêm vòng lặp cập nhật `p_note.replaced_by_text = new_text` cho mọi note tiền nhiệm và gọi `set_notes` cập nhật lại UI lượt cũ. Link ở Lượt 1 tự động đổi thành bản mới nhất. Đã thêm test `test_predecessor_link_updates_when_successor_edited`. |
| **4. Highlight vẫn chạy khi bật giảm chuyển động (`ratReduceMotion=True`)** | `trigger_highlight` luôn chạy `QPropertyAnimation`. | Kiểm tra `surface_layout.motion_enabled()`. Khi tắt chuyển động, dừng animation, hiển thị tĩnh `_highlight_ratio = 0.8` và dùng timer xóa tĩnh sau 1.2s mà không chạy animation tween. Đã thêm test `test_reduced_motion_avoids_animation`. |

---

## 4. Kết quả Kiểm thử Tự động

- `tests/test_turn_notes_preview.py`: **12/12 passed** (8.93s).
- `tests/test_work_context_ui.py`: **9/9 passed** (18.70s).
- `tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py`: **29/29 passed** (11.75s).
- **Tổng cộng**: 50/50 tests đều đạt 100%.

---

## 5. Danh mục Ảnh chụp Thẩm định (Iteration 2 Artifacts)

Toàn bộ ảnh chụp màn hình được lưu trong thư mục riêng:
`audit/rat_turn_notes_stage1_iteration2_20261012/` (thư mục iteration 1 cũ vẫn được bảo toàn nguyên vẹn).

| Ảnh chụp | Nội dung quan sát |
| --- | --- |
| `01_full_turns_overview.png` | Toàn cảnh 3 lượt với dòng ghi chú nhẹ liền phản hồi, text cũ không gạch ngang, composer thật ở đáy, Chuột bên trái, không có scrollbar ngang. |
| `02_companion_clicked_highlight.png` | Bấm Chuột bên trái: Chuột emote tim `♡`, highlight ghi chú active ở Lượt 2, lời thoại tự nhiên không ID kỹ thuật. |
| `03_inline_editor_open.png` | Bấm `[Sửa]` ở Lượt 2: khung editor viền ấm mở ra tại chỗ kèm phím tắt gợi ý và nút `[Áp dụng]` / `[Hủy]`. |
| `04_stale_conflict_warning.png` | Cảnh báo xung đột phiên bản xuất hiện nhưng bản nháp người dùng vẫn được bảo toàn. |
| `05_predecessor_link_updated.png` | Sau khi sửa Lượt 2 thành *"45 phút · Ôn cả BGP"*, link dẫn ở Lượt 1 tự động cập nhật phản ánh bản mới nhất. |
| `06_removed_tombstone_undo.png` | Ghi chú bị bỏ hiển thị tombstone nhẹ kèm nút `[Hoàn tác]`. |
| `07_compact_hud_mode.png` | Chế độ Compact HUD (⌘L) kích thước gọn gàng (680x410px), hiển thị lượt active và composer. |
| `08_compact_revealed_old_turn.png` | Mở lượt cũ cục bộ trong Compact HUD kèm thanh điều hướng `← Quay về lượt hiện tại`. |
| `09_qa_dock_visible.png` | Khung công cụ thử nghiệm QA khi mở ra phục vụ thao tác kiểm tra. |

---

## 6. Khởi chạy Trực tiếp

Để chạy và tương tác trực tiếp:
```bash
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 scripts/preview_turn_notes.py
```
Để xuất lại toàn bộ ảnh chụp màn hình:
```bash
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 scripts/preview_turn_notes.py --save-screenshots audit/rat_turn_notes_stage1_iteration2_20261012
```
