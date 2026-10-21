# Independent Codex review — RAT–CoT Runtime Acceptance, 2026-10-20

**Verdict: REQUEST CHANGES.** Gói bàn giao có source/artifact nguyên vẹn và bộ hồi quy **372/372 pass** được tái lập độc lập. Tuy nhiên chưa thể nghiệm thu B1/B2/B3 hoặc phần chuẩn bị protocol như báo cáo: **6 finding P1 về runtime và 3 finding P2 về bằng chứng/protocol** còn mở. Probe mới: **22 fail / 4 pass** trên 26 cases, tách riêng khỏi 372 tests gốc; không cộng trùng hoặc diễn giải thành measured model quality.

Review chỉ thêm hồ sơ trong thư mục này. Không sửa production, không duyệt held-out thay người, không gọi model thật, không thay Stage 0, không commit/branch/push/pull/reset. `~/github/nesy-docai` resolve về đúng checkout đang review, nhánh `main`.

## R1 — [P1] Ngân sách bằng 0 bị coi như không có override

Vị trí: `reasoning/runtime.py:199–202`.

Ba biểu thức `max_* or self.max_*` loại bỏ giá trị hợp lệ `0`. Cả ba trường hợp `max_strategy_invocations=0`, `max_underlying_requests=0`, `max_generated_tokens=0` vẫn dispatch một COT, trả `completed`, tiêu thụ 40 synthetic tokens. Khi controller có default dương, override 0 cũng khôi phục default đó. Đây là vi phạm quan trọng của zero-quota contract, dù lượt review không gọi model thật.

**Bằng chứng:** 6 parametrized failures `test_zero_per_call_budget_dispatches_nothing` và `test_zero_override_does_not_restore_positive_default` trong `contract_probes.txt/xml`. Cần phân biệt `None` với `0`, kiểm kiểu/miền ngân sách và chặn trước dispatch.

## R2 — [P1] `max_generated_tokens` chưa tạo trần cho generation đang chạy

Vị trí: `reasoning/runtime.py:226–241`, `265–278`.

Controller chỉ kiểm tổng tokens trước strategy, không truyền remaining cap xuống backend hoặc từng subcall. Với cap 1, generation trả 40 tokens và confidence cao khiến controller thoát với `completed`. SC/ToT/ReAct có thể vượt remaining cap ngay trong một strategy. Hiện đây là ngưỡng giữa strategies, không phải maximum generation budget như hợp đồng bàn giao.

**Bằng chứng:** `test_generated_token_ceiling_is_enforced_within_final_strategy` fail, ledger ghi 40 > 1. Cần cap ở generation boundary, tính phần ngân sách còn lại cho mọi subcall, và từ chối backend không thể giữ hard cap nếu caller yêu cầu hợp đồng này.

## R3 — [P1] Exception làm mất attempt ledger và chi phí đã phát sinh

Vị trí: `reasoning/runtime.py:239–247`; `rat/ui/reasoning_worker.py:136–158`.

Nhánh exception chỉ tăng counters cục bộ thêm 1 rồi `raise` exception gốc. Không có result, checkpoint hoặc exception metadata mang ledger ra ngoài. Trace của các subcall đã hoàn thành cũng không được tổng hợp trong nhánh này. Worker bắt lỗi và tạo response mới với `tokens=0`, `cost_ledger=None`, không còn bundle ID hay path đã thực thi.

Probe chạy COT thành công (20 tokens), rồi SC có hai subcall thành công (40 tokens) và một failed dispatch. Sau **4 dispatched requests / 60 synthetic generated tokens**, caller/worker đều không nhận được ledger. Vì vậy test gốc chỉ kiểm `raises` không chứng minh được “failed attempts charged”.

**Bằng chứng:** `test_backend_error_preserves_attempt_ledger_for_caller`, `test_worker_error_preserves_attempt_ledger` fail. Cần ledger ở từng dispatch, kết quả/error mang partial ledger và provenance; không thay lỗi thành canned answer hay hoàn tác chi phí.

## R4 — [P1] Cancellation/deadline không đi vào backend; terminal strategy có thể báo completed sai

