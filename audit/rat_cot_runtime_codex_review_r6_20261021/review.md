# Independent Codex review r6 — RAT–CoT runtime repair

Bắt đầu 2026-10-21, hoàn tất 2026-10-22, Asia/Saigon. Giữ thư mục theo ngày bắt đầu; không sửa các review đã niêm phong trước đó.

**REQUEST CHANGES: còn 2 P1 (R3, R5) và 1 P2 (R10). Đóng R2 trong phạm vi software contract đã kiểm. R12 được xử lý bằng phục hồi counterexamples và ghi nhận mất XML; lỗi digest trong incident được gom vào R10.**

48 probes runtime kế thừa r2–r5 đều pass. Tuy nhiên, bộ boundary mới có **4 fail / 3 pass**. Bộ baseline hiện tại có **408 pass / 9 fail / 3 errors trên 420 cases**. Các failures rộng nằm ở UI/legacy AST checks, không phải các probes runtime mới. Không thể xác nhận claim toàn bộ checkout hiện tại đều pass từ các logs đóng gói.

## R3 — [P1, OPEN] Successful trace cộng lỗi strategy vẫn bị suy thành một request mới

Vị trí: [reasoning/runtime.py:341](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/reasoning/runtime.py:341).

Nhánh `after dispatch` đã được bỏ đúng. Nhưng nó được thay bằng một suy đoán khác:

```python
elif len(gens) > 0 and stop_status == "failed":
    extra_failed = 1
```

Một hoặc nhiều generation thành công không chứng minh một generation khác đã bắt đầu. Lỗi tokenize/format hoặc xử lý kết quả có thể xảy ra sau các successful generations mà không dispatch thêm request.

Probe chạy nguyên Qwen strategy và `_chat` source, với scripted stream provider và không tải model. CoT hoàn tất trước khi vào SC với 2 samples:

| Lỗi được inject | Requests thực tế | Ledger dispatched | Ledger failed | Tokens thực tế / ledger |
| --- | ---: | ---: | ---: | ---: |
| Format prompt của SC sample 2, trước stream | 2 | 3 | 1 | 2 / 2 |
| `_record_status` sau khi cả 2 SC samples hoàn tất | 3 | 4 | 1 | 3 / 3 |

Ở cả hai ca, trace chỉ có successful generations, `in_flight=false`, và không có failed generation. Operation thất bại là thật; failed model request được cộng thêm thì không có bằng chứng. Tokens hiện vẫn được bảo toàn đúng.

**Cần sửa:** ghi dispatch/outcome tại generation boundary bằng facts có cấu trúc, phân biệt lỗi strategy với lỗi model request. Bỏ suy đoán từ successful trace, tương tự yêu cầu bỏ suy đoán theo exception text. Không bắt buộc production giữ một actual count giả để vượt fixture cũ.

Seam r2 `scripted_chat` vẫn tăng counter rồi raise mà không ghi failed-generation hoặc in_flight fact. Như r5 đã nêu, cần version seam đó để cung cấp structured evidence khi thay contract; không thay một heuristic bằng heuristic khác để giữ historical expectation xanh.

Bằng chứng: [native_stage_error_between-samples.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r6_20261021/native_stage_error_between-samples.json), [native_stage_error_after-samples.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r6_20261021/native_stage_error_after-samples.json), [raw boundary probes](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r6_20261021/trace_and_calibrator.txt).

## R5 — [P1, OPEN] Live constant NaN và active calibrator chưa khai báo vẫn được approved

Vị trí: [live constant comparison](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/reasoning/bundle.py:284), [calibrator validation](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/reasoning/bundle.py:421).

Các ca missing/intercept/NaN-artifact của r5 đã được reject đúng. Authoritative-artifact presence check cũng chặn được hai JSON rỗng hoặc non-JSON artifact duy nhất. Hai lỗ hổng còn lại được tái hiện trên artifact đầy đủ cost/performance fields, có file thật và SHA-256 khớp bytes:

1. **Live performance constant thành NaN.** Artifact vẫn ghi constant hữu hạn đúng ban đầu. Validator kiểm `np.isfinite` trên giá trị artifact, nhưng so với live value bằng `abs(artifact-live)>epsilon`. Khi live value là NaN, phép so trả false. Validator trả `is_valid=true`, `is_approved=true`, không errors/warnings; predictor score đầu tiên thành NaN. Đây là live-state mutation trước validation, không phải mutation sau khi controller đã được duyệt.
2. **Bundle khai báo uncalibrated nhưng live policy có active Platt calibrator.** Bundle giữ `calibrator_type=None`, `calibrator_semantics=raw_confidence_uncalibrated`, artifact không đổi. Inject calibrator đã fit trên bốn authored synthetic rows rồi thay parameters của nó; validation vẫn approved. Với cùng confidence=0, `should_escalate` đổi từ **true sang false**. Code hiện chỉ kiểm calibrators khi bundle.calibrator_type khác None, nên không phát hiện extra active calibration.

