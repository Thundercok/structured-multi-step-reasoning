# Bàn giao triển khai Agentic RAT — Đợt 1, 2, 3, 4 (2026-10-25)

Triển khai hợp nhất kiến trúc theo nguyên tắc bất biến:
**“TẤT CẢ CHỨC NĂNG ĐỀU ĐI THEO REASONING AGENTIC.”**
(Không xây tính năng thành tiện ích độc lập; UI và các thao tác trực tiếp dùng chung hợp đồng tool, dispatcher, kết quả quan sát và bước kiểm tra với Agent; không domain dispatch riêng).

Trạng thái: Đã hoàn tất triển khai mã nguồn và kiểm chứng phần mềm cho Đợt 1, 2, 3, 4. Sẵn sàng cho Đợt 5 (Live Acceptance).

---

## 1. Nội dung chi tiết các đợt đã triển khai

### Đợt 1 — Execution chung & Hợp đồng yêu cầu
- **Envelope thống nhất**: Mở rộng `ExecutionRequest` trong `rat/engine/execution.py` theo schema `rat.agent_request/v1`. Quản lý `execution_id`, `turn_id`, `generation`, `origin` (`chat`, `ui_action`, `cli`), `goal`, `context_snapshot` với SHA-256 hash, `resource_bindings`, `budget` (deadline, tokens, calls), và `idempotency_key`.
- **Dịch vụ điều phối `AgentExecutionService`** (`rat/engine/execution_service.py`): Quản lý 6 pha vòng đời chuẩn:
  `accepted -> planning -> dispatching -> observing -> checking -> deciding -> turn_completed / turn_failed`.
- **Pre-checks an toàn**: Kiểm tra chống binding tài nguyên bị sửa đổi (stale file / hash mismatch) trước khi thực hiện I/O; kiểm soát kiệt ngân sách (`budget_exhausted`); ghi nhớ kết quả qua `idempotency_key`; hỗ trợ hủy luồng cộng tác (`cancelled`).
- **Nối kết Worker**: `AssistantWorker` trong `rat/ui/assistant_worker.py` điều phối qua `AgentExecutionService`, loại bỏ các nhánh giải quyết domain độc lập.

### Đợt 2 — Lát cắt Document & PDF Q&A
- **Subplan định vị theo vùng ngữ cảnh (Locator-aware expand)**: Thay thế việc cắt xén cố định 1800 ký tự đầu file bằng tool `expand_document_context` trong `rat/kernel/capabilities/documents.py`. Hỗ trợ trích xuất vùng xung quanh `target_excerpt` và `page` xác thực.
- **Tách bạch hoàn tất và kiểm chứng**: Không tự động gán nhãn PASS cho câu trả lời chỉ vì thao tác đọc tài liệu thành công. Duy trì nhãn UNKNOWN khi suy diễn chưa được bảo đảm bởi trích dẫn trực tiếp.

### Đợt 3 — Reading & Natal (Chiêm tinh & Tarot)
- **Kiến trúc Plugin Tool Pack**: Tách các khả năng đọc bài và phân tích bản đồ sao thành các gói công cụ nạp động (`rat.plugins.packs.divination` và `rat.plugins.packs.astrology`), tuân thủ `ToolPackManifest`. Mặc định không nạp tự động nhằm bảo vệ độ tinh gọn cho headless engine, chỉ kích hoạt khi người dùng mở workspace tương ứng.
- **Loại bỏ hoàn toàn template giả suy luận**: Khi chưa có model hoặc model client offline, tool `synthesize_reading_draft` trả mã lỗi quan sát được `model_unavailable` thay vì chèn văn bản mẫu giả lập quá trình suy luận.
- **Bộ kiểm tra theo phạm vi (`scoped_reading_verifier`)**: Đối chiếu chặt chẽ các lá bài và vị trí hành tinh trong bài viết với dữ kiện đầu vào (`input_facts`) và dữ kiện tính toán (`computed_facts` từ Swiss Ephemeris). Các khẳng định về tương lai giữ trạng thái UNKNOWN. Bản nháp của người dùng luôn được bảo tồn (`draft_preserved`).

