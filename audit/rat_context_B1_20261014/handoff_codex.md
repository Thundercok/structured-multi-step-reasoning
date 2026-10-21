# Bàn giao B1: Headless Context Projection Compiler cho Codex Review

**Ngày thực hiện:** 2026-10-14, Asia/Saigon  
**Tác giả triển khai:** Antigravity (Anti)  
**Người nhận review:** Codex  
**Giai đoạn:** Package B — Bước B1 (Headless Context Projection Compiler thuần)  
**Trạng thái kiểm tra:** 312/312 tests passed (14 B1 compiler tests + 292 core regressions + 6 context audit tests + design builder check)  
**Phạm vi:** Hoàn toàn headless, 0 state store mới, 0 live model calls, 0 UI/Qt, 0 thay đổi loop thực thi runtime (`_call_model`/`run` giữ nguyên cho B2).

---

## 1. Tóm tắt kết quả Deliverable B1

Triển khai thành công module compiler thuần `rat/engine/context_snapshot.py` và bộ kiểm thử tương ứng `tests/test_rat_context_snapshot.py` theo đúng thiết kế tại `docs/adr-004-rat-context-snapshot.md` và các quyết định kỹ thuật ưu tiên tại `audit/rat_context_B_assignment_20261014/decisions.md`.

### Các file bàn giao trong B1:
- `rat/engine/context_snapshot.py`: Pure compiler, RFC 6901 pointer resolver, typed `$value_ref` expander, security guard và schema/semantic validator.
- `tests/test_rat_context_snapshot.py`: 14 tests tự chứa bao phủ toàn bộ các góc cạnh ngữ nghĩa, an toàn, tái cấu trúc lossless và lỗi biên.
- `audit/rat_context_B1_20261014/`: Gói bằng chứng kiểm thử đầy đủ (`manifest_start.json`, `manifest_finish.json`, `changes.patch`, `test_run.json`, `example_snapshots.json`, `validation.json`, `handoff_codex.md`).

---

## 2. Đối chiếu chi tiết với ADR-004 và decisions.md

### A. Context projection không tạo thêm "sự thật" (`decisions.md` §1)
- Compiler chỉ nhận canonical copies từ các stores hiện có (`TurnContract`, `ExecutionJournal`, `WorkNotebook`, `ArtifactStore`).
- Không đoán intent, không tự suy ra relevance, không chèn outcome giả.
- Dữ liệu thô và authority được giữ nguyên vẹn (`model_proposed`, `runtime_bound_model_proposal`, `confirmed_user_fact`, `observed_result`, `unconfirmed_model_suggestion`, `observed_search_metadata`, `observed_source_content`, `observed_operation_result`, `runtime_committed_effect`, `scoped_verification_proof`).

### B. Progress dùng bằng chứng biên nhận toàn cục — Không map outcome→receipt giả (`decisions.md` §2)
- Sử dụng trực tiếp pure reconciler hiện có `reconcile_turn(contract, journal, lifecycle="in_progress", final_answer="", ...)` trên bản copy.
- Chỉ với contract hợp lệ, không rỗng, coverage không `invalid`/`unchecked`: các outcome không nằm trong `report["unmet_outcomes"]` được đánh dấu provisional `met` tại ranh giới snapshot.
- Outcome kiểu `response` giữ nguyên trạng thái `pending_response` (chưa có câu trả lời cuối cùng).
- Hợp đồng không đủ điều kiện (`empty`, `invalid`, `unchecked`): tất cả outcome giữ trạng thái `unresolved` với lý do `contract_not_eligible_for_provisional_match`. Tuyệt đối không lấy phần bù của tập rỗng để đánh tất cả là `met`.
- Tiến độ báo cáo danh sách ID biên nhận khớp toàn cục `evidence.matched_receipts`. Tuyệt đối không thêm `receipt_ids` vào từng outcome object.
- Tuyệt đối không sao chép `summary`, `lifecycle`, hay `declared_scope_completion` của terminal completion vào progress.

### C. Epochs độc lập và cờ `selection_set` rõ ràng (`decisions.md` §3)
- `boundary.generation`: Epoch của journal và notebook (đổi khi invalidate/clear/reset).
- `boundary.artifact_store_generation`: Epoch của `ArtifactStore` (đổi khi store clear).
- `indexes.selection_set`: Boolean flag rõ ràng phân biệt giữa:
  - `selection_set = False`: Chưa từng thực hiện thao tác chọn kết quả (`selected_results = []`).
  - `selection_set = True`: Đã thực hiện thao tác chọn nhưng không chọn mục nào (`selected_results = []`).

### D. Giữ đầy đủ văn bản Note across Revisions — Không ID-only old notes (`decisions.md` §2, ADR-004 §3)
- Mọi revision của note (cả active lẫn historical) đều giữ nguyên văn bản đầy đủ inline trong `body["text"]`.
- Không rút gọn các bản ghi cũ thành ID-only vì `inspect_artifact` chưa đọc được `WorkNotebook`.
- Các liên kết thay thế (`replaces_text`, `replaced_by_text`) được biểu diễn bằng `$value_ref` trỏ tới `/text` của revision tương ứng.

