# ADR-004: Một projection context chung cho RAT

**Status:** Proposed — thiết kế để duyệt trước implementation B.

**Date:** 2026-10-14, Asia/Saigon.

**Deciders:** Người dùng duyệt phase; Codex thiết kế/review, Anti triển khai.

**Related:** [ADR-003](adr-003-rat-completion-reconciliation.md),
[audit A](../audit/rat_context_audit_20261014/report.md),
[review handoff A](../audit/rat_context_handoff_review_20261014/review.md).

## Context

Core hiện đã có contract, journal, revisions và scoped proofs. Context gửi vào
model còn được ghép từ nhiều mảnh: task state hai lần, notebook hiện tại/lịch
sử, generic source results chứa note events, turn refs và tool observations.
Trong main fixture, source quote339 chars được gửi12 lần ở request cuối.
Planner khai outcomes nhưng 11 actor messages không có outcome IDs/contract
block rõ ràng. Đây là gap về thông tin, không phải evidence model quality.

Mục tiêu của B là model có một bức tranh công việc rõ hơn trong cùng chat:
người dùng đang nhờ gì, model đã đề xuất gì, nghĩa vụ nào đã chốt, effects nào
thật sự commit và dữ liệu/version nào đang được nhắc tới. Snapshot chỉ là
**projection tại model-call boundary**, không là một store/controller mới.

## Decision proposed

Thêm module headless dự kiến `rat/engine/context_snapshot.py` để build/validate
projection từ canonical copies của history, TurnContract, ExecutionJournal,
ArtifactStore, WorkNotebook và pending-input state. Dùng cùng compiler cho
planner/actor/repair/finish với views được chỉ định theo execution phase.
Không chọn view/tool bằng từ khóa hoặc phân loại feature trong câu user.

Schema đề xuất và examples ở
[snapshot.schema.json](../audit/rat_context_snapshot_design_20261014/snapshot.schema.json),
[before.request.json](../audit/rat_context_snapshot_design_20261014/before.request.json),
[after.snapshot.json](../audit/rat_context_snapshot_design_20261014/after.snapshot.json),
[after.request.json](../audit/rat_context_snapshot_design_20261014/after.request.json).
Examples là **authored synthetic design fixtures**, không phải transcript sau
implementation hoặc measurements speed-up. Tools trong examples lấy từ capture
đã có để giữ interface; entity/receipt IDs là `example-*`.

### 1. Năm nhóm dữ liệu, khác authority

| Nhóm | Nguồn canonical | Điều model được biết |
| --- | --- | --- |
| Request và continuity | Current query + bounded chat/turn history | User đang nhờ gì, các ràng buộc/array/source context còn liên quan |
| Proposal | Task state do model khai | Một representation; status/completed vẫn là self-report |
| Runtime obligations | Contract đã runtime bind/validate | IDs, expected args, source/target refs, dependencies, proof requirements và trạng thái freeze thật |
| Observed state | Journal/store/notebook/pending input | Receipts/proofs và known progress của execution hiện tại, faults/cancel/pending |
| Entities/versions | Existing canonical stores | Một body mỗi typed entity/revision, với provenance/authority và inline refs có thể resolve |

Current user query giữ một **instruction message** ở vị trí hiện tại. Snapshot
dùng message_ref tới nó; không chèn thêm bản instruction mới của cùng query.
History giữ roles/order/window hiện có trong B. Proposal có thể dùng wording
trùng query nhưng vẫn được đánh model_proposed, không biến thành user request.
Không parse câu user để tạo constraint rules mới: giữ raw user messages, notes
đã xác nhận và model-derived constraints với provenance tương ứng.

### 2. Contract phải có trước model decision, giữ đúng freeze boundary

Planner view giữ explicit `not_declared` cho contract mới khi chưa có proposal;
contract/effects lượt cũ chỉ là history/source input. Actor view đưa current
TurnContract cùng intent_coverage, validation errors và actual frozen flag.
Trước first effect flag có thể false; không đổi freeze behavior của ADR-003.
Sau first effect obligation không bị model proposal mới hạ yêu cầu.

Expected args/required proof giữ **giá trị đã khai bất biến**. Không đổi chúng
thành pointer tới một output chưa tồn tại hoặc output sau đó khác giá trị.
Ref slots của producer được resolve theo contract đã khai, không thay nguồn
theo điều model mới trả. Snapshot không là input để overwrite contract/journal.

