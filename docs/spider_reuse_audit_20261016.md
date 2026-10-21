# Spider: tái sử dụng trước khi tách repo

Rà tĩnh ngày 2026-10-16. Mục đích: debloat các dự án ghép vào repo, giữ năng lực
có ích cho RAT là implementation CoT chính. Chưa tích hợp, build hay gọi web.

## Phần đáng dùng

| Năng lực | Công dụng trong RAT | Quyết định đề xuất |
| --- | --- | --- |
| Đọc một URL thành Markdown/text và lấy links | Người dùng đưa link; RAT đọc nội dung, dùng làm nguồn cho câu trả lời | Lát cắt đầu tiên, qua adapter gọi binary ngoài tiến trình |
| Crawl giới hạn trang/phạm vi | Nhập website tài liệu vào kho nguồn | Backlog sau khi một URL chạy đúng |
| HTML → Markdown/text offline | Chuẩn hóa trang đã lưu | Tái dùng cùng backend nếu đã cần; không xây một engine thứ hai |
| Chrome rendering | Đọc trang cần JavaScript | Optional, chỉ bật theo nhu cầu |
| Agents, cloud, workers, browser automation và search providers | Các lớp điều khiển/hạ tầng bổ sung | Không đưa vào core hiện tại; giữ riêng để dùng sau |

RAT hiện có local-file indexing; trong các capability/engine đã rà không thấy
đường gọi Spider thực sự. Từ “spider” trong `context_engine.py` là từ đồng nghĩa
phục vụ truy xuất code, không phải tích hợp crawler. Không xem engine web này
là bản thay thế PDF/OCR hoặc local-file indexer.

## Phát hiện quyết định phương án tách

- Git theo dõi 321 tệp dưới `spider/`, trong đó 269 tệp nguồn có 123,868 dòng
  không trống. Đếm snapshot hiện tại, gồm code upstream; không phải mã nhóm viết.
- `spider/Cargo.toml` sai cú pháp: `[[example]]` nằm giữa mảng workspace members
  tại dòng 11. Python `tomllib` từ chối parse. Chưa có binary `spider` hay
  `spider-mcp` trên PATH tại lúc rà, nên chưa xác nhận chạy được.
- Manifest crate lõi ghi 2.52.0; CLI/MCP ghi 2.51.208. Đây là thông tin local,
  không phải khẳng định compatibility hay version nên cài. Chọn và pin một
  release/revision được kiểm tra khi làm adapter.
- CLI và MCP đều dùng crate ngoài `spider_transformations` cho chuyển đổi HTML.
  Không thể chỉ copy `transform.rs` rồi coi đó là module độc lập không dependency.
- CLI xuất object bằng `serde_json::to_string_pretty`: dù README nói JSONL,
  object có thể trải nhiều dòng. Adapter phải parse JSON stream có giới hạn,
  không dùng `json.loads` trên từng dòng một cách máy móc.
- `spider_mcp` có scrape một trang (`with_limit(1)`), trả URL, status, content và
  links. Có sẵn MCP server không đồng nghĩa RAT có MCP client tích hợp.
- Feature mặc định CLI bật Chrome/WARC/cloud; MCP bật Chrome/cloud. Một bản
  chạy HTTP không tự chứng minh dependency/build đã tối giản. Cần kiểm tra
  feature flags thực tế của release được chọn; không tự bật cloud.
- `spider/examples/cv_job_crawler.rs` là ví dụ nhắm job board, ghi JSONL, không
  phải adapter RAT. Bảo toàn file cùng các thay đổi local khi chuyển repo;
  nguồn gốc và chênh lệch upstream chưa được đối chiếu.
- Các crate được rà khai báo MIT và có license trong cây nguồn; giữ provenance
  và license notices khi phân phối phần tái sử dụng.

## Hợp đồng adapter đã triển khai (2026-10-16)

Đã hoàn thành lát cắt adapter đầu tiên độc lập với cây nguồn nhúng:
- **Adapter**: `rat/crawler/spider_adapter.py` gọi binary ngoài tiến trình (`rat/bin/spider`, Spider CLI v2.51.208), không import mã Rust nhúng hay đường dẫn `spider/target/`.
- **Capability & Tool**: `rat/kernel/capabilities/web.py` đăng ký operation `read_web_page` trong `build_default_registry()`. Tool trả về kết quả cấu trúc và lưu artifact `web_page_snapshot` với `requested_url`, `final_url`, `status_code`, `content`, `content_hash` (SHA256), `links`, và `engine_version`.
- **Bảo mật & SSRF**: `SpiderAdapter.validate_url()` kiểm tra scheme (chỉ http/https), phân giải DNS và chặn triệt để loopback (127.0.0.0/8, ::1), mạng nội bộ (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7), link-local (169.254.0.0/16, fe80::/10), cloud metadata (169.254.169.254, metadata.google.internal) và địa chỉ không xác định. Môi trường subprocess được cô lập, tước bỏ toàn bộ `SPIDER_CLOUD_*` keys và cookies.
- **Xử lý luồng JSON**: `parse_output()` sử dụng `json.JSONDecoder.raw_decode` để phân tích chính xác JSON nhiều dòng pretty-print của Spider CLI. Hỗ trợ deadline/timeout, cancel callback, giới hạn buffer 2MB và cắt ngắn nội dung quá dài (`truncated=True`).
- **Xác minh & Smoke**:
  - 26/26 tests trong `tests/test_spider_adapter.py` vượt qua với fake binary.
  - Live smoke trên binary thật với URL `https://example.com`: HTTP 200, 171 ký tự, 0.61s, artifact được lưu thành công vào `ArtifactStore` (xem `audit/spider_rat_adapter_20261016/`).
  - Khi thiếu binary, capability báo thiếu dependency trung thực, không làm sập RAT; luồng đọc tệp cục bộ (`read_document`) vẫn hoạt động bình thường.

## Điều kiện gỡ cây nguồn nhúng

1. **Đã đạt**: Pin backend và làm adapter nhỏ; kiểm tra hoàn toàn không dựa vào đường dẫn `spider/`.
2. **Cần chuẩn bị**: Kiểm kê toàn bộ 321 tệp của `spider/` (gồm `examples/cv_job_crawler.rs` và các thay đổi local), tạo manifest tách và xác định đích repo độc lập trước khi xóa khỏi repo chính.
3. **Cần xác nhận**: Chưa gỡ cây `spider/` ở mốc này theo yêu cầu; footprint nguồn hiện vẫn giữ nguyên cho đến khi người dùng chốt đích repo tách.

