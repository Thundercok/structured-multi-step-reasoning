# Anti sửa tiếp core — Codex request changes

Vai trò đã chốt: Codex thiết kế/review, Anti làm code. Phase core đã được user
duyệt; tiếp tục sửa lỗi trong scope đó. Chưa sang UI presentation/live ablation.

Đọc review.md, contract_probes.py, contract_probes.txt và validation.json trong
folder này, cùng ADR-003. Không chỉnh/xóa probes hoặc scope để biến failure thành
PASS; nếu chọn tên/representation public khác, giải thích mapping contract rồi
bổ sung assertions tương đương.

## Thứ tự sửa

1. Native contract encoding thật ở planner ON/OFF. Planning schema hiện không
   cho outcomes nhưng runtime cố đọc sau validate. _call_model chưa decode
   outcomes/contract. Test qua fake native client; không chỉ run(contract=...).
2. Strict validation + runtime-owned immutable frozen snapshot. Empty/unknown
   schema/kind/invalid dependencies giữ unchecked/invalid, không satisfied.
   Journal deep snapshot khi commit; không chia sẻ dict/list mutable.
3. Call-specific refs thống nhất. Sửa id/artifact_id mismatch và cumulative
   changed_artifacts refs. Positive calculate→save đúng phải PASS trước khi
   wrong-source negative có giá trị.
4. Match toàn bộ nghĩa vụ: input/target/source/revision bindings, dependencies
   không phụ thuộc thứ tự declaration, distinct producer receipts và proof lineage
   đúng parent/evidence. Generic effects không được bỏ required proof/refs.
   Effect đã đủ nhưng response bắt buộc chưa có vẫn chưa satisfied.
5. Terminal note revision/proposal/source/field/event kind và trạng thái thực.
   Không dùng confirmed revision1 để xác nhận latest revision2 proposed.
6. Lifecycle cancel/failed/needs_input giữ matched committed effects và unmet
   phần còn thiếu; dùng issuer commit/status thật. Native fail/cancel/pending
   phải chuyển reconciliation vào history như success. Chỉ wiring trong phase
   core; layout/copy/Chuột duyệt sau.
7. Expose/export frozen contract+journal snapshots. Traces phải có outcomes,
   receipts, matched/unmet IDs, parent/evidence refs và artifacts/note versions.

Giữ reconciler chung: operation-specific logic thuộc adapters đăng ký, không
thêm central switch mới theo feature. Không keyword rescue hoặc thêm một call
classifier mặc định để che thiếu contract. Intent model_proposed không là intent
verified; unknown prose quality vẫn giữ scope thực.

## Validation

Chạy bộ224 theo regression_tests.txt, contract probes, và regression mới cho
native OFF, đúng/sai source cùng dữ liệu, nhiều producer, validation/immutability,
proof từ call khác, terminal note, pending/fail/cancel history và omitted-outcome.
Probe dùng model/client fixtures, không model thật. Nếu interface khác, giữ
nguyên behavioral assertion và ghi rõ mapping; đừng xfail/skip lỗi cần sửa.

Bàn giao ở folder mới: diff so với snapshot reviewed_source ở đây để tránh trộn
thay đổi mốc cũ; source hashes start/end; commands/logs; raw transcripts giữ
contract+journal và failures; giới hạn còn lại. Không chạy exporter mặc định
đè audit/rat_core_reconciliation_20261013.

Sửa diễn giải: pre-cancel không phải HTTP in-flight; 197 là selected subset;
freeze flag không là immutable object; hash không phải cryptographic signature;
tests qua không chứng minh model quality hoặc workflow100%. Metadata test
calculation hiện lệch hash phải được ghi đúng trong snapshot mới.

Không chạy live/native khi chưa có phase/budget thích hợp; không đổi default,
research/Stage0/DocAI, không push/pull/reset/force trừ user yêu cầu cùng message.
