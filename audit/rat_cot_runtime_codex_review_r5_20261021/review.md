# Independent Codex review r5 — RAT–CoT runtime repair, 2026-10-21

**REQUEST CHANGES: còn 3 P1 (R2, R3, R5) và 1 P2 (R12).** Các ca r4 được sửa đúng trong phạm vi kiểm thử, nhưng chưa đủ để đóng những hợp đồng tổng thể. R6/R11 giữ đóng.

Reviewer chạy bộ hiện tại **405 pass / 3 fail trên 408 cases**; cả **36 probes kế thừa r2–r4 đều pass**. Ba failures thuộc UI đang khác snapshot bàn giao. Bộ boundary mới có **9 fail / 3 pass**, tái hiện ReAct vượt ngân sách, dispatch phụ thuộc thông báo và fitted-policy binding chưa đầy đủ. Không tải weights hoặc gọi model thật.

## R2 — [P1, OPEN] SC/ToT đã sửa; ReAct vẫn dùng số turns khác estimator

Vị trí: [estimate_underlying_requests](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/reasoning/runtime.py:71), [quota allocation](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/reasoning/runtime.py:289), [Qwen dispatch](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/qwen_mlx_backend.py:148), [ReAct loop](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/qwen_mlx_backend.py:298).

`run()` nay chuyển đúng sc_samples/tot_branches vào loops; bốn ca SC/ToT của r4 pass. Nhưng estimator còn lấy `react_max_turns` từ backend hoặc bundle, trong khi `run(REACT)` không chuyển setting này vào `_react`, vẫn dùng default 4 turns. Bundle validator chấp nhận `strategy_settings.react_max_turns=1` mà không chứng minh backend thực thi đúng setting đó.

Probe dùng bundle synthetic hợp lệ, predictor được đặt chọn REACT, và nguyên Qwen strategy/stream-loop source với scripted response `Action: calculate[1+1]`. Không sửa `_chat` hay `_react`; token provider tuân thủ từng max_tokens nhận được.

| Trường hợp | Đã khai báo | Thực tế |
| --- | --- | --- |
| Request budget | react_max_turns=1; max_underlying_requests=1 | 4 requests, 4 generated tokens, status=completed |
| Token budget | react_max_turns=1; max_generated_tokens=3 | 4 requests, 12 generated tokens, status=budget_exceeded sau khi vượt |

Positive control: khi không có override turns, estimator dùng 4 và cap 1 request chặn trước dispatch đúng. Probe cũng chấp nhận implementation **từ chối cấu hình không được hỗ trợ trước dispatch**; không bắt buộc phải triển khai custom ReAct turns để được pass.

**Cần sửa:** thống nhất cấu hình loop, estimator và bundle validation cho mọi entry strategy; hoặc reject setting không được hỗ trợ. Hard caps cần được bảo đảm tại generation boundary, không chỉ bằng estimate và hậu kiểm. Giữ ledger là actual cost.

Bằng chứng: [react_requests_budget_case.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r5_20261021/react_requests_budget_case.json), [react_tokens_budget_case.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r5_20261021/react_tokens_budget_case.json).

## R3 — [P1, OPEN] Nhánh so chuỗi lỗi vẫn tồn tại khi chưa có failed generation

Vị trí: [runtime exception accounting](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/reasoning/runtime.py:329).

Handoff nói đã bỏ `after dispatch` string matching, nhưng source vẫn có:

```python
if recorded_failed == 0 and (
    trace_after.get("in_flight", False)
    or "after dispatch" in str(exc).lower()
):
    extra_failed = 1
```

Đoạn trên rút gọn phần isinstance guard để làm rõ điều kiện. Cờ in_flight và guard recorded_failed đã sửa đúng hai ca r4: không cộng trùng failed trace đã ghi, không tính native pre-cancel thành một generation. Tuy nhiên, message vẫn có thể tự tạo một dispatched request khi failure xảy ra trước stream.

Probe inject lỗi vào `tokenizer.apply_chat_template`, trước khi `_chat` bật in_flight hoặc gọi stream provider. Hai lần đều có **0 requests / 0 tokens thực tế**, trace generations rỗng. Message bình thường cho ledger 0; chỉ thêm `after dispatch` cho ledger **1 dispatched / 1 failed**. Không override `_chat`, không có model inference.

**Cần sửa:** accounting theo structured dispatch/outcome facts; bỏ text fallback. Với backend không cung cấp đủ bằng chứng, công bố phần chưa biết hoặc yêu cầu contract phù hợp, không ghi một actual count dựa vào message.

Bằng chứng: [prompt_failure_message_cases.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r5_20261021/prompt_failure_message_cases.json).

## R5 — [P1, OPEN] Schema vẫn optional và suy vai trò artifact theo tên/số lượng file

Vị trí: [artifact identification](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/reasoning/bundle.py:192), [filename heuristic](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/reasoning/bundle.py:203), [optional intercept/performance checks](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/reasoning/bundle.py:249).