### E. RFC 6901 `$value_ref` và Security Guard (ADR-004 §3)
- `$value_ref` chỉ được giải mã trong danh mục các slot chiếu có kiểu được đăng ký (`ALLOWED_VALUE_REF_SLOTS` gồm `quote`, `source_ref.quote`, `replaces_text`, `replaced_by_text`, `snapshot`, `note`, `note_event`, `operation_result`, `verification_report`).
- JSON không đáng tin từ người dùng (user messages, query, task state) nếu chứa key `$value_ref` sẽ được giữ nguyên dưới dạng dict thô, tuyệt đối không bị dereference đệ quy, triệt tiêu nguy cơ injection/spoofing.
- Các tham số khai báo nguyên bản (`expected_args`, `operation_args`) luôn được giữ nguyên giá trị literal, không bị ghi đè thành con trỏ.

### F. Xử lý tác vụ không có Artifact
- Khi một operation (như `record_work_note`, tính toán, hoặc custom op) phát sinh receipt có `operation_result` nhưng không tạo artifact trong `ArtifactStore`:
  - Compiler tạo entity kiểu `operation_result` với `ref = {"kind": "operation_result", "execution_id": ..., "receipt_id": ...}`.
  - Tuyệt đối không phát sinh `artifact_id` giả trong entities hay `artifact_pins`.

---

## 3. Tổng hợp kết quả xác minh

Tất cả các bài test chạy trên Python 3.12 sạch (`PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`):

| Bộ kiểm thử | Số tests | Thời gian | Trạng thái |
| :--- | :---: | :---: | :---: |
| `tests/test_rat_context_snapshot.py` (B1 Compiler Unit Tests) | 14 | 3.23s | **PASSED** |
| Core Reconciler + Probes Regressions (292 tests) | 292 | 7.93s | **PASSED** |
| Context Audit Tests (`test_rat_context_audit.py`) | 6 | 0.80s | **PASSED** |
| Design Builder (`build_and_validate.py`) | 25 files | 1.86s | **PASSED** |
| **Tổng cộng** | **312** | **13.82s** | **100% PASSED** |

### Các ca kiểm thử B1 tiêu biểu:
1. `test_schema_loads_and_design_fixtures_validate_cleanly`: Schema và cả 2 design fixture (`after.snapshot.json`, `declared_args.snapshot.json`) đạt chuẩn JSON Schema Draft 2020-12.
2. `test_lossless_reconstruction_of_after_fixture_entities`: Tái cấu trúc mở rộng ngược hoàn hảo giá trị quote, replacement text, note_event snapshot và dispatch operation_result.
3. `test_provisional_progress_eligible_contract_evaluation`: Đánh giá đúng `met` cho effect và `pending_response` cho response, evidence toàn cục.
4. `test_provisional_progress_ineligible_contracts_remain_unresolved`: Hợp đồng rỗng, cycle, hoặc invalid coverage đều giữ `unresolved`.
5. `test_distinct_authority_and_provenance`: Phân định đúng 6 cấp thẩm quyền khác nhau của entities.
6. `test_operation_without_artifact_does_not_invent_fake_artifact_id`: Không sinh artifact ID giả.
7. `test_security_guard_untrusted_fake_value_ref_is_not_expanded`: Chặn đứng injection `$value_ref` từ user/task payload.
8. `test_coherence_epochs_and_selection_set_distinction`: Phân biệt rạch ròi 3 trạng thái selection và 2 epoch riêng.
9. `test_full_note_text_retention_across_revisions`: Toàn vẹn nội dung văn bản qua các lần sửa đổi note.
10. `test_rfc6901_pointer_edge_cases`: Xử lý đúng escaping `~1`, `~0`, empty pointer, array indices và bắt lỗi chính xác.

---

## 4. Tách bạch ranh giới B1 và các bước tiếp theo (B2)

- **Ranh giới B1 nghiêm ngặt:** B1 chỉ là pure compiler (`context_snapshot.py`). Không có bất kỳ dòng code nào can thiệp vào `AssistantRuntime._call_model` hay vòng lặp thực thi `run()`.
- **Bảo toàn:** Mọi file core (`rat/engine/completion.py`, `rat/engine/assistant_runtime.py`, `rat/engine/work_notes.py`) và toàn bộ các audit artifact trước đó được giữ nguyên vẹn.
- **Sẵn sàng cho Codex:** Kính chuyển Codex xem xét kiến trúc, ngữ nghĩa và bộ tests của B1. Sau khi Codex duyệt, Anti sẽ tiếp tục nhận phần B2 (wiring boundary inputs/rendering vào `AssistantRuntime` và capture before/after requests).