### Đợt 4 — Finder, Toán học, Lịch & Các domain còn lại
- **Finder & App Search**:
  - Gợi ý gõ phím phân định rõ thành `preview` subplan (read-only, chạy offline qua `SemanticFuzzyReranker` và `FinderIntentCoordinator`, không sinh effect, không gọi model mỗi phím).
  - Thao tác chọn / Tab kích hoạt chuyển đổi tài liệu vào RAT Desk và submit câu hỏi có ngữ cảnh trực tiếp vào vòng Agentic reasoning.
- **Toán học**: Tool `calculate` an toàn bằng AST / Fraction; kiểm tra chéo kết quả bằng verifier số học.
- **Lịch học (Timetable)**: Chuyển thành plugin pack `timetable` (mặc định tắt), hỗ trợ tìm kiếm khoảng trống chung và xuất ICS thông qua `TimetableCompositor`.
- **Cấu hình**: Thông qua tool schema `get_configuration` và `update_configuration`.

---

## 2. Bảng kiểm kê (Inventory) các Entry Point (§10)

| Entry Point | Mục tiêu | Hợp đồng (Contract) | Operation / Dispatcher | Planner / Model | Observation & Receipts | Checker & Coverage | Stopping & Budget | UI Projection | Bằng chứng phần mềm | Bằng chứng thực tế (Live) | Giới hạn còn lại |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Chat / Free-text** | Trả lời câu hỏi tổng quát bằng suy luận và công cụ | `ExecutionRequest` (`rat.agent_request/v1`), origin=`chat` | `AgentExecutionService.execute` -> `AssistantRuntime` | Live model (`qwen3:4b-instruct`) hoặc fallback thông báo | Output công cụ, tokens, timing | `VerificationEngine` (answer & citation check) | Deadline, max_steps, max_tokens | `PDFDesk.qml`: `lastAssistantAnswer`, event timeline | `test_agent_execution_service.py`, `test_execution_flow.py` | `artifacts/qtquick_only_20261025/live2/model-calls.json` | Phụ thuộc vào model local sẵn có |
| **Document Q&A** | Trả lời câu hỏi bám sát tài liệu PDF đang mở | `ExecutionRequest` với `resource_bindings` (path, sha256) | `expand_document_context`, `read_document_excerpt` | Model nhận excerpts và locator | Đoạn trích text, trang, sha256 | `scoped_document_verifier`, quote match check | 1-2 lần expand, deadline cap | Answer card, citation tags, page viewer | `test_selected_pdf.py`, `test_quick_pdf.py` | `artifacts/qtquick_only_20261025/live2/screenshots/03-live-answer-full.png` | PDF quét dạng ảnh phụ thuộc OCR |
| **Finder & Adopt** | Tìm kiếm tài liệu, app và đưa vào bàn làm việc Agent | Gõ phím: `preview` subplan. Tab: `ExecutionRequest` origin=`ui_action` | `progressive_search`, `find_applications`, reranker | Reranker offline + Agent loop khi adopt | Candidates (`finderHits`), snippet, match_reason | Kiểm tra file path tồn tại, is_pdf check | Limit=10 hits, 300ms preview cap | `PDFDesk.qml`: `finderHits`, `finderAdoptAction` (Tab pill) | `test_quick_finder_flow.py`, `test_semantic_reranker.py` | `artifacts/agentic_finder_build23_20261025/agentic_candidates_520.png` | Phụ thuộc index Spotlight và DB local |
| **Calculator** | Thực hiện phép tính số học chính xác | `ExecutionRequest` với requested_action `calculate` | Tool `calculate` trong capability `math` | Deterministic AST evaluator | Kết quả số học / phân số | `verify_math_answer` đối chiếu biểu thức AST | Tức thì (1 bước), cap 1.0s | Answer text, verification PASS | `test_agent_execution_service.py` | Đã kiểm chứng qua unit test | Không giải phương trình phức tạp phi tuyến |
| **Reading Desk** | Phân tích bài Tarot và bản đồ sao | `load_reading_profile`, `prepare_reading_spread`, `synthesize_reading_draft` | Plugin packs `divination`, `astrology` qua Dispatcher | Model client; trả `model_unavailable` khi offline | Lá bài nhập, góc chiếu Swiss Ephemeris | `scoped_reading_verifier` đối chiếu facts; tương lai UNKNOWN | Model single-call, timeout 45s | `ReadingDesk.qml`, thẻ bài, biểu đồ, draft editor | `test_plugin_tool_packs.py`, `test_reading_session.py` | `artifacts/reading_turn1_20261025/report.json` | Swiss Ephemeris cần giờ sinh chính xác |
| **Timetable** | Phân tích lịch học, tìm giờ trống | Capability trong pack `timetable` (mặc định tắt) | `TimetableCompositor` qua tool pack | Thuật toán ràng buộc | Lịch học, xung đột, giờ trống | Constraint satisfaction checker | Deterministic solver | `view_schedule` factory | `test_timetable_compositor.py`, `test_plugin_tool_packs.py` | `artifacts/qtquick_only_20261025/live/state/club_schedules.json` | Spider adapter đã tách riêng |
| **Context Expand** | Mở rộng đoạn trích tài liệu xung quanh vị trí tìm thấy | `expand_document_context` kèm `target_excerpt` và `page` | Locator-aware window expander | Deterministic tool | Đoạn text mở rộng ngữ cảnh trước / sau | `verify_document_locator` xác thực hash & excerpt | 1 bước, tối đa 2000 ký tự | Excerpt inspector trên `PDFDesk.qml` | `test_selected_pdf.py` | Đã kiểm chứng qua controller | File PDF phải còn nguyên vẹn trên đĩa |
| **Configuration** | Xem và cập nhật cấu hình hệ thống | `get_configuration`, `update_configuration` | Config registry handler | Deterministic presentation / action | Trạng thái cấu hình | Schema type & allowed keys check | Tức thì | Preferences dialog / panel | `test_quick_only_runtime.py` | `artifacts/qtquick_only_20261025/live/state/config.json` | Chỉ sửa các key hợp lệ trong schema |

