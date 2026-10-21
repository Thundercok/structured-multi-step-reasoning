# Independent Codex review r2 — repair R1–R9, 2026-10-20

**Verdict: REQUEST CHANGES. R1 và R9 đã đóng trong phạm vi kiểm tra. R2–R8 mới được sửa một phần; có thêm R10 về gói bằng chứng sửa đổi. Còn 5 finding P1 và 3 finding P2.**

Bộ hiện tại có **398/398 pass** = 372 tests bàn giao + 26 probes reviewer cũ. Counterexamples mới có **22 fail / 3 pass trên 25 cases**, gồm 20/22 failures của general contracts và 2/3 failures của replay logic Qwen. Đây là các checks offline, không phải model-quality evidence. Reviewer không sửa production hay hồ sơ nhận được.

## Phần đã đóng và phần sửa có hiệu lực

| ID | Quyết định r2 | Bằng chứng / giới hạn |
| --- | --- | --- |
| R1 | **CLOSED** | Giá trị 0 được giữ riêng khỏi None, chặn trước embedding/generation; 6 zero-quota probes cũ pass. Kiểm tra kiểu/ngân sách không âm cũng đã thêm. |
| R2 | OPEN — P1 | Có forward max_tokens nếu signature hỗ trợ, nhưng hard cap vẫn là clamp số liệu sau generation; phát sinh undercount. |
| R3 | OPEN — P1 | Exception hiện mang ledger và worker forward được fixture schema mới. Chưa tương thích trace Qwen thực tế; observation-validation errors còn mất ledger. |
| R4 | OPEN — P1 | Stop check sau terminal strategy đã đúng; callbacks đến được double có kwargs. Qwen chưa hỗ trợ hooks; cooperative cancellation/timeout exception bị ghi thành error/failed. |
| R5 | OPEN — P1 | Version whitelist, dimensions, finite values, nonempty dictionaries đã được kiểm. Danh tính/hashes/settings thực tế chưa được đối chiếu. |
| R6 | OPEN — P1 | Đổi nội dung làm thay size/mtime được phát hiện. Document context vẫn bị bỏ qua; thay nội dung giữ size/mtime chưa phát hiện. |
| R7 | OPEN — P2 | Step signal, fixture hooks và telemetry wording đã tốt hơn. Outside-excerpt, stale-result suppression và native workflow claims còn vượt coverage. |
| R8 | OPEN — P2 | Tách ngân sách single-call/multi-call và có script power là tiến bộ. Summary cỡ mẫu sai với chính công thức; định nghĩa F chưa khớp adapter. |
| R9 | **CLOSED** | JSONL mới khớp byte với corrected synthetic request của reviewer trước; completed/unknown=1, status unknown-history, real=0. Probe cũ pass. Không coi đây là model thật hoặc một replay mới của lượt r2. |
| R10 | NEW — P2 | Raw log, XML, validation và patch/source map của repair chưa đồng bộ. |

G1 reporting fix của overnight r7 tiếp tục pass 4/4 probes trong bộ 398; không mở lại finding đó. Default singleton giữ controller-free là đúng với approval boundary hiện tại.

## R2 — [P1] Clamp làm mất số token đã sinh, hard cap chưa chặn generation

Vị trí: `reasoning/runtime.py:244–255`, `291–295`, **348–358**.

Backend không có max_tokens vẫn được dispatch khi caller yêu cầu cap. Sau khi backend trả tokens, code dùng `min(tokens, remaining)` để ghi observation/ledger. Một double sinh **40 tokens**, cap 1, kết quả ghi **1 token**. Với SC nhận max_tokens theo từng generation, COT sinh 2 rồi 5 subcalls × 4 tokens = **22 tokens thực tế**, cap 6, ledger chỉ ghi 6.

Đã kiểm thêm **chính QwenMLXBackend.run/_cot/_self_consistency từ AST source**, thay duy nhất generation seam bằng scripted fixture, không chạy __init__, không import MLX và không load weights. COT phát 20 fixture tokens, cap 1, trace `tokens=20` nhưng ledger `generated_tokens=1`. Vì native run chưa nhận max_tokens từ controller, kwargs inspection bỏ qua cap.

Bằng chứng: 3 failures đầu của `general_contracts.txt/xml`; `qwen_token_cap_case.json`; `test_qwen_boundary_replay.py::test_actual_qwen_cot_does_not_underreport_over_budget_generation`.

**Cần sửa:** giữ nguyên chi phí quan sát được; cap/reserve remaining budget ở từng generation dispatch, bao gồm mọi SC/ToT/ReAct subcall. Backend thiếu capability phải bị từ chối trước dispatch cho hợp đồng hard cap, hoặc caller phải chọn rõ chế độ không có hard cap. Khi backend vi phạm cap, báo violation cùng raw cost đầy đủ; không sửa cost để vừa trần.

