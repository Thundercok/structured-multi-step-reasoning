# Bộ chuẩn bị nghiệm thu một cuộc trò chuyện RAT

Ngày 2026-10-13. Đã chuẩn bị
[spec trải nghiệm](../../docs/rat_conversation_acceptance.md),
[stimuli](../../data/rat_conversation_acceptance_v1/scenarios.json),
[scorecard trống](scorecard_template.json) và [validation](validation.json).

Có một luồng chính bảy lượt: tìm → đọc → giải thích → ghi bản nháp ba ý → sửa một
ý → xem bản cũ → hỏi tiếp. Năm nhánh thêm: save failure/retry, ambiguity, cancel/
continue, failed read, long-source boundary. Tổng sáu scenarios/15 user turns,
ba paraphrases development và ba source fixtures gốc do người viết soạn.

Giữ một chat/composer, Chuột bên trái/click emote, notes nhẹ theo lượt và edit
frame chỉ khi sửa. Copy vui vừa là minh họa; chưa sửa UI/prompt/persona production.
Model paraphrase được lưu như proposed draft nếu nguồn hợp lệ, không giả proof.
Không thêm màn hình DSA, feature menu, notes panel, keyword router hoặc DocAI.

Sanity check đã đọc JSON, kiểm ID/context/source links, source character lengths,
recompute binary-search traces và xác nhận note mẫu chỉ đổi ý2. Không chạy runtime,
model hoặc Qt. Đây là kiểm tra fixture/data tĩnh, không phải measured model success.

Các nguồn ngắn340/255 ký tự cho phép bind whole scalar content theo source_result
hiện có. Nguồn dài4597 ký tự có điều kiện first occurrence ở cuối, sau default
read3000. Scenario dài là diagnostic cho read scope/source binding limit, không
buộc triển khai excerpt feature trong lúc Anti đang sửa core. Một giới hạn backend
không bị gộp thành lỗi năng lực model; lỗi ngữ nghĩa DSA cũng không được PASS chỉ
nhờ số học khớp.

Không index personal files, không chạy model mới, không sửa research/Stage0,
defaults, core hoặc app. Core do Anti đang sửa; bộ này là mục tiêu trải nghiệm
để dùng sau core review và sau budget/phase phù hợp. Không thay task sửa gates
bằng việc mở rộng UI.

Số tests/gates qua của các lượt core trước không phải evidence cho bộ mẫu này.
Mọi examples đã lộ để thiết kế, chưa là held-out publication data. Scorecard giữ
not_observed/null, không có điểm chất lượng hoặc số cost giả.
