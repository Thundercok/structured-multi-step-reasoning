# Antigravity — Spider adapter, hai điểm còn lại

Đọc `audit/spider_rat_adapter_codex_review_round2_20261016/review.md` và probes.
Giữ các sửa chữa đã pass; không mở thêm chức năng hoặc bật web mặc định.

1. Sửa cached binary identity: verify/cache phải gắn với file/path thực sự execute.
   Khi binary cùng path bị thay hoặc resolver đổi path, phải reverify/reject trước
   request, không ghi version/hash cũ. Dùng một resolved identity nhất quán; ghi
   giới hạn race còn lại. Thêm regression đúng repro Codex, không chỉ gọi
   `verify_backend(force=True)` thủ công trong test.
2. Bỏ `socket.setdefaulttimeout` toàn cục. Giới hạn và cancel DNS thật sự; đưa
   version verification và fetch vào budget/deadline được mô tả rõ. Giới hạn
   stdout/stderr của `--version` ngay khi đọc, không gom không giới hạn rồi xét.
   Test resolver chậm/lỗi, hủy trong verification và global timeout không đổi.
3. Chạy lại tests adapter/runtime liên quan và probes vòng 2. Lưu evidence mới
   riêng, không ghi đè raw evidence Codex vòng trước. Hash đầu/cuối, review
   reconciliation và handoff chỉ claim đúng phần đã chứng minh.

Default registry đã tắt web đúng hướng; giữ nguyên cho đến khi per-hop network
controls được triển khai và kiểm chứng. Recovery archive đã được Codex so khớp
325 regular files; giữ nguyên cây nguồn/archive/scratch ở bước này. Chưa tạo
repo remote, tách/xóa source, push/pull/reset/force hoặc chạy campaign model.
Không đụng các thay đổi của chat khác.