**Cần sửa:** kiểm tính hữu hạn của cả artifact và live state trước khi so sánh. Binding cần bao phủ toàn bộ decision state: khi metadata nói uncalibrated thì live policy phải thực sự không calibrate; khi có calibrator phải xác minh type, số lượng, fitted state và parameters đã review. Không chỉ kiểm type của object. Dùng schema/version rõ ràng cho defaults; hardcoded fallback `[1,0,0]` không thay thế được full provenance contract.

Positive control mới có cost/performance state khớp và không có calibrator; nó vẫn validate thành công. Các ca artifact finite của r5 cũng pass. Review không suy chất lượng mô hình từ các fixture này.

Bằng chứng: [approved_state_live-nonfinite-constant.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r6_20261021/approved_state_live-nonfinite-constant.json), [approved_state_undeclared-active-calibrator.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r6_20261021/approved_state_undeclared-active-calibrator.json).

## R10 — [P2, REOPENED] Counts khớp nhưng lineage, timings và incident digest chưa nhất quán

Vị trí: [commands.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_acceptance_20261020/commands.json), [handoff.md](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_acceptance_20261020/handoff.md), [r4 incident](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_acceptance_20261020/r4_baseline_xml_incident.json).

R10 trước đây chỉ được đóng trong phạm vi package counts. Lượt này cần mở lại phần accuracy của nghiệm thu/bằng chứng:

- `regression.xml` 372 pass/37.51s **byte-identical với file đã nhận ở đầu r5**, trước repair hiện tại. SHA-256 `de13ebdbbccfe16864884c777dd2433d6951266c195c44e8b6ea1773808f5d1e`, timestamp 2026-10-21 11:28:10 +07:00. Nó có thể được giữ làm historical regression evidence, nhưng không phải một fresh run gắn với source freeze mới. Ba core files đã đổi so với snapshot r5; patch replay xác nhận điều đó.
- Tổng tám XML là **497 lượt thực thi**, nhưng chỉ **464 distinct (classname, test name) identities**; 33 lượt lặp do mandatory research 29 và G1 4 đã nằm trong 372. Cần ghi rõ đơn vị, không mô tả 497 như 497 tests độc lập. Vấn đề chính vẫn là claim zero failures cho latest checkout chưa được thiết lập.
- Ba durations trong commands/handoff khác raw logs, dù counts đều đúng:

| Suite | Khai báo (s) | Raw stdout (s) | XML (s) |
| --- | ---: | ---: | ---: |
| r2 Qwen replay | 3.18 | 2.94 | 2.941 |
| r4 remaining contracts | 3.64 | 3.33 | 3.324 |
| r5 binding/dispatch | 2.98 | 4.20 | 4.184 |

- Incident XML r4 ghi `actual_sha256=548a8a33fa8134789ba855799c8577da7b9ec598f8fc23ae7355153fb5ea6857`, trong khi received file thực tế có digest **`548a8a33352b56f41aa85d06b5e7c17a6818aa637e33f9fde317bbae295125bb`**. Original expected digest `5ddaf8a3...` vẫn được giữ đúng. Cần sửa digest thực tế trong incident mới, không sửa original manifest hoặc lịch sử để làm khớp.

**Cần sửa:** phân biệt historical logs với fresh source-pinned runs; công bố failures/current-scope limits; đồng bộ metadata từ raw artifacts và dùng đúng đơn vị test executions/distinct cases. Giữ nguyên received logs/XML, lưu phiên bản nghiệm thu mới. Không cần sửa UI hoặc ép legacy tests xanh chỉ để cập nhật báo cáo trung thực.

Verifier của reviewer ban đầu còn assert rằng mọi declared duration phải khớp; nó phát hiện ba lệch trên và dừng. Log này được giữ riêng. Verifier cuối ghi chúng như findings, không giả định package timing metadata đúng.

Bằng chứng: [submitted_evidence_crosscheck.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r6_20261021/submitted_evidence_crosscheck.json), received artifacts và baseline mới của r6.

## Các phần có thể đóng hoặc giữ đóng

