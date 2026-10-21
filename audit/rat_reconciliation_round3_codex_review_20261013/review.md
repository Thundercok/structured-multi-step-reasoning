# Codex review — core package Round 3 và đề xuất context

**Verdict: request changes.** Các lỗi đã báo ở Round 2 đã được sửa: chạy lại
33 probes cũ và selected regression suite đạt **260 passed**. Tuy vậy còn lỗi
ở serialization, matching nguồn/input và proof bắt buộc. Chưa chốt core để
chuyển sang triển khai snapshot context hay duyệt UI.

Đây là review offline trên source khớp bàn giao. Không sửa runtime/tests sản
phẩm, không chạy model thật, không mở Qt/native, không đổi defaults hay gate
nghiên cứu. Các lỗi dưới đây có fixtures tái hiện, không phải quan sát chất
lượng một model live.

## Đối chiếu bàn giao

- Cả **8/8 SHA256** trong `source_hashes.json` của Anti khớp source đọc đầu
  review; snapshot thêm 6 dependencies/docs để ghi phạm vi review.
- Chạy lại 19 Round-1 probes + 14 Round-2 probes + 227 selected regressions
  trong một command: **260 passed in 18.21s**, exit code 0. Không skip/xfail.
- Export lại 11 fixtures sang thư mục mới: 11 đều đạt assertions. Lần thứ hai
  bị `FileExistsError` và hash transcript không đổi. Guard exporter đã sửa.
- 17 boundary probes bổ sung: **11 failed, 6 passed in 0.67s**. Có các positive
  controls cho biểu thức cùng AST, consumer đúng nguồn, note đúng text, proof
  PASS và proof đúng generation. Không chỉ thử toàn ca phải bị chặn.
- Probe ban đầu ép empty contract phải invalid/unresolved đã được điều chỉnh:
  ADR cho phép unchecked khi chưa xác lập coverage. Log đầu giữ nguyên trong
  `boundary_probes_initial.txt`; empty contract không báo satisfied là control
  hợp lệ. Kết luận cuối không tính điều này thành lỗi.

## Findings

### R1 — [P1] Native decoder vẫn cho source_ref sai kiểu đi tới matcher rồi crash

