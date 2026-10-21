# Antigravity — performance, Workbench gọn, tìm tự nhiên và visualize thoughts

Đây là prompt tổng hợp mới theo yêu cầu trực tiếp của người dùng ngày 2026-10-17.
Ưu tiên prompt này khi phạm vi khác handoff cũ. Triển khai, kiểm tra rồi bàn giao
Codex review; không chỉ đề xuất kế hoạch. Tách kết quả từng mốc để dễ đối chiếu.

## Mục tiêu và ranh giới

- Performance là ưu tiên số một. RAT phải dùng được hằng ngày, 100% local/offline
  cho luồng này. Người dùng chấp nhận startup loading; lúc đang gõ/tìm không bị
  chặn bởi model. Dùng model đã cài, không tự download hoặc thêm daemon/provider.
- Một composer, một Workbench. **Toàn bộ Workbench là bong bóng suy nghĩ lớn của
  Chuột, ba chấm nối đầu Chuột lên khung đó.** Giữ mascot, tài sản, tỷ lệ và style
  hiện tại; khung có thể nới theo nội dung trong giới hạn màn hình.
- RAT là implementation chính của CoT/structured reasoning. Đọc AGENTS.md,
  docs/project_scope.md, docs/research_plan.md, docs/research_protocol.md. Đây là
  phát triển ứng dụng và acceptance, không thay research harness, Stage 0 hoặc
  tự công bố kết quả chất lượng/nghiên cứu.
- Giữ main, thay đổi đồng thời và recovery; không commit/push/pull/reset/tạo
  branch. Đọc lại source trước khi ghi. Giữ các cờ thử nghiệm mặc định tắt.
  DocAI/EVRP đã được gỡ theo quyết định riêng; Spider độc lập, không khôi phục.

## 0. Nối tiếp công việc đang làm, giữ baseline

Đọc `docs/prompts/antigravity_finder_keyboard_revision_20261017.md` và
`docs/prompts/antigravity_keyboard_and_native_qa_handoff_20261017.md`.
Review gần nhất: regression 185 tests + 3 subtests qua; probe bàn phím mới còn
4 fail/2 pass: Enter trên Hỏi mở file, Tab lệch shortcut target, Shift+Down bị
chiếm, snapshot tạo lại row làm mất focus. Nếu source mới đã sửa, chứng minh
bằng tests; không triển khai lại hoặc làm yếu assertions.

Backend native đã có: Config.document_model_path/document_model_preload,
AssistantRuntime.preload_document_model() trả Future, một ResidentDocumentModel
với một owner thread. 90 tests backend qua ở
`audit/rat_document_startup_20261016/`. Nối native Hỏi tệp/stream/cancel/quit theo
handoff trước nếu chưa xong; lỗi path/load không được phá finder hoặc rơi về
provider khác. Settings mới chỉ cần đủ dùng; dành effort trước cho luồng nhanh.
Native adapter hiện chỉ hỗ trợ selected-document QA, chưa hỗ trợ general agent
tool-calling. Không đưa adapter này vào model_client chung rồi giả định đã chạy.

## 1. Đo và sửa performance trước khi mở rộng

Số đo cũ chỉ là baseline headless trên fixture, không phải SLA UI:
`audit/rat_document_service_20261016/live_calls.jsonl` ghi tệp ngắn 6,26s, hỏi tiếp
cùng tệp 2,07s, trích đoạn dài 26,05s. Ca dài đọc tệp khoảng 3,6ms; chữ đầu native
sau 24,56s. Đây là khối thời gian model/native, chưa tách đủ các bước bên trong.
Preload weights không tự giải quyết phần chờ này; streaming không tự giảm compute.

Lưu baseline trước sửa và đo lại sau sửa trên cùng model/fixture/điều kiện:

- UI: phím → phản hồi editor, query → kết quả đầu dùng được, delivery → paint;
  cold/warm và tải khi model/indexer đang chạy phải tách riêng.
- QA: queue, load, tokenize, prefill, copy cache, generation, submit → chữ đầu
  thực sự hiển thị, submit → hoàn tất; ghi prompt/output tokens và số calls.
  Nếu chưa đo được một phase thì ghi chưa đo, không suy từ timer phase khác.
- CPU khi idle và tổng RAM tiến trình, mô tả cách đo; MLX allocation báo riêng.
  Không chạy thêm một model/service hoặc polling chỉ để lấy telemetry trong app.
- Có thể đặt mục tiêu ban đầu gõ dưới 100ms và kết quả tên/metadata dưới 200ms
  ở warm UI; đây là mục tiêu cần đo, không phải kết quả đã đạt. Không thêm assert
  wall-time dễ flaky vào unit test; báo số mẫu và phân vị phù hợp. Với ít lượt
  model thật, báo từng lượt, không quảng cáo p95 từ vài mẫu.

