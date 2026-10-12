# Proposed ADR: NeSy hỗ trợ suy luận trong RAT

**Status:** Proposed; review hướng tiếp cận, chưa duyệt implementation.
**Date:** 2026-10-12, Asia/Saigon.
**Decider:** Người dùng, trước giai đoạn triển khai tiếp theo.

## Context

Người dùng xác nhận vẫn phát triển RAT và luồng suy luận của Chuột; muốn xem
NeSy có thể hỗ trợ gì. Giữ một ô chat, mascot, ghi chú theo lượt và compact/full.
Gemini đang tinh chỉnh UI; review này không đổi source UI, runtime, model,
controller fitting hoặc scope/gate nghiên cứu. DocAI tiếp tục đứng riêng.

Mục tiêu hữu ích là Chuột nhận phản hồi kiểm tra có căn cứ để sửa kết quả,
tiếp tục tìm dữ kiện hoặc hỏi thêm. Chỉ thêm công cụ hay badge "verified" chưa
tạo ra vòng phản hồi đó.

## Current implementation

- `rat/ui/assistant_worker.py` gọi `AssistantRuntime.run`. Vòng chạy này dùng
  model thật để đề xuất tool/final answer. Nhánh final tại
  `rat/engine/assistant_runtime.py:722` hiện trả lời trực tiếp; chưa có gate
  chung kiểm tra từng claim của final answer.
- `rat/engine/controller.py:160` hiện quyết định ALLOW/FORCE_STOP cho một số
  action trên trạng thái đã có; chưa nhận PASS/FAIL/UNKNOWN của verifier.
  Controller chưa fit thì cho quyết định model đi qua. Không giả định đã có
  learned policy tốt chỉ vì class tồn tại.
- `rat/engine/vgc.py` có verifier/cascade cũ. Reranker dùng checker tài liệu;
  không thể kết luận mọi câu trả lời chat đã đi qua VGC.
- `scripts/verifiers.py` có ba trạng thái nhưng là checker cho rationale phát
  triển nghiên cứu, với scope riêng. Ordering certificate verifier cũng có
  parser/giới hạn bài toán riêng; chưa là verifier tổng quát cho RAT.
- `rat/engine/work_trace.py` hiển thị kế hoạch được gắn nhãn và các thao tác,
  kết quả quan sát được. Đây là điểm nối để hiện bước kiểm tra/sửa thật.
- `modules/docai/nesy_docai/system2_solver.py` giải các ràng buộc hóa đơn.
  RAT default registry không đăng ký DocAI. Invoice SAT không kiểm chứng được
  lịch học, phép suy luận tự do hay tính đúng nghĩa của câu trả lời tài liệu.

## Evidence from offline counterexamples

`reproduce.py` gọi các checker hiện có, không gọi model. Xem `reproduce.txt`.

| Input | Actual | Giới hạn được chứng minh |
| --- | --- | --- |
| Nguồn: Alice 100, Bob 20; claim: Bob 100; snippet tồn tại trong nguồn | VGC document VALID | Số xuất hiện trong nguồn không xác thực quan hệ chủ thể–giá trị. |
| Target `2 + 2`; code `print(999)`; witness 999 | VGC calculation VALID | Output khớp code không chứng minh code giải đúng target. |
| Rationale `2 + 2 = 4`, final `Answer: 999` | Arithmetic rationale VALID | Các bước phép tính đúng không bảo đảm kết luận cuối đúng. |

Đây là phản ví dụ cho phạm vi claim, không phải ước lượng tỷ lệ lỗi hoặc chất
lượng model. Với scope hẹp "program output reproduced" hay "equations checked",
một checker có thể làm đúng việc của nó; không được nâng thành PASS toàn tác vụ.

VGC quantitative cũng trả `tokens=45`, `confidence=0.99` viết sẵn. Nhánh
"deep escalation" gọi lại `safe_calculate`, không gọi model sâu. Các metadata
này không được dùng như inference cost, confidence đã hiệu chỉnh hoặc bằng chứng
Chuột thực sự suy luận lại. Cần sửa claim/metadata trong một lượt implementation
được chốt riêng, trước khi tái dùng cascade đó.

## Decision proposed

Dùng **LLM đề xuất → kiểm tra phần có contract → phản hồi lỗi cụ thể → LLM
sửa hoặc tìm thêm dữ kiện → kiểm tra lại → trả kết quả** trong core RAT.

