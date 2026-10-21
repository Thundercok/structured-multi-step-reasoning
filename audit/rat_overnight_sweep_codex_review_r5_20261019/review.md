# Independent review r5 — repair r4, 2026-10-19

**Chưa nghiệm thu toàn bộ D1/D2.** Bộ hợp nhất **309/309 pass** khi chạy lại
độc lập, gồm 29 test NCKH bắt buộc và 7 probe r4. Tuy nhiên, 10 probe bổ sung
có **4 fail / 6 pass**, xác nhận ba finding P2 dưới đây. Không có P1 mới.

Đã đọc handoff, diff và đối chiếu snapshot: đúng hai file production được sửa
trong repair r4; 51 file source khớp bàn giao và không đổi trong lượt review.
Reviewer chỉ thêm audit artifacts, không sửa production hay tests cũ.

## E1 — [P2 / D1] Chọn scalar trung gian khi kết luận cuối là phân số

Vị trí: `reasoning/reasoning_strategies.py:168–170`.

`_clean_cand` tìm mọi scalar sau dấu `=` trên cả dòng và trả kết quả cuối cùng
match được **trước khi** kiểm RHS cuối có biểu thức hay không. Regex bỏ qua
`= 1/4`, nhưng vẫn nhận `= 4` trước đó:

| Input | Kết quả hiện tại | Kết luận đúng |
| --- | --- | --- |
| `Answer: 2 + 2 = 4; 1 / 4 = 1/4` | `4` | `1/4` |
| `Therefore 2 + 2 = 4; 1 / 4 = 1/4` | `4` | `1/4` |
| `Answer: x = 3/4` | Giữ `x = 3/4` | Control pass |
| `Answer: 2 + 2 = 4; 4 * 2 = 8` | `8` | Control pass |

Ca có marker là regression mới: snapshot trước repair còn giữ nguyên dòng
`2 + 2 = 4; 1 / 4 = 1/4`. Ca fallback đã sai từ trước và vẫn chưa hết. Bốn
ca D1 cũ đều pass, nên ghi nhận phần sửa đó đã đúng; không thể suy rộng thành
mọi rational conclusion đều được bảo toàn.

Cần chọn kết luận cuối trước, rồi kiểm scalar/expression trên chính kết luận
đó. Nếu chưa tính được phân thức, giữ nguyên biểu thức hoặc báo unresolved;
không thay bằng một scalar ở bước tính trước. Không đổi typed research scoring,
gold data hoặc frozen evaluation để làm test xanh. Chưa có bằng chứng measured
model-quality campaign bị ảnh hưởng từ các ca untyped này.

Bằng chứng: `parser_before_after.json`, hai parser failures trong
`provenance_and_conclusion.txt/xml`.

## E2 — [P2 / D2] Timing và token count của fake ledger bị dùng để xác nhận real inference

Vị trí: `scripts/run_native_performance_session.py:379–382`.

Classifier mới xem bất kỳ legacy record có timing khác 0 hoặc
`prompt_tokens >= 500` là real. Fake backend cũng sinh đủ những trường này.
Đã dùng **ledger fake có thật từ chính review r3**, kèm command
`--fake-backend --max-budget 1` và raw log; không dựng record giả để suy luận.
Record đó có prompt_tokens=2031, first_token_ms=0.531 và không có backend tag.
Classifier hiện tại trả `real`.

Tái hiện end-to-end: copy ledger fake cũ vào `legacy_fake_history_halt/`, chạy
fake CLI cap 1. Guard không dispatch, ledger không đổi byte nào, nhưng summary
ghi `budget_halt_existing_real_history` và khẳng định có
`1 historical real-model records`. Cờ fake không gây nhầm trực tiếp nữa; nguồn
nhầm mới là heuristic xác nhận legacy evidence.

Cần chỉ nhận real từ provenance đã xác minh. Legacy records không rõ nguồn
phải giữ unknown, hoặc dùng migration/sidecar liên kết nguồn và hash đã xác
minh. Giữ ledger 12 real calls gốc nguyên vẹn; đừng dùng độ dài prompt/timing
để chứng minh inference. Unknown records vẫn phải tính vào budget attempts,
không được bỏ qua để mở thêm ngân sách.

Bằng chứng: `legacy_fake_calls.jsonl`, `legacy_fake_command.json`,
`legacy_fake_session.txt`, `legacy_replay_command.json`,
`legacy_fake_history_halt.txt` và summary tương ứng. Một classifier probe fail;
explicit fake, explicit real và unknown controls pass.

