# Antigravity — tận dụng Spider cho RAT trước khi debloat

## Nhiệm vụ

Triển khai lát cắt nhỏ: **người dùng đưa một URL public → RAT đọc trang qua
Spider → tạo bản chụp có nguồn → trả lời dựa trên nội dung đã đọc**. Tái sử dụng
crawler hiện có, không viết lại crawler hoặc nhận bảo trì cả workspace upstream.
Làm code và kiểm tra đến mức review được, không chỉ trả về kế hoạch.

Đọc trước `AGENTS.md`, `docs/project_scope.md`, `docs/spider_reuse_audit_20261016.md`
và các hợp đồng runtime/kernel hiện hành. Repo có nhiều thay đổi chưa commit từ
các chat khác: kiểm tra status và giữ nguyên chúng. Làm trên `main`; không tạo
branch, push/pull/reset/force hoặc gom commit ngoài phạm vi yêu cầu này.

Mục tiêu chat là **debloat các dự án ghép vào repo bằng cách tái sử dụng phần có
ích, đưa phần dư vào backlog rồi tách repo**. RAT là implementation chính của
CoT/structured reasoning, không phải demo phụ để bỏ. Không chuyển sang mở rộng
nghiệp vụ hóa đơn, UI trang trí hay thiết kế chiến dịch nghiên cứu mới.

## Kết quả hiện trạng đã rà

- RAT có local-file indexing; chưa có đường gọi Spider trong capability/engine
  được rà. Từ “spider” trong `context_engine.py` chỉ phục vụ tìm code.
- Cây `spider/` có 321 tệp tracked; 269 tệp nguồn, 123,868 dòng không trống.
  Đây là snapshot, không phải toàn bộ do nhóm viết.
- `spider/Cargo.toml` sai cú pháp ở dòng 11: `[[example]]` lẫn trong mảng members.
  Không giả định `cargo build` từ cây này chạy được. Chưa có binary được xác nhận.
- Crate lõi local ghi 2.52.0; CLI/MCP ghi 2.51.208. Kiểm tra dependency/version
  thực tế, không suy ra chúng tương thích chỉ vì cùng major.
- CLI/MCP dùng dependency ngoài `spider_transformations`. Copy riêng wrapper
  Rust không loại bỏ dependency này.
- CLI serialize bằng `serde_json::to_string_pretty`: output không bảo đảm mỗi
  object nằm trên một dòng, dù README dùng tên JSONL.
- CLI mặc định bật Chrome/WARC/cloud; MCP mặc định bật Chrome/cloud. Không ngầm
  bật những phần đó cho mốc một URL HTTP.
- Bảo toàn `spider/examples/cv_job_crawler.rs` và các local changes trước khi tách.
  Nguồn gốc/chênh lệch với upstream của cây hiện tại chưa được xác minh đầy đủ.

## Phạm vi triển khai

### 1. Adapter backend độc lập với cây nguồn nhúng

Ưu tiên Python adapter gọi binary Spider ngoài tiến trình. Chọn và pin một
release/revision cùng feature flags thực sự chạy được. Có thể build backend
trong khu vực tách biệt; không dùng `spider/target/...` làm đường dẫn bắt buộc
của RAT. Ghi lại version, nguồn, cách cài và license notices cần giữ.

Không tự chọn thêm backend không phải Spider chỉ để làm test xanh. Khi thiếu
binary, capability phải báo thiếu dependency rõ ràng; RAT vẫn khởi động và tìm
tệp local bình thường. Không auto-install/download/build trong startup hoặc
trong lượt chat của người dùng. Không thêm MCP client tổng quát nếu subprocess
adapter đã đủ; không nối Spider Agent làm controller cạnh tranh với RAT.

Adapter cần deadline/cancel, giới hạn stdout/stderr, dung lượng nội dung và
chỉ một trang. Parse JSON nhiều dòng/stream đúng định dạng backend được pin;
phân biệt lỗi binary, timeout, HTTP lỗi, schema sai, nội dung rỗng và cắt ngắn.
Chạy bằng argv, không shell interpolation. Không kế thừa API key, cookie hoặc
chế độ cloud từ môi trường một cách ngầm định; không ghi secrets vào artifacts.

### 2. Hợp đồng nguồn web và tích hợp RAT

Tận dụng registry/dispatcher/artifact/view contracts hiện có. Tên operation
có thể là `read_web_page`; đối chiếu naming hiện hành trước khi chốt. Nối vào
tool loop thực tế, không chỉ thêm một hàm không được runtime sử dụng. Không
thêm cửa sổ hoặc một luồng chat riêng cho web. Không dùng keyword router hoặc
prompt trả lời dựng sẵn thay cho tool execution thật.

