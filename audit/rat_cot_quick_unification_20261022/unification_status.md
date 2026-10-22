# Trạng thái Hợp nhất Toàn diện RAT–CoT & PDF Desk — 2026-10-22

Thực hiện theo chỉ đạo tại `docs/rat_cot_end_to_end_next_20261022.md`. Toàn bộ hệ thống đã hợp nhất trên bề mặt giao diện chính Qt Quick (`rat/ui/quick/PDFDesk.qml`), kết nối trực tiếp với runtime suy luận nhiều lượt, context snapshot, optimistic locking artifact store và các năng lực đọc/tìm kiếm PDF.

## 1. Entry Points & Routing

- **Primary Entry Point (`python main.py`)**: Khởi chạy trực tiếp `rat.ui.quick_app.main()`, mở giao diện Qt Quick Desk hợp nhất.
- **Explicit PDF mode (`python main.py quick-pdf`)**: Khởi chạy Quick Desk với cờ định hướng tài liệu.
- **Legacy Widgets Compatibility (`python main.py widgets` / `spotlight` / `omnibar`)**: Đường dẫn tương thích mở giao diện QtWidgets cũ khi cần kiểm tra đối chiếu.
- **CLI Commands (`python main.py search|index|status|ask|...`)**: Giữ nguyên không suy giảm.

## 2. Kiến trúc Hợp nhất

- **Unified Controller (`rat/ui/quick_pdf_controller.py`)**:
  - Không tạo controller thứ hai, không tạo tutor screen hay keyword router.
  - Sở hữu `AssistantRuntime` và `ConversationHistory`, điều phối qua `ExecutionRequest` chuẩn và `create_execution_worker`.
  - Sử dụng hàng đợi tín hiệu cross-thread (`_execution_delivered`, `_execution_status_delivered`) với `Qt.ConnectionType.QueuedConnection` để cập nhật trạng thái an toàn trên luồng giao diện QML từ background worker.
  - Chuẩn hóa kết quả qua `execution_response(req, raw_result)` -> `AgentResponse` với các trạng thái rõ ràng: `completed`, `budget_exceeded`, `timeout`, `unresolved`, `failed`.
  - Quản lý phiên bản dữ kiện qua `ArtifactStore` dùng chung, hỗ trợ optimistic locking (`expected_revision`), gắn kết artifact với turn.
  - Điều hướng lịch sử phi phá hủy (`navigateToTurn`): cập nhật hiển thị về câu hỏi/câu trả lời quá khứ mà không dispatch model mới và không xóa draft đang soạn thảo của người dùng.
  - Nút sao chép ngữ cảnh đa năng (`copyCitation`): sao chép trích dẫn số trang khi đang đọc PDF, sao chép nội dung câu trả lời khi đang xem kết quả trợ lý (`view === "answer"`).
  - Nút đóng/gỡ PDF (`clearPdf`): giải phóng tài liệu và chuyển placeholder về chế độ trò chuyện tổng quát.

- **Giao diện Qt Quick (`rat/ui/quick/PDFDesk.qml`)**:
  - Tích hợp khung hiển thị kết quả suy luận (`view === "answer"`) với badge trạng thái (accent color), câu hỏi gốc, và văn bản trả lời (`TextArea` hỗ trợ select/copy).
  - Composer placeholder tự động chuyển đổi theo ngữ cảnh: `"Tìm gì trong tài liệu này?"` khi có PDF; `"Chuột nghe đây. Bạn cần gì?"` khi ở chế độ tổng quát.

## 3. Nghiệm thu Kịch bản 1–8 trên QML Flow Thật (`tests/test_quick_unified_flow.py`)

1. **Bước 1 — Khái niệm**: Giải thích binary search, engine provenance rõ ràng, UI chuyển sang view "answer", verifier status UNKNOWN.
2. **Bước 2 — Đưa mảng & mục tiêu 8**: Tạo artifact dữ kiện ở v1, lưu trữ vào store thành công.
3. **Bước 3 — "Sao phải mid + 1?"**: Chuyển context transport chứa dữ kiện của lượt trước mà không yêu cầu nhập lại; sao chép câu trả lời qua clipboard được xác nhận.
4. **Bước 4 — "Đổi sang tìm 6"**: Tạo revision v2 với optimistic locking; snapshot và dữ kiện của lượt 8 ở v1 được bảo toàn nguyên vẹn; kiểm tra từ chối stale revision.
5. **Bước 5 — Quay lại lượt giải thích**: Điều hướng không dispatch model mới (0 dispatches); draft đang soạn được giữ nguyên vẹn.
6. **Bước 6 — Hủy giữa chừng & hỏi tiếp**: Hủy cooperative an toàn; callback muộn từ worker cũ bị từ chối; lượt tiếp theo tạo execution ID / generation mới.
7. **Bước 7a–d — Quản lý ngân sách & xử lý lỗi**:
   - Quota cứng = 0: 0 token phát sinh, trả `budget_exceeded`.
   - Thiếu context tham chiếu: fail-closed với `reasoning_context_unavailable`.
   - Ngoại lệ backend: ghi nhận `failed` nhưng bảo toàn sổ cái chi phí.
   - Timeout deadline: ngắt worker và bảo lưu chi phí.
8. **Bước 8 — Hồi quy PDF**: Chọn file, tìm kiếm từ khóa, đọc trang, trích dẫn, và gỡ file hoạt động trơn tru.

## 4. Bằng chứng Kiểm thử Toàn bộ

```text
tests/test_quick_unified_flow.py .............                           [ 21%]
tests/test_quick_pdf.py ......                                           [ 31%]
tests/test_dsa_multi_turn_flow.py ............                           [ 51%]
tests/test_research_study.py ............                                [ 71%]
test_optimal_stopping.py ............                                    [ 91%]
test_entry_predictor.py .....                                            [100%]

============================= 60 passed in 12.06s ==============================
```

- Ngân sách gọi model thật: **0 VND / 0 tokens** (giữ nghiêm ngặt Stage 0).
- Không tự ý commit/push/branch git. Giữ nguyên working tree trên nhánh `main`.