## E3 — [P2 / D2] Budget halt trên lịch sử fake vẫn báo vừa chạy lại lượt cũ

Vị trí: `scripts/run_native_performance_session.py:406`.

Nhánh fallback của `fake_calls_count` dùng `len(ledger_fake_records)` khi lượt
hiện tại không dispatch. Lỗi vẫn xuất hiện ngay cả khi mỗi request đã có đầy
đủ `backend_type` và `session_id` mới.

| Phiên kiểm tra | Requests mới | Summary fake calls |
| --- | --- | --- |
| `fake_session`, thư mục mới, cap 1 | 1 fake | 1, đúng |
| `locked_ledger_replay`, bản copy 12 real calls, cap 12 | 0 | 0, D2 cũ pass |
| `fake_history_halt`, bản copy phiên fake mới, cap 1 | 0 | **1, sai** |

Ở dòng cuối, log ghi rõ `BUDGET GUARD HALT` và `No new requests will be
dispatched`; ledger byte-identical với phiên fake đầu. Summary lại ghi
`offline_fake_backend_completed_1_calls`. Vì vậy việc tách current-run khỏi
history mới chỉ xử lý trường hợp ledger real, chưa đúng với ledger fake.

Cần dùng số requests của lượt hiện tại cho trường `*_calls_executed`, giữ
historical totals ở trường riêng và dùng status halt cho lượt không dispatch.
Session ID mới phải có tác dụng phân biệt nguồn metrics, không chỉ được ghi
vào ledger. Không gán warm samples của process trước cho process kiểm guard.

Bằng chứng: `session_commands.json`, `fake_history_halt.txt`, hai folder fake,
và một failing replay probe; fresh fake control pass.

## Những phần đã xác nhận đúng

| Hạng mục | Kết quả độc lập |
| --- | --- |
| Consolidated suite | **309 pass**, 0 fail/error/skip, 45.02s |
| Mandatory research subset | **29 pass**, nằm trong 309; không cộng trùng |
| Bốn rational cases D1 cũ | **4/4 pass** |
| Replay 12 real calls theo D2 cũ | 0 requests, fake=0, warm=null, ledger không đổi |
| Unique-attempt budget counting C3 | Controls tiếp tục pass |
| Candidate labels C4 / viewport 420px | Hosted test tiếp tục pass |
| Startup, answer navigation / refresh | Tiếp tục pass trong bộ hợp nhất |
| Parser / mocked backend / typed scoring | **68 pass, 2 skip** trong sandbox |
| Probe bổ sung r5 | **6 pass, 4 fail**, ba findings nêu trên |

Hai skip đòi native MLX bfloat16. Bàn giao ghi 70/70 chạy unsandboxed; kết quả
reviewer khác điều kiện môi trường, không phải bằng chứng bác bỏ lần chạy đó.

Ledger original, ledger bàn giao và bản copy exhausted-budget đều có SHA256
`556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`.
Các manifest review cũ được đối chiếu: 82 + 353 + 96 + 98 entries, không đổi.
Xem `evidence_checks.json`, `prior_artifact_integrity.json`, `source_start/end.json`.

Một fake request mới được chạy; ba phiên guard replay không dispatch, **0 real
model requests mới**. Không chạy lại full 132-file sweep; 16 stale/contract
failures đã ghi ở vòng trước vẫn là backlog riêng, bộ 309 không chứng minh toàn
bộ active tests xanh. Native GUI/cancel/changed-source/outside-excerpt vẫn
not-run/blocked; không dùng offscreen tests thay phép đo native. Stage 0 giữ
nguyên. RAT là implementation của cùng hệ CoT/NCKH với harness đánh giá.

## Tái chạy và bàn giao

- `run_consolidated.py`, `command.json`, `regression.txt/xml`: đúng selectors
  của bộ 309; redirect riêng output ảnh/geometry của module r4 sang folder r5,
  không thay assertion/input hay ghi đè evidence cũ.
- `parser_command.json`, `parser_affected.txt/xml`: 68 pass / 2 skip.
- `test_provenance_and_conclusion.py`, `probes_command.json`,
  `provenance_and_conclusion.txt/xml`: các ca fail và controls.
- `received_artifacts/`, `reviewed_source/`: snapshot bàn giao và 51 file source.
- `message_to_antigravity.md`: brief tiếp tục sửa, chưa tự gửi.

Các finding đều thuộc hai file sửa mới. Không phát hiện thêm lỗi UI trong phạm
vi bộ kiểm tra hiện tại; không sửa production, test cũ, research freeze hay Git.
