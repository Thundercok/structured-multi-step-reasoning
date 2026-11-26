# Kết quả thí nghiệm H4: Liều lượng vết người (`trace_dose_20261120`)

**Ngày hoàn tất đo & phân tích:** 2026-11-25 (`audit/trace_dose_20261120/results.json`)
**Tiền đăng ký:** `docs/trace_dose_prereg.md` (commit `c437df01`) và bản sửa đổi có hiệu lực `docs/trace_dose_prereg_amendment_20261123.md` (commit `d4dbcd80`, ban hành trước khi chạy `analyze`).
**Tập đo:** 500 câu đầu của `data/gsm_plus_v1/holdout_819.jsonl` (0 câu giao với 500 câu H3).
**Dữ liệu huấn luyện:** 5 tập lồng nhau 229 câu (`0 / 25 / 50 / 75 / 100%` vết người = `0 / 57 / 114 / 172 / 229` dòng; `check.json`: 0 lỗi, 0 sai định dạng, 0 dòng > 512 token, độ dài trung bình 209,4–210,2 token).

---

## 1. Kết luận theo đúng quy tắc đọc tiền đăng ký

1. **H4 (phép kiểm chính cấp adapter, chỉ số B1) — ĐẠT:**
   - Hồi quy OLS trên 10 ô (5 tỉ lệ × 2 seed), $y_c = \text{logit}\big((f_c + 0{,}5)/(n_c + 1)\big)$ trên các quan sát có kế hoạch và `expected != None`:
     $$\hat b_{\text{human}} = -0{,}6489 \quad (\text{SE} = 0{,}1206), \quad t(7) = -5{,}380, \quad p = 0{,}00103 < 0{,}05$$
     ($\hat b_{\text{seed}} = -0{,}0846$).
   - **Kết luận chính:** Tỉ lệ vết người trong tập huấn luyện càng cao thì mức bám bước bị can thiệp (`follows`) càng giảm.

2. **Quy tắc giữ từ *"monotonically"* — KHÔNG GIỮ (lùi từ ngữ theo đúng luật):**
   - Trung bình logit B1 của 2 seed ở 5 mức là:
     `0%`: **2,120** (89,4%) → `25%`: **1,795** (85,9%) → `50%`: **1,571** (82,9%) → `75%`: **1,639** (83,8%) → `100%`: **1,386** (80,1%).
   - Vì mức `75%` nhích nhẹ lên trên mức `50%` trên chỉ số chính B1 (chủ yếu ở Seed 0: 1,614 → 1,742; Seed 1 gần phẳng: 1,528 → 1,536), bảng 5 mức **không giảm chặt qua mọi mức trung gian**.
   - **Áp dụng luật đọc:** Bỏ chữ *"monotonically"* trong luận điểm. Phát biểu chuẩn xác theo dữ liệu: **xói mòn theo liều lượng (*dose-dependent erosion*)**, giảm rõ từ 0% đến 50%, có đoạn phẳng ở 50%–75% trên B1, và giảm tiếp xuống đáy ở 100%. (Lưu ý mô tả: trên chỉ số gốc gồm cả `expected = None`, trung bình 5 mức giảm đều chặt từ 1,830 xuống 1,115, Spearman $\rho = -1{,}0$.)

---

## 2. Kiểm tra độ nhạy & phân tích phụ (cấp adapter)

| Phân tích (OLS 10 ô, df = 7) | $\hat b_{\text{human}}$ | SE | $t(7)$ | $p$ | Trung bình logit 5 mức (0 / 25 / 50 / 75 / 100%) |
|---|---:|---:|---:|---:|---|
| **Chính: B1 (`expected != None`)** | **−0,6489** | 0,1206 | −5,380 | **0,00103** | 2,120 / 1,795 / 1,571 / 1,639 / 1,386 |
| Độ nhạy: Tập giao cả 10 ô ($n = 59$ câu/ô, B1) | −0,6774 | 0,1559 | −4,344 | 0,00338 | 2,201 / 1,736 / 1,551 / 1,555 / 1,443 |
| Phụ: Chỉ số gốc (mọi câu có kế hoạch) | −0,6591 | 0,1157 | −5,695 | 0,00074 | 1,830 / 1,591 / 1,386 / 1,371 / 1,115 |

Kết quả trên tập giao 59 câu đủ điều kiện ở đủ cả 10 ô giữ nguyên độ dốc ($\hat b_{\text{human}} = -0{,}6774$, $p = 0{,}0034$), loại trừ khả năng xu hướng chỉ là ảo giác do khác biệt thành phần câu giữa các ô.

