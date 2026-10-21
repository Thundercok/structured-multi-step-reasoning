# Codex: quyết định ngữ nghĩa cho B

Ngày 2026-10-14, Asia/Saigon. Người dùng yêu cầu giao chores cho Antigravity,
Codex giữ phần thiết kế và review. Phần triển khai được chia B1 compiler thuần,
rồi B2 wiring sau khi Codex kiểm tra B1. Đây là tiến độ review kỹ thuật; không
lặp lại câu hỏi xin quyền làm các việc đã giao.

Canonical alias `~/github/nesy-docai` hiện resolve đúng checkout đang dùng:
`/Users/thundercock2/Documents/Github/multi-step-structured-reasoning`.
Không tạo thêm một bản RAT ở checkout khác. DocAI và NCKH vẫn theo AGENTS.

## 1. Context projection không tạo thêm “sự thật”

LLM hiểu yêu cầu, quyết định relevance và chọn hành động. Compiler làm việc
cơ học: lấy canonical copies, giữ typed identity/provenance, render một view.
Verifier/reconciler kiểm phần đã có quy tắc và receipts. Không để projection
đoán intent, relevance, correctness hay tự tạo outcome để lấp chỗ thiếu.

B làm cho model có đủ context để làm tiếp công việc trong cùng chat. Nó chưa
chứng minh model đã suy luận tốt hơn hoặc có learned policy. Những quyết định
cần học phải được đo bằng model thật trong phase có budget riêng. Giữ tách biệt
research và RAT, không dựng một feature DSA hay controller riêng cho từng app.

## 2. Sửa gap trong draft progress của ADR-004

`reconcile_turn` hiện trả `matched_receipts` cho **toàn lượt** và
`unmet_outcomes` có outcome IDs. Nó không trả outcome→receipt mapping.
Draft example trước ghi dispatcher và notebook receipt cùng một outcome là
authored illustration; không phải mapping được core export.

**Quyết định:** giữ evidence receipt IDs ở cấp report của lượt. Không đoán
mapping bằng index/operation name/description, không chạy từng outcome riêng
vì sẽ mất dependency order và receipt-consumption semantics.

Để hiển thị trạng thái từng outcome trước model call:

1. Chạy cùng reconciler trên copied contract/journal/notebook/store view,
   `lifecycle=in_progress`, `final_answer=""`, không dùng rejected candidate
   làm accepted final answer. Không thay current controller/freeze/matchers.
2. Chỉ với contract valid, nonempty, coverage không invalid/unchecked, dùng
   `unmet_outcomes` để biết check chưa khớp. Outcome effect không nằm trong
   unmet set có thể ghi `met`, **provisional tại snapshot boundary**.
3. Response giữ `pending_response`; lưu unmet reason/proof checks riêng.
   Effect chưa khớp giữ `pending`, reason nguyên từ core. Invalid/unchecked/
   empty contract giữ `unresolved`; không dùng complement của empty unmet set
   để đánh tất cả là met.
4. Model nhận report fields về coverage, scoped quality, matched receipts,
   unmet outcomes và unresolved reasons. Không copy terminal-style `summary`,
   `declared_scope_completion` hay `lifecycle` của một exploratory assessment
   rồi trình nó như task đã xong. Lifecycle thật lấy runtime/dispatcher state.
5. Giữ full assessment report trong audit debug artifact nếu cần đối chiếu.
   Final boundary vẫn gọi reconciliation hiện tại như trước. Snapshot không
   write-back hay quyết định dừng/repair mới.

[schema](snapshot.schema.json) và [after example](after.snapshot.json) ở folder
này thay shape của `observed_state.progress` trong draft trước. Không sửa packet
review cũ. Example mới dùng core reconciler thật trên **authored synthetic
receipts**, không là run B. Global match ở example chỉ là notebook receipt,
không tự thêm dispatcher parent vào matched list.

Nếu sau này cần precise outcome→receipt/proof mapping, đó là change riêng của
reconciler với joint matching evidence và regression tests; chưa làm trong B.

## 3. Coherence cần version vector, không một generation giả chung

ArtifactStore generation chỉ đổi khi clear; notebook generation đổi khi
invalidate/reset, mỗi store có epoch riêng. `select_results` đổi selection mà
không tạo NoteEvent. Pending input cũng thay mà không được note cursor bao phủ.
Chỉ so một generation và note cursor có thể giữ view đã cũ.

**Quyết định:** source copier kiểm riêng runtime execution/cancel state,
notebook generation/cursor/active revisions/selection IDs + selection_set,
artifact generation/current membership + revisions, và copied pending-input
state. So trước/sau copy; tối đa2 retry. Không giữ store locks trong inference.
Vẫn cần existing generation/revision guards để từ chối late writes sau send.

Model-facing boundary thêm `artifact_store_generation`; `generation` hiện có
vẫn là journal/notebook epoch. Selection flag đi cùng selected refs để phân biệt
“chưa chọn” với “đã chọn rỗng”. Các kiểm copy/recheck khác có thể nằm trong
internal build diagnostics; không tạo context store hoặc transaction manager.
Không normalize identity gốc chỉ để làm scope check pass.

## 4. Phân biệt projection failure với task failure

Optional/unmodeled observation giữ raw và trust level. Contract/journal/control
export bị lỗi thì trả `context_build_failed` có reason; không tiếp tục với
context thiếu nghĩa vụ. Effects đã commit giữ nguyên. Snapshot không rollback,
không fabricate response và không biến failed projection thành model-quality
measurement. Trong B2, budget/cancel/needs_input/finish-only giữ flow hiện có.

## 5. Wiring phải đọc state mới ở mỗi actual model call

`run()` có thể thay `turn_contract` từ model proposal trước first effect.
Đưa object vào `context` một lần lúc bắt đầu dễ giữ contract cũ. Compiler phải
lấy binding hiện tại tại boundary, sau receipts của các actions đã commit.

| Boundary | Model phải thấy | Điều giữ nguyên |
| --- | --- | --- |
| Planner | Context trước proposal mới; provided contract nếu có, còn lại not_declared | Output schema, tools=[] |
| Actor trước first effect | Current bound proposal/contract, actual frozen=false nếu chưa freeze | First-effect freeze boundary |
| Actor sau action | Journal mới, revisions/selection/cursor mới, actual frozen state | Budgets, decisions, native call/result pairs |
| Verified repair | Rejected candidate và exact hash/check evidence; response vẫn pending | Repair limit, answer_schema, tools=[] khi schema yêu cầu |
| Finish | Effects/proofs/unmet work đủ để nói trung thực | Finish-only tools=[], không thêm execution |
| Queued tool call từ batch | Không có model boundary mới | Không build một fake model call/counter mới |
| Injected model_callable | Existing fixture API | Không gọi model thật hay thay protocol fixture |

B1 không đụng runtime call loop. B2 chỉ wiring boundary inputs/rendering sau
review B1. Issues liên quan chính sách matching/freeze/registry/model defaults
được báo Codex cùng reproducer; Anti không tự mở rộng scope để “cứu” fixture.

## Phần Codex tiếp tục giữ

- Quyết định semantic ambiguity, authority, closure và lifecycle.
- Review source diff, cases phá assumptions và sự khác biệt với baseline.
- Thiết kế phép đo model thật sau B; cùng task/source/budget, raw costs đúng scope.
- Quyết định bước D/learned policy sau đó; không cho Anti tự gộp planner hoặc
  tạo intent router trong lúc làm chores của B.