Giữ tìm tên/FTS/metadata không chờ LLM hoặc embedding. Không scan catalog theo
từng phím, không xếp FIFO query cũ, không đọc sâu/OCR từ hover/mũi tên. Dùng worker
và cancel/query generation đã có. Reconcile row theo id để giảm rebuild và giữ
focus/scroll. Tối ưu chỗ profiler chỉ ra; nếu đổi cách chọn ngữ cảnh/cache/budget
phải kiểm lại đáp án, nguồn, tệp thay đổi và cancellation. Không chọn model nhỏ
chỉ vì nhanh khi tác vụ không hoàn thành, không giấu thời gian bằng animation.

## 2. Thu gọn chữ và nhãn trùng trên Workbench

- Giảm lặp branding/heading như rat., Workbench, Không gian làm việc, tên tác vụ
  và trạng thái khi chúng truyền cùng một ý. Ưu tiên một tiêu đề công việc hữu ích;
  tìm kiếm đơn giản có thể không cần hero heading lớn.
- Đưa diện tích tiết kiệm được cho kết quả/nguồn/preview. Giữ filename hoặc nhãn
  phân biệt tài nguyên, điều kiện lọc, lỗi, thiếu dữ kiện và trạng thái dừng.
- Trace chi tiết mở tại chỗ, không thêm panel/composer. Giữ liên kết Chuột → ba
  chấm → Workbench, lời thoại và composer ở dưới. Không làm trống khung sau done/
  cancel, không đẩy composer khỏi màn hình. Light/dark/reduced-motion/420px vẫn đẹp.
- Kiểm tra geometry/visibleRegion của cả bốn nút tệp, caret/draft, anchor đáy và
  source-detail state; không chỉ isVisible. Không đổi asset hoặc phóng mascot thêm.

## 3. Tìm bằng cách nói tự nhiên, giữ đường nhanh

Ba ví dụ acceptance của người dùng:

| Câu nhập | Diễn giải và hành vi cần có |
| --- | --- |
| “Slide DSA sửa tuần trước” | Tìm DSA, nhận diện slide và ràng buộc modified time của tuần trước; trả nguồn phù hợp. |
| “bản báo cáo mới nhất” | Tìm các ứng viên báo cáo trong phạm vi index, sắp modified time giảm dần trước khi limit; nói rõ phạm vi. |
| “mở Liên Minh” | Nhận diện yêu cầu mở app và alias; gõ chỉ hiện gợi ý, submit mới có thể thực thi. |

Thiết kế parser/intent plan headless có cấu trúc: action, query terms, resource
kind, filters, sort, cần-làm-rõ, và cơ sở diễn giải. Tái sử dụng ApplicationCatalog,
SearchFilters, ProgressiveSearch/SearchCoordinator. Tách từ chỉ hành động/thời
gian khỏi FTS query; giữ nguyên draft. Kết hợp được tên gọi Việt/Anh, không dấu,
viết tắt/alias tường minh, loại tệp và thời gian; không hardcode nguyên ba câu.
Không gọi model theo phím hoặc thêm model call chỉ để paraphrase câu đơn giản.
Phạm vi chưa hiểu phải giữ truy vấn/làm rõ, không tuyên bố hiểu mọi ngôn ngữ tự nhiên.

“Tuần trước” là tuần lịch trước, Thứ Hai 00:00 tới Thứ Hai tuần này, cuối khoảng
không bao gồm; dùng timezone người dùng và clock injectable để test ranh giới.
Giữ phân biệt ngày sửa/ngày tạo. “Mới nhất” dựa metadata có nguồn trong index,
không khẳng định đã xét toàn bộ máy; không chỉ sort top-15 lexical rồi gọi đó là
mới nhất. Ánh xạ slide/PDF phải có quy tắc rõ, không coi mọi PDF là slide.

Nếu thiếu target, nhiều app cùng alias, nhiều bản cài hoặc cách hiểu mâu thuẫn:
trình bày ứng viên cùng thông tin phân biệt, hỏi/chọn ngay trong cùng Workbench.
Không dùng phần trăm confidence tự đặt. Câu chat/Hỏi tệp đang chọn không bị router
chiếm chỉ vì chứa từ “mở”, “báo cáo”, “tuần”; IME preedit không submit/execute.

**Yêu cầu mới này cho phép triển khai operation mở app**, thay phạm vi cũ chỉ tìm
app. Đăng ký qua dispatcher/contracts/receipts hiện có. Chỉ mở sau submit yêu cầu
mở rõ ràng với một exact/explicit-alias match duy nhất, hoặc người dùng chọn hành
động Mở trên ứng viên. Bare query không mở. Revalidate path/bundle/executable tại
execution; xử lý app bị gỡ, tên trùng và phủ định “đừng mở”. Riot Client và League
of Legends là identity riêng. Không ghép shell từ input hoặc suy ra path tùy ý.
Phân biệt gửi yêu cầu mở, OS chấp nhận/khởi chạy và game thật sự sẵn sàng; không
báo “đã vào game” từ một process/launch receipt. Scope hiện là macOS; nền tảng
chưa hỗ trợ phải trả trạng thái thật, không báo thành công giả.

