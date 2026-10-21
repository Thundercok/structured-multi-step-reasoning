# Handoff thảo luận: RAT như Spotlight tích hợp LLM và CoT

Bạn là model tư vấn kiến trúc. Hãy thảo luận, phản biện và đề xuất thiết kế trước;
chưa triển khai code, cài thêm dịch vụ/model hay chạy benchmark. Tôi sẽ gửi kết
quả của bạn cho Codex đối chiếu với source và bằng chứng hiện có.

## Mục tiêu người dùng

RAT phải dùng được hằng ngày như một **advanced Spotlight finder ngay trong
khung chat**, có mô hình ngôn ngữ và triển khai phương pháp CoT/structured reasoning.
Trải nghiệm cần nhanh, nhẹ và liền mạch; cùng một ô nhập cho tìm kiếm, chọn nguồn
và hỏi tiếp. Người dùng muốn cảm giác hữu ích rõ rệt, không chỉ animation hay
stream chữ trong khi tác vụ thực vẫn chậm.

Giai đoạn này **100% local/offline**, chấp nhận thời gian nạp model lúc khởi động.
Người dùng đã phản đối việc thêm một dịch vụ inference nặng vào quá trình phát
triển. Hiện đã có backend MLX native dùng checkpoint local; ưu tiên tận dụng nó.
Máy đã kiểm tra là Apple Silicon M1, RAM 16 GB. Không suy ra hỗ trợ các nền tảng
khác hoặc hiệu năng trên máy consumer khác từ các phép thử này.

Ví dụ người dùng đưa ra: gõ **“Liên Minh Huyền Thoại”**. Trong ngữ cảnh Spotlight,
đề xuất hiện tại là ưu tiên ứng dụng/game thực sự cài trên máy, hỗ trợ tên Việt/
tên Anh/alias đã xác định, rồi cho mở ứng dụng. “Liên Minh chiếm bao nhiêu dung
lượng?” là tác vụ khác, cần xác định đúng tài nguyên và đo dữ liệu local. Đây là
ví dụ để bàn thiết kế; chưa xác nhận game có trên máy hoặc cho phép mở/cài nó.

## Vai trò CoT trong dự án

RAT là **implementation ứng dụng chính của CoT/structured reasoning**. Pipeline
headless đánh giá phương pháp tái lập và hỗ trợ bài nghiên cứu sinh viên NCKH;
RAT không phải demo phụ có thể bỏ. Định hướng nghiên cứu hiện tại là điều phối
chiến lược suy luận và quyết định dừng theo ngân sách cho mô hình nhỏ.

Tuy nhiên, chưa có bằng chứng mọi controller/chiến lược trong harness đã được
nối vào RAT hoặc chạy tương đương. Đừng gọi lookup, routing hoặc chuỗi tool calls
là đóng góp CoT mới chỉ vì có nhiều bước. Cần phân biệt thiết kế sản phẩm,
structured execution, cơ chế suy luận của model và giả thuyết nghiên cứu.

UI chỉ hiển thị tóm tắt bước công khai, nguồn/artifact, phạm vi đã đọc và kết quả
thực thi. Không hiển thị raw/private thoughts, prompts hoặc raw model completion
thành “màn hình bộ não”. Không cần yêu cầu model giải thích dài cho mỗi thao tác.

## Những gì đã có, đã đo

1. **Workbench PyQt6**, cùng một composer; tổng quan ↔ chi tiết nguồn; artifact/
   revision, ownership của turn/execution, hủy và bỏ callback muộn. Sau sửa lỗi
   giữ trạng thái detail và dark mode, Codex tự chạy lại: **156 tests + 3 subtests
   đạt**. Đã xem ảnh Cocoa fixture replay/widget capture, source hashes khớp.
   Native IME và hành trình UI dùng model thật còn chưa kiểm chứng. Cờ
   `RAT_WORKBENCH_SCENE` vẫn mặc định tắt.

2. **Native MLX cho Hỏi tệp**, đã nối runtime/CLI:
   - `AssistantRuntime(document_model_path=local_model_dir)` sở hữu
     `ResidentDocumentModel`; một thread thực hiện load/inference/release.
   - `answer_selected_document()` đọc đúng tệp đã có trong index, giữ artifact,
     nguồn và execution receipts, rồi gọi model tối đa một lần.
   - Giữ weights và một prefix ngữ cảnh; hỏi tiếp sinh đáp án mới từ bản sao cache.
     Đọc lại nội dung trên đĩa mỗi câu; thay excerpt thì cache được xây lại.
   - Có cancellation, timeout, unload/reload, context budget và đóng session.
   - Lệnh `python -m rat.main ask-file ... --model-path ...`; batch hoặc interactive.
   - Chưa nối service này vào UI đang sửa. General assistant vẫn dùng backend cũ.

3. **Giới hạn quan trọng của MLX hiện tại:** adapter chỉ dành cho câu hỏi trên
   excerpt, `thinking=False`; **chưa hỗ trợ general agent tool calling, structured
   agent output hoặc CoT controller mới**. Không mặc định cứ đổi backend là đã có
   một agent offline hoàn chỉnh. Reader hiện tối đa 3.000 ký tự, có nhãn truncated.

4. **Bằng chứng native mới nhất:** Qwen3.5-4B-MLX-4bit đã có trên máy; 76 software
   tests đạt và 9 ca model thật trên tài liệu mẫu tổng hợp, 0 kết nối mạng.
   Nạp model 18,02 giây; câu hỏi tiếp cùng tệp 2,07 giây; hỏi thiếu thông tin
   4,86 giây; tệp mới/vừa sửa 5,36–9,24 giây; trích đoạn dài 26,05 giây.
   Hủy rồi hỏi tiếp, unload/reload và nguồn/receipt đều qua kiểm tra của fixture.
   Đỉnh MLX allocation khoảng 2,99 GB, không phải tổng RAM của app. Đây là ca
   development nhỏ, không phải benchmark tổng quát hay bằng chứng chất lượng CoT.

