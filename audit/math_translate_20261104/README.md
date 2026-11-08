# Chương trình dịch so với PAL độc lập, 2026-11-04

Trên 200 lời giải `base_showcalc` của lượt `math_dev200_20261103`, mô hình dịch từng lời giải đã bỏ dòng `Answer:` cuối sang
Python, không sinh lại lời giải. Luật đọc ghi trong `docs/research_plan.md` trước khi chạy. Mã băm khớp `frozen_sha256.txt`.
Lời nhắc chỉ thử trên 4 câu của lượt 100 câu đầu. Đầu ra thô và `rows.json` không đưa lên git.

## Kết quả chính

| Tín hiệu khác đáp án | Bắt câu sai | KTC 95% | Báo nhầm | KTC 95% | Token TB |
| --- | ---: | --- | ---: | --- | ---: |
| PAL độc lập | 48/82 (58,5%) | 47,7–68,6% | 20/118 (16,9%) | 11,2–24,7% | 412 |
| Chương trình dịch | 47/82 (57,3%) | 46,5–67,5% | 5/118 (4,2%) | 1,8–9,5% | 177 |

Chỉ PAL bắt 14 câu, chỉ bên dịch bắt 13 câu, McNemar p = 1,0. **Theo luật, giả thuyết không đạt và phải bỏ luận điểm.** Trong
200 chương trình dịch có 17 không ra số, 4 chỉ gán hằng số, 2 bị cắt. PAL có 44 không ra số.

## Lát cắt báo kèm, không dùng để kết luận

| Lát cắt | PAL bắt | Dịch bắt | Chỉ PAL / chỉ dịch | p | PAL báo nhầm | Dịch báo nhầm |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Cả hai ra số | 46/50 | 35/50 | 12 / 1 | 0,0034 | 18/100 | 5/100 |
| Bỏ lời giải bị cắt | 40/62 | 34/62 | 14 / 8 | 0,29 | 20/118 | 5/118 |
| Tính 8 ca đọc tay là đúng | 41/74 | 43/74 | 11 / 13 | 0,84 | 27/126 | 9/126 |

Lát cắt "cả hai ra số" ủng hộ giả thuyết còn số chính thì không. Nguyên nhân chính là PAL không ra số nhiều hơn. Lát cắt này loại
các câu theo kết quả chạy của chính hai chương trình, nên không so công bằng.

## Đọc tay sau khi xem số, chưa phải kết quả

Agent chỉ đọc đoạn cuối lời giải và chương trình, biết trước cờ của từng câu, nên nhãn không mù. Chưa có người rà. Nhãn và số
nằm trong `secondary.py`, `secondary.json`.

**34 câu sai, không bị cắt, chương trình dịch báo:**

| Loại | Số câu | Ví dụ |
| --- | ---: | --- |
| Lời giải chỉ nêu kế hoạch, không tính, đáp án không có căn cứ | 12 | "cộng hai kết quả lại", `Answer: 126`; chương trình ra 147 |
| Dòng `Answer:` hỏng do lời nhắc đòi số | 9 | `3/10` thành `310`, `47/128` thành `47` |
| Bước tính hoặc liệt kê tay sai, chương trình làm lại đúng | 7 | `1300 - 422500 = -4223700` |
| Có báo nhưng vì lý do khác | 6 | làm tròn `14.214` so với `14.2126`, chương trình cũng sai |

Như vậy 21/34 lần bắt phụ thuộc cách viết lời nhắc: thinking tắt và đáp án buộc là số. Với lời nhắc tốt hơn, bên dịch có thể bắt
ít đi nhiều.

**12 câu sai chỉ PAL bắt, chương trình dịch ra số và trùng đáp án sai:**

| Loại | Số câu |
| --- | ---: |
| Lập luận sai, chương trình dịch chép lại đúng lập luận đó | 10 |
| Nhiễu của bộ chấm hoặc lời nhắc | 2 |

Ví dụ: lời giải dùng sai công thức rồi ra `100/2 = 50`, chương trình dịch viết `magnitude_squared / 2`. Đáp án đúng là 100.

**Cách đọc gợi ra, chưa được kiểm định:** hai loại chương trình có thể bắt hai loại lỗi khác nhau. Chương trình dịch bắt lỗi thực
thi và chép lại lỗi lập luận; chương trình độc lập bắt được một phần lỗi lập luận nhưng báo nhầm nhiều hơn.

## Số khác nghĩ ra sau khi xem kết quả

- **Báo khi một trong hai khác đáp án:** bắt 61/82 (74,4%, KTC 64,0–82,6%), báo nhầm 20/118, tổng khoảng 1.254 token. Cả 5 báo nhầm
  của bên dịch đều nằm trong 20 báo nhầm của PAL.
- **Dùng giá trị chương trình dịch làm đáp án:** đúng 137/200, so với lời giải 118/200 (29 và 10 câu lệch, p = 0,0034) và PAL
  112/200 (36 và 11 câu lệch, p = 0,0003). Một phần nhờ tránh lỗi dòng `Answer:`. Cách lập luận trước rồi viết code đã có
  ở [HTL](https://arxiv.org/abs/2402.15729), nên đây không phải đóng góp mới.
- **Khi chương trình dịch trùng đáp án:** đúng 108/131 (82,4%, KTC 75,0–88,0%).

## Giới hạn

Chỉ một cỡ mô hình, chưa tinh chỉnh, và mô hình tự dịch lời giải của chính nó. Giả thuyết nảy ra từ chính các câu này, số của PAL đã
biết trước. Lời nhắc đòi đáp án số vẫn giữ, nên 5 báo nhầm của bên dịch phần lớn là `6z`, `25π`. Khảo sát vẫn sơ bộ: chưa tìm thấy bài
đo trực tiếp việc chương trình dịch chép lỗi lập luận, nhưng [CoTnPoT](https://arxiv.org/abs/2410.05318) đã dịch CoT sang code để
kiểm tra và [VeryTrace](https://arxiv.org/abs/2606.24124) đã nêu thiên lệch khi dịch. Hai bài này mới đọc qua kết quả tìm kiếm.
