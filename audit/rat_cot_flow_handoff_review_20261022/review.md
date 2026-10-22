# Review hai handoff trên cùng luồng RAT–CoT — 2026-10-22

**Kết luận:** xác nhận sửa R3 và metadata R10; R5 còn một lỗi P1 về binding tham số calibration. Phần hội thoại nhiều lượt mới là bản chuẩn bị, chưa phải implementation/acceptance hoàn tất. Bước triển khai tiếp theo là đưa context snapshot qua worker và cấu hình composition host hiện có, sau đó chứng minh chuỗi tương tác trong RAT. Không mở thêm dự án/controller DSA.

## Finding còn mở: [P1 / R5] Calibrator hữu hạn vẫn có thể lệch artifact đã duyệt

Vị trí: `reasoning/bundle.py:438–452`, snapshot trong `reviewed_source/reasoning/bundle.py`. Nhánh calibrated chỉ đối chiếu class và kiểm tra finiteness của Platt `a/b`; chưa đối chiếu learned state với artifact có digest trong bundle. Sửa chặn NaN và chặn calibrator trên bundle uncalibrated là đúng, nhưng chưa đủ để đóng R5.

Probe tạo **fixture được tác giả gắn metadata `approved`**, có fitted-policy JSON đầy đủ cost/performance và authored Platt state `a=0, b=-20`. Đây không phải policy thật đã được duyệt cho campaign. Validator chấp nhận baseline. Chỉ đổi live `calibrators[0].b` sang `+20`, giữ nguyên artifact, bundle và SHA-256: validator vẫn trả `is_valid=true, is_approved=true`. `should_escalate(0, 0)` đổi từ `true` sang `false`. Vì vậy cùng artifact được khai báo có thể dẫn tới quyết định dừng/tiếp tục khác do learned state chưa được ràng buộc.

Bằng chứng: `calibrator_parameter_binding.json`, assertion đầu trong `test_remaining_flow_contracts.py`, log/XML cuối `remaining_flow_v3.*`. Positive control artifact uncalibrated đầy đủ vẫn validate. Probe cũng chấp nhận việc validator từ chối schema calibration chưa được hỗ trợ ngay từ baseline; không ép production phải hỗ trợ schema tự đặt.

Yêu cầu sửa trong phạm vi R5 đã có: định nghĩa authoritative calibration representation, đối chiếu loại, thứ tự/số lượng phù hợp với policy, fitted state và toàn bộ learned parameters được dùng khi suy luận. Với định dạng/class chưa được hỗ trợ, từ chối rõ ràng. Kiểm lại trên đường factory/composition trước thực thi; hash file và kiểm tra số hữu hạn riêng lẻ không chứng minh live state khớp file. Chưa kích hoạt real policy trong lần review này.

## Sửa đã được xác nhận và giới hạn

| Mục | Kết luận độc lập | Bằng chứng |
| --- | --- | --- |
| R3 — dispatch accounting | Đóng trong phạm vi đã review. Đã bỏ suy đoán thêm failure từ `len(gens)>0`; lỗi ở stage ngoài generation không tạo request ma. | `reasoning/runtime.py:341–352`; r6 stage-error probes và các boundary probes đạt. |
| R5 — NaN/live state và uncalibrated | Hai phần sửa đạt; toàn bộ R5 vẫn mở do finding trên. | R6 probes đạt; finite calibration mutation vẫn fail ở probe mới. |
| R10 — lineage/metadata | Đóng trong phạm vi đã đối chiếu. 9 XML đúng **504 executions / 471 distinct identities / 33 repeats**; counts và stdout/XML durations khớp metadata. | `submitted_evidence_crosscheck.json`. |
| Regression 372 | Là baseline lịch sử được nhận và hash-pinned, không phải fresh full-checkout regression của source hiện tại. Không chạy lại hoặc cộng thành bằng chứng mới. | `received_runtime/regression.xml`, digest `de13ebdb…`; metadata nay ghi rõ lineage. |
| R12 — evidence lịch sử | Đã ghi nhận mất bản XML gốc ở r4. Có 146/147 entry khớp manifest gốc; actual digest đã sửa đúng. Không gọi đây là nguyên vẹn 100%. Không có thay đổi mới lên các review cũ trong lần này. | `integrity_initial.json`, `integrity_final.json`, incident đã nhận. |
| Unified request/UI bridge | 10 execution-flow tests và 1 composer → composed policy → same-conversation test đạt bằng synthetic backend. | `current_contracts.xml`. |

