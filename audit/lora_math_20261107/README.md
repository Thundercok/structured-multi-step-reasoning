# Huấn luyện LoRA trên tập toán khó MATH (Level 3–5), 2026-11-07

Huấn luyện Qwen3-8B 4-bit với LoRA trên 725 bài toán kiểm chứng được (checkable) từ tập train của MATH (Level 3 đến 5).
Đây là bước kiểm định quy luật mở rộng cấu trúc suy luận từ số học GSM8K sang đại số, tổ hợp, lý thuyết số và hình học phức tạp.

## 1. Dữ liệu (`data/math_source/structured_math_v1/`)

Tạo bằng: `python -m structured_llm.math_convert`
- **Nguồn:** `train_source.jsonl` (801 câu Level 3–5 kiểm chứng được).
- **Tách tập:** Phân chia tất định bằng băm SHA-256 mã câu hỏi:
  - `train.jsonl`: 725 câu (SHA-256: `414001eba97fdafdebfc6f4882ea66bf3fba5d2accee7a6d7a9111df1c394287`)
  - `valid.jsonl`: 76 câu (SHA-256: `de32ad35d3e368f70e1b0d1c631f30d9d44e4d34c8ae24d296dbb870f058cc6d`)
  - `dev.jsonl`: 100 câu kiểm thử độc lập (Level 3–5).

### Phân bố độ khó và chủ đề (801 câu):
- **Độ khó:**
  - Level 5: 351 bài (43,8%)
  - Level 4: 236 bài (29,5%)
  - Level 3: 214 bài (26,7%)
- **Chủ đề:**
  - Đại số (Algebra): 174 bài
  - Tiền đại số (Prealgebra): 157 bài
  - Tổ hợp & Xác suất (Counting & Probability): 126 bài
  - Hình học (Geometry): 122 bài
  - Đại số nâng cao (Intermediate Algebra): 105 bài
  - Lý thuyết số (Number Theory): 78 bài
  - Tiền tích phân (Precalculus): 39 bài

## 2. Thông số Huấn luyện (`adapters/math_lora_1000_s0`)

- **Kiến trúc:** LoRA trên Qwen3-8B 4-bit (Rank 8, Scale 20.0, Dropout 0.0, 8 target layers, lr 5e-5, batch_size 1, grad_checkpoint=true, max_seq_length 512).
- **Số vòng (Iterations):** 1.000 vòng (~2,76 epoch trên 725 mẫu).
- **Hàm mất mát (Loss):** Khởi điểm 1.340 $\to$ Vòng 500: 0.642 $\to$ Vòng 1.000: **Train Loss 0.5140**, **Val Loss 0.5870**.
- **Tài nguyên phần cứng:** Apple M1 16GB, Đỉnh RAM: **5.915 GB**, Tốc độ: ~50.8 tok/s.
- **Hạn chế độ dài chuỗi huấn luyện:** Để duy trì dưới trần bộ nhớ đồ họa Metal 5.915 GB trên máy M1 16GB, tham số `--max-seq-length 512` đã cắt cụt phần đuôi `</think>\n\nAnswer:` của 105/725 (14,5%) bài toán mẫu dài trong tập train; điều này giải thích trực tiếp tại sao các chuỗi suy luận dài khi inference không phát ra thẻ đóng `</think>` và rơi vào vòng lặp suy thoái (greedy repetition loop).

## 3. Bảng Kết quả So sánh trên MATH Dev-100

| Chế độ / Adapter | Đúng (`correct`) | KTC Wilson 95% | Đúng định dạng (`format_valid`) | KTC Wilson 95% | Bắt câu sai (`caught_wrong`) | Báo nhầm (`false_alarm`) | McNemar vs `base_prefill` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `base_prefill` (Gốc mồi Step 1) | 63/100 | 53.2–71.8% | 6/100 | 2.8–12.5% | 35/37 | 63/63 | — |
| `base_showcalc` (Gốc viết phép tính) | 64/100 | 54.2–72.7% | 0/100 | 0.0–3.7% | 36/36 | 64/64 | p = 1.0000 |
| `base_pal` (Chương trình Python) | 55/100 | 45.2–64.4% | 0/100 | 0.0–3.7% | 45/45 | 55/55 | p = 0.2430 |
| **`math_lora_1000_s0` (LoRA 1.000 vòng)** | 40/100 | 30.9–49.8% | 42/100 | 32.8–51.8% | 57/60 | 28/40 | p = 0.0001 |
| **`math_lora_term_1000_s0` (Terminated-512 LoRA)** | 38/100 | 29.1–47.8% | 52/100 | 42.3–61.5% | 55/62 | 23/38 | p = 0.0000 |

## 4. Giải phẫu Lỗi & Điểm nghẽn Cắt cụt (The Flat-Trace Bottleneck)

Tổng số câu đã đánh giá: **100/100** (Không cắt cụt: **55**, Bị cắt cụt ở 1.024 tokens: **45**).

### 4.1. Các câu không bị cắt cụt (Non-Truncated Items)
- **Độ chính xác (`correct`):** **40/55** (72.7%)
- **Đúng định dạng (`format_valid`):** **42/55** (76.4%)
- **Suy luận đúng đáp án nhưng vi phạm cú pháp Cổng 0:** **8** câu (mô hình suy luận ra đáp án đúng nhưng dòng `Calc:` chứa biểu thức ký hiệu LaTeX phức tạp hoặc phép biến đổi đại số).
- **Chi tiết lỗi cú pháp:**
  - `line_outside_grammar`: **13** câu

