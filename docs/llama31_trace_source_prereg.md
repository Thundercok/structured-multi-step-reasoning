# Đăng ký trước (H5): Tái lập nguồn vết (`self` vs. `human`) và cơ chế trật đường ray trên `Llama-3.1-8B-Instruct` (`fp16`)

> **Trạng thái: CÓ HIỆU LỰC từ 2026-11-27** (người làm đề tài đã duyệt khóa quy tắc đọc trước khi sinh bất kỳ đầu ra nào từ `Llama-3.1-8B-Instruct`).
> **Quy tắc liêm chính:** Đã khóa và push lên `main` trước khi chạy notebook trên Kaggle GPU.

---

## 1. Mục tiêu (Gỡ đồng thời 3 hạn chế lớn của H3/H4)

Trên `Qwen3-8B` (4-bit MLX), H3 và H4 cho thấy SFT trên vết người (`human`) làm giảm `follows` so với vết tự sinh (`self`), và phân tích hậu nghiệm chỉ ra ~80% mức giảm đến từ **trật đường ray sau khi đã dùng số mới** (`derailed_after_using_new`) thay vì bỏ qua bước (`bypass_or_revert`). Tuy nhiên còn 3 câu hỏi mở:
1. **Khác họ mô hình & không có chế độ `<think>` bẩm sinh:** Hiệu ứng có lặp lại ngoài họ Qwen (cụ thể trên `meta-llama/Llama-3.1-8B-Instruct`) không?
2. **Không lượng tử hóa 4-bit:** Hiệu ứng có giữ nguyên khi huấn luyện & suy luận ở **`fp16` (16-bit)** không?
3. **Loại bỏ hoàn toàn nhiễu bước thiếu `Calc:` (Limitation #1):** Trong H3/H4 có 8/229 vết `human` thiếu `Calc:` ở bước cuối (`answer_from_last_calc = False`) và 28/229 vết có ít nhất một `Step` không kèm `Calc:`. Ở H5, ta **lọc chặt ngay từ đầu**: mọi `Step` trong cả `self` lẫn `human` bắt buộc có ít nhất 1 dòng `Calc:` hợp lệ và `answer_from_last_calc = True`.

Đồng thời, phân rã **Derailment vs. Bypass** (vốn là khám phá hậu nghiệm trên Qwen3-8B) nay được **tiền đăng ký chính thức thành H5b** trước khi sinh dữ liệu trên Llama-3.1-8B.

---

## 2. Thiết kế thực nghiệm

### 2.1 Mô hình & phần cứng
- **Mô hình gốc:** `meta-llama/Llama-3.1-8B-Instruct` ở độ chính xác **`torch.float16` (`fp16`)**, phân bổ qua `2× NVIDIA T4` (32 GB VRAM trên Kaggle, `device_map="auto"`). Ghi lại `commit_hash` / revision của snapshot HuggingFace vào `manifest.json`.
- **Chat template:** Mẫu hội thoại chuẩn của Llama-3.1 (`tokenizer.apply_chat_template`), cắt chuỗi tại `<|eot_id|>` / `eos_token_id`.

### 2.2 Bộ lọc cặp vết huấn luyện sạch tuyệt đối (`keep_strict`)
1. Nguồn ứng viên: các câu tập `train` của GSM8K (theo đúng thứ tự `gsm8k.rank_key`, loại 120 câu dev cũ, `SOURCE_SHA256 = 17f347dc...`) mà lời giải người chuyển sang `Step`/`Calc` (`enrich_step1=True`) thỏa mãn đồng thời:
   - `format_valid == True`, `errors == []`, `calc_accuracy == 1.0`, **`answer_from_last_calc == True`**;
   - **Mọi `Step` trong `parse(human_trace).steps` đều có `len(step.calcs) >= 1`** (0 bước thiếu `Calc:`);
   - Chuỗi huấn luyện sau khi bọc chat template có độ dài **$\le 512$ token** (theo tokenizer Llama-3.1).
2. Chạy `base_prefill` (cùng `INSTRUCTION` 1-shot và mồi `<think>\nStep 1:`, greedy, `max_new_tokens = 1024`) tăng dần $N = 400, 600, \dots, 2000$ cho tới khi thu được **$K \ge 200$** câu mà vết `self` cũng thỏa toàn bộ điều kiện `keep_strict` (không cắt cụt, đúng đáp án `gold`, `format_valid`, `calc_accuracy == 1.0`, `answer_from_last_calc == True`, 0 bước thiếu `Calc:`, và độ dài chuỗi huấn luyện $\le 512$ token).
3. Nếu tại $N = 2000$ vẫn có $K < 200$: dừng trước khi huấn luyện và báo cáo không đủ vết hợp lệ, không hạ tiêu chuẩn `keep_strict`.
4. Cả hai tập `data/self/train.jsonl` và `data/human/train.jsonl` giữ **đúng $K$ câu đó theo cùng thứ tự dòng**. Kiểm tra tự động `check.json` phải báo `problems == []` trước khi huấn luyện.

### 2.3 Huấn luyện LoRA (khớp siêu tham số MLX của H3/H4)
- **4 adapter:** `{self, human} × {seed 0, seed 1}`.
- **Cấu hình PEFT LoRA:** Áp vào **8 lớp Transformer cuối cùng** (`layers 24..31` của 32 lớp), đủ **7 ma trận chiếu tuyến tính** (`q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj`), `r = 8`, `lora_alpha = 160` (`scale = 20.0`), `lora_dropout = 0.0`, `bias = "none"`.
- **Tối ưu hóa:** `Adam` (`lr = 5e-5` hằng số, `weight_decay = 0.0`), `batch_size = 1`, `iters = 200` bước cập nhật, `max_seq_length = 512`, tính loss trên toàn chuỗi (`mask_prompt = False`, giống `mlx_lm`). Seed đặt cả thứ tự lấy mẫu câu lẫn khởi tạo LoRA.

### 2.4 Tập đánh giá và can thiệp
- **Tập đo:** 500 câu đầu của `data/gsm_plus_v1/holdout_819.jsonl` (`sha256 = d079e99a...`, cùng tập 500 câu của H4; hoàn toàn mới với Llama-3.1-8B).
- **Chấm sạch (`tuned` & mốc `base_prefill`):** Greedy (`do_sample = False`), `max_new_tokens = 1024`, ghép lô cố định `batch_size = 8` theo đúng thứ tự file để hai mô hình chịu cùng ranh giới lô.
- **Can thiệp (`plan_intervention` & `intervene.classify`):** Cùng hàm lập kế hoạch và phân loại tất định của repo, greedy, `max_new_tokens = 512`, `batch_size = 8`.

---

## 3. Giả thuyết tiền đăng ký và quy tắc đọc cố định

### 3.1 Phép kiểm chính H5 (`self` vs. `human` trên chỉ số B1)
- **Đơn vị đo (B1):** Các câu trong 500 câu mà **cả hai** adapter `self` và `human` của cùng một seed đều lập được kế hoạch can thiệp và đều có `expected != None`.
- **Kiểm định:** McNemar chính xác hai phía cho Seed 0 ($p_0$) và Seed 1 ($p_1$), kiểm soát sai số họ ở **$\alpha = 0,05$ theo Holm–Bonferroni** ($p_{\min} < 0,025$; nếu đạt thì kiểm tiếp $p_{\max} < 0,05$).
- **Quy tắc đọc:**
  1. **Tái lập đầy đủ (2/2 seed):** `self > human` ở cả hai seed, $p_{\min} < 0,025$ và $p_{\max} < 0,05$.
  2. **Ủng hộ một phần (1/2 seed):** $p_{\min} < 0,025$ theo chiều `self > human`, seed còn lại cùng chiều nhưng $p_{\max} \ge 0,05$.
  3. **Không phân biệt được:** $p_{\min} \ge 0,025$.
  4. **Ngược giả thuyết / bất nhất:** Có seed đạt ý nghĩa thống kê theo chiều `human > self`.

### 3.2 Phép kiểm cơ chế tiền đăng ký H5b (Derailment vs. Bypass, có điều kiện trên H5)
Áp dụng đúng hàm phân loại tất định `classify_b1_record` (`audit/trace_dose_20261120/decompose_continuations.py`) trên tập câu chung B1 của từng seed:
- **H5b-Derail:** So tỉ lệ `derailed_after_using_new` giữa `human` và `self` bằng McNemar chính xác hai phía (Holm–Bonferroni qua 2 seed, $\alpha = 0,05$).
- **H5b-Bypass:** So tỉ lệ `bypass_or_revert` giữa `human` và `self` bằng McNemar chính xác hai phía.
- **Cách đọc H5b:** Cơ chế *"trật đường ray sau khi dùng số mới chiếm ưu thế"* được xác nhận tiền đăng ký nếu `human` có `derailed_after_using_new` cao hơn `self` có ý nghĩa thống kê (ít nhất $p_{\min} < 0,025$) và mức chênh điểm phần trăm của `derailed` lớn hơn mức chênh của `bypass_or_revert`.

### 3.3 Chỉ số phụ & kiểm tra độ nhạy (báo cáo kèm)
- Chỉ số gốc (gộp cả `expected = None` trên các câu chung có kế hoạch).
- Chỉ tính trên các câu cả hai cùng giải đúng ban đầu (`originally_correct == True`).
- So mô tả với mốc `base_prefill` của Llama-3.1-8B trên cùng 500 câu.
- Bảng đầy đủ cho 5 mô hình (`base_prefill`, `self_s0`, `human_s0`, `self_s1`, `human_s1`): `format_valid`, `accuracy` (kèm Wilson 95% CI), `truncated`, `planned`, `flagged` (`expected = None`), `taxonomy`, `bypass_or_revert`, `derailed_after_using_new`.