Vị trí: `reasoning/runtime.py:239–241`, `275–285`; `qwen_mlx_backend.py:108`, vòng generation trong `_chat`.

Controller gọi `backend.run(strategy, query)` mà không truyền callback hoặc deadline. LLMBackend hiện không có execution-context contract cho prefill/decode; Qwen backend cũng không poll các tín hiệu từ controller. Kiểm tra giữa ladder rungs chỉ ngăn lượt tiếp theo, không hủy generation đang chạy.

Ngoài ra, nhánh `break` khi confidence đủ cao, khi chạy PAL/ReAct hoặc khi đến rung cuối xảy ra trước các kiểm tra sau strategy. Probe đặt cờ cancel hoặc để deadline hết ngay trong lần COT cuối vẫn nhận `status='completed'`. Worker có thể emit status `cancel` nhưng response vẫn mang status completed.

**Bằng chứng:** 3 failures `test_final_strategy_cannot_report_completed_after_stop_event[cancel/deadline]`, `test_cancel_hook_reaches_backend_run`. Cần execution context có khả năng được backend thực thi và finalization kiểm tra stop state trên mọi đường thoát. Không suy ra hard preemption từ cooperative cancel.

## R5 — [P1] Bundle validator chưa ràng buộc provenance/compatibility đã quảng bá

Vị trí: `reasoning/bundle.py:177–201`; `rat/engine/meta_reasoner.py:514–520`.

Backend validation chỉ kiểm hidden size và hai callable. `model_id`, `model_snapshot`, `prompt_profile`, `backend_protocol`, predictor kind, cost/execution semantics mới được kiểm như chuỗi không rỗng; không đối chiếu danh tính/backend capability thực tế. Source/artifact hashes và dataset/provenance dictionaries rỗng vẫn được chấp nhận. `feature_schema_version=999` cũng qua; đổi specimen fit 3 complexity features thành version 2 (6 features) vẫn composition thành công, thay vì bị từ chối trước execution.

Các phép so `abs(a-b)>epsilon` còn chấp nhận NaN trong bundle lambda/thresholds. Validator cũng chưa gắn fitted predictor/calibrator parameters với artifact hash được review. Safe JSON metadata không tự xác minh một fitted policy.

**Bằng chứng:** 6 incompatible-approved-metadata cases và 1 feature-dimension case fail. Control unknown-calibrator không có calibrators đã bị từ chối đúng; không claim case này hỏng. Cần validate supported schema, số hữu hạn, actual fitted dimensions, pinned runtime identity/settings và artifact contents. Backend/profile `aligned-direct-cot-v1` hiện chỉ hỗ trợ DIRECT/COT; không thể mặc nhiên coi là tương thích SC/ToT ladder.

## R6 — [P1] Document path hiện hữu bị bỏ qua; thay đổi giữa lượt không bị phát hiện

Vị trí: `rat/ui/reasoning_worker.py:63–67`, `116–126`.

Worker chỉ kiểm `is_file()` trước execution. Nếu có tệp, path/content/version không đi vào `engine.solve`; không snapshot hay recheck khi emit. Backend đổi nội dung tệp ngay giữa execution vẫn nhận câu trả lời chung, `status='completed'`, `execution_mode='online_policy'`, confidence 0.99. Missing-file guard là đúng nhưng không đủ cho changed-document/outside-excerpt contract.

**Bằng chứng:** `test_worker_document_change_during_execution_is_unresolved` fail. Cần route rõ sang selected-document QA với source identity/version và revalidation, hoặc từ chối document mode trong worker strategy này. Giữ QA session tách khỏi strategy backend; không giả vờ đã dùng tài liệu chỉ vì path tồn tại.

## R7 — [P2] Ma trận VERIFIED và telemetry claims vượt quá hành vi đã kiểm

Vị trí: `tests/test_native_acceptance_readiness.py:78–88`, `91–124`, `179–228`; `audit/rat_cot_runtime_acceptance_20261020/native_acceptance_matrix.md:13–35`.

