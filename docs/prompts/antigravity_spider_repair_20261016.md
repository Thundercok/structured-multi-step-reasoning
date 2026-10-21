# Antigravity — sửa Spider adapter sau Codex review

Đọc `AGENTS.md`, prompt triển khai Spider ban đầu và
`audit/spider_rat_adapter_codex_review_20261016/review.md`, kèm probes/raw results.
Đây là yêu cầu sửa implementation hiện tại, không mở rộng crawler.

1. Xử lý P1 network: default registry không được bật khả năng fetch không có
   kiểm soát destination/redirect thực tế. Có thể fail closed/giữ tool unavailable
   đến khi backend đủ contract. Không dùng post-check hoặc DNS preflight làm
   bằng chứng chặn SSRF. Tests phải kiểm tra network layer hoặc default gate.
2. Sửa pipe deadlock: đọc stdout/stderr đồng thời, enforce cap từng stream khi
   đọc, monotonic deadline/cancel, always kill/reap/close khi cần. Không thay bằng
   `communicate()` gom không giới hạn rồi mới kiểm tra cap. Bao phủ fake output
   hợp lệ khoảng 200 KB, stderr lớn, quá cap và hủy khi process đang chạy.
3. Validate schema/status/content/source: từ chối dữ liệu sai kiểu hoặc nhiều
   trang, không coercion dict thành văn bản. Giữ unknown trung thực. Phân biệt
   source validation với ngăn network; kiểm tra sau tải không thay bảo vệ trước tải.
4. Xác minh version trước request; mismatch/unknown không được ghi version pin
   giả. Chốt release/build identity và sanitized env nhất quán cho version/scrape.
5. Cập nhật tests, raw logs, hashes, audit/backlog và handoff đúng kết quả thực.
   Chạy regression liên quan; lưu riêng fake-binary, real-binary và scripted
   runtime evidence. Không gọi model campaign hay thay research harness.
6. Chuẩn bị manifest migration bao phủ local changes ngoài tracked HEAD; kiểm
   chứng phục hồi. Dùng cùng mẫu số khi báo footprint; chưa xóa/chuyển `spider/`
   hay dọn scratch trước khi các điều kiện migration được đáp ứng.

Không sửa/gom thay đổi của chat khác, không push/pull/reset/force. Để Codex review
vòng tiếp theo; báo rõ P1 nào đã giải quyết và bằng chứng nào còn thiếu. Kết quả
73 tests cũ pass không tự đóng các findings mới.