## R3 — [P1] Ledger sau lỗi chưa tương thích trace của backend chính

Vị trí: **`reasoning/runtime.py:299–309`**, `341–346`; `qwen_mlx_backend.py:294–305`.

Nhánh mới đọc `completion_tokens` và `status='success'`. Qwen `_chat` dùng trường **tokens**, không có status, và chỉ append trace sau generation thành công. Failed generation đã dispatch không có entry. Vì vậy không thể dùng len(completed-generations) làm số attempts hoặc coi missing status là failure.

Replay AST của native strategy: COT thành công 20 tokens, hai SC generations thành công thêm 40, generation thứ ba của SC lỗi sau dispatch. Quan sát thực tế **4 dispatched / 3 succeeded / 1 failed / 60 tokens**. Controller ghi **3 dispatched / 1 succeeded / 2 failed / 20 tokens**. Đây là lỗi schema/dispatch boundary có thể tái lập mà không chạy model.

Ngoài ra, validate answer/confidence/token diễn ra ngoài try/except gắn ledger. Backend sinh 40 tokens nhưng trả confidence NaN thì ValueError không mang cost_ledger, worker tiếp tục mất chi phí.

Bằng chứng: `qwen_failure_case.json`; `test_actual_qwen_strategy_failure_preserves_generation_costs`; `test_failure_accounting_accepts_actual_qwen_trace_schema`; `test_invalid_observation_preserves_dispatched_request_ledger`.

**Cần sửa:** thống nhất trace schema có attempt start/completion, IDs và outcome/tokens; ghi dispatch trước generation, kể cả failed/cancelled request. Đưa mọi failure path sau dispatch, gồm output validation, vào finalization mang partial ledger. Không suy số dispatch từ completed trace và không gán success/failure theo trường backend chưa cung cấp.

## R4 — [P1] Hook mới chưa hoạt động trên Qwen; cooperative stop bị đổi thành error

Vị trí: `reasoning/runtime.py:244–255`, `296–325`; **`rat/ui/reasoning_worker.py:174–206`**; `qwen_mlx_backend.py:108`, `261`.

Terminal success path đã kiểm stop state đúng. Tuy nhiên native Qwen `run(strategy, query)` và vòng prefill/decode vẫn không nhận/poll cancellation hoặc deadline của controller. Signature inspection chỉ bỏ qua kwargs không được hỗ trợ, nên không xác lập được capability mà handoff đang claim.

Khi một backend thực sự hỗ trợ callback và ném exception để dừng decode, nhánh chung ghi ledger.status=failed và worker emit error/response.status=error. Hai QThread probes kích hoạt requestInterruption hoặc hết deadline bên trong backend đã tái hiện việc mất ngữ nghĩa cancelled/timeout; cả hai vẫn giữ 7 fixture tokens nên có thể và cần bảo toàn cost khi phân loại đúng stop.

Bằng chứng: `test_qwen_strategy_entrypoint_exposes_claimed_execution_controls` (AST check, không MLX import), `test_worker_classifies_cooperative_stop_exception[cancel/deadline]`.

**Cần sửa:** capability/context contract được native backend thực thi ở prefill/decode và giữa subcalls; từ chối hợp đồng in-flight cancel/deadline nếu adapter chưa hỗ trợ. Tách cancellation/timeout khỏi backend faults, giữ ledger và status đúng ở cả exception path lẫn return path. Không dùng Future.cancel hoặc QThread flag như bằng chứng hard preemption.

## R5 — [P1] Validator dùng blacklist literal, chưa xác minh tương thích/provenance

Vị trí: **`reasoning/bundle.py:130–149`**, `230–254`.

Model ID/snapshot mới chỉ bị từ chối khi đúng chuỗi incompatible/unsupported/invalid; prompt profile chỉ kiểm whitelist. Không có phép so bundle với backend.model_id/model_snapshot/prompt_profile. Nonempty provenance dictionaries chưa kiểm hash contents hoặc fitted parameters/settings.

Probe dùng approved metadata **chỉ là fixture**, review_scope không chứa synthetic và matching backend metadata làm positive control. Sau đó đổi từng trường sang repository B, revision B, một profile khác nhưng có trong whitelist; hoặc thay source/artifact hashes bằng digest sai, SC/ToT settings=99, predictor kind và token semantics khác. **8/8 mismatch cases vẫn được chấp nhận.** Không dùng lại các blacklist literal của probe cũ.

Các negative cases approved của probe cũ còn giữ synthetic review_scope, nên guard mới có thể từ chối chúng trước khi kiểm trường cần kiểm. 26/26 xanh chưa đủ chứng minh các validation branches độc lập.

Bằng chứng: 8 parametrizations `test_approved_metadata_mismatch_is_not_just_a_literal_blacklist`, positive control `test_control_matching_fixture_and_no_cap`.

