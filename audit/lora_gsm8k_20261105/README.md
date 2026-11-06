# Huấn luyện LoRA thật đầu tiên trên GSM8K, 2026-11-05

Qwen3-8B 4-bit, LoRA theo `structured_llm/train.sh` không đổi tham số, 2.000 vòng, seed 0, một seed. Đo trên 100 câu
`data/structured_gsm8k_v1/dev.jsonl`, nhiệt độ 0, tối đa 1.024 token. 100 câu này đã được xem ở
`audit/gate1_dev100_20261103/`, nên không phải tập sạch. Adapter nằm ở `adapters/` (bị gitignore, không commit).

| Adapter | Dữ liệu | Thời gian | Val loss vòng 1 → 2.000 |
| --- | --- | --- | --- |
| `adapters/gsm8k_plain_2000_s0` | `structured_gsm8k_v1`, 7.059 dòng, 28% epoch | 3 giờ 21 phút, gồm 19 phút tạm dừng | 2,073 → 0,695 |
| `adapters/gsm8k_cf_2000_s0` | `structured_gsm8k_cf_v1`, 10.178 dòng, 20% epoch | 3 giờ 9 phút | 1,990 → 0,678 |

Val loss gần như phẳng (0,55–0,74) từ khoảng vòng 750 ở cả hai bản.

## Luật đọc, agent đề xuất, ghi trước khi huấn luyện

- Dùng adapter cuối ở vòng 2.000. Không chọn checkpoint trên dev.
- Cổng 0 đọc riêng cho `tuned` và `tuned_cf`, ngưỡng `format_valid` ≥ 90/100 không đổi, kèm khoảng Wilson 95%.
- Ngưỡng 30 vết của RQ2 trong kế hoạch được ghi cho MATH. Dùng cho GSM8K là mượn.

## Kết quả trên 100 câu dev

`comparison.json`, tạo bằng `PYTHONPATH=. .venv/bin/python audit/lora_gsm8k_20261105/compare.py`. Ngoặc là Wilson 95%.
McNemar chính xác hai phía, ghép cặp theo câu với `base_prefill`.

| Chế độ | Đúng | Đúng định dạng | Chỉ chế độ này đúng / chỉ `base_prefill` đúng | Token TB |
| --- | ---: | ---: | --- | ---: |
| `tuned` (thường) | 87 (79,0–92,2) | **86** (77,9–91,5) | 3 / 9, p = 0,146 | 157 |
| `tuned_cf` | 83 (74,5–89,1) | **95** (88,8–97,8) | 2 / 12, p = 0,013 | 150 |
| `base_prefill` | 93 (86,3–96,6) | 61 (51,2–70,0) | | 144 |
| `base_instructed` | 85 (76,7–90,7) | 0 | 1 / 9, p = 0,022 | 498, 14 câu bị cắt |
| `base_showcalc` | 85 (76,7–90,7) | không áp dụng | 2 / 10, p = 0,039 | 139 |

- **Cổng 0: `tuned_cf` đạt (95/100), `tuned` thường không đạt (86/100).** Cận dưới KTC của `tuned_cf` là 88,8%, dưới 90%,
  nên đạt theo số điểm chứ chưa chắc chắn. Giữa hai adapter, định dạng khác nhau có ý nghĩa (10 câu chỉ bản phản thực
  đúng định dạng, 1 câu ngược lại, p = 0,012). Độ đúng thì không (11 câu chỉ bản thường đúng, 7 câu ngược lại, p = 0,48).
- **Lỗi định dạng đều nằm ở dòng `Calc`:** chuỗi bằng nhau (`4*140+35=560+35=595`), đơn vị (`5999+1=6000 yards`),
  phân số (`20/100=1/5`), so sánh (`404>400`).
- **Độ đúng của cả hai adapter thấp hơn `base_prefill`.** Với `tuned_cf`, mức giảm có ý nghĩa ở 100 câu này. Đây là kết quả âm.
- `base_prefill` lặp lại đúng số của lượt cổng 1 (93 đúng, 61 đúng định dạng, 144,2 token), nên phần đo đã chạy ổn định.

## Can thiệp

Chạy cho `tuned_cf` (đã qua cổng 0) và hai chế độ gốc như ở cổng 1. Không chạy cho `tuned` thường vì nó không qua cổng 0.
Sửa một kết quả `Calc` ở giữa, cho mô hình viết tiếp, rồi phân loại bằng `structured_llm.intervene`.