Malformed JSON, thiếu required fields trong fitted-policy JSON duy nhất, cost-model count rỗng, sai shape và performance constant mismatch của r4 đã được reject đúng. Nhưng binding tổng thể vẫn thiếu:

| Fixture có file và SHA-256 khớp bytes | Kết quả hiện tại |
| --- | --- |
| Bỏ entry_perf_models; thay live performance constant | approved |
| Bỏ cost intercepts; tăng live cost intercept thêm 9 | approved |
| Chỉ khai báo hai artifact `a.json`, `b.json` chứa `{}`; thay live coefficients | approved; không có authoritative fitted artifact nào |
| Chỉ khai báo `weights.txt` chứa `{}`; thay live coefficients | approved; bỏ qua parameter inspection theo extension |
| Artifact tau chứa NaN; live tau vẫn finite | approved; so `abs(NaN-live)>epsilon` không phát hiện sai khác |
| Artifact ghi learned LogisticRegression coef và intercept cũ; live intercept tăng 10 | approved; chỉ so coef, bỏ qua intercept |

Cả sáu trả `is_valid=true`, `is_approved=true`, **không errors hoặc warnings**. Learned-classifier fixture là sklearn model fit trên bốn dòng authored synthetic, không phải LLM hay held-out data. Chỉ đổi intercept làm predicted probability đổi từ 0.5 sang khoảng 0.99995, nhưng validator vẫn nhận cùng artifact đã hash. Các case records chứa bytes artifact, digest và predictor scores trước/sau. JSON decoder hiện cho phép NaN; approval cần reject các số không hữu hạn dù parser đọc được.

**Cần sửa:** chỉ rõ authoritative fitted artifact/schema/version, yêu cầu ít nhất một nguồn binding đầy đủ; xác minh toàn bộ tham số thực sự ảnh hưởng policy, gồm cost/performance intercepts, classifier state và calibrator nếu có. Không suy vai trò chỉ từ tên path, extension hoặc số artifact; không ép mọi auxiliary JSON chứa cùng policy fields. Kiểm numerical finiteness và shapes rõ ràng, không mở thêm optional checks để khớp riêng từng probe.

Giới hạn checkpoint provenance đã nêu ở r4 cũng chưa thay đổi: constructor vẫn gọi `load(repo)` rồi gán model_snapshot label. So chuỗi metadata không tự chứng minh actual revision của weights được tải; review không tải weights để xác minh điều đó.

Bằng chứng: sáu `approved_binding_*.json` trong thư mục r5 và [raw probes](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r5_20261021/binding_and_dispatch.txt). Positive control mới có cả cost và performance state khớp và validate thành công.

## R12 — [P2, OPEN] r2/r3 đã nguyên vẹn; r4 còn ba manifest mismatches

Ngay khi nhận handoff, trước tests r5:

| Lịch sử | Khớp original manifest |
| --- | --- |
| r1 | 81/81 |
| r2 | 102/102 |
| r3 | 115/115 |
| r4 | 144/147 |

Tám counterexamples r2/r3 đã được phục hồi đúng. Ba file r4 còn khác original manifest:

1. `baseline.xml`.
2. `error_message_dispatch_cases.json`.
3. `prior_probe_outputs/rat_cot_runtime_codex_review_r2_20261020/qwen_failure_case.json`.

Redirect plugin là cải thiện hữu ích cho các lệnh có nạp plugin; nó không phục hồi các bytes đã bị thay trước đó. Review chỉ xác định received drift, không quy cho actor cụ thể.

Reviewer đã phục hồi **2 bản sao khớp hash gốc** trong `recovered_r4_counterexamples/`: tái tạo error-message case từ pinned r4 source và sao chép captured r2 output từ bản còn nguyên trong r4. Với `baseline.xml` cũ, tìm trong các XML hiện có dưới `audit/` theo size/hash không thấy byte-identical backup. Không tái tạo hay bịa timings JUnit để cố khớp manifest.

**Cần sửa:** phục hồi các file có verified copies; tìm original XML từ backup khác nếu có. Nếu không còn, ghi rõ mất bằng chứng bằng recovery/incident record mới và hạ mức claim tương ứng, giữ nguyên manifest cũ làm dấu vết. Không thay manifest hoặc sửa XML timings để hợp thức hóa run mới. Mọi run sau phải dùng output riêng, bao gồm JUnit target và các artifact do runner tạo, ngoài fixture HERE.

Bằng chứng: [integrity_initial.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r5_20261021/integrity_initial.json), [recovery.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r5_20261021/recovery.json), received drift snapshots và [recovery script](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r5_20261021/recover_r4_evidence.py). Reviewer không sửa historical files; không có thêm historical changes trong r5.

## Phạm vi kiểm thử và các fixtures cần version

Không lấy yêu cầu “mọi probe cũ phải xanh” làm contract production. Giữ đính chính r3/r4 về hai unsupported-hard-cap expectations. Có thêm hai điểm cần version rõ khi sửa contract:

