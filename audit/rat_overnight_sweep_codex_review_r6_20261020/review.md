# Independent review r6 — repair r5, 2026-10-20

**319/319 pass độc lập; E1 đóng trên các ca đã kiểm, E2/E3 chưa đóng hết.**
Tám probe bổ sung có **4 fail / 4 pass**, tập trung vào hai finding P2 dưới đây.
Không có P1 mới hoặc lỗi UI mới trong phạm vi kiểm tra hiện tại.

Đã đọc handoff/diff và dùng fake artifacts mới do reviewer tạo, không chỉ đọc
summary bên sửa. Đủ 51 file source khớp bàn giao. Repair chỉ đổi hai file
production; reviewer không sửa production hay tests cũ.

**Phạm vi snapshot:** ngay sau bộ 319 hoàn tất, hash check vẫn khớp source đầu
lượt review. Sau đó `rat/ui/omnibar.py` được sửa từ bên ngoài (mtime 00:27:06 UTC,
sau regression log 00:24:51 UTC). Giữ nguyên thay đổi đó; kết quả 319 dưới đây
áp dụng cho snapshot đã kiểm, không nghiệm thu thay đổi UI phát sinh sau này.
Hai file của repair đang review không đổi. Diff/copy riêng được giữ tại
`external_omnibar_change.patch`, `external_changes/`, `external_change_observation.json`.

## F1 — [P2 / E2] Đường dẫn vẫn được dùng thay provenance đã xác minh

Vị trí: `scripts/run_native_performance_session.py:381–386`.

Đã bỏ heuristic timing/token count, và ledger fake r3 nguyên gốc nay được giữ
unknown. Tuy nhiên, classifier thay bằng hai heuristic mới:

- `model_path` chứa `qwen3.5` hoặc `mlx-community` thì nhận real;
- `document_path` chứa `rat_native_perf_f9mhsshs` thì nhận real.

Đường dẫn model mô tả checkpoint cấu hình, không xác nhận backend thực thi.
Đường dẫn tài liệu mô tả input, không xác nhận request đến từ phiên inference
đã review. Không có đối chiếu hash/identity của ledger chuẩn tại hai nhánh này.

Đã kiểm bằng **fixture tổng hợp**, xây từ record fake r3 và ghi rõ provenance
trong `same_document_fixture.json`. Chỉ đổi trường `document_path` sang tài liệu
của phiên 12 real calls; một fixture khác thêm model path có tên checkpoint.
Cả hai bị classifier gọi là real. Đây không phải raw run mới hoặc bằng chứng
ledger gốc bị thay; nó kiểm xem classifier có phân biệt nguồn thực thi với
metadata của input/model hay không.

Fixture cùng tài liệu còn được replay qua CLI thật với `--fake-backend` và
budget 1 đã hết: 0 request mới, ledger không đổi, nhưng summary ghi
`historical_ledger_totals.real_records: 1` và
`budget_halt_existing_real_history`. Explicit-fake và legacy-unknown controls
đều pass. Có ba failing probes cho cùng finding: hai classifier fixtures và
một replay end-to-end.

Cần giữ unknown khi thiếu backend provenance; để nhận diện legacy 12 calls đã
review, dùng migration/sidecar hoặc mapping liên kết artifact hash đã xác minh,
không chỉ substring đường dẫn. Unknown vẫn tính vào budget attempts. Giữ nguyên
ledger gốc và ghi mapping riêng nếu cần.

Bằng chứng: `same_document_fixture.json`, `same_document_legacy_fake/`,
`same_document_legacy_fake.txt`, `session_commands.json`,
`test_legacy_identity_and_real_history.py`, raw JUnit/log tương ứng.

## F2 — [P2 / E3] Nhánh real vẫn đếm lịch sử thành calls của process hiện tại

Vị trí: `scripts/run_native_performance_session.py:431`, liên quan 434–437.

Nhánh fake đã dùng `new_fake_executed`, halt status đúng và warm=null. Nhánh
real lại giữ fallback `else len(ledger_real_records)` khi lượt hiện tại không
dispatch. Khi có 12 record real cũ và `current_run_dispatched=[]`, reporting
block hiện tại tạo ra:

| Trường | Output |
| --- | --- |
| Requests mới | 0 |
| `real_calls_count` / `real_model_calls_executed` | **12** |
| `scope_status` | `backend_inference_verified_12_calls` |
| `all_12_requests_succeeded` | true, lấy từ lịch sử |
| Records chọn cho warm aggregation | **12 record của phiên trước** |

