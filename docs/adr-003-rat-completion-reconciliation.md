# ADR-003: Đối chiếu kết quả công việc trong RAT

**Status:** Accepted for core implementation — người dùng chốt core trước, duyệt UI sau; Antigravity triển khai, Codex thiết kế và review. Chưa có implementation cho contract này.
**Date:** 2026-10-13
**Deciders:** Người dùng phụ trách RAT.
**Related:** [ADR-001](adr-001-rat-interaction-kernel.md),
[ADR-002](adr-002-rat-adaptive-interaction.md),
[contract result notes](rat_result_notes_contract.md),
[review thiết kế](../audit/rat_outcome_contract_review_20261013/review.md).

## Context

User muốn một chat liền mạch, có Chuột và notes gắn theo lượt, cùng một core cho
các năng lực. Model 4B trong development pilot đã nói lưu 324 mà không tạo note.
Runtime hiện có dispatcher, artifact revisions, note events và scoped proofs,
nhưng completion còn lấy từ task state do model tự báo. Reconciliation cần nối
những phần đó, không tạo các bộ điều khiển riêng cho mỗi feature.

Đối chiếu được một effect không chứng minh model đã hiểu đủ yêu cầu hay prose
luôn đúng. LLM vẫn chịu trách nhiệm hiểu mục tiêu, phối hợp năng lực và giao tiếp;
checker hỗ trợ phần có scope hình thức. Bản này không thay hướng NCKH, Stage 0
hoặc DocAI; không coi fixture hay pilot đã lộ là evidence chất lượng held-out.

## Decision proposed

Dùng contract request-scoped và journal effects trong kernel/runtime. Module
headless nhỏ `rat/engine/completion.py` chứa schema và pure reconciler.
Tận dụng NoteEvent, DispatchResult/ExecutionEvent, ArtifactStore revisions,
VerificationReport; receipt là snapshot/index đáng tin của những dữ liệu đó.
Không lập một nguồn truth song song với notebook/store.

### 1. Tách ba điều cần biết

| Trục | Dữ liệu | Điều được chứng minh |
| --- | --- | --- |
| Coverage ý định | Đề xuất outcomes có schema/provenance, `model_proposed / ambiguous / invalid / unchecked` | Đây là cách model hiểu yêu cầu; chưa bảo đảm đủ mọi ý. |
| Completion trong scope đã khai | Nghĩa vụ `satisfied / partial / unresolved / not_applicable` và matched receipts | Effects/response đã đáp ứng contract đã khai đến đâu. |
| Correctness theo scope | Reports PASS / FAIL / UNKNOWN, checker và evidence IDs | Kết luận hình thức được kiểm tra; quality ngoài scope giữ UNKNOWN. |

Lifecycle lượt `in_progress / completed / needs_input / failed / cancelled`
giữ ý nghĩa vòng đời execution. Một lượt đã kết thúc với response không đồng nghĩa
mọi công việc đã hoàn thành. History, turn refs và UI cùng nhận reconciliation
snapshot, không suy từ lifecycle label hoặc câu model viết.

### 2. Contract trước thực thi và hỗ trợ planner OFF

Đề xuất outcomes có `schema_version, contract_id, conversation_id, turn_id,
execution_id, generation, proposed_by, source_message_refs`; các identity là
runtime-supplied, model không được tự gán.

Mỗi outcome có ID, kind chung (`response` hoặc `registered_effect`), tham chiếu
đích/nguồn và dependency IDs; adapter đã đăng ký mô tả effect/proof cần đáp ứng.
Calculator và notes là adapters đầu tiên, không phải enum feature bắt buộc ở
reconciler. Không dùng regex từ yêu cầu để chọn hoặc âm thầm thực hiện tool.

Planner ON đề xuất qua schema mở rộng của planning call hiện có. Planner OFF cần
đề xuất cùng contract trong model decision trước effect đầu; việc encoding qua
native structured decision phải được triển khai/test cho client hiện có. Không
mặc định thêm một call phân loại riêng. Fixture injection có nhãn riêng.

Runtime validate và cố định nghĩa vụ trước thực thi; chỉ resolve slot/ref đang
chờ theo producer đã khai. Model status update không được xóa nghĩa vụ, hạ proof
hay thay đích sau khi đã chạy để hợp thức hóa kết quả. User đổi mục tiêu tạo
contract mới trong lượt/execution phù hợp; lịch sử contract cũ giữ nguyên.
Đích mơ hồ tạo needs_input, không chọn bừa.

Contract vắng/sai/trống khi chưa có căn cứ giữ unchecked/invalid. Contract chỉ
khai response có completion `not_applicable` cho effects và coverage
`model_proposed`; không chấm “ý định đã verified”. Đây là giới hạn đối với model
bỏ luôn outcome; phải có ca test/semantic review cho lỗi đó.

