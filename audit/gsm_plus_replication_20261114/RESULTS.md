# Kết quả: kiểm chứng lại trên GSM-Plus

Đăng ký trước: [`docs/gsm_plus_replication_prereg.md`](../../docs/gsm_plus_replication_prereg.md), commit `e0e2020b`,
push trước khi tải dữ liệu. Chạy 2026-11-14 14:04 đến 2026-11-15 01:17 bằng `run.sh`. Số liệu từ `results.json`
(do `analyze.py` ghi), đã tính lại độc lập từ các file `*_interventions.jsonl` và khớp.

## Dữ liệu

10.552 dòng, 1.319 câu numerical substitution (đúng như đăng ký), 0 câu trùng với train/valid/dev, lấy 500 câu.
sha256 trong `data_manifest.json`. Dữ liệu không được commit (`data/gsm_plus_v1/`).

## Giả thuyết chính (McNemar chính xác hai phía, Holm)

| | Cặp | `follows` | Lệch | p | Chênh (95% CI, Wald ghép cặp) | Kết luận |
| --- | --- | --- | --- | --- | --- | --- |
| H1: CF > Plain | 262 | 197 / 193 | 30 / 26 | 0,689 | +1,5 điểm (−4,1; +7,1) | **không ủng hộ** |
| H2: Plain < gốc | 185 | 142 / 159 | 10 / 27 | 0,0076 | −9,2 điểm (−15,5; −2,9) | **ủng hộ** |

Holm: p nhỏ hơn (H2, 0,0076) dưới 0,025; p còn lại (H1, 0,689) không dưới 0,05.

Độ mạnh tính trước chỉ khoảng 34% cho H1, nên H1 "không ủng hộ" **không** là bằng chứng không có hiệu ứng. Cũng cần
ghi rõ: số cặp lệch gần hòa (30/26), khác hẳn GSM8K test (66/34), và chênh lệch ước tính (+1,5) nhỏ hơn GSM8K (+4,8),
dù khoảng tin cậy vẫn chứa +4,8.

## Chỉ số phụ (chỉ mô tả)

- Độ đúng trên 500 câu: gốc 424 (84,8%, Wilson 81,4–87,7), CF 378 (75,6%, 71,6–79,2), Plain 369 (73,8%, 69,8–77,5).
- CF so với gốc về `follows`: 178 cặp, 146 / 154, lệch 14 / 22, p = 0,243, chênh −4,5 điểm (−11,1; +2,1).
- Số câu có kế hoạch can thiệp: CF 298, Plain 317, gốc 214.
- Bị cắt ở 1.024 token: CF 10, Plain 5, gốc 3.

| Phân loại | CF | Plain | Gốc |
| --- | --- | --- | --- |
| follows | 223 | 224 | 180 |
| follows_rounded | 13 | 20 | 7 |
| follows_approximate | 5 | 3 | 2 |
| reverted | 14 | 17 | 8 |
| moved | 18 | 27 | 5 |
| other | 22 | 23 | 11 |
| no_answer | 3 | 3 | 1 |

## Đọc kết quả

- Tinh chỉnh thường làm giảm mức đi theo bước so với mô hình gốc (H2): lặp lại, lần này đã đăng ký trước.
- Huấn luyện phản thực đi theo bước nhiều hơn tinh chỉnh thường (H1): không lặp lại ở cỡ mẫu này.
- Câu hậu nghiệm cũ "CF giữ mức đi theo bước gần mô hình gốc" không được củng cố: CF thấp hơn gốc 4,5 điểm, không
  có ý nghĩa thống kê (p = 0,24), trên dữ liệu ít.

Khám phá, quyết định sau khi thấy kết quả: hai adapter kém mô hình gốc khoảng 10 điểm độ đúng trên GSM-Plus, so với
khoảng 9 điểm trên GSM8K test. Chưa kiểm định.