Bộ kiểm tra source hiện tại: **95 passed** (55 probe r2–r6, 29 mandatory research, 10 execution flow, 1 composer). Đây là kiểm tra hợp đồng phần mềm bằng fixture, không đo chất lượng model. Runner dùng adapter được nộp trong `received_runtime/redirect_plugin.py`: ngoài redirect outputs, nó version fake `_chat` seam cũ của r2 để ghi structured failed-generation fact khi fake seam ném lỗi. Do đó không diễn giải 3 ca r2 là chạy nguyên xi fixture cũ; r3–r6 cung cấp các kiểm tra độc lập bổ sung.

Bộ probe giới hạn còn lại, bản cuối v3: **2 failed / 2 passed**. Hai failures là finite calibration binding và context transport; hai controls là plain request identity/UNKNOWN và approved uncalibrated artifact. Bản đầu cũng ghi cùng hai khoảng trống. Bản v2 lỗi instrumentation khi serialize callback trong kwargs; đã giữ nguyên log, sửa serializer chỉ trong probe và chạy lại 4 ca. Kết luận context dựa vào v1 và v3; không dùng TypeError của v2 làm bằng chứng lỗi sản phẩm.

## Handoff hội thoại: đúng hướng, còn phần nối cần làm

Probe đi qua factory thật → `OnlineReasoningWorker` → composed controller → synthetic backend → `execution_response`. Request có history, `task_state` (mảng `[2,4,6,8,10]`, target 8) và tham chiếu turn-2. Backend chỉ nhận `Sao phải dùng mid + 1?`; kwargs chỉ có cancel/deadline. Response vẫn về đúng `exec-followup` / `turn-3`, không chạy fallback. Đây là **khoảng trống integration đã được kế hoạch xác định**, không phải lỗi mới phát sinh do bản chuẩn bị.

Source xác nhận factory truyền `request.query` và controls tại `rat/ui/assistant_worker.py:159–166`; worker giữ `query_to_solve=self.query` khi không có document và gọi `engine.solve` tại `rat/ui/reasoning_worker.py:127,155`. Việc đính `worker.execution_request` chưa tự đưa context tới suy luận. Bằng chứng quan sát: `reasoning_context_transport.json`. Chi phí 2 generated tokens trong fixture là số tác giả khai báo, không phải full inference cost; thời gian pytest không phải online model latency.

Trong source đã tìm, `ratReasoningEngine` / `ratAllowSyntheticPolicy` được app đọc, nhưng chỉ test gắn engine. Chưa có bằng chứng host production đã cấu hình một policy được duyệt; một ca composer không xác nhận cả chuỗi 7 bước.

Các quyết định áp dụng cho bản triển khai tiếp theo nằm trong `implementation_handoff.md`:

- “Đổi sang tìm 6”: tạo lượt chat mới, trỏ artifact/lượt nguồn và tạo revision mới khi commit thành công; giữ kết quả tìm 8. `target_revision` là revision nguồn. Ví dụ nguồn v1 → request `target_revision=1` → output v2; không gửi `target_revision=2` trước khi cập nhật.
- Tách quota=0, lỗi trước dispatch và lỗi sau dispatch. Chỉ trường hợp không dispatch mới có actual cost 0; giữ request và partial tokens đã phát sinh khi fail/cancel/timeout.
- Public `AgentResponse.answer_verification_status` giữ `UNKNOWN` khi chưa có checker DSA. Internal result có thể dùng `unverified`; kiểm mapping theo đúng lớp.
- Fixture chỉ chứng minh context/routing/lifecycle/presentation. Các yêu cầu “model hiểu mid+1” hoặc tuân thủ “chưa đưa code” cần acceptance model riêng khi được cấp budget. Giá trị trong schema minh họa không phải số đo.
- Lookback là điều hướng đã xác định thì không cần gọi model. Câu hỏi mới về kết quả cũ có thể cần suy luận; không tạo keyword router riêng để khớp câu ví dụ.

## Phạm vi và bảo toàn

Review không sửa production, tài liệu trước đó, audit đã nhận, audit r1–r6 hay Git history/remote. Patch được replay trên **bản sao** source r5 và cho ra digest đúng current source ở cả 3 file sửa. Giữ các thay đổi đang có của chat khác. Các file review mới nằm riêng trong thư mục này.

61/61 source entries của handoff và 91/91 manifest artifact entries khớp khi nhận. Hash 13 input/artifact trong fresh-data packet được kiểm bằng bytes, không in held-out queries/gold. Ledger lịch sử giữ SHA-256 `556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`. **0 model calls mới**, không tải model/network; Stage 0, independent human data review và execution authorization giữ nguyên. Xem `integrity_final.json` và `validation.json` cho kiểm tra cuối.
