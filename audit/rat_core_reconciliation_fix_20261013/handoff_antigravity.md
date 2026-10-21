# Core Round 3 findings đã được Codex sửa

Người dùng yêu cầu Codex xử lý trực tiếp. Không tiếp tục triển khai lại brief
sửa R1–R6 trong audit review trước: source mới nằm ở `completion.py` và
`assistant_runtime.py`, regression mới ở `tests/test_rat_completion_boundaries.py`.
Xem [report](report.md), [patch](changes.patch) và [validation](validation.json).

Kết quả: **292 tests passed** (33 old probes + 227 selected regressions + 32
boundary cases); 11 mock transcript fixtures qua. Audit lịch sử được giữ nguyên.
Không model calls mới, UI changes, default changes, git push/pull/reset/force.

Sửa đã bao gồm validation/JSON equality/export/source binding/proof gate dùng
chung, typed input fidelity cho calculator/notes, và native planner/decision
decoder thống nhất. Proof native final gắn hash candidate, same generation;
unsupported refs giữ unmet. Không thêm bộ điều phối riêng cho từng feature.

Gói A/B/C/D là bước sau, chưa được thực hiện ở lượt sửa này. A có thể audit
context bằng mock trên source mới đã ghi hash. Giữ nguyên yêu cầu một chat,
turn-owned notes và personality Chuột. B chưa được giả định rằng
`inspect_artifact` có thể đọc WorkNotebook note revisions; C cần audit registry
order trước khi thay; D vẫn là design/budget phase riêng. Live model/UI chưa
được nghiệm thu lại và không có evidence speed-up mới.