---

## 3. Tái lập H3 trên 500 câu mới (McNemar theo cặp adapter)

*(Lưu ý: mỗi dòng dưới đây so sánh đúng hai adapter cụ thể đó trên các câu cả hai cùng đủ điều kiện.)*

| Cặp so sánh | $n$ chung | Tỉ lệ `follows` (A vs B) | Bất đồng (chỉ A / chỉ B) | Chênh lệch (95% CI) | McNemar $p$ |
|---|---:|---|---:|---|---:|
| Seed 0: `0%` vs `100%` | 147 | 130 (88,4%) vs 109 (74,1%) | 23 / 2 | +14,3 đ% [8,0; 20,5] | $1{,}94 \times 10^{-5}$ |
| Seed 1: `0%` vs `100%` | 152 | 137 (90,1%) vs 119 (78,3%) | 20 / 2 | +11,8 đ% [6,1; 17,6] | $1{,}21 \times 10^{-4}$ |
| Seed 0: `25%` vs `75%` | 157 | 141 (89,8%) vs 133 (84,7%) | 11 / 3 | +5,1 đ% [0,5; 9,7] | 0,0574 |
| Seed 1: `25%` vs `75%` | 170 | 142 (83,5%) vs 134 (78,8%) | 16 / 8 | +4,7 đ% [−0,9; 10,3] | 0,1516 |

Hai cặp trung gian `25% vs 75%` đi cùng chiều (+5,1 đ% và +4,7 đ%) ở cả hai seed, nhưng chưa đạt $p < 0{,}05$ riêng lẻ ở cỡ mẫu ~160 cặp.

---

## 4. Bảng mô tả đủ 10 ô (trả lời phản biện *"self không học gì"*)

| Ô | `format_valid` (/500) | `accuracy` (/500, Wilson 95% CI) | `truncated` | `planned` | `flagged` (`expected=None`) | `follows` B1 | `follows` gốc |
|---|---:|---|---:|---:|---:|---:|---:|
| `s0_r0` | 323 (64,6%) | 411 (82,2% [78,6–85,3]) | 10 | 245 | 10 (4,1%) | 209/235 (88,9%) | 209/245 (85,3%) |
| `s0_r25` | 327 (65,4%) | 408 (81,6% [78,0–84,8]) | 6 | 246 | 8 (3,3%) | 208/238 (87,4%) | 208/246 (84,6%) |
| `s0_r50` | 337 (67,4%) | 398 (79,6% [75,8–82,9]) | 4 | 253 | 10 (4,0%) | 203/243 (83,5%) | 203/253 (80,2%) |
| `s0_r75` | 327 (65,4%) | 388 (77,6% [73,7–81,0]) | 9 | 224 | 7 (3,1%) | 185/217 (85,3%) | 185/224 (82,6%) |
| `s0_r100` | 314 (62,8%) | 367 (73,4% [69,4–77,1]) | 35 | 209 | 14 (6,7%) | 156/195 (80,0%) | 156/209 (74,6%) |
| `s1_r0` | 341 (68,2%) | 403 (80,6% [76,9–83,8]) | 9 | 236 | 7 (3,0%) | 206/229 (90,0%) | 206/236 (87,3%) |
| `s1_r25` | 306 (61,2%) | 405 (81,0% [77,3–84,2]) | 11 | 236 | 7 (3,0%) | 193/229 (84,3%) | 193/236 (81,8%) |
| `s1_r50` | 318 (63,6%) | 397 (79,4% [75,6–82,7]) | 6 | 250 | 7 (2,8%) | 200/243 (82,3%) | 200/250 (80,0%) |
| `s1_r75` | 319 (63,8%) | 380 (76,0% [72,1–79,5]) | 14 | 238 | 16 (6,7%) | 183/222 (82,4%) | 183/238 (76,9%) |
| `s1_r100` | 320 (64,0%) | 353 (70,6% [66,5–74,4]) | 50 | 235 | 12 (5,1%) | 179/223 (80,3%) | 179/235 (76,2%) |

### Phân loại kết quả can thiệp (`taxonomy`)

