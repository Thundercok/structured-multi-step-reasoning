# Đăng ký trước: liều lượng vết người (0 / 25 / 50 / 75 / 100%) và mức bám bước

Ghi ngày 2026-11-20, trước khi tạo dữ liệu trộn, huấn luyện adapter mới hoặc chạy bất kỳ đánh giá nào trên tập đo.
Người làm đề tài đã chốt luận điểm mục tiêu (Bản B trong `docs/paper/outline_20261116.md`) và các lựa chọn thiết kế
(D1–D5) ngày 2026-11-20. Mã: `structured_llm/trace_mix.py`, `audit/trace_dose_20261120/analyze.py`,
`audit/trace_dose_20261120/run_phase.sh`.

## Câu hỏi

Thí nghiệm H3 (`docs/trace_source_prereg.md`, lặp lại ở seed 0 và seed 1) cho thấy trên 500 câu GSM-Plus đầu tiên,
adapter huấn luyện trên vết tự viết (`self`) làm theo bước bị sửa nhiều hơn adapter huấn luyện trên vết người (`human`):
+8,6 điểm (p = 0,023) ở seed 0 và +9,7 điểm (p = 0,007) ở seed 1.

Câu hỏi tiếp theo: **mức bám bước có giảm dần đều theo tỉ lệ vết người trong tập huấn luyện không, hay đó chỉ là hiệu ứng
bậc thang / nhị phân (hoặc do `self` ít thay đổi so với mô hình gốc)?**

## Thiết kế

### Dữ liệu huấn luyện (tập lồng nhau, giữ nguyên thứ tự dòng)

- Nguồn: đúng hai tập 229 câu của H3 tại `audit/trace_source_20261117/data/`:
  - `self/train.jsonl` (sha256: `fc3008919661319244a09d90acd352b6be95a5a586f6b6b1777c28239c6edf03`)
  - `human/train.jsonl` (sha256: `3723d40bcec4491bf76cf1621812232dd84a1653c7ec0bf309815538120a5a50`)
  - Tập valid dùng chung: `data/structured_gsm8k_enriched_v1/valid.jsonl`.
- Xếp hạng 229 chỉ số dòng `0..228` tất định bằng `sha256(f"20261120:{i}")` (`structured_llm/trace_mix.py`).
- Với 5 mức tỉ lệ **0 / 25 / 50 / 75 / 100%**, số dòng dùng vết `human` lần lượt là **0 / 57 / 114 / 172 / 229**
  (tỉ lệ chính xác `human_frac = k / 229`: `0.0, 0.248908, 0.497817, 0.751092, 1.0`).
- **Tính lồng nhau chặt:** $S_0 \subset S_{25} \subset S_{50} \subset S_{75} \subset S_{100}$.
- **Thứ tự dòng giữ nguyên hoàn toàn** ở cả 5 tập train, nên ở cùng một seed, mọi bước huấn luyện thấy cùng chuỗi câu hỏi.
- Trước khi huấn luyện, `audit/trace_dose_20261120/check.py` phải đạt 0 lỗi (`problems == []`, 0 dòng sai định dạng, 0 dòng > 512 token).

### Huấn luyện

- Dùng lại nguyên vẹn 4 adapter đã có cho hai đầu 0% và 100%:
  - `adapters/trace_self_200_s0`, `adapters/trace_self_200_s1` (0%)
  - `adapters/trace_human_200_s0`, `adapters/trace_human_200_s1` (100%)
- Huấn luyện thêm 6 adapter mới cho 25 / 50 / 75% ở seed 0 và seed 1:
  - `adapters/trace_mix{25,50,75}_200_s{0,1}`
  - Giữ y hệt siêu tham số của H3: `structured_llm/train.sh <dst> 200 <data> 512 <seed>` (LoRA 8 lớp, batch 1, lr 5e-5, 200 vòng, max_seq 512).

### Tập đánh giá sạch (không giao với H3)

- **Dữ liệu:** 500 câu đầu của `data/gsm_plus_v1/holdout_819.jsonl` (sha256: `d079e99a5b9cef8d887f28ac39ac20b0a1b14cdee5b003a451d67087651f6e7a`).
- Các câu này thuộc cùng loại biến đổi `numerical substitution`, nhưng **tách biệt hoàn toàn** (`shared_with_first_500 == 0`) với 500 câu của H3 và chưa từng được chấm trên bất kỳ adapter `trace_*` nào.
- Đánh giá cả 10 adapter (5 tỉ lệ × 2 seed) bằng cùng lệnh `structured_llm.evaluate --modes tuned --max-tokens 1024 --limit 500` (greedy) và cùng bộ can thiệp `run_standard_interventions` (`max_tokens=512`).

