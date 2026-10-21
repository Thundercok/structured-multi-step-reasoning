# Spider adapter — Codex review vòng 2

Ngày 2026-10-16. **Cần sửa hai điểm P2 dưới đây; chưa đồng ý claim “ALL FINDINGS
RESOLVED”.** Default registry đã fail closed; không còn kết luận web tool đang
mở mặc định như vòng 1. Không sửa product source hoặc chạy network ở lượt này.

## Phần đã xác nhận

- Suite adapter/runtime/work-context: **88 passed in 17.32s**, lưu `tests.log`.
- Source đã chuyển sang đọc stdout/stderr đồng thời, enforce cap khi đọc và
  cleanup/reap; tests output lớn và cancel đã có. Không còn vòng poll deadlock cũ.
- Default registry không đăng ký web; capability disabled trả lỗi trước fetch.
  Đây là vô hiệu hóa đường mặc định, **không phải đã triển khai network controls**.
- Schema không còn ép dict/list thành text, từ chối status 0 và nhiều trang.
- Binary sai version mới gặp bị từ chối; không còn fallback version giả ở nhánh
  lỗi đầu tiên. Vấn đề còn lại là cache identity ở các lần gọi sau.
- Recovery archive đọc trực tiếp, so hash toàn bộ file: **325 file hiện tại =
  325 regular files trong archive, không thiếu/thừa/khác byte**. SHA256 archive:
  `e883fcfa6f88325d0e80571956f21fb49006bc93855f9a1b6f671536f68ece0f`.
  Phép so đọc tar không giải nén hay thực thi nội dung archive. File permissions,
  symlink semantics và full migration acceptance không được suy ra từ so bytes.

## Findings còn lại

### P2 — Cache version/hash không gắn với binary đang chạy

`rat/crawler/spider_adapter.py:217-218` trả cache nếu đã xác minh một lần mà
không kiểm tra binary path/file identity hiện tại. `scrape_page` lại resolve
binary tại dòng 641 sau `verify_backend()`, nên file được cập nhật/thay hoặc
đường resolve thay đổi vẫn có thể chạy với provenance cũ.

Repro offline: verify fake binary v2.51.208; thay nội dung file cùng đường dẫn
thành fake v99.0.0; scrape tiếp được accepted, nhưng artifact vẫn ghi 2.51.208
và hash file cũ. `probe_results.json` có hash actual khác reported. Không có
network, initial URL validation được mock để chỉ kiểm tra identity contract.

Sửa: resolve một identity dùng nhất quán cho verify + execute; invalidate cache
khi file/path đổi, từ chối hoặc reverify trước fetch. Đừng chỉ trả hash mới sau
khi đã chạy binary chưa xác minh. Regression cho cùng path bị thay, đổi resolver
path và trường hợp file không đổi. Ghi đúng giới hạn race nếu chưa khóa được
identity trong khoảng verify/execute.

### P2 — DNS chưa được giới hạn; timeout socket toàn cục gây side effect

`spider_adapter.py:317-324` đặt `socket.setdefaulttimeout(2.0)` rồi gọi
`getaddrinfo`. Global socket timeout không giới hạn lời gọi DNS hệ thống; DNS
còn nằm ngoài monotonic deadline của `_execute_subprocess`. Lệnh verify version
cũng có budget 5s riêng; chưa có budget chung/cancel cho toàn thao tác.

Probe resolver giả mất 0.3s, adapter timeout 0.05s, executor/version được mock
để tách riêng pha DNS: lời gọi vẫn tiếp tục accepted sau 0.304s. Trong resolver,
global default đã bị đổi thành 2.0, ảnh hưởng cả socket được tạo bởi thread khác.
Đây là kiểm tra pha DNS với mocks, không phải số đo deadline của network thật.

Sửa: bỏ việc thay đổi socket default toàn tiến trình. Có cơ chế DNS bounded
phù hợp, truyền remaining deadline/cancel qua DNS/version/fetch; enforce caps
cho output `--version` nữa thay vì `capture_output` không giới hạn. Hoặc định
nghĩa rõ budget từng pha nhưng mỗi pha phải bounded/cancellable theo contract.
Test resolver chậm/lỗi/hủy và assert global socket timeout luôn giữ nguyên.

## Ý nghĩa cho debloat

Recovery data đã đủ cơ sở cho bước chuẩn bị tách, và backend binary không cần
cây Rust ở runtime. Tuy nhiên RAT mặc định **chưa dùng web tool** vì gate đang
tắt; đừng báo “người dùng đã dùng web an toàn” từ smoke opt-in. Per-hop network
enforcement vẫn backlog. Chưa có đích repo tách được chốt trong lượt này.

Hai P2 là lỗi identity/deadline của adapter, không phải lý do giữ toàn bộ Rust
vĩnh viễn. Sửa và verify nhỏ trong phạm vi hiện tại; sau đó chốt migration đích,
license/build provenance và mới gỡ cây nguồn. Chưa xóa gì, chưa claim giảm LOC.

Evidence: `probe_remaining.py`, `probe_results.json`, `tests.log`, `manifest.json`.