| Chế độ | Đủ điều kiện | Theo | Theo, có làm tròn | Giữ đáp án cũ | Đổi khác | Bị cờ, chỉ thấy đổi |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `tuned_cf` | 71/100 | 54 | 7 | 2 | 5 | 3 |
| `base_prefill` | 53/100 | 45 | 8 | 0 | 0 | 0 |
| `base_showcalc` | 40/100 | 26 | 5 | 3 | 1 | 5 |

- **Đủ ngưỡng 30 vết** (mượn từ luật MATH) ở `tuned_cf` và `base_prefill`. `base_showcalc` có 40 vết, nhưng 5 vết không biết đáp án kỳ vọng.
- **Tỷ lệ không theo** (giữ đáp án cũ hoặc đổi khác, bỏ các vết chỉ thấy đổi): `tuned_cf` 7/68 (10,3%, KTC 5,1–19,8%),
  `base_prefill` 0/53 (0–6,8%). Theo luật mượn (từ 5%, ít nhất 5 ca, ít nhất 30 vết), `tuned_cf` vượt ngưỡng, còn `base_prefill`
  vẫn không có khoảng trống.
- **Ghép cặp trên 49 câu đủ điều kiện ở cả hai chế độ:** 4 câu chỉ `tuned_cf` không theo, 0 câu ngược lại, McNemar p = 0,125. Chưa đủ
  để nói khác `base_prefill`.
- **Đọc tay sau khi xem số, chưa có người rà:** trong 5 ca đổi khác của `tuned_cf`, phần lớn là mô hình nhận số đã sửa rồi viết các bước
  sau khác dự tính, chẳng hạn cộng thêm, đổi dấu (−1 thành 1) hay đọc lại đề. Chỉ 2 ca thật sự quay về đáp án cũ (2/68, 0,8–10,1%).
  Vì vậy con số 10,3% không nên đọc là mô hình bỏ qua phần suy nghĩ.

## Kiểm chứng nhiễu theo checkpoint trên `valid.jsonl`

Người dùng chốt ngày 2026-11-06 (kiểm chứng số 1 trong `error_reading.md`). **Luật ghi trước khi chấm câu nào; agent đề xuất.**

- **Dữ liệu:** `data/structured_gsm8k_v1/valid.jsonl`, 99 câu, trước đây chỉ dùng để tính val loss. **Từ lượt này `valid.jsonl` không còn sạch.**
  Không đọc tập test chính thức của GSM8K.
- **Chế độ:** `tuned` của `gsm8k_plain_2000_s0` và `gsm8k_cf_2000_s0` ở checkpoint 1.000, 1.500 và 2.000, cùng `base_prefill`. Nhiệt độ 0,
  tối đa 1.024 token, `evaluate.py` không đổi.
- **Khoảng cách** của một checkpoint = số câu đúng của nó trừ số câu đúng của `base_prefill` trên cùng 99 câu. Dấu gồm âm, 0 hoặc dương.
- **Đọc riêng cho từng adapter:**
  - Nếu khoảng cách đổi dấu giữa ba checkpoint, hoặc chênh giữa lớn nhất và nhỏ nhất quá 5 câu, thì khoảng cách trên dev **chưa được giải thích
    bằng dữ liệu**, vì nhiễu theo checkpoint đủ lớn để tạo ra nó.
  - Ngược lại, khoảng cách ổn định. Khi đó mới coi mức giảm so với `base_prefill` là thật trên 99 câu này, và đọc tiếp cách giải thích bằng dữ liệu.
- **Báo kèm, không dùng để kết luận:** `format_valid` từng checkpoint, khoảng Wilson 95%, McNemar ghép cặp với `base_prefill`. Cổng 0 vẫn đọc
  trên dev, không đọc lại trên `valid`.

**Kết quả, 2026-11-06** (`valid/comparison_valid.json`, tạo bằng `PYTHONPATH=. .venv/bin/python audit/lora_gsm8k_20261105/compare_valid.py`).
File câu hỏi `data/structured_gsm8k_v1/valid_eval.jsonl` được dựng từ `valid.jsonl` bằng `build_valid_eval.py` (SHA-256 `59905739…13f85`,
không trùng câu nào với dev). Ngoặc là Wilson 95%. McNemar ghép cặp với `base_prefill`.

