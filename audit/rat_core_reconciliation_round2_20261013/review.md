# Báo cáo Bàn giao Core Reconciliation (Round 2) — Antigravity

**Ngày:** 2026-10-13 (Asia/Saigon)  
**Phạm vi:** Triển khai core completion reconciliation theo ADR-003, giải quyết toàn bộ 8 findings (R1–R8) từ Codex Review.  
**Vai trò:** Codex thiết kế và review; Antigravity thực hiện code.  
**Trạng thái phase:** Core hoàn tất; UI presentation và live model ablation **chưa mở** (tiếp tục bảo lưu chờ user duyệt).  

---

## 1. Tóm tắt Kết quả Thực nghiệm

| Hạng mục | Kết quả | Thời gian | Exit Code | Ghi chú |
|---|---|---|---|---|
| **Contract Probes (Codex)** | **19 / 19 PASSED** | 0.79s | 0 | Chạy trực tiếp `audit/rat_reconciliation_codex_review_20261013/contract_probes.py` |
| **Regression Tests** | **224 / 224 PASSED** | 24.53s | 0 | Chạy 17 test modules theo `regression_tests.txt` |
| **Fixture Transcripts** | **11 / 11 PASSED** | 0.65s | 0 | Transcripts đầy đủ `turn_contract` & `execution_journal` |
| **Live Model Calls** | **0 calls** | 0.00s | — | Toàn bộ chạy qua mock/fixture client; không tốn budget |

- Log chi tiết probes: [`contract_probes.txt`](contract_probes.txt)
- Log chi tiết regression: [`regression_tests.txt`](regression_tests.txt)
- Transcripts có contract + journal: [`transcripts/fixture_transcripts.json`](transcripts/fixture_transcripts.json)
- Unified patch từ reviewed snapshot: [`diff_from_reviewed_source.patch`](diff_from_reviewed_source.patch)
- Bảng mã băm SHA-256: [`source_hashes.json`](source_hashes.json)
- Manifest bàn giao: [`validation.json`](validation.json)

---

## 2. Chi tiết Triển khai và Giải quyết Findings R1–R8

### R1: Native planner & decision encoding (ON/OFF)
- **Schema & Extraction**: `_plan_task` trong `rat/engine/assistant_runtime.py` bổ sung `outcomes` vào JSON schema (`planning_schema`). Tách biệt phần trích xuất `outcomes` khỏi hàm `validate_task_state` để tránh lỗi schema rejection (`task_plan_failed:invalid_object:arguments`).
- **Decoder Planner OFF**: Cập nhật `_call_model` để giải mã cấu trúc native `contract` hoặc `outcomes` trả về từ model vào `ModelDecision`.
- **Identity & Binding**: Tại runtime `run()`, contract từ model/caller được deepcopy và gán định danh runtime-owned (`turn_id`, `execution_id`, `generation`).
- **Loại bỏ Self-Report Bypass**: Trạng thái hoàn thành `calc_comp_status` được ánh xạ trực tiếp từ `reconciliation.declared_scope_completion`, không dựa vào nhãn tự khai `model_reported_...`.

### R2: Call-specific artifact refs & normalized producer-consumer linking
- **Tách biệt phạm vi call**: Thay vì dùng `changed_artifacts()` tích lũy từ đầu request, mỗi bước tool call ghi nhận `step_starting_revisions` riêng để chỉ tính những artifacts thực sự thay đổi trong bước đó (`step_changed_artifacts`).
- **Thống nhất định dạng ref**: Lưu trữ song song cả `id` và `artifact_id` trong danh sách `art_refs` của journal receipt, giải quyết lỗi mismatch khóa tra cứu.
- **Positive Control**: Luồng calculate `18 * 7` -> tạo artifact `126` -> lưu note với đúng artifact `126` đạt trạng thái `satisfied` trước khi kiểm tra các ca lỗi wrong-source.

### R3: Strict contract validation & immutable frozen contracts
- **Kiểm tra tính hợp lệ nghiêm ngặt**:
  - `OutcomeKind.VALID_KINDS = (RESPONSE, REGISTERED_EFFECT)`.
  - `TurnContract.__post_init__` và `TurnContract.from_dict` kiểm tra bắt buộc `schema_version == "1.0"`, enum `kind`, trùng lặp `outcome_id`, và các phụ thuộc `dependency_ids` không tồn tại. Nếu vi phạm, contract được đánh dấu `is_valid = False` và giữ nguyên trạng thái `unresolved` khi đối soát.
- **Bất biến cấu trúc (Freeze)**:
  - `OutcomeSpec` cài đặt cờ `_frozen` và chặn sửa thuộc tính qua `__setattr__`.
  - `TurnContract.freeze()` đóng băng toàn bộ outcomes con và chuyển `self.outcomes` sang `tuple` bất biến, chống triệt để các thao tác `outcomes.clear()` hoặc sửa đổi sau khi lập kế hoạch.
- **Deepcopy Journal Envelopes**: `ExecutionJournal.record_operation` thực hiện deepcopy toàn bộ `args`, `result`, `artifact_refs`, `note_event`, và `verification_report` tại thời điểm commit, ngăn ngừa callback hoặc caller chỉnh sửa bằng chứng sau khi ghi nhận.

