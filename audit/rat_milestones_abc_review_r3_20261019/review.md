# Xác minh độc lập bản sửa F1–F5 — vòng 3

Ngày 2026-10-19, Asia/Ho_Chi_Minh. **263 tests pass; còn một ca P2 thuộc F2.**

Đã chạy lại nguyên bộ 263 tests của bàn giao, gồm 245 regression và 18 probe
hai vòng review. Cả 7 probe F1–F5 vòng 2 đều qua. Audit/probe cũ giữ nguyên hash;
source không đổi giữa start/end của lần xác minh. Qt offscreen, model/launcher
mock; không có generation hoặc app launch thật.

## F2 — [P2] Predicate slide bị mất khi projection cắt summary

Vị trí: `rat/crawler/db.py:110-121` (UDF dùng summary đầy đủ), phần projection
`substr(coalesce(d.summary, ''), 1, 200)` trong `search_metadata`, và
`rat/engine/progressive_search.py:241-243` (lọc lại projection bằng Python).

Sửa UDF đã giải quyết đúng ca thư mục tổ tiên chiếm LIMIT. Tuy nhiên, SQL gọi
`is_slide_row()` với toàn bộ `d.summary`, trong khi hàng trả về chỉ còn 200 ký
tự summary. Bước `SearchFilters.accepts()` sau đó kiểm lại hàng đã mất thông tin.

Fixture trung tính `books/DSA.pdf`, content `DSA trees`, summary 306 ký tự,
chứa từ `slide` bắt đầu tại vị trí 301:

| Kiểm tra | Kết quả |
| --- | --- |
| `is_slide_row()` trên hàng đầy đủ | true |
| SQL candidates cho `DSA`, `slide_rule=True` | 1 |
| Summary trong projection | 200 ký tự |
| `is_slide_row()` trên projection | false |
| `ProgressiveSearch.initial('slide DSA')` | 0 hits |

Tệp được chính rule chung nhận là slide và SQL trả về, rồi bị loại ở tầng kế
tiếp. Cần giữ bằng chứng predicate đã đạt qua projection hoặc thống nhất phạm
vi dữ liệu của predicate trước LIMIT và hậu kiểm. Không trả full content lên
fast lane và không thêm model call. Nếu nhiều hàng bị loại, việc overfetch
không bảo đảm lấy được đủ kết quả hợp lệ.

`test_slide_summary_projection.py` chứa hai ca dùng cùng fixture setup:
short-summary control **PASS**, indicator sau 200 **FAIL**. Không có assertion
wall-time. Log và XML được lưu nguyên vẹn.

## Kết luận theo finding

| Finding vòng 2 | Kết luận trên source đã kiểm tra |
| --- | --- |
| F1 — error trace sau QA | Probe lỗi revalidation qua; state cũ được dọn trong nhánh lỗi. |
| F2 — rule slide trước LIMIT/projection | Probe tổ tiên qua; ca mất summary mới vẫn lỗi, chưa đóng đầy đủ. |
| F3 — cụm ngày tạo | Hai ca `đã tạo` và `created last week` qua; dùng chung danh sách động từ. |
| F4 — key → editor | Clock probe qua; các phép gán slot-duration ghi đè đã bỏ. |
| F5 — first usable hit | Hai ca same-query update và empty snapshot qua; có chốt theo query ID. |

Có thể xác nhận **các ca lỗi F1–F5 đã báo ở vòng 2 đều được sửa**. Chưa thể
khẳng định toàn bộ F1–F5 hoàn toàn sạch lỗi, vì F2 còn ca P2 được tái hiện trên.
Đây là software acceptance có phạm vi, không phải xác nhận native Cocoa/IME,
performance hay chất lượng mô hình.

## Handoff và visual plan

Đã đọc đầy đủ handoff sửa F1–F5 và
`/Users/thundercock2/.gemini/antigravity/brain/1543d8ec-005e-4709-a052-c585c9fd7d2a/visual_refinement_plan.md`,
đồng thời xem cả 5 specimen được dẫn. Các ảnh là Qt offscreen fixture replay;
chưa coi là ảnh acceptance trên source sau sửa mới.

Đã sửa overnight brief để **bao gồm V1–V6**, đặc biệt V2: tránh lặp source/answer
ở overview nhưng giữ renderer instance cho source_detail, answer_lbl vẫn được
populate, ResultDeskCard hiện khi streaming/truncated/interactive/revision.
Brief trước loại V1–V6 là bỏ sót plan và đã được đính chính.

Thứ tự bàn giao: đóng F2 projection → V1–V6 theo plan → full sweep/native/
performance → evidence chung RAT–CoT/NCKH. Xem
`docs/prompts/antigravity_overnight_rat_cot_sweep_20261019.md`.

## Artifacts và kết quả

- `regression.txt`, `regression.xml`, `command.json`: 263 passed, 37.45 s.
- `summary_projection_probe.json`: quan sát độc lập SQL/full/projection.
- `summary_projection.txt`, `summary_projection.xml`: 1 failed, 1 passed, 0.14 s.
- `test_slide_summary_projection.py`: probe để giữ khi sửa.
- `source_start.json`, `source_end.json`, `reviewed_source/`: snapshot/hash.
- `validation.json`, `artifact_manifest.json`: phạm vi và tổng hợp.

Chỉ thêm audit và sửa prompt bàn giao; không sửa production code, không commit
hoặc thao tác Git remote. Không thay research protocol hoặc Stage 0.
