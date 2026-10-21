# Codex review: Core reconciliation Round 2

Ngày 2026-10-13, Asia/Saigon. **Verdict: Request changes; chưa duyệt phase UI.**
Vai trò: Codex thiết kế/review, Anti triển khai. Review này chỉ thêm probes và
tài liệu audit, không sửa runtime hoặc tests sản phẩm, không gọi model thật/Qt.

## Kết quả đã xác nhận

**19 probes cũ + 224 regression tests = 243 passed in 11.97s** khi chạy lại.
Các sửa reference key/call-specific artifacts, shallow freeze và schema outcome
trong initial planner đã xử lý được các ca đã tái hiện trước đó. Raw transcripts
Round 2 có contract và journal trong cả 13 turns của 11 fixtures. Wiring fail/
cancel/needs_input của omnibar hiện có truyền reconciliation.

Các kết quả này có tiến bộ thật về phần mềm. Chúng không chứng minh mọi điều kiện
R1–R8 đã được đáp ứng. Probes bổ sung cho các yêu cầu còn thiếu trong cùng scope:
**14 cases chạy qua hai lệnh, 13 failed / 1 passed**.
[Log243](regression_and_original_probes.txt),
[probes bổ sung](remaining_contract_probes.py),
[log failures](remaining_contract_probes.txt), [manifest](validation.json).
Producer-first positive control qua; cùng actions/receipts nhưng consumer-first
không qua. Không gọi 13 failures là 13 bug/model-quality samples độc lập.

## Findings

### R1 [P1] Proof gates thiếu cả positive linkage và required-note check