### 3. Receipts phát hành từ điểm thực thi thật

Envelope do runtime phát hành gồm `receipt_id, issuer, sequence, conversation_id,
turn_id, execution_id, generation, operation_call_id, status, committed,
artifact/note refs, before/after revisions, parent_receipt_ids, evidence_hash`.
Dữ liệu payload là snapshot riêng hoặc canonical representation; không chia sẻ
nested dict mutable với model. Model có thể tham chiếu receipt ID; matcher chỉ
tra journal thực, không nhận receipt JSON làm bằng chứng.

Note mutation dùng NoteEvent đã commit với context. Operation success/pending/
error/cancelled lấy từ dispatcher, không đếm “operation_started” là thành công.
Proof liên kết với đúng evidence/revision/scope/checker. Receipt của thất bại
được giữ để giải thích, không thỏa success requirement.

Journal request không phụ thuộc vào model prose, `task_state.completed`, hoặc
chỉ vào 100 events gần nhất của global state. Các effects đã commit được phản ánh
đúng ngay cả khi bước sau lỗi/cancel. Không thêm rollback giả.

### 4. Matching cả đối tượng và quan hệ giữa effects

Ví dụ “tính gấp đôi kết quả hiện tại rồi ghi lại” có producer và consumer:

- Producer có nguồn input/revision đã khai, output artifact/revision thật.
- Consumer note phải trỏ tới output đó với field đúng; checker yêu cầu ở scope
  đã khai phải đạt. Lưu 126 không thỏa nghĩa vụ lưu kết quả producer 324.
- Update khớp note ID đích, revision quan sát trước và revision sau commit.
- Receipts của execution cũ không thỏa một yêu cầu mutation mới. Kết quả cũ dùng
  làm input/continuation qua ref rõ ràng; không giả receipt mới.
- Evaluator kiểm trạng thái tại boundary completion: một note đã remove trong
  cùng execution không được báo đang được lưu. User sửa sau đó tạo version/turn
  mới; không thay kết luận lịch sử của lượt trước.

Không bắt mọi câu giải thích dùng tool. Numeric response có proof literal phù hợp
có thể đủ cho yêu cầu số học không cần artifact; lưu kết quả thì cần nguồn có thể
tham chiếu. Lookback có context có nguồn không phải gọi inspect chỉ để có receipt.

### 5. Reconciliation và các trạng thái còn thiếu

| Điều kiện | Kết quả |
| --- | --- |
| Effects bắt buộc có committed receipts khớp và mọi proof bắt buộc đạt | Satisfied trong declared scope; coverage intent vẫn model_proposed. |
| Không có nghĩa vụ effect, có response | Response produced; effects not_applicable; content quality giữ scope thực. |
| Thiếu receipt, chưa làm nghĩa vụ đã khai | Unresolved với reason omitted_action và outcome ID. |
| Một số nghĩa vụ thỏa | Partial; giữ kết quả đã commit, ghi unmet outcomes. |
| Có proposed note | Effect proposal được ghi; chỉ thỏa nếu obligation cho phép proposal. |
| Proof bắt buộc UNKNOWN/FAIL | Nghĩa vụ đó unresolved; bounded repair nếu budget cho phép. |
| Không có checker hoặc UNKNOWN ngoài nghĩa vụ hình thức | Ghi not_checked/UNKNOWN; không tự PASS, không tự chặn mọi effect. |
| InputRequest thật còn chờ | Lifecycle needs_input; ghi các nghĩa vụ pending cùng receipts đã có. |
| Cancel | Lifecycle cancelled; không nhận late writes, giữ effects commit trước cancel. |
| Lỗi hoặc budget hết | Lifecycle kết thúc theo lý do thực; giữ partial/unresolved và data đã commit. |

Không dùng enum lỗi riêng cho từng feature. Reason codes và unmet outcome IDs
giải thích completion chung. Bounded repair không tự gọi tool cứu hộ và không
vượt budget; model vẫn đề xuất bước tiếp dựa trên missing outcomes.

### 6. Câu trả lời, history và một bề mặt chat

Raw candidate và model self-report giữ trong audit. Phản hồi user cùng context
lượt sau nhận facts và reconciliation đã kiểm tra, không lưu một câu xác nhận
thao tác thiếu receipt như completed work. Nếu cần viết lại, model nhận facts/
unmet outcomes trong cùng budget; không làm được thì hiện trạng thái thực đã biết.

Receipt matcher không kiểm chứng mọi mệnh đề trong prose tùy ý. Phần claims
ngôn ngữ tự nhiên vẫn cần schema/semantic evaluation, chưa được hứa chặn hoàn toàn.
UI không tự phát nhãn “đã lưu” từ prose/model status. Copy dùng effects cụ thể:
“Đã ghi 324”, “Mình đã tính xong; phần ghi chú chưa lưu”, “Ghi chú này đang là
đề xuất”. Technical receipt/proof scopes nằm trong trace khi mở.