**Cần sửa:** ràng buộc review-approved metadata với runtime identity/capabilities thật và nội dung fitted artifact được hash; xác minh prompt/strategy settings, schema/cost semantics. Tests cần matching approved control rồi thay một field và kiểm đúng lý do reject. Bộ source/artifact hash là dữ liệu cần đối chiếu, không chỉ một dict không rỗng.

## R6 — [P1] Tài liệu chưa đi vào reasoning; integrity check bỏ lọt thay đổi

Vị trí: `rat/ui/reasoning_worker.py:95–101`, **129–151**.

Worker vẫn gọi engine chỉ với query, không có document content/source context. Tệp hiện hữu và ổn định cho câu trả lời chung `completed` dù backend chưa nhận một byte nội dung. Snapshot hash giải quyết một phần mutation detection, chưa giải quyết việc trả lời theo selected document.

Recheck chỉ hash lại nếu size hoặc mtime thay đổi. Probe thay nội dung AAA → BBB, giữ số bytes và khôi phục mtime bằng os.utime: nội dung khác nhưng kết quả vẫn completed. Các thao tác copy/restore có thể bảo toàn metadata; saved hash hiện không được so trong trường hợp này.

Bằng chứng: `test_existing_document_is_used_or_explicitly_rejected`; `test_same_size_and_mtime_document_mutation_is_still_detected`.

**Cần sửa:** route selected-document execution sang QA với source identity/context được cung cấp, hoặc từ chối document mode trong strategy worker. Revalidation phải dựa trên content identity cần bảo vệ, fail closed khi snapshot thất bại; giữ QA backend tách khỏi LLMBackend strategy.

## R7 — [P2] Acceptance còn claim outside-excerpt/stale suppression chưa được kiểm

Vị trí: `tests/test_native_acceptance_readiness.py` cases 4/6/8; **`audit/rat_cot_runtime_acceptance_20261020/native_acceptance_matrix.md:18–20`**; `handoff.md:13`; `validation.json` stale_results/cases_verified.

Đã xác nhận step_completed thật sự được nối qua engine/controller; telemetry unmeasured và default-singleton scope đã được mô tả rõ hơn. Prefill/decode double tests nay nhận được controller callback, phù hợp phạm vi fixture hook.

C6 vẫn gọi PAL thiếu dữ kiện, không gọi document QA/outside-excerpt và không có prior PASS turn. C8 chỉ nhận result generation=2 và tự viết điều kiện local chấp nhận current result; không bơm stale result qua production UI consumer. Matrix vẫn ghi expected delayed callback discarded; validation vẫn ghi stale results suppressed. C4 chỉ cancel trước dispatch, không chứng minh resource cleanup sau generation bị hủy. Handoff vẫn gọi toàn workflow fully verified.

**Cần sửa:** giới hạn claim đúng vào step progress, result ID binding, cold pre-cancel re-ask và PAL fallback đã kiểm. Giữ document outside-excerpt, stale-result suppression và post-inflight-cancel cleanup pending cho đến khi có tests qua đúng production boundaries. Không cần bật policy chưa review vào singleton/UI để sửa wording này.

## R8 — [P2] Power summary hardcode N sai; định nghĩa fresh F còn lệch adapter

Vị trí: **`scripts/calculate_power_sensitivity.py:111–112`**, `data_review_checklist.md` phần power/Study 1; `unauthorized_real_execution_plan.md` arm F; `experiments/cot_restart_fresh.py:83–118`.

Power artifact có thể tạo lại **byte-identical**, nhưng hai giá trị summary N=125 và N=498 được hardcode, không tính bằng hàm power. Với đúng p_discordant=0.30, alpha hai phía=0.05 mà script dùng:

| Delta | N ghi là đủ 80% | Power từ chính hàm tại N đó | N nhỏ nhất đạt 80% trong chính approximation này |
| --- | ---: | ---: | ---: |
| 0.10 | 125 | **0.532389** | **236** |
| 0.05 | 498 | **0.530764** | **942** |

`power_crosscheck.json` và hai power probes fail ghi lại phép đối chiếu. Các N=236/942 ở đây chỉ xác minh tính nhất quán của approximation được nộp, **không phải đề xuất cỡ mẫu, power validation cho practical margin, hoặc execution freeze mới**. Không dựa vào chúng để mở data/model gate.

Tách ngân sách 280 single-call arms khỏi routing ladder đã sửa nhầm lẫn subcall chính. Tuy nhiên draft gọi F là generation from scratch / cache manipulation, trong khi build_request F tiếp tục từ prefix của O tại requested q=0.50; CONT dùng full reasoning prefix; A là nhánh không prefix cùng user CoT prompt. Cả ba thực thi với fresh per-call cache trong adapter. Cần ghi chính xác prompt/prefix/sampling/IDs/cost mapping của source, không diễn giải F thành no-prefix hoặc suy riêng causal effect của cache từ một contrast chưa định nghĩa như vậy.

