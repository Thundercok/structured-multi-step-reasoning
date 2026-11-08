# Báo cáo Thực nghiệm LoRA trên Tập Toán Khó MATH (Level 3–5, Dev-100)

| Chế độ / Adapter | Đúng (`correct`) | KTC Wilson 95% | Đúng định dạng (`format_valid`) | KTC Wilson 95% | Bắt câu sai (`caught_wrong`) | Báo nhầm (`false_alarm`) | McNemar vs `base_prefill` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `base_prefill` (Gốc mồi Step 1) | 63/100 | 53.2–71.8% | 6/100 | 2.8–12.5% | 35/37 | 63/63 | — |
| `base_showcalc` (Gốc viết phép tính) | 64/100 | 54.2–72.7% | 0/100 | 0.0–3.7% | 36/36 | 64/64 | p = 1.0000 |
| `base_pal` (Chương trình Python) | 55/100 | 45.2–64.4% | 0/100 | 0.0–3.7% | 45/45 | 55/55 | p = 0.2430 |
| **`math_lora_1000_s0` (LoRA 1.000 vòng)** | 40/100 | 30.9–49.8% | 42/100 | 32.8–51.8% | 57/60 | 28/40 | p = 0.0001 |
| **`math_lora_term_1000_s0` (Terminated-512 LoRA)** | 38/100 | 29.1–47.8% | 52/100 | 42.3–61.5% | 55/62 | 23/38 | p = 0.0000 |

---

## 2. Phân tích Giải phẫu Lỗi & Hiện tượng Cắt cụt (Error & Truncation Anatomy)

Tổng số câu đã đánh giá: **100/100** (Không cắt cụt: **55**, Cắt cụt token tối đa: **45**).

### 2.1. Các câu không bị cắt cụt (Non-Truncated Items)
* **Độ chính xác (`correct`):** **40/55** (72.7%)
* **Đúng định dạng (`format_valid`):** **42/55** (76.4%)
* **Sai định dạng nhưng tính đúng đáp án:** **8** câu (mô hình suy luận ra đáp án đúng nhưng cú pháp vi phạm ngữ pháp quy định).
* **Lỗi ngữ pháp chi tiết:**
  - `line_outside_grammar`: **13** câu (chủ yếu do dòng `Calc:` chứa biểu thức ký hiệu LaTeX phức tạp hoặc phép biến đổi đại số).

### 2.2. Hiện tượng suy thoái cắt cụt (Truncation Breakdown)
* **Tổng số câu bị cắt cụt:** **45** câu.
* **Vòng lặp suy thoái lặp lại (Greedy Repetition Loop):** **34/45** (75.6%) câu bị bẫy trong vòng lặp vô hạn ở bước lập luận, lặp lại cùng một dòng $\ge 5$ lần hoặc chuỗi ký tự đuôi $\ge 3$ lần.
* **Lập luận dài vượt ngưỡng (Long Derivations):** **11/45** (24.4%) câu lập luận logic dài vượt giới hạn 1.024 token.

### 2.3. So sánh ghép cặp trên tập câu chung (Paired Comparison on Shared Completed Items)
* **Vs `base_prefill`:** Trên 100 câu chung, LoRA đúng **40/100** so với **63/100** của `base_prefill` (Chỉ LoRA đúng: **6**, Chỉ `base_prefill` đúng: **29**, McNemar exact **p = 0.0001**).
* **Vs `base_showcalc`:** Trên 100 câu chung, LoRA đúng **40/100** so với **64/100** của `base_showcalc` (Chỉ LoRA đúng: **7**, Chỉ `base_showcalc` đúng: **31**, McNemar exact **p = 0.0001**).

---

## 3. Kiểm định Ngưỡng RQ2 trên MATH (Pre-Registered Gate)

> **Quy tắc tiền đăng ký (`docs/research_plan.md` dòng 188–196):**  
> RQ2 duy trì hiệu lực nếu tỷ lệ không theo can thiệp $\ge 5\%$, có $\ge 5$ ca và $\ge 30$ vết đủ điều kiện.  
> Dưới 30 vết: *chưa đo được (`unmeasurable`)*. Dưới 5 ca hoặc $< 5\%$: *bác bỏ RQ2 (`inactive`), chuyển trọng tâm sang RQ3*.

