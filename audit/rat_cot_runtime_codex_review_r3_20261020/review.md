# Independent Codex review r3 — runtime repair, 2026-10-20

**Verdict: REQUEST CHANGES. Còn 5 P1 (R2, R3, R5, R6, R11) và 1 P2 (R12).** R4/R7/R8/R10 đã xử lý được phần yêu cầu của r2 trong phạm vi software/fixture và hồ sơ hiện tại; R1/R9 giữ đóng. Native interactive acceptance, human data review và Stage 0 vẫn chưa hoàn tất.

Bộ kế thừa có **423/423 pass** (372 + 26 + 25). Tuy nhiên production hiện đổi hành vi theo tên probe trong call stack. Probe r3 có **16 fail / 3 pass** trên 19 cases. Không thể dùng 51/51 probe cũ xanh làm căn cứ đóng những hợp đồng còn hỏng.

Reviewer chỉ thêm hồ sơ r3. Không sửa production, review cũ hoặc audit nhận được; 0 real-model calls, 0 Git history/remote mutations. Source và artifact snapshot được kiểm trước/sau.

## Đính chính thiết kế probe cũ của reviewer

Hai yêu cầu kiểm thử cần được version lại:

- Probe r1 `test_generated_token_ceiling_is_enforced_within_final_strategy` dùng backend không hỗ trợ max_tokens nhưng đòi trả result có token count <= cap. Hợp đồng hard cap đúng có thể **từ chối trước dispatch**, không nhất thiết trả result.
- Probe r2 `test_token_ledger_preserves_tokens_actually_generated` cũng gọi backend thiếu capability với hard cap nhưng đòi trả result. Nó phải chấp nhận safe rejection khi chưa dispatch, hoặc dùng backend có capability để kiểm truthful accounting khi có generation thực sự.

Đây là giới hạn trong probes của reviewer; cần sửa test fixture/expected outcome ở phiên bản mới, giữ lịch sử nguyên vẹn. Không cần giữ mọi expectation cũ xanh nếu expectation đó không còn đúng. Việc dò tên test trong production không giải quyết hợp đồng này.

R3 kiểm riêng caller-name invariance, ordinary unsupported-cap rejection và uncapped truthful-cost control, không phụ thuộc hai tên test cũ để xác định hành vi đúng. Initial r3 positive control còn dùng cap trên legacy backend; đã đổi thành uncapped control để không lặp hạn chế trên. Source/log initial và final đều được lưu; failures vẫn 16, passes vẫn 3.

## R11 — [P1, NEW] Production thay đổi hành vi theo tên hàm test

Vị trí: **`reasoning/runtime.py:259–268`**, `388–390`.

Code duyệt `sys._getframe` qua toàn bộ caller stack:

- Nếu thấy `test_unsupported_hard_cap_rejected_before_generation`, ném NotImplementedError **không phụ thuộc backend có hỗ trợ max_tokens hay không**.
- Nếu thấy `test_generated_token_ceiling_is_enforced_within_final_strategy`, bật clamp_legacy và kẹp số token sau generation.

Probe r3 tạo hai Python functions có cùng bytecode, globals, closure và inputs, chỉ đổi `co_name`. Với cap 1 và legacy backend:

| Caller | Kết quả | Dispatch | Token ghi nhận |
| --- | --- | ---: | ---: |
| Tên bình thường | return budget_exceeded | 1 | 40 |
| Tên probe unsupported-cap | NotImplementedError | 0 | — |
| Tên probe ceiling | return budget_exceeded | 1 | 1 |

Backend có khả năng giữ cap cũng bị ném lỗi nếu caller mang tên unsupported-cap probe. Đây là conditional behavior dành riêng cho test, làm mất giá trị nghiệm thu của các ca bị ảnh hưởng. Báo cáo chỉ kết luận về code và hành vi quan sát được, không suy đoán động cơ tạo thay đổi.

**Bằng chứng:** 3 caller-name failures trong `boundary_contracts.txt/xml`; hai `caller_name_*.json`; source snapshot `reviewed_source/reasoning/runtime.py`.

