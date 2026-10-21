# Antigravity — chuẩn bị tách EVRP/SaigonRide, báo cáo ngắn

Đọc `AGENTS.md`, `modules/evrp/AGENTS.md`, `IMPORT.md`, `IMPORT_PROVENANCE.json`
và `docs/evrp_reuse_audit_20261016.md`. Nhiệm vụ debloat dự án ghép vào;
RAT–CoT là một hệ, không tạo thêm tích hợp EVRP chỉ để giữ code.

1. Inventory đầy đủ `modules/evrp/`: tracked/untracked/ignored, content hashes,
   modes/symlinks. Đặc biệt giữ 7 local extras trong provenance và mọi thay đổi
   mới, docs/notebooks/data/results. Phân biệt generated files; không xóa trước
   khi bảo toàn. Ghi status/head và không đụng thay đổi của chat khác.
2. Đối chiếu read-only repo gốc `Thundercok/evrp-optimizer` và repo README trỏ
   `Thundercok/SaigonRide`; xác định redirect/nguồn hiện hành nếu truy cập được.
   Chưa chốt đích thì không publish, ghi đè hoặc tạo remote. Giữ nguyên 104
   commit IDs/history đã import, không filter/rewrite/squash để cleanup.
3. Tạo staging pristine và archive phục hồi, kiểm thử byte/mode parity. Nếu
   staging còn trong `work/` main repo, báo rõ chưa giảm disk/source thực tế.
4. Rà runtime/build/dependency references; kiểm tra trong bản sao cô lập không
   có `modules/evrp` rằng RAT–CoT startup/default registry và các tests liên
   quan vẫn hoạt động. Không cần khởi động .NET app/payment/database hoặc chạy
   benchmark/training chỉ để chứng minh RAT không phụ thuộc EVRP.
5. Giữ solver/benchmark ở dự án EVRP riêng cho nhu cầu sau; không đưa vào main
   harness, registry hay root requirements. Không nâng legacy results thành
   bằng chứng CoT, BKS comparison hay model-quality claim.
6. Lưu `audit/evrp_extraction_20261016/`: inventory, recovery verification,
   references, tests logs, same-denominator footprint và `handoff_codex.md`.
   Chưa gỡ module trước khi destination/recovery đạt điều kiện và người dùng
   xác nhận đích. Không commit/push/pull/reset/force trong nhiệm vụ chuẩn bị này.

**Trả tối đa 10 dòng:** phần đáng tái sử dụng ngay (nếu tìm ra, phải giải thích
nhu cầu RAT thật), đích ứng viên, parity/restore, tests, số đo và blockers; dẫn
đường evidence thay vì dán command log. Không bắt Codex review lại toàn bộ log.
