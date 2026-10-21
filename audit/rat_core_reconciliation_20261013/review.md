# Báo cáo bàn giao Core RAT: Completion Reconciliation theo ADR-003

**Ngày:** 2026-10-13 | **Múi giờ:** Asia/Saigon  
**Phạm vi:** Core completion contract, execution journal, receipt matching và history references wiring.  
**Vai trò phối hợp:** Codex thiết kế và review; Antigravity triển khai mã nguồn core và fixtures.  

---

## 1. Ranh giới thực hiện & Các cam kết đã tuân thủ

1. **Core trước, duyệt UI sau:** Toàn bộ tầng core (`rat/engine/completion.py`, `rat/engine/assistant_runtime.py`, `rat/ui/chat_session.py`, `rat/ui/omnibar.py`) đã được hoàn thiện và kết nối đúng đắn. Không thay đổi layout Qt, composer, badge trực quan, biểu cảm Chuột hay copy người dùng trên bề mặt sản phẩm.
2. **Không gọi model thật (Zero live calls):** Chưa chạy benchmark/ablation trực tiếp với model vì ngân sách (calls/time/model) chưa được người dùng phê duyệt.
3. **Phân định ranh giới bằng chứng:** Kết quả kiểm thử phần mềm (**197/197 passed**) chỉ chứng minh các ràng buộc contract, lifecycle và matching hoạt động chính xác theo mã nguồn, **không** được đánh đồng với chất lượng suy luận tự nhiên hay độ chính xác NLP của model thật.
4. **Bảo tồn tài nguyên:** Không sửa đổi Stage 0 gate, pipeline nghiên cứu NCKH, DocAI (`modules/docai/`), hay các thư mục audit cũ. Không thực hiện các lệnh nguy hiểm (`git push/pull/reset/force`).

---

## 2. Thiết kế & Triển khai Kỹ thuật Core

### 2.1 Mô hình 4 trục độc lập (`rat/engine/completion.py`)
Hệ thống phân tách rạch ròi 4 trục trạng thái theo đúng tinh thần của ADR-003:
- **`lifecycle`**: Vòng đời kỹ thuật của lượt (`completed`, `in_progress`, `needs_input`, `failed`, `cancelled`).
- **`intent_coverage`**: Độ phủ ý định người dùng từ model (`model_proposed`, `ambiguous`, `invalid`, `unchecked`). Nếu model không khai contract hoặc contract lỗi, giữ nguyên `unchecked`.
- **`declared_scope_completion`**: Mức độ thỏa mãn các nghĩa vụ đã khai (`satisfied`, `partial`, `unresolved`, `unchecked`). Một turn chỉ được coi là hoàn tất khi mọi nghĩa vụ trong hợp đồng đều có receipt hợp lệ; hứa trong văn bản ("đã ghi/đã tính") mà thiếu biên nhận sẽ bị xếp vào `unresolved` với lý do `omitted_action`.
- **`scoped_quality`**: Chất lượng kiểm tra nội bộ trong phạm vi hẹp (`PASS`, `FAIL`, `UNKNOWN`, `not_checked`). Trạng thái arithmetic `PASS` không tự động biến thành workflow completion.

### 2.2 Đóng băng hợp đồng trước effect đầu tiên (`freeze()`)
Model đề xuất danh sách `outcomes` lúc bắt đầu lượt (planner ON hoặc OFF). Ngay trước khi thao tác có hiệu ứng phụ (tool call) đầu tiên diễn ra, runtime thực hiện `turn_contract.freeze()`. Mọi cố gắng thêm, sửa, hoặc xóa bỏ nghĩa vụ sau đó đều ném ngoại lệ `RuntimeError`, ngăn model tự xóa nghĩa vụ để ngụy tạo thành công.

