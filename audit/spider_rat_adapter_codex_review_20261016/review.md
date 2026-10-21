# Spider adapter — Codex review, 2026-10-16

Verdict: **request changes; chưa sẵn sàng debloat cây nguồn Spider**.
Không sửa product source trong lượt review này. Phạm vi là thay đổi Spider;
runtime chứa thay đổi của chat khác nên không quy mọi diff runtime cho Spider.

Đã chạy lại suite adapter/runtime/work-context: **73 passed in 13.03s**.
Đã đọc raw smoke example.com do Antigravity lưu, không chạy lại network smoke.
Smoke đó chứng minh một trang nhỏ đã đọc được, không bao phủ các lỗi dưới đây.

## Findings

### P1 — Default web tool chưa kiểm soát được nơi kết nối thực tế

`rat/crawler/spider_adapter.py:280` chỉ kiểm tra DNS trước khi khởi chạy một
tiến trình tự resolve/fetch; argv ở dòng 285 không kiểm soát redirect. Cấu hình
upstream và bản source dùng build có `RedirectPolicy::Loose` mặc định.
`rat/kernel/capabilities/__init__.py:31` vẫn đăng ký tool mặc định.

URL ban đầu public có thể redirect sang địa chỉ nội bộ; việc kiểm tra trước
cũng không ràng buộc IP của kết nối sau đó. `limit=1` giới hạn trang trả về,
không bảo vệ các hop. Không có test trên lớp network thực sự chặn redirect.
Handoff trước đã yêu cầu giữ tool chưa bật mặc định nếu chưa có kiểm soát này.

Sửa: chặn mặc định việc thực thi network tool chưa đạt yêu cầu, hoặc triển khai
kiểm soát connection/redirect được kiểm chứng cho mỗi hop. Post-validate URL sau
khi tải không hoàn tác được request. Không chỉ thêm một preflight HTTP request.

### P1 — Chờ process thoát trước khi đọc pipe làm trang bình thường timeout

`spider_adapter.py:342-348` gọi `communicate()` sau khi `poll()` đã trả exit
code. Child ghi đầy pipe sẽ chờ parent đọc, trong khi parent chờ child thoát.
Cap stdout tại dòng 356 chỉ kiểm tra sau đó; stderr không có cap. Timeout/cancel
kill process nhưng không reap/đóng pipes trong finally.

Repro `probe_adapter.py`: fake binary trả một object JSON hợp lệ chứa 200,000
ký tự, dưới cap 2 MB; kết quả `SpiderTimeoutError` sau 3.023 giây. Không có
network. Fake được chạy với `-S` để giảm ảnh hưởng startup/site packages.

Sửa: đọc đồng thời stdout/stderr trong khi process chạy; enforce byte caps khi
đọc, deadline monotonic và cleanup/wait trong mọi nhánh. DNS và truy vấn version
cũng phải có budget rõ ràng, không chỉ vòng poll. Test output lớn vẫn dưới cap,
stderr lớn, vượt cap, mid-flight cancel và cleanup.

### P2 — Schema sai được biến thành nguồn đã đọc

`spider_adapter.py:376-390` cho phép status 0, content object qua `str(...)` và
URL trả về tùy ý. Probe fake trả content là dict, HTTP 0 và URL loopback; adapter
vẫn accepted. Đây là phép thử parser, không phải exploit network: initial URL
validation được mock; không có request nào tới loopback.

Kết quả bị coercion có thể được capability gắn `found/read=true` rồi dùng làm
bằng chứng. Sửa: kiểm tra schema/types, URL/source correspondence và semantics
status của backend đã pin; từ chối nhiều page ngoài hợp đồng một trang. Không
chuyển object/list thành prose. Unknown phải giữ unknown, không giả định thành công.

### P2 — Version không được pin; fallback có thể bịa provenance

`spider_adapter.py:161-178` chỉ đọc version sau scrape và chấp nhận bất kỳ chuỗi
chứa “spider”; khi lỗi lại ghi version constant. Probe chấp nhận `spider_cli
99.0.0`; version output không hợp lệ bị ghi thành `2.51.208`. Hằng số không phải
kiểm tra backend pin. Lệnh version còn chạy với inherited env khác lệnh scrape.

Sửa: xác minh backend/version trước request, báo mismatch/unknown trung thực,
pin và ghi hash binary/build provenance khi cần; dùng cùng env/deadline contract.

## Debloat và số đo

- 123,868 là dòng không trống của **source files**; 139,745 trong handoff là
  dòng đếm ở **mọi tệp tracked đọc như text**. Không phải cùng mẫu số và không
  phải đã giảm/thêm từng ấy product code. Khi đo lại, dùng cùng extension rules.
- Binary khoảng 20.7 MB là dependency/runtime footprint; scratch build khoảng
  1.9 GB là generated build material tại lúc review. Không tính bản copy build
  là mã tự viết hay claim repo đã gọn khi cây gốc còn nguyên.
- Manifest tách hiện chỉ kiểm kê tracked files. Trước migration cần inventory
  mọi local/untracked changes cần giữ, xác minh gói phục hồi thực sự khôi phục
  được và đích repo. `git archive HEAD` không chứa uncommitted/untracked content.
- Chưa thay pipeline nghiên cứu, không có kết luận model quality hay Stage 0.

Evidence: `tests.log`, `probe_adapter.py`, `probe_results.json`, `manifest.json`.
Sửa và bàn giao lại trước khi đánh dấu acceptance hoặc xóa/tách `spider/`.
