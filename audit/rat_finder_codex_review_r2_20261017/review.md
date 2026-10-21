# Finder review vòng 2 — 2026-10-17

Verdict: **Request changes for keyboard behavior**. Hai exception P1 và các
case đã báo trong vòng trước đều qua probe; không báo lại chúng là lỗi còn mở.

## Kiểm chứng bản sửa

- Source hashes khớp toàn bộ metadata ảnh; các file review không đổi trong lượt.
- Regression: **185 passed, 3 subtests passed in 52.57s**, gồm 12 probe cũ,
  progressive search, tám suite UI trước, selected-document UI và active-detail.
- Ảnh finder 620px/420px hiện thấy đủ bốn action. Metadata ghi **offscreen**,
  không phải Cocoa; chưa xác nhận native IME hoặc model thật.
- Các file backend `rat/` trong validation startup MLX trước vẫn nguyên hash.

## Findings mới, P2

| Vị trí snapshot | Trigger thực tế trong probe | Kết quả |
| --- | --- | --- |
| omnibar.py:487–493 | Chọn beta, focus Hỏi, nhấn Return | `open_file_default(beta.path)` được gọi; không chọn document QA. Space qua. |
| omnibar.py:482–485 và focus row | Tab từ nút Hỏi alpha qua các action tới Hỏi beta, Cmd+Return | Reveal alpha thay vì beta; focus và selection không đồng bộ. |
| omnibar.py:376–393 | Shift+Down ở caret 2 của draft một dòng | Mất hành vi chọn text native: caret/anchor (2,2) thay vì (7,2). Đã kiểm tra composer có focus trước phím. |
| workbench_scene.py:2196–2222 | Focus Hỏi beta, nhận snapshot tiếp cùng query/id | Row bị tạo lại, focus action mất dù selection id được giữ. Semantic update được mô phỏng; provider thật chưa nối. |

Probe bổ sung: **4 failed, 2 passed in 3.67s**. Hai case qua: Space kích hoạt
Hỏi mà không mở file, Down thuần trong draft nhiều dòng giữ chỉnh sửa native.
Các hành động ngoài app được mock, không mở tệp/ứng dụng. Không sửa source sản
phẩm hoặc tests gốc; chỉ thêm probes và tài liệu audit/handoff.

Xem `regression.xml`, `keyboard.xml`, `source_start.json`, `source_end.json`,
`evidence_metadata.json` và `reviewed_source/`. Handoff:
`docs/prompts/antigravity_finder_keyboard_revision_20261017.md`.
