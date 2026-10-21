# Antigravity Implementation Report: Core Reconciliation Round 2

**Ngày**: 2026-10-13, Asia/Saigon  
**Vai trò**: Codex thiết kế & review, Antigravity triển khai  
**Trạng thái**: Hoàn thành toàn bộ gates Core Round 2; sẵn sàng cho Codex review core trước khi bước sang phase UI presentation / live model.

---

## 1. Tóm tắt kết quả kiểm thử

Tất cả 13 ca lỗi (trên tổng số 14 probes) được phát hiện trong Codex review Round 2 cùng toàn bộ test suites đã được giải quyết triệt để:

| Bộ kiểm thử | Số ca | Kết quả | Thời gian | Ghi chú |
|---|---|---|---|---|
| **Remaining Contract Probes (Round 2)** | 14 | **14 / 14 PASSED** | 0.44s | Khắc phục 13/14 failures từ Round 2 |
| **Contract Probes (Round 1)** | 19 | **19 / 19 PASSED** | 0.51s | Giữ nguyên 100% pass rate từ Round 1 |
| **Tổng Contract Probes** | 33 | **33 / 33 PASSED** | 0.73s | Chạy đồng thời không phát sinh xung đột |
| **Selected Regression Suite** | 227 | **227 / 227 PASSED** | 8.15s | Bao gồm unit, contract, kernel & lifecycle tests |
| **Export Transcripts (11 Fixtures)** | 11 | **11 / 11 PASSED** | 3.55s | Transcripts đầy đủ contract, journal, envelopes |

> [!NOTE]
> Toàn bộ các kết quả trên được thực thi bằng mock/fixtures và deterministic execution journals trong môi trường kiểm thử. Không có cuộc gọi live model, không tiêu tốn API token, và không đại diện cho đo lường chất lượng model thực tế.

---

## 2. Chi tiết triển khai theo các Findings của Codex (R1 – R6)

### R1 [P1] Proof Envelope & Lineage Linkage
- **Hiện tượng cũ**: `ExecutionJournal.record_verification` lưu `parent_receipt_ids` ở `ReceiptEnvelope`, nhưng matcher tìm `operation_receipt_id`/`parent_receipt_ids` bên trong payload `verification_report`. Khiến positive control phép tính `18 * 7` với verification PASS vẫn không được thỏa mãn.
- **Giải pháp**:
  - `TurnReconciliation._resolve_verification_report` được cập nhật để đối chiếu trực tiếp qua `ReceiptEnvelope` (`envelope.parent_receipt_ids` và `envelope.operation_call_id`).
  - Kiểm tra nghiêm ngặt `envelope.status == "PASS"` và scope khớp với `required_proof_scope`. Proof từ call khác, proof thiếu, hoặc proof có status UNKNOWN/FAIL đều bị từ chối.
  - Positive control `test_correct_calculation_with_linked_pass_proof_is_satisfied` chuyển từ FAILED sang PASSED.

### R2 [P1] Typed Input Binding & Bỏ Heuristic Substring Matcher
- **Hiện tượng cũ**: Matcher xóa khoảng trắng rồi kiểm tra `expr_clean in desc_clean`, dẫn tới phép tính sai (ví dụ `118 * 7`) vẫn thỏa mãn outcome có description chứa `18 * 7`.
- **Giải pháp**:
  - Bổ sung `OutcomeSpec.expected_args: dict[str, Any]` với schema rõ ràng.
  - Bỏ hoàn toàn logic regex substring. `CalculateOperationAdapter` chuẩn hóa biểu thức số học qua parser và đối chiếu canonical expression:
    ```python
    req_canon = canonicalize_expression(expected_expr)
    call_canon = canonicalize_expression(call_expr)
    if req_canon == call_canon:
        ...
    ```
  - `test_wrong_expression_cannot_match_by_substring` chuyển từ FAILED sang PASSED.

