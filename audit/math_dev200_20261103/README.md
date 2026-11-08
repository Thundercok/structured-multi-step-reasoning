# Đo lại trên 200 câu MATH mới, 2026-11-03 đến 04

Câu 101 đến 300 của dev MATH, Qwen3-8B-4bit chưa tinh chỉnh, `--max-tokens 2048`. Luật đọc ghi trong `docs/research_plan.md`
trước khi chạy. Mã băm của bộ chấm và script khớp `frozen_sha256.txt`. Đầu ra thô và `pal_full.json` không đưa lên git.

## Kết quả chính

| Chế độ | Đúng | KTC 95% | Token TB | Bị cắt |
| --- | ---: | --- | ---: | ---: |
| `base_showcalc` | 118/200 | 52,1–65,6% | 665 | 20 |
| `base_pal`, bộ thông dịch mở rộng | 112/200 | | 412 | 12 |

Trong 200 chương trình PAL, 44 không ra số.

| Tín hiệu trên `base_showcalc` | Bắt câu sai | KTC 95% | Báo nhầm | KTC 95% | Theo luật |
| --- | ---: | --- | ---: | --- | --- |
| A. Có đẳng thức LaTeX sai | 2/82 (2,4%) | 0,7–8,5% | 0/118 | 0–3,2% | **Không đạt** |
| B. Khác đáp án PAL | 48/82 (58,5%) | 47,7–68,6% | 20/118 (16,9%) | 11,2–24,7% | **Đạt** |

Có 82 câu sai, đủ mức 50 câu. **Theo luật, cổng 4 chưa đạt theo nghĩa kiểm phần suy nghĩ.**

## Tín hiệu B không vững bằng con số chính

Các dòng dưới không được chốt trước, chỉ dùng để hiểu kết quả. Số nằm trong `secondary.json`.

| Lát cắt | Bắt câu sai | Báo nhầm |
| --- | ---: | ---: |
| Đáp án số | 24/47 (51,1%) | 8/80 (10,0%) |
| Đáp án ký hiệu | 24/35 (68,6%) | 12/38 (31,6%) |
| Bỏ câu bị cắt | 40/62 (64,5%) | 20/118 (16,9%) |
| Tính 8 ca đọc tay là đúng | 41/74 (55,4%) | **27/126 (21,4%)** |
| Báo cả khi PAL không ra số | 78/82 (95,1%) | 34/118 (28,8%) |

- **8 ca đọc tay:** bộ chấm đã khóa bỏ sót 3 ca (`72` với `72°`, `105` với `105°`, `3.175` với `11√3/6`), và 5 ca do lời nhắc đòi đáp
  án số (`2304` với `2304π`, `910` với `9/10`). Nếu tính các ca này là đúng, báo nhầm vượt ngưỡng 20%. Bộ chấm không sửa
  theo luật đã ghi.
- **Khi PAL ra số và trùng đáp án:** 84/88 câu đúng (95,5%, KTC 88,9–98,2%), so với 59% trên toàn bộ. Các câu này chiếm 44% số câu.
  Đây là cách đọc nghĩ ra sau khi xem số.
- **Giới hạn của PAL với đáp án ký hiệu:** lời nhắc chỉ cho ra số, nên `6z`, `10x` hay `a` không thể trùng. Đây là một phần
  của 12/38 báo nhầm.
- **Chi phí:** tổng 1.077 token mỗi câu so với 665, tức khoảng 1,6 lần.

## Giới hạn

Agent đọc 20 ca báo nhầm, 4 ca cùng sai và danh sách câu sai không bị cắt, nhưng chỉ đọc cặp đáp án, không đọc cả lời giải;
chưa có người rà. Đây là mô hình chưa tinh chỉnh, và chỉ có một cỡ mô hình.
