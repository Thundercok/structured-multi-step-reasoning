# Bộ mẫu trải nghiệm — đọc để giữ mục tiêu, triển khai sau core review

User giao Codex chuẩn bị luồng RAT trong lúc Anti sửa core. Các file:
- docs/rat_conversation_acceptance.md: luồng, copy minh họa, tiêu chí và phase.
- data/rat_conversation_acceptance_v1/scenarios.json: sáu scenarios/15 turns.
- data/rat_conversation_acceptance_v1/sources/: ba tài liệu fixture gốc.
- audit/rat_conversation_acceptance_preparation_20261013/scorecard_template.json:
  bảng chấm trống theo content/references/effects/surface.
- validation.json ở folder này: sanity check dữ liệu tĩnh, không model-quality result.

Tiếp tục fixes core đang mở theo review mới nhất. Bộ này không thêm phase UI/live
được duyệt hoặc thay việc sửa các gates còn lỗi bằng một demo màn hình.

Sau core review, dùng luồng chính để duyệt copy/notes trên một chat: source inline,
note nhẹ theo lượt; edit frame khi sửa; phiên bản cũ/link mới; cùng composer ở
full/compact. Chuột bên trái và click chỉ emote. Không DSA mode, toolbar gợi ý,
popup app hoặc notes drawer.

Model được tự chọn hành động trên user prompts, source thật trong fixture và
context. Reply examples/specimen notes/criteria là gold design cho người chấm,
không đưa vào model prompt như đáp án hoặc dùng làm keyword policy. Runtime
không có nhánh riêng cho câu trong bộ này.

Nếu dùng fixture adapters, ghi rõ search hits/read/fault setup là controlled
development data; không gọi đó là retrieval quality trên personal index.
Live run sau này cần budget riêng, source/model hashes, raw calls/receipts và
manual grading, không tiêm model decisions rồi chấm AI success.

Notes paraphrase từ document_content giữ proposed/nháp trừ khi có authority/
proof phù hợp. Lưu draft có thể thỏa yêu cầu lưu draft; đừng ép user confirm mỗi
note để demo đậu. Source_quote là lời user, không dùng văn bản tài liệu giả làm
lời user. Các source ngắn dưới500 ký tự có thể bind content scalar hiện có.

Long-source case ghi capability gap nếu whole-field binding không được hỗ trợ;
không cắt nguồn ngầm hoặc tích hợp DocAI để làm nó PASS. Missing/partial/cancel
phải giữ kết quả thực đã commit và nói đúng phần chưa làm; không fake completion.

Nghiệm thu coi wording là linh hoạt, chấm đúng dữ liệu/hành động/ownership/history,
không regex vài keywords. DSA content là manual semantic review; arithmetic PASS
không xác nhận algorithm hay hiểu ý định. Chưa đặt latency/model-success threshold
khi baseline chưa đủ; ghi first useful result time, call costs và unknowns riêng.

Giữ mọi audit cũ. Không chạy live/native, đổi defaults hoặc push/pull/reset/force
do chỉ đọc brief này. Codex review bằng evidence của phase được user chốt.
