# RAT: Báo cáo Bản xem Giao diện Ghi chép theo Lượt (Giai đoạn 1)

Ngày: 2026-10-12, Asia/Saigon.
Trạng thái: Đã hoàn thành Giai đoạn 1 (Bản xem tương tác Qt bằng dữ liệu mẫu / Fixture).

---

## 1. Mục tiêu Giai đoạn 1 & Ranh giới Kỹ thuật

- **Mục tiêu**: Xây dựng bản xem UX tương tác bằng Qt để người dùng duyệt mật độ hiển thị, thứ tự các phần tử trong lượt chat, cơ chế liên kết bản cũ/bản mới, editor tại chỗ, và tương tác với Chuột bên trái.
- **Ranh giới minh bạch**: Toàn bộ dữ liệu hiển thị (câu hỏi, câu trả lời, ghi chú, đề xuất) là **kịch bản mẫu (test fixtures)**. Bản xem hoàn toàn không kết nối live model AI, không phải bằng chứng về năng lực suy luận của SLM/LLM thật.
- **Bảo toàn dự án**: Giữ nguyên toàn bộ working tree hiện tại, không thay đổi pipeline NCKH (`experiments.research_study`), không đổi model mặc định, và không tác động đến trạng thái Stage 0.

---

## 2. Các Quyết định Thiết kế Đã Triển khai trong Bản xem

1. **Ghi chú thuộc từng lượt chat (Turn-level Notes)**:
   - Thay vì nằm ở một `NotebookPane` riêng với thanh cuộn độc lập, ghi chép nằm ngay bên dưới phản hồi của Chuột và ngay trên khối “Cách Chuột làm” (Work Trace).
   - Thứ tự hiển thị chuẩn: `Câu người dùng` → `Phản hồi chính` → `Ghi chép của lượt` → `Cách Chuột làm (trace)`.
   - Nằm cùng trên bề mặt và thanh cuộn của chat stream (không có vùng cuộn con).

2. **Bảo tồn bản cũ & Dẫn tới bản mới khi bị thay thế**:
   - Ở Lượt 1: Ghi chú ban đầu là *"Có 20 phút · Chỉ ôn TCP"*.
   - Ở Lượt 2: Người dùng yêu cầu *"Đổi thành 30 phút nhé"*. Ghi chú mới ở Lượt 2 ghi rõ: *"Đã đổi: Có 30 phút · Chỉ ôn TCP (Congestion Control)"* kèm liên kết ngược: `Thay thế bản ở lượt 1 · [Xem bản cũ: Có 20 phút]`.
   - Ghi chú cũ ở Lượt 1 **giữ nguyên snapshot cũ** (gạch ngang nhẹ), hiển thị nhãn: `Bản cũ:` và liên kết dẫn tiếp: `Đã được thay thế ở lượt 2 → [Xem bản mới (20 → 30 phút)]`.
   - Khi bấm vào liên kết ở Lượt 1 hoặc Lượt 2, hệ thống cuộn mượt đến lượt tương ứng và phát hiệu ứng sáng vàng (amber glow) làm nổi bật ghi chú đích.

3. **Chuột đứng bên trái & Chuyển động vui vừa**:
   - Chuột (`LiveCompanion`) đứng cố định ở bên trái khung hội thoại.
   - Chuyển động nhịp nhàng, có kiểm soát (`math.sin` chu kỳ 2.4s thở nhẹ, lắc lư nhẹ khi idle, không giật lắc khung hình).
   - Khi chạm Chuột: Chuột emote vui (`happy`, nhảy nảy nhẹ, tim `♡`), đồng thời tự động cuộn đến và làm nổi bật (highlight glow) ghi chú active mới nhất trong cuộc trò chuyện.
   - Tôn trọng cờ `ratReduceMotion` khi tắt hoạt họa.

4. **Trình sửa tại chỗ (Inline Editor)**:
   - Nút `[Sửa]` mở ngay khung nhập tại dòng ghi chú với [Áp dụng] và [Hủy].
   - Hỗ trợ bàn phím đầy đủ: `Enter` xuống dòng, `⌘Enter` / `Ctrl+Enter` áp dụng, `Escape` hủy và trả lại focus.
   - Giữ nguyên bản nháp (draft) khi chuyển đổi chế độ hoặc gặp cảnh báo xung đột (stale warning).

5. **Chế độ Thu gọn (Compact HUD) vs Đầy đủ (Full ⌘L)**:
   - Chế độ Compact hiển thị lượt mới nhất.
   - Khi người dùng bấm liên kết xem ghi chú ở lượt cũ trong chế độ Compact, lượt cũ được mở cục bộ ngay trong cùng viewport kèm thanh điều hướng: `← Quay về lượt hiện tại`.

---

## 3. Danh sách Ảnh chụp Minh chứng (Audit Artifacts)

| Tệp ảnh | Mô tả trạng thái quan sát |
| --- | --- |
| `01_full_turns_overview.png` | Toàn cảnh 3 lượt hội thoại, Chuột bên trái, ghi chú inline, liên kết bản cũ ⇄ bản mới, đề xuất viền đứt, và dock kiểm tra. |
| `02_companion_clicked_highlight.png` | Chạm Chuột bên trái: Chuột emote tim `♡`, nhảy nhẹ, và highlight ghi chú active ở Lượt 2. |
| `03_inline_editor_open.png` | Mở inline editor tại Lượt 2 với phím tắt gợi ý, giữ nguyên văn bản cần sửa. |
| `04_stale_conflict_warning.png` | Mô phỏng xung đột phiên bản: cảnh báo lỗi tại chỗ nhưng bản nháp của người dùng được giữ nguyên. |
| `05_removed_tombstone_undo.png` | Bỏ ghi chú: hiển thị tombstone *"Không còn giữ trong ghi chép"* kèm nút `[Hoàn tác]`. |
| `06_compact_hud_mode.png` | Chế độ Compact HUD (⌘L): cửa sổ thu nhỏ, hiển thị lượt tương tác mới nhất cùng Chuột bên trái. |
| `07_compact_revealed_old_turn.png` | Điều hướng trong Compact: lượt cũ được mở cục bộ kèm nút `← Quay về lượt hiện tại`. |

---

## 4. Kết quả Kiểm thử Tự động

- `tests/test_turn_notes_preview.py`: **8/8 passed** (6.20s).
- `tests/test_work_context_ui.py`: **9/9 passed** (11.46s).
- `tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py`: **29/29 passed** (13.50s).
- **Tổng cộng**: 46 kiểm tra đều đạt 100%.

---

## 5. Lệnh Chạy Bản xem Tương tác Trực tiếp

Người dùng có thể khởi chạy và trực tiếp tương tác với cửa sổ Qt bằng lệnh:

```bash
python scripts/preview_turn_notes.py
```
Hoặc xuất lại bộ ảnh chụp màn hình kiểm tra bất kỳ lúc nào:
```bash
python scripts/preview_turn_notes.py --save-screenshots audit/rat_turn_notes_stage1_preview_20261012
```