### R3 [P1] Terminal Note Matcher & Authority Verification
- **Hiện tượng cũ**: `_match_note` lấy `source_ref` từ event lịch sử và bỏ qua `required_proof_scope`/`required_authority`. Một note bị sửa đổi nguồn ở revision sau vẫn được tính là satisfied bởi receipt cũ.
- **Giải pháp**:
  - Matcher đối chiếu toàn diện đối với **terminal version** của note trong `notebook_snapshot` hoặc event stream mới nhất.
  - Xác thực đầy đủ: `source_ref`, `field`, `text`, `source_verification` (proof scope & authority), và revision update. Nếu note terminal thiếu proof scope đã khai hoặc đã bị đổi nguồn ở revision sau, outcome sẽ không được thỏa mãn.
  - `test_note_cannot_satisfy_required_source_proof_when_no_proof_exists` và `test_terminal_confirmed_note_must_still_match_required_source` chuyển từ FAILED sang PASSED.

### R4 [P1] Native ON/OFF Protocol & Envelope Decoding
- **Hiện tượng cũ**: Planner OFF trả về JSON chứa metadata `outcomes`/`contract`, làm leak cả JSON string vào `AgentResponse.answer`. Payload malformed ném uncaught `AttributeError` hoặc `RuntimeError` làm crash runtime thay vì trả về invalid reconciliation có log.
- **Giải pháp**:
  - Bổ sung logic trích xuất `answer` sạch từ payload JSON trong `assistant_runtime.py`, tách biệt hoàn toàn user-facing text và metadata contract.
  - Bọc decoder an toàn: các payload malformed (e.g. `outcomes=["malformed"]`) hoặc dictionary chứa metadata không hợp lệ được bắt và gán `intent_coverage = "invalid"`, ghi error log rõ ràng.
  - Model không thể tự gán các cờ tin cậy (`frozen`, `is_valid`): runtime tự bind trusted identity và tự thực hiện freeze.
  - `test_native_off_contract_envelope_is_not_user_facing_answer`, `test_malformed_native_outcomes_return_invalid_result_instead_of_crashing`, và `test_untrusted_frozen_contract_metadata_does_not_crash_runtime` chuyển từ FAILED sang PASSED.

### R5 [P1] DAG Cycle Validation & Topological Matching
- **Hiện tượng cũ**: Matcher duyệt outcome theo thứ tự khai báo danh sách thay vì topological dependency order, khiến thứ tự consumer-first bị `partial` trong khi producer-first lại `satisfied` với cùng tập actions/receipts. Cycle A ↔ B vẫn bị lọt.
- **Giải pháp**:
  - Phát hiện chu trình (cycle detection qua DFS) ngay trong `TurnContract.__post_init__`; nếu có cycle, hợp đồng tự động set `is_valid = False` và `intent_coverage = "invalid"`.
  - Thực hiện `topological_sort_outcomes` trong `MatchContext` và theo dõi tiến trình qua `satisfied_outcome_ids`. Đảm bảo thứ tự khai báo (producer-first hay consumer-first) cho cùng một tập hành vi và receipts sẽ luôn cho ra kết quả verdict như nhau.
  - `test_cyclic_dependencies_cannot_be_satisfied` và `test_valid_producer_consumer_matching_is_independent_of_declaration_order` chuyển từ FAILED sang PASSED.

### R6 [P2] Recursive Deep Freezing
- **Hiện tượng cũ**: `TurnContract.freeze()` chỉ đóng setter ở tầng ngoài (`__setattr__`), nhưng các nested dictionary/list (`source_ref`, `target_ref`, `dependency_ids`) vẫn có thể bị mutate bằng `.clear()` hoặc `__setitem__`. Cờ `frozen` có thể bị gán lại `False`.
- **Giải pháp**:
  - Thêm `_freeze_nested`: đóng băng đệ quy các trường lồng nhau bằng `types.MappingProxyType` và `tuple`.
  - Chặn triệt để việc gán `frozen = False` (raise `RuntimeError`).
  - Mọi thao tác sửa đổi sau khi freeze đều raise `(RuntimeError, AttributeError, TypeError)`.
  - `test_freeze_also_protects_nested_refs_and_dependencies` (3 variants: `source_ref`, `target_ref`, `dependency_ids`) chuyển từ FAILED sang PASSED.

---

## 3. Duy nhất một nguồn sự thật Completion & Migration Assertion Legacy