### 4.2. Hiện tượng suy thoái cắt cụt (Truncation Breakdown)
- **Tổng số câu bị cắt cụt:** **45** câu.
- **Vòng lặp suy thoái (Greedy Repetition Loop):** **34/45** (75.6%) câu bị lặp vô hạn ở bước lập luận (lặp lại cùng 1 dòng $\ge 5$ lần hoặc chuỗi ký tự đuôi $\ge 3$ lần).
- **Lập luận dài vượt ngưỡng 1.024 token:** **11/45** (24.4%) câu.

### 4.3. So sánh ghép cặp trên tập câu chung (Paired Comparison)
- **Vs `base_prefill`:** Trên 100 câu chung, LoRA đúng **40/100** so với **63/100** của `base_prefill` (Chỉ LoRA đúng: **6**, Chỉ `base_prefill` đúng: **29**, McNemar exact **p = 0.0001**).

## 5. Kiểm định Ngưỡng RQ2 trên MATH (Pre-Registered Gate)

> **Quy tắc tiền đăng ký (`docs/research_plan.md` dòng 188–196):**  
> RQ2 duy trì hiệu lực nếu tỷ lệ không theo can thiệp $\ge 5\%$, có $\ge 5$ ca và $\ge 30$ vết đủ điều kiện.  
> Dưới 30 vết: *chưa đo được (`unmeasurable`)*. Dưới 5 ca hoặc $< 5\%$: *bác bỏ RQ2 (`inactive`), chuyển trọng tâm sang RQ3*.

- **Trạng thái cổng hiện tại:** `unmeasurable (< 30 eligible traces)`
- **Vết đủ điều kiện can thiệp (`eligible`):** **2** (Dưới ngưỡng 30 vết $\to$ Vùng chưa thể đo lường / *unmeasurable regime*).
- **Chi tiết các lý do loại trừ (Skipped Reasons):**
  - `invalid_format`: **47** câu
  - `non_numeric_answer`: **33** câu
  - `too_few_calcs`: **11** câu
  - `no_result_used_later`: **5** câu
  - `ambiguous_propagation`: **1** câu
  - `answer_needs_comparison`: **1** câu

## 6. Breakdown by Difficulty Level & Subject

### 6.1. Table 6.1: By Difficulty Level (Level 3, Level 4, Level 5)

| Level | N | `base_prefill` Acc | `base_showcalc` Acc | `base_pal` Acc | `math_lora_1000_s0` Overall Acc | `math_lora_1000_s0` Format Valid | `math_lora_1000_s0` Truncated | `math_lora_1000_s0` Non-Trunc Acc |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Level 3 | 25 | 18/25 (72.0%) | 22/25 (88.0%) | 18/25 (72.0%) | 14/25 (56.0%) | 16/25 (64.0%) | 7/25 (28.0%) | 14/18 (77.8%) |
| Level 4 | 23 | 16/23 (69.6%) | 14/23 (60.9%) | 13/23 (56.5%) | 11/23 (47.8%) | 9/23 (39.1%) | 9/23 (39.1%) | 11/14 (78.6%) |
| Level 5 | 52 | 29/52 (55.8%) | 28/52 (53.8%) | 24/52 (46.2%) | 15/52 (28.8%) | 17/52 (32.7%) | 29/52 (55.8%) | 15/23 (65.2%) |

### 6.2. Table 6.2: By Subject (7 MATH Domains)

| Subject | N | `base_prefill` Acc | `base_showcalc` Acc | `base_pal` Acc | `math_lora_1000_s0` Overall Acc | `math_lora_1000_s0` Format Valid | `math_lora_1000_s0` Truncated | `math_lora_1000_s0` Non-Trunc Acc |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `algebra` | 27 | 25/27 (92.6%) | 23/27 (85.2%) | 21/27 (77.8%) | 18/27 (66.7%) | 18/27 (66.7%) | 5/27 (18.5%) | 18/22 (81.8%) |
| `counting_and_probability` | 11 | 5/11 (45.5%) | 6/11 (54.5%) | 5/11 (45.5%) | 3/11 (27.3%) | 4/11 (36.4%) | 7/11 (63.6%) | 3/4 (75.0%) |
| `geometry` | 16 | 4/16 (25.0%) | 6/16 (37.5%) | 5/16 (31.2%) | 2/16 (12.5%) | 5/16 (31.2%) | 10/16 (62.5%) | 2/6 (33.3%) |
| `intermediate_algebra` | 18 | 9/18 (50.0%) | 10/18 (55.6%) | 9/18 (50.0%) | 4/18 (22.2%) | 3/18 (16.7%) | 13/18 (72.2%) | 4/5 (80.0%) |
| `number_theory` | 13 | 8/13 (61.5%) | 8/13 (61.5%) | 8/13 (61.5%) | 5/13 (38.5%) | 3/13 (23.1%) | 5/13 (38.5%) | 5/8 (62.5%) |
| `prealgebra` | 11 | 10/11 (90.9%) | 8/11 (72.7%) | 6/11 (54.5%) | 7/11 (63.6%) | 8/11 (72.7%) | 2/11 (18.2%) | 7/9 (77.8%) |
| `precalculus` | 4 | 2/4 (50.0%) | 3/4 (75.0%) | 1/4 (25.0%) | 1/4 (25.0%) | 1/4 (25.0%) | 3/4 (75.0%) | 1/1 (100.0%) |

## 7. Reproduction Commands

```bash
# 1. Huấn luyện và đánh giá toàn diện
audit/lora_math_20261107/run_math_training.sh

# 2. Cập nhật bảng so sánh và báo cáo thống kê
PYTHONPATH=. .venv/bin/python audit/lora_math_20261107/compare_math.py
```
