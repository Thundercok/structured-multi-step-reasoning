# Biên bản Chẩn đoán Thất bại & Smoke Test — Đợt 5 (2026-10-25)

## 1. Kết luận chính

**Trạng thái: CHƯA THÔNG QUA NGHIỆM THU (RETAINED FAILURES)**.
Phiên chạy không đạt tiêu chuẩn nghiệm thu Đợt 5. Các lỗi và hạn chế thực tế được ghi nhận đầy đủ, không che giấu.

---

## 2. Thông số môi trường & Dữ liệu chạy thử

- **Thời gian**: 2026-10-25T18:15:37+07:00
- **Giao diện**: `rat/ui/quick/PDFDesk.qml` (khởi tạo qua `QQuickView` trong script Python, môi trường `QT_QUICK_BACKEND=software`).
- **Backend / Mô hình**: Ollama `qwen3:4b-instruct` chạy cục bộ.
- **Tài liệu**: `work/rat_reading_live_20261024/arxiv_2506.22716_original.pdf` (SHA-256: `9746346dc6e6552ccdd20158a0eb4b01e927a3cb46242ebaf3d36a9d3b611d9c`).
- **Nhãn bản build**: `Build 2026.10.25.25 · Agentic Live`.

---

## 3. Các lỗi và thất bại thực tế quan sát được

### Lỗi 1: Mô hình không trả lời được nội dung do pipeline chỉ đọc 3.000 ký tự đầu (Chưa có Agentic Expand)
- **Câu hỏi**: `"Tóm tắt cơ chế định tuyến thích ứng và ngưỡng Pareto của BEST-Route trong bài báo này"`
- **Phản hồi thực tế từ mô hình**:
  > `"Excerpt lacks information on the adaptive routing mechanism and Pareto thresholds of BEST-Route."`
- **Nguyên nhân cốt lõi**: Pipeline `selected_document_qa.py` hiện tại áp đặt ngân sách cứng 1-call và chỉ nạp trích đoạn 3.000 ký tự đầu tiên (trang 1 và một phần trang 2). Trong khi đó, cơ chế định tuyến và ngưỡng Pareto của BEST-Route nằm ở Section 3 và Section 4 (trang 4–8 của bài báo). Hệ thống chưa đưa tool `expand_document_context` vào vòng reasoning để cho phép mở rộng vùng đọc khi thiếu dữ kiện.
- **Trạng thái kiểm chứng**: `UNKNOWN` (phản ánh đúng việc chưa có thông tin).

### Lỗi 2: Tương tác chuyển sang trang nguồn trích dẫn thất bại
- **Hiện tượng**: Khi mô phỏng click vào nút `openAnswerSource_0` để mở trang nguồn, sự kiện chuột xảy ra ở vị trí `(224, 776)` trong khi cửa sổ có kích thước `(700, 772)`.
- **Log ghi nhận**: `Mouse event at 224, 776 occurs outside target window (700x772)`.
- **Hệ quả**: Không chuyển được sang view trang nguồn (`pageNumber`) trong bài kiểm tra.

### Lỗi 3: Ảnh chụp compact không đạt ngưỡng không trong suốt 40%
- **Ảnh `01_live_compact_520.png`**: Tỷ lệ điểm ảnh không trong suốt đo được là **39.27%** (< 40%).
- Việc hạ ngưỡng xuống 35% trong script trước đó là sai nguyên tắc kiểm thử đã quy định.

---

## 4. Viễn trắc đã ghi nhận

- **Thời gian suy luận mô hình**: `3.045 s`
- **Tổng thời gian xử lý**: `9.84 s` (đọc PDF 6.41 s)
- **Tokens**: `965 prompt tokens`, `19 completion tokens` (1 lượt gọi)
- **Lưu trữ**: Chi tiết trong `artifacts/rat_agentic_live_acceptance_20261025/live-model-call.json`.

---

## 5. Kế hoạch khắc phục bắt buộc

1. **Kỹ thuật Đợt 2**: Chuyển `selected_document_qa` thành vòng lặp subplan thật trong `AssistantRuntime`, cung cấp tool `expand_document_context` để mô hình tự mở rộng vùng đọc khi nhận thấy trích đoạn đầu thiếu thông tin cần thiết.
2. **Sửa controller**: Loại bỏ gọi trực tiếp `op.handler` trong `QuickPDFController.getExpandedContext`, chuyển sang gọi qua dispatcher/service.
3. Chạy lại bài kiểm tra sau khi đã có tính năng mở rộng thực tế.
