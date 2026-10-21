# Audit A đã xong — đầu vào cho design B/C

Xem [report](report.md), [analysis](analysis.json) và [captures](captures.json).
0 live inference; 11 core fixtures + main C01 bảy lượt, tất cả do script quyết
định. 12 cases/20 runtime turns/41 mock port calls; 6 audit tests qua. Chưa
nghiệm thu model/native UI hay toàn bộ conversation pack.

Core hiện vẫn là bản Codex đã sửa với 292 tests trước đó. Lượt này chỉ thêm
`scripts/audit_rat_context.py`, `tests/test_rat_context_audit.py` và audit files;
không đổi runtime/prompt/defaults hay UI.

Ưu tiên design B theo thứ tự:

1. **Explicit runtime obligations cho actor.** Planner C01 khai outcomes nhưng
   actor messages không có outcome IDs/contract block. Actor cần nhìn frozen
   obligations, typed source/target/dependencies/proof scope và effects đã
   commit, riêng với model task proposal. Reconciliation hiện ở boundary cuối,
   chưa có missing-outcome feedback loop; đừng hứa đã có auto-repair phần này.
2. **Một task proposal representation.** Task state trùng hai places trong
   11/11 C01 actor calls; planning event giữ assessment/phase và reference tới
   proposal body. Không hạ trust của receipts hoặc nâng trust của proposal.
3. **Một body mỗi entity/revision.** Source quote339 chars lặp tới12 locations
   ở request cuối, chủ yếu note, source_ref và note_event.snapshot bị đưa lại
   vào previous_sources. Dùng typed links/metadata chung; full event payload
   vẫn ở journal/notebook, không biến event cũ thành nguồn truth mới.
4. **Giữ continuity và authority.** Query, no-code preference, array/example,
   read boundary, proposed/confirmed status, current/historical revisions,
   cancellation và replacement links phải còn đủ. Strings giống nhau chỉ là
   dấu hiệu cần xem xét; không xóa theo wording.

Trình before/after snapshot JSON và contract fixtures trước khi triển khai B.
Không rút note history thành refs-only: `inspect_artifact` chưa đọc WorkNotebook
versions. Chưa cần code resolver mới trong audit A.

C: captures cho thấy first system/tools hashes ổn định, registry order không
churn trong tập này. Kiểm thêm repair/finish-only khi thiết kế; chưa có cache
savings hay latency measurement. Không tự sort/prune tools để tạo claim.

D: one-call proposal + action là spec riêng sau B/C. Giữ model quyết định,
freeze trước side effect, faults/cancel/resume cùng core. Không keyword router,
feature apps, notes drawer, model/planner default change hoặc DocAI integration.
Live budget và UI review vẫn là phases riêng theo yêu cầu người dùng.

Brief này chưa được gửi bằng tool tới Anti.