### R4: Matcher tổng quát, proof lineage và ràng buộc response
- **Matcher theo registered effects**:
  - `_match_calculate`: kiểm tra biểu thức/tham số bắt buộc, tiêu thụ receipt duy nhất (`used_receipt_ids`), và đối soát bằng chứng xác minh (proof report) phải thuộc về chính receipt hoặc artifact của phép tính đó (`v.target_id in (receipt_id, artifact_id)`), ngăn ngừa hiện tượng proof PASS của call khác che mất lỗi.
  - `_match_note`: đối soát liên kết nguồn (`artifact_id`, `field`, `revision`) với artifact thực tế, kiểm tra snapshot terminal của sổ tay và trạng thái note event.
  - `_match_generic`: đối soát `target_ref`, `target_revision`, `source_ref` và bắt buộc đạt `required_proof_scope`.
- **Ràng buộc response**: Khi contract yêu cầu `OutcomeKind.RESPONSE`, việc thiếu câu trả lời văn bản sẽ khiến outcome đó bị đánh dấu `missing_response` và ngăn không cho lượt đạt `satisfied` dù các effects đã hoàn tất.
- **Xử lý Omitted Action**: Khi contract có khai báo registered effects nhưng không có effect nào được thực thi (`met_effect_count == 0`), kết quả đối soát là `unresolved` (thay vì `partial`), bất kể model có sinh ra câu trả lời hội thoại hay không.

### R5: Terminal note verification & quản lý phiên bản
- Trạng thái note được kiểm tra trực tiếp tại boundary hoàn tất bằng snapshot terminal của notebook (`notebook_snapshot`).
- Một phiên bản cũ đã confirmed không thể được dùng để hợp thức hóa một phiên bản mới hơn đang ở trạng thái proposed (`allow_proposal=False`).
- Note bị tạo rồi xóa trong cùng một execution không được coi là đang lưu trữ.

### R6: Bảo toàn tiến độ đã commit khi cancel / fail / needs_input
- Trong các trường hợp lượt dừng sớm (`cancelled`, `failed`, `needs_input`), runtime vẫn chạy matcher đối với các thao tác đã hoàn thành trước đó để đưa vào `matched_receipts`.
- Trạng thái tổng quát của lượt được ghi nhận là `unresolved` kèm lý do cụ thể (`cancelled_in_flight`, `pending_input_required`, `execution_failed`).
- Thu nhận trạng thái thực tế từ `DispatchResult.status` thay vì suy đoán từ callback.

### R7: Wiring đầy đủ qua history & turn references
- `rat/ui/omnibar.py` được bổ sung việc truyền dữ liệu `reconciliation`, `artifact_refs`, và `note_ids` vào các nhánh `cancel_turn()` và `fail_turn()`, cũng như khi dispatcher chuyển sang trạng thái chờ thông tin bổ sung (`needs_input`).
- Đảm bảo dữ liệu reconciliation và unresolved reasons xuất hiện đồng nhất trong lịch sử hội thoại và turn references mà không làm thay đổi layout hay copy giao diện.

### R8: Xuất bản và lưu vết Contract + Journal trong Transcripts
- Dataclass `AgentResponse` cung cấp hai trường dữ liệu đọc authoritative: `turn_contract` và `execution_journal`.
- Kịch bản xuất `scripts/export_reconciliation_transcripts.py` đã ghi nhận đầy đủ snapshots của contract, journal, receipts, artifacts và failure traces vào file transcript tại thư mục audit độc lập này.

---

## 3. Làm rõ Provenance và Diễn giải Kỹ thuật

1. **Ý nghĩa mã băm SHA-256**: Các mã băm được báo cáo trong `source_hashes.json` và `validation.json` là checksum toàn vẹn nội dung tệp tin để theo dõi thay đổi mã nguồn, không phải chữ ký điện tử số (cryptographic digital signatures).
2. **Độ bao phủ của bộ 224 tests**: 224 bài kiểm tra đã chạy thành công là một tập hợp các test suites được chọn lọc phục vụ mốc reconciliation và tương tác cốt lõi; chúng không đại diện cho 100% độ bao phủ của toàn bộ repository.
3. **Bản chất của fixture pre-cancel**: Bài kiểm tra `test_cancel_during_waiting_probe_has_zero_artifacts` là một fixture kiểm tra hành vi hủy trước khi tool được kích hoạt (`pre-execution cancel`), không phải là một bài kiểm tra ngắt kết nối mạng hoặc timeout tầng HTTP in-flight.
4. **Phân định giữa Test phần mềm và Chất lượng Model**: Việc vượt qua các unit tests và contract probes dựa trên mock client chứng minh tính đúng đắn của logic đối soát và luồng dữ liệu của bộ máy phần mềm; điều này **không chứng minh** hay thay thế việc đánh giá năng lực ngôn ngữ tự nhiên và chất lượng suy luận của mô hình thật trong môi trường thực tế.

---

## 4. Tình trạng và Bước tiếp theo

- **Thư mục cũ được bảo toàn nguyên vẹn**:
  - `audit/rat_core_reconciliation_20261013/` (không bị ghi đè)
  - `audit/rat_reconciliation_codex_review_20261013/` (không bị sửa đổi)
- **Mã nguồn sạch, sẵn sàng cho Codex Review**:
  - Toàn bộ 19 probes của Codex đã chạy và PASS mà không chỉnh sửa bất kỳ assertion nào trong file probe.
  - Sẵn sàng bàn giao cho Codex kiểm tra lại trước khi bước vào các thảo luận về Phase UI Presentation hoặc kế hoạch đo lường thực nghiệm (Ablation / Live Pilot).
