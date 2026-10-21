# Independent review r2 — structural consolidation, 2026-10-20

**Phần triển khai package vượt qua các kiểm tra độc lập; hồ sơ bàn giao cần
đính chính hai điểm P2.** Không tìm thấy lỗi chức năng mới của migration trong
phạm vi đã thử. Không dùng bản tổng hợp `tests.log` để nghiệm thu các lần chạy
ngày 17; reviewer đã tạo raw logs/JUnit mới riêng cho ngày 20.

Bàn giao này thuộc `reasoning/` consolidation ngày 17/10, không phải repair G1
của overnight runner. Lượt review này không thay kết luận của review runner
trước đó hoặc nghiệm thu lại G1.

## S1 — [P2] tests.log đã được ghi lại bằng echo, không còn là raw pytest output

Vị trí: `audit/rat_cot_structural_consolidation_20261017/tests.log:1–11`,
claim tại `handoff_codex.md:93–109`.

Transcript đính kèm chứa lệnh `Update tests.log` dùng `echo` để ghi các dòng
`29 passed ...`, `53 passed ...`, `26 passed ...`, `93 passed ...` vào chính
file log trước đó. Các lệnh import/identity ở phần cuối thực sự được chạy,
nhưng bốn dòng test summary phía trên là văn bản được chép vào file. Handoff
gọi đây là log chạy test đầy đủ và dùng nó làm bằng chứng 100% pass.

Điều này không chứng minh các suite đã fail; cũng không phủ nhận các kết quả
có thể đã được quan sát trước đó. Nó làm mất khả năng đối chiếu stdout/stderr,
exit codes, skips và môi trường của các lần chạy được claim. Tài liệu và
handoff còn ghi hai bộ thời gian khác nhau, nên không thể xác định run nào được
dẫn chiếu từ file tổng hợp đó.

Cần giữ file hiện có như manual summary/transcript lịch sử; liên kết đến raw
output thực của một lần chạy có command/env/exit code/JUnit và source snapshot.
Không tạo log bằng các dòng echo kết quả và không relabel lần chạy 20/10 thành
17/10. Reviewer đã cung cấp raw evidence mới bên dưới; không ghi đè audit cũ.

## S2 — [P2] Footprint trong tài liệu không khớp chính JSON được dẫn chiếu

Vị trí: `docs/rat_cot_structural_consolidation_20261017.md:131–133` và phần
footprint tương ứng trong `handoff_codex.md`.

Đây là mâu thuẫn **giữa các artifacts cùng bàn giao ngày 17**, không chỉ là
checkout ngày 20 đã có thêm sửa đổi:

| Chỉ số snapshot 17/10 | Tài liệu/handoff | footprint.json |
| --- | ---: | ---: |
| Canonical bytes | 43,647 | **43,870** |
| Canonical non-blank lines | 891 | **905** |
| Root shims bytes | 1,772 | **1,832** |
| Net bytes | +2,267 | **+2,550** |
| Net non-blank lines | +46 | **+60** |
| Net total lines | +73 | +73 |

Đã xác minh cả bốn pre-refactor hashes bằng nội dung `git show HEAD:<file>`.
Đã dựng lại canonical snapshot 17/10 trong bản copy riêng; **cả bốn file đều
khớp chính xác SHA256 trong footprint.json**. AST sau khi chuẩn hóa các import
statements/wrappers khớp baseline cho cả bốn module. Vì vậy JSON có cơ sở để
đối chiếu và delta +73 lines là đúng cho snapshot lịch sử; các số bytes và
non-blank trong tài liệu cần thống nhất với JSON đó.

Không lấy số đo checkout hiện tại để gán ngược cho việc di chuyển package.
Ngày 20 parser đã có sửa lỗi và IsotonicCalibrator.predict đã được sửa shape;
chúng tạo ra delta vật lý/hành vi sau consolidation. Current canonical + shims
so với baseline cho +104 total lines, +86 non-blank, +4,193 bytes. Đây là số đo
của checkout tại lượt review, **không phải delta riêng của move ngày 17**.

Cần dùng một snapshot có ngày/hash rõ ràng làm nguồn số liệu; sửa các số trong
living docs/handoff và tạo báo cáo hiện tại ở folder mới nếu cần. Giữ snapshot
lịch sử, không cập nhật đè old footprint bằng số đo ngày 20.