`ExecutionJournal.record_verification` lưu parent receipt IDs ở envelope;
[completion.py:638](../../rat/engine/completion.py#L638) chỉ lấy payload
`verification_report`. [Matcher:439](../../rat/engine/completion.py#L439) lại tìm
operation_receipt_id/parent_receipt_ids bên trong payload. Report do runtime phát
không có những keys đó; evidence IDs là request/step/hash, không phải artifact ID.
Phép tính18*7 có PASS thật, proof envelope trỏ đúng calculation receipt, nhưng
outcome yêu cầu calculation_execution vẫn unresolved. Đây là positive control
còn thiếu; negative “proof từ call khác” qua chưa chứng minh proof đúng được nhận.

[_match_note](../../rat/engine/completion.py#L477) trong rewrite bỏ hẳn việc kiểm
required_proof_scope và không kiểm required_authority. Probe ghi scalar126 theo
artifact sample, confirmed copy nhưng không có source_verification; nghĩa vụ
bắt buộc source_calculation_note vẫn satisfied.

Cần resolver dùng verification envelopes đã lọc đúng request/identity, parent
call/evidence/revision/field và scope; cả proof đúng lẫn proof sai/thiếu phải có
controls. Notes kiểm proof/authority từ phiên bản terminal đúng. Exact copy có
thể đủ nếu obligation chỉ yêu cầu observed copy, nhưng không được tự đáp ứng
một proof scope đã khai mà chưa kiểm.

### R2 [P1] Dùng substring trong prose để nhận phép tính sai

[completion.py:426](../../rat/engine/completion.py#L426) xóa khoảng trắng rồi dùng
`expr_clean in desc_clean` hoặc chiều ngược lại. Outcome description18*7,
operation118*7 tạo826 vẫn được satisfied. Đây là heuristic mà review R4 trước
đã yêu cầu tránh; arithmetic checker chỉ chứng minh phép tính đã gọi đúng, không
chứng minh đã thực hiện expression mà contract yêu cầu.

Bổ sung binding input có kiểu, ví dụ expected_args được schema operation kiểm
tra, thay vì suy constraint từ description. Calculator adapter có thể canonicalize
expression theo parser số học đã hỗ trợ rồi đối chiếu chính xác. Description là
text cho người/model, không là authority hình thức. Không parse keyword để chọn
hành động hoặc cứu bằng một tool call tự phát.

### R3 [P1] Terminal note đúng trạng thái nhưng sai nguồn vẫn satisfied

[completion.py:490](../../rat/engine/completion.py#L490) lấy source_ref từ event
cũ, còn terminal_note chỉ dùng để kiểm confirmed/proposed/removed. Probe lưu126
confirmed rồi sửa cùng ID sang162 confirmed từ nguồn khác trong execution đó;
outcome yêu cầu nguồn126 vẫn satisfied bằng receipt revision1.

Phải gắn receipt/revision với trạng thái terminal phù hợp toàn bộ source/ref/
field/proof/authority/text contract, không chỉ boolean confirmed. Đúng revision/
event kind cho update; expected_revision không được coi before_revision=None
là khớp. Historical outcome ở lượt cũ vẫn bất biến khi user sửa ở lượt mới.

### R4 [P1] Planner OFF nhận metadata nhưng còn leak JSON và ném exception

[assistant_runtime.py:576](../../rat/engine/assistant_runtime.py#L576) đọc
outcomes/contract từ content JSON nhưng final_answer vẫn giữ toàn bộ JSON.
Mock-native envelope có answer “Xin chào” trả nguyên outcomes/answer JSON ra
AgentResponse.answer, rồi có thể vào UI/history.

`outcomes=["malformed"]` ném AttributeError ở TurnContract.__post_init__;
`contract={"frozen":true,...}` ném RuntimeError khi dataclass gán is_valid.
[run:974](../../rat/engine/assistant_runtime.py#L974) decode/bind ngoài error boundary
nên không trả AgentResponse invalid/failed theo contract. Model output lỗi phải là
failure có log, không exception làm đứt lượt.

Cần một protocol và schema rõ cho native ON/OFF, giữ raw envelope ở audit, tách
answer khỏi metadata, validate types/refs/bounds trước constructors và effects,
bind identity/freeze/validity phía runtime. Không tin flags/IDs do model tự khai.
Mock phải kiểm cả payload hợp lệ và malformed qua decoder thực; chưa cần live run.

[response:858](../../rat/engine/assistant_runtime.py#L858) vẫn có fallback
model_reported_in_progress/completed khi plan thiếu outcomes, trái mô tả báo cáo
đã bỏ fallback. Probe cho completion_status=model_reported_in_progress trong khi
reconciliation=unchecked. Dùng một completion truth; giữ model task report ở
task_state riêng. Một legacy assertion ở tests/test_rat_task_memory.py:31 cần
migration có giải thích, vẫn kiểm task_state và provenance/unchecked, không xóa
coverage để chỉ làm xanh suite.

### R5 [P1] Dependency order/cycle chưa được xử lý

Comment ở [completion.py:713](../../rat/engine/completion.py#L713) nói topological,
nhưng code vẫn duyệt list gốc. Đặt consumer trước producer làm correct source flow
partial; producer trước thì satisfied với cùng operation sequence. Cycle A↔B
có hai generic receipts lại satisfied vì chỉ kiểm dependencies đã xuất hiện
trong unmet_outcomes. `satisfied_outcome_ids` chưa dùng để bắt phụ thuộc thực sự.

Validate DAG, refs tới producer và IDs tại boundary; sort theo dependency order
để matcher không lệ thuộc thứ tự model khai. Consumer chỉ xét sau khi producer
đã thỏa và có artifact binding hợp lệ. Cycle/unknown ref giữ invalid trước effects.

### R6 [P2] Freeze mới bảo vệ attribute, chưa bảo vệ nested refs

[completion.py:52](../../rat/engine/completion.py#L52) khóa setter, nhưng
source_ref.clear(), target_ref.clear(), dependency_ids.clear() vẫn đổi các nghĩa
vụ sau freeze. Probes dùng dependency thật tới producer để chứng minh có thể
xóa constraint. TurnContract.frozen cũng có thể được gán False theo setter hiện có.

Dùng runtime-owned immutable snapshot/serialized canonical structure hoặc
recursive freezing cho nested values. Đừng chỉ thay list outcomes bằng tuple.
Response currently expose object contract/journal; consumer không được đổi truth
của snapshot bằng mutable refs. Constructors không tin cờ frozen từ model.

## Provenance và điểm còn cần giữ trong handoff

- Hash của sáu files runtime/tests khớp manifest Round2; exporter hiện khác
  workspace_source_sha256_finish đã báo. Ghi discrepancy trong validation,
  không sửa manifest/log cũ để khớp. Metadata “start” là reviewed_source của
  phiên bản trước, chưa là snapshot ngay trước test/model run.
- Exporter vẫn dùng exist_ok=True và ghi đè fixture_transcripts.json ở target.
  Không chạy lại vào folder audit cũ; thêm guard fresh directory trước fixtures/
  writes để đáp ứng kỷ luật raw artifacts. Đây là source inspection, chưa chạy
  destructive probe vào audit có sẵn.
- Matchers vẫn được chọn bằng central if theo calculate/record_work_note
  (dòng759), chưa là registered adapter như contract chung đã yêu cầu.
  Đặt special input/proof matching ở operation adapters; shared reconciler làm
  identity/dependency/completion, không thêm nhánh feature/regex vào runtime.
- Global scoped_quality hiện gộp mọi report lịch sử; giữ reports theo scope và
  candidate/evidence, không tuyên bố scalar đó chứng minh toàn answer/workflow.
- Không có live/native acceptance mới. Scope của phần mềm không thay đổi Stage0,
  DocAI, research claims hay default model/planner.

[Brief sửa tiếp cho Anti](handoff_antigravity.md) thu hẹp vào các gates/protocol còn
thiếu trong contract đã duyệt. Không cần duyệt lại phase core; chưa mở UI/live
ablation. Audit cũ và source production được giữ nguyên trong lượt review này.