### 2.3 Trusted Execution Journal & Biên nhận (`ReceiptEnvelope`)
Runtime duy trì một `ExecutionJournal` cấp request (gồm `conversation_id`, `turn_id`, `execution_id`). Mọi thao tác qua `dispatcher`, `notebook`, và `verification` đều được cấp biên nhận có chữ ký cấu trúc (`ReceiptEnvelope`). Reconciler từ chối mọi dict biên nhận giả mạo do model tự khai và ngăn chặn việc dùng biên nhận từ `exec-1` để thỏa mãn đột biến ở `exec-2`.

### 2.4 Khớp nối Producer Output và Consumer Note
Reconciler kiểm tra chuỗi phụ thuộc (`source_ref` / `dependency_ids`):
- Khi một outcome yêu cầu ghi nhận kết quả của phép tính vừa thực hiện (`producer_outcome_id`), nhưng ghi chú lại tham chiếu tới một artifact cũ khác (ví dụ: tính 324 nhưng tiêu thụ artifact 126 của lượt trước), reconciler phát hiện mismatch và đánh dấu nghĩa vụ là thất bại với lý do `wrong_source_consumer`.
- Kiểm tra biên giới sống còn: Nếu một ghi chú được tạo ra rồi bị xóa (`remove`) ngay trong cùng execution, kiểm tra snapshot cuối lượt sẽ phát hiện ghi chú không còn tồn tại và đánh dấu `note_removed` / `removed_before_completion`.

### 2.5 Hai kịch bản Cancel độc lập
- **Cancel sau khi commit artifact:** Thao tác commit (`calculate`) thành công tạo ra artifact được bảo toàn trong store. Lệnh cancel sau đó chặn các ghi chú muộn trong cùng execution. Lượt tiếp theo mở ra một `execution_id` mới có thể đọc lại artifact này và tiếp tục ghi chú thành công.
- **Cancel trong lúc thăm dò chờ:** Khi hủy giữa chừng một probe chưa commit, hệ thống bảo đảm 0 artifact nào bị ghi nhận, ghi nhận trạng thái `cancelled` và `unresolved`.

---

## 3. Kết nối Runtime và Lịch sử Hội thoại

1. **`rat/engine/assistant_runtime.py`**:
   - Khởi tạo `ExecutionJournal` cho mỗi `run()`.
   - Đóng băng hợp đồng trước khi thực thi tool đầu tiên.
   - Tự động ghi biên nhận cho operations, note events và verifications.
   - Chạy hàm thuần túy `reconcile_turn(...)` ở ranh giới hoàn tất lượt và trả về `TurnReconciliation` trong `AgentResponse.reconciliation`.
2. **`rat/ui/chat_session.py`**:
   - `TurnSnapshot` mở rộng thêm trường `reconciliation` và `reconciliation_status`.
   - Các phương thức `complete_turn()`, `fail_turn()`, `cancel_turn()` lưu trữ reconciliation và cập nhật trạng thái tương ứng.
   - `turn_references()` xuất thông tin `reconciliation_status`, `reconciliation`, và `unresolved_reasons` cho các consumer hạ nguồn.
3. **`rat/ui/omnibar.py`**:
   - Chuyển tiếp `response.reconciliation` vào `_conversation.complete_turn()`.
   - Không thay đổi layout hay copy hiển thị trong pha này.

---

## 4. Kết quả Kiểm thử & Xác minh Headless

