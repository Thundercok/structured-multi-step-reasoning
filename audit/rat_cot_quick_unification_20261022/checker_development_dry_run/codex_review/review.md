# Review độc lập checker development dry-run — 2026-10-23

**Request changes cho gói checker dry-run.** Bridge R1/R2/R3 trước đó vẫn giữ
nghiệm thu; không mở lại review normalization/runtime. Reviewer chạy đúng suite
được báo: **97 passed in 10.29s**, không failure/error/skip. Chín output hashes
trong manifest nhận bàn giao đều khớp. Tests pass và hashes đúng chưa xác nhận
các claims trong report hoặc bao phủ các interruption/budget paths dưới đây.

## Findings cần sửa trong cùng một gói

### R1 · P1 — Dùng chung budget giữa các đối chứng và hardcode bảng kết quả

`experiments/checker_dry_run.py:1046` tạo một ledger cho cả năm paths và mọi
item. Mỗi path lại thực hiện scripted generations, nên paths/items chạy sau
thừa hưởng budget đã tiêu bởi đối chứng trước. Đó không phải paired replay
trên cùng immutable recipe outputs. Tái build cho kết quả giống raw bàn giao:

| Path | Calls | Valid / 8 | Dừng vì budget / 8 |
| --- | ---: | ---: | ---: |
| fixed CoT | 4 | 2 | 4 |
| fixed SC | 20 | 3 | 4 |
| fixed candidate selection | 12 | 3 | 5 |
| always escalate | 31 | 3 | 5 |
| checker gated | 13 | 3 | 5 |

Trong khi đó template report tại `experiments/checker_dry_run.py:1229` ghi
8/40/32/80/23 calls và 4/8, 8/8, 8/8, 8/8, 8/8 correctness, bất kể JSON.
Claim “100%, 23 calls, giảm 71,2%” không được artifacts nhận bàn giao hỗ trợ.
Generated/prompt counters của mock cũng do tác giả đặt, kể cả 120 token/call
CoT; không phải cost lịch sử đo lại. Outputs SC/TOT được lấy từ solver để tạo
fixture: chúng chỉ chứng minh đường thực thi do tác giả thiết kế.

**Sửa:** pin một trace bank synthetic, replay độc lập từng policy và giữ
collection cost khác selected-path cost; không chạy lại/cộng đối chứng vào cùng
request budget. Tạo mọi report number từ JSON đã tính; nhãn synthetic phải có
ngay ở bảng/JSON/ledger, tách khỏi historical CoT coverage. Không báo benefit
mô hình từ fixture. Test JSON/report agreement, item-order invariance và budget
isolation; không giải quyết bằng tăng global cap cho cả năm paths.

### R2 · P1 — Mất chi phí rung dang dở và chưa giữ journal khi interruption

`experiments/checker_dry_run.py:675` cộng cost từ các `steps` hoàn tất. Hủy sau
CoT và hai samples SC: checker-gated và always-escalate đều trả **1 call / 50
tokens**, nhưng ledger đã có **3 calls / 180 tokens**. Chi phí SC bị bỏ vì chưa
có `LadderStepResult` hoàn chỉnh. Cùng nguy cơ áp dụng cho fixed rung và error
paths; không được coi completed-step sum là toàn bộ call cost.

`GenerationLedger` chỉ ghi RAM; `calls.jsonl` được tạo cuối builder tại
`experiments/checker_dry_run.py:1300`. Probe ngắt builder sau call đầu đã xong:
thư mục run **rỗng** trước/sau interruption. Vì vậy tests kiểm object còn trong
RAM chưa chứng minh yêu cầu giữ raw artifacts qua interruption. Không có
completed-call/on-disk started evidence khi tiến trình dừng.

**Sửa:** tính per-evaluation cost bằng ledger deltas, gồm rung dang dở và
unknown reservations; giữ valid output và lifecycle status tách nhau. Append
started event bền vững trước dispatch và outcome sau call. Ghi manifest trạng
thái interrupted/failed và giữ các event đã ghi khi BaseException; không yêu
cầu auto-resume. Test hủy giữa SC, lỗi selector và interruption sau completed
call, đối chiếu returned totals với journal. Unfinished attempt không được
âm thầm retry/reset budget.

### R3 · P1 — Per-call cap và token counts chưa được validate

Tại `experiments/checker_dry_run.py:149` và `:179`, probe xác nhận:

- Ledger cap 1.024 nhưng chấp nhận declared max 2.048 trước dispatch.
- Declared 1.024 nhưng `record_success` chấp nhận measured 2.048, status succeeded.
- Measured −100 được chấp nhận, làm remaining tokens **82.020 > 81.920**.

**Sửa:** validate budget config, declared cap và measurements trước state
transition; positive integer cap ≤ configured cap, nonnegative finite integer
counts theo semantics backend, reject bool/negative/over-cap và unknown recipe.
Validation failure phải giữ reservation/evidence an toàn, không tạo credit.
Kiểm cả success/failure paths. Không sửa bằng clamp để che over-budget record.

