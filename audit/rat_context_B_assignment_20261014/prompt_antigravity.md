# Prompt giao Antigravity — B1 trước

User phân công: Antigravity lo triển khai, chạy checks và lưu artifacts; Codex
lo kiến trúc, semantic decisions và review. Thực hiện **B1: headless context
projection compiler**, theo thiết kế đã chuẩn bị và phần quyết định bổ sung.
Không cần lặp lại audit A hoặc xin user chốt các bước code nhỏ trong scope này.

Đọc theo thứ tự:

1. `AGENTS.md` ở root canonical `~/github/nesy-docai`.
2. `audit/rat_context_B_assignment_20261014/decisions.md` — ưu tiên khi khác draft.
3. `docs/adr-004-rat-context-snapshot.md`.
4. `audit/rat_context_B_assignment_20261014/snapshot.schema.json` và examples.
5. `audit/rat_context_snapshot_design_20261014/README.md` + provenance.
6. `audit/rat_context_handoff_review_20261014/review.md` để bỏ claims sai của A.

Canonical alias đang trỏ vào checkout này. Xác nhận realpath trước làm việc;
không làm một bản thứ hai ở legacy worktree. Giữ mọi uncommitted work khác.

**Deliverable B1:**

- Thêm `rat/engine/context_snapshot.py`: pure compiler nhận canonical copies,
  typed entity refs, ref/pointer/namespace validation và projection/render data.
  Không đọc personal index, không Qt, không model call, không state store mới.
- Proposal một representation; contract export giữ nguyên declarations/errors/
  frozen flag; actual receipts/proofs riêng với proposal. Dùng input assessment
  từ existing reconciler, không viết một matcher mới trong compiler.
- Progress dùng shape bổ sung: **global matched receipt evidence**, không tự
  đoán outcome→receipt. Empty/invalid/unchecked không tự thành met; response
  pending trước final. Không dùng terminal summary làm runtime lifecycle.
- Full note text từng cần thiết revision inline, cùng status/source/authority/
  owner/replacement links. Quote cùng exact source/revision/field có thể dùng
  generated ref. Không ID-only old note khi chưa có notebook resolver.
- `$value_ref` chỉ decode typed projection slots. Unknown result giữ raw;
  user JSON có key giống wrapper không là runtime ref. Native expected args
  và operation input values giữ nguyên, không pointer sang mutable output.
- Coherence metadata giữ separate artifact epoch, notebook epoch và selection
  flag. Pure compiler không tự đi mutate store; B2 source copier sẽ kiểm copies.
- Thêm meaningful tests cho lossless reconstruction, distinct authority,
  arbitrary operation artifact/no-artifact result, invalid/empty contract,
  stale generation, missing/cyclic refs, raw fake wrapper, note revisions và
  selection_set false/true với [] khác nhau. Tests phải fail nếu bug quay lại.
- **Chưa sửa runtime wiring hoặc UI ở B1.** Không thay freeze/controller/budgets/
  registry ordering/default live model/planner. DocAI/Stage0/NCKH giữ như AGENTS.

**Validation và handoff:**

- Chạy focused B1 tests rồi exact existing regression command từ
  `audit/rat_core_reconciliation_fix_20261013/test_run.json`; giữ 33 old probes,
  227 selected regressions và 32 boundary cases. Ghi raw log/exit/source hashes.
  `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`; không cài dependency mới.
- Một fresh folder `audit/rat_context_B1_<timestamp>/`, không overwrite A/design/
  review packets hoặc xóa audit sau failure. Lưu manifest, source diff, tests,
  example snapshots, unmodeled/fallback cases và `handoff_codex.md`.
- Handoff ghi files changed, exact commands/results, known limits, remaining
  B2 wiring items và discrepancies. Passing software tests không là AI quality.
  B1 chưa có real before/after runtime measurement; không claim latency/cache/
  token savings. 0 live inference; không git push/pull/reset/force.
- Khi B1 concrete, trả packet để Codex review trước B2. Nếu API hiện có thiếu
  canonical data, giữ explicit unresolved/raw fallback hoặc đưa reproducer cho
  Codex; đừng tự sửa policies/copy authored example receipts thành evidence.

B2 sau review sẽ wire planner/actor/repair/finish theo decisions.md, capture
fresh mock requests cùng source/decision sequence và kiểm full lifecycle.
