# RAT: lời nhắc tìm và hỏi PDF — 2026-10-24

Minor UI: khi có PDF, placeholder composer là **Tìm từ khóa ↵ · Hỏi PDF ⌘↵**.
Đã nhìn min/full thực tế: lời nhắc vừa một dòng, nút Hỏi PDF và hành vi gửi giữ nguyên.
Chỉ sửa copy một dòng trong `rat/ui/quick/PDFDesk.qml`; không đổi model/prompt.

Kiểm qua desktop CUA với QML/backend thật, state riêng, không canned answer.
PDF BEST-Route do người dùng gửi: <https://arxiv.org/pdf/2506.22716>.
Dùng lại nguyên bản v1, 25 trang tại
`work/rat_reading_live_20261024/arxiv_2506.22716_original.pdf`.
SHA256 trước/sau: `9746346dc6e6552ccdd20158a0eb4b01e927a3cb46242ebaf3d36a9d3b611d9c`.

- Enter tìm `BEST-Route`: khớp 16 trang, hiện 5; chưa gọi model.
- Command Enter hỏi: “Theo abstract, BEST-Route chọn mô hình và đại lượng nào nữa?
  Chỉ ghi tên đại lượng đó bằng tiếng Việt.”
- Model local `qwen3:4b-instruct` trả thật: **Số lượng phản hồi**.
  Đối chiếu thủ công khớp abstract; UI verifier vẫn UNKNOWN.
- Đúng một request model: 970 prompt tokens, 6 generated tokens,
  model request khoảng 52.52 giây. Không coi đây là full inference cost hay
  latency tổng quát. Không có timeout trong lượt này.

Artifacts: `work/rat_pdf_composer_hint_live_20261024/` chứa conversation.md/json,
inflight.json, model-calls.json, model-identity.json, document-provenance.json,
enter-search-check.json, acceptance-summary.json, ảnh live-turn-turn-1-min.png
và live-turn-turn-1-full.png. Desktop/Ollama log được giữ nguyên, gồm cả
diagnostic nền tảng Cocoa–Carbon keymapper/IMK/getApplicationProperty.

QML không phát warning; source hash không đổi trong lần chạy; PDF hash không đổi.
git diff --check qua. Không thêm/chạy lại unit tests cho thay đổi copy một dòng;
12 kiểm tra liên quan đã qua ở iteration trước. Native app exit 0; daemon Ollama
riêng PID 65565 đã dừng, exit 0. Không commit/push trong lượt này.

Giới hạn còn nguyên: đoạn đọc 3.000 ký tự, history tối đa hai cặp cùng path/hash;
local smoke không vượt Stage 0 và không đo chất lượng phương pháp. Bàn giao các
thay đổi trước: xem `rat_pdf_compact_action_live_20261024.md` và
`rat_best_route_reading_live_20261024.md`; giữ research dirty work/audit.

Minor UI đề xuất tiếp: rút trạng thái khi chờ trong min mode thành nhãn cụ thể
theo công việc đang chạy, vì “Xem tiến trình” chưa cho biết app đang đọc hay chờ model.
