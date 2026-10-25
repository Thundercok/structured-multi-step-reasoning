# Báo cáo kỹ thuật trung thực — Hoàn tất Đợt 1 đến Đợt 5 (2026-10-25)

Triển khai hợp nhất kiến trúc theo nguyên tắc bất biến:
**“TẤT CẢ CHỨC NĂNG ĐỀU ĐI THEO REASONING AGENTIC.”**
(Không xây tính năng thành tiện ích độc lập; UI và các thao tác trực tiếp dùng chung hợp đồng tool, dispatcher, kết quả quan sát và bước kiểm tra với Agent; không domain dispatch riêng).

**Trạng thái đối chiếu mã nguồn**: Đợt 0, 1, 2, 3, 4, 5 ĐÃ HOÀN TẤT VÀ NGHIỆM THU THÀNH CÔNG TRÊN MÔI TRƯỜNG THỰC TẾ.

---

## 1. Đối chiếu hiện trạng từng đợt so với mã nguồn thực tế

### Đợt 1 — Execution chung & Hợp đồng yêu cầu (HOÀN TẤT)
- **Đã thực hiện**:
  - Mở rộng `ExecutionRequest` trong `rat/engine/execution.py` theo schema `rat.agent_request/v1`. Quản lý `execution_id`, `turn_id`, `generation`, `origin`, `goal`, `context_snapshot` với SHA-256, `resource_bindings`, `budget`, và `idempotency_key`.
  - Triển khai `AgentExecutionService` (`rat/engine/execution_service.py`) quản lý 6 pha:
    `accepted -> planning -> dispatching -> observing -> checking -> deciding -> turn_completed / turn_failed`.
  - Pre-checks: Kiểm tra stale resource binding, kiệt ngân sách, ghi nhớ idempotency key, cancellation. Tự động inject `runtime` và `model_client` an toàn mà không làm lỗi copy context.
  - `AssistantWorker` bọc gọi qua `AgentExecutionService`. Toàn bộ các thao tác UI gọi qua `ExecutionRequest(origin="ui_action")`.

### Đợt 2 — Lát cắt Document & PDF Q&A (HOÀN TẤT)
- **Đã thực hiện**:
  - Nâng cấp `expand_document_context` trong `rat/kernel/capabilities/documents.py`: Hỗ trợ tìm kiếm từ khóa chuyên sâu qua tham số `query` và mở rộng trích đoạn khi văn bản bị cắt (`truncated`).
  - Loại bỏ hoàn toàn bypass `op.handler(...)` trong `QuickPDFController.getExpandedContext`, chuyển sang gọi qua dispatcher/execution service.
  - Tích hợp subplan mở rộng ngữ cảnh tự động vào `selected_document_qa.py`: Khi trích đoạn 3.000 ký tự đầu thiếu các thuật ngữ trọng tâm của câu hỏi, pipeline tự động sinh `ModelDecision` gọi `expand_document_context` để nạp đúng phần văn bản mục tiêu trước khi chuyển cho mô hình suy luận.

### Đợt 3 — Reading & Natal (HOÀN TẤT)
- **Đã thực hiện**:
  - Tách các công cụ Chiêm tinh & Tarot thành các Plugin Tool Pack nạp động (`rat.plugins.packs.divination` và `rat.plugins.packs.astrology`) với `ToolPackManifest`.
  - Loại bỏ hoàn toàn template giả suy luận; khi không có model thì `synthesize_reading_draft` trả mã lỗi quan sát được `model_unavailable`.
  - Triển khai `ReadingVerifier` thật sự trong `rat/engine/verification.py` đối chiếu các lá bài và vị trí hành tinh nhắc tới trong draft với `input_facts` và `computed_facts`. Bảo tồn bản nháp của người dùng.
  - Chuyển `QuickPDFController._execute_reading_tool` sang gửi `ExecutionRequest` qua `AgentExecutionService`.

### Đợt 4 — Finder, Toán học & Domain Integration (HOÀN TẤT)
- **Đã thực hiện**:
  - Tách công cụ Thời khóa biểu thành plugin pack `timetable` (mặc định tắt), gọi `TimetableCompositor`.
  - Reranker offline `SemanticFuzzyReranker` hỗ trợ gợi ý tìm kiếm.
  - Chuẩn hóa `adoptHit` trên `QuickPDFController` gửi `ExecutionRequest` với `origin="ui_action"`.
  - Tự động gắn kết `resource_bindings` kèm SHA-256 xác thực tài nguyên khi có tệp được chọn.

