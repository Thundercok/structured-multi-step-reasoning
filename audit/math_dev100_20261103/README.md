# 100 câu đầu của dev MATH, 2026-11-03

Qwen3-8B-4bit chưa tinh chỉnh, trên tập con kiểm được của MATH mức 3 đến 5, `--max-tokens 2048`.
Đầu ra thô `*.jsonl` không đưa lên git vì chứa đề MATH. `summary.json` và `eval_log.txt` dùng bộ chấm cũ, đừng đọc số từ đó.

## Độ chính xác

Lệnh: `python -m structured_llm.analyze audit/math_dev100_20261103 --baseline base_prefill`, riêng PAL lấy từ `pal_full.py`.

| Chế độ | Đúng | KTC 95% | Token TB | Bị cắt |
| --- | ---: | --- | ---: | ---: |
| `base_prefill` | 63 | 53,2–71,8% | 567 | 10 |
| `base_showcalc` | 64 | 54,2–72,7% | 787 | 10 |
| `base_pal`, bộ thông dịch cũ | 32 | 23,7–41,7% | 461 | 6 |
| `base_pal`, bộ thông dịch mở rộng | 55 | | 461 | 6 |

`base_showcalc` so với `base_prefill`: 15 câu chỉ bên này đúng, 14 câu chỉ bên kia đúng, McNemar p = 1,0.

**Cổng 3b đạt.** PAL có 27 chương trình không ra số: 7 lỗi cú pháp, 4 `TypeError`, 2 vượt giới hạn phép tính, 2 dùng
numpy, 2 chia cho 0, còn lại mỗi loại 1 đến 2 ca. Nếu cả 27 đều đúng thì PAL đạt 82/100, vẫn dưới ngưỡng 84.

Bộ thông dịch mở rộng được thêm sau khi thấy kết quả, vì bộ cũ từ chối `while`, `def` và `set`. Chấm lại từ đầu ra đã
lưu, không chạy lại mô hình. Mốc GSM8K vẫn dùng bộ cũ.

## Nhiễu đo do lời nhắc

- Lời nhắc đòi đáp án là số, nên `base_showcalc` viết `27π` trong bài rồi chốt `Answer: 27`, tương tự với `193π` và `108π`.
  Một ca khác viết `\frac{1003}{502}` rồi chốt `1003502`. Các ca này bị chấm sai đúng theo những gì mô hình đã chốt.
- PAL dùng π xấp xỉ nên `27π`, `108π`, `193π` bị chấm sai. Nếu tính cả 3 ca này, PAL được 58/100.
- 33/100 câu có đáp án không phải số nguyên hay số thập phân.

## Can thiệp

Chạy `plan_for` với `freeform=True`, chưa sinh đầu ra nào.

| Lý do | `base_prefill` | `base_showcalc` |
| --- | ---: | ---: |
| **Đủ điều kiện** | **3** | **7** |
| Đáp án không phải số | 33 | 33 |
| Quá ít phép tính đọc được | 26 | 16 |
| Không có phép tính đọc được | 17 | 24 |
| Kết quả không được dùng về sau | 15 | 16 |
| Khác | 6 | 4 |

Theo ngưỡng đã chốt trong `docs/research_plan.md`, dưới 30 vết là **chưa đo được**. Bộ lập can thiệp giả định lời giải là
một chuỗi phép tính số, còn lời giải MATH thường biến đổi ký hiệu.

## Tín hiệu phát hiện sai

Lệnh: `python audit/math_dev100_20261103/checker_signal.py`. Số nằm trong `checker_signal.json`.

| Tín hiệu | Chế độ | Bắt câu sai | Báo nhầm câu đúng |
| --- | --- | ---: | ---: |
| Đẳng thức LaTeX sai | `base_prefill` | 2/37 | 0/63 |
| Đẳng thức LaTeX sai | `base_showcalc` | 0/36 | 0/64 |
| Khác đáp án PAL | `base_prefill` | 21/37 | 10/63 |
| Khác đáp án PAL | `base_showcalc` | 23/36 | 6/64 |

- Chương trình PAL không ra số được tính là không báo. Nếu chỉ xét 73 câu PAL ra số, `base_showcalc` là 23/23 và 6/50.
- `format_valid` của `base_prefill` chỉ 5/100, nên số `caught_wrong` trong `analyze` (36/37, báo nhầm 63/63) gần như
  chỉ phản ánh lỗi định dạng. Đừng dùng số đó.
- Bộ kiểm hiện chỉ đọc đẳng thức trong LaTeX. Một bộ đọc văn bản thuần đã thử và bỏ, vì đọc tay thấy hầu hết kết quả là
  đọc nhầm, ví dụ `1 - 1/8 = 7/8`. Do đó 2/37 và 0/36 là cận dưới của một bộ kiểm phép tính tốt hơn.
- Dòng PAL được nghĩ ra sau khi xem dữ liệu, trên chính 100 câu này. Ba ca `27π`, `193π`, `108π` trong số bị bắt là nhiễu do
  lời nhắc. Cần đo lại trên câu mới.

## Giới hạn

Agent đọc các câu sai của `base_showcalc`, các ca PAL báo nhầm và các phép tính bị bộ đọc văn bản thuần gắn cờ; chưa có
người rà. Mẫu 100 câu nên khoảng tin cậy rộng. Mô hình chưa tinh chỉnh, nên chưa nói được gì về `tuned`.
