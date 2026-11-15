# Đăng ký trước: H1 trên 819 câu GSM-Plus còn lại

Ghi ngày 2026-11-15, sau khi đã có kết quả lượt 500 câu
([RESULTS.md](../audit/gsm_plus_replication_20261114/RESULTS.md), commit `b16a907e`), trước khi chạy mô hình trên
819 câu còn lại. Chưa đọc câu hỏi hay đầu ra nào của 819 câu này. Commit chứa file này là mốc thời gian.

## Đã biết lúc ghi

Ở lượt 500 câu, H1 (CF đi theo bước nhiều hơn Plain) không được ủng hộ: 197 so với 193 trên 262 cặp, lệch 30/26,
p = 0,69. Lượt này **không** gộp vào 500 câu đó để tính lại p, vì thêm câu sau khi thấy kết quả sẽ làm tăng tỉ lệ
dương tính giả. Đây là một kiểm định mới, trên tập câu tách riêng.

## 1. Dữ liệu

- Cùng file `data/gsm_plus_v1/raw_test.jsonl`. sha256 phải là `885c279b…` như trong
  `audit/gsm_plus_replication_20261114/data_manifest.json`, nếu khác thì dừng.
- Cùng cách lọc và sắp xếp như lượt trước (numerical substitution, bỏ câu trùng, sắp theo `gsm8k.rank_key`). Lấy
  các câu từ vị trí 501 đến hết. Phải có đúng 819 câu và không `id` nào trùng với 500 câu trước, nếu không thì dừng.
- Không xem tay câu hỏi hay đầu ra trước khi chạy xong `analyze.py`.

## 2. Mô hình và cách chạy

CF `adapters/gsm8k_cf_enriched_2000_s0` và Plain `adapters/gsm8k_enriched_2000_s0`, chế độ `tuned`, greedy, tối đa
1.024 token. Can thiệp bằng `run_standard_interventions`, giống hệt lượt trước. Không chạy mô hình gốc, vì giả thuyết
duy nhất không cần nó.

## 3. Giả thuyết chính (duy nhất)

**H1.** Trên các câu mà cả CF và Plain đều có kế hoạch can thiệp, CF ra `follows` (khớp chính xác) nhiều hơn Plain.
McNemar chính xác hai phía, α = 0,05, không hiệu chỉnh vì chỉ có một kiểm định. **Ủng hộ** khi đúng chiều và
p < 0,05. Mọi trường hợp khác là **không ủng hộ**. Báo kèm chênh lệch và khoảng tin cậy 95% (Wald, ghép cặp).

**Độ mạnh, tính trước** (ước khoảng 429 cặp, theo tỉ lệ 262/500 của lượt trước):

| Giả định | Độ mạnh |
| --- | --- |
| Hiệu ứng như GSM8K test (tỉ lệ lệch 14,9%, chia 66/34) | 70% |
| Tỉ lệ lệch như GSM-Plus (21,4%), chia 66/34 | 85% |
| Hiệu ứng như lượt 500 câu GSM-Plus (chia 30/26) | 8% |

Cách đọc kết quả: nếu ở đây H1 được ủng hộ mà lượt 500 câu thì không, ghi là hai lượt không nhất quán, không chọn
lượt có lợi. Nếu ở đây H1 cũng không được ủng hộ, ghi rằng hiệu ứng trên GSM8K test không lặp lại trên GSM-Plus.

## 4. Chỉ số phụ (chỉ mô tả)

- Độ đúng CF và Plain, Wilson 95%, McNemar giữa hai mô hình.
- Phân loại kết quả can thiệp và số đầu ra bị cắt.
- Gộp cả 1.319 câu (500 + 819) để ước lượng chênh lệch `follows` của CF so với Plain. Đây là ước lượng mô tả,
  không có giá trị p dùng để kết luận.

## 5. Tệp

`audit/gsm_plus_h1_holdout_20261115/`: `prepare.py`, `run.sh`, `analyze.py`. Ước tính khoảng 12 giờ trên M1 16 GB
(lượt trước: 2,5 giờ chấm mỗi mô hình và 1 giờ can thiệp mỗi mô hình cho 500 câu).