| Chế độ | Đúng | Đúng định dạng | Khoảng cách | Chỉ adapter đúng / chỉ gốc đúng |
| --- | ---: | ---: | ---: | --- |
| `base_prefill` | 91 (84,9–95,8) | 62 | | |
| thường, vòng 1.000 | 80 (72,0–87,4) | 85 (77,7–91,4) | −11 | 1 / 12, p = 0,003 |
| thường, vòng 1.500 | 79 (70,8–86,5) | 94 (88,7–97,8) | −12 | 1 / 13, p = 0,002 |
| thường, vòng 2.000 | 83 (75,3–89,8) | 89 (82,4–94,4) | −8 | 1 / 9, p = 0,022 |
| phản thực, vòng 1.000 | 82 (74,2–89,0) | 79 (70,8–86,5) | −9 | 1 / 10, p = 0,012 |
| phản thực, vòng 1.500 | 77 (68,6–84,8) | 87 (80,0–92,9) | −14 | 2 / 16, p = 0,001 |
| phản thực, vòng 2.000 | 77 (68,6–84,8) | 84 (76,5–90,6) | −14 | 1 / 15, p < 0,001 |

- **Theo luật: khoảng cách ổn định ở cả hai adapter.** Không đổi dấu. Chênh giữa các checkpoint là 4 câu với bản thường và đúng 5 câu
  với bản phản thực, tức sát ngưỡng. Vậy mức giảm so với `base_prefill` là thật trên 99 câu này, không phải nhiễu của checkpoint.
  Bước tiếp theo là giải thích bằng dữ liệu.
- **Một seed:** luật này chỉ đo nhiễu giữa các checkpoint của cùng một lượt chạy, không đo nhiễu giữa các seed.
- **Báo kèm, không dùng để kết luận:** `tuned_cf` vòng 2.000 chỉ đúng định dạng 84/99 trên `valid`, so với 95/100 trên dev. Bản thường được
  89/99, so với 86/100 trên dev. Cổng 0 vẫn đọc trên dev theo luật, nhưng việc `tuned_cf` qua cổng có vẻ không vững khi đổi tập câu.
- **Tạm dừng:** lượt bản thường vòng 1.000 dừng 12:05–15:55 vì máy rút sạc (pin 38%). Lượt vòng 2.000 dừng hai lần, mỗi lần một phút,
  cũng vì rút sạc. Mã 145 trong `eval_log.txt` là do zsh trả về khi tiến trình bị `SIGSTOP`. `run_valid.sh` đã sửa để chờ đến khi
  tiến trình thật sự kết thúc. Mọi lượt đều đủ 99 dòng.

## Giới hạn

- Một seed, 100 câu, GSM8K dễ. Bản phản thực có nhiều dòng hơn nhưng học cùng số vòng nên thấy ít epoch hơn.
- Bản thường và bản phản thực khác nhau cả về dữ liệu lẫn về số lượt mỗi câu được học, nên chênh lệch định dạng chưa quy được cho phần phản thực.
- `run_eval.sh` kết thúc với mã 145 sau khi `base_showcalc` đã ghi đủ 100 câu và `summary.json`. Có thể do `wait` của zsh gặp tiến trình
  bị `SIGSTOP`. Không có dòng nào thiếu.

## Máy và sweep VRPTW chạy song song

Người dùng chọn chạy song song với `vrptw-neural-hybrid-optimizer/results/ges_sweep_20261102`. Trainer và các lượt đo tự tạm dừng
khi pin ≤ 6% hoặc rút sạc (`*_load.txt` ghi từng phút):

- Huấn luyện bản thường tạm dừng 22:32–22:51 vì mất nguồn sạc. Lượt đo gốc tạm dừng hai lần, 04:50–04:54 và 05:30–05:34, vì pin 6%.
- Từ 21:07 ngày 5/11 đến 07:09 ngày 6/11, sweep ghi 4 lần giữ ca mới (tải 9,2–11,5). Để chạy lại, sweep cần pin trên 8%, mà pin
  đứng ở 7–8% suốt đêm, nên không có ca nào xong trong khoảng 22:00–00:00, và từ 00:00 chỉ còn 44–57 ca mỗi giờ so với khoảng 224 ca
  thường lệ.

## Chạy thử 40 vòng (`probe/`)

Trước khi chạy dài: 34–36 token/giây, 218 token/vòng, khoảng 6,3 giây/vòng, bộ nhớ đỉnh 5,8 GB. Kế hoạch ước tính 15 token/giây và
khoảng 8 giờ cho 2.000 vòng. Lượt thật mất khoảng 3 giờ 10 phút mỗi bản.

## File

- `run_training.sh`, `train_*.log`, `train_*_load.txt`: lệnh, mã băm dữ liệu, log huấn luyện, pin và tải.
- `run_eval.sh`, `eval_plain/`, `eval_cf/`, `eval_base/`: đầu ra thô `.jsonl`, `summary.json`, `manifest.json` (có mã băm adapter).
- `run_intervene.sh`, `eval_cf/tuned_interventions.jsonl`, `eval_base/*_interventions.jsonl`, `interventions_summary.json`.
- `compare.py`, `comparison.json`: bảng so sánh.
