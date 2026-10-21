# Follow-up sau independent review r6 — 2026-10-20

Đọc `audit/rat_overnight_sweep_codex_review_r6_20261020/review.md` và raw evidence.
Review độc lập xác nhận **319/319 pass**, gồm 10 probe r5 và 29 NCKH bắt buộc.
E1 đóng trên các ca kiểm tra. E2/E3 còn hai phần trong runner, chưa cần sửa
parser/UI thêm:

1. **F1 / E2 — đường dẫn vẫn là heuristic provenance.**
   `model_path` chứa tên checkpoint hoặc `document_path` chứa random directory
   của phiên real cũ không chứng minh backend thực thi. Fixture tổng hợp từ
   record fake chỉ đổi input path bị nhận real; replay exhausted budget xác
   nhận summary sai. Giữ unknown, hoặc nhận diện ledger legacy đã review bằng
   artifact identity/hash mapping/sidecar. Không sửa raw ledger để thêm tags.
   Cần giữ classifier cho explicit backend đúng và budget vẫn tính unknown.
2. **F2 / E3 — real mode vẫn dùng historical count khi current run rỗng.**
   Dòng 431 còn fallback len(history); dòng 437 còn fallback warm records phiên
   trước. Reporting block với 0 current + 12 historical real records vẫn báo
   executed=12, verified_12 và chọn 12 records cho warm. Dùng current dispatch
   cho executed, guard halt status và warm=null cho cả hai backend. Historical
   totals/verification để riêng; giữ 12-call baseline đã review nguyên vẹn.

Hai finding được kiểm offline, không có real-model calls mới. `reporting_block_cases.json`
là AST fixture của code báo cáo thực, không phải một phiên chạy real backend.
Counterexample path là fixture tổng hợp, không phải ledger lịch sử bị sửa.

Sửa source trên main, giữ unrelated work và recovery. Không commit/branch/
push/pull/reset, không thêm ngân sách, không gọi model thật. Không đổi typed
research scoring, gold datasets, evaluation freeze hoặc Stage 0. Không dùng
software test counts thay quality/native evidence.

Sau lúc bộ 319 hoàn tất có thay đổi `rat/ui/omnibar.py` từ bên ngoài. Reviewer
đã lưu diff và giữ nguyên; các kết quả ở đây ghim snapshot trước thay đổi UI
đó. Hai file repair vẫn khớp. Đọc trạng thái hiện tại trước khi sửa, giữ các
thay đổi mới từ chat khác, không restore source snapshot đè lên chúng.

Tạo folder repair mới, giữ toàn bộ review cũ immutable. Fresh fake cap 1 và
replays dùng bản copy ledger, như `session_commands.json`; guard replays không
được thêm request. Với same-document fixture, dùng đúng input đã lưu; đừng
chạy runner vào review folder. Kiểm probe qua:

```bash
QT_QPA_PLATFORM=offscreen \
RAT_REVIEW_R6_OUTPUT_DIR=/absolute/path/to/new_repair_output \
.venv/bin/python -m pytest \
  audit/rat_overnight_sweep_codex_review_r6_20261020/test_legacy_identity_and_real_history.py -q
```

Output root cần có `same_document_legacy_fake/native_performance.json` và
`same_document_legacy_fake.txt`. Nếu refactor helper/provenance mapping khiến
AST isolation không còn phù hợp, điều chỉnh cơ chế gọi hoặc thay bằng fake-only
integration tương đương; giữ assertions và fixture provenance, không nới test.

Giữ bộ 319 cũ và checks parser/backend/scoring; ghi rõ skip native bfloat16 nếu
có. Bộ NCKH 29 là subset của 319. Tránh ghi đè ảnh/geometry vào review r4 khi
chạy lại hosted viewport test; dùng output redirect như wrapper r6.

Handoff cần source before/after hashes + diff, commands/env, logs/JUnit, ledger
byte checks, counters/current-history scope và native cases chưa đo. Không
mở rộng phạm vi thành thêm UI hoặc một campaign model mới để sửa hai lỗi này.
