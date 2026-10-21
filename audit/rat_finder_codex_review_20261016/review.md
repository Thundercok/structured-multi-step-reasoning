# Review độc lập finder/composer — 2026-10-16

Verdict: **Request changes**. Phạm vi là phần hành vi finder/composer và
regression liên quan, không làm lại thiết kế thought bubble.

Snapshot source khớp metadata Cocoa của revision thought bubble mới được người
dùng gửi. Source đầu/cuối review không đổi. Codex không sửa code sản phẩm.

## Findings

| Ưu tiên | Vị trí snapshot | Trigger và kết quả |
| --- | --- | --- |
| P1 | omnibar.py:2163 | Finder bật, compact, chưa có chat; gõ rồi xóa query → AttributeError do `has_meaningful_content` không tồn tại. Qt process exit 134 khi chưa cài hook chẩn đoán. |
| P1 | omnibar.py:2178 | Draft 2.001 ký tự → submit finder phát `invalid_finder_request` ra Qt slot; không được để giới hạn search phá composer. |
| P2 | omnibar.py:371, 404; chỗ install filter | Down trong composer return sớm; filter chưa cài cho finder/rows. Hai probe QTest.keyClick fail. |
| P2 | omnibar.py:2102; workbench_scene.py:2155 | Chọn hàng thứ hai rồi nhận snapshot cùng query → bị chọn lại hàng đầu. Selection giữa widget và window lệch nhau. |
| P2 | omnibar.py:2088 | Nhập trước khi catalog ready → không replay query khi init xong. |
| P2 | omnibar.py:2088 | catalog_ready sau shutdown vẫn tạo SearchCoordinator mới. |
| P2 | workbench_scene.py:1910–1957, 2080–2144 | Text row ép chiều rộng, action bị cắt; probe 620px/420px và ảnh Cocoa đều cho thấy overflow. |

Nhánh Cmd+Enter trong filter cũng đang dùng selection danh sách legacy thay
vì hit finder; cần sửa khi nối filter thật. Chưa tính là một lỗi người dùng
tách riêng vì nhánh finder hiện chưa được cài vào đường event.

## Kiểm chứng

- Regression gốc: **171 passed, 1 failed, 3 subtests passed**, 45.95s.
- Test scroll thất bại chạy riêng: **1 failed**, 4.46s, giá trị 7 so với 8.
  Chưa quy kết nguyên nhân cho một thay đổi cụ thể; khác biệt 1px không ngang
  mức nghiêm trọng với hai exception trong finder.
- Probe bổ sung cuối: **9 failed, 3 passed**, 11.34s. Test exceptions dùng
  custom sys.excepthook để báo lỗi thay vì làm pytest abort. Lần cô lập clear
  trước đó không có hook đã exit 134; không có JUnit hoàn chỉnh cho lần abort.
- Ba hợp đồng đã qua: bỏ snapshot stale tại GUI delivery; nút file gửi đúng
  path; Hỏi chọn nguồn và giữ draft, không tự tạo lượt chat.
- Fixture tổng hợp, mock model/actions, Qt offscreen. Không kiểm tra model
  thật, không thực thi mở file/app, không xác nhận native IME hay latency UI.
- Xem `source_start.json`, `source_end.json`, `reviewed_source/` và các XML.
  Các tệp được thêm trong audit không phải thay đổi code sản phẩm.

Handoff sửa cụ thể:
`docs/prompts/antigravity_finder_revision_after_codex_review_20261016.md`.