| Ô | `follows` | `follows_rounded` | `follows_approx` | `reverted` | `other` | `moved` | `no_answer` |
|---|---:|---:|---:|---:|---:|---:|---:|
| `s0_r0` | 209 | 12 | 0 | 7 | 7 | 9 | 1 |
| `s0_r25` | 208 | 12 | 1 | 9 | 9 | 6 | 1 |
| `s0_r50` | 203 | 12 | 1 | 16 | 12 | 5 | 4 |
| `s0_r75` | 185 | 8 | 2 | 8 | 17 | 3 | 1 |
| `s0_r100` | 156 | 12 | 1 | 11 | 16 | 9 | 4 |
| `s1_r0` | 206 | 11 | 1 | 7 | 4 | 7 | 0 |
| `s1_r25` | 193 | 11 | 1 | 13 | 10 | 6 | 2 |
| `s1_r50` | 200 | 11 | 0 | 13 | 19 | 5 | 2 |
| `s1_r75` | 183 | 10 | 1 | 11 | 17 | 13 | 3 |
| `s1_r100` | 179 | 10 | 1 | 8 | 21 | 8 | 8 |

**Điểm đáng chú ý:**
- **Phản bác *"self không học gì"*:** `0%` (`self`) đạt `format_valid` ngang hoặc cao hơn `100%` (`human`) (323–341 vs 314–320), đồng thời đạt `accuracy` cao hơn hẳn (~81,4% vs ~72,0%) và ít bị cắt cụt hơn nhiều (9–10 vs 35–50 ca `truncated`).
- **Phân rã lỗi khi tăng tỉ lệ vết người:** Phần giảm của `follows` chủ yếu chuyển sang `other` (tăng từ 4–7 ở `0%` lên 16–21 ở `100%`), `reverted` (tăng ở các mức giữa 25%–50%), và `no_answer` (tăng lên 4–8 ở `100%`). `follows_rounded` giữ ổn định (8–12 ca/ô), xác nhận hiệu ứng không phải do làm tròn.

---

## 5. Phân tích GLMM mô tả (chỉ tham khảo, không dùng để kết luận)

> **Cảnh báo theo sửa đổi 2026-11-23:** GLMM có random intercept theo câu hỏi coi các quan sát trong cùng một adapter là độc lập (không có random effect theo adapter), nên $p$-value dưới đây có thể quá nhỏ khi tồn tại phương sai giữa các lần huấn luyện ($\tau > 0$). Chỉ báo cáo để đối chiếu với bản tiền đăng ký gốc.

- **B1 GLMM (`n_obs = 2274`, 367 câu):** $\hat\beta_{\text{human}} = -1{,}690$, LRT(1) = 36,04 ($p = 1{,}93 \times 10^{-9}$); Seed 0: $\hat\beta = -2{,}307$ ($p = 9{,}98 \times 10^{-7}$); Seed 1: $\hat\beta = -1{,}519$ ($p = 1{,}22 \times 10^{-4}$); tập giao 59 câu: $\hat\beta = -2{,}556$ ($p = 1{,}14 \times 10^{-4}$); kiểm tra phi tuyến 3 df: LRT = 7,87 ($p = 0{,}0489$).
- **Chỉ số gốc GLMM (`n_obs = 2372`, 396 câu):** $\hat\beta_{\text{human}} = -1{,}762$, LRT(1) = 50,56 ($p = 1{,}15 \times 10^{-12}$); kiểm tra phi tuyến 3 df: LRT = 4,56 ($p = 0{,}207$).

---

## 6. Hạn chế cần ghi rõ trong bài báo

1. **Không độc lập về adapter ở hai đầu:** Các adapter `0%` và `100%` là chính các adapter của H3 (độc lập về tập câu đo, không độc lập về trọng số). Độ dốc liều lượng chịu ảnh hưởng lớn bởi hai đầu này.
2. **Lọc theo đặc tính của adapter:** Cả điều kiện có kế hoạch can thiệp (`planned`, ~42–51% số câu) lẫn chỉ số B1 (`expected != None`, bỏ 2,8–6,7% số câu có kế hoạch) đều phụ thuộc vào đầu ra của chính adapter. Tập giao 59 câu chung giúp kiểm soát phần nào nhưng chỉ chiếm 11,8% tổng số câu.
3. **Phạm vi dữ liệu và mô hình:** Một mô hình gốc (`Qwen3-8B-4bit` trên MLX), 2 seed, 229 câu huấn luyện, đánh giá trên GSM-Plus (`numerical substitution`). Không suy rộng sang mô hình/miền khác hoặc khẳng định đường cong là đơn điệu chặt.
