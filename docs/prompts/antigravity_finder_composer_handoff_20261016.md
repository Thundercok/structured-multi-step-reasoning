# Antigravity — nối finder vào composer và polish Workbench

**Đính chính ý người dùng, 2026-10-16:** toàn bộ khung Workbench phía trên là
bong bóng suy nghĩ của Chuột, được nối với đầu Chuột bằng ba chấm tròn. Nới
khung đó để chứa công việc. Codex đã diễn giải sai thành bubble nhỏ chứa dấu
`...` bên cạnh đầu Chuột; phần đó của bản triển khai vừa rồi cần sửa. Đọc thêm
`docs/prompts/antigravity_workbench_thought_surface_revision_20261016.md`.

Triển khai trong repo hiện tại; Codex sẽ review kết quả. Đọc AGENTS.md và
docs/project_scope.md. Giữ main, thay đổi đồng thời và recovery material; không
commit/push/pull/reset/tạo branch. Không đổi framework hoặc mở rộng nghiên cứu.

## Nền đã có

Đọc docs/rat_progressive_finder_20261016.md trước khi sửa:

- rat/engine/app_resolver.py: ApplicationCatalog.scan(), catalog ứng dụng macOS
  theo metadata/path có thật, alias và identity riêng cho từng cài đặt.
- rat/engine/progressive_search.py: ProgressiveSearch, SearchRequest,
  SearchFilters, SearchCoordinator. Kết quả lexical trước; semantic provider là
  injection point, chưa nối embedding thật. Callback chạy trên worker.
- 13 test mới; regression liên quan tổng cộng 203 tests + 3 subtests đạt.
  Bằng chứng: audit/rat_progressive_finder_20261016/.
- Luồng này chưa nối UI và không mở ứng dụng. Số đo 0,5–10,4 ms là warm backend
  trên fixture 5.000 tệp, không phải độ trễ UI.
- Native MLX Hỏi tệp đã có runtime/CLI, nhưng tích hợp UI/model ngoài scope lượt
  này: docs/rat_document_service_20261016.md. Không đổi inference/backend/CoT.

## 1. Nối tìm kiếm vào cùng composer

Giữ một composer và một nguồn draft/selection/focus hiện có. Đọc luồng submit,
navigation, chọn tệp để hỏi và ownership trong OmnibarWindow trước khi nối.
Không biến mọi câu chat thành lệnh tìm kiếm hoặc chiếm Enter của hỏi tài liệu.

Trong lúc nhập truy vấn tìm kiếm, hiển thị các gợi ý app/tệp trên Workbench hiện
có. Gợi ý chưa phải một lượt chat mới. Giữ phân biệt tìm kiếm, chọn nguồn để hỏi
và yêu cầu thực thi; bare query không tự mở ứng dụng. Khi thiếu rõ ràng, giữ tác
vụ hiện tại và cho chọn hành động rõ thay vì âm thầm đổi ý định.

Catalog phải được xây trên worker trước khi dùng, không scan theo từng phím.
Luồng tên/FTS không chờ model hoặc embedding. Bỏ qua nhịp thay đổi chỉ là preedit
của IME; tránh submit/tìm lại trong khi đang ghép chữ. Không kích hoạt model,
đọc sâu/OCR hoặc chuẩn bị prefix khi rê chuột/đi qua kết quả bằng phím mũi tên.

Đưa callback qua queued Qt signal. Tại thời điểm GUI nhận signal, kiểm tra query
ID/generation bằng coordinator.is_current(); kết quả cũ không được ghi đè.
Giữ selection bằng resource_id, không bằng số dòng. Kết quả bổ sung giữ vị trí
đang chọn. Workbench được nới theo bố cục thought bubble đã đính chính bên dưới;
giới hạn theo viewport và dùng scroll khi hết chỗ, giữ composer truy cập được.
Xử lý cancel, đổi truy vấn, semantic chưa có/lỗi, index lỗi và tài nguyên bị gỡ.
Đóng coordinator đúng lifecycle, không terminate thread cưỡng bức.

Giữ cờ Workbench/finder thử nghiệm mặc định tắt theo quy ước hiện tại. Dùng các
action renderer/dispatcher có sẵn cho tệp. Chỉ trình bày app tìm thấy; chưa thêm
capability launch app hoặc đo dung lượng trong lượt này.

## 2. Yêu cầu polish mới của người dùng

Người dùng muốn **cả Workbench là thought bubble của Chuột**, **Chuột lớn hơn
một chút**, và vài minor improvements, vẫn đẹp/gọn. Cách hiểu bubble nhỏ chứa
dấu `...` là sai; yêu cầu này thay thế cách hiểu đó.

