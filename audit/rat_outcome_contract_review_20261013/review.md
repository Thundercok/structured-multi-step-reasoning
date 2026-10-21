# Review thiết kế Antigravity: outcomes và completion

Ngày 2026-10-13. Phạm vi: review tài liệu do người dùng cung cấp và đối chiếu source.
**Quyết định: giữ hướng reconciliation, sửa contract trước khi triển khai.**
Người dùng sau đó đã chốt ADR-003 đã chỉnh: core trước, duyệt UI sau;
Antigravity triển khai, Codex thiết kế và review. Chưa có code triển khai mới.
Chưa sửa runtime, chưa chạy model/Qt, chưa phê duyệt budget live ablation.
Skill áp dụng: engineering:architecture.

Bản gốc được giữ trong `original_design.md.txt`; không chỉnh artifact của Antigravity
ngoài workspace. [ADR-003](../../docs/adr-003-rat-completion-reconciliation.md)
là contract đã chỉnh và được user chốt cho phase core. [Brief](handoff_antigravity.md)
là văn bản người dùng có thể gửi lại, chưa gửi bằng công cụ.

## Những phần phù hợp

Phân biệt task state do model đề xuất và hiệu ứng thực, giữ scope của checker,
giữ dữ liệu đã commit khi cancel, không cứu bằng keyword, không mở app con.
Đây là phần NeSy giúp RAT kiểm chứng phần có thể kiểm chứng trong core chung.
Nó không chứng minh model đã hiểu đủ mọi ý trong một yêu cầu.

## Các sửa cần thiết

### R1 — Mục tiêu bị bỏ sót có thể biến mất trước khi reconciler chạy

Mục 2.1/2.3 và projected diff chưa định nghĩa cách lấy OutcomeSpec ở planner ON/OFF,
khi nào cố định, xử lý plan trống/sai/thiếu mục tiêu và có cho model xóa mục tiêu
sau thực thi không. Nếu cùng model trả `conversational_response` và “Đã ghi”,
không khai mục tiêu ghi, bộ đối chiếu không tự biết mình phải tìm note event.
Tuyên bố “xử lý triệt để omitted actions” chưa có căn cứ.

Cần cố định đề xuất mục tiêu trước hiệu ứng đầu tiên, schema/version và provenance;
không cho status update hạ yêu cầu. Theo dõi `intent_coverage=model_proposed`
riêng với completion của các nghĩa vụ đã khai. Không có contract hợp lệ thì
completion unchecked; không nâng thành workflow verified. Fixture omission phải
có cả ca bỏ tool và ca bỏ luôn outcome; chấm intent ở live run độc lập.
Không thêm một call phân loại mặc định chỉ để schema trông đầy đủ.

Source: `AssistantRuntime._plan_task` hiện dùng TASK_STATE_SCHEMA dạng mô tả,
chưa có outcomes; `ModelDecision` cũng chưa mang contract. Planner OFF vẫn cần
một đường model đề xuất có kiểu, không thể dựa riêng vào initial planner.

### R2 — Có receipt chưa có nghĩa đã làm đúng việc yêu cầu

Bản thiết kế chưa gắn calculate → note bằng quan hệ nguồn bắt buộc. Model có thể
tính 324 nhưng lưu lại 126, hoặc một event của execution cũ được dùng như thao tác
mới. `NoteReceipt` đề xuất thiếu conversation/execution/generation,
before_revision và liên kết cụ thể với nghĩa vụ.

Dùng trusted NoteEvent/DispatchResult/evidence làm nguồn, snapshot trong journal
runtime của request; tham chiếu ID/revision/field/hash, thời điểm và parent receipt.
Outcome ghi “kết quả vừa tính” chỉ được thỏa khi nguồn note là artifact/revision
của producer đó. Update phải khớp note đích, revision trước/sau và trạng thái note
ở boundary đối chiếu. Artifact cũ được đọc làm input không thay thế receipt ghi
mới. Model đưa receipt ID; runtime tra journal thật, không tin receipt JSON của model.
`frozen=True` với dict lồng bên trong không bảo đảm snapshot bất biến.

Source: WorkNotebook đã có NoteEvent chứa sequence, conversation_id,
before/after_revision, snapshot và context execution/generation. Nên dùng lại
thay vì lập thêm NoteReceipt yếu hơn.

### R3 — Completion phải đi hết tới UI, history và câu trả lời

Projected diff bỏ qua `rat/ui/omnibar.py`. Hiện `_on_assistant_response` dùng
`response.error` và pending input để phân luồng; phần còn lại lấy response.answer
rồi gọi complete_turn. `_complete_chat_turn` chưa truyền reconciliation.
`ConversationHistory.complete_turn` ghi status completed và giữ answer làm
history. Vì vậy response.error=None với unresolved có thể vẫn thành turn completed
và phát câu “Đã ghi” nguyên văn.

Cần truyền một reconciliation snapshot chung vào full/compact/history/turn refs.
Giữ lifecycle của lượt riêng với completion của công việc. Raw candidate phải
được lưu ở audit; câu dùng cho user/history không được trình bày như một xác nhận
thao tác đã xảy ra khi receipt thiếu. Bounded resynthesis từ receipts dùng cùng
budget; nếu thất bại, chỉ hiện tình trạng thực đã biết. Việc một prose tùy ý còn
khẳng định sai là phần semantic cần review, không tuyên bố receipt matcher hiểu
và chặn được mọi câu nói sai.

