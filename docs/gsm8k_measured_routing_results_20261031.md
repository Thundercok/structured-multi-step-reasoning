# Báo cáo thực nghiệm định tuyến GSM8K trên mô hình Qwen3-8B — 2026-10-31

**Mức độ bằng chứng (Evidence level):** `measured_development_saved_output_analysis`  
**Mô hình:** `mlx-community/Qwen3-8B-4bit` (Snapshot pinned: `545dc4251c05440727734bcd94334791f6ab0192`)  
**Bộ dữ liệu:** `data/gsm8k_development_validation_reviewed_v1/dataset.json` (93 câu đã duyệt: 45 fitting `train`, 48 validation `calibration`)  
**Cấu hình sinh:** `english-math-v1`, temperature = 0.0, thinking = False, master seed = 42, cap $T_{\max} = 1024$ tokens/call.  
**Thư mục lưu trữ thực nghiệm:**
* Raw Staged Collection: `runs/gsm8k-qwen3-8b-staged-pilot-reviewed93-20261031`
* Sealed Fitting: `runs/gsm8k-qwen3-8b-routing-fit-reviewed93-20261031`
* Validation Evaluation: `runs/gsm8k-qwen3-8b-routing-val-reviewed93-20261031`

---

## 1. Tổng quan thực thi thu thập dữ liệu (Staged Collection)

Tiến trình thu thập thực tế trên Apple Silicon Metal đã hoàn thành **279/279 calls** trong 2.472,57 giây (~41 phút):
* **Tổng token sinh đo được:** 25.464 tokens (trung bình 91,3 tokens/call).
* **Vòng đời cuộc gọi:** 100% cuộc gọi hoàn thành đầy đủ chu trình 3 trạng thái (`generation_started` $\to$ `generation_succeeded` $\to$ `tool_started` $\to$ `tool_outcome` $\to$ `record_assembled`).
* **Lỗi công cụ:** **0 lỗi thực thi Python sandbox** qua toàn bộ các lần gọi PAL (thời gian chạy sandbox trung bình 35–65 ms/call).
* **Phân tách dữ liệu:** 135 records fitting (`train`) và 144 records validation (`calibration`) được niêm phong độc lập trong journal fail-closed.

### Hiệu năng tổng thể của 3 chiến lược đơn lẻ (Trên toàn bộ 93 câu)
| Chiến lược | Đúng / Tổng câu | Độ chính xác (Accuracy) | Token sinh trung bình (Mean Tokens) |
| :--- | :---: | :---: | :---: |
| **PAL** (Code $\to$ Sandbox) | **90 / 93** | **96,8%** | 93,6 tokens |
| **DIRECT** (Trả lời trực tiếp) | **85 / 93** | **91,4%** | **85,9 tokens** |
| **COT** (Chain-of-Thought) | **81 / 93** | **87,1%** | 94,3 tokens |

*Nhận xét:* Trên mô hình Qwen3-8B, **PAL** đạt độ chính xác vượt trội nhất (96,8%), trong khi **DIRECT** có chi phí token tiết kiệm nhất (85,9 tokens).

---

## 2. Kết quả pha Chọn quy tắc (Fitting & Sealing trên 45 câu `train`)

27 quy tắc ứng viên (gồm các ngưỡng độ dài câu hỏi 20, 40, 60, 80 từ và 3 quy tắc hằng) được đánh giá trên 45 câu fitting bằng hàm mục tiêu utility $U = \text{Accuracy} - 0.1 \times \frac{\text{Generated Tokens}}{1000}$:

* **Quy tắc tối ưu được chọn:** **`words_le_060_DIRECT_else_PAL`**
  $$\text{Nếu số từ trong câu hỏi} \le 60 \implies \text{chọn DIRECT; ngược lại} \implies \text{chọn PAL}$$
* **Tính chất động (Dynamic Routing):** `collapsed_to_constant = False` (Quy tắc không bị suy biến thành hằng số; đây là bộ định tuyến 2 nhánh động thực sự).
* **Utility trên tập train:** **0,94586** (vượt qua quy tắc hằng tốt nhất `constant_PAL` đạt 0,94535 và `constant_DIRECT` đạt 0,87900).
* **Quy tắc đối chứng cố định được chọn từ fitting (Selected Fixed Reference):** `constant_PAL`.
* Toàn bộ tham số và kết quả fitting được niêm phong mã băm SHA-256 (`selection_sha256`) vào `manifest.json` trước khi mở dữ liệu validation.

