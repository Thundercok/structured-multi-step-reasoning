# Đề cương Thử nghiệm Ablation: Kiểm chứng Nguyên nhân Gây Vòng lặp Cắt cụt trên MATH (Level 3–5)

> **Mục tiêu**: Xác định bằng thực nghiệm nhân quả liệu tỷ lệ cao các mẫu 1-Step (65%) trong tập huấn luyện có phải là nguyên nhân chính khiến mô hình biến `Step 1` thành đoạn văn độc thoại khổng lồ và rơi vào vòng lặp tham lam (greedy repetition loops) hay không.

---

## 1. Giả thuyết Khoa học & Tiêu chí Bác bỏ

- **Giả thuyết ($H_1$)**: Khi loại bỏ hoàn toàn các mẫu 1-Step khỏi tập huấn luyện (chỉ giữ lại các mẫu $\ge 2$ `Step`), mô hình sẽ học được cấu trúc phân rã bước rõ ràng, giảm tỷ lệ cắt cụt do độc thoại `Step 1` kéo dài trên tập Dev-100 từ **29/45 ca xuống dưới 10 ca**.
- **Tiêu chí bác bỏ (Disconfirmation Criteria)**:
  - Nếu tỷ lệ cắt cụt do `Step 1` kéo dài vẫn duy trì $> 20/45$ ca, giả thuyết bị bác bỏ. Hiện tượng nghẽn mạch không phải do dữ liệu 1-Step mà là giới hạn cố hữu của cấu trúc trace phẳng khi giải toán ký hiệu phức tạp.

---

## 2. Thiết kế Tập dữ liệu Thực nghiệm

1. **Tập gốc (Control)**: `data/math_source/structured_math_v1/train.jsonl` (725 mẫu, 65% là 1-Step).
2. **Tập lọc đa bước (Treatment - Multi-step only)**:
   - Đường dẫn: `data/math_source/structured_math_multistep_v1/train.jsonl`
   - Bộ lọc: Chỉ giữ các mẫu có $\ge 2$ dòng bắt đầu bằng `Step `.
   - Quy mô dự kiến: $725 - 473 = 252$ mẫu.
   - Validation set: Giữ nguyên `valid.jsonl` (76 mẫu) để bảo đảm tính tương đồng thẩm định loss.

---

## 3. Cấu hình Huấn luyện & Đánh giá (Dành cho Chat thực thi)

- **Script huấn luyện**:
  ```bash
  structured_llm/train.sh adapters/math_lora_multistep_1000_s0 1000 data/math_source/structured_math_multistep_v1 512 0
  ```
- **Tập đánh giá độc lập (Test bed)**:
  - `data/math_source/structured_math_v1/dev.jsonl` (100 câu cố định).
  - Lệnh đánh giá:
    ```bash
    .venv/bin/python -m structured_llm.evaluate \
      --adapter adapters/math_lora_multistep_1000_s0 \
      --data data/math_source/structured_math_v1/dev.jsonl \
      --out audit/lora_math_multistep_20261109/eval \
      --max-tokens 1024
    ```

---

## 4. Bảng Đo Lường So Sánh Cần Thu Thập

| Chỉ số | Baseline (`math_lora_1000_s0`) | Ablation (`math_lora_multistep_1000_s0`) |
| :--- | :---: | :---: |
| Số câu hoàn thành (Non-truncated) | 55/100 | *Cần đo* |
| Số câu bị cắt cụt (Truncated) | 45/100 | *Cần đo* |
| Cắt cụt do 1-Step độc thoại kéo dài | **29/45** | *Cần đo* |
| Vòng lặp nguyên dòng `Calc` | 7/45 | *Cần đo* |
| Độ chính xác tổng thể | 40/100 | *Cần đo* |
| Đúng cú pháp (`format_valid`) | 42/100 | *Cần đo* |