- **R2 CLOSED, software scope:** Qwen nhận react_max_turns và forward vào loop; settings được đồng bộ trong controller. Các request/token-cap probes r5 đều pass cùng SC/ToT controls trước đó. Native hardware/MLX enforcement chưa được đo, không phát sinh model call để mở rộng kết luận.
- **R12 RESOLVED WITH LOSS RECORDED:** r1 81/81, r2 102/102, r3 115/115, r5 156/156 entries khớp original manifests. r4 146/147 khớp; sai khác duy nhất là XML đã được ghi nhận mất original. Hai counterexamples r4 trước đây lệch hash đã được phục hồi đúng. Không đòi tái tạo timings không còn dữ liệu; lỗi digest incident thuộc R10 ở trên. Không báo toàn bộ lịch sử 100% nguyên vẹn.
- **R1/R4/R6/R7/R8/R9/R11/G1:** giữ các kết luận đóng trong scope trước đây. Không dùng các closures này để tuyên bố native interactive acceptance, data review hoặc Stage 0 đã hoàn tất.
- **Patch packaging:** unified patch nay chứa đủ qwen_mlx_backend.py, reasoning/runtime.py và reasoning/bundle.py. Reviewer apply vào bản sao r5 dưới `r6/patch_replay_source/`, không chạm production; cả 3 outputs khớp SHA-256 current source. Xem [patch_replay.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r6_20261021/patch_replay.json).

## Kiểm thử và phạm vi checkout hiện tại

| Hạng mục | Reviewer r6 |
| --- | --- |
| Baseline, 372 + 48 historical runtime probes | 408 pass / 9 fail / 3 errors trên 420 cases, 44.88s |
| Historical runtime probes trong baseline | r2 3 + r3 19 + r4 14 + r5 12 = 48 pass |
| Mandatory research / native readiness / G1 | 29 / 8 / 4 pass, đã nằm trong baseline |
| New trace/live-state probes | 4 fail / 3 pass, 2.78s |
| Backend/strategy/scoring | 68 pass / 2 skip, 3.87s; skips cần native MLX bfloat16 |
| Submitted artifact manifest | 85/85 khớp; 86 received files không đổi trong review |
| Submitted source manifest | 56/61 khớp ngay khi nhận và cuối review |
| Reviewer source snapshot | 71/71 không đổi, gồm cả lúc tiếp tục ngày 2026-10-22 |
| Pinned candidate data/artifacts | 13/13 khớp; human review pending |
| Historical changes do r6 | 0; known lost r4 XML vẫn giữ original manifest entry |

Chín failures rộng gồm 8 UI assertions (Finder viewport/keyboard/focus, result-card/bubble visibility) và 1 legacy AST seam tìm constant 25 không còn khớp. AST failure xảy ra trước khi tính golden scores; không suy một measured ranking regression từ nó. Ba errors là assertions khi setup fixture QA vẫn đòi câu trả lời nằm trong bubble, trong khi bubble hiện trả thông báo đặt kết quả ở trên. Đây không phải lỗi missing-file do runner.

Năm source/test files đã khác submission manifest ngay khi bắt đầu: `rat/ui/omnibar.py`, `rat/ui/workbench.py`, `test_qwen_mlx_backend_mocked.py`, `tests/test_rat_magic_ui.py`, `tests/test_reranker_golden.py`. Reviewer không sửa các parallel UI/ranking changes và không tự quyết định liệu mỗi legacy expectation còn đúng. Các broad failures được ghi nhận riêng, không quy chúng cho runtime repair chỉ từ tên test.

Runner chuyển fixture outputs và JUnit target sang r6. Qt chạy offline trên host vì Qt abort trong sandbox; new Qwen probes loại MLX imports, bỏ qua constructor tải weights, giữ nguyên strategy/stream-loop source và dùng scripted token provider. Các calibrator rows là authored synthetic, không phải held-out data.

Reviewer chỉ thêm hồ sơ trong r6, không sửa production hoặc historical reviews, không commit/branch/push/pull/reset/force. Git apply chỉ tác động bản sao patch-replay. Nhánh main giữ nguyên. Git status xuất hiện thêm docs/prototype/preview files ngoài scope; chúng được giữ nguyên. Ledger 12 calls lịch sử giữ SHA-256 `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`; **0 real-model calls mới**.

Không in held-out queries/gold, không fit/tune theo candidate data. Structural review chỉ kế thừa qua pinned hashes; human review, Stage 0 và native interactive acceptance vẫn pending. Generated-token costs trong probes là synthetic; timings là software-test wall time, không phải full inference costs hoặc measured online latency.

Hồ sơ tái lập: [commands.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r6_20261021/commands.json), [validation.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r6_20261021/validation.json), [integrity_final.json](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_runtime_codex_review_r6_20261021/integrity_final.json), raw logs/XML, source snapshots, case JSONs, received package và artifact_manifest. Cần xử lý R3/R5 và sửa evidence metadata R10 trước khi tuyên bố đóng toàn bộ findings.
