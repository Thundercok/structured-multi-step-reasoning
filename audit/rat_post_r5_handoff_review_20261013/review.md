# RAT review sau bàn giao R5

Ngày 2026-10-13, Asia/Saigon. Phạm vi: review bàn giao Antigravity, sửa harness
development và nối kiểm chứng nguồn vào core notes. Không đổi research pipeline,
Stage 0, DocAI, default model hoặc lựa chọn planner của app.

## Kết luận để duyệt

**R5 và các contract lifecycle có bằng chứng đạt trên những ca đã kiểm tra;
trải nghiệm AI xuyên suốt chưa đạt.** Không quy đổi test phần mềm thành năng lực
model, không dùng nhãn runtime `completed` làm workflow success.

Đã triển khai các sửa có thể nghiệm thu headless: log/evaluator trung thực,
guard số học không nhận UNKNOWN do syntax lỗi như một kết luận đã đủ điều kiện,
notes được checker của nguồn kiểm tra trong scope hẹp, và system prefix không
thay đổi chỉ vì đồng hồ/member đổi. Bộ cuối: **206 passed in 4.87s**; xem
[log](headless_tests.txt) và [validation](validation.json).

Hai development conversations thật bên dưới chạy **trước** các sửa guard,
source-note checker và prefix. Chưa chạy model lại trên source cuối; chưa có
nghiệm thu native compact/full cho source này.

## Review bằng chứng Antigravity

Giữ nguyên toàn bộ raw artifacts và review cũ; manifest
[protected_artifacts_sha256.json](protected_artifacts_sha256.json) dùng để đối chiếu.
[raw_smoke_review.json](raw_smoke_review.json) ghi hash, token và các điểm cần sửa
diễn giải của hai smoke DSA:

- R5 thu history/references trước `begin_turn`, không cắt phản hồi assistant cuối;
  execution ID được truyền đúng. 170 tests trong bàn giao đã bao gồm bảy ca
  lifecycle tương đương probes; không cộng thành 177 tests độc lập.
- Câu “viết gọn ... để tôi chép bài” không phải yêu cầu lưu note rõ ràng. 0 note
  events ở DSA không chứng minh model luôn không dùng tools. Không thêm DSA mode
  hoặc hardcode lời giải vào runtime.
- Keyword như `mid=2` không đủ chấm đúng trace: prose vẫn có thể tiếp tục tìm
  sau khi đã gặp đích. Lượt 2 có ví dụ cuối đúng nhưng mô tả nửa phải chứa mid
  đã bị loại; lượt 3/4 sai và lượt 5 lặp lại lời giải sai.
- Flag cancel trong lúc chờ HTTP, với timeout override 0.6s, cùng late-write
  guards chỉ chứng minh phạm vi đó. `request_dispatched` trước `urlopen`
  không chứng minh server đã nhận request hay dừng inference; không chứng minh
  nút cancel native phản hồi tức thì.
- Một call thiếu một trong hai counter không có tổng token đầy đủ. Tổng token
  đã biết ở raw DSA là partial sum 27,263 (planner bật) / 18,420 (tắt); mỗi run
  có cancel probe thiếu usage. Không gọi đó là full inference cost.
- Thời điểm cancel trong review chữ khác raw JSON. Phân tích này dùng raw hashes
  và raw timings. Hai DSA runs cũng có trước contract calculation/result notes
  được thêm ở mốc trước, nên không dùng chúng để xác nhận source mới.

Không sửa hoặc ghi đè các báo cáo/raw run lịch sử.

## Sửa harness development

`scripts/run_dsa_core_smoke.py` dùng cùng runtime/registry/history, DB mock và
timetable rỗng. Thêm scenario calculation chỉ là dữ liệu kiểm thử, không phải
logic định tuyến feature trong app.

1. Output directory phải mới; từ chối trước model calls nếu đã tồn tại. Đường dẫn
   tuyệt đối ngoài repo được hỗ trợ.
2. HTTP refusal không được giả thành cancel. Log phân biệt attempted/waiting,
   cancel flag và timeout; server receipt/abort chưa được kiểm chứng.
3. Chỉ đánh dấu usage known khi prompt và completion đều là counter hợp lệ.
   Partial sums và unknown usage tách riêng.
4. Chấm keyword thành candidate/flagged cần review; không tự chứng nhận đúng.
5. Hash source đầu/cuối, các files runtime liên quan, config/budget; ghi JSONL
   sau mỗi model call. Ghi errors của journal, không che giấu.
6. Ghi status, decision/intervention, verification reports, artifact snapshots,
   note events và execution/turn provenance. Logging bổ sung cuối chưa được
   chạy model thật; đã qua regression fixtures.

Không khẳng định full native equivalence, checkpoint identity hay transport abort
từ metadata harness. Thiết lập `plan_tasks=True`, max_steps=8 và cap generation
mỗi call giống lựa chọn tương ứng của app tại snapshot chạy, nhưng không bao hàm
UI, dữ liệu và mọi cấu hình native.

## Hai conversations model thật đã đo

Dùng các model đã cài; không download, restart service hay đổi default.
`--scenario calculation --mode omnibar --timeout 90 --max-steps 8`.
Mỗi model chạy một conversation bảy lượt đã lộ trong development: tính 18*7,
ghi, đổi 7 thành 9/sửa, so chênh, nhớ kết quả đầu, cancel probe, tiếp tục/ghi gấp đôi.
Lượt 6 dùng riêng timeout 0.6s cho cancel probe.

