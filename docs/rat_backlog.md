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

**RAT-FIND-01 — Advanced Spotlight finder ngay trong khung chat.** Theo yêu cầu
người dùng ngày 2026-10-16. Đã có lát cắt headless: catalog ứng dụng macOS theo
tên/alias, tìm metadata/FTS trước, API bổ sung ngữ nghĩa và coordinator chỉ giữ
truy vấn mới nhất. Xem [triển khai backend](rat_progressive_finder_20261016.md).
UI/composer, mở ứng dụng và bộ điều phối CoT mới chưa được nối trong lát cắt này.
Tìm và lọc tệp local, xem trước, chọn nguồn để hỏi tiếp, mở tệp hoặc hiện trong
Finder ngay trong cùng cuộc trò chuyện/composer. Tái sử dụng index, quyền và
artifact/nguồn hiện có; phân biệt kết quả tìm thấy với nội dung thực sự đã đọc.
Mục tiêu sử dụng offline, phản hồi tìm kiếm nhanh; chỉ gọi model khi tác vụ cần.
Thiết kế chi tiết và acceptance cho bàn phím, lọc kết quả, chọn tệp và tiếp nối
hội thoại sẽ chốt trong lần làm sau. Không thêm một cửa sổ/chế độ tìm kiếm mới
hoặc mở rộng indexing cá nhân trong lát cắt backend này.

| ID | Hướng phát triển | Trạng thái | Phụ thuộc / bằng chứng cần có |
| --- | --- | --- | --- |
| RAT-AI-01 | Model điều khiển làm rõ, tiếp tục, đổi ý và tham chiếu công việc. | Backlog | [ADR-002](adr-002-rat-adaptive-interaction.md); cần kiểm tra model thật, không chỉ scripted tool calls. |
| RAT-AI-02 | Model ghép phần kết quả và UI khai báo theo yêu cầu, hỗ trợ nhiều artifact/revision. | Có lát cắt bảng tham chiếu nguồn trong source; phần rộng hơn vẫn backlog | `compose_result_table` ghép các ô từ artifact/revision thật; có regression phần mềm. Chưa review model thật, chưa sinh UI phong phú hoặc xác nhận độ đúng diễn giải. [Phạm vi triển khai](rat_book_features.md). |
| RAT-AI-03 | Phối hợp lịch, tài liệu và phép biến đổi dữ liệu để xử lý yêu cầu chưa có workflow riêng. | Backlog | Dữ liệu và thao tác thực, đánh giá yêu cầu mới; tránh thêm một màn hình riêng cho mỗi ví dụ. |
| RAT-AI-04 | Model đề xuất recipe, thành phần hoặc logic mới trong môi trường tách biệt. | Xa hơn | Sau nền tảng và evidence phù hợp; chưa chọn runtime/SDK hoặc triển khai code tùy ý. |

## DocAI — giữ độc lập, dùng sau

**DOCAI-01 — Hoãn; source dư đã gỡ theo yêu cầu ngày 2026-10-17.**
`modules/docai/` đã được đóng gói phục hồi và gỡ khỏi cây source. Người dùng hiện không
có nhu cầu đọc hóa đơn; chưa nối XML, sinh ứng viên số hoặc solver hóa đơn Z3
vào RAT hay pipeline CoT. Chỉ mở lại khi có yêu cầu sử dụng cụ thể.

Thư viện `document_intake/` đã hợp nhất PDF, Apple Vision và Tesseract tiếp tục
được dùng chung; việc giữ DocAI độc lập không hoàn tác phần tái sử dụng này.
Giữ source, tests, raw artifacts và bản phục hồi hiện có. Không mở chiến dịch
model hoặc thay đổi Stage 0 từ mục backlog này.

## Spider — tái sử dụng trước khi tách repo

