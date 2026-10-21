# B: context chung để duyệt trước khi code

**Status: proposed.** [ADR-004](../../docs/adr-004-rat-context-snapshot.md)
là thiết kế chính. Chưa sửa compiler/runtime, chưa có live run B hay kết quả
AI/latency. `before` lấy shape từ exposed mock capture37 và thay IDs;
`after`, receipts và progress là ví dụ tự soạn. Xem [provenance](provenance.json).

## Ví dụ cụ thể: sửa note ở lượt5

User nói: “Ý thứ hai dài quá, sửa ngắn lại.” Model đã gọi operation ghi sửa
note và đang chuẩn bị phản hồi. Nội dung note là model paraphrase, vẫn proposed.

| Dữ liệu | Before hiện tại, adapted | After đề xuất |
| --- | --- | --- |
| Proposal | Task state ở2 blocks | `proposal.state` một lần, model_proposed |
| Nghĩa vụ đã khai | Không có contract rõ trong actor input | Canonical contract export, freeze/coverage/validation đúng runtime |
| Đã thực sự làm gì | Tool observation có note và event snapshots | Scoped receipts, một operation-result body liên kết event và note |
| Note bản cũ | Full text lặp trong history và replaces_text | Full text bản1 inline, `replaced`, link bản2; không bị ghi đè |
| Note mới | Full text lặp trong active note/result/event | Full text bản2 inline, owner lượt5, proposed; vị trí khác tham chiếu |
| Quote nguồn | Cùng quote xuất hiện nhiều places | Exact source/revision/content inline một lần; typed value refs giữ lineage |
| Phản hồi | Model tự diễn giải observation | Provisional progress: effect draft đã lưu, response đang pending |
| Protocol | Assistant call + tool result | Giữ native call/name/IDs/order; tool reply tham chiếu body đã inline |

[before.request.json](before.request.json),
[after.snapshot.json](after.snapshot.json),
[after.request.json](after.request.json) đọc được độc lập. Fields đã có semantics
khác nhau vẫn giữ riêng: expected arguments là nghĩa vụ, observed call arguments
là việc model đã gửi, note.text là nội dung lưu. Không gộp chúng theo cùng chữ.

Contract trong ví dụ chính giữ nguyên declarations của A sau thay IDs:
`expected_args` và `target_ref` vẫn null. B **không tự thêm nghĩa vụ**.
[declared_args.snapshot.json](declared_args.snapshot.json) là ví dụ giả định
riêng khi planner thật sự khai expected args và target revision. Các literal
đó giữ nguyên trong contract, không chuyển thành pointer tới note/result mới.

## Schema và ref rules

[snapshot.schema.json](snapshot.schema.json) là **transport schema**, không
output schema cho LLM. Contract invalid vẫn phải export nguyên trạng để actor
thấy validation errors. Entity bodies và receipt bodies dùng canonical exports
với projection slots có định nghĩa; schema tổng quát không thay canonical
validation hoặc reconciler. Compiler là writer duy nhất; model không tự forge
authority, receipts, freeze hay coherence bằng JSON trả về.

`$value_ref` có typed entity identity + RFC6901 pointer tới body trong cùng
request; pointer rỗng chỉ whole body. Không refs tới filesystem/URL cần fetch,
không artifact ID giả cho notebook/operation result. Không reference cycle,
duplicate identities hay pointer sai. Native operation vẫn nhận IDs/revisions
đúng input schema đã có, không nhận projection wrappers.

Chỉ decode wrappers trong **registered typed projection slots**:
note.quote/source_ref.quote, version-link text, event.snapshot, result.note/
note_event, receipt.operation_result/note_event. Không recursive decode object
người dùng hoặc unmodeled raw payload chỉ vì có key `$value_ref`. Giữ fallback
raw nguyên giá trị và trust level. Hai quotes cùng chữ từ document và user
message là hai sources khác nhau; không dùng ref của document thay user quote.

Các contract source refs/target refs vẫn native, phải kiểm identity/revision
và closure với entity table bên cạnh. Missing ref có reason rõ; source quote
trong notebook có thể giữ inline khi source body đã unavailable. Không nói đã
đọc phần chưa có, không mất committed effect, không gọi absent proof là PASS.
Mandatory control export thất bại thì explicit context build error; không quay
về actor context thiếu obligations. Không thêm summarizer/caps/ngầm truncate.

## Validation và giới hạn

Chạy offline từ root repo, dùng Python3.12 + jsonschema đang có:

```bash
PYTHONDONTWRITEBYTECODE=1 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 audit/rat_context_snapshot_design_20261014/build_examples.py
PYTHONDONTWRITEBYTECODE=1 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 audit/rat_context_snapshot_design_20261014/validate_examples.py
```

[validation.json](validation.json) kiểm shape/ref closure, full note text và
lossless expansion về [canonical_example_values.json](canonical_example_values.json),
contract không tăng yêu cầu, native tools/history giữ đúng và data không bị
nâng thành system message. Đây là validation **design artifacts**, không phải
software tests của B. `coherence=validated_copies` trong example là giả định
illustrative; Anti phải kiểm copies/cursors/pins thật ở implementation boundary.

Không coi khác biệt kích thước hai files này là đo savings: after thêm nghĩa vụ,
effect/provenance và authored artifact bodies mà baseline input thiếu. Audit B
sau code cần cùng source/decision sequence, raw payloads và phần thêm thông tin
riêng. Tokens/latency/model quality vẫn pending, Stage0 không đổi.