| Quan sát | qwen2.5:1.5b | qwen3:4b-instruct |
| --- | ---: | ---: |
| Model calls đã thử, gồm cancel | 13 | 17 |
| Operations do model thực hiện | 0 | 4 (2 calculate, 2 record_work_note) |
| Note events | 0 | 2 |
| Notes được xác nhận như observed result trên source lúc chạy | 0 | 0 |
| Wall time lượt không cancel: min / median / max | 19.49 / 24.76 / 33.46 s | 73.16 / 101.04 / 179.14 s |
| Prompt tokens đã biết, partial sum | 21,399 | 48,991 |
| Completion tokens đã biết, partial sum | 358 | 1,591 |
| Usage toàn run đầy đủ | Không | Không |

Model 1.5B trả vài phép tính đúng nhưng không làm yêu cầu ghi/sửa, nhớ sai kết quả
đầu thành 162 và không tiếp tục gấp đôi. Model 4B thực hiện tính và tạo/sửa notes
với đúng nguồn/revision; hai notes còn proposed vì text là phương trình đầy đủ,
trong khi field nguồn chỉ chứa scalar. Lượt cuối model 4B nói “Đã ghi lại ...
324” nhưng không gọi operation, không có note event mới. Cả hai workflow chưa đạt.

Sáu lượt không cancel của mỗi run có `error=None`; đó là runtime status,
không phải sáu nhiệm vụ thành công. Chỉ có một conversation/model, chạy tuần tự,
không kiểm soát load/seeds; không suy ra mô hình nào tốt hơn nói chung hoặc
mọi lỗi đều do model. Planner có thêm calls/context, nhưng chưa có ablation
cùng điều kiện cho flow calculation.

[calculation_model_review.json](calculation_model_review.json) chứa raw hashes,
câu trả lời, events, client planner time và thời gian prompt/generation do server
báo. Các trường timing có scope khác nhau, không cộng tùy ý và không phải latency
native/full inference cost. API tags ghi model Q4_K_M; digest tag không chứng
minh toàn bộ identity của inference session. Không suy diễn CPU-only.

Raw runs:
[1.5B](../rat_calculation_live_20261013_1p5/live_calculation_smoke_plan_tasks_true.json),
[4B Instruct](../rat_calculation_live_20261013_4b_instruct/live_calculation_smoke_plan_tasks_true.json).
Source hashes đầu/cuối bằng nhau trong từng run và journal không báo lỗi.

## Sửa core sau các runs

**Literal arithmetic guard.** Với request số học nằm trong phạm vi, answer dạng
“Tính 2 + 2 = 999” có expression không parse được từng dẫn đến UNKNOWN không
retryable, controller nhận unchecked ACCEPT. Nay UNKNOWN yêu cầu bounded repair;
hết budget trả unresolved, không phát kết luận đó. Native repair fixture kiểm
tra feedback/schema và token accounting. Enum answer do phép tính symbolic xác
định là sửa có ràng buộc, không phải bằng chứng model tự suy luận đúng.

**Source note verification.** `record_work_note` vẫn là một operation chung.
Runtime lấy checker đã đăng ký của artifact nguồn, tạo evidence từ ID/revision,
inputs/payload thật và hash, rồi có thể kiểm tra statement trọn vẹn trong scope.
Calculator checker chấp nhận “18 * 7 = 126” đối với nguồn đó và giữ proof trong
note version. Sai giá trị bị chặn trước commit; prose/biểu thức khác nguồn vẫn
proposed; checker lỗi/report sai contract giữ UNKNOWN. Không có luật theo
keyword DSA/calendar/file hay bộ app riêng.

Exact copy chỉ xác nhận observation đã chép. PASS equation chỉ xác nhận phép tính
gắn nguồn, không chứng nhận ý định user hay mọi diễn giải. User edit bỏ proof cũ;
user acceptance của prose có authority user_supplied, không tự biến thành observed
result. Bản cũ giữ proof và nguồn cũ. Checker time được ghi ở proof/operation,
chưa cộng vào aggregate VerificationSession của answer/operation checks.

**Static system prefix.** Thời gian/member chuyển sang trusted runtime message,
giữ static system/tools prefix. Test xác nhận context vẫn có đủ dữ liệu và prefix
không đổi theo đồng hồ. Chưa đo cache hit hoặc tốc độ sau thay đổi, không tuyên bố
latency cải thiện.

Contract chi tiết: [docs/rat_result_notes_contract.md](../../docs/rat_result_notes_contract.md).

## Phạm vi validation và phần còn thiếu

- 206 headless tests qua, gồm source-note proofs, guard, harness regressions,
  lifecycle, calculator conversation, registry/dispatch và các bộ research
  regression yêu cầu. Các model/HTTP decisions được tiêm trong tests; không phải
  evaluation model thật.
- Source hashes cuối và các protected artifacts được kiểm tra trong
  [validation.json](validation.json). Có nhiều research files do writer khác
  đang sửa trong working tree; review này không bao gồm hoặc sở hữu các thay đổi đó.
- Lệnh Qt offscreen `tests/test_rat_verification_ui.py` ngoài sandbox **chưa
  thực thi**: automatic approval review trả lỗi usage limit. Không retry theo
  đường khác để vượt cơ chế duyệt. Qt cần kiểm tra lại khi công cụ có thể duyệt.
- 53 Qt tests của mốc trước thuộc source trước các sửa guard/checker/prefix.
  Không dùng chúng làm chứng nhận source cuối.
- Chưa nghiệm thu native compact/full, model sau sửa, tốc độ prefix hay hủy
  inference backend. Không công bố Mốc 1 “100% AI success”.

Bước kế tiếp đề xuất là một mốc core có thể review: model đề xuất kết quả cần đạt,
controller đối chiếu actual receipts, và đo lại overhead planner/context. Bản
[hướng dẫn Antigravity](handoff_antigravity.md) đã sẵn để người dùng gửi; chưa gửi
bằng công cụ, chưa triển khai thay đổi lớn đó trong lượt này.
