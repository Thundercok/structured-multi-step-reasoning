# Spider — Codex review vòng 3, 2026-10-16

**Kết luận theo phạm vi:** chấp nhận bước chuẩn bị tách source Spider, với web
tool tiếp tục tắt mặc định. Binary identity và deadline trả về cho caller đã
được sửa. Chưa chấp nhận tuyên bố DNS worker bị dừng/dọn hết khi timeout; còn
một P2 về lifecycle tài nguyên trước khi đưa network tool vào sử dụng thường lệ.
Không giữ toàn bộ workspace Rust chỉ vì vấn đề Python adapter này.

## Đã kiểm tra

- Hash của 5 tệp adapter/capability/registry/tests khớp manifest bàn giao.
- Suite adapter/runtime/work-context chạy lại: **93 passed in 17.83s**.
  Bao gồm regression binary bị thay, cache không đổi, DNS timeout/cancel,
  output cap cho version và default registry gate.
- Đã đối chiếu code: verify và execute dùng cùng resolved path; identity cache
  ràng buộc path/stat/hash; không còn fallback version giả. Khoảng race sau
  kiểm tra file trước exec còn được ghi nhận, không coi là atomic execution.
- Không còn thay đổi `socket.setdefaulttimeout`; DNS và version/fetch nhận
  deadline; version dùng reader có cap. Đây là deadline trên các pha được
  kiểm tra, không bảo đảm mọi syscall/filesystem operation có hard deadline.
- Archive vẫn khớp byte toàn bộ **325 file hiện tại**, không thiếu/thừa.
  SHA256: `e883fcfa6f88325d0e80571956f21fb49006bc93855f9a1b6f671536f68ece0f`.
- Không gọi web/model và không chạy lại smoke online. Không sửa product source,
  không xóa source/scratch/archive, không Git publish trong lượt này.

## P2 còn lại — Resolver workers tồn tại sau timeout

`rat/crawler/spider_adapter.py:327-346` tạo một ThreadPoolExecutor mới mỗi lần
DNS. `shutdown(wait=False, cancel_futures=True)` chỉ hủy việc chưa bắt đầu,
không ngắt `socket.getaddrinfo` đang chạy. Vì thế response của caller bounded,
nhưng số worker đang chờ có thể tăng theo số retry; ThreadPoolExecutor còn có
thể chờ các worker lúc interpreter shutdown.

Repro offline `probe_dns_workers.py`: mock resolver chờ Event, gọi 6 lần với
deadline 40 ms; cả 6 timeout nhưng còn 6 worker sống. Probe sau đó release Event
và join toàn bộ worker, kết thúc với 0 worker; không để lại process/thread chờ.
Đây không phải đo DNS thật hay một request mạng.

Hướng sửa giới hạn trong adapter: resolver service có trần in-flight/queue và
admission rõ ràng, không tạo executor không giới hạn theo từng retry. Nếu yêu
cầu dừng hẳn resolver khi hủy/thoát, dùng isolation có thể terminate/reap hoặc
DNS API cancellable. Đừng chỉ tăng timeout, dùng daemon flag rồi tuyên bố đã
cancel syscall, hoặc đổi global socket defaults. Test nhiều timeout liên tiếp
và shutdown ngoài kiểm tra latency một lời gọi. Ghi rõ giới hạn nếu chỉ giới
hạn concurrency mà không dừng được system resolver đang chạy.

## Điều kiện tiếp theo để debloat

1. Giữ web default-disabled; không gọi smoke opt-in là end-user acceptance.
2. Chọn đích repo riêng và bảo toàn source/license/local changes, archive và
   build provenance. Kiểm tra chế độ cài binary không dựa vào cây `spider/`.
3. Gỡ source nhúng sau khi bản tách được xác minh; báo mức giảm source riêng với
   disk footprint. Không đồng thời xóa recovery material hoặc scratch tùy tiện.
4. P2 DNS lifecycle được theo dõi riêng và cần giải quyết trước bật web rộng rãi;
   per-hop connection/redirect control vẫn là backlog độc lập.

Chưa có claim giảm LOC thực tế, tăng chất lượng CoT hay thay đổi Stage 0.
Evidence: `tests.log`, `manifest.json`, `probe_dns_workers.py`,
`dns_worker_results.json`.
