# RAT backlog

Updated: 2026-10-24, Asia/Ho_Chi_Minh.

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

### RAT-EFF-01 — Đo chi phí toàn lượt và tối ưu context theo SoL-Pi

**Backlog triển khai, thêm theo yêu cầu người dùng ngày 2026-10-23.**
Tham khảo [SoL-Pi: Recursively Scaling Auto-Research Loops for Efficient Agent
Harness](https://arxiv.org/pdf/2609.20519). Mục tiêu là giảm chi phí lặp lại
context/tool observations trong RAT mà vẫn giữ kết quả, nguồn và trạng thái
thực thi có thể kiểm tra. Đây là hạ tầng core của cùng hệ RAT–CoT; hiệu quả
trên RAT/model nhỏ là giả thuyết cần đo, chưa phải kết quả chuyển giao từ paper.
Ưu tiên sau baseline RAT chạy model thật ổn định và công việc routing/stopping
hiện tại; chưa triển khai runtime từ việc ghi backlog này.

Thứ tự triển khai:

1. **Đo trước khi tối ưu.** Ghi chi phí từng model call và tổng mỗi request:
   input/output tokens, cached input nếu backend cung cấp, số calls và thời
   gian online gồm các bước model/tool/context maintenance. Chi phí nén hoặc
   delegated reading cũng phải được cộng. Trường backend không cung cấp để
   unknown kèm nguồn/phạm vi đo, không điền 0 hoặc suy ra từ token sinh.
   Phân biệt số token, chi phí API và full inference cost; local MLX không tự
   có giá API tương đương. Giữ tương thích số đo generated-token lịch sử.
2. **Giảm tool observations trước.** Thử cơ chế opt-in giới hạn/lược bỏ phần
   dư của output lớn, tham khảo ObservationPack; giữ raw artifact bất biến,
   ID/revision, nguồn/trang, lỗi và trạng thái execution/verification. Cho phép
   đọc lại phần gốc theo tham chiếu; không biến nội dung bị lược thành đã đọc
   hoặc đã xác minh. Giữ cấu hình tắt làm đối chứng và đường rollback.
3. **Nén lịch sử khi có số đo hỗ trợ.** Thử tại ranh giới subtask đã hoàn tất,
   giữ yêu cầu hiện hành, ràng buộc, việc đang dở và evidence references.
   Gate cần tính cả overhead nén và ảnh hưởng cache; tiết kiệm dự kiến phải
   ghi là ước lượng rồi đối chiếu với số đo toàn lượt. Action Fusion và
   Evidence-Preserving Reducer cho delegated reading là lát cắt sau, chỉ làm
   khi trace cho thấy nhu cầu; chưa mở vòng auto-research tự sửa harness.

Điều kiện nghiệm thu:

- Có paired runs bật/tắt trên cùng model snapshot, tác vụ development,
  prompt/settings, budget và seeds đã chốt; lưu cấu hình/source hashes, public
  responses, tool artifacts, lỗi và số đo từng call. Báo riêng chất lượng,
  source/verification failures, chi phí và online latency, gồm cả trường hợp
  tối ưu làm kết quả xấu đi. Chốt tiêu chí chất lượng và mức tiết kiệm cần đạt
  trước khi xem kết quả; chưa tự đặt numerical margins từ paper.
- Kiểm tra hội thoại qua UI thật và backend/model thật, gồm follow-up cần
  nguồn cũ, tool output dài, lỗi/cancel và truy hồi raw artifact; giữ prompts,
  public responses và screenshots. Fixtures chỉ xác nhận hợp đồng phần mềm,
  không thay live acceptance hoặc bằng chứng chất lượng model.
- Không đổi routing/stopping, prompts nghiên cứu hoặc policy đã freeze trong
  cùng phép so sánh để tránh lẫn nguyên nhân. Nếu đưa thay đổi vào research
  harness, cần protocol/source freeze và regression theo AGENTS; historical
  artifacts giữ nguyên. Mục này không cấp ngân sách inference, không mở test
  được bảo vệ và không thay trạng thái Stage 0.

**RAT-FIND-01 — Hỗ trợ tìm và mở file/app khi không nhớ tên, ngay trong chat.** Theo yêu cầu
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

**Giới hạn người dùng chốt ngày 2026-10-24:** không định làm một launcher đầy
đủ. Nhu cầu là giúp người dùng tìm/mở file hoặc ứng dụng khi không nhớ tên;
định hướng này thay mọi cách hiểu mở rộng từ tên “Advanced Spotlight finder”.

- Ưu tiên hiểu mô tả không đầy đủ (công dụng, nội dung nhớ được, một phần tên),
  gợi ý vài mục có thật rồi cho người dùng chọn/mở. Hiển thị tên và vị trí đủ
  để phân biệt; nếu chưa rõ thì hỏi ngắn, không đoán ra file/app không tồn tại.
- Một composer; không cần nút “Ứng dụng” thường trực. Nút mở hộp thoại file có
  thể là icon với tooltip/accessibility. Catalog/grid hiện có là implementation
  tạm, không phải mục tiêu tiếp tục mở rộng.
- Không thêm launcher dashboard, quản lý/cài đặt ứng dụng, dock, widget, hay
  tính năng launcher khác nếu chưa có yêu cầu mới. Không tự mở rộng indexing
  tệp cá nhân để phục vụ mục này.
- Backlog chính: truy hồi khi không nhớ tên và chọn/mở đúng mục qua hội thoại.
  Lệnh `/apps`/“ứng dụng” hiện chỉ mở catalog, chưa đáp ứng đầy đủ nhu cầu mô tả
  mơ hồ. Chỉ coi hoàn tất sau khi thử mô tả thật với file/app thật và giữ bằng
  chứng lựa chọn/mở đúng; tests routing hoặc screenshot grid không thay thế ca đó.

### RAT-MAIL-01 — Đọc email ra lịch trình/plan, tạo bản nháp email và kiểm chứng tiền điện tháng

**Backlog triển khai, thêm theo yêu cầu người dùng ngày 2026-10-24.**
Mục tiêu là bổ sung một lát cắt ứng dụng thực tế gắn trực tiếp với suy luận nhiều
bước và kiểm chứng (CoT + Verification, nối hướng `RAT-AI-03`) ngay trên cùng một
box chat (`RAT-UX-01`), không mở màn hình quản lý email hay hóa đơn riêng. Ưu tiên
sau baseline RAT chạy model thật ổn định và chiến dịch nghiên cứu NCKH hiện tại;
chưa triển khai runtime từ việc ghi backlog này.

Phạm vi chức năng:

1. **Đọc email → lịch trình / plan có đối chiếu.** Bóc sạch nội dung email bằng
   Python parser chuẩn (`From`, `Subject`, `Date`, `text/plain`, loại bỏ HTML rác
   và phần quote lặp) để neo mốc thời gian tương đối cho model nhỏ; đối chiếu với
   lịch hiện có (`timetable`) nhằm phát hiện trùng giờ, tìm khung trống và xuất
   kế hoạch kèm trích dẫn email nguồn.
2. **Soạn email dừng ở bản nháp (`email_draft`).** Tạo artifact bản nháp (`To`,
   `Subject`, `Body`) trong cuộc trò chuyện kèm thao tác Copy hoặc mở bản nháp
   ngoài (`mailto:` / `Mail.app`) để người dùng tự duyệt và bấm gửi. **Không tự
   động gửi (no auto-send)** để phòng gửi nhầm người/giờ hoặc prompt injection từ
   email đến.
3. **Kiểm chứng tiền điện tháng này.** Đọc từ email thông báo tiền điện hoặc tệp
   PDF/ảnh phiếu báo qua `document_intake` / `documents` hiện có; trích xuất kỳ
   thanh toán, chỉ số cũ – mới, `kWh` tiêu thụ, đơn giá/bậc thang, thành tiền và
   hạn đóng. Chạy verifier số học Python độc lập kiểm tra phép trừ chỉ số và tổng
   tiền (báo rõ trường thiếu hoặc sai lệch thay vì tự điền số), hỗ trợ ghép bảng
   so sánh với kỳ trước qua `compose_result_table` (`RAT-AI-02`).

Ranh giới kỹ thuật và điều kiện nghiệm thu:

- Nguồn email ưu tiên tệp `.eml`/PDF/nội dung đính kèm (Mức 1) hoặc đọc on-demand
  giới hạn qua `Mail.app` local / IMAP theo truy vấn (Mức 2). Không xây email
  client đầy đủ, không đồng bộ/index ngầm toàn bộ hộp thư cá nhân và không triển
  khai luồng Google Cloud Gmail OAuth2 phức tạp trong lát cắt này.
- Không viết bot đăng nhập hoặc cào trực tiếp cổng web/app EVN.
- Giữ ranh giới `DOCAI-01`: chỉ dùng schema gọn và verifier số học cho phiếu/email
  tiền điện; không khôi phục `modules/docai/` hay nối XML/solver hóa đơn Z3 vào
  startup RAT.
- Phân biệt nội dung thực sự đọc từ email/PDF với phần kế hoạch/bản nháp do model
  đề xuất. Nghiệm thu qua UI thật và backend/model thật với email/tệp `.eml` thật
  và PDF có provenance/hash xác minh được theo `AGENTS.md`; không thay đổi Stage 0.

| ID | Hướng phát triển | Trạng thái | Phụ thuộc / bằng chứng cần có |
| --- | --- | --- | --- |
| RAT-AI-01 | Model điều khiển làm rõ, tiếp tục, đổi ý và tham chiếu công việc. | Backlog | [ADR-002](adr-002-rat-adaptive-interaction.md); cần kiểm tra model thật, không chỉ scripted tool calls. |
| RAT-AI-02 | Model ghép phần kết quả và UI khai báo theo yêu cầu, hỗ trợ nhiều artifact/revision. | Có lát cắt bảng tham chiếu nguồn trong source; phần rộng hơn vẫn backlog | `compose_result_table` ghép các ô từ artifact/revision thật; có regression phần mềm. Chưa review model thật, chưa sinh UI phong phú hoặc xác nhận độ đúng diễn giải. [Phạm vi triển khai](rat_book_features.md). |
| RAT-AI-03 | Phối hợp lịch, tài liệu và phép biến đổi dữ liệu để xử lý yêu cầu chưa có workflow riêng. | Backlog | Dữ liệu và thao tác thực, đánh giá yêu cầu mới (ví dụ lát cắt `RAT-MAIL-01`); tránh thêm một màn hình riêng cho mỗi ví dụ. |
| RAT-AI-04 | Model đề xuất recipe, thành phần hoặc logic mới trong môi trường tách biệt. | Xa hơn | Sau nền tảng và evidence phù hợp; chưa chọn runtime/SDK hoặc triển khai code tùy ý. |

## DocAI — giữ độc lập, dùng sau

**DOCAI-01 — Hoãn; source dư đã gỡ theo yêu cầu ngày 2026-10-17.**
`modules/docai/` đã được đóng gói phục hồi và gỡ khỏi cây source. Nghiệp vụ hóa đơn
tổng quát (XML, sinh ứng viên số, solver hóa đơn Z3) chưa nối vào RAT hay pipeline
CoT và chỉ mở lại khi có yêu cầu cụ thể; nhu cầu đọc/kiểm chứng số học gọn cho
phiếu hoặc email tiền điện được theo dõi riêng ở `RAT-MAIL-01` mà không khôi phục
module cũ.

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