**SPIDER-01 — Đã sửa và hoàn thiện lát cắt adapter sau Codex review (2026-10-16).**
Đã hoàn thành Python adapter `rat/crawler/spider_adapter.py` gọi binary ngoài tiến trình
độc lập (`rat/bin/spider`, CLI 2.51.208), cùng capability `web` (`read_web_page`)
tạo artifact `web_page_snapshot` có nguồn URL, HTTP status và SHA256 content hash.
Sau Codex review vòng 1, đã giải quyết triệt để:
1. **Network destination control (P1)**: default registry fail-closed gate (`enable_web=False`); capability tắt mặc định khi backend thiếu per-hop redirect/destination control.
2. **Pipe deadlock (P1)**: đọc đồng thời bằng `selectors.DefaultSelector` non-blocking, enforce cap 2MB stdout/512KB stderr, deadline monotonic và cleanup/reap trong mọi nhánh.
3. **Schema & status validation (P2)**: yêu cầu kiểu `str` nghiêm ngặt (không coercion dict), status $\in [100, 599]$ (loại status 0), hợp đồng 1 trang, source validation loại loopback.
4. **Version verification (P2)**: kiểm tra `spider_cli 2.51.208` trước khi scrape với sanitized env, từ chối mismatch/unknown, không bịa fallback.
Đã kiểm tra 41 unit/contract tests, 88 regression tests, 17 UI tests và live smoke real-binary trên `https://example.org` (HTTP 200).
Cây nguồn `spider/` (321 tệp, 123.868 dòng Rust) và `release.sh` được kiểm kê đầy đủ, gói phục hồi `scratch/spider_migration_bundle.tar.gz` đã kiểm chứng khôi phục 100%, bảo lưu nguyên vẹn chờ tách repo.


## Spider — kết luận review debloat ngày 2026-10-16

Source-separation preparation đã được Codex review vòng 3: 93 tests pass;
archive khớp byte 325/325 file. Binary identity và deadline caller đã sửa;
web tool tiếp tục tắt mặc định. Chưa gỡ source, chưa có đích repo được chốt.
Xem [review vòng 3](../audit/spider_rat_adapter_codex_review_round3_20261016/review.md).

**SPIDER-02 — DNS worker lifecycle (P2), trước khi bật web sử dụng thường lệ.**
Timeout/cancel trả về cho caller nhưng không ngắt system resolver đang chạy;
executor mới mỗi request có thể làm tích lũy worker qua retries. Cần trần
in-flight/queue và hành vi shutdown rõ ràng, hoặc isolation cancellable nếu
cần hard cancellation. Probe offline tái hiện 6 timeout còn 6 worker chờ;
probe đã release/join toàn bộ. Không tuyên bố đã dọn hết worker chỉ vì latency
timeout pass. Mục này không phải lý do giữ cả workspace Rust trong repo chính.
Per-hop network/redirect control vẫn backlog và web không được bật mặc định.

## EVRP / SaigonRide — đã gỡ theo yêu cầu

**EVRP-01 — Đóng ngày 2026-10-17.** Người dùng chọn xóa module khỏi main project,
không chuyển repo và sẽ làm lại từ đầu nếu cần. `modules/evrp/` đã gỡ; giữ archive,
bundle 104-commit history, staging và audit theo recovery policy. Không tự khôi
phục hoặc tích hợp lại. Số đo và tests sau gỡ ở
`audit/evrp_removal_20261017/`. Các tài liệu chuẩn bị tách trước đó là lịch sử,
không phải nhiệm vụ migration còn chờ repo đích.

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

**RAT-ARCH-05 — Đang thử từng phần, cập nhật 2026-10-22.** Người dùng đã đồng ý
thử Qt Quick/QML và chọn luồng PDF offline làm công năng đầu tiên. Có component
dùng chung và entry point `python main.py quick-pdf`: chọn tệp → tìm trang →
đọc đúng trang → chép trích dẫn, dùng backend đọc PDF hiện có. Xem
[luồng Qt Quick PDF](rat_quick_pdf_20261022.md) và
[ADR-005](adr-005-rat-quick-ui-preview.md). Default Widgets/rat.app chưa thay.
Quyết định hoãn ngày 2026-10-15 là lịch sử trước yêu cầu mới này.

