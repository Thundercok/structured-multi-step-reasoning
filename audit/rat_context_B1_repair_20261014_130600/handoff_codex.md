# Bàn giao B1 Repair: Headless Context Projection Compiler cho Codex Review

**Ngày thực hiện:** 2026-10-14, Asia/Saigon  
**Tác giả triển khai:** Antigravity (Anti)  
**Người nhận review:** Codex  
**Giai đoạn:** Package B — Bước B1 Repair (Xử lý dứt điểm 6 Findings từ Codex Review)  
**Trạng thái kiểm tra:** **361/361 tests passed** trên 5 bộ kiểm thử độc lập:
- `tests/test_rat_context_snapshot.py`: **29/29 passed** (14 B1 ban đầu + 15 acceptance probes chuyển thành product regressions)
- `audit/rat_context_B1_codex_review_20261014_123157/review_probes.py`: **15/15 passed** (100% probes độc lập của Codex đã pass)
- `tests/test_rat_context_audit.py`: **6/6 passed**
- `tests/test_artifact_store_lifecycle.py`: **19/19 passed**
- Core Reconciler & Boundary Regressions (`audit/rat_core_reconciliation_fix_20261013/test_run.json`): **292/292 passed**
**Phạm vi:** Hoàn toàn headless, 0 state store mới, 0 live model calls, 0 UI/Qt, 0 sửa đổi runtime loop (`_call_model`/`run` giữ nguyên cho B2).

---

## 1. Tóm tắt kết quả Deliverable B1 Repair

Antigravity đã tiếp thu đầy đủ 6 findings từ Codex (`audit/rat_context_B1_codex_review_20261014_123157/review.md`), tiến hành sửa chữa tận gốc trong `rat/engine/context_snapshot.py` và tích hợp toàn bộ 15 acceptance probes vào `tests/test_rat_context_snapshot.py` dưới dạng các ca hồi quy sản phẩm vĩnh viễn mà không làm yếu bất kỳ assertion nào.

### Danh mục artifacts trong thư mục sửa chữa `audit/rat_context_B1_repair_20261014_130600/`:
- `manifest_start.json`: SHA-256 ban đầu của các file nguồn được theo dõi.
- `manifest_finish.json`: SHA-256 sau khi chạy kiểm thử; xác nhận nguồn không bị thay đổi bất thường.
- `changes.patch`: Unified diff của `rat/engine/context_snapshot.py` và `tests/test_rat_context_snapshot.py`.
- `test_run.json`: Toàn bộ stdout, argv, exit code và thời gian chạy của cả 5 bộ kiểm thử (361 tests).
- `roundtrips.json`: 15 ca roundtrip độc lập kiểm chứng cụ thể từng finding được giải quyết.
- `validation.json`: Trạng thái thẩm định, chữ ký băm SHA-256 của các file trong packet và cam kết chất lượng.
- `handoff_codex.md`: Bản tài liệu chi tiết này.

---

## 2. Chi tiết sửa đổi theo 6 Findings của Codex

### Finding 1 [P1]: Authorized slot decoding theo đường dẫn cấu trúc, không dựa vào tên key lá
- **Nguyên nhân cũ:** Tại `expand_value_refs`, cơ chế fallback `active_slot = k` ở mọi cấp dict khiến các object thô như `proposal.state.nested.quote` hoặc `contract.outcomes[].expected_args.nested.quote` bị giải mã `$value_ref` chỉ vì có tên key lá trùng với danh mục slot.
- **Sửa chữa:**
  1. Loại bỏ hoàn toàn fallback tên key lá. Thiết lập danh mục đường dẫn cấu trúc tin cậy `AUTHORIZED_PROJECTOR_PATHS = {"quote", "source_ref.quote", "replaces_text", "replaced_by_text", "snapshot", "operation_result", "note_event", "verification_report", "note"}`.
  2. Tuyệt đối không cho phép giải mã `$value_ref` khi duyệt bên trong `proposal` hoặc `runtime_obligations`.
  3. Mọi payload từ user/model dù chứa key `$value_ref` hoặc các key trùng tên (`quote`, `note`) đều được giữ nguyên vẹn dưới dạng dict thô, ngăn chặn triệt để nguy cơ injection/spoofing.
- **Kiểm chứng:** `test_raw_nested_quote_key_never_authorizes_value_ref_decode[proposal]` và `[runtime_obligations]` (PASSED).

