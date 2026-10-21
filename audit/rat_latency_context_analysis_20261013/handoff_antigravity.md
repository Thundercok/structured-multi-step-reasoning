# Anti: việc tiếp theo để RAT liền mạch hơn

Core reconciliation vẫn là ưu tiên đang triển khai. Sau khi chốt core, ưu tiên
giảm thời gian chờ và context lặp trên luồng chat hiện tại. Giữ một ô chat, note
gắn turn, full/compact dùng chung phiên và personality Chuột. Không mở thêm
feature app hay cửa sổ notes.

Đây là brief/spec đề xuất, **không cho phép tự chạy model mới, đổi default hay
đụng phần research/DocAI**. Người dùng giao Codex suy nghĩ/review và Anti làm;
review UI là giai đoạn sau core. Không trộn việc này vào diff core chưa xong.

## Evidence đã có

Xem [offline report](report.md) và [per-call metrics](analysis.json). Không có
model calls mới trong phân tích. Hai run lịch sử pre-fixes không dùng làm
benchmark của bản hiện tại và không phải model comparison có kiểm soát.

- Prompt processing chiếm 69,30% / 69,71% server total có báo cáo.
- Planner riêng chiếm 32,76% / 28,90% wall time của sáu lượt không hủy.
- Actor gửi 15 schemas, 8.615 canonical JSON characters, mỗi call.
- Cùng task-state object xuất hiện ở hai messages trong 16/16 actor calls.
- History, turn refs, note versions và source refs có nội dung giao nhau,
  nhưng ID/provenance cần giữ. Không thể giảm số calls bằng cách bỏ outcome.

Không suy ra speed-up từ các tỷ lệ này. Một call cancel thiếu token/server
metrics mỗi run; tổng chi phí đầy đủ chưa biết. Timestamp trong system và cache
count lịch sử là chẩn đoán, không xác nhận nguyên nhân cache. System prefix đã
được tách sau run; kiểm tra triển khai hiện tại trước khi sửa.

## Gói công việc để thiết kế sau core

**A. Audit context hiện tại bằng mock, không inference.** Snapshot core xong,
capture request ở các vòng planner/actor/tool. Báo từng phần theo characters/
bytes, marker/provenance và IDs. Chỉ dùng fixture để phát hiện lặp và mất
contract; không gọi software tests là measured model quality. Đầu ra cần chỉ
rõ field nào lặp giống hệt, field nào chỉ giống nội dung nhưng khác quyền hạn.

**B. Thiết kế một model-facing context snapshot.** Task proposal có một nơi,
state/receipts/outcomes/source references có typed roles rõ. Giữ immutable
note history và version references trong storage; snapshot giữ đủ revision và
nguồn để model xem bản cũ khi được hỏi. Không xóa proof scope, unmet outcomes,
failure/cancel state, source boundaries hoặc user constraints. Nếu thay đổi
snapshot schema, mô tả before/after request rồi review contract trước khi
triển khai. Không thêm feature routing bằng if/else/keywords.

**C. Kiểm tra static prefix đã làm.** Giữ ổn định registry order và static
instruction; runtime time/member/session ở message động. Không đẩy retrieved
text/notes/tool result vào trusted instruction. Giữ mọi tools được discoverable;
chưa chọn schema pruning theo tên feature. So sánh raw-request fixtures trước
và sau để kiểm nội dung/ID, không tuyên bố đã nhanh hơn.

**D. Spec riêng cho one-call proposal + action nếu còn cần.** Đề xuất gộp
planner và first decision vào structured response, model tự chọn action.
Controller đóng băng đủ requested outcomes trước side effect; proposal không
trở thành bằng chứng thực hiện. Tool receipt và NeSy proof đúng scope mới phục
vụ reconciliation. Ambiguity/failure/cancel/resume phải đi qua cùng contract.
Không bật thay đổi này mặc định trong lúc đang sửa core; trình design và
phương án đo trước. Learned controller vẫn là hướng nghiên cứu cần dữ liệu/
gate riêng, không có policy training ngầm từ vài logs này.

## Acceptance và đo về sau

Review bằng [conversation pack](../../docs/rat_conversation_acceptance.md):
follow-up nhiều cách nói, sửa note thứ hai, đọc bản cũ, lỗi rồi retry, cancel/
resume và source dài. Chi tiết source dài hiện chỉ là diagnostic cho boundary
đọc; không tự mở rộng thành tính năng DocAI/excerpt.

Điều kiện trước khi xin chạy live: contract fixtures vẫn đúng, source snapshot
được freeze, budget/model/cap/order được nêu rõ. Khi có duyệt live, giữ mọi raw
calls, prompt/completion/cached counts, server load/prompt/generation và wall
time; usage thiếu giữ unknown. Quality cần đối chiếu actual outcome/receipt và
false completion. Không bỏ lượt thất bại khỏi bảng chi phí. Không hứa mức tăng
tốc chưa đo, không dùng hai pilot cũ để đổi model mặc định.

Codex sẽ review bản core riêng và design context ở giai đoạn tiếp theo. Brief
này chưa được gửi qua tool tới Anti và chưa có sửa runtime/UI từ Codex.