Artifact giữ URL yêu cầu, URL cuối nếu biết, thời điểm lấy, trạng thái HTTP nếu
có, engine/version, nội dung đã thu, hash bản chụp và trạng thái cắt ngắn/lỗi.
Trường backend không cung cấp phải để unknown, không tự bịa URL cuối/status.
Lưu bản chụp theo artifact store phù hợp để câu trích dẫn không phụ thuộc trang
live thay đổi. Giữ revision/provenance khi tham chiếu từ câu trả lời.

Không đặt URL vào trường file-path rồi gọi các thao tác file local, không tự
lập chỉ mục mọi trang vào kho tệp cá nhân. Nội dung web là dữ liệu không tin
cậy, không phải system instructions. Model chỉ được nói đã đọc khi tool đã
trả nội dung thành công; lỗi phải hiện trung thực. Citation trỏ về URL và bản
chụp đúng nguồn; không gán độ tin cậy hoặc kết quả CoT chưa được đo.

Mốc này chỉ hỗ trợ URL public HTTP(S) do người dùng cung cấp. Kiểm tra scheme,
host/IP và redirect; chặn loopback/private/link-local/metadata destinations.
Phải kiểm soát được từng hop và việc crawl theo link bằng backend hoặc lớp
network phù hợp. Nếu binary không cung cấp khả năng đó, không gọi preflight
DNS/URL check là bảo vệ đầy đủ: ghi rõ hạn chế và giữ network tool chưa được
bật mặc định cho model đến khi có biện pháp kiểm chứng được. Không dùng một
request HTTP phụ không giới hạn để “kiểm tra trước” rồi lại fetch độc lập.

### 3. Những thứ để backlog

Crawl nhiều trang, lịch crawl, nhập cả website vào index, Chrome rendering,
cloud, workers, distributed crawling, search providers và Spider Agent.
DocAI vẫn standalone; PDF/OCR shared hiện có không bị thay đổi. Không đụng
research harness, dataset, model defaults hay Stage 0.

## Kiểm tra bắt buộc theo hành vi

- Unit/contract bằng binary giả/fixture: JSON pretty nhiều dòng, lỗi schema,
  timeout/cancel, output vượt giới hạn, HTTP lỗi/rỗng và provenance/hash.
- URL/redirect: scheme không hợp lệ, private IP/host, redirect sang địa chỉ bị
  chặn, giới hạn số hop/trang; test phải bao phủ lớp thực sự chặn network.
- Runtime scripted: yêu cầu có URL đi qua registry/dispatcher thật, tạo artifact
  đúng; lỗi/thiếu binary không sinh lời khẳng định đã đọc. Local-file flow và
  khởi động không có binary vẫn hoạt động, không cần Qt cho adapter tests.
- Smoke binary Spider thật trên trang public được phép: lưu command, version,
  exit status, raw output và artifact. Phân biệt với tests dùng fake binary.
  Không scrape tệp cá nhân, cookies hoặc trang đăng nhập. Không chạy campaign
  model; scripted acceptance không phải bằng chứng model thật biết dùng tool.
- Chạy regression phù hợp với runtime/kernel bị đổi. Không gọi toàn bộ suite
  không liên quan chỉ để tăng số lượng tests. Nếu buộc phải đổi harness, đọc
  protocol và chạy bộ tests bắt buộc trong AGENTS; ưu tiên không đổi harness.

## Điều kiện debloat và bàn giao

Chưa xóa/chuyển `spider/` trong bước đầu này: chưa có đích repo tách được chốt
và chưa đối chiếu upstream/local changes. Sau khi adapter chạy độc lập, chuẩn
bị manifest tách gồm mọi tệp, hashes, license, local examples/changes, các nơi
còn tham chiếu cây nguồn và phương án phục hồi. Nêu rõ còn vướng gì để chuyển.
Không tạo repo remote hoặc publish code ngoài yêu cầu hiện tại.

Đo lại footprint nguồn được giữ/thêm/bỏ, tách product code, tests, fixtures,
audit và dependency bên ngoài. Không nói đã giảm 124k dòng khi chưa gỡ cây cũ;
không biến việc chuyển dependency ra ngoài thành giảm tổng chi phí runtime.

Viết `audit/spider_rat_adapter_20261016/` chứa manifest đầu/cuối, lệnh và kết
quả tests, smoke raw outputs, giới hạn còn lại và `handoff_codex.md`. Cập nhật
backlog/audit Spider đúng trạng thái. Báo cáo theo thứ tự: đã chạy được gì,
thay đổi file nào, kiểm tra gì, còn thiếu gì, sẵn sàng tách repo hay chưa.
Không khẳng định vượt gate, tăng accuracy hoặc tiết kiệm token từ tích hợp này.
