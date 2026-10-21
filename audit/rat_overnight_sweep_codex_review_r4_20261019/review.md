# Independent review — repair r3 follow-up, 2026-10-19

**Kết luận: 302/302 pass độc lập; C3/C4 đã đóng trên các ca kiểm tra, C1/C2 còn
hai nhánh chưa xử lý hết.** Không còn tái hiện startup crash hay answer-navigation
failure. Không có P1 mới trong lượt này.

Đã dùng một fake session mới của reviewer cho toàn bộ bộ 302, không chỉ đọc
artifact fake do bên sửa bàn giao. Checks parser/backend/typed scoring bổ sung:
**68 pass / 2 skip**, hai skip cần native MLX bfloat16. Bảy probe bổ sung có
**3 fail / 4 pass**, tập trung vào hai finding P2 dưới đây.

## D1 — [P2 / C1] Parser fallback vẫn làm đổi giá trị phân số khi không có Answer marker

Vị trí: `reasoning/reasoning_strategies.py:87–94`, caller tại dòng 215.

Nhánh marker đã giữ `Answer: x = 3/4` đúng. Nhưng fallback đi thẳng qua
`extract_conclusion_number` và không dùng logic bảo toàn rational vừa sửa:

| Input | Parsed | Giá trị đúng |
| --- | --- | --- |
| `Therefore x = 3/4` | `4` | `3/4` |
| `x = 3.25/4` | `3` | `13/16` |
| `Answer: x = 3/4` | `x = 3/4` | Control pass |
| `x = 3/4` | `x = 3/4` | Control pass |

Ở ca có “Therefore”, conclusion cue dẫn đến `extract_number(text)`, lấy mẫu số
cuối cùng làm kết luận. Với decimal numerator, `EQUALS_RESULT` có thể backtrack
và nhận dấu chấm thập phân làm delimiter, lấy prefix `3` từ `3.25/4`.

Đây là phần còn thiếu của C1 trên cùng API có fallback đã được hỗ trợ, không
phải yêu cầu một loại dữ liệu mới. Hai probe fail; hai controls pass. Không chỉ
cần từ chối một mẫu regex: marker và fallback phải dùng cùng quy tắc bảo toàn
toàn bộ giá trị kết luận, tránh lấy tử/mẫu hay prefix số ra khỏi expression.
Giữ nguyên typed research scoring và các negative/contradiction checks; chưa
có bằng chứng campaign/model-quality bị ảnh hưởng từ hai ca untyped này.

## D2 — [P2 / C2] Cờ CLI vẫn phân loại lại toàn bộ lịch sử ledger, thay vì provenance từng request/session

Vị trí: `scripts/run_native_performance_session.py:362–405`, nhất là 376–385.

Fresh fake session nay đúng: real=0, fake=1, warm=null, không còn verified_12
hardcode. Tuy nhiên, classification vẫn áp `args.fake_backend` cho **mọi record
trong ledger**, kể cả record lịch sử từ backend khác.

Tái hiện không gọi model: copy byte-identical ledger 12 real calls vào thư mục
review riêng, chạy `--fake-backend --max-budget 12` trên bản copy. Guard thấy
12/12 và **không dispatch request nào**, ledger không đổi byte nào, nhưng file
summary mới ghi `fake_model_calls_executed: 12` và status
`offline_fake_backend_completed_12_calls`. Đồng thời warm samples của phiên real
cũ xuất hiện dưới model ID mock của lượt không chạy request này.

Đã giữ command, stdout, ledger trước/sau và output tại
`locked_replay_command.json`, `locked_ledger_replay.txt`, `locked_ledger_replay/`.
Probe fresh-fake control pass; probe budget-halt-on-real-history fail. Không có
bằng chứng thêm real calls hoặc mất ledger; lỗi nằm ở cách diễn giải evidence.

Cần gắn backend/session provenance vào request records và tách current-run
attempts khỏi historical totals. Với legacy records, dùng nguồn/migration đã
xác nhận hoặc giữ unknown/reject mismatch; không suy backend từ cờ CLI mới.
Khi budget halt, không claim vừa thực thi lại số calls lịch sử, không viết đè
phép đo cũ bằng RSS/load của process kiểm guard. Warm aggregation chỉ dùng đúng
session/cache context; đổi process/document không tự trở thành warm sample.

## Phần đã xác nhận đóng và bằng chứng được giữ

| Hạng mục | Kết quả |
| --- | --- |
| C1 — các rational cases có marker trước đó | Pass; còn fallback D1 |
| C2 — fake session mới, bỏ warm constants | Pass; còn historical/mode D2 |
| C3 — unique attempt counting | 4 controls cũ pass; ledger 12/12 halt không phát sinh request |
| C4 — same-directory renamed copy | Pass; kiểm thêm renderer trong host 420px thật, hai label đủ chiều rộng |
| Startup / source-detail-back / refresh | Giữ pass trong consolidated 302 |
| Historical load/RSS/host CPU/font telemetry | Đã khôi phục khớp gói original; `restored_telemetry_checks.json` |
| Historical ledger 12 real calls | Byte-identical, SHA256 `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34` |
| Old review artifacts/probes | Không đổi theo manifests được đối chiếu |

Về geometry: diagnostic renderer top-level bị Qt layout co về 131px dù có yêu
cầu width 420/620; không dùng diagnostic đó làm viewport acceptance hay finding.
Đã kiểm lại bằng hosted renderer có assert host.width == renderer.width == 420:
content width 398px, hai text widths 229/261px, đều hiện đủ. Evidence:
`hosted_candidate_geometry.json`, `hosted_candidate_labels_420.png`.

Bàn giao ghi 70/70 parser pass. Trong môi trường chạy của reviewer, kết quả là
68 pass và 2 skip do yêu cầu native MLX bfloat16; không cộng hai skip thành pass.
Không suy ra lượt unsandboxed của bên sửa có cùng điều kiện môi trường.

16 stale/contract expectation failures từ full sweep vẫn là backlog riêng đã
được mô tả; bộ 302 xanh không phải tuyên bố toàn bộ active tests đã xanh. Native
GUI/cancel/changed-source/outside-excerpt vẫn chưa đo và cần giữ not-run/blocked.
Stage 0 không đổi; RAT và harness vẫn là các vai trò trong cùng hệ CoT/NCKH.

## Artifacts và phạm vi review

- `command.json`, `regression.txt/xml`: **302 pass, 0 fail/error/skip**.
- `parser_command.json`, `parser_affected.txt/xml`: **68 pass / 2 skip**.
- `fake_command.json`, `fake_session.txt`, `fake_session/`: một synthetic request.
- `locked_replay_command.json`, `locked_ledger_replay.txt`: exhausted-budget
  replay trên bản copy, **0 requests**; lịch sử giữ nguyên.
- `test_final_edges.py`, `final_edges_command.json`, `final_edges.txt/xml`:
  **3 fail / 4 pass**; hai parser fail và một provenance fail.
- `source_start/end.json`, `reviewed_source/`, `received_artifacts/`:
  snapshot mã và gói bàn giao được kiểm. Reviewer không sửa production hoặc tests cũ.
- Không real model generation, không OS app launch, không full 132-file rerun,
  không push/pull/reset/branch hoặc thay research freeze.

Brief tiếp tục: `message_to_antigravity.md`.
