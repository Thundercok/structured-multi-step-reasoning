# Codex review B1 — Request changes trước B2

Ngày 2026-10-14, Asia/Saigon. Review source B1 và bộ tests của Anti theo
ADR-004 cùng decisions.md. Không sửa product source trong lượt review này.

Core/runtime vẫn khớp packet bàn giao. Codex chạy độc lập 14 B1 tests +6 audit
tests: **20 passed**. Trên 21 probes bổ sung tự soạn:1 control hợp lệ qua,
**20 ca vi phạm yêu cầu**,0 lỗi runner. Đây là software counterexamples được
nhóm dưới đây, không là20 features hay tỷ lệ lỗi/chất lượng AI được đo.

## Những phần đúng

- Headless, không live inference/Qt hay runtime wiring.
- Reuse joint reconciler, không tự map outcome→receipt; response giữ pending.
- Separate epochs và selection_set, giữ inline note text cho current/history.

Phần chưa đạt nằm ở typed ref ownership, lossless projection và validation.
Các tests hiện có chủ yếu mở rộng **design fixtures đã được viết đúng sẵn**;
chưa kiểm full roundtrip những snapshots do compiler tự sinh trong các cases
dưới đây. Vì thế pass312 tests trong packet không đóng các gaps này.

## F1 — [P1] Raw payload và literal args bị diễn giải thành runtime refs