Khi đến lượt, thử riêng Workbench gồm Chuột, hai bong bóng, ô nhập và thẻ file,
giữ engine Python hiện có. Mục tiêu nền tảng là macOS, Windows và Linux.
So sánh với bản hiện tại về thời gian hiện cửa sổ/gõ được, độ mượt animation,
CPU/RAM khi chờ và dung lượng toàn bộ bản đóng gói, gồm cả backend. Chỉ quyết
định chuyển tiếp khi có số đo và kiểm tra tương tác trên các nền tảng; chưa
coi Qt Quick/QML hoặc việc đổi Python binding là bằng chứng app sẽ nhanh hơn.


## Spider — repo đích và ranh giới đã chốt, 2026-10-16

Người dùng xác nhận `https://github.com/Thundercok/tdtu-timetable-compiler` là
repo đích để chuyển **Spider**, dù tên repo hiện nói về timetable. Đây là dự án
độc lập ngoài phạm vi RAT/CoT; người dùng sẽ mass rework tại đó sau. Không suy
ra yêu cầu tích hợp timetable từ tên repo. Adapter Python tùy chọn đã giữ lại
vẫn default-disabled; mở rộng Spider không còn là ưu tiên main project.

Bản import được chuẩn bị trong checkout riêng, giữ nguyên bốn tệp hiện có của
repo đích và bảo toàn snapshot 325 file cùng license/patch/provenance. Trạng thái
publication/removal phải đọc từ `audit/spider_destination_prepare_20261016/`;
không gọi việc đã chọn đích hoặc chuẩn bị local commit là đã push hoặc đã xóa
cây nguồn. Chỉ gỡ cây gốc sau khi import remote và recovery được xác minh.


## Debloat — cập nhật 2026-10-17

Watch bot đã gỡ theo yêu cầu; recovery và metrics tại
`audit/watchbot_removal_20261017/`. DocAI đã gỡ sau khi kiểm tra recovery đầy đủ;
xem `audit/docai_removal_20261017/`. Không còn chờ nơi chuyển source trong lần này.
Bước tiếp theo: đối chiếu imports/hợp đồng của lõi reasoning dùng chung giữa
`rat/engine/meta_reasoner.py` và `experiments/research_study.py` trước khi gom package;
không xem đây là hai dự án và không dùng lần thu gọn này để thay đổi phương pháp.


## RAT-REASON-01 — online predictor và stopping, 2026-10-19

Có controller opt-in `reasoning/runtime.py` nối fitted predictor → backend execution → calibrated stopping vào `MetaReasonerEngine(controller=...)`, có kiểm tra synthetic bằng predictor/policy fit thật. Chưa bật trong singleton/UI mặc định: cần bundle policy có provenance được review và hợp đồng backend tương thích; caller cần budget/deadline/cancellation/worker. Không gọi đây là model acceptance hoặc vượt Stage 0. Lát cắt và giới hạn: [online reasoning](rat_online_reasoning_20261019.md). Lỗi VGC legacy được ghi riêng, không gán nhãn verified giả.


### VGC — cập nhật 2026-10-20

Lỗi Qt/VGC được ghi ở lượt online controller đã xử lý: kỳ vọng kiểm chứng CPA thiếu dữ kiện là sai; bỏ tự điền CPA/học phí, chỉ kiểm chứng biểu thức literal được hỗ trợ và không hiển thị xác suất/token model giả. Giữ unknown cho round/paraphrase ngoài phạm vi. Xem [sửa VGC](vgc_verification_fix_20261020.md) và audit/vgc_verification_fix_20261020/. Parser bài toán lời văn đầy đủ chưa triển khai; Stage 0 không đổi.