## 4. Thể hiện structured reasoning / visualize thoughts có căn cứ

Người dùng muốn nhìn thấy Chuột hiểu và làm việc ngay trong thought bubble lớn.
Triển khai cả quyết định bước tiếp theo/kiểm tra điều kiện/dừng và projection UI;
không chỉ thêm chữ “đang nghĩ” hoặc một chuỗi animation cố định.

Tái sử dụng `rat/engine/work_trace.py`, `rat/engine/completion.py`,
`rat/ui/work_context.py`, WorkSceneProjector/GroundedRelationsWidget và artifact
store hiện có. Trình bày giải thích công khai ngắn, kế hoạch có nhãn và dữ kiện
đã quan sát; không đưa raw/private thought, raw_completion, model_input hoặc
reasoning tokens lên UI. Giữ native thinking=False; không thêm inference chỉ để
tạo lời giải thích/trace, không đổi nghiên cứu vì một visualization.

- Flow gọn: hiểu yêu cầu → tìm/đọc nguồn → kiểm tra điều kiện → kết quả/hỏi làm rõ.
  Chỉ hiện nhánh/bước thực sự có; tác vụ xác định không cần tạo CoT model giả.
- Phân biệt dự định, đang chạy, đã tìm thấy, đã đọc, kiểm tra đạt/chưa đạt,
  chờ lựa chọn, lỗi và hủy. Mỗi trạng thái/edge bám event, resource_id, artifact
  revision hoặc receipt có thật; kế hoạch chưa thực thi không được tô “đã làm”.
- Ví dụ: “mở Liên Minh” có hai bản cài → hiển thị hai ứng viên → chờ chọn;
  chưa mở app. “Slide DSA…” → hiện cách hiểu tuần/loại tệp → kết quả đã lọc;
  chưa đọc toàn bộ nội dung. Hỏi tệp → đọc trích đoạn có range → sinh trả lời →
  kiểm điều kiện hoàn tất đã định nghĩa; receipt không tự chứng minh đáp án đúng.
- Đủ điều kiện kiểm chứng thì dừng; thiếu dữ kiện thì làm rõ; lỗi/hết budget thì
  thể hiện chưa hoàn tất. Không kéo dài tác vụ để đủ một số bước/nhịp animation.
- Cập nhật incremental, giữ vị trí đọc/selection/focus; chi tiết trace thu gọn
  mặc định khi không cần. Không che nội dung để trình diễn thoughts. Hủy/reset/
  đổi query phải vô hiệu callback cũ; nội dung đã làm còn xem lại được.

## 5. Kiểm chứng, thứ tự bàn giao

Đi theo mốc: (A) keyboard + baseline perf + native QA tối thiểu;
(B) Workbench gọn; (C) parser/filters + app open contract headless rồi UI;
(D) projection reasoning thật và acceptance tích hợp. Có source hash/test/report
từng mốc; tiếp tục tự làm các mốc đã được giao, báo blocker cụ thể nếu có.

Giữ 12 probe cũ, 6 keyboard cases và regression trong handoff trước, cùng 90
tests backend native. Thêm test có ý nghĩa cho kết hợp intent/date/type/sort,
ranh giới tuần/timezone, tên trùng, index stale/file missing, phủ định, chat/QA
không bị chiếm, chưa submit không mở, callback muộn và trace planned/observed.
Mock launch trong regression; real smoke chỉ app vô hại trong fixture hoặc app
người dùng đã yêu cầu, không tự mở game để demo. Test trace không đọc raw thought
và không tăng model calls, giữ fast lane không dùng model/embedding.

Dùng DB/tệp/app fixture tổng hợp có nhãn; không crawl thư mục cá nhân để nghiệm
thu. Real-model QA smoke dùng checkpoint local có sẵn và tối đa 5 generations
như handoff trước; không chạy overnight hoặc campaign nghiên cứu. So sánh perf
trên cùng input/thiết lập và điều kiện đã ghi; lưu cả fail/cancel, không bỏ case
chậm hoặc trả lời sai. Đặt thay đổi đã đo bên cạnh raw artifacts.

Ảnh cuối desktop/narrow/light/dark, thought bubble và nội dung/trace thật. Native
Cocoa phải ghi qpa_platform=cocoa; offscreen/fixture replay/QWidget.grab ghi đúng
loại, không gọi là live model/native IME đã xác nhận. Báo chưa đo/chưa thử rõ ràng.

Final handoff ngắn: thay đổi theo mốc, commands/results, số model calls, bảng
latency/RAM/CPU trước-sau kèm giới hạn, ảnh/source hashes, vấn đề còn mở. Không
đổi passing software tests thành claim model quality, CoT novelty hay Stage 0.