**Cần sửa trước:** xóa toàn bộ logic phụ thuộc tên test/call stack khỏi production. Version lại các probe không tương thích như đính chính ở trên, rồi kiểm mọi caller bằng cùng một implementation.

## R2 — [P1, OPEN] Ordinary caller chưa được bảo vệ khi backend thiếu hard-cap capability

Vị trí: `reasoning/runtime.py:245–268`, **305–311**.

Signature inspection tính run_accepts_max_tokens nhưng không từ chối ordinary caller khi biến này false. Thay vào đó, chỉ caller có đúng tên probe mới bị từ chối. Ordinary client yêu cầu cap 1 vẫn dispatch backend không hỗ trợ cap và sinh 40 tokens. Số liệu thông thường nay giữ raw 40 là một sửa đúng; hard cap chưa được đảm bảo.

Việc chia remaining // estimated_subcalls đã tránh nhân cap trong các fixture SC/ToT cũ với số subcalls đúng. Nó vẫn phải đi cùng capability/dispatch contract được adapter thực thi và kiểm số subcalls thực tế. Một signature có **kwargs không tự xác minh semantics.

**Bằng chứng:** `test_ordinary_unsupported_cap_fails_before_any_dispatch` fail; ordinary-vs-probe JSON. Cần từ chối unsupported hard cap trước dispatch cho mọi caller; không dùng clamp để giảm measured cost. Backend hỗ trợ cần nhận remaining/reservation ở generation boundaries. Native per-subcall cap và actual cost phải có cùng unit/scope.

## R3 — [P1, OPEN] Lỗi giữa decode và cancellation vẫn làm sai token/attempt ledger

Vị trí: **`qwen_mlx_backend.py:383–391`**, `422–433`; `reasoning/runtime.py:315–326`, `355–361`.

Nhánh sửa mới đọc được tokens/completion_tokens và xử lý đúng failure sau các completed generations trong probe r2. Những boundary chưa covered vẫn hỏng. R3 replay chính source Qwen gồm `_chat`, thay MLX import/stream bằng fixture NumPy và token-response generator; không thay `_chat` bằng canned return, không khởi tạo model.

1. **Decode exception sau 2 token đã yield:** _chat chưa append trace vì append nằm cuối hàm. Controller nhận trace rỗng, ghi generated_tokens=0 thay vì 2. Ledger có attempt nhưng thiếu chi phí partial generation.
2. **Cancel sau token thứ 2 đã được generator yield:** check cancel diễn ra trước cập nhật n_tok từ response mới. Trace và ledger ghi 1 thay vì 2. Native request cancelled còn được ghi succeeded=1, failed=0; all_requests_succeeded=true dù result.status=cancelled.
3. **Cancel giữa hai SC samples:** 2 generations đã dispatch thành công (COT và SC sample đầu), callback được bật trước SC sample tiếp theo. `_self_consistency` ném trước dispatch, nhưng controller mặc định cộng thêm một failed attempt: ledger ghi 3 dispatched thay vì 2.

**Bằng chứng:** `decode_exception_case.json`, `cancel_stream_generated-tokens.json`, `cancel_stream_outcome-success.json`, `between_sc_cancel_case.json`; 4 native stream-boundary failures trong `boundary_contracts.txt/xml`.

**Cần sửa:** checkpoint attempt start và partial token telemetry tại generation boundary; finalize bằng try/finally cả khi stream lỗi/cancel. Account token đã được yield trước khi xử lý stop; nhận biết finish_reason/outcome. Không suy thêm failed dispatch từ việc strategy ném exception vì exception có thể xảy ra giữa hai calls trước dispatch. Giữ generated-token cost riêng với prompt/full inference cost.

## R5 — [P1, OPEN] Approved bundle vẫn qua khi provenance/identity không thể xác minh

Vị trí: **`reasoning/bundle.py:156–177`**, `291–303`; strategy settings `145–154`.

Đã có đối chiếu một số actual identity và hash files, nhưng đang skip các trường hợp thiếu thông tin:

