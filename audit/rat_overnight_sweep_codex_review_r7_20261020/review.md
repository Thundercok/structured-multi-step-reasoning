# Independent review r7 — repair r6, 2026-10-20

**327/327 pass độc lập; F1/F2 đóng trên các ca kiểm tra cũ.** Bốn probe bổ sung
cho request thất bại có **2 fail / 2 pass**, xác nhận một finding P2 còn lại
trong nhánh báo cáo request mới. Không có P1 mới hoặc finding UI mới.

Đã đọc handoff/diff, đối chiếu đủ 51 file source với bàn giao và dùng fake
artifacts mới của reviewer. Repair chỉ đổi `scripts/run_native_performance_session.py`.
Hash cả 51 file vẫn khớp ngay sau test, gồm omnibar đã sửa ở chat khác và được
repair giữ nguyên. Reviewer không sửa production hay tests cũ.

## G1 — [P2] Request exception vẫn được mô tả là successful/verified inference

Vị trí: `scripts/run_native_performance_session.py:445–447`.

`new_real_executed` đếm mọi current-run completed attempt, gồm record có status
`exception:...` hoặc `error:...`. Đây là cách đếm attempts hợp lệ. Tuy nhiên,
status và note mới lại coi toàn bộ số đó là successful requests trước khi kiểm
gate thành công ở dòng 447.

Đã thực thi **đúng AST của classifier và reporting block** với synthetic
current-run records. Không khởi tạo backend, không load weights và không chạy
real-mode CLI:

| Fixture | `scope_status` | Note | Success gate |
| --- | --- | --- | --- |
| 12 attempts, 0 success, tất cả exception | **`backend_inference_verified_12_calls`** | **`12 successful backend requests`** | false |
| 1 attempt, 0 success, exception | `backend_inference_completed_1_calls` | **`1 successful backend requests`** | false |
| 12 attempts, 12 success | `backend_inference_verified_12_calls` | Đúng số successful | true |
| 1 attempt, 1 success | `backend_inference_completed_1_calls` | Đúng số successful | false, đúng vì chưa đủ 12 |

Hai failure fixtures fail; hai success controls pass. Gate đã tính đúng nhưng
status và mô tả trái với chính gate đó. Một phiên inference gặp lỗi có thể
được đọc thành bằng chứng 12 requests đã thành công, trong khi raw records
không có successful response nào. Đây là lỗi báo cáo ở nhánh vừa sửa, không
phải phát hiện sai dữ liệu của 12 calls lịch sử.

Cần tính current-run successful/failed outcomes trước khi chọn status và note;
chỉ ghi verified khi đúng điều kiện thành công. Khi có lỗi, mô tả attempts và
outcomes đúng, giữ counts/budget theo attempts. Không bỏ failed attempts khỏi
budget và không sửa raw ledger hay baseline cũ để khớp summary.

Bằng chứng: `test_failed_request_reporting.py`, `failed_request_cases.json`,
`failed_request_reporting_command.json`, `failed_request_reporting.txt/xml`.
Fixture là dữ liệu tổng hợp để kiểm phần tính báo cáo; không phải một run model
mới và không chứng minh backend thật đã phát sinh lỗi trong lượt review này.

## Xác nhận F1/F2 và các phần giữ pass

| Hạng mục | Kết quả reviewer |
| --- | --- |
| Consolidated suite | **327 pass**, 0 fail/error/skip, 76.64s |
| Probe F1/F2 r6 | **8/8 pass**, nằm trong 327 |
| Probe r5 / r4 / r3 | **10/10**, **7/7**, **13/13 pass**, nằm trong 327 |
| Mandatory research suite | **29/29 pass**, subset của 327, không cộng trùng |
| Parser / mocked backend / typed scoring | **68 pass / 2 skip**, sandbox |
| G1 failure/success probes mới | **2 fail / 2 pass** |
| Fresh fake | 1 request mới, real=0, fake=1, warm=null |
| Fake-history halt | 0 request mới, counts=0, warm=null, đúng status |
| Real-history replay ở fake mode | 0 request mới, counts=0, warm=null, lịch sử real=12 |
| Legacy fake / same-document fake fixture | 0 request mới, historical real=0, unknown=1 |
| Real-mode reporting fixture cũ | Current=0 -> real count=0, guard status đúng, không mượn warm lịch sử |
| Startup / navigation / candidate viewport | Tiếp tục pass trong bộ 327 |

