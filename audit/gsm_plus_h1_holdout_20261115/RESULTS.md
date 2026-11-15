# Kết quả: H1 trên 819 câu GSM-Plus còn lại

Đăng ký trước: [`docs/gsm_plus_h1_holdout_prereg.md`](../../docs/gsm_plus_h1_holdout_prereg.md), commit `eae137c7`,
push trước khi có kết quả. Chạy 2026-11-15 17:20 đến 2026-11-16 04:33 bằng `run.sh`. Số liệu từ `results.json`, đã
tính lại độc lập từ các file `*_interventions.jsonl` và khớp.

## Dữ liệu

sha256 của file gốc khớp với lần tải trước. 819 câu (vị trí 501 đến 1.319 theo `rank_key`), không câu nào trùng với
500 câu của lượt trước. Dữ liệu không được commit.

## Giả thuyết chính

| | Cặp | `follows` CF / Plain | Lệch | p | Chênh (95% CI) | Kết luận |
| --- | --- | --- | --- | --- | --- | --- |
| H1: CF > Plain | 428 | 336 / 330 | 32 / 26 | 0,512 | +1,4 điểm (−2,1; +4,9) | **không ủng hộ** |

Độ mạnh tính trước là 70% nếu hiệu ứng bằng GSM8K test. Theo quy tắc đọc đã đăng ký: cả hai lượt GSM-Plus đều không
ủng hộ H1, nên ghi rằng **hiệu ứng trên GSM8K test không lặp lại trên GSM-Plus**.

## Chỉ số phụ (chỉ mô tả)

- Độ đúng: CF 624/819 (76,2%, Wilson 73,2–79,0), Plain 605/819 (73,9%, 70,8–76,8). McNemar 77/58, p = 0,12.
- Số câu có kế hoạch can thiệp: CF 508, Plain 513. Bị cắt ở 1.024 token: CF 13, Plain 20.
- Gộp 1.319 câu (500 + 819), chỉ mô tả, không có p: 690 cặp, 533 / 523, lệch 62 / 52, chênh +1,4 điểm
  (95% CI −1,6; +4,5). Cận trên thấp hơn mức +4,8 trên GSM8K test.

| Phân loại | CF | Plain |
| --- | --- | --- |
| follows | 385 | 387 |
| follows_rounded | 21 | 28 |
| follows_approximate | 9 | 4 |
| reverted | 18 | 23 |
| moved | 38 | 33 |
| other | 35 | 35 |
| no_answer | 2 | 3 |

## Đọc kết quả

Trên GSM8K test, CF đi theo bước sửa nhiều hơn Plain (+4,8 điểm, p = 0,0018). Trên các biến thể đổi số của chính các
câu đó, chênh lệch còn khoảng +1,4 điểm ở cả hai lượt, và không có ý nghĩa thống kê. Khám phá, chưa kiểm định: lợi
thế của CF có thể gắn với phân phối GSM8K mà nó được huấn luyện.
