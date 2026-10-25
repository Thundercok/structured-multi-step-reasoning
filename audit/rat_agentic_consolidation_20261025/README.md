# Báo cáo kỹ thuật trung thực — Đợt 1, 2, 3, 4 (2026-10-25)

Triển khai hợp nhất kiến trúc theo nguyên tắc bất biến:
**“TẤT CẢ CHỨC NĂNG ĐỀU ĐI THEO REASONING AGENTIC.”**
(Không xây tính năng thành tiện ích độc lập; UI và các thao tác trực tiếp dùng chung hợp đồng tool, dispatcher, kết quả quan sát và bước kiểm tra với Agent; không domain dispatch riêng).

**Trạng thái thực tế đối chiếu mã nguồn**: Đợt 0 ĐÃ XONG; Đợt 1 và Đợt 3 MỘT PHẦN; Đợt 2 và Đợt 4 CHƯA ĐẠT; Đợt 5 CHƯA THÔNG QUA (chỉ có smoke test có lỗi giữ lại).

---

## 1. Đối chiếu hiện trạng từng đợt so với mã nguồn thực tế

### Đợt 1 — Execution chung & Hợp đồng yêu cầu (Một phần)
- **Đã làm**:
  - Mở rộng `ExecutionRequest` trong `rat/engine/execution.py` theo schema `rat.agent_request/v1`. Quản lý `execution_id`, `turn_id`, `generation`, `origin`, `goal`, `context_snapshot` với SHA-256, `resource_bindings`, `budget`, và `idempotency_key`.
  - Triển khai `AgentExecutionService` (`rat/engine/execution_service.py`) quản lý 6 pha:
    `accepted -> planning -> dispatching -> observing -> checking -> deciding -> turn_completed / turn_failed`.
  - Pre-checks: Kiểm tra stale resource binding, kiệt ngân sách, ghi nhớ idempotency key, cancellation.
  - `AssistantWorker` đã bọc gọi qua `AgentExecutionService`.
- **Chưa hoàn tất**:
  - `QuickPDFController` vẫn còn các bypass trực tiếp: nút "Đọc thêm" gọi thẳng `op.handler(...)` của `expand_document_context` thay vì gửi request qua service/dispatcher; các tác vụ Reading gọi qua `_execute_reading_tool` tới dispatcher chứ chưa đồng bộ qua `AgentExecutionService`.

### Đợt 2 — Lát cắt Document & PDF Q&A (Chưa đạt)
- **Đã làm**:
  - Bổ sung tool `expand_document_context` trong `rat/kernel/capabilities/documents.py` (cửa sổ trích xuất văn bản có định vị `page` và `target_excerpt`).
- **Chưa đạt**:
  - `selected_document_qa.py` vẫn là pipeline 1-call cứng nhắc đọc 3000 ký tự đầu. Vòng điều phối của `AssistantRuntime` chưa tích hợp tool `expand_document_context` vào subplan reasoning, khiến model khi thiếu thông tin không thể tự động mở rộng vùng đọc tiếp theo trong tài liệu.
  - Không có các checker hư cấu như `scoped_document_verifier` hay `verify_document_locator`; hệ thống sử dụng `VerificationEngine` cơ bản và giữ `UNKNOWN` khi chưa chứng minh được suy luận.

### Đợt 3 — Reading & Natal (Một phần)
- **Đã làm**:
  - Tách các công cụ Chiêm tinh & Tarot thành các Plugin Tool Pack nạp động (`rat.plugins.packs.divination` và `rat.plugins.packs.astrology`) với `ToolPackManifest`.
  - Loại bỏ hoàn toàn template giả suy luận; khi không có model thì `synthesize_reading_draft` trả mã lỗi quan sát được `model_unavailable`.
  - Triển khai `ReadingVerifier` thật sự trong `rat/engine/verification.py` đối chiếu các lá bài và vị trí hành tinh nhắc tới trong draft với `input_facts` và `computed_facts`. Bảo tồn bản nháp của người dùng.
- **Chưa hoàn tất**:
  - `QuickPDFController` vẫn gọi các tool reading qua `_execute_reading_tool` trực tiếp, chưa chuyển thành `ExecutionRequest` chuẩn gửi qua `AgentExecutionService`.

### Đợt 4 — Finder, Toán học, Lịch & Các domain còn lại (Chưa đạt)
- **Đã làm**:
  - Tách công cụ Thời khóa biểu thành plugin pack `timetable` (mặc định tắt), gọi `TimetableCompositor`.
  - Reranker offline `SemanticFuzzyReranker` hỗ trợ gợi ý tìm kiếm.
- **Chưa đạt**:
  - Luồng Finder chưa chuyển sang `AgentExecutionService`.
  - Chưa có tool/checker cấu hình như `get_configuration`/`update_configuration` trong runtime.
  - Phép tính toán chưa có checker riêng biệt `verify_math_answer` (chỉ có AST evaluator của tool `calculate`).

---

## 2. Bảng kiểm kê (Inventory §10) trung thực theo mã nguồn

