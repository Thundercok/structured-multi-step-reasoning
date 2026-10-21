# RAT: chẩn đoán thời gian chờ và context từ logs đã có

Hai cuộc hội thoại development cũ cho thấy một điểm đáng ưu tiên: xử lý prompt
chiếm khoảng **69–70% tổng server duration được báo**, còn planner riêng chiếm
**29–33% thời gian chờ của sáu lượt không bị hủy**. Context cũng có dữ liệu lặp
cụ thể. Đây là căn cứ chọn việc cần đo và tối ưu tiếp; chưa có mức tăng tốc đã
được kiểm chứng trên core hiện tại.

Phân tích này chỉ đọc artifacts, **0 model calls mới**, không sửa core, UI hay
model mặc định. Antigravity tiếp tục sở hữu phần triển khai core đang chạy.

## Phạm vi và nguồn

- Mỗi model có một cuộc hội thoại bảy lượt đã lộ, planner bật, cap 640 output
  tokens/call, tối đa tám bước; probe hủy dùng timeout ngắn riêng.
- Hai lần chạy tuần tự, không kiểm soát thứ tự, tải máy, seed hoặc cache.
  Bảng đặt cạnh nhau để mô tả logs, không phải so sánh model hay ablation planner.
- Source của hai lượt này ổn định trong từng run và cùng manifest lịch sử.
  Chúng có trước literal guard, kiểm chứng note-source, tách system prefix và
  các vòng completion reconciliation. Số liệu không mô tả bản RAT đang sửa.
- Headless development runner dùng dữ liệu giả cho DB/lịch học và model Ollama
  thật. Không có quan sát UI/native trong phân tích này.
- Raw calls trong JSONL được đối chiếu bằng giá trị đầy đủ với calls nằm trong
  từng turn JSON. Hash raw JSON và tổng token/thời gian được đối chiếu lại với
  [review lịch sử](../rat_post_r5_handoff_review_20261013/calculation_model_review.json).

Nguồn: [1.5B raw turns](../rat_calculation_live_20261013_1p5/live_calculation_smoke_plan_tasks_true.json),
[1.5B journal](../rat_calculation_live_20261013_1p5/raw_calls_plan_tasks_true.jsonl),
[4B raw turns](../rat_calculation_live_20261013_4b_instruct/live_calculation_smoke_plan_tasks_true.json),
[4B journal](../rat_calculation_live_20261013_4b_instruct/raw_calls_plan_tasks_true.jsonl).

## Số đo lịch sử

| Đại lượng | qwen2.5:1.5b | qwen3:4b-instruct |
| --- | ---: | ---: |
| Tổng calls / có token usage / thiếu usage | 13 / 12 / 1 | 17 / 16 / 1 |
| Planner / actor calls, gồm probe hủy | 7 / 6 | 7 / 10 |
| Median wall time, 6 lượt không hủy | 24,76 s | 101,04 s |
| Wall time cộng của 6 lượt không hủy | 148,04 s | 664,33 s |
| Planner client time trong 6 lượt đó | 48,50 s | 191,97 s |
| Planner / wall time của 6 lượt đó | 32,76% | 28,90% |
| Tổng server duration có báo cáo | 146,39 s | 663,16 s |
| Prompt processing, server báo cáo | 101,45 s | 462,27 s |
| Generation, server báo cáo | 29,68 s | 177,51 s |
| Load, server báo cáo | 6,98 s | 9,06 s |
| Server total trừ load/prompt/generation | 8,28 s | 14,32 s |
| Prompt processing / server total có báo cáo | 69,30% | 69,71% |
| Prompt tokens đã biết, tổng một phần | 21.399 | 48.991 |
| Completion tokens đã biết, tổng một phần | 358 | 1.591 |

Planner là một phần của các model calls và server duration, không cộng thêm vào
chúng để tính chi phí. Phần server duration còn dư chưa được quy nguyên nhân.
Token thiếu ở probe hủy giữ `null`; không suy ra zero và không có full-run token
total. Đếm prompt/completion không phải full inference cost, cũng không có nghĩa
mỗi loại token có chi phí thời gian bằng nhau. Cancel probe không chứng minh
server đã dừng inference ngay khi client kết thúc chờ.

## Context lặp có thể kiểm tra trực tiếp

Mỗi actor call chứa cùng **15 tool schemas**, tương đương **8.615 ký tự** khi
serialize canonical compact JSON. Phần `tools` chiếm **62,77% / 53,61%** tổng
ký tự request actor qua hai run. Đây là tỷ lệ ký tự của JSON tái serialize,
không phải tỷ lệ token, wire size thực tế hay phần latency có thể tiết kiệm.
Một schema hash duy nhất được lặp 6 lần ở run 1.5B và 10 lần ở run 4B.

Task state giống nhau về giá trị JSON xuất hiện cả trong message
`Previous model-authored task state` và `observation.task_state`: **6/6 và
10/10 actor calls**. Hai cách đóng gói làm lặp cấu trúc, dễ tạo state lỗi thời
nếu sau này một nơi được cập nhật mà nơi kia không đổi. Có thể cân nhắc một
representation rõ provenance và phiên bản; proposal vẫn là proposal.