### Finding 2 [P1]: Bảo toàn trạng thái invalid của canonical contract dict
- **Nguyên nhân cũ:** `TurnContract.from_dict` là parser dành cho model proposals nên tự động chạy lại validation và tính lại cờ, làm xóa mất `is_valid=False` và `validation_errors` (ví dụ `runtime_binding_error`) của bản export chuẩn tắc.
- **Sửa chữa:**
  1. Khi nhận contract dạng dict đã chuẩn tắc, compiler sao chép và bảo toàn nguyên trạng các trường `is_valid`, `validation_errors`, và `intent_coverage`.
  2. Đồng bộ hóa logic đánh giá: hợp đồng có `is_valid=False` hoặc `validation_errors` không rỗng được xác định là không đủ điều kiện cho provisional matching (`contract_not_eligible_for_provisional_match`).
  3. Mọi outcome của hợp đồng không hợp lệ bắt buộc phải giữ nguyên trạng thái `unresolved` trong `progress`, kể cả khi có receipt khớp trong journal.
- **Kiểm chứng:** `test_canonical_invalid_dict_cannot_be_reparsed_into_met_progress` (PASSED).

### Finding 3 [P1]: Bảo toàn kiểu JSON, unknown operation results và so sánh chính xác tuyệt đối
- **Nguyên nhân cũ:**
  1. Kết quả scalar/list không có artifact được bọc trong `{"result": val}` nhưng pointer trỏ vào root `""`, khiến khi giải mã bị dư một lớp object `{"result": ...}`.
  2. Operation result lạ chứa `note.id`/`revision` bị thay thế nhầm bằng notebook body dù không phải do `record_work_note` tạo ra, làm mất các trường bổ sung như `plugin_field`.
  3. Ép kiểu `str()` và `.strip()` làm sai lệch kiểu số `"42"` thành `42` và xóa khoảng trắng `" source text "`.
- **Sửa chữa:**
  1. Khi bọc kết quả scalar/list vào envelope `{"result": res}`, receipt pointer được gán chính xác là `"/result"`. Khi `expand_value_refs` giải mã, nó khôi phục chính xác 100% giá trị và kiểu JSON gốc (`int`, `list`, `bool`, `str`).
  2. Chỉ thay thế operation result của plugin khi nó thuộc về operation tin cậy đã đăng ký (`record_work_note`). Các plugin output khác giữ nguyên raw.
  3. So sánh chuỗi trích dẫn quote chỉ áp dụng khi cả hai đối tượng đều là chuỗi và khớp chính xác tuyệt đối từng ký tự và khoảng trắng (`isinstance(val, str) and isinstance(raw_quote, str) and val == raw_quote`). Không ép kiểu chuỗi, không strip khoảng trắng.
- **Kiểm chứng:**
  - `test_no_artifact_operation_result_roundtrip_preserves_json_type` (4 ca: int, list, bool, str) (PASSED).
  - `test_unknown_result_note_shaped_payload_is_preserved_verbatim` (PASSED).
  - `test_quote_projection_preserves_exact_string_and_type` (2 ca: số vs chuỗi, khoảng trắng) (PASSED).

### Finding 4 [P1]: Đóng kín kiểm tra ngữ nghĩa trong `validate_context_snapshot`
- **Nguyên nhân cũ:** `validate_context_snapshot` chỉ kiểm tra pointer 1 cấp mà bỏ sót closure của các typed refs, chấp nhận entity trùng lặp định danh nhưng khác body, và không phát hiện chu trình dereference.
- **Sửa chữa:**
  1. **Đóng kín miền tham chiếu (Typed Ref Closure):** Kiểm tra toàn bộ tham chiếu có kiểu trong `indexes` (`selected_results`, `current_results`, `previous_sources`, `active_notes`, `historical_notes`), `boundary.pins`, và `continuity.confirmed_constraint_refs`. Mọi ref phải trỏ tới một entity tồn tại trong `entities` hoặc được khai báo tường minh trong `unavailable_refs`.
  2. **Chống xung đột định danh (Entity Identity Uniqueness):** Phát hiện và báo lỗi ngay lập tức nếu xuất hiện từ 2 entity trở lên có cùng khóa định danh chuẩn tắc `(kind, id/receipt_id/action_id, revision/turn_id)`.
  3. **Phát hiện chu trình (Dereference Cycle Detection):** Triển khai thuật toán kiểm tra chu trình đồ thị có hướng (DFS cycle detection) trong `validate_context_snapshot`. Đồng thời trong `expand_value_refs`, bổ sung tập `seen_refs` để chặn đứng đệ quy vô hạn và báo lỗi `ValueError` tường minh nếu gặp chu trình tham chiếu.