| Entry Point | Mục tiêu | Hợp đồng (Contract) | Operation / Dispatcher | Planner / Model | Observation & Receipts | Checker thực tế | Stopping & Budget | UI Projection | Bằng chứng phần mềm | Bằng chứng thực tế (Live) | Giới hạn thực tế |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Chat / Free-text** | Trả lời câu hỏi tổng quát bằng suy luận và công cụ | `ExecutionRequest` (`rat.agent_request/v1`), origin=`chat` | `AgentExecutionService.execute` -> `AssistantRuntime` | Live model (`qwen3:4b-instruct`) hoặc fallback thông báo | Output công cụ, tokens, receipts | `VerificationEngine` (answer check) | Deadline, max_steps, max_tokens | `PDFDesk.qml`: `lastAssistantAnswer`, event timeline | `test_agent_execution_service.py`, `test_execution_flow.py` | `artifacts/qtquick_only_20261025/live2/model-calls.json` | Phụ thuộc vào model local sẵn có |
| **Document Q&A** | Trả lời câu hỏi bám sát tài liệu PDF đang mở | `ExecutionRequest` với `resource_bindings` (path, sha256) | `read_document` qua `selected_document_qa` | 1-call model nhận trích đoạn 3000 ký tự đầu | Đoạn trích text, sha256 | `VerificationEngine` (trả `UNKNOWN` khi suy luận thiếu bằng chứng) | 1-call budget cứng | Answer card, citation tags, page viewer | `test_selected_pdf.py`, `test_quick_pdf.py` | `artifacts/rat_agentic_live_acceptance_20261025/` (thất bại: thiếu thông tin) | Chưa có vòng mở rộng tự động khi excerpt thiếu dữ kiện |
| **Finder & Adopt** | Tìm kiếm tài liệu, app và đưa vào bàn làm việc Agent | Gõ phím: preview. Tab: adopt file | `progressive_search`, `find_applications`, reranker | Reranker offline; adopt submit query | Candidates (`finderHits`), snippet | Kiểm tra file path tồn tại | Limit=10 hits, 300ms preview | `PDFDesk.qml`: `finderHits`, `finderAdoptAction` | `test_quick_finder_flow.py`, `test_semantic_reranker.py` | `artifacts/agentic_finder_build23_20261025/` | Chưa chạy qua AgentExecutionService |
| **Calculator** | Thực hiện phép tính số học chính xác | `ExecutionRequest` với requested_action `calculate` | Tool `calculate` trong capability `math` | AST evaluator | Kết quả số học | Đánh giá trực tiếp từ AST (chưa có verifier độc lập) | Tức thì | Answer text, verification PASS/UNKNOWN | `test_agent_execution_service.py` | Unit test | Không giải phương trình phức tạp |
| **Reading Desk** | Phân tích bài Tarot và bản đồ sao | `prepare_reading_spread`, `load_reading_profile`, `synthesize_reading_draft` | Plugin packs `divination`, `astrology` qua Dispatcher | Model client; trả `model_unavailable` khi offline | Lá bài nhập, góc chiếu Swiss Ephemeris | `ReadingVerifier` thật sự trong `verification.py` | Model single-call, timeout 45s | `ReadingDesk.qml`, thẻ bài, biểu đồ, draft editor | `test_plugin_tool_packs.py`, `test_reading_session.py` | `artifacts/reading_turn1_20261025/report.json` | Controller gọi dispatcher trực tiếp, chưa qua service |
| **Timetable** | Phân tích lịch học, tìm giờ trống | Pack `timetable` (mặc định tắt) | `TimetableCompositor` qua tool pack | Thuật toán ràng buộc | Lịch học, xung đột, giờ trống | Thuật toán kiểm tra xung đột | Deterministic solver | `view_schedule` factory | `test_timetable_compositor.py`, `test_plugin_tool_packs.py` | `artifacts/qtquick_only_20261025/live/state/club_schedules.json` | Spider adapter đã tách riêng |
| **Context Expand (Nút Đọc thêm)** | Mở rộng đoạn trích tài liệu xung quanh vị trí tìm thấy | Gọi `op.handler` trong controller (cần sửa sang dispatcher) | `expand_document_context` | Deterministic tool | Đoạn text mở rộng ngữ cảnh trước / sau | Chưa có verifier độc lập | 1 bước, tối đa 2000 ký tự | Excerpt inspector trên `PDFDesk.qml` | `test_selected_pdf.py` | Chưa có live trace | Controller đang bypass dispatcher |

---

## 3. Bằng chứng kiểm thử phần mềm

Chạy độc lập các test suite hiện tại:
- `test_agent_execution_service.py`, `test_execution_flow.py`, `test_plugin_tool_packs.py`, `test_reading_session.py`: **31 passed**
- `test_selected_pdf.py`: **14 passed**
- `test_quick_pdf.py`: **11 passed**
- `test_quick_finder_flow.py`: **21 passed**
- `test_semantic_reranker.py`, `test_progressive_search.py`: **25 passed**
- `test_quick_only_runtime.py`: **2 passed**
- Bộ nghiên cứu (`test_research_study.py test_optimal_stopping.py test_entry_predictor.py`): **29 passed** (bảo toàn).

**Tổng cộng: 133 tests passed.**
*(Lưu ý: Test pass chứng minh code không lỗi runtime, không chứng minh toàn bộ các đợt đã hoàn thành).*