Lịch sử chat và turn references cùng được gửi. Trong run 4B, tổng raw-content
characters qua actor calls là 1.235 cho history, 9.735 cho turn references,
4.825 cho active notes và 2.500 cho historical notes. Những phần này có nội dung
giao nhau nhưng cũng giữ ID, revision và source riêng; không coi toàn bộ là dữ
liệu thừa để xóa. Lượt hỏi kết quả đầu tiên và giữ note hiện tại là lý do cần
bảo toàn phân biệt cũ/mới.

First actor prompt tăng từ **2.434 lên 3.488 tokens** ở run 1.5B và **3.049 lên
5.448** ở run 4B, từ turn 1 tới turn 7. Đây là quan sát trên hai trajectory
khác nhau, không quy riêng mức tăng cho một field hay so hiệu suất model.

System message lịch sử có 2.606 ký tự contract/persona trước `Current time`.
Timestamp đổi trong tất cả actor calls, kể cả giữa các bước cùng turn.
Server báo `prompt_eval_cached_count=3` cho sáu actor calls đầu mỗi turn ở cả
hai run; bốn actor calls bổ sung của 4B báo 513. Counts này là chẩn đoán từ
server, không xác nhận cache savings, cache policy hay nguyên nhân chậm duy
nhất. Thay đổi timestamp, chèn context giữa vòng tool và lịch gọi xen kẽ
planner/actor là các giả thuyết cần đo, không phải kết luận nhân quả. Tách
system prefix đã được làm sau các run này; cần kiểm tra bản mới trước khi
đề xuất sửa lại.

## Thứ tự phát triển đề xuất

1. **Core đúng trước.** Kết quả phải khớp requested outcomes, receipts,
   dependency, proof scope và trạng thái note cuối. Lượt ít calls nhưng quên
   lưu kết quả không phải một lượt tối ưu thành công. Lịch sử 1.5B không thực
   thi operation nào; 4B thực thi bốn operation nhưng lượt resume vẫn nói đã
   lưu dù không tạo note event. Không dùng chúng làm baseline chất lượng tốt.
2. **Đo context của core mới, rồi bỏ representation lặp.** Một state snapshot
   cho model, phần còn lại giữ trong storage; references ngắn có ID/revision
   và đường inspect nguồn khi cần. Không xóa user constraints, note mới/cũ,
   requested outcomes, source/proof hay cancellation provenance để đạt cap.
3. **Giữ prefix ổn định và kiểm tra lại cache.** Registry ordering và static
   contracts cần nhất quán; current time/member/session data ở phần động.
   Đối chiếu raw requests với cached count/server time; không tuyên bố lợi ích
   chỉ vì prompt trông gọn hơn.
4. **Sau đó mới thử gộp proposal + first action trong một call.** Model vẫn
   hiểu yêu cầu và chọn thao tác theo schema. Outcome được đóng băng trước
   side effect, ambiguity và failure giữ nguyên. Đây là thay đổi behavior cần
   spec/gate riêng, chưa được triển khai hay bật mặc định.
5. **Schema discovery chỉ xét nếu vẫn cần.** Metadata chung ngắn + khám phá
   schema qua registry theo lựa chọn của model là hướng dài hạn. Không thêm
   keyword router cho calendar/file/DSA/astrology. Discovery có thể thêm call,
   tăng latency hoặc làm mất khả năng chọn tool; chưa có evidence lợi ích.

Giai đoạn offline gần nhất cho Anti: snapshot source đã hoàn tất core; lưu
fixtures raw-request từ native mock cho chat, follow-up, note create/update,
lookback và cancel/resume; so context representation và kiểm tra ID/source/
outcome còn đủ. Các fixtures đó chỉ kiểm contract/size, không đo chất lượng AI.

Giai đoạn live sau đó cần duyệt ngân sách riêng. Dùng cùng model, data, cap và
máy, counterbalance thứ tự, báo warm/cold load/cache, giữ đủ raw calls và mọi
operation thất bại. Bộ [conversation acceptance](../../docs/rat_conversation_acceptance.md)
đã lộ dùng cho development; nếu kiểm tra độ tổng quát, chuẩn bị và review nhóm
paraphrase mới trước khi chạy. Đánh giá outcome correctness và false completion
cùng latency; không loại lượt sai khỏi latency tổng rồi chỉ báo lượt tốt.
NCKH/Stage 0 không đổi và DocAI vẫn tách riêng.

## Tái lập

Tại repo root, xuất sang đường dẫn **chưa tồn tại**:

```bash
PYTHONDONTWRITEBYTECODE=1 python audit/rat_latency_context_analysis_20261013/analyze.py --output /tmp/rat_latency_context_reproduced.json
```

[analysis.json](analysis.json) giữ metric từng call, turn, schema hash và input
hash; [validation.json](validation.json) giữ kết quả tái lập offline.
Không chạy runner model để tái lập phân tích này.