Đã cô lập **đúng AST của classifier và reporting block trong source hiện tại**
với fixture explicit backend/session tags. Không khởi tạo real backend, không
load weights và không chạy CLI ở real mode. Vì vậy đây là kiểm phần tính báo
cáo offline, không phải một phiên real/native mới. Thêm control một request
real giả lập của lượt mới cho count=1; fake-history halt control cho count=0,
warm samples rỗng. Một failing probe, hai controls pass.

Control có 12 history + 1 current còn cho status `completed_13_calls` trong khi
executed=1: status và counter đang dùng hai scope khác nhau. Không cần thêm
finding riêng; cùng nguyên nhân trộn current run và history.

Cần áp dụng quy tắc current-run cho cả hai backend: executed lấy từ current
dispatches; halt thì 0 và warm=null. Giữ historical totals/verification trong
scope riêng. Không phủ nhận 12 inference calls đã review, cũng không gán lại
chúng cho process kiểm guard hoặc mượn latency/cache context của phiên trước.

Bằng chứng: `reporting_block_cases.json`, failing probe `real-history-halt`
trong `legacy_identity_and_real_history.txt/xml`. Đã dùng explicit tags để lỗi
đếm này không phụ thuộc F1 hoặc cách sửa legacy mapping sau này.

## Phần đã xác nhận đúng

| Hạng mục | Kết quả độc lập |
| --- | --- |
| Consolidated suite | **319 pass**, 0 fail/error/skip, 73.66s |
| E1 terminal fraction / scalar cases | **4/4 pass**, gồm marker và fallback |
| Toàn bộ probe r5 | **10/10 pass**, nằm trong 319 |
| Probe r4 / r3 | **7/7** và **13/13 pass**, nằm trong 319 |
| Mandatory research suite | **29/29 pass**, nằm trong 319, không cộng trùng |
| Parser / mocked backend / typed scoring | **68 pass / 2 skip** trong sandbox |
| Fresh fake session | 1 request, real=0, fake=1, warm=null |
| Fake-history halt | 0 request, fake=0, status đúng, warm=null |
| Legacy fake gốc | 0 request, unknown=1, status đúng, warm=null |
| 12-real-history replay ở fake mode | 0 request, fake=0, status đúng, warm=null |
| Startup / navigation / candidate viewport | Tiếp tục pass trong 319 |
| Tám probe bổ sung r6 | **4 pass / 4 fail**, hai finding trên |

Bàn giao lần này chỉ claim 44 parser/scoring tests, không claim toàn bộ 70
backend cases đã chạy thành công. Reviewer chạy đủ ba file và ghi đúng 68/2;
hai skip cần native MLX bfloat16. Không cộng skip thành pass.

Các phiên runner của reviewer tạo **1 fake request mới** và **4 guard replays
không dispatch**. Không có real generation mới. Real-mode reporting fixture
cũng không thực thi request nào; record “new-real-control” là dữ liệu tổng hợp.

Ledger 12 real calls original, bàn giao và replay giữ SHA256
`556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`.
50/51 source files giữ nguyên đến final audit; một thay đổi omnibar từ bên
ngoài được ghi rõ ở trên và không bị reviewer ghi đè. Năm manifest review cũ
được đối chiếu, tổng 735 entries không đổi. Xem `evidence_checks.json`,
`prior_artifact_integrity.json`, `source_start/end.json`.

Không chạy lại full 132-file sweep; 16 stale/contract expectation failures đã
ghi trước đó vẫn là backlog riêng. Không dùng bộ 319 xanh để claim toàn bộ
active suite xanh. Native GUI/cancel/changed-source/outside-excerpt vẫn chưa
được đo; offscreen/software tests không thay native acceptance hoặc measured
model quality. RAT và headless harness thuộc cùng hệ CoT/NCKH. Stage 0 không đổi.

## Artifacts và tái chạy

- `received_artifacts/`, `reviewed_source/`, `handoff_received.txt`: snapshot.
- `run_consolidated.py`, `command.json`, `regression.txt/xml`: đối chiếu đúng
  selectors 309 cũ + 10 r5; chỉ redirect r4 image/geometry output sang r6 để giữ
  evidence cũ, không thay assertion/input.
- `parser_command.json`, `parser_affected.txt/xml`: checks 68 pass / 2 skip.
- `session_commands.json`, năm session folders và raw logs: fake/guard replays.
- `probes_command.json`, `test_legacy_identity_and_real_history.py`,
  `legacy_identity_and_real_history.txt/xml`: thêm 8 probes và controls.
- `message_to_antigravity.md`: brief sửa tiếp, được chuẩn bị nhưng chưa gửi.

Reviewer chỉ ghi audit artifacts; không sửa production/tests cũ hoặc Git,
không đổi research freeze và không yêu cầu thêm budget model để kiểm hai lỗi này.
