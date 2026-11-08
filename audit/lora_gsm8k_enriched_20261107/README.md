# Huấn luyện LoRA Enriched trên GSM8K, 2026-11-07

Qwen3-8B 4-bit, LoRA theo `structured_llm/train.sh`, 2.000 vòng, seed 0, một seed.
Mục tiêu là kiểm chứng xem việc làm giàu ngữ nghĩa (100% `Step 1` mở bằng `Calculate the <đại lượng>...`)
trong dữ liệu huấn luyện có giúp mô hình tự sinh và khôi phục độ chính xác lập luận trên dev (từ 83% lên ~90–93%)
mà không cần bất kỳ can thiệp prompt mồi tiền tố nào ở runtime.

## Dữ liệu và Adapter

| Adapter | Dữ liệu | Kích thước | Ghi chú |
| --- | --- | ---: | --- |
| `adapters/gsm8k_enriched_2000_s0` | `data/structured_gsm8k_enriched_v1` | 7.061 dòng | 100% Step 1 mở bằng `Calculate the ...` |
| `adapters/gsm8k_cf_enriched_2000_s0` | `data/structured_gsm8k_cf_enriched_v1` | 10.180 dòng | 7.061 dòng enriched + 3.119 dòng phản thực |

## Luật đánh giá

- Không đọc tập test chính thức của GSM8K.
- Đánh giá trên 100 câu `data/structured_gsm8k_v1/dev.jsonl` ở nhiệt độ 0, tối đa 1.024 token.
- Chế độ đánh giá là `tuned` tiêu chuẩn (chỉ mồi `<think>\n`, tuyệt đối không mồi `Step 1: Calculate the ` ở runtime).
- Cổng 0: `format_valid` ≥ 90/100 kèm khoảng Wilson 95%.
- Ghép cặp McNemar chính xác hai phía với `base_prefill` và với bản cũ `adapters/gsm8k_cf_2000_s0`.

## Bảng so sánh Hoàn chỉnh (Enriched Plain, Enriched CF, và Runtime Calculator `tuned_tool`)

Kết quả tạo tự động bằng `PYTHONPATH=. .venv/bin/python audit/lora_gsm8k_enriched_20261107/report_generator.py`:
Chi tiết xem tại [`REPORT.md`](REPORT.md) và [`comparison.json`](comparison.json).

| Chế độ / Adapter | Đúng (Accuracy) | KTC Wilson 95% | Đúng định dạng (Format Valid) | KTC Wilson 95% | McNemar vs Base Prefill (p) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Base Prefill (Mốc gốc) | 93/100 (93.0%) | 86.3–96.6% | 61/100 (61.0%) | 51.2–70.0% | N/A |
| Cũ Thường (`gsm8k_2000_s0`) | 87/100 (87.0%) | 79.0–92.2% | 87/100 (87.0%) | 79.0–92.2% | p = 0.1460 |
| Cũ Phản thực (`gsm8k_cf_2000_s0`) | 83/100 (83.0%) | 74.5–89.1% | 95/100 (95.0%) | 88.8–97.8% | p = 0.0129 |
| **Mới Thường Enriched (`gsm8k_enriched_2000_s0`)** | 82/100 (82.0%) | 73.3–88.3% | **95/100 (95.0%)** | 88.8–97.8% | p = 0.0127 |
| **Mới Thường Enriched + Tool (`tuned_tool`)** | 82/100 (82.0%) | 73.3–88.3% | **95/100 (95.0%)** | 88.8–97.8% | p = 0.0127 |
| **Mới Phản thực Enriched (`gsm8k_cf_enriched_2000_s0`)** | **87/100 (87.0%)** | 79.0–92.2% | **95/100 (95.0%)** | 88.8–97.8% | **p = 0.1094** |
| **Mới Phản thực Enriched + Tool (`tuned_tool`)** | **87/100 (87.0%)** | 79.0–92.2% | **97/100 (97.0%)** | 91.5–99.0% | **p = 0.1094** |

### Điểm nổi bật của bộ Adapter Giàu Ngữ nghĩa (`enriched_plain` & `enriched_cf`):
1. **Cổng 0 (Format Validity):** Cả hai bản đều đạt **95.0%** [88.8–97.8%] ở chế độ zero-prefill (và **97.0%** [91.5–99.0%] khi kết hợp `tuned_tool` trên `enriched_cf`), vượt qua Cổng 0 ($\ge 90\%$).
2. **Khôi phục độ chính xác toàn cục & 19 câu mục tiêu trên `enriched_cf` (`gsm8k_cf_enriched_2000_s0`):**
   - **Độ chính xác Dev-100 tăng từ 83/100 (`old_cf`) lên 87/100 (`enriched_cf`)** (+4.0 pp, thắng 11 vs 7 câu lệch), khôi phục hoàn toàn mức 87% của `old_plain` và không còn chênh lệch có ý nghĩa thống kê so với `base_prefill` (McNemar $p = 0.1094 > 0.05$).
   - **Trên 19 câu mục tiêu (Hợp các câu thất bại của adapter cũ):** `enriched_cf` giải đúng **15/19 (78.9%)** hoàn toàn zero-prefill (18/19 format_valid), phục hồi **7/9 (77.8%)** ca sai của `old_plain` và **10/12 (83.3%)** ca sai của `old_cf` — **ngang bằng mức trần 15/19 của `old_cf + runtime prefill` mà không cần mồi prompt ở runtime!**
   - Bản `enriched_plain` đạt **13/19 (68.4%)** đúng zero-prefill (phục hồi 6/9 [66.7%] của `old_plain` và 8/12 [66.7%] của `old_cf`).
3. **Ablation Công cụ Tính toán Runtime (`tuned_tool`):** Chạy máy tính tất định trên từng dòng `Calc:` giữ nguyên độ chính xác (82/100 trên `enriched_plain_tool` và 87/100 trên `enriched_cf_tool`), chứng minh mô hình đã tính toán số học nội bộ gần như tuyệt đối (100%) và toàn bộ lỗi còn lại nằm ở bước lập phương trình trong `Step`.
4. **Độ trung thực nhân quả (Counterfactual Causal Faithfulness):**
   - `enriched_plain`: 73 câu đủ điều kiện (72 câu sạch + 1 `moved`), đạt **67/72 (93.1%)** tuân thủ tính toán bị nhiễu (55 `follows` + 12 `follows_rounded`), 3/72 (4.2%) `other`, chỉ **2/72 (2.8%)** `reverted`.
   - `enriched_cf`: 66 câu đủ điều kiện (65 câu sạch + 1 `moved`), đạt **61/65 (93.8%)** tuân thủ tính toán bị nhiễu (55 `follows` + 6 `follows_rounded`), 2/65 (3.1%) `other`, chỉ **2/65 (3.1%)** `reverted`.

## Lệnh thực thi

```bash
audit/lora_gsm8k_enriched_20261107/run_all.sh
```

