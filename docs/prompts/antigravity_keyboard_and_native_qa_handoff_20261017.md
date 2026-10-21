# Antigravity — hoàn tất bàn phím, nối native Hỏi tệp, kiểm tra offline

**Prompt tổng hợp mới nhất:**
`docs/prompts/antigravity_performance_natural_finder_thoughts_20261017.md`.
Người dùng bổ sung performance ưu tiên, thu gọn nhãn, tìm tự nhiên và visualize
thoughts; prompt mới điều khiển phạm vi mở rộng, gồm operation mở app có kiểm tra.
Tài liệu này giữ làm chi tiết wiring native QA và lifecycle cần tái sử dụng.

Người dùng muốn giao thêm việc cùng revision hiện tại. Làm theo thứ tự A → B → C;
lưu kết quả kiểm tra từng phần để Codex review được. Đọc AGENTS.md và
docs/project_scope.md. Giữ main, thay đổi đồng thời và recovery; không tạo branch,
commit/push/pull/reset. Giữ bố cục thought bubble đã đính chính.
Giữ cờ Workbench/finder mặc định tắt; native QA chỉ được chọn khi có cấu hình
model local rõ ràng, không tự dò rồi tải/nạp model cho người dùng.

## A. Chốt bốn lỗi bàn phím trước

Thực hiện `docs/prompts/antigravity_finder_keyboard_revision_20261017.md`:

1. Enter trên Hỏi phải kích hoạt Hỏi; không bubble thành mở file.
2. Tab/focus sang row khác phải đồng bộ selection và shortcut target.
3. Shift+Down giữ chọn văn bản native; Down thuần tại biên vẫn vào finder.
4. Snapshot cùng query giữ resource_id, vai trò action đang focus và scroll.

Baseline độc lập: 185 tests + 3 subtests qua, gồm 12 probe cũ. Probe bàn phím
mới còn 4 failed/2 passed tại
`audit/rat_finder_codex_review_r2_20261017/test_keyboard_followups.py`.
Giải quyết phần này trước khi thêm wiring MLX; không làm yếu assertions.

## B. Nối native MLX vào Hỏi tệp trong cùng UI

Mục tiêu: tệp tìm thấy → Hỏi → nhập câu hỏi → nhận đáp án có nguồn → hỏi tiếp,
hủy hoặc đổi nguồn. Dùng model MLX đã cài, không cần Ollama cho luồng native này.
Đây là tích hợp selected-document QA, không chuyển general agent sang MLX.

### Backend đã có — tái sử dụng

Đọc `docs/rat_document_service_20261016.md` và
`audit/rat_document_startup_20261016/report.md`:

- `Config.document_model_path` (mặc định rỗng), `document_model_preload`
  (mặc định false); launch overrides `RAT_DOCUMENT_MODEL_PATH` và
  `RAT_DOCUMENT_MODEL_PRELOAD` đã có. Cấu hình riêng chưa làm GUI dùng native.
- `AssistantRuntime(..., document_model_path=...)` sở hữu một
  `ResidentDocumentModel`. `runtime.preload_document_model()` trả Future hoặc
  None, không chặn caller. Load/generate/release dùng cùng owner thread.
- `answer_selected_document()` giữ indexed read, receipts, nguồn, giới hạn một
  generation; ưu tiên `runtime.document_model_client`. Có on_text/should_cancel.
- Backend có 90 tests qua, gồm preload/cancel/unload/close và đọc tệp thật với
  model giả. Adapter chỉ hỗ trợ QA từ trích đoạn tối đa 3.000 ký tự, không hỗ
  trợ tool-calling/thinking/response_format của general agent.

Không viết một model service/cache/pool thứ hai hoặc đổi prompt/backend,
max-context, read limit, cost semantics hay nghiên cứu trong lượt tích hợp này.

### Wiring và trạng thái

- Điểm vào: `rat/ui/omnibar.py` tạo runtime; `rat/ui/assistant_worker.py` đã gọi
  `answer_selected_document` khi có document_path, nhưng chưa truyền on_text ra UI.
- Truyền đường model cấu hình vào runtime khi chọn native. Đường sai hoặc model
  thiếu phải báo lỗi riêng cho native QA; window/finder vẫn dùng được. Native đã
  được chọn mà lỗi thì không âm thầm rơi về SLM/Ollama hoặc cloud.
- Trong settings hiện có, thêm điều khiển gọn để chọn thư mục model local và
  tùy chọn preload. Đủ dùng với model đã cài; không thêm trình download. Có thể
  áp dụng thay đổi từ lần khởi động sau và ghi rõ trong UI để tránh nạp hai model.
  Tôn trọng launch overrides đã có; không hardcode đường home/snapshot của máy dev.
- Khi preload được bật, gọi API Future một lần từ startup ownership phù hợp.
  Cửa sổ phải hiện và gõ/tìm metadata được trong lúc load. Chỉ hiển thị trạng thái
  quan sát được: đang chuẩn bị/sẵn sàng/lỗi; không dựng phần trăm hoặc suy nghĩ.
- Future callbacks chỉ phát queued signal về GUI; có guard service generation/
  shutdown để completion muộn không cập nhật window đã đóng. Không gọi .result()
  chờ future chưa xong trên GUI thread.