**F1:** đã bỏ path-substring heuristic. Whitelist `(call_index,timestamp_utc)`
khớp đúng 12 identities trong ledger gốc đã review, hash
`556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`.
12 genuine records đều được nhận real, fake/path counterexamples giữ unknown
hoặc explicit fake. Xem `legacy_identity_catalogue.json`. Đây là mapping nhận
diện legacy requests trong trusted-local-ledger scope; không phải chữ ký số
mật mã hoặc cơ chế chống sửa nội dung artifact. Không suy rộng tính bảo mật
từ tên `verified_real_signatures` hay wording trong handoff.

**F2:** current/history counters, zero-dispatch status và warm isolation đã đúng
trên các probe cũ ở cả fake lẫn real reporting branch. G1 tách riêng vì nó xét
**outcome của request mới bị lỗi**, trong khi các ca F2 cũ xét history/guard và
new-request success control. Không mở lại parser/UI hoặc phủ nhận phần sửa đã đúng.

Hai parser skips cần native MLX bfloat16; báo đúng skip, không cộng thành pass.
Bàn giao chỉ claim bộ parser/scoring 44 pass sau khi bộ backend đầy đủ không
chạy thành công; reviewer đã kiểm đủ ba file và ghi kết quả 68/2 riêng.

## Integrity, scope và giới hạn

Các phiên runner mới chỉ tạo **1 fake request** và **4 guard replays không
dispatch**; **0 real-model requests mới**. Synthetic reporting fixtures cũng
không thực thi inference. Mọi seeded replay ledger giữ nguyên byte. Ledger real
original, bàn giao và reviewer copy đều giữ hash nêu trên. Sáu manifest review
cũ, tổng **860 entries**, không đổi. Xem `session_checks.json`,
`prior_artifact_integrity.json`, `evidence_checks.json`, `source_start/end.json`
và `source_after_validation.json`.

Không chạy lại full 132-file sweep. 16 stale/contract expectation failures đã
ghi trước đó vẫn là backlog riêng; bộ 327 xanh không chứng minh toàn bộ active
suite xanh. Native GUI/cancel/changed-source/outside-excerpt vẫn chưa đo, không
được thay bằng offscreen tests. Software tests không xác nhận measured model
quality. RAT và harness là các vai trò của cùng hệ CoT/NCKH; Stage 0 giữ nguyên.

## Artifacts

- `received_artifacts/`, `reviewed_source/`, `handoff_received.txt`: snapshot.
- `run_consolidated.py`, `command.json`, `regression.txt/xml`: đối chiếu đúng
  selectors 319 cũ + 8 r6; chỉ redirect output ảnh/geometry r4 sang r7, không
  thay assertions hoặc ghi đè review cũ.
- `parser_affected_command.json`, `parser_affected.txt/xml`: 68 pass / 2 skip.
- `session_commands.json`, `session_checks.json`, năm session folders và raw
  logs: fresh fake và bốn exhausted-budget replays.
- `test_failed_request_reporting.py`, `failed_request_cases.json`, raw log/XML:
  một finding G1, hai failure fixtures và hai success controls.
- `message_to_antigravity.md`: brief sửa G1, đã chuẩn bị nhưng chưa gửi.

Reviewer chỉ thêm audit artifacts; không sửa production/tests cũ, không đổi
Git hoặc research freeze, không thêm ngân sách và không gọi model thật.
