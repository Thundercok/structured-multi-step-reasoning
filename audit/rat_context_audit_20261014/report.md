# Audit A: context RAT trên core đã sửa

Audit cho thấy context vừa có phần lặp đáng giảm, vừa thiếu một phần nên bổ sung:
**actor không được gửi outcomes đã khai như một block nghĩa vụ runtime rõ ràng**.
Snapshot B cần giải quyết cả hai, để model biết công việc còn phải làm trong
khi nhận ít copies của cùng dữ liệu hơn.

Không sửa core/UI hoặc prompt trong lượt này. Thêm script audit và tests cho
chính audit; **0 live inference**, không personal indexing hay native window.

## Phạm vi đã chạy

- 11 core fixtures hiện có, đi qua native message builder và decoder bằng
  client mock; hai fixtures chỉ đối chiếu journal/cancel trước cổng model nên
  không tạo model-port request. Tất cả assertions của fixtures đạt.
- Luồng C01 bảy lượt từ conversation pack: tìm → đọc → hỏi tiếp → ghi draft →
  sửa → xem bản cũ → hỏi tiếp. Dùng hai Markdown do ta tự soạn và DB mock chỉ
  chứa chúng. Các tool/notes/artifacts/history vẫn thực thi trong memory.
- **12 cases, 20 runtime turns, 41 mock port calls:** 7 planner và 34 actor.
  Main C01 có 18 calls: 7 planner và 11 actor. Raw responses do fixture cung cấp,
  gồm câu trả lời mẫu; không phải model chọn đúng hoặc chất lượng AI đã đo.
- Script block real `SLMEngine.chat_with_meta`, urllib HTTP và socket connection
  helper. Client capture là mock riêng. Runtime classes được patch tạm trong
  collection rồi khôi phục; source không đổi.
- Clock runtime cố định cho fixture. UUID/check timing/event timestamp vẫn có
  thể khác khi collect lại; số ký tự bên dưới gắn với captures đã lưu. Analyzer
  tái tính chính xác từ captures đó, không replay latency hay sinh model mới.

Các branch còn lại của pack (đọc lỗi, note retry/ambiguity và source dài) chưa
được capture đầy đủ ở A; một số lifecycle failures được core fixtures phủ.
Không chấm đã nghiệm thu cả sáu scenarios, full/compact hay personality.

## Kích thước tại cổng model

Đo canonical compact JSON UTF-8 của **arguments runtime truyền vào client**:
messages, tools và response_format. Chưa phải HTTP wire serialization hoặc
backend chat template; không chuyển chars/bytes thành token/cost.

| Đại lượng | Planner | Actor |
| --- | ---: | ---: |
| Mock port calls | 7 | 34 |
| Tổng canonical JSON characters | 81.147 | 557.473 |
| Tổng canonical JSON UTF-8 bytes | 89.926 | 570.241 |
| Tools gửi mỗi call | 0 | 15 |
| Tools JSON characters mỗi actor call | — | 8.732 |
| Tools / tổng actor JSON characters | — | 53,26% |
| Unique first-system canonical hashes | 1 | 1 |
| Actor calls có hai task-state objects giống nhau | — | 11 |

Empty tools list vẫn chiếm hai ký tự JSON trong mỗi planner request. Components
và phần punctuation/key overhead cộng đúng total ở cả chars và bytes của từng
call. Prompt/completion tokens, cache và server duration giữ `null`. Counter 0
trả vào runtime chỉ là placeholder cho fixture bookkeeping, không phải cost.

### Main C01

| Lượt | Planner chars | First actor chars | Last actor chars |
| --- | ---: | ---: | ---: |
| 1 — Tìm | 2.271 | 12.509 | 13.666 |
| 2 — Đọc | 4.583 | 15.313 | 16.704 |
| 3 — Hỏi tiếp | 6.756 | 17.745 | 17.745 |
| 4 — Ghi draft | 8.150 | 19.216 | 24.903 |
| 5 — Sửa | 14.611 | 25.840 | 32.171 |
| 6 — Xem bản cũ | 21.647 | 33.051 | 33.051 |
| 7 — Hỏi tiếp | 23.129 | 34.599 | 34.599 |

Từ first actor turn 1 tới last actor turn 7 tăng khoảng **2,77 lần** trong một
trajectory fixture. Không suy ra đây là mức tăng token, latency hoặc pattern
tổng quát của các cuộc hội thoại thật.

## Những gì đã xác định

### 1. Actor chưa nhận nghĩa vụ đã khai thành context riêng

Planner trong cả bảy lượt trả outcomes; runtime đã bind chúng vào contract
và reconciler cuối lượt. Nhưng cả 11 actor requests của C01 không chứa
`outcome_id` trong messages. Source `_native_messages` cũng không nhận
turn_contract/journal. `_plan_task` outcomes được tách khỏi task_state, còn
trajectory initial-plan chỉ gửi task_state/assessment/phase.

Điều này không chứng minh model sẽ thất bại: C01 thành công do quyết định và
wording được script cung cấp. Nó cho thấy actor thiếu explicit current
obligations/source/proof requirements để đối chiếu quyết định của mình. Phần
unmet outcomes được tính ở boundary response, chưa là feedback loop của actor.

**B cần:** block runtime obligations có outcome ID, kind, typed args/refs,
dependencies và proof yêu cầu; block committed effects/known unresolved state
riêng với model proposal. Không nâng model intent coverage thành verified.

