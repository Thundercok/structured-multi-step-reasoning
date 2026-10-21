# Sửa review trước khi gom reasoning/

1. Đọc audit/rat_cot_structural_consolidation_review_20261017/review.md và AGENTS.md; RAT–CoT là một hệ.
2. Đính chính DocAI/qwen_backend đã gỡ; cập nhật import map và số đo từ working tree hiện tại, giữ raw audit cũ.
3. Ghi đúng: meta_reasoner chỉ import EntryPredictor, chưa gọi; policy branch đang dùng confidence/escalation mô phỏng, chưa có evidence nguồn tau.
4. Ghi đúng research_study: stopping fit calibration, predictor fit train; replay records, không Gym episode loop; bootstrap mặc định tắt.
5. Gom canonical reasoning/ thành diff nhỏ, giữ nguyên logic/model/prompt/policy; không sửa các khoảng trống tích hợp trong cùng refactor.
6. Compatibility không chỉ import *: bảo toàn module/symbol identity, patch behavior và tránh circular imports; __init__ nhẹ, không kéo Qt/ML khi chỉ import parsers.
7. Cập nhật source_hashes/source-pinned checks để hash implementation mới lẫn shims; kiểm tra thay đổi canonical source làm fingerprint đổi, giữ artifacts cũ.
8. Chạy bộ AGENTS, tests env/strategies/scoring/backend mock và runtime phù hợp; báo số đo thật trước/sau, không hứa delta LOC=0.
9. Giữ việc chat khác/recovery; không branch/commit/push/pull/reset. Bàn giao diff, logs và các giới hạn.
