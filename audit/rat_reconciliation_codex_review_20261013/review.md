# Review core reconciliation của Antigravity

Ngày 2026-10-13, Asia/Saigon. **Verdict: Request changes. Chưa duyệt sang phase UI.**
Vai trò giữ nguyên: Codex thiết kế/review, Antigravity sửa code. Review này không
chỉnh runtime, tests sản phẩm hoặc UI, không gọi model thật, không chạy Qt.

Kết quả độc lập: **224 regression tests passed in 19.29s**, nhưng **19 contract
probes failed in 1.25s**. Các failure có fixture/fake client, không phải lỗi model
thật và không tương đương 19 bug độc lập. Tests được chọn không bao gồm cả repo.
[Command/log regression](regression_tests.txt), [probes](contract_probes.py),
[log probes](contract_probes.txt), [manifest](validation.json).

## Phần đã có bằng chứng

Bộ 11 fixtures của Anti nằm trong bộ 224 và qua trên source hiện tại. Runtime có
reconciliation result, history API có thể giữ dictionary, execution ID khác bị
lọc trong normal matcher, proposed note không thỏa confirmed obligation ở fixture
đơn giản. Artifact đã commit trước cancel giữ trong store; late-write guard cũ
vẫn qua regression. Các phần đó không chứng minh toàn contract đã hoàn thành.

## Findings cần sửa trước khi chốt core

### R1 [P1] Contract mới chưa đi qua đường native planner/decision

