# Độ phủ SymPy trên MATH, 2026-11-03

Đo trên lời giải mẫu của phần train MATH, không gọi mô hình. Phần test không được đọc.
Cổng 3a yêu cầu 50% trên 5.586 bài mức 3 đến 5, ngưỡng ghi trước khi đo. **Không đạt.**

| Số đo | Kết quả | File |
| --- | ---: | --- |
| Bộ đọc lần đầu | 21,8% | `coverage_first_reader.json` |
| Bộ đọc đã sửa lỗi, kết quả chính thức | 23,3% (1.301 bài) | `coverage.json` |
| Thêm cách thế đáp án số vào phương trình một ẩn | 24,2% | `math_bound_output.txt` |
| Bộ đọc hoàn hảo: đẳng thức chưa đọc được coi là đúng, đẳng thức có ẩn không tính | 42,4% | `math_bound2_output.txt` |
| Coi mọi đẳng thức không tầm thường đều kiểm được, kể cả có ẩn | 59,6% | `math_bound_output.txt` |

41,9% số bài có ít nhất một đẳng thức có ẩn, dạng `2x+3=7`.

Theo định nghĩa hiện tại, sửa bộ đọc khó đưa kết quả lên 50%: giới hạn nằm nhiều ở lời giải MATH. Các cận trên
là ước lượng, không phải cận chặt: đáp án so theo chuỗi nên có thể hụt ca viết khác dạng, còn coi mọi đẳng thức
chưa đọc được là đúng thì có thể dư.

`math_bound.py` và `math_bound2.py` do một phiên làm việc khác viết, đã đọc và chạy lại trên `math_check.py` hiện tại.
Đây là phân tích sau khi thấy kết quả, không làm thay đổi kết luận của cổng.

## Độ lệch của tập con 1.301 bài (đếm thật)

| Nhóm | Toàn bộ mức 3 đến 5 | Tập con |
| --- | ---: | ---: |
| algebra | 1.226 (21,9%) | 286 (22,0%) |
| counting_and_probability | 602 (10,8%) | 205 (15,8%) |
| geometry | 727 (13,0%) | 206 (15,8%) |
| intermediate_algebra | 1.070 (19,2%) | 175 (13,5%) |
| number_theory | 691 (12,4%) | 135 (10,4%) |
| prealgebra | 750 (13,4%) | 231 (17,8%) |
| precalculus | 520 (9,3%) | 63 (4,8%) |
| Level 3 | 1.592 (28,5%) | 341 (26,2%) |
| Level 4 | 1.690 (30,3%) | 380 (29,2%) |
| Level 5 | 2.304 (41,2%) | 580 (44,6%) |

Tập con có ít precalculus và intermediate algebra hơn, nhiều counting và prealgebra hơn. Phải ghi trong phần giới hạn của bài.