Giữ composer, full/compact, Chuột bên trái và click emote. Thay wiring status/
history là một phần correctness, không mở rộng layout. Copy mới cần review ở
phase UI theo yêu cầu của user.

### 7. Measurement là phase riêng

Không có model calls được cấp thêm bởi ADR này. Budget pilot sau đó cần model,
số conversations/arms, tổng calls hard cap gồm planner/repair/cancel attempts,
timeout và wall cap. Cap phải chặn ngay ở transport trước mỗi attempt.
Hai arms ON/OFF cần hai conversations; “một conversation/20 calls” không mô tả
được ablation đó nếu không nói rõ toàn budget.

Log client model-call wall spans, operation/check spans với parent IDs và server
prompt/eval durations riêng. Note checker lồng trong operation không cộng hai lần.
Giữ prompt/completion null khi chưa biết, partial sums và chi phí đầy đủ riêng.
Hash source start/end, journal sau từng call, config/seed thực truyền và thứ tự/load
đã biết. Static prefix không đồng nghĩa cache reuse đã xảy ra.

Một conversation/arm là exposed development pilot, không đủ claim nhân quả/tổng
quát; context diverges theo phản hồi/actions phải được ghi. Không đổi default
planner/model trước review bằng chứng.

## Options considered

| Phương án | Complexity | Cost | Mở rộng | Quan hệ code |
| --- | --- | --- | --- | --- |
| Tiếp tục dùng model task status làm completion | Thấp | Không thêm call | Lỗi nói đã làm còn tồn tại | Giữ source hiện tại |
| Contract chung + snapshot receipts từ stores/events hiện có | Vừa, tập trung | Reconciliation offline; model schema overhead cần đo | Operation adapters dùng một reconciler | Tận dụng kernel/notes/proofs |
| Một bộ luật riêng cho calculator/notes/calendar và receipt store song song | Tăng theo feature | Có thể thêm calls/copy data | Mỗi feature thêm nhánh và nguồn truth | Dễ tái tạo trải nghiệm rời rạc |

Đề xuất phương án thứ hai. Chỉ viết matcher cho effects/scopes đã hỗ trợ ở lát cắt;
các phần chưa hỗ trợ giữ unchecked, không xây solver mọi intent hay hệ DSL lớn.

## Trade-off analysis

Contract giúp phát hiện thiếu hành động đã khai và provenance sai. Schema không
bảo đảm model khai đủ intent; receipts không thay thế model mạnh, chất lượng prose
hay latency đo thực. Lát cắt đầu phải chứng minh cả nguyên tắc chung và trường hợp
calculator/notes, không mở nhiều feature để tạo cảm giác agent.

## Consequences

- Có thể nối tính, lưu, sửa và tiếp tục bằng đúng dữ liệu trong một chat.
- Trạng thái làm việc không bị model tự báo completed che mất phần còn thiếu.
- Cần thêm identity, matching dependencies và wiring history/UI được test.
- Cần chấm intent coverage/content trong live evaluation riêng với receipt matching.
- Trước mắt chưa có capability AI-generated hoặc thay đổi research claims.

## Action items

1. [x] User chốt thiết kế và phase core: Antigravity triển khai, Codex thiết kế/review; UI duyệt sau.
2. [ ] Implement schema/reconciler headless + adapters tối thiểu; reuse journal events/proofs.
3. [ ] Wire planner ON/OFF; freeze contract; error/needs_input/cancel và action summaries.
4. [ ] Propagate reconciliation qua AgentResponse/TurnSnapshot/turn refs/UI hiện có.
5. [ ] Test original lifecycle, source/proposal/versioning và negative fixtures bên dưới.
6. [ ] Review UI copy và budget live pilot riêng, rồi mới chạy model/native.
7. [ ] Báo raw traces, source hashes, counters có thiếu và các lỗi semantic chưa giải quyết.

Các negative cases bắt buộc: omit tool; omit cả outcome; plan bị hạ requirement;
tính đúng nhưng lưu nhầm output; receipt khác execution/generation; fake receipt;
source/revision stale; proposed không đạt proof bắt buộc; tạo rồi remove; có lỗi
đã phục hồi; needs_input; cancel trước call và cancel sau commit (hai probes riêng);
continuation execution mới; unresolved tới cùng full/compact/history; câu giải
thích không tool vẫn có response và không có giả quality PASS.

Chỉ tài liệu thay đổi ở mốc review này. Chưa có implementation/tests/model runs
mới cho contract đề xuất; [review/manifest](../audit/rat_outcome_contract_review_20261013/validation.json)
ghi source và attachments đã đối chiếu.