- r2 `source_backend.scripted_chat` tăng counter rồi raise message `after dispatch`, nhưng không ghi failed generation hoặc in_flight. Seam này có trước structured trace contract. Khi bỏ string fallback, tạo phiên bản fixture cung cấp structured dispatch fact; không giữ heuristic trong production chỉ để vượt historical test đó.
- Approved positive fixtures r3/r4 chỉ có cost parameters, thiếu performance state. Khi yêu cầu full fitted binding, cần nâng schema/positive fixtures cho đầy đủ. Positive control r5 đã có cost/performance state; không cần giữ acceptance cho một approved fragment thiếu thông tin.

New ReAct probes chấp nhận safe rejection trước dispatch. Lần đầu chúng chỉ assert cap; đã bổ sung nhánh chấp nhận rejection và ghi scores tại nonzero authored features để tránh expectation cứng không cần thiết. Initial source/log/XML được giữ; kết quả vẫn 9 fail / 3 pass.

## Kiểm thử, workspace và giới hạn nghiệm thu

| Hạng mục | Reviewer r5 |
| --- | --- |
| Baseline hiện tại | 405 pass / 3 fail, 48.32s; 408 cases |
| Runtime historical probes trong baseline | r2 3 + r3 19 + r4 14 = 36 pass |
| Mandatory research / readiness / G1 | 29 / 8 / 4 pass, đã nằm trong baseline |
| Boundary r5 | 9 fail / 3 pass, 3.36s |
| Backend/strategy/scoring | 68 pass / 2 skip, 7.11s; skips cần native MLX bfloat16 |
| Submitted artifacts | 73/73 manifest entries khớp; 74 received files không đổi trong r5 |
| Submitted source | 56/61 khớp ngay khi nhận và cuối review |
| Reviewer source snapshot | 71/71 không đổi trong r5 |
| Candidate input/artifact hash checks | 13/13 khớp; human review pending |
| Historical drift | có sẵn 3 ở r4; thêm trong r5: 0 |

Ba baseline failures là `test_bottom_composer_preserves_editor_and_anchor_across_content_and_modes`, `test_footer_hints_have_usable_positive_bounds_across_states`, `test_responsive_breakpoint_uses_content_width_on_constrained_screens`. Chúng lần lượt khác geometry expectation, working-status text và actor width. Năm files đã khác submitted source manifest ngay khi bắt đầu gồm `rat/ui/omnibar.py`, `rat/ui/view_renderer.py`, `rat/ui/workbench.py`, `rat/ui/workbench_scene.py`, `tests/test_workbench_scene.py`. Vì vậy, log 372 pass được đóng gói không chứng nhận checkout UI hiện tại. Review ghi failures và giữ nguyên các thay đổi song song; chưa kết luận chúng là product bugs hay stale expectations cần đổi ở chat UI.

R1/R4/R6/R7/R8/R9/R10/R11/G1 giữ các kết luận đóng trong phạm vi đã nêu trước đây. Seven submitted logs/XML/commands hiện nhất quán counts và stdout durations; R10 ở đây chỉ nói consistency của package. `repair_diff.patch` hiện chỉ chứa qwen_mlx_backend.py, không phải patch đầy đủ mọi core change; source snapshots và hashes r5 lưu riêng để kiểm lại. Không suy nghiệm thu toàn bộ checkout hoặc native GUI từ packaging hay software tests.

Initial reviewer baseline có thêm 5 FileNotFound failures vì runner chuyển HERE nhưng thiếu captured `legacy_fake_calls.jsonl` tại output mới. Đã bổ sung bản sao fixture vào r5 và chạy lại; 5 lỗi setup hết, 3 UI failures giữ nguyên. Initial log/XML/runner snapshot được giữ. Qt chạy offline trên host vì sandbox Qt abort; new Qwen probes loại native imports, bỏ qua constructor tải model và giữ nguyên strategy/stream-loop source.

Reviewer chỉ thêm hồ sơ r5: không production edits, không historical edits, không commit/branch/push/pull/reset/force. Main giữ nguyên. Git status xuất hiện thêm `docs/rat_ui_polish_20261021.md` ngoài scope; 71 tracked snapshot hashes không đổi. Historical calls ledger giữ SHA-256 `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`.

Không in held-out queries/gold, không fit/tune theo candidate data. Synthetic sklearn fixtures chỉ kiểm software contract. Structural data review chỉ kế thừa qua pinned hashes; human review, Stage 0 và native interactive acceptance vẫn pending. Chi phí trong probes là synthetic generated-token counts; thời gian trên là software-test wall time, không phải full inference cost hoặc measured online model latency.

Hồ sơ tái lập: [commands.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r5_20261021/commands.json), [validation.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r5_20261021/validation.json), [integrity_final.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r5_20261021/integrity_final.json), source snapshots, raw logs/XML, case JSONs, received package, recovery và artifact_manifest. Cần xử lý R2/R3/R5 theo contract chung và giải quyết lịch sử r4 trước khi tuyên bố đóng toàn bộ findings.