- Giữ một composer và draft/caret/focus. Click Hỏi chỉ chọn nguồn; submit mới đọc
  tệp và gọi model. Hover/mũi tên/Tab không load model, OCR, đọc sâu hoặc prefill
  tài liệu. Preload startup chỉ tải weights/tokenizer, không scan nội dung cá nhân.
- Nếu hiển thị streaming, nối on_text qua signal của AssistantWorker về GUI,
  kèm hoặc ràng buộc handle chứa turn_ref/execution_id/chat generation. Kiểm tra
  ownership lại tại delivery. Text đang stream là tạm thời; cancel/failure không
  ghi thành final thành công, không nhân đôi text lúc final response tới.
- Sau hủy, hỏi tiếp dùng được, chunk cũ bị bỏ. Đổi hoặc sửa tệp phải đọc lại dữ
  liệu mới theo backend có sẵn; không thêm answer cache hoặc generation dự phòng.
- Nhãn backend và lỗi của native QA phải đúng luồng đang dùng; không hướng người
  dùng kiểm tra Ollama cho lỗi native. Giữ nguồn/range/truncated label; đừng gọi
  trích đoạn là đã đọc toàn bộ tài liệu.

### Lifecycle cần nối đủ

- Hide window giữ phiên; quit thật mới hủy/đóng runtime. Không gọi native close
  đang chờ load/inference trên GUI thread, không terminate thread.
- Đọc cả `OmnibarWindow.shutdown/closeEvent` và
  `rat/os/app.py:ResidentApplication._on_app_quit` (đang nối aboutToQuit). Thiết
  kế ownership/quit handshake rõ ràng: giữ runtime/worker/bridge sống tới khi
  cleanup xong rồi mới kết thúc app. Chỉ đưa close vào worker mà thoát event loop
  ngay là chưa đủ. Không mang wait(31000) của luồng cũ vào native GUI cleanup.
- Native load đã bắt đầu không ngắt giữa file reads; phải chờ có quản lý, không
  báo đã unload/quit xong khi cleanup chưa hoàn tất. Lưu test quit lúc preload và
  lúc generation bằng backend giả trước khi thử model thật.

## C. Kiểm chứng và bàn giao

Trước sửa lưu manifest/hash; đối chiếu lại source trước khi ghi để giữ thay đổi
đồng thời. Tests mock cần kiểm tra selection, late chunks, lỗi path/load, preload
không chặn GUI, cancel → hỏi tiếp và quit. Giữ 90 tests backend; thêm test UI có
giá trị cho wiring/ownership, không chỉ kiểm widget tồn tại.

Chạy lại 12 probe cũ + 6 keyboard cases + tám module UI của handoff trước,
`tests/test_progressive_search.py`, `tests/test_selected_document_ui.py`,
`audit/rat_workbench_flash_review_20261016/test_live_detail_probe.py`, và 5 suite
backend trong `audit/rat_document_startup_20261016/report.md`. Lưu XML riêng cho
A và B, lỗi phát hiện thực tế và source hashes; không dùng số tests thay evidence.

Tám module UI là `tests/test_rat_magic_ui.py`, `tests/test_rat_one_box_ui.py`,
`tests/test_work_context_ui.py`, `tests/test_rat_chat_session.py`,
`tests/test_rat_verification_ui.py`, `tests/test_work_context.py`,
`tests/test_omnibar.py`, `tests/test_workbench_scene.py`. Năm suite backend là
`tests/test_document_model_startup.py`, `tests/test_mlx_document_session.py`,
`tests/test_selected_document_qa.py`, `tests/test_assistant_runtime.py`,
`tests/test_rat_headless_cli.py`.

Sau software checks, thử một phiên UI với checkpoint local đã có và tối đa
5 generations trên tệp synthetic do mình tạo/index trong DB tạm riêng: câu đầu,
hỏi tiếp, sửa tệp, hủy giữa câu trả lời, hỏi lại sau hủy. Không crawl/index thư
mục cá nhân. Chặn network/download/provider requests trong phiên này; nếu app
startup còn probe Ollama/cloud thì ghi nhận và tách khỏi native path rõ ràng.
Native QA phải chạy được khi Ollama không có; không gọi fallback để vượt test.

Đo submit → chữ đầu nhìn thấy và submit → hoàn tất; tách model-load time, dùng
wall time UI chứ không thay bằng raw_response.first_text_s. Báo RAM tiến trình
với cách đo rõ ràng; MLX allocation không phải tổng RAM app. Không áp một SLA
hoặc tuyên bố speedup từ các fixture khác nhau. Không chạy overnight benchmark.

Ảnh desktop/narrow/light/dark từ source cuối. Nếu dùng Qt Cocoa, metadata phải
thực sự ghi qpa_platform=cocoa; ảnh offscreen vẫn hữu ích nhưng ghi đúng loại.
Phân biệt QWidget.grab/fixture replay với tương tác native/live model. Native
IME chưa thử trực tiếp thì để pending, không suy ra từ setText/preedit giả lập.

Báo cáo ngắn: A sửa gì và test nào; B đã nối luồng nào; C command/result, raw
artifacts, ảnh, model/version, số calls, giới hạn. Không tuyên bố toàn bộ RAT đã
native/offline hoặc model quality đã đạt từ lát cắt Hỏi tệp này. Để general-agent
backend, app launching, semantic provider và thay đổi CoT cho tác vụ riêng.