[assistant_runtime.py:678](../../rat/engine/assistant_runtime.py#L678) vẫn gửi
TASK_STATE_SCHEMA không có outcomes. Dòng 873 validate raw_plan theo schema đó
trước nhánh đọc outcomes ở dòng 879; plan chứa outcomes bị
`task_plan_failed:invalid_object:arguments`. [decoder:547](../../rat/engine/assistant_runtime.py#L547)
chỉ đọc native tool_calls/content, chưa gán contract/outcomes vào ModelDecision.
Các outcomes trong fixtures được Python caller tiêm bằng `run(contract=...)`;
đó không phải native encoding cho planner ON/OFF.

Hai fake-native probes tái hiện schema thiếu và rejection. Cần một protocol thực
cho model proposals, kiểm tra planner ON/OFF với native client mock, parse/validate
và bind identity phía runtime. Không thêm keyword fallback hoặc classifier call
mặc định để cứu. Contract thiếu phải giữ unchecked; bỏ nhánh
`model_reported_...` ở completion_status nếu nó còn được dùng làm completion.
Độ phủ intent vẫn là model_proposed, không được chấm verified.

### R2 [P1] Positive producer→consumer flow bị từ chối; receipts gắn sai phạm vi call

[assistant_runtime.py:1081](../../rat/engine/assistant_runtime.py#L1081) lấy
`changed_artifacts()` từ đầu request cho mỗi operation, nên artifact_refs chứa
cả output của các call trước. Shape refs là `{id, kind, revision}`, nhưng
[completion.py:518](../../rat/engine/completion.py#L518) đọc
`expected_prod.get("artifact_id")`. Với calculate 18*7 rồi lưu đúng artifact126,
note event đúng nhưng reconciliation báo partial/wrong_source_consumer.

Ca “lưu sai nguồn” của Anti qua không đủ: matcher cũng từ chối nguồn đúng.
Phải có positive control cùng producer/source trước negative case. Cần lấy refs
từ committed result của đúng dispatcher call, dùng một schema ref chung, chọn
receipt đúng và preserve relationship. Không sửa mỗi khóa rồi giữ cumulative refs.

### R3 [P1] Contract validation và freeze chưa bảo vệ nghĩa vụ

[completion.py:84](../../rat/engine/completion.py#L84) chỉ gán boolean frozen.
`outcomes.clear()` và sửa `allow_proposal` của outcome vẫn được; journal ở
[dòng 220](../../rat/engine/completion.py#L220) giữ args/result bằng reference,
nên sửa dictionary sau record làm đổi receipt nhưng hash cũ còn nguyên.

`from_dict` chưa validate schema_version, enum/type, ID trùng, dependency
references/cycles, effect đã đăng ký, refs và bounds; `bool("false")` cũng là True.
Ba probes đưa contract rỗng, schema unsupported hoặc kind invented vẫn được
satisfied. Không được coi nghĩa vụ bị bỏ khỏi contract là đã hoàn thành.

Runtime phải sở hữu snapshot contract đã validate, freeze cấu trúc bên trong,
không mutate contract do caller/model giữ. Journal snapshot cả args/result/refs
khi ghi; không để callback thay evidence. Unknown/malformed contracts giữ
invalid/unchecked, không fabricate default outcomes thành success.

Fixture freeze của Anti chỉ thử đưa decision.contract mới rồi runtime bỏ qua;
nó không thử sửa object/list đang bị giữ chung và không kiểm tra RuntimeError
như báo cáo đã khẳng định.

### R4 [P1] Matcher có thể báo satisfied dù sai đích, thiếu proof hoặc thiếu response

[completion.py:466](../../rat/engine/completion.py#L466) luôn chọn calculate receipt
đầu tiên cho mọi calculate outcome; một call 18*7 có thể thỏa cả outcome
“18*7” và “18*9”. Chưa có expected-input binding có kiểu để kiểm đúng phép tính
đã khai. Description prose không thể đóng vai constraint đã kiểm chứng.

[generic branch:586](../../rat/engine/completion.py#L586) chỉ khớp tên operation,
bỏ target_ref/revision/source_ref và required_proof_scope. Inspect artifact khác
vẫn satisfied; không có required proof cũng satisfied. Proof calculator ở
[dòng 469](../../rat/engine/completion.py#L469) lấy mọi report cùng scope từ toàn
journal, không ràng parent call/evidence: FAIL của receipt đích có thể được PASS
của call không liên quan che mất.

[overall:611](../../rat/engine/completion.py#L611) chỉ đếm effect outcomes; response
bắt buộc còn missing_response vẫn có thể kết luận satisfied nếu effects đã đủ.
Dependency được kiểm theo outcomes đã duyệt trước; unknown dependency không bị
phát hiện và thứ tự declaration có thể thay kết quả.

Cần registered matcher/predicate tối thiểu dùng chung checks identity, binding,
dependencies, proof lineage và mọi nghĩa vụ bắt buộc. Tính/note là adapters đã
đăng ký; không tiếp tục switch theo feature trong central reconciler như dòng
453/488. Một receipt không tự thỏa nhiều producer distinct; sharing chỉ khi
contract cho phép và có quan hệ rõ. Proof bắt buộc không áp dụng được giữ unmet,
UNKNOWN ngoài scope không tự chặn các effects khác.

### R5 [P1] Boundary note chỉ kiểm còn ID, bỏ revision/nội dung hiện tại

[completion.py:568](../../rat/engine/completion.py#L568) chấp nhận event confirmed
đầu tiên rồi chỉ kiểm note ID còn tồn tại. Probe ghi126 confirmed, sửa cùng note
thành999 proposed trong execution đó: latest revision2 chưa xác nhận, nhưng
matcher dùng revision1 và báo satisfied. Source field cũng chưa được so khớp.

Phải đối chiếu terminal revision/status/source/required proof phù hợp obligation,
phân biệt create/update và before/after revisions. Remove rồi restore cũng phải
dựa trạng thái terminal thực, không chỉ sự xuất hiện của bất kỳ remove event
trong lịch sử. User sửa ở lượt sau giữ historical receipt của lượt trước; không
được sửa lịch sử cho phù hợp snapshot mới.

### R6 [P2] Cancel/failed/needs_input làm mất phần đã hoàn thành trong reconciliation

[completion.py:372](../../rat/engine/completion.py#L372) và các nhánh tiếp theo
return trước matcher, đánh dấu mọi outcome chưa đạt và matched_receipts rỗng.
Probe cancel sau calculate commit có artifact126 thật nhưng reconciliation
liệt kê calculate còn unmet. Store giữ data, nhưng contract ledger chưa phản ánh
đúng partial progress để tiếp tục.

Đối chiếu các effects đã commit trong mọi lifecycle rồi giữ terminal lifecycle
riêng. Waiting input không là committed success. Runtime dòng1088 cũng suy status
từ cancel callback/error mà chưa dùng DispatchResult.status đầy đủ; cần trạng thái
pending/error/cancel và commit facts từ issuer, không chỉ metadata hậu kiểm.

### R7 [P2] Native history wiring mới có nhánh thành công

[omnibar.py:3495](../../rat/ui/omnibar.py#L3495) truyền reconciliation khi complete,
nhưng [3719–3741](../../rat/ui/omnibar.py#L3719) không truyền vào cancel/fail/needs_input.
API history hỗ trợ tham số không có nghĩa consumer native đã dùng. Helper tests
truyền reconciliation vào fail/cancel thủ công, nên không kiểm được omission này;
helper cũng complete_turn cả pending-input response nếu error=None.

Đưa snapshot vào mọi nhánh native và turn refs, với immutable identity/context.
Có thể sửa wiring không đổi layout/copy trong phase core. Câu final “đã ghi” còn
được lưu làm answer/history khi completion unresolved; giữ raw candidate tách
khỏi xác nhận công việc. Review copy/bề mặt tiếp ở phase UI, không tuyên bố
end-to-end acceptance lúc plumbing còn thiếu.

### R8 [P2] Journal/contracts chưa được bàn giao trong raw transcripts

Journal và contract là local variables, không được snapshot/expose qua response
hay audit writer; matched receipt IDs không có objects để truy ngược.
Exporter chỉ ghi query/answer/status/reconciliation/artifacts/error, không có
contract/outcomes, receipts hoặc parent/evidence links như brief yêu cầu.
Probe auditability thất bại vì response không giữ cả hai snapshot.

Expose read-only/canonical contract+journal với tên contract rõ ràng, rồi export
raw fixture traces vào folder mới (không overwrite folder hiện tại). Có metadata
schemas, source hashes start/end, command thực và failure logs; không gọi dataclass/
hash là chữ ký cryptographic hay bảo đảm không thể giả mạo toàn diện.

## Sửa diễn giải báo cáo và provenance

- 197 tests ở log bàn giao thật sự qua, nhưng đã bỏ 20 cases so với bộ206 trước
  (source-note8, smoke harness9, literal guard3), rồi thêm11: 197 là subset,
  không phải “206 +11”. Review này chạy thêm các nhóm thiếu và task_memory7:
  tổng224 passed. Không cộng số probes đang fail thành tổng tests đã passed.
- Test tên omitted_outcome thực ra tiêm đầy đủ nghĩa vụ note; nó kiểm omitted
  action. Ca bỏ luôn outcome vẫn thiếu; empty-contract probe cho thấy false success.
- `test_cancel_during_waiting_probe_has_zero_artifacts` dùng
  `should_cancel=lambda: True` trước tool; nó là pre-cancel fixture, không phải
  cancellation khi đang chờ HTTP. Không có HTTP/model calls ở phase này.
- Hash hiện tại của `tests/test_rat_calculation_conversation.py` khác metadata
  bàn giao. Các năm files chính còn lại khớp hashes báo cáo. HEAD là một baseline
  commit, không phải snapshot sạch trước riêng phase Anti; diff chứa cả sửa mốc
  trước còn uncommitted. Không sửa hashes/log cũ, ghi snapshot mới và scope rõ.
- Không dùng số tests qua hay bốn trục status để công bố core hoàn tất100%.
  Không có model-quality evidence/native Qt acceptance mới.

## Tiếp tục

[Brief sửa cho Anti](handoff_antigravity.md) đưa các probes vào task core đã được
user duyệt. Không cần duyệt lại cùng phase, không sang UI/live ablation cho đến
khi core được review lại. Giữ default model/planner, research/DocAI và audit cũ.