Verifier trả `claim_id`, `scope`, `status`, `reason`, evidence/source revision,
các ràng buộc đã kiểm tra và phần chưa kiểm tra. PASS chỉ áp dụng cho claim
trong scope; schema hợp lệ không có nghĩa dữ liệu đúng, SAT không bảo đảm nghiệm
duy nhất, và trích dẫn tồn tại không bảo đảm diễn giải đúng.

Điểm nối đề xuất là contract của operation/artifact, không bảng keyword cho từng
câu hỏi. Capability khai báo checker phù hợp; runtime tự thực thi khi cần,
không phụ thuộc việc model có nhớ gọi tool kiểm tra hay không. Model vẫn hiểu
yêu cầu, đề xuất kế hoạch, hành động và cách giao tiếp.

- **PASS:** cho phép dùng claim trong phạm vi đã kiểm tra; không duyệt tự động
  mọi phần khác của câu trả lời.
- **FAIL:** đưa vi phạm cụ thể về model để sửa, không báo tác vụ đã thành công.
- **UNKNOWN:** giữ phần chưa biết; có thể đọc thêm, hỏi một dữ kiện cần thiết
  hoặc trả lời có giới hạn. Không mặc định chạy một model đắt hơn mọi lần.

Budget/controller quyết định có đáng chạy tiếp không. Budget exhaustion không
biến FAIL/UNKNOWN thành PASS. Giới hạn sửa/recheck hữu hạn và đo các call/tool
thật. Muốn đưa verifier features vào learned controller cần data, phiên bản
feature mới và fitting/review riêng; không tái dùng artifact đã fit như thể
feature semantics không đổi.

## Options considered

| Option | Assessment |
| --- | --- |
| Import nguyên invoice solver vào RAT | Không phù hợp scope người dùng: thêm DocAI nhưng không giải nhu cầu kiểm tra suy luận chung. |
| Checker theo contract dùng chung vòng phản hồi | Đề xuất: kiểm tra chính xác phần có thể formalize, cùng UI/cơ chế thực thi hiện có; cần checker riêng và bằng chứng nguồn cho mỗi scope. |
| Dùng LLM thứ hai làm judge cho mọi câu trả lời | Có thể khảo sát sau, nhưng tăng chi phí và không tạo bằng chứng symbolic độc lập. |

## User experience

Giữ UI Gemini đang làm. Bước kiểm tra xuất hiện nhẹ trong cùng lượt, chỉ dựa
trên event thật. Ví dụ thiết kế, chưa chạy: "Đã đối chiếu lịch → phát hiện
trùng 15 phút → điều chỉnh khung giờ → kiểm tra lại". Chi tiết mở tại chỗ.
Luồng hiển thị là kế hoạch, evidence, thao tác và bản sửa có thể kiểm tra;
không dựng câu suy nghĩ để giả làm suy luận model.

Lịch: kiểm tra overlap, duration, timezone trên dữ liệu lịch thực đã đọc; không
bảo đảm biết mọi lịch của người dùng. Phép tính: bind biểu thức/đầu vào, kết quả
và kết luận cuối. Tài liệu: giữ source/span/revision; chưa có checker quan hệ
ngữ nghĩa thì chỉ báo scope trích dẫn, giữ UNKNOWN cho suy diễn chưa kiểm tra.
Ghi chú/artifact phải bind đúng lượt và revision để không kiểm tra nhầm bản cũ.

## Next steps proposed

1. Chốt một ca RAT hiện có để làm vertical slice: phép tính có đầu vào rõ hoặc
   ràng buộc lịch. Không thêm bề mặt app mới.
2. Làm contract và các phản ví dụ chống false PASS, final-answer binding,
   timeout/UNKNOWN, stale revision và bounded repair trước khi nối model.
3. Nối feedback/recheck vào runtime và work trace; phân biệt dữ kiện đã kiểm
   tra với phần model tự diễn giải.
4. Development smoke trên cùng câu hỏi/model/settings: so trước/sau về câu đúng,
   false acceptance, rescue/harm, số lần sửa và prompt/completion/tool latency
   thực. Smoke không thay held-out study hoặc chứng minh đóng góp NCKH.

Chưa thực hiện các bước này trong review. Không đổi Stage 0, research entry
point, default model, protocol hoặc fitting.

## Validation scope of the pasted handoff

`audit/repository_migration_20261012/validation.json` ghi 91 root tests và
54 DocAI tests, 1 skipped: tổng 145 passed. Đây là record kiểm tra migration,
không phải đo NeSy hỗ trợ RAT tốt hơn. Review này không chạy lại 145 tests.
Git local khi review ở main, HEAD ghi trong `source_state.json`; tài liệu bàn
giao nhánh chưa push là trạng thái cũ, không là yêu cầu publish trong lượt này.