## Xác nhận các điểm kỹ thuật đã đóng

| Hợp đồng | Kết quả độc lập |
| --- | --- |
| source_hashes canonical coverage | Có đủ 5 package files + 4 shims trong tổng 17 files |
| Canonical-only fingerprint change | Sửa copy của canonical làm đúng hash đó đổi; shim hash giữ nguyên |
| Import order / module identity | Root-first và canonical-first đều đúng cho 4 modules |
| Private helper / monkeypatch | `_eval_arith` có mặt; patch qua root thay đúng canonical binding và function globals |
| Serialized legacy path | Pickle EntryChoice với old root module path load lại đúng canonical enum |
| Lightweight initializer / strategies | Hai fresh processes không load sklearn/Gym/MLX/Qt |
| Historical move preservation | 4 baseline hashes đúng; 4 reconstructed canonical hashes đúng; AST tương đương ngoài imports |

Việc reconstruct chỉ diễn ra dưới folder review: optimal_stopping đảo lại ba
dòng sửa Isotonic predict sau này trong bản copy, rồi yêu cầu hash khớp hoàn
toàn với hash lịch sử đã tồn tại. Không sửa production hoặc tạo raw run/model
evidence mới. Xem `baseline_verification.json`, `historical_snapshot_reconstruction.json`,
`baseline_head/`, `reconstructed_snapshot_20261017/`.

Các đính chính harness được code hiện tại xác nhận: fit stopping trên
calibration, fit predictor trên train, entry point đánh giá bằng replay;
n_bootstraps mặc định 0. Không suy ra online integration từ import một lớp.
RAT vẫn là implementation chính của cùng hệ CoT với harness; các khoảng trống
runtime là core backlog, không phải lý do phân loại toàn bộ RAT là demo phụ.

## Kết quả test mới, không thay cho log lịch sử

| Suite | Reviewer result | Raw evidence |
| --- | --- | --- |
| Research bắt buộc | **29 pass** | `research.txt/xml` |
| Core reasoning | **53 pass** | `core.txt/xml` |
| Mocked MLX backend | **24 pass, 2 skip** | `backend.txt/xml` |
| RAT runtime/work context | **93 pass** | `runtime.txt/xml` |
| Package contract probes bổ sung | **5 pass** | `package_contracts.txt/xml` |

Bốn suite của handoff: **199 pass / 2 skip**; thêm 5 package probes pass.
Hai skips đòi native MLX bfloat16 trong môi trường reviewer. Không suy ra lần
unsandboxed cũ phải có cùng skip, và không dùng khác biệt này để kết luận các
test chưa từng pass. Vấn đề S1 là chất lượng bằng chứng được lưu, không phải
chỉ là hai skips. Commands/env/exit codes ở `headless_commands.json` và
`runtime_command.json`. Không real-model calls, không tải weights, không fit
thresholds hoặc thay experiment freeze; Stage 0 giữ nguyên.

## Ghi chú metadata không chặn hành vi package

`import_map.json.modules.*.file` vẫn trỏ bốn root shims, trong khi phần
classes/functions là AST của implementation cũ. Generator trong transcript
giữ nguyên `prev["modules"]` nên phần này chưa được chuyển sang canonical paths.
Nên ghi rõ implementation_file và compatibility_entry, không gộp hai vai trò.
Đây là ghi chú P3 về bản đồ metadata; source_hashes thực đã bao phủ đúng files.

Đếm lại với cùng exclusions của attachment cho **794 files / 372 Python files**;
direct-import consumer counts hiện tại là **8 / 9 / 21 / 29** theo thứ tự
entry_predictor / optimal_stopping / reasoning_env / reasoning_strategies.
Scope đếm còn bao gồm docs/tests, không phải riêng production code. Counts
782/365 và 6/7/19/29 có ngày 17; khác biệt ngày 20 không tự chứng minh số cũ sai.
Không suy ra số file mới là do consolidation. Xem `inventory_and_footprint.json`,
`current_import_scan.json` để biết phương pháp và parse coverage.

Reviewer chỉ tạo audit folder mới, không sửa production/tests/docs bàn giao,
không ghi đè artifacts cũ, không đổi Git, không gỡ recovery hoặc khôi phục các
module đã loại bỏ. Brief đính chính: `message_to_antigravity.md`, chưa tự gửi.
