# RAT companion, ghi chép và luồng thực hiện

2026-10-12, Asia/Ho_Chi_Minh. Triển khai trong source. Không build lại app/DMG,
không push/pull/reset git. Giữ thay đổi khác có sẵn trong checkout.

## Kết quả

Theo lựa chọn người dùng ở từng giai đoạn, Chuột toàn thân lớn đứng bên trái
khung chat. Chuyển động vui vừa: thở/đung đưa nhẹ lúc rảnh, nhảy ngắn khi nhận
việc, prop sổ/bút khi ghi chép, emote khi chạm hoặc có phản hồi. Không tự nhảy
lúc rảnh, không di chuyển editor. Nhân vật và emote tĩnh vẫn hiện khi reduced
motion; timer dừng khi cửa sổ ẩn hoặc teardown. Dùng tài sản RAT hiện có.

Một notebook dùng chung cho công việc, có nguồn, quote, xác nhận và revision;
xem/thêm/sửa/xóa trong box. Runtime có `record_work_note` với quote validation
và sửa theo ID/revision, `select_work_results` chỉ chọn ID thật. Hỏi tiếp giữ
cùng result host/canvas/selection. Reset ngăn ghi muộn; Stop giữ ghi chép đã
nhận và chặn ghi thêm từ lượt cũ. Ghi chép chỉ trong phiên, chưa persist.

“Cách Chuột làm” có chuỗi ngắn và chi tiết mở tại chỗ: dự định có nhãn, thao
tác, dữ kiện, lỗi, thiếu đầu vào và dừng. Không đọc/hiển thị private `thought`,
raw completion hoặc model input. Đây là public plan/execution summary. Plan
và câu trả lời của model không xác nhận thực thi. Plan khởi đầu không được
khai đã hoàn thành công việc; không đưa annotation của plan vào notebook.

Thiết kế và giới hạn: [work context](../../docs/rat_companion_work_context.md),
[brief UI](../../docs/rat_ui_fluidity.md), [backlog](../../docs/rat_backlog.md).
RAT-AI-01/02/03 vẫn cần evidence; renderer vẫn là các thành phần đã đăng ký.

## Kiểm tra phần mềm và giao diện

| Kiểm tra | Kết quả | Log |
| --- | --- | --- |
| Runtime/context/provenance, conversation/model adapter, kernel, natal calculation/places | 110 passed | `headless_live_companion_final.txt` |
| Qt: companion, draft/focus/compact/full, notes, trace, continuation, worker/export, natal UI, mode shortcut from note editor | 107 passed, 3 subtests | `ui_verified_final.txt` |
| Kiểm tra riêng bố cục bên trái và export worker | 31 passed | `side_layout_checks.txt` |
| Research harness smoke có sẵn | 29 passed | `research_smoke.txt` |

Qt fixture tests kiểm tra contract/lifecycle, không đo năng lực AI. Preview
được tạo từ QWidget thật, quyết định hội thoại scripted và phép tính thực.
Ngày/giờ sinh là minh họa, không là dữ liệu cá nhân người dùng. Các ảnh
`compact_idle.png`, `compact_notes.png`, `compact_notes_trace.png`,
`full_notes_trace.png`, `compact_chart.png` do `preview.py` tái tạo.

Giữ log các lần lỗi trước: startup thiếu `_mascot_state` đã sửa; hai assertion
message order bị ảnh hưởng bởi reminder cuối đã sửa bằng prompt chung đầu
conversation; một lượt Qt trước bố cục cuối bị native segmentation fault khi
export trong worker. Ca export riêng và suite cuối đều pass; không khẳng định
đã xác định nguyên nhân native crash. Kiểm tra whitespace của các file task
pass. `git diff --check` toàn checkout còn báo blank line EOF trong file
research test có sẵn ngoài task này; không sửa file đó.

## Thử model thật: giới hạn vẫn còn

Ba câu phát triển đã lộ trong `live_smoke.py`, dữ liệu fixture riêng: ghi câu
20 phút/chỉ TCP, hỏi lại ghi chép, sửa 30 phút và tính 30*60. Không là unseen
benchmark, không có review độc lập, không kết luận về chất lượng nghiên cứu.
Không fallback sang intent if/else hoặc completion giả. Không đổi model mặc
định của app; 4B là override chỉ cho kiểm tra.

| Lượt cuối | Quan sát | Online wall time |
| --- | --- | --- |
| qwen2.5:1.5b, 3 câu | Chỉ plan rồi trả lời; không gọi ghi/sửa/tính. Notebook vẫn rỗng dù lời trả lời nói đang ghi/đã sửa. Cả 3 chưa đạt yêu cầu. | 43.4s / 32.4s / 34.7s |
| qwen3:4b-instruct, 3 câu riêng | Plan trả về; actor timeout 90s. Không có thao tác ghi/sửa/tính. Cả 3 chưa hoàn tất. | 165.5s / 154.8s / 159.0s |

Raw request/response, reported prompt/generated tokens và latency giữ trong
`live_v3/live_calls.jsonl`, `live_v3/live_smoke_results.json`, `live_4b/…`.
Token counts chỉ gồm calls trả được metadata; timeout không cho biết usage
thực. Không gọi đây là full inference cost hoặc so sánh model có kiểm soát.
Các attempts trước vẫn giữ ở root audit và `live_v2`. Attempt đưa annotation
plan vào ghi chép cho thấy diễn giải sai ràng buộc, nên final contract chỉ ghi
từ thao tác thật hoặc dữ liệu người dùng nhập.

## Native và research boundary

`native_launch.json` ghi đường source/log cửa sổ macOS chạy thật. Nạp bản cuối
bằng LaunchServices, không đổi cấu hình model. Kiểm tra native từng bước sẽ
được ghi trong `native_checks.json`; chỉ những thao tác đã xác nhận mới được
coi là verified. Công cụ có lúc bị chặn do Mac khóa; người dùng đã được hỏi
mở khóa. Không dùng ảnh Qt làm bằng chứng native.

Đã xác nhận native trên source cuối: Chuột bên trái, chạm mở ghi chép/emote,
thêm ghi chú minh họa, sửa 20→30 phút, ⌘L từ chính editor đổi full/compact mà
giữ draft/focus, Tab đưa focus tới Áp dụng và Space lưu, nhãn đổi thành
“Bạn sửa / xác nhận”. Giữ app chạy và ghi chú có nhãn “Ví dụ kiểm tra”. Mac
khóa lại khi thử thu pane sau kiểm tra; không coi lần thu đó là thành công.
Phím mode giờ áp dụng cho mọi editor thuộc box; không chặn phím trong app
hoặc dialog khác. Compile và task-relative whitespace checks pass.

Runtime/prompt của app thay đổi; pipeline `experiments.research_study`, fitting,
controller, train/calibration/test splits và Stage 0 không thay trong task.
Research tests là smoke phần mềm, không chứng minh model quality hoặc gate.

Baseline và thay đổi riêng của task: `baseline_sha256.json`, `before/`,
`changed_files.json`, `companion_changes.patch`. Audit trước
`rat_one_box_ui_20261012` giữ nguyên.