### 2. Task proposal có hai representation cùng giá trị

Ở 11/11 C01 actor calls, task_state xuất hiện cả trong message
`Previous model-authored task state` và initial-plan trajectory observation.
Raw JSON value giống nhau; phần assessment/phase ở wrapper vẫn có ý nghĩa
provenance. Có thể giữ một proposal value và tham chiếu từ planning event.
Không coi cả message là thừa hay đổi proposal thành execution receipt.

### 3. Note/source snapshots bị phát lại qua nhiều đường

Đoạn source content đã strip có **339 chars**, được copy tại 12 locations trong
actor request cuối C01: active note quote/source_ref.quote, historical version
quote/source_ref.quote và hai `previous_sources` note results; mỗi result lại
giữ note + note_event.snapshot với quote ở hai nơi.

`observed_sources` thêm fallback result của `record_work_note` vào sources, nên
note mutation payload cũ tiếp tục đi qua `previous_sources`. Notebook đã gửi
active/historical versions đồng thời. Đây là giao nhau giữa receipt/event,
current notebook state và source context; không cần coi chúng là ba nguồn
truth khác nhau.

**B cần:** mỗi entity/revision có một representation body, event/effect/source
links tham chiếu nó với typed provenance. Store/journal giữ full payload; model
snapshot tránh phát lại toàn event snapshot như một nguồn mới. Áp dụng bằng
metadata/roles chung trong kernel, không route riêng theo tên feature.

### 4. Giống wording không đồng nghĩa cùng authority

History chứa user request/assistant explanation; turn refs thêm IDs, lifecycle
và reconciliation. Note text là proposed, source quote là content đã đọc, bản
cũ là immutable historical version. Analyzer ghi vị trí của repeated strings,
luôn để `removal_safe_without_provenance_review=false`.

Giữ current query, constraints (“chưa đưa code”), dữ liệu mảng/bước giải thích,
source read boundary, note confirmation, ID/revision/owner và replacement links.
Một scalar text giống nhau có thể được liên kết chung nhưng các authority tags
không được nhập làm một.

### 5. Static prefix hiện đã ổn định ở captures

First actor system và tools canonical hashes đều chỉ có một giá trị trong 34
calls. Registry có 15 operations cùng thứ tự trong các requests đã capture.
Time/member nằm ở runtime-context message riêng. Không có bằng chứng cần sort
registry để sửa churn trong tập này.

Đây là structural opportunity cho prefix reuse; mock không có backend cache.
Không bỏ tools hay tuyên bố speed-up từ hash. Trong A chưa capture verified
repair/finish-only channel; C cần kiểm riêng khi thiết kế và khi duyệt live.

## Thiết kế B nên dựa trên kết quả này

| Block snapshot | Authority | Body cần giữ |
| --- | --- | --- |
| Current request + continuity | User request / prior conversational data | Query mới, constraints, array/example/source context liên quan |
| Work proposal | Model proposed, may be stale | Một task state và provenance tới planning event |
| Runtime obligations | Runtime-bound declaration, intent still model_proposed | Frozen outcomes/refs/proof scope và dependency graph |
| Observed effects | Committed journal/store facts | Receipt IDs, status, versions, known failures/pending/cancel; bodies qua entity refs |
| Entities/versions | Typed source + authority | Artifact context, active note, historical note, source payload cần thiết |

Snapshot là cách gửi context, không là kho dữ liệu thứ hai. Reuse store/notebook/
journal và immutable JSON helpers hiện có. Model vẫn chọn thao tác; context
builder không dùng câu hỏi để route feature.

Điểm chặn cụ thể: `inspect_artifact` chỉ đọc ArtifactStore, chưa đọc note version
trong WorkNotebook. **Không rút lịch sử note xuống refs-only** trước khi có
typed resolver thật. Có thể dedupe quote/events trước, vẫn giữ text bản cũ để
lookback. Source dài/cut boundary cũng phải giữ; chưa tích hợp DocAI.

Gói D gộp proposal/action vẫn là design riêng, chưa bật. A không chứng minh gộp
call sẽ nhanh hơn, không thay default model/planner hay learned policy/Stage 0.

## Kiểm chứng và tái lập

6 audit tests qua: additive multibyte accounting, phân biệt task-state values,
không xóa overlap khác authority, fresh-directory guard và phục hồi class
methods sau mock capture. Không cần chạy lại 292 core tests vì core không đổi.

Tại repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m scripts.audit_rat_context --output /tmp/rat_context_audit_NEW_DIRECTORY
PYTHONDONTWRITEBYTECODE=1 python -m audit.rat_context_audit_20261014.analyze /tmp/rat_context_analysis_NEW_FILE.json
```

Lệnh thứ hai chỉ recompute captures đã lưu trong audit này. Output phải chưa
tồn tại. Raw fixture data đã lộ; không dùng cho held-out AI/publication claim.

Artifacts: [captures](captures.json), [call journal](calls.jsonl),
[analysis](analysis.json), [tests](audit_tests.txt), [Codex validation](codex_validation.json),
[handoff](handoff_antigravity.md).

`validation.json` được thêm trong lượt làm song song và được giữ nguyên. Xác
minh của Codex ở file riêng; 20 là runtime turns đã capture, không phải 20
independent runs chứng minh registry/cache stability.
