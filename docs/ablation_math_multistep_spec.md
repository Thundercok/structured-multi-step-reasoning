# Đề cương Thử nghiệm Ablation: Kiểm chứng Nguyên nhân Gây Vòng lặp Cắt cụt trên MATH (Level 3–5)

> **Mục tiêu**: Xác định bằng thực nghiệm nhân quả liệu tỷ lệ cao các mẫu 1-Step (65%) trong tập huấn luyện có phải là nguyên nhân chính khiến mô hình biến `Step 1` thành đoạn văn độc thoại khổng lồ và rơi vào vòng lặp tham lam (greedy repetition loops) hay không.

> **Thay thế ngày 2026-11-09, trước khi chấm bất kỳ kết quả nào:** thiết kế ở mục 1–4 có nhiễu, xem mục 5. Lượt `math_lora_multistep_1000_s0` đã dừng ở vòng 650 và không được chấm.

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

---

## 5. Thiết kế sạch (ghi ngày 2026-11-09, trước khi huấn luyện)

**Vì sao đổi.** Trong tập lọc 252 bài, 121 bài (48%) dài hơn 512 token nên bị cắt mất đoạn kết khi học, so với 31% ở tập gốc. Số lượt đọc mỗi bài cũng khác (4,0 so với 1,4). Vì vậy không tách được tác động của bài một bước. Ngoài ra lệnh chấm ở mục 3 thiếu `--limit`, nên chỉ chạy 20 câu.

**Hai tập, cùng lấy từ `data/structured_math_term_v1` (không bài nào bị cắt), cùng 131 bài, cùng `valid.jsonl`:**

| Nhóm | Dữ liệu | Quy tắc | Bài một bước |
| --- | --- | --- | --- |
| Can thiệp | `data/structured_math_term_multistep131_v1` | Mọi bài có từ 2 bước | 0 |
| Đối chứng | `data/structured_math_term_random131_v1` | Chọn ngẫu nhiên, seed trong `tools/build_math_clean_ablation_dataset.py` | 95 |

Cả hai huấn luyện 1.000 vòng, `max-seq` 512, seed 0, rồi chấm trên 100 câu `data/math_source/structured_math_v1/dev.jsonl` với `--limit 100 --modes tuned --max-tokens 1024`.

**Quy tắc đọc, chốt trước khi có kết quả:**

- **Chỉ số chính:** số đầu ra bị cắt ở 1.024 token trên 100 câu, so ghép cặp bằng McNemar chính xác hai phía.
- **Ủng hộ giả thuyết** nếu nhóm can thiệp bị cắt ít hơn và $p < 0{,}05$. Các trường hợp còn lại là **không ủng hộ**.
- `format_valid`, độ đúng và số lần cắt ở bài có đúng 1 bước chỉ là chỉ số phụ, báo cáo đầy đủ nhưng không dùng để kết luận.
- Nếu không ủng hộ, chỉ kết luận rằng bỏ bài một bước không làm giảm cắt cụt ở quy mô này, không suy ra giới hạn của vết phẳng.
- Giới hạn: một seed, 131 bài, độ dài trung vị vẫn khác nhau (385 và 299 token) vì bài nhiều bước vốn dài hơn, và 100 câu dev đã được đọc trước đó, nên đây là kết quả thăm dò.

**Kết quả (chấm xong 2026-11-10 lúc 20:00, `audit/lora_math_multistep_clean_20261109/comparison.json`):**

| Chỉ số | Can thiệp | Đối chứng | Chỉ bên này có (can thiệp / đối chứng) | p |
| --- | :---: | :---: | :---: | :---: |
| Bị cắt ở 1.024 token (chính) | 20 | 25 | 10 / 15 | 0,424 |
| Đúng | 40 | 44 | 9 / 13 | 0,523 |
| `format_valid` | 44 | 46 | 18 / 20 | 0,871 |
| Bị cắt, đầu ra chỉ có 1 bước | 4 | 11 | | |
| Bị cắt do lặp nguyên dòng `Calc` | 4 | 6 | | |

Loss kiểm định ở vòng 1.000: 1,451 (can thiệp) và 1,408 (đối chứng).

**Kết luận theo quy tắc trên: không ủng hộ.** Ở quy mô này, bỏ bài một bước không làm giảm cắt cụt một cách rõ rệt. Không suy ra giới hạn của vết phẳng. Chênh lệch ở dòng "đầu ra chỉ có 1 bước" (4 so với 11) chỉ là chỉ số phụ, không dùng để kết luận.

