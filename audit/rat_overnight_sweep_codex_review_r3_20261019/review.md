# Independent review — overnight repair follow-up, 2026-10-19

**Kết luận: startup và lỗi answer navigation đã đóng; còn 4 phát hiện P2 cần sửa.**
Không còn tái hiện P1 `NameError: padding` trên bộ kiểm tra hiện tại. Đã chạy độc
lập **289/289 pass** và thêm các checks sát thay đổi parser/backend: **68 pass,
2 skip**. Tuy nhiên, 13 probe mới có **8 fail / 5 pass**, thuộc bốn vấn đề bên
dưới. Chưa chốt toàn bộ R1–R6 resolved như validation bàn giao.

## C1 — [P2] Parser untyped mới bỏ mẫu số của kết luận dạng phân số

Vị trí: `reasoning/reasoning_strategies.py`, `_clean_cand` khoảng dòng 164.

Điều kiện mới cho phép rút số khi chuỗi có arithmetic operator và một
`EQUALS_RESULT`. Regex này chỉ bắt numeric literal ngay sau `=`, nên cắt
`Answer: 1 - 1/3 = 2/3` thành **2**, và `Answer: x = 3/4` thành **3**.
Đây là thay đổi giá trị toán học của câu trả lời, không chỉ đổi format.

Đối chiếu snapshot trước sửa: cả hai trường hợp còn giữ nguyên equation/RHS.
Kết luận số nguyên `... = 290` pass control. Hai fraction probes fail;
`parser_before_after.json` giữ đầu vào và kết quả trước/sau.

Cần giữ nguyên rational/expression hoặc chỉ rút khi toàn bộ vế kết luận hợp lệ
là một scalar được parser hỗ trợ. Không lấy một prefix số trong `2/3`. Giữ fix
placeholder và integer conclusion nhưng không nới typed research scoring, không
thay frozen labels/artifacts. Bộ typed scoring/backend đã chạy thêm vẫn pass;
review này chưa kết luận model-quality hoặc campaign results bị thay đổi.

## C2 — [P2] Fake run vẫn tạo claim real-model và warm latency được ghi cố định

Vị trí: `scripts/run_native_performance_session.py:366–397`.

Đã chạy đúng một request bằng **--fake-backend**, output ở `fake_session/`, không
load MLX weights và không gọi model thật. Artifact vẫn ghi:

- `real_model_calls_executed: 1`;
- status `backend_inference_verified_12_calls` dù chỉ có một fake completion;
- warm min/max/median và call 8 trùng số lịch sử, dù phiên này không có warm sample
  hay call 8 nào.

Nguyên nhân: count lấy mọi completion record, status/note và bốn warm statistics
được gán literal trong code. Model ID/type có ghi mock/offline nhưng các field
trên lại khẳng định điều ngược lại. Ba telemetry assertions fail độc lập trên
artifact thực do runner vừa tạo; không phải chỉ suy từ source.

Cần phân loại backend/session tại mỗi record, tách real và synthetic counts,
tính statistics từ samples thuộc đúng session và provenance. Không có warm
sample thì null/empty + n=0. Status/gates phụ thuộc plan và kết quả thực, không
gán verified_12 cho mọi phiên. Giữ historical ledger/telemetry nguyên vẹn; một
lần chạy guard hoặc fake không được viết đè measurement gốc bằng process mới.

R5 về tên CPU/prefix/suffix và native scope đã được đính chính tốt hơn. Tuy
nhiên, file telemetry bàn giao cũng đổi load time **27.542 → 1.258 s**, current
RSS **104.09 → 2221.72 MB**, peak **876.31 → 2503.25 MB**, trong khi calls vẫn
byte-identical với phiên cũ. Các số mới cần raw sample/session ID riêng hoặc
giải thích provenance từng field; chưa thể coi cả file là một phép đo của
phiên 12 calls cũ. Đổi tên metric không tự xác nhận nguồn của giá trị mới.

## C3 — [P2] Budget guard đếm start và complete thành hai attempts

Vị trí: `scripts/run_native_performance_session.py:82–85`.

Điều kiện `event == request_start or 'call_index' in rec` đếm cả hai event của
cùng request vì `request_complete` cũng có `call_index`. Một completed request
được tính **2** attempts; một legacy record cộng một completed pair được tính
**3** thay vì **2**. Sau interruption/resume, guard có thể từ chối phần ngân sách
còn lại và đánh số call sai. Đây là lỗi đếm dư, không phải bằng chứng đã vượt
ngân sách real-model trong lượt bàn giao.