[context_snapshot.py:178](../../rat/engine/context_snapshot.py#L178) dùng
full path nếu có, còn lại **fallback theo tên key**. Các key `quote`, `note`,
`snapshot`… ở bất kỳ depth/root nào đều có thể được decode. Validator cũng dùng
last path segment ở line203. Không có typed owner/registered projector origin.

Probes `raw_payload_quote_wrapper`, `operation_args_quote_wrapper`:
unmodeled custom result hoặc `operation_args={quote: fake_ref}` trở thành
`{quote: "inline source"}` khi expand. Test injection hiện tại chỉ đặt fake ref
dưới `remaining`, nên bỏ sót key trùng allowed slot. Line604–621 còn tự project
generic custom result có `note`/`note_event` dựa vào shape/ID mà không có output
projector contract; `unknown_operation_note_shape` đổi text raw thành text note
trong notebook. `is_value_ref` cũng nhận object có thêm keys rồi bỏ chúng khi
resolve, thay vì exact wrapper shape.

**Sửa:** root/owner kind + declared exact paths và metadata do compiler tạo
quyết định refs; không base-key fallback và không caller/user JSON tự cấp quyền
decode. Raw fallback, operation args, expected args, proposal/document bodies
luôn opaque trừ slot đã được registered projector xác nhận. Một ref được
resolve vào raw body không cho phép tiếp tục recursive decode raw body đó.

## F2 — [P1] Projection đánh “lossless” nhưng đổi dữ liệu/type/snapshot

[quote projection:483](../../rat/engine/context_snapshot.py#L483) dùng `str`/
`strip` equivalence: string quote `"42"` trở thành integer42; `"source"` trở
thành `"source  \n"`. Line487 ghi đè `source_ref.quote` theo quote khác, kể cả
khi giá trị ban đầu không giống. Quote refs chỉ hợp lệ khi exact JSON value/type
và source identity/revision/field cùng nhau; không normalize để dedupe.

[replacement projection:501](../../rat/engine/context_snapshot.py#L501) thay
replaces/replaced_by text mà không so nguyên giá trị với target `/text`.
[event snapshot:555](../../rat/engine/context_snapshot.py#L555) và generic
result.note/note_event cũng dùng identity-only substitution. Probe event lưu
original status=proposed; historical view của cùng revision có status=replaced
và replacement fields. Expand event sau compiler làm mất original snapshot.
Một canonical ID/revision không chứng minh hai projections có cùng body.

[result body:629](../../rat/engine/context_snapshot.py#L629) wrap scalar/list/
string thành `{result: ...}` nhưng receipt lại trỏ whole body. Expanded receipt
có type/value khác operation_result gốc. [artifact body:383](../../rat/engine/context_snapshot.py#L383)
drop provenance/status/created_at dù entity ghi lossless; thiếu provenance và
status là thông tin thực thi, không chỉ kích thước text.

**Sửa:** exact full-value equality trước substitution; khác nhau giữ raw slot
inline với lineage metadata riêng. Không ép historical view thành immutable
event snapshot. Scalar/list có thể nằm trong envelope nhưng pointer cần trỏ
tới **value gốc**, không envelope. Retain canonical provenance/status; mọi
intentional slim projection cần scope rõ, không claim full lossless. Dotted/
escaped field pointers phải theo canonical field semantics, không tự đổi `.`
thành `/` hay bỏ RFC escaping.

Các probes:3 non_object_result cases, quote_numeric_type, quote_whitespace,
independent_source_ref_quote, replacement_link_text, immutable_event_snapshot,
artifact_metadata; xem expected/actual trong raw JSON.

## F3 — [P1] Snapshot nhận control/proofs khác boundary và điền scope còn thiếu

[progress:844](../../rat/engine/context_snapshot.py#L844) đánh contract/journal
đã đưa vào, không yêu cầu match boundary mới. Probe `foreign_bound_contract`:
boundary conv-review/turn-2/exec-review/gen2, contract/journal conv-old/
turn-old/exec-old/gen0; validator trả valid và current progress effect=`met`.
Peer example `repair_candidate` cũng dùng contract/journal conv-example-2
trong boundary conv-example-4; schema pass không chứng minh scope đúng.

[journal entities:586](../../rat/engine/context_snapshot.py#L586) không filter
current scope trước khi dựng receipts/proof_refs. Stale gen1 PASS report nằm
trong current gen2 proof_refs dù progress matcher tự filter nó. Line656–659
điền identity/epoch thiếu bằng boundary hiện tại; probe missing_receipt_epoch
biến `None` thành2. Compiler không được làm receipt cũ/unknown trông current.

**Sửa:** mandatory contract/journal identity và known generation phải match
boundary, mismatch explicit context error. Current effects/proofs filter đúng
canonical scope; historical records chỉ ở history/raw với scope gốc. Không
rewrite None/empty receipt identities để pass. Coherence tag chỉ được dùng
khi caller copy/recheck certificate và internal control consistency đã hợp lệ;
không suy validated từ một transport schema pass.

## F4 — [P1] Semantic validator thiếu closure/unique/cycle và selection honesty

[validator:930](../../rat/engine/context_snapshot.py#L930) chỉ kiểm one-hop
value pointer +vài fields đã được schema cover; không graph/identity/namespace
validation. Probes duplicate entity (same identity, conflicting body), missing
active-note index và self-cycle đều trả valid. Self-cycle sau đó làm expander
`RecursionError`. Compile selected ID không có trong supplied artifacts ở
line869–874 âm thầm bỏ nó: selection_set=true, selected_results=[]; khác nghĩa
với user chọn rỗng.

**Sửa:** unique typed identities, exact canonical body conflicts phải error;
typed ref graph/JSON pointers có cycle detection; every index/pin/current native
binding có closure hoặc explicit unavailable reason. Không coi arbitrary old
audit ID labels là dereference refs. Missing selection không được drop; thiếu
revision phải thể hiện unresolved selection theo input contract đã thiết kế,
không bịa rev1. Expander cũng reject cycles độc lập với validation để callers
không thể tạo recursion crash.

## F5 — [P1] Canonical invalid dict bị đọc lại như model proposal và thành met

[contract decode:272](../../rat/engine/context_snapshot.py#L272) gọi
`TurnContract.from_dict` cho runtime export. Decoder đó được viết cho model
proposal, không khôi phục canonical `is_valid`/`validation_errors` nguyên trạng.
Probe canonical_invalid_dict có is_valid=false, validation_error do runtime
ghi, coverage=model_proposed; obligations giữ false nhưng progress lại met,
evidence coverage=model_proposed. Cùng dict và object input phải nhất quán.

**Sửa:** phân biệt proposal decoding với copied canonical control state.
Assessment dùng canonical state đã validate, hoặc reject ambiguous dict input;
không phục hồi validity bằng cách re-parse. Object/serialized export của invalid
contract phải cho cùng unresolved progress; giữ original errors/freeze/identity.

## F6 — [P2] Runtime schema phụ thuộc dated audit artifacts

[schema loader:52](../../rat/engine/context_snapshot.py#L52) ưu tiên hai audit
folders; module chưa có own `snapshot.schema.json`. Runtime sẽ phụ thuộc raw
review artifacts khi B2 wire, và fallback draft cũ có transport shape khác.

**Sửa:** versioned schema dưới package/runtime resource, audit chỉ giữ copies
và compare hash trong tests. Không fallback sang khác schema version/shape.
Ghi dependency trong configuration hiện có nếu cần, không tự cài thêm trong
review. Packaging/resource check không cần model hoặc full UI.

## Evidence và bước tiếp theo

- [probe_results.json](probe_results.json):21 cases, expected/actual values,
  compiler/test/core hashes; [runner](probes.py), không đổi production source.
- [focused_test_run.json](focused_test_run.json), [raw log](focused_tests.txt):
 20 passed,36 inputs unchanged trong rerun.
- Peer code/test hashes khớp manifest_finish. Core vẫn khớp fix packet trước;
  không chạy lại292 vì code core không đổi và không có core failure mới.
- Peer manifest_start được tạo sau implementation theo pasted commands; nó
  không tự chứng minh pre/post preservation. Codex đã kiểm hash independently
  với previous fixed source và bảo toàn packet hiện tại. Không sửa metadata gốc.

**Verdict: Request changes.** Anti sửa B1 theo brief kèm; Codex review lại
semantics/reproducers trước B2. Stage0/DocAI/UI/model defaults không đổi.