**Cần sửa:** derive sample-size summaries bằng cùng solver/công thức và kiểm target; công khai approximation/null/margin/discordance assumptions. Đồng bộ arms với canonical adapter, phân biệt smoke settings khỏi preregistration. Giữ blind review và Stage 0.

## R10 — [P2] Gói raw evidence và patch chưa khớp snapshot repair

Vị trí: `audit/rat_cot_runtime_acceptance_20261020/regression.txt`, `regression.xml`, `validation.json`, `repair_diff.patch`, `source_end.json`.

- XML mới có 372 pass và time 79.897 s, phù hợp một run mới. Nhưng regression.txt vẫn byte-identical với log trước repair, ghi **89.80 s**; validation cũng giữ 89.80. Handoff mới ghi 79.97. Không ghép các artifacts này thành cùng một raw run đã được xác minh.
- Parser/scoring raw log/XML vẫn là bộ 44 trước sửa. Handoff nêu các lượt riêng 69 tests (19.97 s), 29 tests (8.36 s) và 26 probes, nhưng gói không có command/raw log/XML riêng để đối chiếu các lượt và thời gian đó. Bộ 29 có coverage trong XML consolidated; reviewer r2 đã chạy lại 69 và 26 độc lập. Thiếu raw riêng không chứng minh các lệnh chưa từng chạy; cần phân loại rõ bằng chứng kế thừa/subset và các lượt đã báo.
- repair_diff.patch nay chỉ có **rat/engine/meta_reasoner.py**. Các sửa cốt lõi runtime.py, bundle.py, reasoning_worker.py, native-readiness tests và power script không có trong patch. Source_end chứa 59 file nhưng không pin script power mới.

Bằng chứng: `repair_evidence_crosscheck.json`, `raw_run_metadata.json`, snapshot `received_artifacts/`. Reviewer đã tạo raw checks mới cho source hiện tại, song không relabel các run reviewer thành run gốc của repair.

**Cần sửa:** lưu logs/XML/argv/exit codes trong audit repair có version riêng, dẫn đúng source hashes và phân biệt subset/overlap; ghi rõ log cũ được kế thừa. Xuất patch đầy đủ so với snapshot review trước, hash cả generator power và các artifacts. Giữ raw trước sửa có thể phục hồi, không thay những file cũ bằng manual summary.

## Integrity, kiểm thử và phạm vi

- **59/59** source hashes bàn giao và **48/48** artifact entries khớp lúc bắt đầu. Tất cả manifest entries của review trước vẫn nguyên; r2 snapshot riêng incoming artifacts và source trọng yếu.
- Candidate packet tiếp tục khớp 13/13 pinned input/artifact hashes. Structural overlap/counts của review trước được kế thừa theo hashes, không phải human approval mới.
- Ledger 12 calls lịch sử giữ SHA256 `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`.
- **398 pass**: bộ gốc 372 cùng 26 probe cũ. Mandatory research 29, readiness 8, bundle 11 và G1 4 đều là subsets, không cộng trùng.
- **25 probes mới: 22 fail / 3 pass**. General contracts 20 fail/2 pass; Qwen AST boundary replay 2 fail/1 pass. Failure counts là các counterexamples cho 5 nhóm runtime P1 và power, không phải 22 findings riêng.
- Parser/scoring **44/44 pass** và bộ bổ sung được báo **69/69 pass**, chạy riêng; subsets/overlap không được cộng thành independent total. Lần đầu bộ 69 lỗi import Metal trong sandbox (exit 2). Lượt xin host run hết hạn xét duyệt tự động trước khi spawn; retry một lần thành công, 69 pass trong 14.27 s. Raw error và retry output đều được giữ.
- Power generator được chạy với output path đổi **trong memory** sang review folder; file nộp không bị ghi đè. Source Qwen chỉ được replay logic với generation seam scripted; không khởi tạo model, không inference, không import native MLX trong replay này.
- Không in câu hỏi/gold held-out, không tune theo chúng. Human review 71/70 tiếp tục pending; Stage 0 chưa đổi; quota model thật=0. Không có model calls thật mới, Git mutation hoặc production fix của reviewer.
- Source hoặc startup thay đổi ở chat khác trước review chỉ được ghi nhận/preserve qua hash; review này không nghiệm thu toàn bộ application startup hay full active suite. Software test timings không phải online latency; fixture token counts không phải full inference cost.

Hồ sơ kiểm tra cuối: `validation.json`, `source_start/end.json`, `integrity_final.json`, `commands.json`, `artifact_manifest.json`. Chỉ đóng toàn bộ repair sau khi các remaining contracts có bằng chứng đúng boundary và gói raw phản ánh đúng snapshot.