## Tìm kiếm hiện tại và đề xuất chưa triển khai

Đã có index SQLite/FTS, tên tệp, metadata, parser loại tệp/thời gian và hybrid
retrieval. SearchWorker hiện tắt HyDE và reranker không gọi LLM, nhưng vẫn chờ
embedding/vector và các bước hybrid trước khi trả một response cuối. Constructor
worker còn thực hiện warmup embedding trước khi chuyển sang search thread.
Chưa có capability tìm/mở ứng dụng với catalog và identity được kiểm chứng.

Đề xuất đang bàn, **chưa phải trạng thái triển khai**:

- Gõ → kết quả tên tệp/FTS/metadata hiện trước; semantic retrieval bổ sung sau.
- Model chưa sẵn sàng vẫn tìm và mở được tài nguyên local.
- Giữ selection/draft/focus; cập nhật bổ sung không làm nhảy tệp đang chọn.
- Truy vấn mới hủy/thay truy vấn cũ, bỏ kết quả muộn theo ownership hiện có.
- Chọn tệp để hỏi → chuẩn bị ngữ cảnh ở worker → hỏi tiếp dùng lại prefix.
- Mục tiêu kết quả đầu tiên khoảng 100–200 ms khi index sẵn sàng là **mục tiêu
  cần đo**, chưa phải hiệu năng đã đạt.

Finder trong chat đã được ghi backlog **RAT-FIND-01**; chưa triển khai đợt này.
Không thêm màn hình riêng, framework mới hoặc một task store cạnh tranh với kernel.

## Cần bạn giải quyết

1. Thiết kế cụ thể cách **điều phối mức suy luận**: khi nào lookup/parser đủ,
   khi nào cần semantic retrieval, một lượt model, nhiều bước hay hỏi làm rõ?
   Điều kiện dừng dựa trên dữ kiện quan sát/kiểm chứng nào? Không dùng confidence
   model tự khai như một xác suất đã được hiệu chỉnh.
2. Với “Liên Minh Huyền Thoại”, “mở Liên Minh”, “Liên Minh chiếm bao nhiêu dung
   lượng?” và “tóm tắt PDF vừa chọn”, mô tả các bước, dữ liệu cần có, tool calls,
   số lượt model dự kiến và bằng chứng hoàn thành. Bare query nên tìm trước;
   chọn kết quả/ý định mở rõ ràng mới thực thi việc mở. Không tự suy đoán đường dẫn.
3. Nêu **CoT nằm ở đâu một cách thực chất**, phần nào deterministic, phần nào là
   model reasoning; cơ chế nào nối được với routing/stopping đang nghiên cứu?
   Có thể giữ các bước trung gian ngắn, có cấu trúc mà vẫn hữu ích không?
4. Phân bố latency, CPU/RAM và cache giữa retrieval và model thế nào để tác vụ
   đơn giản nhanh? Tránh để tìm kiếm làm mất cache tài liệu, hoặc chuẩn bị mọi tệp
   khi rê chuột. Nêu trade-off và failure modes thay vì hứa nhanh hơn chưa đo.
5. Đề xuất **một lát cắt đầu tiên nhỏ**, có headless acceptance và sau đó UI
   acceptance. Nếu muốn so sánh nghiên cứu, nêu đối chứng, thước đo và dữ liệu
   cần review, tách khỏi phép thử phần mềm. Không tự mở chiến dịch model.

Trả lời bằng một kiến trúc đề xuất, bảng luồng cho bốn ví dụ, các đánh đổi chính
và thứ tự triển khai. Chỉ rõ điều gì đã có, điều gì cần thêm, điều gì chưa biết.
Phản biện cả hướng đề xuất ở trên nếu có lý do; tránh trả lời chung chung kiểu
“thêm cache, streaming, agent framework”.

## Nếu được truy cập repository

Root hiện tại: `/Users/thundercock2/Documents/Github/multi-step-structured-reasoning`.
Canonical repo: `Thundercok/nesy-docai`. Đọc `AGENTS.md`, `docs/project_scope.md`,
`docs/research_plan.md`, `docs/research_protocol.md`; hướng dẫn mới coi RAT là
implementation chính thay cho những snapshot cũ gọi nó là demo phụ.

Đọc chọn lọc:

- `rat/engine/hybrid_search.py`, `rat/engine/context_parser.py`, `rat/crawler/db.py`.
- `rat/engine/assistant_runtime.py`, `rat/engine/controller.py`,
  `rat/engine/completion.py`, `rat/engine/verification.py`.
- `rat/kernel/registry.py`, `rat/kernel/dispatcher.py`, `rat/kernel/contracts.py`.
- `rat/engine/document_model_service.py`, `rat/engine/mlx_document_session.py`,
  `rat/engine/selected_document_qa.py`.
- `docs/rat_document_service_20261016.md`, `docs/rat_backlog.md`.
- Raw backend evidence: `audit/rat_document_service_20261016/`.
- UI review: `audit/rat_workbench_flash_review_r3_20261016/review.md`.

Working tree có nhiều thay đổi đồng thời. Làm trên `main`, giữ công việc khác và
recovery material; không commit/push/pull/reset/tạo branch khi chưa có yêu cầu.
DocAI ở `modules/docai/` vẫn độc lập. Giữ nguyên Stage 0 và các ranh giới dữ liệu
nghiên cứu. Handoff này chỉ yêu cầu thảo luận kiến trúc.
