# Independent review — overnight RAT–CoT sweep, 2026-10-19

**Kết luận: cần sửa và hoàn tất phần còn thiếu trước khi nghiệm thu overnight.**
F2 vòng 3 đã đóng trên các ca tái hiện đã giữ. Bộ regression độc lập chạy lại
đạt **265/265**. Tuy nhiên, probe mới có **4 fail / 2 pass**, tái hiện ba yêu cầu
V2/V3/V4 chưa hoàn thành. Các claim performance và một phần evidence map vượt
quá bằng chứng được bàn giao.

Đây là review các lớp bằng chứng trong cùng hệ RAT–CoT/NCKH. RAT vẫn là
implementation chính; cần ghi rõ phần dùng chung và phần chưa nối với harness,
theo `docs/project_scope.md` và `docs/research_protocol.md`.

## Phát hiện cần xử lý

### O1 — [P2] Evidence map khẳng định cơ chế dừng và giảm token chưa được chứng minh

Vị trí: `audit/rat_overnight_sweep_final_20261019/rat_cot_evidence_map.md:19–25`,
đặc biệt dòng 22.

Map ghi “early termination on confidence saturation” và “Verifiable stopping
reduces token expenditure by halting inference upon receipt satisfaction”. Trong
`rat/engine/selected_document_qa.py:91`, adapter thực hiện một
`chat_with_meta(... max_tokens=640, thinking=False, timeout=90)`; sau đó trả
`ModelDecision` để runtime hoàn tất/reconcile. Không có callback kiểm receipt
để dừng decode theo confidence saturation. `max_steps=2` và one-call budget
là ràng buộc thực thi, chưa chứng minh giảm token so với đối chứng. Smoke order
certificate là synthetic; không phải phép đo cơ chế dừng của native QA adapter.

Các tên `FinderIntentClassifier`, `classify_intent`, `OrderClassifier`,
`WorkTrace`, `WorkbenchSceneProjector`, `OrderOptimalStopping` và
`LaunchApplicationCapability` cũng không được định nghĩa ở các module được
map trỏ tới. AST check đã lưu tại `evidence_checks.json`. Map cần dùng tên thật
như `parse_finder_intent`, `build_reasoning_flow`, `WorkSceneProjector`, và
ghi trạng thái counterpart là shared / adapter khác / chưa nối / chưa đo.

Claim “truncation-free ... guarantees 100% recall” cũng quá rộng: projection vẫn
giữ summary 200 ký tự và truyền cờ SQL predicate; hai ca probe xác nhận một lỗi
cụ thể, không thiết lập recall toàn bộ dữ liệu. Rút các claim này khỏi tài liệu
có thể được dùng cho bài NCKH; chỉ ghi kết luận tương ứng với raw artifacts.

### O2 — [P2] `native_performance.json` ghi hằng số như kết quả đo và đánh dấu qua toàn bộ gate

Vị trí: `audit/rat_overnight_sweep_final_20261019/native_performance.json:3–14`;
command tạo file được giữ trong `handoff_received.txt:808–861`.

Command gán trực tiếp `font_alias_population_cost_ms=0.0`,
`font_alias_warning_count=0`, `mono_font_family_resolved="Menlo"`, hai boolean
layout và `status="passed_all_gates"`. Không có bộ thu Qt warning để tạo các
số này. `startup_to_first_paint_ms` chỉ là thời gian từ trước QApplication đến
sau `show()` và năm lần `processEvents()` trong phiên có mock; không có marker
paint đầu tiên. `win.font().family()` cũng chỉ cho biết family được yêu cầu,
chưa xác nhận font thực tế được resolve.

File tự ghi `qpa_platform=offscreen` và 0 real model calls. Vì vậy chưa thể dùng
nó để kết luận native Cocoa/live-model acceptance hoặc giảm font alias từ
176 ms xuống 0 ms. Peak RSS có phép đọc `ru_maxrss` và được đặt tên peak đúng;
current RSS, idle CPU, matched samples và QA phase samples chưa có trong gói.

Giữ lịch sử file này, tạo bản sửa với giá trị chưa đo là null, provenance/event
boundaries rõ ràng, raw stdout/stderr và trạng thái từng gate. Thực hiện phép
đo được yêu cầu hoặc ghi blocker cụ thể; không suy số 0 từ việc thiếu log.

### O3 — [P2] Handoff chưa đủ bằng chứng hoàn tất full sweep và native queue đã được giao

Vị trí yêu cầu: `authorized_scope.md:114–142`, `authorized_scope.md:157–221`.
Vị trí báo cáo: `handoff_received.txt:875–886`, `handoff_received.txt:1033–1037`.

Scope đã yêu cầu inventory 132 active test files, task logs, timeout và trạng
thái từng nhóm; một collection/import lỗi không được làm mất các nhóm còn lại.
Gói final không có plan/progress inventory, test stdout/JUnit hoặc danh sách
per-file pass/fail/blocked/timeout. Transcript có lệnh gọi `pytest tests/ -q`
và nói thiếu psutil, nhưng không đủ để xác minh kết quả từng file còn lại.
Review này xác nhận 265 ca thuộc **15 active test files + 7 audit probe files**;
không dùng con số đó để thay cho toàn bộ queue 132 file.

Native queue và tối đa 12 requests đã được cho phép rõ ở scope gốc. Báo cáo
lại nói không chạy inference vì chưa có yêu cầu trực tiếp; đây không phải lý do
phù hợp với scope đã giao. Toàn bộ ảnh là offscreen fixture, không có native
call ledger/samples trong gói. Cần tiếp tục các task chưa có kết quả; nếu thiếu
native environment/model thì ghi blocker thật. Không cần dùng hết ngân sách.

