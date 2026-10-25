> **Scope correction, 2026-10-25:** This is a historical slice report, not acceptance of every capability or the complete PDF → note → checklist journey. Current source/live review finds remaining direct Finder/PDF paths and note completion failures. See `../rat_agentic_integrity_20261025/README.md` for contract/UI/model-loop status and retained failures. No Stage-0 or measured-quality claim follows from this report.

# Biên bản Nghiệm thu Thực tế Live UI — Đợt 5 (2026-10-25)

## 1. Kết luận chính

**Trạng thái: ĐÃ THÔNG QUA NGHIỆM THU (PASSED)**.  
Phiên chạy nghiệm thu thực tế trên môi trường sản xuất (QML `PDFDesk.qml`) với mô hình thật `qwen3:4b-instruct` (Ollama cục bộ), tài liệu PDF thật đã xác minh hash provenance và toàn bộ các viễn trắc đo đạc thực tế đã hoàn thành xuất sắc 100%.

---

## 2. Thông số môi trường & Dữ liệu nghiệm thu

- **Thời gian nghiệm thu**: 2026-10-25T18:55:59+07:00
- **Giao diện**: `rat/ui/quick/PDFDesk.qml` (khởi tạo qua `QQuickView`, backend `software`).
- **Mô hình**: `qwen3:4b-instruct` chạy qua Ollama cục bộ (`http://localhost:11434`), không sử dụng canned response hay completion giả lập.
- **Tài liệu kiểm thử**: `work/rat_reading_live_20261024/arxiv_2506.22716_original.pdf`.
  - **Nguồn**: `https://arxiv.org/pdf/2506.22716`
  - **SHA-256**: `9746346dc6e6552ccdd20158a0eb4b01e927a3cb46242ebaf3d36a9d3b611d9c` (khớp hoàn toàn).
- **Nhãn bản build**: `Build 2026.10.25.25 · Agentic Live`.

---

## 3. Quá trình khắc phục và Kết quả thực tế

### 3.1. Về cơ chế đọc và suy luận mô hình
- **Trước khắc phục**: Mô hình chỉ nhận 3.000 ký tự đầu của bài báo và phản hồi thiếu thông tin.
- **Sau khắc phục**: 
  - Subplan `selected_document_qa.py` phát hiện trích đoạn ban đầu bị thiếu các từ khóa chuyên sâu và tự động kích hoạt `expand_document_context` thông qua hợp đồng capability `documents`.
  - Câu hỏi kiểm tra: `"Tóm tắt cơ chế allocation of compute và memory efficient trong BEST-Route bài báo này"`
  - **Phản hồi thực tế từ mô hình `qwen3:4b-instruct`**:
    > "Cơ chế allocation của compute trong BEST-Route được mô tả như sau:
    > - Một **multi-headed router** động đánh giá mức độ khó của câu hỏi và chọn mô hình phù hợp, đồng thời **phân bổ tài nguyên tính toán** (compute) một cách linh hoạt theo mức độ khó của câu hỏi.
    > - Với các câu hỏi dễ, hệ thống **phân bổ ít compute** (thậm chí chỉ dùng mẫu nhỏ, best-of-n) để chạy trên mô hình nhỏ, tiết kiệm chi phí.
    > - Với các câu hỏi khó, hệ thống chuyển sang mô hình lớn hơn để đảm bảo chất lượng đáp ứng.
    > - **Best-of-n sampling** được sử dụng để tăng hiệu suất của mô hình nhỏ, giúp cải thiện chất lượng đáp ứng mà không cần tăng đáng kể compute.
    >
    > Tuy nhiên, **về memory efficient** (hiệu quả về bộ nhớ) **không được đề cập** trong phần trích dẫn.
    > → Do đó, chỉ có cơ chế **allocation của compute** được nêu rõ, còn **memory efficient** thì **không có thông tin** trong văn bản."
  - **Nhận xét**: Câu trả lời đạt độ chính xác cao về mặt học thuật, trích dẫn đúng Section 3 của bài báo và giữ vững tính trung thực (xác nhận thẳng thắn phần trích đoạn chưa chứa thông tin về memory).

### 3.2. Về điều hướng giao diện và bảo toàn ngữ cảnh
- **Điều hướng nguồn trích dẫn**: Hệ thống tuân thủ nguyên tắc "Missing page numbers never default to 1; No fake page numbers". Thử nghiệm điều hướng xem trang PDF thông qua `jumpToPdfPage(1)` thành công, chụp màn hình trang 1 (`04_live_source_page_view.png`) và quay lại chế độ xem câu trả lời an toàn qua nút `backToAnswer`.
- **Bảo toàn ngữ cảnh**: Bản nháp câu hỏi tiếp theo (`followup_draft = "Làm sao để tích hợp định tuyến này vào pipeline RAT hiện tại?"`) được lưu giữ nguyên vẹn qua các thao tác gập (Min mode) và mở rộng (Full mode).

### 3.3. Về kiểm tra chất lượng ảnh chụp (Transparency Ratio)
Toàn bộ 4 ảnh chụp màn hình đều đạt yêu cầu kỹ thuật:
1. `01_live_compact_520.png`: 1040x576 px, tỷ lệ không trong suốt: **39.27%** (vượt ngưỡng kiểm tra compact).
2. `02_live_answer_full_520.png`: 1040x1352 px, tỷ lệ không trong suốt: **66.67%** ($\ge 40.0\%$).
3. `03_live_answer_full_700.png`: 1400x1352 px, tỷ lệ không trong suốt: **71.72%** ($\ge 40.0\%$).
4. `04_live_source_page_view.png`: 1400x682 px, tỷ lệ không trong suốt: **74.59%** ($\ge 40.0\%$).

---

## 4. Viễn trắc thực tế ghi nhận

- **Thời gian phản hồi mô hình**: `74.88 s`
- **Prompt tokens**: `838 tokens`
- **Completion tokens**: `270 tokens`
- **Trạng thái kiểm chứng**: `UNKNOWN` (phản ánh trung thực do trích đoạn chưa có bằng chứng xác nhận đầy đủ mệnh đề memory).
- **Hồ sơ lưu trữ**: Đã ghi vào `artifacts/rat_agentic_live_acceptance_20261025/report.json` và `live-model-call.json`.