### R4 · P2 — Recipe candidate selection không cùng semantics với backend

`experiments/checker_dry_run.py:564` gửi selector đúng chuỗi “Select best among
3 candidates”, thiếu query và candidate contents. Tại `:575`, selector không
parse được thì chọn candidate 0. Backend thật ở `qwen_mlx_backend.py:268–288`
đưa query+candidates và fallback majority. Authored candidates [sai, đúng, đúng]
với selector invalid: dry-run chọn sai, majority contract chọn đúng.

**Sửa ưu tiên:** để gate evaluator consume public output đã được recipe chọn
và generation traces bất biến, thay vì viết lại SC/TOT loop cạnh implementation
hiện có. Scripted call backend chỉ cần cho ledger/fault tests. Nếu giữ recipe
mock, phải pin và kiểm đúng parser/tie/selector fallback semantics; không tuyên
bố runtime/recipe parity từ fake selector luôn trả index tác giả chọn. Không
yêu cầu model hoặc framework mới để sửa phần offline này.

### R5 · P2 — Historical inputs chưa validate đầy đủ; model provenance bị đổi

Dictionary comprehension tại `experiments/checker_dry_run.py:911` âm thầm lấy
record cuối khi duplicate `(id,strategy,budget)`. Trên bản copy cô lập, thêm
CoT duplicate với answer `99` vẫn build complete và thay historical answer.
`missing_recipes` được hardcode, không derive từ dữ liệu. Manifest chỉ hash
outputs, thiếu input/source fingerprints cho lần build này.

Execution plan ở `experiments/checker_dry_run.py:1146` tự đổi candidate thành
`mlx-community/Qwen2.5-7B-Instruct-4bit`, revision `main`. Historical manifest
và handoff chỉ tới **Qwen3-8B-4bit**, revision
`545dc4251c05440727734bcd94334791f6ab0192`. Không có bằng chứng cho provenance
mới. `finish_reason: stop` là outcome, không phải setting bảo đảm trước run.

**Sửa:** validate unique/complete IDs, groups/splits/recipe keys và query-number
binding; derive missing/duplicate coverage; verify pinned historical manifest
hashes và ghi inputs/source hashes vào manifest mới. Test tampered/duplicate
copies mà không đụng raw gốc. Giữ đúng historical candidate hoặc ghi alternative
là đề xuất mới chưa chọn; không gọi `main` là frozen revision. Human/source/model
content review vẫn pending. Dùng “wall time” cho `perf_counter`, hoặc đo CPU
riêng nếu báo CPU time. Không hardcode accuracy/latency solver ngoài kết quả đo.

## Phần giữ lại và hướng tiếp

- Reuse verifier/enum có sẵn; checker không nhận gold; human review vẫn pending.
- Historical CoT coverage **4 valid / 1 invalid / 3 unverifiable** được giữ riêng;
  không có matched SC/TOT measured outputs cho tám nhóm này.
- Solver tìm được expression cho tám nhóm exposed. Đây là diagnostic hẹp;
  không có lý do tự cấp inference chỉ để tạo một bảng synthetic thành real.
- Prompt profile incompatibilities đã được chỉ ra; chưa cần xin phép authoring
  profile hoặc bật model để hoàn tất sửa offline đã giao.

Sửa R1–R5 cùng một lần, thêm regression cho counterexamples cụ thể và chạy lại
suite bắt buộc. Để report/manifest sinh từ artifacts, không chỉnh số bằng tay.
Giữ run cũ; xuất thư mục repair mới. Không mở nhánh UI, không sửa bridge đã đạt,
không tăng budget inference. Mục tiêu là gói offline đáng tin, không tạo thêm
controller hoặc phiên bản sản phẩm.

## Bằng chứng và tái lập

- `regression.txt/.xml`: fresh reviewer run, **97/97**.
- `probes.json/.txt`: counterexamples, nhận/built manifest hashes, historical
  inputs before/after; original dataset và records không đổi.
- `rebuilt/`: lần dựng độc lập với source nhận bàn giao, không ghi đè run cũ.
- `source_start.json`, `checks.json`: source fingerprints ổn định trong kiểm tra.
- `review_probes.py`: script offline; truyền `--output` là folder mới để giữ
  evidence hiện có. Source dùng authored fixtures, không đọc held-out.

```bash
.venv/bin/python -m pytest tests/test_research_pilot.py tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py tests/test_verifiers.py tests/test_checker_dry_run.py -q
.venv/bin/python audit/rat_cot_quick_unification_20261022/checker_development_dry_run/codex_review/review_probes.py --output /private/tmp/checker-review-repeat-20261023
```

**0 model/embedding calls; 0 fitting; không load/download weights, không Qt,
không approve policy/dataset/campaign, không sửa production files.**