- C1 nhận một whole-answer callback sau khi run xong; không kiểm token streaming. `OnlineReasoningWorker.step_completed` chưa emit lần nào và engine không forward `on_step`; probe worker progress fail.
- C2 cài cancel sẵn trong double, không truyền `controller.is_cancelled`; C3 đặt `fail_phase='decode'`, còn `make_cancel` không được gọi. Đây là injected failure, không phải hủy decode qua production path.
- C4 cancel trước dispatch; chưa kiểm resource cleanup sau hủy generation đang chạy. C5 xóa tệp giữa hai lượt, không đổi giữa lượt. C6 gọi PAL thiếu dữ kiện, không kiểm outside-excerpt document QA.
- C7 chỉ assert exception và deadline đã hết trước dispatch, không kiểm failed ledger. C8 kiểm một hàm local viết trong test, không gọi production worker/UI consumer.
- Queue latency và first displayed UI token được ghi “Measured”, nhưng không có phép đo/field tương ứng trong worker/tests mới; `latency_ms` bắt đầu trong `run()` nên không gồm queue time.

Cần hạ trạng thái các ô chưa được chứng minh và viết fixture tests qua đúng production boundaries. Default singleton vẫn controller-free; việc import worker trong assistant_worker chưa thiết lập luồng UI sử dụng worker. Đây là opt-in component acceptance, chưa phải bằng chứng toàn bộ native RAT flow đã tích hợp. Không yêu cầu bật policy chưa review vào UI mặc định.

## R8 — [P2] Draft protocol trộn fresh restart với routing ladder và công bố power chưa tái lập

Vị trí: `audit/rat_cot_runtime_acceptance_20261020/data_review_checklist.md:55–75`; `unauthorized_real_execution_plan.md:21–33`.

Docs canonical `docs/cot_restart_fresh_adapter_20261016.md` định nghĩa O/F/CONT với optional A, temperature/top_p, fresh caches, original token IDs và prefix rules; cap 64/q=0.50 là smoke settings, chưa freeze cho nghiên cứu. Draft mới gọi F là dynamic RL routing/ladder, A là offline ablation hoặc baseline without escalation, rồi suy `70 × 4 = 280 maximum generation requests`. Một F ladder riêng đã có thể gồm COT+SC+ToT = 10 requests; số arms không xác định trần subcalls. Chưa có mapping cho fresh continuation và các điều kiện token/prefix/seed của adapter. Không thể dùng draft này như một execution freeze có thể chạy sau quota approval.

Các số N≈110–130, N≈50–65 và MDE 0.13–0.15 cũng thiếu script, giả định paired outcome probabilities/variance, test/decision implementation và numerical artifact. Hypothesis viết một phía nhưng alpha ghi two-sided. N và effect size riêng chưa đủ suy ra power; không dùng những số này để chốt dataset size. Validation JSON còn mô tả margin 0.05 khác với expected difference 0.10 trong checklist.

Cần version draft, định nghĩa đúng arms trước; tách routing study khỏi fresh-restart manipulation trong cùng hệ RAT–CoT, ánh xạ worst-case dispatched attempts, rồi chuẩn bị power sensitivity trên giả định công khai. Các giá trị hiện tại chỉ có thể là đề xuất chưa xác minh. Human review, frame freeze, Stage 0 và quota vẫn đóng; reviewer không thay protocol hay chọn thêm tham số theo held-out.

## R9 — [P2] Same-document replay được báo thành unknown-history nhưng đầu vào là metadata

Vị trí: `audit/rat_cot_runtime_acceptance_20261020/same_document_legacy_fake/calls.jsonl:1–7` và raw `native_performance.json` cùng thư mục.

Tệp gọi là ledger thực tế là một pretty-printed metadata object với các trường kind/source/only_modified_field/replacement/no_real_inference. Không có completed request; cả 7 dòng đều không phải JSONL records hợp lệ. Runner count 7 malformed lines cho budget halt, báo `budget_halt_existing_ledger`, completed/unknown đều 0. Handoff/validation/pasted report lại ghi `budget_halt_existing_unknown_history` cho case này. Các test kế thừa chỉ assert “không dispatch” và historical real=0 nên vẫn pass.