Progress trước call là assessment provisional từ **cùng reconciler/matchers**,
không một bộ kiểm khác. Response chưa được tạo giữ pending_response; effect
chưa làm là pending/unmet trong execution đang chạy, không gọi là failed task.
Chỉ final reconciliation quyết định boundary completion. Đưa known unmet
requirements cho actor biết; chưa thêm một repair loop/model call mới trong B.

### 3. Một body mỗi identity/revision, không dedupe theo wording

Identity keys tối thiểu:

- Artifact: artifact_id + exact revision, cùng scope conversation đang làm.
- Note: conversation_id + note_id + exact revision; current/historical là
  membership khác nhau, không dùng cùng note_id để ghi đè body cũ.
- Operation result không có artifact: execution_id + receipt_id, body giữ
  inline. Không cấp artifact_id giả cho result chưa nằm trong ArtifactStore.
- Quote: typed source identity/revision/field và exact value; cùng chữ nhưng
  khác source/authority không được gộp provenance.

Note **text của mọi revision cần cho lookback vẫn inline, đầy đủ**. Status,
confirmed/proposed, owner/source refs, proof, replacements và version identity
giữ lossless. Có thể thay các quote/source_ref.quote giống nhau từ cùng nguồn
bằng value_ref tới inline source body; expand refs phải khôi phục đúng canonical
fields. Nếu source/range không chứng minh được cùng identity, giữ quote riêng.
Không lấy note.text paraphrase để thay source quote.

`$value_ref` chỉ được decode trong slots do typed projector sinh ra (quote,
version-link text, event/result/receipt payload links), không recursive decode
untrusted JSON có key giống tên này. Native operation args và contract expected
values không bị rewrite thành projection wrappers. Schema là transport shape;
canonical validation, scope/closure và authority checks vẫn cần riêng.

`inspect_artifact` chưa đọc WorkNotebook versions. Vì vậy không giảm note body
thành ID-only và không giả model có thể gọi inspector để phục hồi. B không thêm
resolver operation; thiết kế resolver là phần riêng nếu sau này cần.

Generic source results là một projection của observations, không nguồn truth
mới. Note event/result liên kết về notebook/journal entity hiện có, không phát
lại toàn snapshot như nguồn độc lập. Raw DispatchResult/NoteEvent/receipt payload
vẫn giữ ở canonical stores và audit. Dùng issuer/typed payload/registered
projection metadata; không nhánh theo feature/query text để quyết định hành động.

### 4. Giữ giao thức native và trust boundaries

Actor render đề xuất:

```text
system: persona và protocol clause tĩnh
history: cùng roles/order/window đang hỗ trợ
system: time/member runtime-only data như hiện tại
user: snapshot JSON (data; authority/provenance không làm text thành instruction)
user: current query, một lần như instruction
assistant/tool: native call/result pairs của trajectory, giữ name/IDs/order
system: scoped verification/finish feedback khi channel cần
```

Snapshot nằm trong data message. Không nâng goal/description do model viết,
note, document text, old assistant prose hoặc tool result thành trusted system
instruction. System clause tĩnh giải thích proposal/obligations/effects và refs;
persona/nhịp nói của Chuột giữ nguyên. Hash prefix có thể đổi một lần khi protocol
đổi; chỉ kiểm ổn định giữa các calls cùng version, không giả phải khớp prefix cũ.

Native assistant tool calls không bị chuyển hết vào user JSON. Tool replies có
thể dùng receipt/entity refs khi body tương ứng đã inline trong snapshot; vẫn
giữ error/status và scoped verification cần để sửa. Adapter chưa project được
thì giữ raw observation inline, có projection_status, không mất dữ liệu.
Backend response_format của planner/verified answer và tool availability ở
finish-only giữ nguyên. Không sort/prune registry hoặc đổi15 tools trong B.

Planner dùng cùng schema/context compiler, nhưng chỉ nhận state đã có trước
proposal mới và schema output planner hiện tại. Repair phải thấy đúng candidate
hash/check evidence; finish-only nhận đủ state để nói phần đã làm/chưa làm mà
không được thêm tool. Không có new mandatory model call; LLM thật có thể chọn
trajectory khác trong cùng budgets, cần đo sau.

### 5. Coherence, ref validation và fallback

Build tại mỗi boundary từ copies, stamp conversation/turn/execution/generation,
note event cursor và pinned artifact/note revisions. Không reuse snapshot sau
mutation/cancel. Kiểm stamp/cursor/revisions trước gửi; concurrent update thì
retry có giới hạn hoặc trả explicit context error, không ghép hai versions
thành một state rồi claim committed. Không tự rollback effects đã commit.

