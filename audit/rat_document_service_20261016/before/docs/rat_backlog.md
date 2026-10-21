# RAT backlog

Updated: 2026-10-16, Asia/Ho_Chi_Minh.

Theo yêu cầu ngày 2026-10-13, bước RAT đang được bàn là **hoàn thiện một luồng
core xuyên suốt bằng ví dụ hội thoại DSA**, với minor UI chỉ chỉnh cách đọc
code, notes và khoảng cách. Chuột là nhân vật trang trí; chạm chỉ giãy/emote.
Notes thuộc từng lượt chat và không có panel riêng hoặc entry point qua Chuột.
Xem [kế hoạch hội thoại](rat_conversation_dsa_example_plan.md).
Baseline core/UI đã triển khai trong source và có regression phần mềm. Smoke
DSA development còn timeout và lỗi nội dung; chưa đạt chấp nhận toàn bộ luồng
bằng model thật. Một box chat và cùng trải nghiệm compact/full tiếp tục áp dụng.
Ưu tiên bài báo NCKH, research protocol và Stage 0 giữ nguyên.

## Vai trò RAT đã chốt — áp dụng cho mọi chat

RAT là **implementation ứng dụng chính của phương pháp CoT/structured reasoning**,
không phải demo phụ. Pipeline headless dùng để đánh giá phương pháp tái lập.
Ưu tiên và phân loại công việc theo [phạm vi dự án](project_scope.md): phần suy
luận, kiểm tra, điều phối, dừng và bằng chứng là core; giao diện phục vụ kiểm tra
hành vi có thể thuộc core, còn trang trí và tiện ích riêng là mở rộng. Không
đóng băng toàn bộ RAT chỉ vì ưu tiên NCKH. Đây là định hướng người dùng xác nhận,
không phải thông báo mọi khả năng đã hoạt động hay đã được đo bằng model thật.

## Ưu tiên hiện tại trong RAT

| ID | Kết quả cần đạt | Trạng thái | Phụ thuộc / điều kiện hoàn thành |
| --- | --- | --- | --- |
| RAT-UX-01 | Một box chat cho mọi chức năng, co giãn theo nội dung; compact/full dùng cùng bề mặt và cách thao tác. | Đã triển khai trong source và app chạy từ source | [Brief UI](rat_ui_fluidity.md). Bỏ khung lồng nhau và màn hình chức năng riêng; cần thử nội dung ngắn, hình và chi tiết ở cả hai mức. |
| RAT-UX-02 | Chuyển trạng thái và compact ↔ full liên tục, giữ draft/caret, focus, vị trí đọc, lựa chọn và task đang chạy. | Đã triển khai; có kiểm tra trạng thái Qt | Cùng brief; một nguồn trạng thái/composer. Toggle không submit, gọi model hoặc thực thi lại. |
| RAT-UX-03 | Kiểm tra trải nghiệm hai mục trên với người dùng qua một prototype tương tác. | Có prototype Qt và kiểm tra native; chờ phản hồi người dùng | Prototype ghi rõ dữ liệu mẫu; thử sửa/hủy/lỗi, toggle khi đang gõ/stream và reduced motion trước rollout. |
| RAT-UX-04 | Personality xuyên suốt một box chat; nhân vật Chuột bên trái là trang trí, chạm chỉ giãy/emote. | Đã tách click → notes trong source và có regression Qt; chờ native acceptance | [Hướng companion trong brief](rat_ui_fluidity.md). Giữ chuyển động vui vừa; notes có nguồn và thao tác trong từng lượt chat. |
| RAT-UX-05 | Thể hiện luồng suy luận và thực thi bên cạnh kết quả, có thể mở chi tiết. | Đã triển khai trong source | [Ngữ cảnh và trace](rat_companion_work_context.md). Phân biệt dự định với thao tác đã chạy, lỗi/dừng/thiếu dữ kiện; không hiển thị raw/private reasoning. |

Không gán deadline hoặc effort chưa được ước lượng. Source đã cập nhật ngày 2026-10-12; chưa build lại bản đóng gói. Bằng chứng và giới hạn: [audit UI](../audit/rat_one_box_ui_20261012/REPORT.md) và [audit companion](../audit/rat_companion_reasoning_20261012/REPORT.md).

## Backlog kiến trúc

| ID | Hướng phát triển | Trạng thái | Phụ thuộc / bằng chứng cần có |
| --- | --- | --- | --- |
| RAT-AI-01 | Model điều khiển làm rõ, tiếp tục, đổi ý và tham chiếu công việc. | Backlog | [ADR-002](adr-002-rat-adaptive-interaction.md); cần kiểm tra model thật, không chỉ scripted tool calls. |
| RAT-AI-02 | Model ghép phần kết quả và UI khai báo theo yêu cầu, hỗ trợ nhiều artifact/revision. | Có lát cắt bảng tham chiếu nguồn trong source; phần rộng hơn vẫn backlog | `compose_result_table` ghép các ô từ artifact/revision thật; có regression phần mềm. Chưa review model thật, chưa sinh UI phong phú hoặc xác nhận độ đúng diễn giải. [Phạm vi triển khai](rat_book_features.md). |
| RAT-AI-03 | Phối hợp lịch, tài liệu và phép biến đổi dữ liệu để xử lý yêu cầu chưa có workflow riêng. | Backlog | Dữ liệu và thao tác thực, đánh giá yêu cầu mới; tránh thêm một màn hình riêng cho mỗi ví dụ. |
| RAT-AI-04 | Model đề xuất recipe, thành phần hoặc logic mới trong môi trường tách biệt. | Xa hơn | Sau nền tảng và evidence phù hợp; chưa chọn runtime/SDK hoặc triển khai code tùy ý. |