Bộ kiểm thử headless bao gồm **197 tests** chạy qua pytest (thời gian: 30.64s):
- **11 fixtures mới (`tests/test_rat_completion_reconciliation.py`)** kiểm tra toàn bộ các ca đối chiếu, ca biên giới và ca phủ định:
  1. `test_omitted_outcome_model_claims_saved_without_tool_execution`: Model nói đã lưu nhưng không gọi tool -> `unresolved`, `omitted_action`.
  2. `test_wrong_source_producer_consumer_calculate_324_save_126_fails`: Tính 324 nhưng ghi 126 -> `partial`, `wrong_source_consumer`.
  3. `test_cross_execution_receipt_cannot_satisfy_new_mutation`: Biên nhận cũ từ exec trước không thể thỏa mãn exec mới -> `unresolved`.
  4. `test_contract_freeze_prevents_downgrade_or_obligation_deletion`: Không thể xóa nghĩa vụ sau khi đã freeze.
  5. `test_pending_input_reconciles_to_needs_input_and_unresolved`: Chờ input người dùng -> `needs_input`, `unresolved`.
  6. `test_cancel_after_calculate_commit_preserves_artifact_and_resumes_in_new_exec`: Giữ artifact đã commit, tiếp tục ở execution mới -> `satisfied`.
  7. `test_cancel_during_waiting_probe_has_zero_artifacts`: Hủy probe -> 0 artifacts, `cancelled`.
  8. `test_conversational_response_without_tools`: Trả lời thuần văn bản thỏa mãn response outcome mà không cần tool.
  9. `test_proposed_note_does_not_satisfy_confirmed_obligation`: Ghi chú proposal không thỏa nghĩa vụ confirmed -> `unresolved`.
  10. `test_note_created_then_removed_in_same_execution_fails_boundary_check`: Tạo rồi xóa trong cùng lượt -> `note_removed`, `unresolved`.
  11. `test_stale_revision_update_is_unmet`: Cập nhật revision lỗi thời -> `unresolved`.
- **186 regression tests kế thừa** (bao gồm `test_rat_calculation_conversation`, `test_work_context`, `test_rat_chat_session`, `test_assistant_runtime`, v.v.) tiếp tục vượt qua 100%.

Toàn bộ log chi tiết được lưu tại `audit/rat_core_reconciliation_20261013/test_logs.txt`.  
Transcripts chi tiết của 11 fixtures (outcomes, receipts, matched/unmet IDs, artifacts) được xuất tại `audit/rat_core_reconciliation_20261013/transcripts/fixture_transcripts.json`.

---

## 5. Bảng SHA-256 Source Files

| Tệp nguồn | SHA-256 Ban đầu (HEAD) | SHA-256 Hiện tại |
| --- | --- | --- |
| `rat/engine/completion.py` | *(Tạo mới)* | `596a1c69368d256cb33fa039b764d38acb43051bc2071b32655200f59a5ef30f` |
| `rat/engine/assistant_runtime.py` | `ed349eb746708786b7df0756d20d2845a432b4665471e433191cb20104258977` | `3a8be41260f87c298439f7f1f864b44e0b475730a54395ff41ce8fdfeac3fcc0` |
| `rat/ui/chat_session.py` | `366056822407c3438a492c97d943dbd7bb09de674b914d46e6861eec95059271` | `13dd0a5f2b6dfd25e0c1a0b29f3e98b575b404ee9848a7603d0ffa8d2ed78b44` |
| `rat/ui/omnibar.py` | `f02bfc8061c97646e63b27ff7593a174ab13d18d8bbd058f91678685a0c01671` | `657fbe090f2ec9bd7e8697c6ea240506b3b505a094c471f8169289801380b401` |
| `tests/test_rat_completion_reconciliation.py` | *(Tạo mới)* | `d8383866667ca17c92b74389d3468314038cd1bb29bdd555bf0247ee4da26edd` |
| `tests/test_rat_calculation_conversation.py` | *(Kế thừa)* | `01b2289c8942a4fc0197d6fa925c43d7890f6b412bf6fe750c3bc05fa9bb3ce3` |

Diff hoàn chỉnh được lưu tại `audit/rat_core_reconciliation_20261013/core_diff.patch`.

---

## 6. Trạng thái Bàn giao & Bước tiếp theo cho Codex Review

1. **Phần Core hoàn tất:** Lớp logic hợp đồng, matching và lưu trữ references đã hoàn tất 100% theo đặc tả ADR-003.
2. **Phần UI chờ duyệt:** Giao diện hiển thị, nhãn trạng thái unresolved trên UI và copy review được tách thành pha tiếp theo để Codex đánh giá.
3. **Live model budget:** Khi người dùng phê duyệt ngân sách kiểm thử trực tiếp cho các model cụ thể, tiến hành chạy đo đạc và so sánh A/B planner ON vs OFF.