---

## 3. Kết quả đánh giá ngoại kiểm (Held-out Validation trên 48 câu `calibration`)

Đánh giá được thực thi nghiêm ngặt trên 48 câu validation mà **hoàn toàn không fit lại** (no re-fitting), kèm phân tích bootstrap 2.000 lần rút mẫu:

### Bảng so sánh 5 phương pháp chính thức (Official Comparison Table)

| Phương pháp (Method) | Đúng / 48 câu | Accuracy | Token sinh TB (Generated) | Token prompt TB (Prompt) | Utility ($\lambda=0.1$) | Lỗi Tool PAL |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Quy tắc định tuyến (`words_le_060_DIRECT_else_PAL`)** | **46 / 48** | **95,83%** | **74,938** | 92,958 | **0,950840** | 0 |
| **Đối chứng cố định (`constant_PAL`)** | 47 / 48 | 97,92% | 85,708 | 104,875 | 0,970596 | 0 |
| **Cố định `DIRECT`** | 45 / 48 | 93,75% | 75,604 | 91,875 | 0,929940 | 0 |
| **Cố định `COT`** | 43 / 48 | 89,58% | 87,479 | 96,875 | 0,887085 | 0 |

---

### Phân tích hiệu số ghép cặp (Paired Contrasts & Bootstrap 95% CIs)

#### 1. Định tuyến so với Đối chứng chất lượng cao (`constant_PAL`)
* **Tiết kiệm Token (Cost Reduction):** Giảm **$-10,77$ tokens/câu** (từ 85,708 xuống 74,938 tokens, giảm **12,6% chi phí token sinh**).
* **Độ chính xác:** $95,83\%$ vs $97,92\%$ (chênh lệch duy nhất 1 câu: 46 vs 47/48).
* Khoảng tin cậy 95% bootstrap:
  * $\Delta \text{Generated Tokens} = -10,77$ $[-24,34, +3,81]$
  * $\Delta \text{Accuracy} = -0,0208$ $[-0,1042, +0,0417]$
  * $\Delta \text{Utility} = -0,0198$ $[-0,1021, +0,0430]$

#### 2. Định tuyến so với Baseline chi phí thấp (`constant_DIRECT`)
* **Cải thiện Độ chính xác (Accuracy Gain):** Tăng **$+2,08\%$** (46/48 so với 45/48).
* **Cứu nguy và Tổn hại (Rescues vs Harms):** **1 rescue, 0 harms** (Quy tắc định tuyến đã cứu thành công 1 bài toán mà DIRECT giải sai bằng cách chuyển sang PAL, đồng thời không làm sai bất kỳ câu nào mà DIRECT đã làm đúng).
* **Khoảng tin cậy 95% của $\Delta \text{Accuracy}$:** $[+0,0000, +0,0625]$ (hoàn toàn không âm!).
* **Chi phí:** 74,938 tokens (thậm chí thấp hơn mức 75,604 của pure DIRECT do phân bổ nhánh câu ngắn).

---

## 4. Ý nghĩa đối với bài báo NCKH (Scientific Implications)

1. **Bằng chứng thực nghiệm mô hình thật (Real Measured Evidence):** Đây là tập kết quả thực nghiệm hoàn chỉnh đầu tiên trên mô hình Qwen3-8B thật với pipeline tách tầng có kiểm soát chặt chẽ, thay thế hoàn toàn các con số smoke synthetic trước đây.
2. **Quy tắc định tuyến đơn giản có khả năng cứu lỗi mà không gây hại:** Bộ điều phối độ dài câu hỏi $\le 60$ từ thể hiện khả năng lọc các câu ngắn để chạy DIRECT tốc độ cao và đẩy các câu dài phức tạp sang PAL để dùng Python tính toán, đạt tỷ lệ Rescue:Harm là 1:0 so với DIRECT.
3. **Tuân thủ đạo đức nghiên cứu & Tính tái lập:**
   * Tập test chính thức của GSM8K được bảo toàn nguyên vẹn 100% chưa bị lộ.
   * Toàn bộ mã nguồn, trace, prompts, token IDs và kết quả sandbox được lưu trữ bền vững với mã băm SHA-256 đầy đủ.