## DocAI — giữ độc lập, dùng sau

**DOCAI-01 — Hoãn theo yêu cầu ngày 2026-10-16.** Giữ module ở
`modules/docai/` cùng dependencies, CLI và tests riêng. Người dùng hiện không
có nhu cầu đọc hóa đơn; chưa nối XML, sinh ứng viên số hoặc solver hóa đơn Z3
vào RAT hay pipeline CoT. Chỉ mở lại khi có yêu cầu sử dụng cụ thể.

Thư viện `document_intake/` đã hợp nhất PDF, Apple Vision và Tesseract tiếp tục
được dùng chung; việc giữ DocAI độc lập không hoàn tác phần tái sử dụng này.
Giữ source, tests, raw artifacts và bản phục hồi hiện có. Không mở chiến dịch
model hoặc thay đổi Stage 0 từ mục backlog này.

## Spider — tái sử dụng trước khi tách repo

**SPIDER-01 — Đã triển khai lát cắt adapter một URL (2026-10-16).** Đã hoàn thành
Python adapter `rat/crawler/spider_adapter.py` gọi binary ngoài tiến trình độc lập
với cây nguồn (`rat/bin/spider`, CLI 2.51.208), cùng capability `web` (`read_web_page`)
tạo artifact `web_page_snapshot` có nguồn URL, HTTP status và SHA256 content hash.
Đã kiểm tra 26 unit/contract tests với fake binary và live smoke trên `https://example.com`
thành công (0.61s, HTTP 200). Các phần nâng cao: crawl nhiều trang, crawl lịch trình,
nhập website vào index, Chrome rendering, cloud, workers và Spider Agent được đưa
vào backlog để xử lý sau khi tách repo `spider/`.


## Thay đổi ưu tiên

Ngày 2026-10-14, người dùng yêu cầu thêm tìm nội dung/số trang trong PDF trên
máy, một chức năng được đề xuất và một mục từ backlog. Source đã có tìm từng
trang PDF, đọc đúng trang kèm nguồn trích dẫn, và bảng ghép dữ liệu có tham
chiếu nguồn từ RAT-AI-02. Cả ba dùng cùng ô chat. Đây là bổ sung ứng dụng;
không coi software tests là bằng chứng model đã điều phối được luồng mới.
Chi tiết, cách thử và giới hạn ở [tài liệu chức năng](rat_book_features.md).

Ngày 2026-10-12, ADR-002 được đưa vào backlog để ưu tiên UI. Ngày 2026-10-13,
người dùng yêu cầu chuyển sang hoàn thiện công việc thật, dùng DSA làm ví dụ
cho luồng chung. Minor UI và tương tác trang trí đã chốt; baseline core/UI đã
kiểm tra phần mềm, không thêm một chức năng DSA riêng. Smoke model đã lưu còn
lỗi; kết quả phần mềm hoặc UI không tự chứng minh RAT có năng lực AI mới.

Các bộ tính, artifact store, dispatcher và bằng chứng review hiện có giữ vai
trò nền tảng. Đợt UI đã cập nhật app chạy từ source. Cấu hình model, các mục RAT-AI và pipeline nghiên cứu chưa thay đổi.

Người dùng đã cho triển khai persona, ngữ cảnh công việc và luồng các bước.
Ghi chép theo phiên, continuation giữ kết quả và chọn tập kết quả thật đã có
contract và Qt kiểm tra. Đây là nền tảng nối với RAT-AI-01/02/03; presentation
vẫn dùng renderer đã đăng ký, chưa sinh UI tùy ý. Các mục kiến trúc vẫn ở backlog,
cần model thật xử lý yêu cầu mới và review kết quả. Thử phát triển 1.5B cho thấy
model có thể nói đã ghi/sửa mà chưa thực thi; không coi software tests là bằng
chứng năng lực. Cấu hình model mặc định, pipeline NCKH và Stage 0 giữ nguyên.

## Ưu tiên cuối cùng: đánh giá chuyển giao diện sang Qt Quick/QML

**RAT-ARCH-05 — Hoãn, xếp sau các mục RAT còn lại**, theo yêu cầu người dùng
ngày 2026-10-15. Tiếp tục dùng PyQt hiện tại; chưa làm bản thử hoặc chuyển
framework trong đợt công việc hiện tại.

Khi đến lượt, thử riêng Workbench gồm Chuột, hai bong bóng, ô nhập và thẻ file,
giữ engine Python hiện có. Mục tiêu nền tảng là macOS, Windows và Linux.
So sánh với bản hiện tại về thời gian hiện cửa sổ/gõ được, độ mượt animation,
CPU/RAM khi chờ và dung lượng toàn bộ bản đóng gói, gồm cả backend. Chỉ quyết
định chuyển tiếp khi có số đo và kiểm tra tương tác trên các nền tảng; chưa
coi Qt Quick/QML hoặc việc đổi Python binding là bằng chứng app sẽ nhanh hơn.