### 3.1. Thống kê Khảo sát từ Bộ lập Can thiệp Trực tiếp (Live Planner Counts)
* **Vết đủ điều kiện can thiệp (`eligible`):** **2**
* **Lý do bỏ qua (Skipped Reasons):**
  - `invalid_format`: **47** câu
  - `non_numeric_answer`: **33** câu
  - `too_few_calcs`: **11** câu
  - `no_result_used_later`: **5** câu
  - `ambiguous_propagation`: **1** câu
  - `answer_needs_comparison`: **1** câu

### 3.2. Trạng thái Đánh giá Cổng RQ2 Chính thức
* **Trạng thái cổng hiện tại:** `unmeasurable (< 30 eligible traces)`
* **Số vết đủ điều kiện can thiệp:** 2
* **Số vết không cờ (`unflagged`):** 1
* **Số ca tuân thủ (`follows` + `follows_rounded`):** 1 + 0
* **Số ca không tuân thủ (`reverted` + `other`):** **0** (0.0%)
* **Kết luận:** `unmeasurable (< 30 eligible traces)`

---

## 6. Phân tích chi tiết theo Cấp độ và Chủ đề (Breakdown by Difficulty Level & Subject)

### 6.1. Phân tích theo Cấp độ Khó (Table 6.1: By Difficulty Level)

| Cấp độ | N | `base_prefill` Đúng | `base_showcalc` Đúng | `base_pal` Đúng | `math_lora_1000_s0` Chung | `math_lora_1000_s0` Đúng Cú pháp | `math_lora_1000_s0` Bị cắt cụt | `math_lora_1000_s0` Không cắt cụt |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Level 3 | 25 | 18/25 (72.0%) | 22/25 (88.0%) | 18/25 (72.0%) | 14/25 (56.0%) | 16/25 (64.0%) | 7/25 (28.0%) | 14/18 (77.8%) |
| Level 4 | 23 | 16/23 (69.6%) | 14/23 (60.9%) | 13/23 (56.5%) | 11/23 (47.8%) | 9/23 (39.1%) | 9/23 (39.1%) | 11/14 (78.6%) |
| Level 5 | 52 | 29/52 (55.8%) | 28/52 (53.8%) | 24/52 (46.2%) | 15/52 (28.8%) | 17/52 (32.7%) | 29/52 (55.8%) | 15/23 (65.2%) |

### 6.2. Phân tích theo Chủ đề Toán học (Table 6.2: By Subject)

| Chủ đề | N | `base_prefill` Đúng | `base_showcalc` Đúng | `base_pal` Đúng | `math_lora_1000_s0` Chung | `math_lora_1000_s0` Đúng Cú pháp | `math_lora_1000_s0` Bị cắt cụt | `math_lora_1000_s0` Không cắt cụt |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `algebra` | 27 | 25/27 (92.6%) | 23/27 (85.2%) | 21/27 (77.8%) | 18/27 (66.7%) | 18/27 (66.7%) | 5/27 (18.5%) | 18/22 (81.8%) |
| `counting_and_probability` | 11 | 5/11 (45.5%) | 6/11 (54.5%) | 5/11 (45.5%) | 3/11 (27.3%) | 4/11 (36.4%) | 7/11 (63.6%) | 3/4 (75.0%) |
| `geometry` | 16 | 4/16 (25.0%) | 6/16 (37.5%) | 5/16 (31.2%) | 2/16 (12.5%) | 5/16 (31.2%) | 10/16 (62.5%) | 2/6 (33.3%) |
| `intermediate_algebra` | 18 | 9/18 (50.0%) | 10/18 (55.6%) | 9/18 (50.0%) | 4/18 (22.2%) | 3/18 (16.7%) | 13/18 (72.2%) | 4/5 (80.0%) |
| `number_theory` | 13 | 8/13 (61.5%) | 8/13 (61.5%) | 8/13 (61.5%) | 5/13 (38.5%) | 3/13 (23.1%) | 5/13 (38.5%) | 5/8 (62.5%) |
| `prealgebra` | 11 | 10/11 (90.9%) | 8/11 (72.7%) | 6/11 (54.5%) | 7/11 (63.6%) | 8/11 (72.7%) | 2/11 (18.2%) | 7/9 (77.8%) |
| `precalculus` | 4 | 2/4 (50.0%) | 3/4 (75.0%) | 1/4 (25.0%) | 1/4 (25.0%) | 1/4 (25.0%) | 3/4 (75.0%) | 1/1 (100.0%) |
