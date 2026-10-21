# Bước tiếp theo — Hỏi tệp trong UI dùng native MLX

Chuẩn bị trong lúc Antigravity sửa thought bubble. Đây là đề xuất tích hợp,
phần UI chưa triển khai hoặc gửi cho một agent khác. Không sửa các file UI đang
được Antigravity làm đồng thời.

Backend đã bổ sung trong lúc chờ: `Config.document_model_path`,
`Config.document_model_preload` và launch overrides; API không chặn
`AssistantRuntime.preload_document_model()` / `ResidentDocumentModel.preload()`
trả Future, dùng cùng owner thread. Xem phần startup trong
`docs/rat_document_service_20261016.md`. Chưa có consumer UI cho cấu hình/API này.

## Khoảng trống đã kiểm tra trong source

- `rat/ui/omnibar.py`: tạo `AssistantRuntime` với `SLMEngine`, chưa truyền
  `document_model_path`. Cấu hình giao diện còn hướng tới Ollama.
- `rat/ui/assistant_worker.py`: đã gọi `answer_selected_document` khi có
  `document_path`, có progress/step/cancel; chưa chuyển `on_text` ra GUI.
- `rat/engine/assistant_runtime.py`: có sẵn `document_model_path` và sở hữu
  `ResidentDocumentModel`. `answer_selected_document` ưu tiên client này nếu
  được cấu hình; thiếu client thì luồng cũ dùng SLM/Ollama.
- Runtime/CLI native và số đo headless đã có ở
  `docs/rat_document_service_20261016.md`. Không suy ra độ trễ UI từ số đo đó.

## Lát cắt nên làm sau khi UI ổn

1. Cấu hình đường model MLX đã cài, truyền vào runtime cho Hỏi tệp. Không tải
   model tự động, không hardcode đường home máy phát triển. Lỗi đường/model
   trả lỗi rõ; không âm thầm đổi provider khi đã chọn native.
2. Cho chuẩn bị model một lần trên worker khi startup nếu được cấu hình;
   cửa sổ vẫn hiện/gõ được. Tái sử dụng service giữa các câu hỏi. Thiếu model
   không được chặn tìm app/tệp bằng metadata/FTS.
3. Nếu thêm streaming, dùng queued signals kèm turn/execution identity và
   kiểm tra lại lúc nhận; chữ đang stream là tạm thời, cancelled/failed không
   thành câu trả lời cuối. Không append token cũ vào lượt mới.
4. Đóng service khi app thực sự quit, ngoài GUI thread trong lúc chờ cleanup.
   Phân biệt hide cửa sổ với quit. Load weights hiện không ngắt được giữa các
   file reads: shutdown phải chờ có quản lý, không terminate thread.

Native adapter hiện chỉ hỗ trợ selected-document QA, chưa hỗ trợ protocol tool
calling của general agent. Không thay `runtime.model_client` chung bằng adapter
này rồi tuyên bố toàn bộ assistant đã native. Tổng quát hóa backend là lát cắt
riêng. Ollama cũng có thể chạy offline; việc bỏ daemon và việc không dùng mạng
là hai yêu cầu cần kiểm tra riêng.

## Nghiệm thu nhỏ, thực tế

- Tìm tên app/tệp: không gọi model, không chờ model load, không mở tài nguyên
  chỉ vì hover hoặc điều hướng bằng phím.
- Chọn tệp đã index → Hỏi → câu hỏi tiếp: đúng nguồn, một lần generation mỗi
  câu, tái sử dụng model; sửa nội dung cùng path phải đọc lại dữ liệu mới.
- Hủy khi đang trả lời → hỏi tiếp, đổi nguồn và quit khi đang load/generate:
  không kết quả muộn, không mất draft hoặc treo GUI, không worker bị bỏ lại.
- Với fixture do nhóm tự tạo và model có sẵn, chặn network/model download để
  xác nhận riêng luồng native. Ghi load time, submit→chữ đầu tiên nhìn thấy,
  submit→hoàn tất và tổng RAM tiến trình; không gọi MLX allocation là RAM app.

Tái sử dụng tests backend và selected-document UI đang có; thêm regression
ownership/lifecycle có ý nghĩa. Chỉ chạy real-model acceptance nhỏ sau khi
phần mềm ổn; không lặp overnight benchmark trong lúc UI vẫn đang sửa.