---

## 3. Bằng chứng kiểm thử phần mềm (Software Evidence)

Tất cả các bài kiểm tra được chạy độc lập, tách riêng theo module để đảm bảo tính toàn vẹn vòng đời ứng dụng trên macOS:

- `tests/test_agent_execution_service.py`, `tests/test_execution_flow.py`, `tests/test_plugin_tool_packs.py`, `tests/test_reading_session.py`: **31 passed**
- `tests/test_selected_pdf.py`: **14 passed**
- `tests/test_quick_pdf.py`: **11 passed**
- `tests/test_quick_finder_flow.py`: **21 passed**
- `tests/test_semantic_reranker.py`, `tests/test_progressive_search.py`: **25 passed**
- `tests/test_quick_only_runtime.py`: **2 passed**
- Bộ nghiên cứu (`tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py`): **29 passed** (bảo toàn không đổi).

**Tổng cộng: 133 tests passed 100%.**

---

## 4. Giới hạn giữ lại (Retained Limits)

1. Chưa thực hiện đo chất lượng mô hình (model quality benchmark) hay thay đổi Stage 0 nghiên cứu.
2. Việc vượt qua các bài kiểm thử phần mềm không đồng nghĩa với việc đã thông qua nghiệm thu ứng dụng trực tiếp (Live UI Acceptance).
3. Đợt 5 sẽ thực hiện nghiệm thu trực tiếp trên môi trường production với file PDF thật có provenance SHA-256 xác thực và mô hình cục bộ.
