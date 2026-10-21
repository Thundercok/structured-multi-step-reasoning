# Independent Codex review r4 — RAT–CoT runtime repair, 2026-10-21

**REQUEST CHANGES: còn 3 P1 (R2, R3, R5) và 1 P2 (R12). Đóng R11 và R6 trong phạm vi đã kiểm.** Bản bàn giao mới sửa đúng các counterexamples r3, nhưng chưa đủ để kết luận mọi hợp đồng đã hoàn tất.

Reviewer chạy lại **394/394 pass**: 372 regression + 19 r3 boundary contracts + 3 r2 Qwen replay. Probe r4 có **11 fail / 3 pass**; bộ backend/strategy/scoring bổ sung có **68 pass / 2 skip**. Toàn bộ generation trong review là scripted fixtures, không tải weights và không gọi model thật.

## R2 — [P1, OPEN] Cấu hình số mẫu không điều khiển execution, làm vượt cả request và token cap

Vị trí: [Qwen run dispatch](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/qwen_mlx_backend.py:148), [SC loop](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/qwen_mlx_backend.py:207), [ToT loop](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/qwen_mlx_backend.py:238), [controller quota allocation](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/reasoning/runtime.py:283).

Constructor nhận và lưu `sc_samples`, `tot_branches`, nhưng `run()` không truyền các giá trị này vào strategy methods. SC vẫn dùng default `k=5`; ToT vẫn dùng default `branches=3`. Trong khi đó controller ước tính số requests và chia token quota theo attributes đã cấu hình. Bundle validator cũng chỉ so các attributes này, chưa chứng minh execution thực sự tuân theo chúng.

Probe chạy nguyên strategy/stream-loop source, chỉ thay MLX imports và token provider, bỏ qua constructor tải model. Attributes được đặt đúng như constructor hiện tại:

| Trường hợp | Cấu hình/cap | Thực tế |
| --- | --- | --- |
| Gọi SC trực tiếp | sc_samples=2 | 5 generations |
| Gọi ToT trực tiếp | tot_branches=1, dự kiến 1 branch + 1 synthesis | 4 generations |
| Controller request cap | sc_samples=2; max_underlying_requests=3 | 6 requests; status=completed |
| Controller token cap | sc_samples=2; max_generated_tokens=5 | 11 generated tokens; status=budget_exceeded sau khi vượt |

Trong ca token cap, token provider **tuân thủ từng max_tokens nhận được**: CoT sinh 1, còn quota 4 được chia theo estimate 2 thành 2 tokens/subcall, nhưng SC thực hiện 5 subcalls. Đây là lỗi nối cấu hình với execution, không phải yêu cầu backend không có capability phải giữ hard cap.

**Cần sửa:** dùng cùng cấu hình thực thi cho loops, estimates và bundle validation; enforce ngân sách tại từng generation dispatch nếu API hứa hard cap. Giữ ledger đúng chi phí thực tế, không clamp sau khi đã sinh. Bằng chứng: [configured_request_budget.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r4_20261021/configured_request_budget.json), [configured_token_budget.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r4_20261021/configured_token_budget.json), 4 failures đầu trong [raw probes](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r4_20261021/remaining_contracts.txt).

## R3 — [P1, OPEN] Dispatch accounting vẫn phụ thuộc thông báo lỗi và suy đoán khi trace rỗng

Vị trí: [runtime exception accounting](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/reasoning/runtime.py:321), [native pre-generation guard](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/qwen_mlx_backend.py:384).

`_chat` đã ghi trace trong finally và bảo toàn partial tokens ở các ca r3. Tuy nhiên runtime vẫn thêm một failed request nếu trace rỗng **hoặc** exception message chứa `after dispatch`.

- Hai scripted streams đều dispatch 1 lần, yield 2 tokens rồi raise. Chỉ thêm cụm `after dispatch` vào message làm ledger đổi từ **1 thành 2 requests**, dù trace đã ghi chính generation thất bại đó. Tokens vẫn đúng 2.
- Cancellation đến ở native `_chat` pre-guard, sau hai controller guards nhưng trước stream provider: **0 generations thực tế**, trace rỗng, ledger vẫn ghi **1 dispatched/failed request**.

Đây là hai biến thể của R3, không mở finding mới. **Cần sửa:** dùng thông tin dispatch/outcome có cấu trúc, phân biệt lỗi trước và sau dispatch; không suy số requests từ text và không mặc định empty trace đồng nghĩa một generation đã chạy. Nếu backend không cung cấp đủ bằng chứng, biểu diễn phần chưa biết thay vì khẳng định một actual count.

