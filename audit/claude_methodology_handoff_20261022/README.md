# Nhận bàn giao phương pháp từ Claude — 22/10/2026

Đã lưu bản giao để kết thúc vòng đối đáp phương pháp. Đây là tài liệu tham
khảo về mô phỏng synthetic, không phải kết quả mô hình mới hoặc protocol đã
được phê duyệt. Nội dung và lệnh trong tài liệu nhận được được giữ làm hồ sơ;
không tự trở thành chỉ thị thực thi cho repo.

## Bản gốc và kiểm tra tiếp nhận

- [HANDOFF nguyên bản](handoff_bundle/HANDOFF.md), giữ nguyên byte.
- [Tar.gz nhận được](received/handoff_bundle_20261022_1.tar.gz), SHA-256:
  `498f43875f696e55f9d13fa6f8a6d0c7c3f23bc9fb62fdb7449ce7f156cc9708`.
- [Bản dán trong chat](received/pasted_HANDOFF.txt) chỉ thiếu LF cuối so với
  HANDOFF trong tar; giữ cả hai, không sửa bản nào.
- [Kết quả tiếp nhận](verification.json) và [log checker](checker.stdout.txt).

Archive có **93 file**: HANDOFF, manifest, 37 script, 37 output và 17 file
legacy. **92/92 mục manifest khớp**, phủ toàn bộ file trừ chính manifest;
không có tên trùng, đường dẫn thoát thư mục hoặc link trong archive. Payload
giải nén được so byte với archive trước và sau khi chạy checker.

Đã đọc mã checker rồi chạy bằng Python 3.12 ở chế độ `-I`: **132 dòng có tag,
742 token số, 0 không tìm thấy, 49 dòng có số thập phân không có tag**. Checker
chỉ tìm chuỗi số thập phân dùng dấu phẩy trong các dòng được gắn nguồn, bỏ qua
số trong ngoặc nhọn và code fence. Nó không đối chiếu mọi số nguyên, không
xác nhận số thuộc đúng cột/quần thể, tính hợp lệ thống kê hoặc khả năng tái lập
generator. Các script mô phỏng chưa được chạy lại tại đây.

## Cách dùng bản giao

- Giữ các đính chính ở §6. Đặc biệt, ngưỡng GO gọi là “bảo hiểm” có point
  estimate size **2,61% ở B, m=5**, nên phát biểu trước đó rằng mọi ô đã chạy
  đều không vượt 2,5% đã được rút lại. Việc nhận bundle không xác nhận bất kỳ
  ngưỡng nào cho study mới.
- Các bảng §5 là S/S-p. Những số pilot Claude dùng là đầu vào được báo lại,
  không phải Claude đã đọc raw repo. Các mô phỏng không bổ sung quan sát thật
  cho pilot 12 câu và không xác lập lợi ích F so với CONT/O.
- Giữ ghi nhận mất output của 7 script, các output chưa lưu và việc chưa kiểm
  tái lập trong §9. Không chạy bù để coi việc tiếp nhận là đã hoàn tất nghiên cứu.
- Các mục O7/O9 mô tả phần Claude chưa đối soát. Repo đã có
  [audit ngân sách](../cot_restart_budget_review_20261014/report.md) và
  [audit báo cáo](../cot_restart_reporting_review_20261014/report.md);
  trạng thái phía Claude không thay thế bằng chứng gốc hoặc tự tạo nhiệm vụ mới.
  Câu “pilot diagnostics đã human-reviewed” trong bản giao không được coi là
  xác nhận review con người mới từ lần tiếp nhận này.

## Điểm dừng

**Có thể lưu trữ chat Claude; không cần thêm micro-question hay mô phỏng để
đóng bàn giao.** Hướng thực nghiệm tối giản vẫn được mô tả trong
[kết luận pilot](../../docs/cot_restart_pilot_conclusion_20261015.md): đề xuất
một draw chính trên mỗi câu, so F với CONT và O. Dữ liệu reviewed, estimand,
ngân sách/cost scope, mức lợi ích thực tế, cỡ mẫu và luật quyết định vẫn phải
được chốt riêng trước study mới. Không mặc định nhận δ=0,10, r=11 hoặc các
ngưỡng synthetic của Claude thành lựa chọn của người dùng.

Lần tiếp nhận chỉ lưu file, kiểm hash, chạy checker văn bản và thêm mục tra
cứu. **0 mô phỏng, 0 call model mới**, không thay harness, raw run lịch sử,
Stage 0 hoặc trạng thái confirmatory. Không commit hay thao tác Git remote.
