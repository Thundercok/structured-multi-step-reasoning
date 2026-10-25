# Bàn giao RAT–CoT — 25/10/2026

Người dùng đang review 96 câu GSM8K trong PDF/CSV cùng thư mục. Tiếp theo: nhận quyết định và ghi chú của người dùng, rồi chuẩn bị release dữ liệu và cấu hình phép đo development.

Đọc AGENTS.md, docs/project_scope.md, docs/research_plan.md, docs/research_protocol.md và docs/gsm8k_development_validation_protocol_20261004.md trước khi thay đổi.

- RAT dùng CoT; đây là một hệ thống phục vụ bài NCKH và pipeline đo tái lập.
- Candidate gốc: data/gsm8k_development_validation_candidate_v1/dataset.json. Có 48 fitting + 48 development validation. Agent đã đọc và kiểm tra 96 câu: 93 khớp gold, 3 có tranh chấp. Trạng thái cũ “chưa đọc candidate” đã hết hiệu lực. Chưa fit quy tắc từ candidate hoặc thu model outputs.
- Ba câu đề xuất loại: gsm8k-dev-02343 (before/on ngày 25), gsm8k-dev-00484 (giảm cân theo tỷ lệ hay lượng cố định), gsm8k-dev-03823 (thinking chưa đồng nghĩa cam kết bỏ phiếu). Cả ba thuộc fitting. Người dùng nghiêng về loại nhưng chưa ký quyết định cuối. Nếu loại cả ba: 45 fitting + 48 validation = 93 câu; dự kiến 279 calls với ba chiến lược. Cần release/protocol guards mới trước khi chạy; chưa sửa candidate.
- Review ledger và kiểm chứng: audit/gsm8k_candidate_agent_review_20261024/README.md. Đề xuất sửa wording chưa áp dụng: audit/gsm8k_adjudication_proposal_20261025/README.md.
- Các nghiệm thu offline checker/collector/adapter đã đóng; không mở lại bridge. Sửa native seed fail-closed đã kiểm tra 189 tests pass, xem audit/gsm8k_seed_fail_closed_20261024/README.md.
- Inference/embedding budget vẫn 0. Không load model hoặc chạy generation. Stage 0 và measured staged gate chưa được thông qua; tests phần mềm không chứng minh chất lượng model.
- Cấu hình/hash lịch sử phải giữ nguyên; cần freeze mới cho source hiện tại trước phép đo thật.
- Bản thảo/phép đo: docs/gsm8k_measurement_review_packet_20261024.md; trạng thái docs/gsm8k_development_review_readiness_20261023.md; mục lục docs/research_artifact_index.md.
- Giữ main, giữ thay đổi UI không liên quan. Không push/pull/reset/force nếu người dùng không yêu cầu trong cùng tin nhắn. Không tự mở chat mới.

Prompt tiếp nối: “Tiếp tục RAT–CoT từ START_NEXT_CHAT.md. Đây là các quyết định review dữ liệu của tôi: ... Đối chiếu source mới nhất, cập nhật release và cấu hình development theo quyết định; giữ inference budget 0 và các gate nghiên cứu hiện hành.”