- Biến khung chứa công việc phía trên thành một bong bóng suy nghĩ lớn, bo mềm,
  chứa finder, nguồn, kết quả và chế độ xem chi tiết đang có. Ba chấm tròn nối
  từ gần đầu Chuột lên khung đó, tăng dần về phía khung. Không thêm một oval
  chứa ellipsis riêng bên cạnh đầu Chuột.
- Nới diện tích hữu dụng của bong bóng Workbench; cho mở rộng/thu gọn hợp lý
  theo nội dung và chỗ trên màn hình. Giữ một composer ở dưới và lời thoại
  hiện có của Chuột; không đưa hai vùng đó vào một panel mới.
- Bố cục phải cho thấy rõ mối nối Chuột → ba chấm → Workbench. Dành chỗ cho
  đường nối trong layout; không che mặt/tai, lời thoại, nội dung hay composer.
  Phần trang trí không chiếm focus hoặc chặn chuột.
- Thought bubble là hình thức trình bày công việc, không chỉ là loading indicator.
  Khi xong/lỗi/hủy vẫn giữ nội dung đã có để xem lại. Chỉ chuyển động biểu thị
  đang xử lý mới dừng; không xóa cả khung hoặc ép thu về ba chấm.
- Chuyển động mở/thu nhẹ, không trì hoãn kết quả. Reduced motion chuyển trạng
  thái trực tiếp; khi idle/ẩn cửa sổ không có animation loop hoặc polling mới.
  Nội dung vẫn là dữ kiện/kết quả/trạng thái thực, không thêm raw/private reasoning
  hay bịa phần trăm, bước công cụ hoặc suy nghĩ của model.
- Tăng Chuột khoảng 8–12% làm điểm bắt đầu, tinh chỉnh theo ảnh thực tế. Giữ tỷ lệ,
  không vẽ lại nhân vật, không crop tai/đuôi/chân, không làm ảnh nhòe hơn. Nếu ảnh
  nguồn không đủ độ phân giải, ghi rõ và giữ mức phóng phù hợp.
- Compact/hẹp phải vẫn cân đối; ưu tiên chỗ cho nội dung và composer, cho phép
  giảm mức phóng Chuột ở bề rộng nhỏ. Giữ anchor ô nhập khi đủ chỗ.
- Ngoài thay đổi hình thức Workbench thành thought bubble theo yêu cầu này,
  minor improvements chỉ gồm spacing/alignment, hover/focus affordance và
  transition quanh vùng vừa sửa. Không thêm panel/composer hoặc đổi tài sản
  mascot. Màu/font bám WorkbenchTokens, kiểm tra light/dark.

## 3. Kiểm chứng và bàn giao

Ghi baseline/hash trước sửa; đọc lại file trước khi ghi để giữ thay đổi đồng thời.
Fixture app/index phải được ghi nhãn, không crawl tài liệu cá nhân để demo.

Kiểm tra: gõ nhanh/đổi truy vấn, bàn phím chọn kết quả, draft/caret/selection,
hỏi tệp đang chọn vẫn submit đúng luồng, không mất tác vụ đang chạy, index bị khóa,
hide/show, cancel + callback muộn, narrow 420px, light/dark và reduced motion.
Kiểm tra geometry/visibleRegion thay vì chỉ isVisible. Thêm regression có giá trị
cho ownership, tương tác mới, kích thước/đường nối thought bubble và khả năng
xem lại nội dung sau khi xong/hủy; không chỉ đếm widget.

Chạy tests/test_progressive_search.py và tám module UI:
tests/test_rat_magic_ui.py, tests/test_rat_one_box_ui.py,
tests/test_work_context_ui.py, tests/test_rat_chat_session.py,
tests/test_rat_verification_ui.py, tests/test_work_context.py,
tests/test_omnibar.py, tests/test_workbench_scene.py; thêm probe
audit/rat_workbench_flash_review_20261016/test_live_detail_probe.py.

Capture native Cocoa từ source mới: toàn cảnh Chuột nối với Workbench bằng ba
chấm, khung nới khi có nội dung, kết quả tìm, trạng thái đang xử lý và xong/hủy,
compact/narrow và light/dark. Lưu PID/platform/source hashes và kịch bản
tái lập. Phân biệt fixture replay/widget grab với thao tác native và model thật.
Ghi rõ nếu IME chưa được thử trực tiếp; setText() không xác nhận bộ gõ native.

Báo cáo ngắn: thay đổi gì, test command/result, ảnh, giới hạn và file đã sửa.
Không tuyên bố tốc độ UI từ số đo backend hoặc gọi slice này là CoT mới đã được
chứng minh. Nếu luồng chat/tìm kiếm có xung đột, nêu trigger cụ thể và cách giải
quyết đã kiểm thử; không âm thầm thay toàn bộ routing.
