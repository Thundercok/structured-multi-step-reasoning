# Follow-up sau independent review r7 — 2026-10-20

Đọc `audit/rat_overnight_sweep_codex_review_r7_20261020/review.md` và
`failed_request_cases.json` trước khi sửa. F1/F2 đã được xử lý trên các ca cũ;
không cần mở lại parser, legacy path matching hay current/history counters.
Chỉ còn một finding P2 ở báo cáo kết quả của request mới:

**G1 — attempts bị mô tả thành successful/verified dù request trả exception.**
Trong `scripts/run_native_performance_session.py:445–447`, status và note chỉ
dựa vào `new_real_executed`, trong khi gate ngay sau đó có kiểm status success.
Actual reporting block với 12 request records đều exception sinh đồng thời:

- `scope_status = backend_inference_verified_12_calls`;
- note khẳng định `12 successful backend requests`;
- `all_12_requests_succeeded = false`.

Với một exception, note vẫn claim `1 successful backend requests`. Hai success
controls pass. Đây là fixture tổng hợp chạy đúng AST nhánh báo cáo, không khởi
tạo real backend, không gọi model và không làm sai lệch ledger lịch sử.

Tính success/failure của current run trước khi viết status và note. Chỉ ghi
verified khi đúng điều kiện thành công; báo attempts và outcomes đúng ở ca lỗi
hoặc hỗn hợp. Giữ executed/attempt counters và budget accounting hiện tại,
không chuyển budget sang chỉ đếm successful requests. Giữ 12-call baseline cũ
nguyên vẹn; finding không phủ nhận 12 calls lịch sử đã review.

Chạy lại đúng probe mới (không cần model):

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  audit/rat_overnight_sweep_codex_review_r7_20261020/test_failed_request_reporting.py -q
```

Nếu refactor reporting helper, có thể điều chỉnh cách gọi AST thành helper hoặc
fake-only integration tương đương, giữ assertions về failed/successful outcomes.
Giữ bộ 327 cũ, năm fake/guard scenarios và checks parser/backend/scoring; 29
NCKH là subset, không cộng trùng. Giữ native bfloat16 skip đúng nếu môi trường
không hỗ trợ, không gọi model thật để làm software checks xanh.

Legacy whitelist `(call_index,timestamp_utc)` hiện khớp đúng 12 record của ledger
đã review và hash gốc không đổi. Gọi nó là request identity whitelist/mapping,
không gọi là chữ ký số mật mã. Không cần mở rộng thành hệ thống ký artifact để
sửa G1 trong trusted-local-ledger scope.

Tạo folder repair mới; giữ tất cả audit evidence cũ immutable, không chạy
runner đè vào review folders. Chỉ sửa phần cần thiết; giữ các thay đổi từ chat
khác, không restore source snapshot lên checkout. Main, không commit/branch/
push/pull/reset, không thêm real-model budget, không thay research freeze/Stage 0.
Handoff cần diff/source hashes, commands/env, raw logs/JUnit, outcomes và scope
native chưa đo; không claim quality/native acceptance từ số software tests.