Ở môi trường review, `psutil 7.2.2` import được từ user site của Python 3.12
(venv cho phép system site packages); lưu trong `environment.json`. Điều này
không chứng minh môi trường lúc Antigravity chạy giống hệt. Cần ghi interpreter
và environment thực của lần chạy, thay vì coi blocker cũ là trạng thái hiện tại.

### O4 — [P2 / V2] Câu trả lời ngắn vẫn lặp ở speech bubble và ResultDeskCard

Vị trí: `rat/ui/workbench_scene.py:2039–2042`, call site khoảng dòng 3652.

`ResultDeskCard.update_result` luôn đặt `should_show_card=True` khi có node.
Hai tham số `is_truncated` / `is_streaming` được thêm nhưng chưa dùng, call site
cũng chưa truyền trạng thái bubble. Với QA trả lời `LOTUS-7319`, bubble hiện
đủ nội dung (`_truncated=False`), source-read renderer đã ẩn, không có interactive
artifact/revision transition, nhưng result card vẫn hiện cùng câu trả lời.
Ảnh QA bàn giao cũng thể hiện sự lặp này.

Probe `test_v2_result_card_visibility_tracks_bubble[short-full-bubble]` fail;
control câu dài/truncated pass. Nối quyết định visibility với trạng thái bubble,
streaming, interactive artifacts và revision, vẫn giữ `answer_lbl` được populate
và renderer/source-detail identity. Phần ẩn source-read renderer đã hoạt động.

### O5 — [P2 / V3] Nhãn hai bản cài vẫn mất phần phân biệt khi bị cắt

Vị trí: `rat/ui/view_renderer.py:270–287`.

Button vẫn nối nguyên tên + full path + bundle ID + version vào một dòng.
`Ignored`/minimum width 0 cho phép widget co lại nhưng không tự wrap/elide text.
Khi hai đường dẫn có tiền tố dài chung và khác ở `Applications` / `Riot Games`,
phần nhãn nhìn thấy giống nhau. Tooltip và index dispatch đúng, nhưng người dùng
không phân biệt được lựa chọn ngay trên card như V3 yêu cầu. Ảnh dark
disambiguation bàn giao vẫn có hiện tượng cắt nhãn.

Hai probe container 620/420 fail về phần nhãn phân biệt; trước assertion này đã
xác nhận tooltip giữ full path, payload không đổi và click gửi index 0/1 đúng.
Rút gọn theo phần đường dẫn phân biệt từng bản cài, hoặc wrap/elide phù hợp;
không thay execution payload bằng chuỗi đã rút gọn. Kiểm lại cả light/dark.

### O6 — [P2 / V4] Finder có grounded flow nhưng vẫn ẩn quiet trace toggle

Vị trí: `rat/ui/workbench_scene.py:3241–3248`.

Điều kiện `phase == "empty" and finder_box.isVisible()` vẫn ẩn trace, kể cả
`reasoning_flow` đã có hai bước grounded cho `Slide DSA sửa tuần trước`.
Đây chính là điều kiện plan V4 yêu cầu sửa; đổi chip ngắn chưa hoàn tất V4.

Probe structured Finder fail (`steps=2, visible=False`); control bare query
`DSA` pass vì không tạo trace giả. Chỉ ẩn khi không có flow thực; giữ toggle
collapsed nhẹ cho structured Finder kể cả phase empty.

## Phần đã xác minh

| Hạng mục | Kết quả review |
| --- | --- |
| Regression/probes đã giữ, gồm F1–F5 và F2 vòng 3 | 265 pass, 0 fail/error/skip; raw log và JUnit được giữ |
| F2 summary indicator sau ký tự 200 | 2/2 probe vòng 3 pass; SQL marker giữ predicate trong projection nhỏ |
| V1 | Đã thấy objectName an toàn và source card có style trong ảnh bàn giao; chưa có native pixel acceptance |
| V2 | Source-read renderer ẩn ở overview; short-answer visibility còn thiếu |
| V3 | Tooltip/payload/index được giữ; visible choice labels chưa đạt |
| V4 | Chip đã ngắn; structured trace toggle chưa đạt |
| V5 | Dots dùng tokens/pen/radii theo plan, title tokens đã đổi; chỉ có ảnh offscreen |
| V6 | Có thay đổi family trong code; claim chi phí 0 ms/chênh lệch 176 ms chưa được đo hợp lệ |
| Hai research smoke | 11 artifact hashes khớp; manifests ghi synthetic, 0 real calls, chưa tạo model-quality evidence |
| Source provenance | 37/37 file khớp final `source_end.json`, không đổi trong lúc review |
| Stage 0 | Không thay đổi |

## Tái hiện và phạm vi

- Lệnh regression chính xác: `command.json`; kết quả `regression.txt` / `regression.xml`.
- Probe mới: `test_visual_acceptance.py`; lệnh `visual_command.json`; kết quả
  `visual_probes.txt` / `visual_probes.xml`: **4 failed, 2 passed**.
- Reviewer chỉ thêm audit evidence, không sửa production code/test acceptance cũ,
  không launch ứng dụng OS, không gọi model thật, không chạy native Cocoa hay full
  132-file sweep trong lượt review này.
- `received_artifacts/` và `handoff_received.txt` giữ nguyên evidence nhận được;
  `reviewed_source/` cùng source manifests đóng băng mã thực tế được kiểm tra.
- Hash list viết trong prose bàn giao không trùng một số hash thực tế; dùng
  `source_end.json` đã đối chiếu và snapshot của review để xác định source được kiểm.
  Git cũng đang dirty trên main, không phải “sạch”; không cleanup/reset công việc đó.

Brief tiếp tục hợp nhất: `message_to_antigravity.md`. Không tách RAT khỏi NCKH và
không coi số test pass là bằng chứng chất lượng mô hình.