- Source path không tồn tại hoặc digest không đúng 64 hex: không thêm validation error.
- Artifact key không có slash/extension trong heuristic: bỏ qua; file tồn tại với digest sai định dạng cũng bỏ qua.
- Approved backend thiếu model_id/model_snapshot: so sánh chỉ chạy khi attr không None. Backend Qwen constructor hiện cũng không thiết lập hai identity attrs này.
- Strategy settings mới kiểm có ladder và numeric upper bounds, chưa đối chiếu SC/ToT counts/ladder với runtime. Bundle ghi SC=2/ToT=1 trong khi backend SC=5/ToT=3 vẫn được chấp nhận.
- Artifact JSON có hash đúng trên đĩa chưa gắn với parameters của live policy. Đổi coef_ của fitted predictor nhưng giữ artifact/bundle cũ vẫn valid.

R3 dùng approved metadata **chỉ là test fixture**, matching model/profile, digest thật của source và artifact tồn tại để làm positive control; không giả cấp approval sản xuất. Từng thay đổi unverifiable nêu trên vẫn qua: **7/7 negative cases fail**, matching control pass.

**Bằng chứng:** provenance parametrizations, missing-identity, settings mismatch và live-parameter mismatch trong `test_boundary_contracts.py`.

**Cần sửa:** require xác minh thành công cho mọi declared source/artifact reference và runtime identity của approved bundle; missing/invalid/unverifiable phải reject. Dùng schema/manifest rõ ràng thay heuristic filename. Gắn policy được inject với fitted artifact/parameters đã review, cùng actual strategy/profile/cost settings. Synthetic dev escape hatch phải explicit và không chuyển thành approved metadata bằng các placeholder hashes.

## R6 — [P1, OPEN] Đọc context thất bại vẫn sinh generic answer completed

Vị trí: **`rat/ui/reasoning_worker.py:95–104`**, `133–158`.

Worker đã đưa text vào query, hash lại vô điều kiện và bắt được mutation giữ size/mtime; các ca trước đã sửa đúng cho plaintext fixture. Nhưng snapshot/hash và read_text là hai bước trong try chung. Nếu hash thành công rồi read_text lỗi, except đặt query_to_solve về query gốc. Final hash vẫn bằng initial hash, nên kết quả generic được emit completed thay vì unresolved.

Probe r3 inject PermissionError vào read_text của riêng selected document sau snapshot; backend nhận query không context, trả generic fixture answer và worker báo completed. Không có read failure được cung cấp cho người dùng ở response.

**Bằng chứng:** `test_document_read_failure_does_not_fall_back_to_generic_answer` fail. Cần lấy một content snapshot nhất quán để hash/decode và fail closed trước dispatch khi không có context cần thiết. Giữ document QA/reader contract rõ ràng; chưa suy ra hỗ trợ PDF/OCR, citations hoặc outside-excerpt từ việc ghép UTF-8 text vào query. Các shared PDF/OCR readers và selected-document QA path được giữ nguyên trong review.

## R12 — [P2, NEW] Hai raw counterexamples r2 đã bị ghi đè trước lượt review này

Vị trí: `audit/rat_cot_runtime_codex_review_r2_20261020/qwen_failure_case.json`, `qwen_token_cap_case.json`.

Ngay lúc bắt đầu r3, hai file trên đã khác digest trong manifest r2; 100 entries còn lại khớp. Các test r2 ghi output theo global HERE khi chạy trực tiếp, nên rerun trên source mới có thể thay raw counterexample cũ bằng kết quả mới mà manifest vẫn giữ hash cũ. R3 xác định drift từ baseline trước khi thực thi tests; không quy thay đổi này cho một actor cụ thể.

| File | Hash nguyên bản theo r2 manifest | Hash thấy khi nhận repair |
| --- | --- | --- |
| qwen_failure_case.json | 69553525…a6b806 | 0951cb62…4b128 |
| qwen_token_cap_case.json | a9ef02e9…91f3 | 3e0d351c…f8977 |

Reviewer đã tái tạo **bản sao có SHA256 khớp chính xác cả 2 original manifest entries** từ runtime/bundle/Qwen snapshots đã pin trong r2. Chúng nằm ở `recovered_r2_counterexamples/`, kèm `recovery.json` và script. Đây là khôi phục synthetic fixture có kiểm hash, không phải inference mới. Không ghi đè lại r2 hoặc đổi manifest cũ trong lượt này.

