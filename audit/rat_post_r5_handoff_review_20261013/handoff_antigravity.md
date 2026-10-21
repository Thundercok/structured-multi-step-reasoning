# Mốc kế tiếp đề xuất: RAT hoàn thành việc và nói đúng trạng thái

Đọc review.md, validation.json, docs/rat_result_notes_contract.md và AGENTS.md
trước khi làm. Đây là brief để người dùng duyệt/gửi, chưa phải xác nhận mốc đã triển khai.
Giữ evidence folders cũ; output live run phải là folder mới. Không git
push/pull/reset/force trừ khi user yêu cầu trong cùng message.

## Kết quả cần đạt

Một chat giữ mục tiêu, dữ liệu và kết quả xuyên các lượt. Khi user yêu cầu ghi/sửa,
RAT thực hiện và có receipt thật, hoặc nói rõ việc nào còn thiếu. Phản hồi không
được gọi một công việc hoàn tất chỉ dựa vào câu model nói “đã làm”.
Không mở app mới, không thêm DSA mode/keyword router/feature menu, không chạm DocAI
hay research gate/default model để làm demo dễ đậu. Giữ Chuột bên trái và click
chỉ emote; notes inline theo lượt, lịch sử bất biến.

## Thiết kế trước implementation

Đề xuất một contract chung cho requested outcomes, action receipts và completion.
Model hiểu yêu cầu và đề xuất outcomes có kiểu; controller kiểm tra receipts từ
dispatcher/store/notebook, không tin một nhãn completed do model tự khai.
Contract phải phân biệt trả lời hội thoại, action thành công, proposed note,
UNKNOWN, còn thiếu outcome và cancelled. Không bắt mọi câu giải thích cần gọi tool.

Giải quyết cả omitted action: không chỉ kiểm tra tool khi model đã gọi. Ví dụ
“ghi lại” nhưng không có note event phải còn unresolved. Cách xác định user intent
vẫn là phần model/contract cần đo, không tuyên bố checker đã chứng minh ngôn ngữ
tự nhiên đúng. Nếu contract chưa đủ chứng cứ, giữ trạng thái chưa kiểm chứng,
không tạo luật bắt keyword rồi gọi tool cứu hộ âm thầm.

Proof của một phép tính/note chỉ có scope của nó. Không đánh đồng arithmetic PASS
với workflow completion, không sửa ngược raw trace để cho đẹp.

Gửi thiết kế ngắn và diff dự kiến để user review trước khi đổi contract core.
Chưa thêm UI; nếu cần biểu thị unresolved, dùng trạng thái inline hiện có và
review copy trước.

## Đo và giảm chi phí gọi model

Đo cùng flow với planner bật/tắt dưới cùng config/model, ghi raw requests/responses,
source hashes, prompt/completion và unknown cost. Instrument planner, generation,
verification và operations riêng, để biết phần nào chậm. Có thể đề xuất tránh
planning call dư hoặc giảm context trùng; chỉ đổi default sau review bằng chứng.
Static prefix vừa sửa chưa có live latency result.

Mỗi live run phải có budget cụ thể user duyệt (calls/time/model), folder mới và
journal. Không tự mở một benchmark dài hoặc download model. Dữ liệu đã dùng là
exposed development, không gọi là held-out NCKH. Kiểm tra API model metadata nhưng
không suy ra checkpoint/native equivalence từ tag.

## Điều kiện review

- Fixture trên cùng core cho tính → ghi → đổi/sửa → so bản cũ → nhớ bản đầu →
  dừng → tiếp tục; assertions dựa store/events/version, không theo câu “đã ghi”.
- Negative cases: model hứa nhưng không gọi; ghi proposal rồi nói đã xác nhận;
  source/revision giả; sửa stale; cancelled callback; chỉ hoàn thành một trong
  nhiều outcomes. Không có fallback hardcode theo scenario.
- Live prompts gốc và cách diễn đạt mới: chấm hành động, dữ kiện, nội dung và
  completion riêng. Giữ thất bại; không tiêm fixture decisions vào live runs.
- Regression headless phù hợp, Qt khi approval tool hoạt động, native compact/full
  sau core acceptance. Model mới/nguồn mới chưa được coi là đã qua native test.
- Báo thay đổi, hash, chi phí còn thiếu, latency scope, tác vụ thành công/thất bại
  và rủi ro còn lại. Không cộng probes vào tests nếu đã trùng cases.
