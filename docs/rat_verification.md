# Kiểm chứng trong vòng làm việc của RAT

RAT dùng cùng runtime, registry, lượt chat và `WorkTracePane` cho đề xuất,
thực thi, kiểm tra và sửa kết luận. Verifier là contract của operation, không
phải feature UI hoặc tool mà model cần nhớ gọi. DocAI vẫn đứng riêng.

## Contract và điểm nối

`OperationDefinition.verifier` nhận một implementation `OperationVerifier`:

- `check_execution(evidence)` đối chiếu đầu vào và kết quả thực thi đã snapshot.
- `check_answer(goal, answer, evidence)` trả report cho phần checker hỗ trợ;
  trả `None` khi không áp dụng.

`VerificationSession` được tạo mới trong mỗi `AssistantRuntime.run`, ghi evidence
ID theo request/step cùng SHA256 đầu vào/kết quả và thời gian kiểm tra thực.
Các checker dùng chung session, feedback, ngân sách và work trace. Thêm checker
cho capability không cần thêm nhánh quyết định theo keyword trong runtime.

Report có `PASS / FAIL / UNKNOWN`, scope, reason, evidence IDs, các check đã chạy
và `retryable`. Status chỉ nói về scope đã ghi. Checker lỗi hoặc trả contract
không hợp lệ phải thành UNKNOWN; không được chấp nhận âm thầm như PASS.

Mỗi candidate final của model được kiểm tra trước khi trả. FAIL hoặc UNKNOWN
cần sửa được đưa về model cùng candidate và vi phạm cụ thể. Có tối đa hai lần
sửa mặc định, đồng thời bị giới hạn bởi max_steps/token budget/cancel. Các lần
gọi sửa đều là inference thực và được cộng prompt/completion tokens, model time.
Checker có thể cung cấp `answer_schema` trong report để lượt sửa dùng native
JSON grammar với envelope `{"answer": "..."}`. Runtime decode envelope rồi
checker vẫn đối chiếu nội dung; đúng schema không tự trở thành PASS. Không có
fallback tự thay text của model bằng một câu trả lời thành công. Với phép tính
có kết quả duy nhất đã tính độc lập, schema đặt enum của `answer` thành giá trị
đó. Đây là **symbolic result constrained decoding**, không phải bằng chứng model
đã học hoặc tự giải lại phép toán. Model vẫn thực sự sinh lượt sửa; nếu format,
giá trị hoặc call thất bại thì giữ failure. Enum và nguồn giá trị nằm trong raw
request/report để audit không nhầm với kết quả generation không ràng buộc.
Checker time ghi riêng trong `verification_time_ms`. Không fit lại utility
controller; guard kiểm chứng không thay đổi feature vector hoặc thresholds.

Hết ngân sách khi còn lỗi thì trả `verification_failed` hoặc
`verification_unresolved`, giữ trace/evidence/usage, không trả candidate sai như
câu trả lời đã hoàn tất. Câu hỏi ngoài scope vẫn được trả với trạng thái UNKNOWN.
`completion_status` của task state vẫn là báo cáo từ model, không chứng nhận
thành công. `answer_verification_status=PASS` phải được đọc cùng scopes trong
`verification_reports`, không dùng để duyệt toàn bộ tác vụ.

## Phạm vi đầu tiên: số học

Calculator registry khai báo `CalculationVerifier`. Checker tính độc lập bằng
số hữu tỉ, có giới hạn AST/độ dài/intermediate/exponent và không thực thi code.
Số nguyên so chính xác; biểu diễn thập phân cho phép sai số tuyệt đối 1e-9 để
đối chiếu output float hiện có. Đây là contract số học, không kiểm chứng đơn vị.

Yêu cầu là toàn bộ một biểu thức số học, có thể có tiền tố `tính`, `calculate`,
`compute`, `calc`, `what is`, được bind trực tiếp với kết luận. Kết luận hỗ trợ
toàn bộ một scalar hoặc `expression = scalar`, với nhãn/Markdown đơn giản.
Không tìm một số phù hợp ở giữa prose, không bỏ câu phủ định hoặc kết luận khác.
Biểu thức/format ngoài phạm vi không được báo PASS.

Với đề bài tự nhiên, chỉ có thể đối chiếu một kết luận scalar với một phép tính
đã quan sát không mơ hồ. Scope khi đó là `calculation_answer_only`: **không chứng
minh rằng biểu thức do model chọn giải đúng đề bài**. Không dùng kết quả này như
ground truth nghiên cứu. Kiểm tra ràng buộc lịch, extraction/schema và claim
tài liệu cần implementation riêng vào cùng contract trong lượt tiếp theo.

## VGC compatibility

VGC cũ dùng lại checker số học này; output Python khớp witness chưa đủ, phải
đối chiếu với target và claim. Checker tài liệu chỉ xác nhận nguyên đoạn trích
khớp source đã cung cấp, không xác nhận diễn giải, quan hệ ngữ nghĩa, relevance
hoặc tính xác thực tài liệu. Reranker ghi rõ “Trích đoạn khớp nguồn”.

Cascade AST/excerpt không gọi model nên token inference là 0, confidence chưa
hiệu chỉnh là `None`; tính lại AST không được gọi là escalation sang model sâu.
Đây là sửa contract runtime, không là kết quả của nghiên cứu VGC. Các code path
MetaReasoner legacy khác vẫn chưa được đo và không là entry point nghiên cứu.

## Validation

Tests scripted/Qt kiểm tra luồng phần mềm, không đo chất lượng model:

```bash
python -m pytest tests/test_rat_verification.py tests/test_vgc_verification.py tests/test_assistant_runtime.py tests/test_controller.py tests/test_work_context.py tests/test_interaction_kernel.py tests/test_interaction_kernel_regressions.py -q
QT_QPA_PLATFORM=offscreen python -m pytest tests/test_rat_verification_ui.py tests/test_work_context_ui.py tests/test_assistant_worker.py -q
```

Development audit ở `audit/rat_symbolic_core_20261012/`. Một live smoke dùng
database tạm rỗng, không index tài liệu cá nhân và giữ raw model inputs/outputs.
Không có đánh giá accuracy corpus, ablation hoặc baseline đo trước/sau trong
lượt này; không tuyên bố cải thiện model quality. Research harness, fitting,
default model, DocAI separation và Stage 0 không đổi.