## Giả thuyết chính (H4) và quy tắc đọc

- **Chỉ số:** `follows` khớp chính xác (`outcome == "follows"`), trên toàn bộ các quan sát có kế hoạch can thiệp ở cả 10 ô (5 tỉ lệ × 2 seed).
- **Mô hình chính:** hồi quy logistic có random intercept theo câu hỏi (tích phân Gauss–Hermite 21 điểm):
  $$\text{logit}\,P(\text{follows}_{ij} = 1 \mid u_i) = \beta_0 + \beta_{\text{human}}\,x_{ij} + \beta_{\text{seed}}\,s_{ij} + \sigma u_i, \qquad u_i \sim \mathcal{N}(0, 1)$$
  trong đó $x_{ij} = k/229$ là tỉ lệ vết người, $s_{ij} \in \{0, 1\}$ là seed.
- **Phép kiểm chính:** Likelihood Ratio Test (LRT, 1 bậc tự do, hai phía) cho $H_0: \beta_{\text{human}} = 0$, ngưỡng **$\alpha = 0,05$**.
- **Quy tắc đọc cố định (không sửa sau khi thấy số):**
  1. Nếu $p_{\text{LRT}} < 0,05$ và $\hat{\beta}_{\text{human}} < 0$: **ủng hộ xu hướng giảm theo tỉ lệ vết người**.
  2. Nếu $p_{\text{LRT}} \ge 0,05$: **không phân biệt được** — bỏ vế *"monotonically"* trong Bản B và lùi về Bản A.
  3. Nếu $p_{\text{LRT}} < 0,05$ và $\hat{\beta}_{\text{human}} > 0$: **ngược giả thuyết**.

### Kiểm tra phi tuyến / bậc thang (rất quan trọng cho từ *"monotonically"*)

Một đường bậc thang (ví dụ 0% cao, còn 25–100% cùng rớt xuống đáy) vẫn có thể cho $p_{\text{LRT}} < 0,05$ ở mô hình tuyến tính.
Vì vậy `analyze.py` tính kèm LRT 3 bậc tự do so sánh mô hình 5 mức rời rạc với mô hình tuyến tính (`nonlinearity_lrt_3df`), cùng tỉ lệ `follows` từng mức và hệ số Spearman $\rho$.
- Chỉ giữ từ *"monotonically"* trong Bản B nếu H4 đạt **và** kiểm tra phi tuyến + bảng 5 mức cho thấy mức bám bước thật sự giảm dần qua các mức trung gian (không phải rơi 1 bước từ 0% sang 25% rồi phẳng). Nếu là dạng bậc thang/bão hòa, ghi trung thực đó là hiệu ứng ngưỡng (threshold effect).

## Chỉ số phụ và kiểm tra độ nhạy (báo cáo kèm, không đổi kết luận H4)

1. **Độ nhạy trên tập giao chung (`common_intersection_glmm`):** cùng GLMM nhưng chỉ chạy trên các câu có kế hoạch can thiệp ở **đủ cả 10 ô**, để loại khả năng lệch do chọn lọc định dạng giữa các tỉ lệ.
2. **Theo từng seed (`per_seed_glmm`):** GLMM riêng cho seed 0 và seed 1.
3. **Tái lập H3 trên câu mới (`paired_checks`):** McNemar chính xác hai phía cho `0% vs 100%` và `25% vs 75%` ở từng seed.
4. **Trả lời phản biện *"self không học gì"* (`descriptive`):** báo cáo `format_valid`, `accuracy` (kèm Wilson 95% CI), `truncated`, `planned`, `follows_rate` và phân bố `taxonomy` cho đủ 10 ô.

## Chia pha chạy an toàn (có thể dừng bất cứ lúc nào)

Chạy từng pha bằng `audit/trace_dose_20261120/run_phase.sh`:
- `prep`: tạo dữ liệu trộn & kiểm tra (<10 giây).
- `train <seed> <ratio>` hoặc `train-seed <seed>`: ~30 phút/adapter (bỏ qua nếu đã có).
- `eval <seed> <ratio>`: ~4,2 giờ/ô, ghi từng câu một nên `Ctrl-C` hoặc đóng máy không mất công.
- `status`: xem tiến độ chính xác của cả 10 ô.
- `analyze`: chạy sau khi cả 10 ô đủ 500/500 và xong can thiệp.