### R4 — Quy tắc “mọi verification PASS” làm nghẽn các tác vụ không có checker

Mục 2.3 dùng completed khi “verifications PASS”, unresolved khi UNKNOWN, nhưng
chưa phân biệt proof bắt buộc của một outcome với UNKNOWN ngoài scope. Lịch,
search, read và nhiều câu hỏi hội thoại chưa có verifier toàn nội dung. Cần giữ
UNKNOWN ở chất lượng chưa kiểm chứng mà vẫn ghi nhận tool/effect đã xảy ra.

Một proof bắt buộc trả FAIL/UNKNOWN thì nghĩa vụ đó chưa thỏa; không có checker
được ghi `not_checked`/UNKNOWN, không tự gọi PASS và không tự chặn mọi hành động.
Receipt chứng minh effect; checker chứng minh đúng trong scope; coverage ý định là
một trục khác. Đặc biệt, matrix phải giữ `needs_input` cho InputRequest thật,
không biến thiếu dữ liệu thành failed hoặc omitted action.

### R5 — Contract đang gắn mục tiêu quá chặt vào tên chức năng

`artifact_calculation`, `note_record`, `artifact_inspection` có thể là adapters
đầu tiên; không nên thành các nhánh trung tâm phải bổ sung mỗi khi thêm capability.
“Tính 2+2” có thể đủ bằng đáp án số đã kiểm tra; đọc lại một giá trị có nguồn
trong context không luôn đòi gọi inspect_artifact. “So bản cũ” không nên để fixture
tùy ý chọn conversational hoặc completed mà không có quy tắc.

Reconciler dùng nghĩa vụ chung: response và effect đăng ký, refs/dependencies cùng
proof scope nếu bắt buộc. Domain adapter mô tả receipt phù hợp; runtime không
switch theo DSA/calendar/natal/calculate. Bắt buộc artifact khi cần nguồn lưu/
thao tác tiếp, không bắt gọi tool chỉ để có badge. Không xây DSL/universal solver
ở mốc này.

### R6 — Cancel sau commit và timeout HTTP là hai probes khác nhau

Fixture hiện có kích cancel sau calculate callback và giữ artifact 324, hợp lệ.
Live harness lại kích timer trong lúc chờ HTTP với timeout 0.6s; lúc đó chưa chắc
đã có artifact nào. Không được dùng kết quả HTTP probe để chấm fixture “giữ 324”.
Cancel khóa execution cũ; các effects đã commit hợp lệ vẫn giữ; tiếp tục bằng
execution mới và explicit refs. Không tự rollback, khóa artifact hay đánh dấu
turn cũ completed khi lượt sau đã làm xong.

### R7 — Budget A/B và timing cần xác định theo call thật

“20 calls, 1 conversation” mâu thuẫn với hai arms ON/OFF. max_steps mỗi lượt không
phải hard cap toàn run. Cần budget được user duyệt riêng: model, 2 conversations,
cap tổng calls gồm planner/repair/cancel attempts, timeout và wall cap toàn run.
Kiểm tra cap ngay ở client trước mỗi HTTP attempt và ghi lý do dừng.

Model-call wall time gồm transport/prompt/generation; không gọi toàn bộ là
generation time. Checker note nằm trong operation time; tổng nested timings có
thể double count. Ghi phase span có parent ID, server timing riêng, partial tokens/
unknown và source hashes. A/B một conversation/arm là development pilot, không
chứng minh causal efficiency hay chất lượng tổng quát; thứ tự, load/cache và
divergent context phải được ghi. Không tuyên bố cùng seed nếu chưa truyền/ghi seed
thực tế. Projected line-count diff là ước tính, không phải diff đã thực thi.

### R8 — Copy “đối chiếu biên nhận” đưa implementation vào trải nghiệm

Receipt là dữ liệu trace. Bề mặt chat dùng câu cụ thể theo hiệu ứng thật như
“Đã ghi 324”, “Đã sửa ghi chú”, hoặc “Mình đã tính xong; phần ghi chú chưa lưu”.
Giữ note proposed là proposed, không ép user xác nhận mỗi note chỉ để mốc được PASS.
Khi nghĩa vụ chỉ yêu cầu một đề xuất, lưu proposal có thể thỏa effect đó;
khi yêu cầu dữ kiện đã xác nhận, proposal chưa đủ. Review copy trong phase UI;
không thêm toolbar/panel/badge và không sửa Chuột.

## Bàn giao để triển khai

Ưu tiên R1–R4 và đường UI/history trong lát cắt đầu, với các adapter hiện có.
R5–R8 là ràng buộc phạm vi và measurement. Không đổi default planner/model để
làm demo đậu; không tích hợp DocAI hoặc thay Stage 0.

Review này chỉ xác nhận thiết kế và source đã đọc. 206 tests ở mốc trước là
evidence phần mềm của snapshot cũ, không phải tests cho reconciliation đề xuất.
Không có tests/live runs mới trong lượt review này; không thay nội dung raw logs cũ.