**Bằng chứng:** `replay_fixture_probe.txt/xml`: 1 fail; `fresh_replays/commands.json` tái lập chính xác raw status. Reviewer tạo **fixture synthetic mới** từ captured legacy fake request, chỉ đổi document_path theo real history, trong `corrected_same_document_replay/`. Với đúng 1 request JSONL, runner báo unknown=1, real=0, new calls=0 và giữ ledger byte-identical. Finding này thuộc fixture/report bàn giao; không mở lại classifier fix đã đúng. Không sửa ledger nhận được để che sự khác biệt.

## Phần đã xác nhận

- 59/59 submitted source hashes và 47/47 artifact manifest entries khớp. Toàn bộ bytes trong thư mục acceptance được đối chiếu lại cuối review; production/source snapshot không đổi.
- Ledger 12 real calls lịch sử giữ SHA256 `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`.
- G1 reporting fix của overnight r7 hiện đúng trên **4/4 probes** trong consolidated suite: success/failure được tách trước chọn status, warm scope dùng success. Nghiệm thu giới hạn vào logic đã probe, không suy thành native acceptance/model quality.
- Safe JSON metadata roundtrip, pending/synthetic review guards được test, successful-path multi-call count trong fixture và missing-file handling đều có coverage hữu ích; các finding trên không phủ nhận các phần này.
- Candidate packet 13/13 pinned input/artifact hash checks khớp. Train/calibration/test: 36/71/70 groups; test 71 items/70 groups; không trùng group giữa splits hoặc với bốn exposed pools. Chỉ kiểm metadata/hashes, không in câu hỏi/gold held-out hoặc tune implementation theo chúng. Human review vẫn pending.

## Raw validation và giới hạn

| Lượt kiểm độc lập | Kết quả | Raw evidence |
| --- | --- | --- |
| Submitted consolidated suite | 372 pass, 0 fail/error/skip, pytest 68.22 s | `regression.txt/xml` |
| Mandatory research suite | 29 pass, subset của consolidated | `mandatory_research.txt/xml` |
| Parser/scoring | 44 pass | `parser_scoring.txt/xml` |
| Runtime/bundle/worker contract probes | 21 fail / 4 pass | `test_contract_probes.py`, `contract_probes.txt/xml` |
| Submitted same-document fixture | 1 fail | `test_replay_fixture_probe.py`, `replay_fixture_probe.txt/xml` |
| Supported fresh smoke | 12 mock calls / 3 authored groups / 0 real; 1,405 synthetic tokens | `fresh_smoke/`, `fresh_smoke.txt` |
| Five fresh fake CLI replays | exits 0; first dispatch 1 fake, remaining four dispatch 0; all real=0 | `fresh_replays/commands.json` |
| Corrected synthetic same-document replay | unknown=1, new fake/real=0, ledger preserved | `corrected_same_document_replay/validation.json` |

Five replays use newly generated outputs, not copied outputs relabeled as new runs. Copied submitted replay folders at review root support the original suite's artifact-reading tests and are identified separately. Same-document status mismatch is explicitly R9.

Initial sandbox attempts aborted on native PyQt6 import (exit 134); raw logs retained as `*_sandbox_abort.txt`. Offline Qt tests then ran outside sandbox. First redirected regression setup omitted two copied `.txt` fixture logs: 370 pass / 2 missing-file failures, saved in `regression_initial.*`; review runner copied the missing files, then all 372 passed. No production change was needed. `contract_probes_initial.*` preserves the first probe run; final probes additionally use realistic COT-success/partial-SC failure and positive controls.

0 real-model requests mới. Fixture/smoke costs là synthetic generated-token counts; full inference cost chưa đo. Timings ở đây là thời gian software tests, không phải online RAT latency. Không chạy full 132-file inventory hoặc native interactive model session. Không suy tổng active suite đều xanh từ 372 pass. Đóng R1–R9 cần source/fixture/doc repairs có hash mới và kiểm lại đúng hợp đồng, trước khi nâng mức nghiệm thu.