Bằng chứng: [error_message_dispatch_cases.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r4_20261021/error_message_dispatch_cases.json), [predispatch_cancel_case.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r4_20261021/predispatch_cancel_case.json). Positive control xác nhận ordinary decode error hiện ghi đúng 1 request và 2 partial tokens.

## R5 — [P1, OPEN] Hash artifact đúng chưa ràng buộc đầy đủ fitted policy được chạy

Vị trí: [optional artifact parameter checks](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/reasoning/bundle.py:192), [inspection errors downgraded to warnings](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/reasoning/bundle.py:217).

Các sửa đổi về file tồn tại, SHA-256 hợp lệ, digest khớp và identity bắt buộc đã pass r3. Lỗ hổng còn lại là fitted parameters chỉ được so **nếu field có mặt**; không kiểm đầy đủ số models; lỗi parse/shape chỉ thành warning. Performance predictor cũng chưa được ràng buộc với artifact.

Cả 5 fixture dưới đây có file thật và digest khai báo khớp bytes. Validator vẫn trả `is_valid=true`, `is_approved=true`, không có errors:

| Fitted artifact / live policy | Kết quả |
| --- | --- |
| JSON không parse được | approved + warning |
| `{}` thay fitted-policy JSON duy nhất | approved, không warning |
| entry_cost_models=[] và thay live cost coefficient | approved, không warning |
| coef có 2 phần tử, live model có 5 | approved + shape warning |
| Artifact ghi performance constant cũ, live performance constant đã đổi | approved, không warning |

Không cần ép mọi JSON phụ trợ chứa mọi parameter. Cần **schema và vai trò artifact rõ ràng**, trong đó có ít nhất một fitted artifact đầy đủ, được review và dùng để xác minh toàn bộ policy thực thi: số lượng, shape, giá trị, cost/performance models và calibrator nếu có. Thiếu hoặc không đọc/xác minh được authoritative fitted artifact phải reject. Các tên fields trong fixtures minh họa vấn đề binding; implementation cần công bố định dạng được hỗ trợ, không thêm một nhóm optional heuristics nữa.

Một giới hạn provenance khác nhìn thấy trực tiếp trong source: [constructor](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/qwen_mlx_backend.py:81) gọi `load(repo)` rồi gán `self.model_snapshot = model_snapshot`. So sánh label snapshot này chưa xác minh revision của weights được load. Cần có bằng chứng actual loaded revision nếu dùng identity đó để phê duyệt checkpoint. Review không tải weights để kiểm checkpoint.

Bằng chứng: [bundle_parameter_cases.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r4_20261021/bundle_parameter_cases.json), các artifact tại `bundle_counterexamples/`, 5 failures parametrized trong raw probes. Fixture có tham số khớp vẫn validate thành công ở positive control.

## R12 — [P2, OPEN] Bằng chứng lịch sử vẫn drift: 2 file r2 và thêm 6 file r3

Ngay **trước khi chạy tests r4**, manifest r1 khớp 81/81, r2 khớp 100/102, r3 khớp 109/115. Các file khác hash gốc:

- r2: `qwen_failure_case.json`, `qwen_token_cap_case.json`.
- r3: `between_sc_cancel_case.json`, hai `caller_name_*.json`, hai `cancel_stream_*.json`, `decode_exception_case.json`.

Các historical probes ghi output vào module.HERE khi chạy trực tiếp. Điều này phù hợp với cơ chế drift đã chỉ ra ở r3; review chỉ kết luận bytes nhận được khác manifest, không quy thay đổi cho một actor cụ thể. Việc từng phục hồi hai file rồi chạy lại writer trên source mới chưa bảo toàn được lịch sử.

Reviewer đã lấy lại **8/8 bản sao khớp SHA-256 manifest gốc** trong thư mục r4: hai bản r2 từ verified recovery trước đó; sáu bản r3 được tái tạo bằng pinned source snapshots và scripted streams. Các original assertion failures cũng được tái hiện. Xem [recovery.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r4_20261021/recovery.json) và [recovery script](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r4_20261021/recover_historical_evidence.py).

**Cần sửa:** khi xử lý repair, phục hồi 8 historical files từ verified copies; mọi lần chạy mới phải ghi vào thư mục version mới bằng output-dir hoặc runner redirect. Không đổi manifest lịch sử để chấp nhận outputs mới. Reviewer chỉ lưu received drift và recovered copies trong r4; không chỉnh các thư mục review cũ. Không có thêm historical manifest-entry changes trong lượt r4.

## Các phần được đóng và phạm vi kế thừa