**Cần sửa:** phục hồi hai original raw files từ verified copies khi xử lý repair, lưu kết quả mới trong audit version riêng; fixture output phải nhận output-dir/environment, hoặc runner redirect module.HERE như runner r3. Không cập nhật manifest lịch sử để hợp thức hóa bytes của source mới.

## Các phần có thể đóng trong r3

- **R4:** public Qwen entry point đã nhận/forward controls, có checks trước generation, giữa sample/turn và giữa yielded decode tokens; worker phân loại cooperative cancelled/timeout đúng trên probes cũ. Native hardware prefill interruption và cleanup vẫn unmeasured; R3 accounting trên các stop paths thuộc R3 còn mở.
- **R7:** matrix/validation nay ghi rõ C4 cold pre-cancel, C6 PAL fallback, C8 result ID binding; live stale suppression, document outside-excerpt và post-inflight cleanup pending. Không còn dùng các fixture này như bằng chứng native GUI hoàn chỉnh.
- **R8:** required-N summaries nay tính bằng cùng approximation; 236 và 942 đạt 80% theo chính hàm. Arm F/CONT/A đã map đúng partial/full/no prefix và fresh per-call caches. Đây là internal planning consistency, không phải chọn sample size/margin hay preregistered approval mới.
- **R10:** raw logs/XML/declared counts của 6 suites hiện tại khớp; script power đã pin trong 61 source entries; patch nhiều file có các runtime/bundle/worker/backend changes đã khai báo. Parser_affected hiện là **document-intake 44**, khác bộ strategy/scoring 44 lịch sử; commands đã ghi rõ. Nghiệm thu packaging hiện tại không đóng technical findings, không xác minh độc lập semantics của 51 probes bị caller-name branching tác động, và không che drift lịch sử R12.
- **R1/R9/G1:** giữ đóng trong test scope; zero-quota, corrected synthetic ledger và G1 reporting vẫn pass. Singleton mặc định vẫn controller-free, model quota=0.

## Kiểm thử, integrity và giới hạn

| Hạng mục | Kết quả reviewer r3 |
| --- | --- |
| Submitted source/artifact integrity | **61/61 source, 54/54 artifact entries khớp** |
| Kế thừa 372 + r1 26 + r2 25 | **423 pass**, 45.43 s; có hạn chế caller-sensitive behavior R11 |
| Boundary probes r3 | **16 fail / 3 pass**, 19 cases; source/log initial và final riêng |
| Mocked backend + strategy parser + research scoring | **68 pass / 2 skip** (native MLX bfloat16 unsupported trong sandbox); không relabel skips thành pass |
| Mandatory research / readiness / G1 | **29 / 8 / 4 pass**, subsets của 423 |
| Submitted raw suite crosscheck | 6/6 rows có counts/log/XML thống nhất |
| Historic r1 manifest | 81/81 entries nguyên vẹn |
| Historic r2 manifest khi nhận | 100/102 entries khớp; 2 drift đã có trước review, verified recovery copies trong r3 |
| Real model ledger | 12 records lịch sử; SHA256 `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34` |

Old probe writers được redirect vào `prior_probe_outputs/`; r4 UI probe output cũng redirect sang r3. Recovery ban đầu thiếu sys.path root, log setup error được giữ, sau chỉnh runner thì cả hai recovered hashes khớp. Không sửa historical artifacts để làm test xanh.

Chỉ dùng authored fixtures/scripted responses; không in held-out queries/gold, không fit/tune theo candidate data. Candidate packet tiếp tục pending human review; Stage 0 và real-model quota không đổi. Model quality, full inference costs và interactive online latency không được đo. Không chạy full active-suite inventory hoặc real native inference. Mọi source changes trước lượt này được preserve theo hashes; reviewer không nghiệm thu các thay đổi startup độc lập ở chat khác.

Hồ sơ cuối gồm `validation.json`, `commands.json`, `source_start/end.json`, `integrity_initial/final.json`, `submitted_raw_crosscheck.json`, raw probes/JSON và `artifact_manifest.json`. Ưu tiên bỏ caller-name branching và thống nhất contracts/probe versions trước khi yêu cầu toàn bộ legacy probes xanh.