`OutcomeSpec.__post_init__` chỉ kiểm kind; `from_dict` copy source/target/args
mà không validate hình dạng. Payload native có `source_ref="not-an-object"`
vẫn thành contract hợp lệ. Sau khi `record_work_note` thực sự commit, final
reconciliation gọi `.get()` trên string ở
[completion.py:685](../../rat/engine/completion.py#L685) và ném `AttributeError`
ra khỏi `AssistantRuntime.run`.

Probe `test_native_malformed_source_reference_returns_invalid_without_crashing`
dùng client mock theo đúng đường `_call_model`, không chỉ chèn contract trực
tiếp. Cần validator schema/type chung cho mọi điểm vào contract: planner,
decision, injected continuation. Invalid metadata trả reconciliation invalid
có reason; vẫn giữ effects đã commit. Không chỉ bọc decoder ban đầu rồi giả
định nested fields đã đúng. Không chuyển receipt matcher exception thành một
success response.

### R2 — [P1] Deep freeze phá JSON export và matching array của thao tác đúng

[completion.py:84](../../rat/engine/completion.py#L84) chỉ chuyển mappingproxy
tầng ngoài thành dict rồi `deepcopy`. Với expected args hợp lệ
`{"text":"126","source_result":{"artifact_id":"a","revision":1,"field":"result"}}`,
mappingproxy tầng trong gây `TypeError: cannot pickle 'mappingproxy' object`
khi `turn_contract.to_dict()`. Đây là cấu trúc source_result đang được dùng,
không phải object Python tùy ý.

Freeze cũng đổi JSON array thành tuple. Generic matcher tại
[completion.py:776](../../rat/engine/completion.py#L776) so list args thật với
tuple expected nên `select_work_results(artifact_ids=["a"])` đã commit đúng
vẫn bị unresolved. Tái hiện qua runtime và notebook visible IDs thật trong
memory, không chỉ so một cặp list/tuple riêng lẻ.

Giữ deep immutability nhưng thêm recursive export/thaw về JSON values và so
sánh theo JSON semantics cho objects/arrays. History/export/transport phải
serialize được toàn contract. Tránh bỏ freeze để qua probes hoặc ép các
operation thực thi dùng immutable internal containers.

### R3 — [P1] Typed expected_args chưa được thực thi nhất quán

Calculator tại [completion.py:573](../../rat/engine/completion.py#L573) chỉ so
giá trị evaluate, không canonical AST/argument identity như bàn giao nói.
Contract yêu cầu expression `18 * 7`; operation chạy `63 * 2`; cả hai ra 126
nên outcome bị chấm satisfied. PASS calculation proof chỉ chứng minh phép tính
đã chạy, không chứng minh nó là expression đã khai. Positive control
`(18 * 7)` vẫn satisfied đúng.

`RecordWorkNoteAdapter` bỏ qua expected_args hoàn toàn. Contract khai
`expected_args={"text":"126"}` nhưng note thực lưu và confirmed `162` vẫn
satisfied. Probe cùng một flow khi expected text là `162` đạt đúng, cho thấy
cần ràng buộc input chứ không cần chặn mọi lưu note.

Chia sẻ input matcher cho các adapters; calculator chỉ thêm canonical expression
theo quy tắc công bố rõ. Note kiểm args của operation receipt thật liên kết
event, rồi đối chiếu terminal note/source/revision như hiện tại. Không suy
expression bằng prose nếu đã có typed expected_args. Numeric equality và
operation identity là hai scope khác nhau.

### R4 — [P1] Generic consumer bỏ qua source_ref của producer

[GenericOperationAdapter](../../rat/engine/completion.py#L755) kiểm expected
args/target/proof nhưng không kiểm source_ref. Runtime fixture tính 126 từ
`18 * 7`, rồi `inspect_artifact` đọc artifact `unrelated` chứa 999. Consumer
đã khai `source_ref={"producer_outcome_id":"calc"}` và dependency `calc` vẫn
được chấm satisfied. Đổi inspection sang đúng artifact producer cũng satisfied
đúng, là positive control.

DAG order đã được sửa, nhưng dependency có nghĩa producer hoàn tất chưa đủ để
chứng minh consumer dùng output producer. Cần common binding cho source
identity/revision/field bằng contract metadata/adapter đã đăng ký. Khi một
operation chưa hỗ trợ source requirement đó, đánh unmet/unsupported; không
âm thầm bỏ constraint rồi satisfied. Không thêm keyword route hay nhánh theo
feature trong reconciler để sửa một fixture.

### R5 — [P1] Response bỏ qua required proof; proof matcher thiếu generation isolation

Nhánh response tại [completion.py:976](../../rat/engine/completion.py#L976)
chỉ cần final_answer nonempty. Với required scope `literal_arithmetic_answer`,
cả thiếu proof, proof UNKNOWN và proof FAIL đều cho completion satisfied.
`scoped_quality=FAIL` riêng không thay việc nghĩa vụ proof bắt buộc phải unmet.
Control PASS satisfied. Câu hội thoại không khai proof tiếp tục không cần tool.

Ngoài ra `verif_envelopes` tại
[completion.py:855](../../rat/engine/completion.py#L855) không filter generation
như operation receipts. Proof PASS generation 1 được liên kết vào operation
generation 2 trong journal fixture vẫn thỏa contract generation 2. Control
proof generation 2 satisfied. Đây là robustness probe của journal matching;
chưa quan sát late proof trong live run.

Cần common proof selection theo trusted scope, authority, identity/generation,
evidence và revision; áp dụng khi một outcome thật sự đòi proof, gồm response.
Proof của final candidate phải liên kết candidate đang trả, không bất kỳ PASS
nào cùng scope. Không tạo verifier giả cho prose chưa có checker.

### R6 — [P2] Planner schema chưa giới thiệu trường typed expected_args

OutcomeSpec đã có expected_args nhưng `_plan_task` outcome schema tại
[assistant_runtime.py:708](../../rat/engine/assistant_runtime.py#L708) không có
field này. Probe đọc `response_format` thực truyền cho native client mock báo
`KeyError`. Nested schema chưa đóng additionalProperties, nên không kết luận
model không thể sinh field; vấn đề là đường model-facing không công bố hợp
đồng typed input mới. Cần dùng schema/decoder chung và kiểm native ON/OFF;
không coi tests chèn expected_args bằng Python là validation cho model path.

## Nhận xét về đề xuất A/B/C/D

Hướng chung phù hợp với yêu cầu một chat liền mạch và một core; chưa có implementation
context mới trong bàn giao. Gói A là audit độc lập hợp lý sau khi core chốt.

Ba điều cần sửa trong design trước khi B/C/D đi tiếp:

1. `inspect_artifact` chỉ đọc ArtifactStore. Notes/versions nằm trong
   WorkNotebook; chưa có model operation đọc note revision. Không giảm
   historical notes thành refs-only rồi dựa vào `inspect_artifact` để đọc bản
   cũ. Giữ payload cần thiết cho lookback cho tới khi có đường resolve typed
   note reference thật, hoặc thiết kế resolver riêng trong registry và review.
2. B cần giữ continuity của câu hỏi và dữ liệu đã đọc, không chỉ task/note/ref
   lists. Follow-up “sao cộng 1” cần array, mục tiêu và explanation/source
   liên quan. Tách model proposal khỏi trusted runtime obligations/receipts;
   nguồn đọc và prose cũ là dữ liệu, không được nâng thành system instruction.
3. C cần đo tính ổn định của registry order hiện có trước. Alphabetical sort
   là một phương án, không tự động là fix hay evidence cache tăng. A/mock
   chỉ cho character/byte breakdown; token/cache/latency cần live budget sau.
   D vẫn là spec có gate riêng; outcome phải freeze trước side effect, và
   không tăng số calls khi native protocol bị fallback mà không ghi rõ.

## Việc tiếp theo

Anti sửa R1–R6 bằng schema/value/reference/proof helpers dùng chung, giữ adapters
cho semantics được hỗ trợ. Sau khi qua probes cũ và mới, đóng gói source hashes,
diff, logs và mock transcripts vào một folder mới; Codex review core trước A.
Không cần thêm feature, UI, inference, planner/default change hay DocAI cho việc
khắc phục này. NCKH Stage 0 và giới hạn evidence không đổi.

Artifacts: [probes](boundary_probes.py), [log](boundary_probes.txt),
[regression log](regression_and_previous_probes.txt), [export guard check](exporter_check.json),
[handoff](handoff_antigravity.md), [validation](validation.json).