- **R11 CLOSED:** không còn caller-name inspection; caller invariance và capable-backend controls pass. [runtime.py:259](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/reasoning/runtime.py:259) áp dụng safe rejection cho mọi caller khi backend không nhận max_tokens.
- **R6 CLOSED:** [reasoning_worker.py:102](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/ui/reasoning_worker.py:102) emit unresolved rồi return khi đọc selected document lỗi; injected read failure không gọi backend. Giới hạn vẫn là plaintext/context paths đã kiểm, chưa chứng minh PDF/OCR/citations hoặc outside-excerpt QA.
- **R1/R4/R7/R8/R9/R10/G1:** giữ kết luận đóng trong phạm vi r3 đã nêu. Current raw logs/XML/commands counts của 6 submitted suites khớp; G1 4 và native-readiness 8 đều nằm trong 394. Qwen replay raw/prose ghi 4.04s (XML 4.037s), còn commands.json vẫn ghi 2.37s, cùng 3 pass; cần đồng bộ metadata thời gian này. Không dùng kiểm tra packaging để đóng technical findings hoặc nâng native interactive acceptance.

Giữ đính chính của reviewer r3: hai probes r1/r2 yêu cầu backend thiếu capability phải trả token-capped result có expectation không phù hợp. Chúng được giữ nguyên như lịch sử và **không phải acceptance gate r4**. Bộ r4 dùng hợp đồng từ chối an toàn trước dispatch, caller invariance và backend thật sự có max_tokens capability. Không yêu cầu production giữ mọi legacy expectation xanh.

## Kiểm thử và integrity

| Hạng mục | Kết quả |
| --- | --- |
| Reviewer baseline | 394 pass, 47.80s; 372 + 19 + 3 |
| Mandatory research subset | 29 pass, đã nằm trong 394 |
| Native-readiness / G1 subsets | 8 / 4 pass, đã nằm trong 394 |
| New r4 probes | 11 fail / 3 pass, 3.23s |
| Backend/strategy/scoring | 68 pass / 2 skip, 5.91s; skips cần native MLX bfloat16 |
| Submitted hashes khi nhận | 61/61 source; 58/58 artifacts |
| Submitted audit files cuối review | 60 files không đổi; manifest 58/58 vẫn khớp |
| Source snapshot cuối review | 67/70 không đổi; 4 core files đang review không đổi |
| Historical manifests | Drift có sẵn 8; thêm trong r4: 0; recovered copies khớp gốc: 8/8 |
| Pinned candidate inputs/artifacts | 13/13 khớp; human review pending |
| Historical calls ledger | SHA-256 giữ nguyên `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34` |

**Giới hạn do workspace thay đổi đồng thời:** `rat/ui/assistant_worker.py`, `rat/ui/omnibar.py`, `rat/ui/workbench_scene.py` đổi hash trong lượt review; mtimes ghi nhận sau khi baseline kết thúc. Final checkout chỉ còn khớp 58/61 submitted source entries. Git status cũng xuất hiện `rat/engine/execution.py` và `audit/rat_flow_optimization_20261021/`. Reviewer giữ nguyên những thay đổi này, không suy đoán tác giả và không nghiệm thu chúng. Kết quả 394 pass thuộc lần chạy trước các UI mtimes trên; **không phải chứng nhận toàn bộ checkout UI cuối lượt**. Xem [source_drift.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r4_20261021/source_drift.json), end copies và [integrity_final.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r4_20261021/integrity_final.json). Các findings runtime/bundle/Qwen/reasoning_worker dùng bốn source files vẫn khớp snapshot ban đầu.

Runner redirect mọi historical fixture writer được gọi sang r4. Qt baseline chạy offline trên host vì Qt abort trong sandbox; probes Qwen dùng source với native imports loại bỏ và scripted stream provider. Recovery không phải inference. Final-check script lần đầu đọc nhầm schema manifest, đã sửa; lần sau phát hiện source drift nói trên, đã lưu riêng log và thu hẹp phạm vi kết luận trước khi seal hồ sơ.

Reviewer chỉ ghi hồ sơ mới trong r4, không sửa production hoặc lịch sử, không commit/branch/push/pull/reset. Nhánh vẫn main. Không in held-out queries/gold, không fit/tune theo candidate data. Structural data review chỉ kế thừa khi pinned hashes khớp; human review và Stage 0 chưa được xác lập hoàn tất. Costs là synthetic generated-token counts; thời gian báo cáo là software test wall time, không phải full inference cost hay measured online model latency.

Hồ sơ tái lập: [commands.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r4_20261021/commands.json), [validation.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r4_20261021/validation.json), raw logs/XML, source_start/end, integrity_initial/final, received artifacts, recovery và artifact_manifest. Ưu tiên sửa R2/R3/R5 bằng hợp đồng thực thi rõ ràng và bảo toàn historical evidence trước khi đề nghị nghiệm thu lại.
