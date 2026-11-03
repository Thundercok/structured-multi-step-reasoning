# Cổng 1 trên 100 câu dev GSM8K, 2026-11-03

Mô hình `tuned` là adapter thử 200 vòng (`adapters/smoke_20261102`), chưa phải mô hình cuối. Nhiệt độ 0, một seed.
Đầu ra thô ở các file `.jsonl`. Chấm lại bằng `python -m structured_llm.analyze` và
`python -m structured_llm.intervene --run ... --rescore`.

| Chế độ | Đúng | Đúng định dạng | Token TB | Câu sai bị bắt | Câu đúng bị báo nhầm |
| --- | ---: | ---: | ---: | ---: | ---: |
| `tuned` | 94 | 70 | 182 | 4/6 | 47/94 |
| `base_prefill` | 93 | 61 | 144 | 6/7 | 35/93 |
| `base_pal` | 93 | | 87 | | |
| `base_showcalc` | 85 | | 139 | | |

Cờ của `base_pal` và `base_showcalc` không có nghĩa vì chúng không dùng định dạng này.

| Can thiệp | Đủ điều kiện | Đổi theo | Đổi theo, có làm tròn | Giữ đáp án cũ | Đổi khác | Bị cờ, chỉ thấy đáp án đổi |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `base_prefill` | 53/100 | 45 | 8 | 0 (0 đến 6,8%) | 0 | 0 |
| `tuned` | 31/100 | 24 | 4 | 2 (1,8 đến 20,7%) | 0 | 1 |
| `base_showcalc` | 40/100 | 26 | 5 | 3 (2,6 đến 19,9%) | 1 | 5 |

Ngoặc là khoảng Wilson 95% cho tỷ lệ giữ đáp án cũ. 11 câu đủ điều kiện ở cả ba chế độ.

**Đọc kết quả.** Khi mô hình đã viết phép tính ra, đáp án của nó gần như luôn đổi theo phép tính bị sửa, kể cả không huấn luyện.
Đây chỉ là trên các vết đủ điều kiện: `base_showcalc` có 38 câu không tìm thấy phép tính, và chưa đo được những câu đó.
Bộ kiểm tra chưa đo được trên bộ này, vì quá ít câu sai và cờ định dạng chiếm phần lớn báo nhầm.

**Giới hạn.** Nhãn `follows_rounded` được thêm **sau khi** đọc kết quả (lần đầu `base_prefill` là 45 đổi theo, 8 khác). Ngưỡng 1 đơn vị
hoặc 1% do agent chọn; 8 ca của `base_prefill` đã được đọc tay. Sửa một số trong văn bản chỉ kiểm tra sự phụ thuộc vào chữ viết ra, không
chứng minh đó là cách mô hình tính bên trong. Mô hình 200 vòng chưa đại diện cho tinh chỉnh đầy đủ.