---

## 6. Phân tích phụ ở vòng 150 (ghi ngày 2026-11-10, 14:32, trước khi nhóm đối chứng được chấm)

**Đã biết lúc ghi.** Nhóm can thiệp đã chấm ở vòng 1.000: 20/100 bị cắt, 40/100 đúng. Nhóm đối chứng đang huấn luyện ở vòng 760 và chưa được chấm ở vòng nào.

**Vì sao thêm.** Loss kiểm định của cả hai nhóm thấp nhất ở vòng 150 (0,619 và 0,609) rồi tăng lên khoảng 1,45 (nhóm can thiệp ở vòng 1.000, nhóm đối chứng ở vòng 750). Loss huấn luyện cùng lúc giảm còn 0,019 và 0,036. Mỗi bài được đọc khoảng 7,6 lần. Phép so ở vòng 1.000 vì vậy so hai mô hình đã học thuộc tập huấn luyện.

**Cách làm.** Chấm thêm checkpoint vòng 150 của cả hai nhóm trên cùng 100 câu, cùng lệnh chấm, bằng `audit/lora_math_multistep_clean_20261109/run_early.sh`. Vòng 150 được chọn từ loss trên `valid.jsonl`, không từ kết quả dev, nhưng sau khi đã thấy kết quả vòng 1.000 của nhóm can thiệp.

**Quy tắc đọc:**

- Kết luận của thí nghiệm vẫn là kết luận ở mục 5, tại vòng 1.000. Kết quả vòng 150 không thay được nó.
- Vòng 150 dùng cùng chỉ số và cùng phép kiểm như mục 5. Cả hai vòng đều được báo cáo, dù kết quả thế nào.
- Hai vòng cùng hướng: ghi rằng kết quả không phụ thuộc mức học thuộc. Hai vòng khác hướng: ghi là không nhất quán và cần seed mới, không chọn vòng có lợi.

**Giải thích cạnh tranh.** Cả hai nhóm đều học từ bài không bị cắt ở 512 token, khác với lượt gốc 725 bài (`math_lora_1000_s0`: 45/100 bị cắt trên cùng 100 câu). Hai giải thích cho ra hai dự đoán khác nhau về nhóm đối chứng ở vòng 1.000:

| Giải thích | Nhóm đối chứng bị cắt |
| --- | --- |
| Bài một bước gây cắt cụt ($H_1$) | Nhiều hơn 20 rõ rệt. Với 20 ca ở nhóm can thiệp, mục 5 cần từ 26 ca (nếu không cặp nào lệch ngược) đến khoảng 31 ca |
| Bài huấn luyện bị cắt gây cắt cụt | Gần 20, thấp hơn 45 nhiều |

Nếu rơi vào dòng thứ hai, đó chỉ là giả thuyết cho thí nghiệm sau: phép so với lượt gốc còn lẫn số bài (131 so với 725) và số lượt đọc (7,6 so với 1,4).

**Dự đoán:** không có dự đoán nào được ghi trước khi nhóm đối chứng được chấm.

**Ghi chú về thời điểm (2026-11-11).** Mục này được viết lúc 14:32 ngày 2026-11-10 nhưng được commit sau commit kết quả `a288aeef`, nên lịch sử git không chứng minh được bảng trên có trước kết quả vòng 1.000 của nhóm đối chứng. Khi mục này được commit, chưa checkpoint vòng 150 nào được chấm.

**Đối chiếu với bảng trên (thăm dò, làm sau khi có kết quả).** Nhóm đối chứng bị cắt 25 ca, không tách được khỏi 20 ca của nhóm can thiệp ($p = 0{,}424$) và dưới mức 26 ca của dòng thứ nhất. So với lượt gốc trên cùng 100 câu, ghép cặp bằng McNemar chính xác:

| Nhóm | Bị cắt | Lượt gốc | Chỉ nhóm này / chỉ lượt gốc | p |
| --- | :---: | :---: | :---: | :---: |
| Đối chứng | 25 | 45 | 2 / 22 | < 0,001 |
| Can thiệp | 20 | 45 | 5 / 30 | < 0,001 |

Cả hai nhóm đều bị cắt ít hơn lượt gốc nhiều, dù nhóm đối chứng vẫn có 95 bài một bước. Phép so này còn lẫn số bài và số lượt đọc, nên chỉ nêu giả thuyết cho thí nghiệm sau: bài huấn luyện bị cắt ở 512 token gây ra đầu ra bị cắt.