Hai probe paired/mixed fail; controls legacy-only và pending-start pass. Cần đếm
unique request IDs/start checkpoints một lần, tương thích legacy records; một
start chưa complete vẫn tiêu một attempt. Giữ append-only checkpoint và kiểm
resume bằng fake backend. Không tự tăng `max-budget` để bù lỗi đếm.

## C4 — [P2 / V3] Hai bundle trong cùng thư mục vẫn nhận nhãn giống hệt

Vị trí: `rat/ui/view_renderer.py:272–291`.

Thuật toán chỉ so suffix của **parent directories**. Với hai bundle có cùng
CFBundleName/version nhưng filesystem names khác nhau, ví dụ:
`/Applications/League of Legends.app` và
`/Applications/League of Legends copy.app`, parent giống nhau ở mọi depth.
Fallback lại cho cả hai nhãn **Applications · League of Legends · v1.0**.

Probe fail với renamed copy cùng directory; control system/user Applications
pass. Tooltip giữ path đúng. Cần phân biệt từ full bundle identity, dùng basename
khi directory không đủ unique, rồi kiểm phần phân biệt còn đọc được trong viewport.
Giữ full tooltip/payload và index dispatch. Không cần mở ứng dụng để kiểm ca này.

## Kết quả đã xác minh và trạng thái review trước

| Hạng mục | Kết quả |
| --- | --- |
| R1 — tray startup NameError | Đóng trên 8 crash-shield tests; braces đã escape |
| R2 — answer biến mất khi back/refresh | Đóng trên 5 follow-up cases giữ nguyên; vẫn kiểm visible text |
| R3 — system/user Applications | Probe cũ pass; cùng directory khác bundle còn C4 |
| R4 — append-only pre-request checkpoint | Đã có; count/resume còn C3 |
| R5 — CPU/native/prefix measurement labels | Đã ghi scope/null đúng hơn; generation/provenance còn C2 |
| R6 — các tên class/callable cũ | Đã sửa ActionDispatcher/QtViewRenderer/capability; còn ghi sai method render_candidates ở prose |
| 12 historical real-call records | SHA256 byte-identical với gói trước; review không tạo thêm real calls |
| Parser/backend/typed scoring checks bổ sung | 68 pass / 2 skip do cần native MLX bfloat16 |
| Golden reranker stale feature count | Kiểm lại đủ 200 score/bounds/additive invariants với schema 25: pass |

Triage 19 fail đã tiến bộ: ba code bugs cũ hiện pass. Với golden test, review
thay **duy nhất** assertion feature count 20→25 trong AST in-memory; không sửa
test nguồn và giữ nguyên 200 score checks, xác nhận lý do stale ở ca đó.
Các nhóm khác chưa thành full-suite green: query-compound case score 100 vs 60
không chỉ là khác danh sách keyword; VGC còn đổi status/tolerance/exact-excerpt/
confidence contracts, không chỉ chuỗi English/Vietnamese. Cần ghi lý do đúng từng
case nếu đóng backlog, không nới verifier để khớp expectation cũ.

Native GUI/cancel/changed-source/outside-excerpt đã được ghi not-run/blocked thay
vì PASS: ghi nhận giới hạn này là đúng. Không yêu cầu thêm inference trong lượt
review. Stage 0 và research freeze giữ nguyên, RAT vẫn là implementation chính
của cùng hệ CoT/NCKH.

## Evidence và cách tái hiện

- `command.json`, `regression.txt/xml`: **289 pass**.
- `parser_command.json`, `parser_affected.txt/xml`, `parser_skips.json`:
  **68 pass, 2 skip**.
- `fake_command.json`, `fake_session.txt`, `fake_session/`: một synthetic request,
  0 real requests, phạm vi output riêng không ghi đè gói nhận được.
- `remaining_command.json`, `remaining_probes.txt/xml`: **6 fail / 4 pass**.
- `fraction_command.json`, `fraction_probes.txt/xml`: **2 fail / 1 pass**.
- `test_remaining_probes.py`: 13 cases. Khi sửa runner, tạo một fake request vào
  thư mục mới rồi đặt `RAT_REVIEW_FAKE_OUTPUT_DIR=/absolute/new/output` để probe
  đọc artifact mới. Không sửa captured failing data trong `fake_session/`.
- `source_start.json` khớp toàn bộ reported source_end, snapshots giữ code được
  kiểm; `received_artifacts/` giữ gói bàn giao. Các artifact review cũ khớp manifest.
- Reviewer chỉ thêm audit/probes, không sửa production/tests cũ, không launch
  OS app hoặc real model, không rerun full 132-file sweep và không thay Git state.

Brief sửa tiếp: `message_to_antigravity.md`.
