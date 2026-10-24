# RAT: Hỏi PDF ngay trong min mode — 2026-10-24

Thay nhãn RAT ở chân composer bằng **Hỏi PDF ⌘↵** khi có PDF đang chọn.
Nút và popup dùng chung hàm gửi; khóa khi đang chạy hoặc draft trống.
Command Enter trong composer hỏi PDF; Enter vẫn tìm từ khóa. Các nhánh
Finder, ứng dụng và Shift Enter được giữ nguyên. Không đổi model/prompt.

## Kiểm bằng UI và model thật

PDF người dùng gửi: <https://arxiv.org/pdf/2506.22716>, bản v1, 25 trang.
Tệp nguyên gốc dùng lại tại
`work/rat_reading_live_20261024/arxiv_2506.22716_original.pdf`.
SHA256: `9746346dc6e6552ccdd20158a0eb4b01e927a3cb46242ebaf3d36a9d3b611d9c`.
Provenance đầy đủ ở thư mục đó; không tạo/sửa PDF.

Chỉ nhập/bấm bằng desktop CUA; QML và backend production, state riêng,
không lập chỉ mục tệp cá nhân. Ollama local `qwen3:4b-instruct`, digest trong
`work/rat_pdf_compact_action_live_20261024/model-identity.json`.
Tổng **hai** request model, không chèn đáp án, không chạy thêm để chọn kết quả đẹp.

1. Bấm nút Hỏi PDF với câu hỏi hai quyết định trong abstract: model timeout
   sau 90,014 ms. UI min/full hiện lỗi đúng; public answer rỗng, trạng thái failed.
   Token usage không biết, không coi giá trị 0 trong transport là chi phí bằng 0.
2. Test đầu tiên của Command Enter bắt lỗi ánh xạ: nó chạy tìm từ khóa.
   Qt macOS ánh xạ Command sang ControlModifier; đã nhận cả Control/Meta,
   đóng cửa sổ rồi mở lại trước kiểm bản sửa.
3. Bản cuối: Enter thường tìm `BEST-Route`, khớp 16 trang, hiện 5, không gọi model.
   Command Enter hỏi `Chỉ ghi tên viết tắt của phương pháp trong tiêu đề PDF này.`
   Model thật trả **BEST-Route**, 959 prompt tokens / 4 generated tokens,
   model request khoảng 30.70 giây. Đã xem min/full. Verifier vẫn UNKNOWN.

Do lượt đầu timeout, lượt còn lại dùng câu hỏi độc lập ngắn; **không kiểm hỏi tiếp
trong iteration này**. Kiểm scoped follow-up trước đó nằm ở báo cáo BEST-Route
reading và PDF follow-up. Đây là local smoke, không chứng minh chất lượng hay
latency tổng quát, không vượt Stage 0.

## Bằng chứng

- Lỗi nút + lỗi shortcut ban đầu:
  `work/rat_pdf_compact_action_live_20261024/` — conversation.md/json,
  model-calls.json, ui-transitions.json, desktop.log, live-search-min.png,
  live-turn-turn-1-min.png và live-turn-turn-1-full.png.
- Bản sửa shortcut:
  `work/rat_pdf_compact_action_shortcut_live_20261024/` — conversation.md/json,
  inflight.json, model-calls.json, live-turn-turn-1-min.png và
  live-turn-turn-1-full.png.
- Tóm tắt hợp nhất: thư mục đầu / acceptance-summary.json.
- 12 kiểm tra liên quan qua; git diff --check sạch. QML không phát warning.
  desktop.log giữ nguyên các diagnostic nền tảng IMK/getApplicationProperty/
  Cocoa–Carbon keymapper; không che log.
- Source hash không đổi trong từng lần chạy. Hai cửa sổ exit 0, daemon Ollama
  riêng PID 30766 đã dừng, exit 0. Không để model/test app chạy nền.

## Bàn giao ngắn

Đọc AGENTS.md và docs/project_scope.md. Tiếp tục trên main, không push/reset,
giữ research dirty work và toàn bộ audit/recovery. Các thay đổi UI/PDF/history
của chuỗi này chưa được commit trong iteration này.

Giới hạn còn lại: đoạn đọc 3.000 ký tự, history tối đa hai cặp cùng path/hash;
model đôi khi sai cấu trúc yêu cầu; lần này có timeout thật. Preview là đoạn
câu trả lời thật, không phải bản tóm tắt sinh riêng. Reading prose nối dòng
bảo thủ; trích dẫn giữ nguyên văn bản gốc (xem báo cáo reading trước).

Minor UI đề xuất lượt tới: đổi placeholder khi có PDF thành lời nhắc rõ hai
thao tác “Tìm từ khóa ↵ · Hỏi PDF ⌘↵”, vì placeholder hiện tại vẫn chỉ gợi tìm.
Kiểm lại bằng desktop/model thật, ảnh rõ cả lỗi nếu có; không mở rộng scope.