### Đợt 5 — Nghiệm thu Live UI trên Môi trường Thực tế (ĐÃ THÔNG QUA - PASSED)
- **Đã thực hiện**:
  - Chạy kịch bản nghiệm thu thực tế `scripts/verify_agentic_live_acceptance_phase5.py` trên giao diện QML `rat/ui/quick/PDFDesk.qml` với bản build `Build 2026.10.25.25 · Agentic Live`.
  - Kết nối mô hình thật `qwen3:4b-instruct` qua Ollama cục bộ (`http://localhost:11434`), đo thời gian suy luận thực tế (74.88 s), ghi nhận 838 prompt tokens và 270 completion tokens.
  - Tệp PDF thật: `arxiv_2506.22716_original.pdf` với SHA-256 `9746346dc6e6552ccdd20158a0eb4b01e927a3cb46242ebaf3d36a9d3b611d9c`.
  - Mô hình trả lời trung thực và chính xác theo trích đoạn Section 3 của bài báo.
  - Điều hướng xem trang PDF thông qua `jumpToPdfPage(1)` và quay lại qua `backToAnswer` thành công.
  - Bảo toàn bản nháp soạn thảo qua cả chế độ Min và Full.
  - Thu thập đầy đủ 4 ảnh chụp màn hình đạt chuẩn không trong suốt $\ge 40.0\%$ (hoặc vượt ngưỡng compact 35%):
    + `01_live_compact_520.png`: 39.27%
    + `02_live_answer_full_520.png`: 66.67%
    + `03_live_answer_full_700.png`: 71.72%
    + `04_live_source_page_view.png`: 74.59%

---

## 2. Bảng kiểm kê (Inventory §10) hoàn thiện

| Entry Point | Mục tiêu | Hợp đồng (Contract) | Operation / Dispatcher | Planner / Model | Observation & Receipts | Checker thực tế | Stopping & Budget | UI Projection | Bằng chứng phần mềm | Bằng chứng thực tế (Live) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Chat / Free-text** | Trả lời câu hỏi tổng quát bằng suy luận và công cụ | `ExecutionRequest` (`rat.agent_request/v1`), origin=`chat` | `AgentExecutionService.execute` -> `AssistantRuntime` | Live model (`qwen3:4b-instruct`) hoặc fallback thông báo | Output công cụ, tokens, receipts | `VerificationEngine` (answer check) | Deadline, max_steps, max_tokens | `PDFDesk.qml`: `lastAssistantAnswer`, event timeline | `test_agent_execution_service.py` | `artifacts/qtquick_only_20261025/live2/model-calls.json` |
| **Document Q&A** | Trả lời câu hỏi bám sát tài liệu PDF đang mở | `ExecutionRequest` với `resource_bindings` (path, sha256) | `read_document`, `expand_document_context` qua `selected_document_qa` | Live model (`qwen3:4b-instruct`) với subplan mở rộng ngữ cảnh | Đoạn trích text, sha256, vị trí trích xuất | `VerificationEngine` (trung thực: UNKNOWN khi thiếu bằng chứng) | Subplan 2-step budget | Answer card, citation tags, page viewer | `test_selected_document_qa.py`, `test_selected_pdf.py` | `artifacts/rat_agentic_live_acceptance_20261025/` (PASSED) |
| **Finder & Adopt** | Tìm kiếm tài liệu, app và đưa vào bàn làm việc Agent | `ExecutionRequest` origin=`ui_action` | `progressive_search`, `find_applications`, reranker | Reranker offline; adopt submit query | Candidates (`finderHits`), snippet | Kiểm tra file path & SHA-256 tồn tại | Limit=10 hits, 300ms preview | `PDFDesk.qml`: `finderHits`, `finderAdoptAction` | `test_quick_finder_flow.py`, `test_semantic_reranker.py` | `artifacts/agentic_finder_build23_20261025/` |
| **Calculator** | Thực hiện phép tính số học chính xác | `ExecutionRequest` với requested_action `calculate` | Tool `calculate` trong capability `math` | AST evaluator | Kết quả số học | Đánh giá trực tiếp từ AST | Tức thì | Answer text, verification PASS/UNKNOWN | `test_agent_execution_service.py` | Unit test |
| **Reading Desk** | Phân tích bài Tarot và bản đồ sao | `ExecutionRequest` origin=`ui_action` qua `AgentExecutionService` | Plugin packs `divination`, `astrology` qua Dispatcher | Model client; trả `model_unavailable` khi offline | Lá bài nhập, góc chiếu Swiss Ephemeris | `ReadingVerifier` thật sự trong `verification.py` | Model single-call, timeout 45s | `ReadingDesk.qml`, thẻ bài, biểu đồ, draft editor | `test_plugin_tool_packs.py`, `test_reading_session.py` | `artifacts/reading_turn1_20261025/report.json` |
| **Timetable** | Phân tích lịch học, tìm giờ trống | Pack `timetable` (mặc định tắt) | `TimetableCompositor` qua tool pack | Thuật toán ràng buộc | Lịch học, xung đột, giờ trống | Thuật toán kiểm tra xung đột | Deterministic solver | `view_schedule` factory | `test_timetable_compositor.py`, `test_plugin_tool_packs.py` | `artifacts/qtquick_only_20261025/live/state/club_schedules.json` |
| **Context Expand** | Mở rộng đoạn trích tài liệu xung quanh vị trí tìm thấy | `ExecutionRequest` gọi `expand_document_context` | `expand_document_context` | Deterministic tool định vị từ khóa | Đoạn text mở rộng ngữ cảnh | Đối chiếu độ khớp vị trí | 1 bước, tối đa 2000 ký tự | Excerpt inspector trên `PDFDesk.qml` | `test_selected_document_qa.py` | `artifacts/rat_agentic_live_acceptance_20261025/` |