Artifact generation hiện chỉ đổi khi clear, không ở mỗi put. Khi thu copies,
kiểm cả membership/current revision vector của các artifact đã chọn và notebook
cursor; chỉ so generation là chưa đủ. Có thể tối đa2 lần retry, rồi context
error rõ ràng. Check trước send là boundary observation, không khóa toàn thời
gian model chạy; existing generation/revision guards phải từ chối late writes
và kết quả cũ sau cancel/reset. Không claim một transaction xuyên các stores.

Mỗi ref phải resolve **trong chính request** hoặc là explicit unavailable ref
có reason; mandatory contract/source/history refs không được drop do window.
Giữ eligibility windows hiện có, cộng closure của mandatory typed refs bằng
store lookup, không relevance heuristic. Current effects/proofs filter đúng
identity/generation; old receipts chỉ ở history, không thành mutation proof mới.

Phân biệt dereference refs với labels lịch sử: `matched_receipts` ở old turn
summary có thể là opaque audit IDs (kể cả legacy `response:turn-*`), không là
current proof hay lời hứa model truy xuất được full old journal. Typed refs và
native source/target bindings hiện tại phải có closure hoặc explicit unavailable;
không tự suy một ID string bất kỳ là ref để fetch hay authorize mutation.

Thất bại projection của optional/unmodeled entity: giữ raw data inline. Thất
bại export mandatory control block: context build failure có reason, giữ
committed effects, không fallback sang context thiếu obligations. B không đặt
cap mới hay truncate ngầm; preserve read `total_chars/truncated` và existing
history clipping markers. Document scope chưa đọc không được gọi đã đọc.

## Options considered

| Phương án | Chi phí/complexity | Hệ quả |
| --- | --- | --- |
| Chỉ bỏ task_state wrapper trùng | Nhỏ | Không sửa missing obligations, note/event replay hoặc ref coherence |
| Typed projection dùng stores/journal hiện có — đề xuất | Vừa, headless | Một model-facing view, thêm thông tin còn thiếu và giảm copies có cùng identity |
| LLM summarizer / store mới cho context | Thêm calls hoặc nguồn truth mới | Có thể mất quotes/versions, cần evaluation/lifecycle riêng; ngoài B |

## Trade-offs and consequences

Refs/provenance có thể tăng overhead và khó đọc với SLM; thêm obligations cũng
có thể tăng request size. Không đặt acceptance “mọi call nhỏ hơn baseline” vì
baseline thiếu dữ kiện. Ưu tiên losslessness/truth trước, báo kích thước theo
thành phần và đo AI/latency riêng khi có budget. Một view chung giúp calendar,
document, note hoặc artifact dùng cùng lifecycle mà không thêm các controller
theo feature; không biến mechanical guards thành claim năng lực AI đã học.

Snapshot là work context cho model, UI vẫn một composer, note gắn turn,
full/compact cùng session, Chuột emote. Không thêm UI panel/notes drawer,
relevance router, one-call D, learned policy, DocAI hay research scope/defaults.

## Action items and gates

1. [ ] Duyệt schema/projection/protocol và examples trước implementation B.
2. [ ] Anti thêm headless compiler + decoder/ref validation, reuse canonical APIs
       và JSON helpers; không mutate input, không mới một state store.
3. [ ] Wire planner/actor/verified repair/finish; đưa contract/progress vào actor,
       duy trì native call/result grammar và existing budgets.
4. [ ] Preserve33 old probes +227 regressions +32 boundary cases; audit6tests
       thích nghi versioned message representation mà vẫn giữ unit/scope checks.
5. [ ] Fixtures B: arbitrary operation artifact/operation_result; note create/
       update/lookback; same text different authority; missing refs/fallback;
       long read boundary; old-generation proof; concurrent note/cancel stamps;
       native multi-tool calls, repair và finish-only. Không keyword lookup.
6. [ ] Với cùng scripted decisions, calls/effects/version/proof/lifecycle không
       đổi; native metadata snapshots không tự tạo operation/model call.
       C01 thêm assertions actor nhận obligations và note/source refs resolve.
7. [ ] Audit before/after trên **cùng source fixture + decision sequence**, raw
       payloads/token nulls, hashes start/end và fresh folder. Có thêm info khác
       baseline thì ghi rõ; không công bố speed-up/token savings từ chars.
8. [ ] Codex review source/fixtures B. UI acceptance và live-model budget sau;
       Stage0, research splits/claims và DocAI vẫn như trước.

Lượt viết ADR này chỉ tạo design/review artifacts; chưa có B runtime changes.