- **Kiểm chứng:**
  - `test_missing_typed_index_ref_requires_explicit_unavailable` (PASSED).
  - `test_duplicate_entity_identity_with_conflicting_bodies_is_rejected` (PASSED).
  - `test_cycle_in_projection_quote_refs_is_rejected_before_expansion` (PASSED).

### Finding 5 [P2]: Lọc scope cho verification receipts / current proofs
- **Nguyên nhân cũ:** Verification receipt ngoại lai hoặc từ execution/generation cũ trong journal vẫn bị gom vào `observed_state.proof_refs`.
- **Sửa chữa:** Tại `_build_journal_entities_and_receipts`, tiến hành kiểm tra scope nghiêm ngặt: chỉ những receipt kiểu `"verification"` có `conversation_id`, `execution_id`, và `generation` trùng khớp hoàn toàn với boundary hiện hành mới được đưa vào danh sách `proof_refs`. Các proof ngoại lai hoặc cũ chỉ thuộc về lịch sử và bị loại bỏ khỏi current proof view. Tuyệt đối không tự ý điền đè boundary hiện tại vào receipt để lách kiểm tra.
- **Kiểm chứng:** `test_foreign_execution_proof_is_not_current_proof` (PASSED).

### Finding 6 [P2]: Bảo toàn đầy đủ metadata của Artifact
- **Nguyên nhân cũ:** Thân entity của Artifact chỉ trích xuất một số trường được chọn, làm mất các trường metadata chuẩn tắc như `status` (`waiting_input`), `provenance`, và `created_at` trong khi vẫn gắn nhãn `projection_status = "lossless"`.
- **Sửa chữa:** Sử dụng trực tiếp `art.to_dict()` để giữ nguyên vẹn toàn bộ các trường metadata chuẩn tắc trong `body` của entity, bao gồm `status`, `provenance`, `created_at`, và `payload`. Các thông tin phân loại dẫn xuất (`authority`, `owner`) được quản lý riêng ở cấp entity, không làm ghi đè hay mất thông tin gốc.
- **Kiểm chứng:** `test_artifact_projection_retains_status_provenance_and_timestamp` (PASSED).

---

## 3. Tổng hợp kết quả kiểm thử (Verification Matrix)

Toàn bộ các bộ test được thực thi tuần tự bằng Python 3.12 sạch (`PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`):

| Bộ kiểm thử | File / Lệnh | Số tests | Thời gian | Trạng thái |
| :--- | :--- | :---: | :---: | :---: |
| **B1 Unit & Regressions** | `tests/test_rat_context_snapshot.py` | 29 | 2.74s | **100% PASSED** |
| **Codex Review Probes** | `audit/rat_context_B1_codex_review_20261014_123157/review_probes.py` | 15 | 1.97s | **100% PASSED** |
| **Context Audit Tests** | `tests/test_rat_context_audit.py` | 6 | 0.77s | **100% PASSED** |
| **ArtifactStore Lifecycle** | `tests/test_artifact_store_lifecycle.py` | 19 | 0.63s | **100% PASSED** |
| **Core Reconciliation** | Core test suites từ `audit/rat_core_reconciliation_fix_20261013/test_run.json` | 292 | 7.91s | **100% PASSED** |
| **TỔNG CỘNG** | **Toàn bộ 5 bộ kiểm thử** | **361** | **14.02s** | **100% PASSED** |

---

## 4. Cam kết ranh giới và chuẩn bị cho B2

1. **Ranh giới B1 được giữ nguyên tuyệt đối:**
   - Chỉ chỉnh sửa `rat/engine/context_snapshot.py` và bổ sung regressions trong `tests/test_rat_context_snapshot.py`.
   - Giữ nguyên vẹn các bản vá `ArtifactStore` high-water và presentation dispatcher.
   - Không có bất kỳ dòng code nào can thiệp vào `AssistantRuntime._call_model` hay vòng lặp thực thi `run()`. Việc nối dây (wiring) runtime hoàn toàn được bảo lưu cho bước B2.
2. **Không có tuyên bố sai về hiệu năng:**
   - 0 model calls mới, 0 chi phí suy luận phát sinh.
   - Không tuyên bố bất kỳ sự cải thiện nào về latency, token count, hay prompt caching; toàn bộ cam kết là tính nhất quán toán học và phần mềm của context projection compiler.
3. **Kính chuyển Codex xem xét và nghiệm thu B1 Repair** để tiến hành bước B2 theo kế hoạch.
