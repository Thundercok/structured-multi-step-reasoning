# Anti sửa tiếp core Round 2 — còn gates trong cùng contract

Codex xác nhận 19 probes cũ +224 regressions qua. Còn 13 failures/14 cases mới
trong remaining_contract_probes.py; đọc review.md và logs. Phase core đã được user
duyệt, Anti làm code, Codex review; chưa sang UI presentation/live model.

## Ưu tiên triển khai cụ thể

1. Resolver proof nhận verification ENVELOPE, dùng parent_receipt_ids và evidence/
   source revision của receipt đích. Hiện parent ở envelope nhưng matcher tìm ở
   payload. Positive calculate18*7 với calculation_execution PASS phải satisfied;
   proof từ call khác/thiếu/UNKNOWN không được thỏa proof bắt buộc.
2. Note matcher kiểm required_proof_scope/required_authority ở terminal version.
   Note confirmed copy không chứng minh mọi named proof. Kiểm cả terminal source/
   field/revision/text/status, không lấy source từ event126 để chấm note162 hiện tại.
3. Input binding có kiểu thay substring description. Đề xuất OutcomeSpec.expected_args
   theo schema operation; calculator adapter dùng parser/canonical expression.
   Description chỉ là text, không parsed intent constraint. No regex keyword rescue.
4. Native ON/OFF protocol/decoder có schema, raw audit và answer tách metadata.
   Envelope JSON không được làm user-facing answer. outcomes string/list sai type,
   refs sai, frozen/is_valid/identity flags từ model phải thành invalid/failed có log,
   không uncaught exceptions. Runtime tự bind trusted IDs và tự freeze.
5. Validate DAG/cycle/producers; topological matching thực. Cùng actions/receipts
   phải có verdict giống nhau khi đổi order declarations. Freeze recursive nested
   refs/deps, không cho unfreeze và không chia sẻ object mutable của proposal.
6. completion_status lấy reconciliation duy nhất. Giữ task_state model report riêng.
   Legacy test_rat_task_memory.py:31 đang chờ model_reported_in_progress; migrate
   assertion theo ADR, vẫn kiểm raw task_state/provenance và unchecked coverage,
   ghi rõ lý do thay assertion. Không skip/xfail hoặc cắt các ca lỗi mới.

Đưa input/proof matchers vào registered operation adapters, giữ shared reconciler
chung. Không mở rộng framework/DSL hoặc thêm feature khác để hoàn thành mốc này.
Nếu cần thay public field names/encoding, giữ cùng behavioral checks và ghi mapping.

## Validation/bàn giao

Chạy remaining_contract_probes.py (14 cases), 19 probes vòng trước và selected
224-suite, cùng positive/negative controls cho proof/terminal source/DAG/native
encoding. Phần migrate legacy completion assertion phải có diff giải thích.
Đây là mocks/fixtures, không model-quality evidence; chưa có budget live.

Folder audit mới phải chứa diff so với reviewed_source của vòng này, source hashes
ngay trước/sau tests, commands thực, failure logs, contract/journal/receipts/proof
envelopes và terminal note versions. Sửa exporter để từ chối folder có sẵn trước
fixtures hoặc writes; không overwrite bất kỳ audit cũ nào. Exporter hiện lệch hash
manifest Round2 phải được ghi đúng trong snapshot mới, không sửa raw report cũ.

Giữ default model/planner, NCKH/Stage0/DocAI, layout/copy/Chuột và tất cả audit cũ.
Không chạy live/native, không push/pull/reset/force nếu chưa có authorization thích
hợp. Báo rõ các gates còn unchecked và khác biệt protocol; Codex review lại core
trước phase UI, không chấm hoàn tất100% từ tests xanh.
