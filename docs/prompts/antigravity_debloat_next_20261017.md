# Bước tiếp theo: gom cấu trúc trong cùng hệ RAT–CoT

1. Đọc AGENTS.md và docs/project_scope.md; RAT sử dụng CoT, CoT được thể hiện bằng RAT.
2. Watch bot/EVRP đã gỡ; không khôi phục. Giữ recovery, audit, Spider adapter mặc định tắt.
3. DocAI source đã gỡ theo yêu cầu tiếp theo; recovery đã kiểm chứng ở audit/docai_removal_20261017/removal_metrics.json. Không nhập lại modules/docai/.
4. Giữ document_intake/ dùng chung; khi tách DocAI phải cung cấp wheel/version dependency này, không chép một bản OCR mới vào DocAI.
5. Rà entry_predictor.py, optimal_stopping.py, reasoning_env.py, reasoning_strategies.py và consumers RAT/harness; lập bản đồ imports và hợp đồng trước khi đề xuất gom package.
6. Ưu tiên một implementation dùng chung, adapter UI/headless riêng; không suy ra tương đương hành vi từ tên lớp/imports.
7. Không đổi model, prompt, threshold, policy hoặc claims trong structural cleanup; đọc research_plan/protocol nếu chạm phạm vi đó.
8. Giữ toàn bộ thay đổi của chat khác; không branch/commit/push/pull/reset. Chạy tests thích hợp theo AGENTS khi sửa harness.
9. Bàn giao diff nhỏ, số liệu trước/sau cùng phương pháp, kết quả tests và giới hạn; không tính audit/backups là mã sản phẩm.

Cập nhật tiếp 2026-10-17: đã gỡ legacy/V1, legacy/V2, qwen_backend.py và generate_history.py; không nhập lại. Giữ qwen_mlx_backend.py, pipeline.MockDemoBackend và scripts/legacy/run_sweep_p.py vì vẫn có consumers/provenance. Evidence: audit/unused_source_removal_20261017/.