- **Loại bỏ fallback**: Trong `rat/engine/assistant_runtime.py`, đã xóa fallback tự động gán `completion_status = "model_reported_in_progress"`. Giờ đây `completion_status` hoàn toàn phản ánh phán quyết của `TurnReconciliation`. Trạng thái model tự khai báo được giữ nguyên và cô lập trong `response.task_state`.
- **Migration assertion tại `tests/test_rat_task_memory.py:31`**:
  ```diff
  -    assert response.completion_status == "model_reported_in_progress"
  +    # Per ADR-003: completion_status is solely driven by TurnReconciliation (unchecked here).
  +    # Model reported state is isolated in task_state without altering single completion truth.
  +    assert response.completion_status == "unchecked"
  +    assert response.task_state.get("status") == "in_progress"
  +    assert response.reconciliation.intent_coverage == "unchecked"
  ```
  *Lý do*: Theo ADR-003, không cho phép hai nguồn sự thật về hoàn thành tác vụ. Test vẫn kiểm tra đầy đủ việc task state ghi nhận `in_progress`, và reconciliation ghi nhận `unchecked` do model không khai báo outcomes. Không có test nào bị skip hoặc xfail.

---

## 4. Bảo vệ Thư mục Audit & Xử lý Hash Manifest

1. **Exporter Fresh-Directory Guard**:
   - `scripts/export_reconciliation_transcripts.py` đã được cập nhật để kiểm tra `os.path.exists(output_dir)`. Nếu thư mục đã tồn tại, script sẽ raise `FileExistsError` ngay trước khi chạy fixtures hoặc ghi file.
   - Thư mục audit `audit/rat_core_reconciliation_round3_20261013/` được tạo mới hoàn toàn, không ghi đè bất kỳ artifact lịch sử nào.
2. **Khắc phục Discrepancy Hash ở Round 2**:
   - Trong Round 2, manifest ghi nhận hash nháp của `scripts/export_reconciliation_transcripts.py` (`7d929b...`) trong khi file thực tế là `283656...`.
   - Trong Round 3, file đã được chỉnh sửa bổ sung guard và hash được đo lường chính xác, đồng nhất giữa trước và sau test run tại `2da1a0e186240efbc41ba855ca740d455bbee8a9108dc225719de52dd90f979c`.
   - Báo cáo cũ được giữ nguyên không chỉnh sửa, sự khác biệt được ghi nhận minh bạch trong `source_hashes.json`.

---

## 5. Artifacts trong thư mục Audit Round 3

Thư mục: [`audit/rat_core_reconciliation_round3_20261013/`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_core_reconciliation_round3_20261013/)
- [`diff_from_reviewed_source.patch`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_core_reconciliation_round3_20261013/diff_from_reviewed_source.patch): Toàn bộ diff so với reviewed source của Round 2 (57,362 bytes).
- [`source_hashes.json`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_core_reconciliation_round3_20261013/source_hashes.json): SHA256 trước và sau kiểm thử của các file core, kèm ghi chú giải quyết lệch hash exporter.
- [`transcripts/fixture_transcripts.json`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_core_reconciliation_round3_20261013/transcripts/fixture_transcripts.json): 11 fixtures hoàn chỉnh với contract, journal, verification envelopes, terminal notes.
- [`contract_probes.txt`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_core_reconciliation_round3_20261013/contract_probes.txt): Log thực thi 33 probes (19 R1 + 14 R2) đạt 100% PASS.
- [`regression_tests.txt`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_core_reconciliation_round3_20261013/regression_tests.txt): Log thực thi 227 regression tests đạt 100% PASS.
- [`validation.json`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_core_reconciliation_round3_20261013/validation.json): Metadata tổng hợp trạng thái validation.

---

## 6. Gates Chưa Kiểm (Unchecked Gates) & Bàn giao Codex

Theo đúng chỉ đạo của user: **Không tự ý chấm hoàn tất 100% từ tests xanh; Codex cần review lại core trước khi chuyển sang phase UI presentation.**

Các hạng mục còn lại chưa thực hiện trong phase này:
1. **Live Model Ablation**: Chưa gọi mô hình thực tế, chưa đo lường latency hoặc token overhead trực tiếp trên GPU/API.
2. **UI Presentation & Omnibar Badging**: Chưa mở rộng component hiển thị thẻ UI hoặc badge tiến trình trực quan cho người dùng.
3. **Multi-turn Agent Dynamic Replanning**: Cần Codex đánh giá độ ổn định của contract reconciliation khi agent sinh hợp đồng động qua nhiều lượt hỏi-đáp phức tạp.
