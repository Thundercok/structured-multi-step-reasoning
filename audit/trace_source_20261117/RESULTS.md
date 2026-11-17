# Kết quả: nguồn vết huấn luyện (self và human) và mức bám bước

Đăng ký trước: [`docs/trace_source_prereg.md`](../../docs/trace_source_prereg.md), commit `38a70de3`. Script chạy và
phân tích được commit ở `74db4bc3`, trước khi sinh vết. Hai commit này chưa được push trước khi có kết quả, nên thứ tự
chỉ được chứng minh bằng git cục bộ.

Lượt chạy bắt đầu lúc 2026-11-17 14:44 bằng `run.sh` và xong lúc 2026-11-18 02:02. Người làm đề tài cho dừng giữa
chừng từ 19:29 đến 20:44, trong lúc chấm `self`, rồi chạy tiếp. Khi chạy tiếp, script dựng lại hai tập huấn
luyện và được đúng sha256 cũ, còn bước huấn luyện được bỏ qua. Số liệu lấy từ `results.json`. H3 đã được tính lại độc
lập từ hai file `*_interventions.jsonl`, và kết quả khớp.

## Dữ liệu huấn luyện

- Mô hình gốc sinh vết `base_prefill` cho 400 câu train đầu tiên. `keep()` giữ lại **K = 229** vết. Các vết bị loại
  gồm: sai định dạng 148, sai đáp án 11, Calc sai 11, bị cắt 1. Vì K ≥ 200 nên không cần thêm câu.
- Kết quả kiểm tra trước khi huấn luyện (`check.json`):
  - Hai tập có cùng 229 dòng, cùng prompt và cùng thứ tự.
  - Không dòng nào sai định dạng, và không dòng nào vượt 512 token.
  - Độ dài trung bình là 209,4 token với `self` và 210,2 token với `human`; trung vị là 202 và 207.
- sha256 của `train.jsonl`: `self` là `fc300891…`, `human` là `3723d40b…` (đầy đủ trong `data/manifest.json`).

## Giả thuyết chính

| | Cặp | `follows` self / human | Lệch | p | Chênh (95% CI) | Kết luận |
| --- | --- | --- | --- | --- | --- | --- |
| H3: self và human | 140 | 126 / 114 | 18 / 6 | 0,023 | +8,6 điểm (+1,9; +15,3) | **self hơn** |

Theo quy tắc đọc: `self` ra `follows` nhiều hơn và p < 0,05, nên kết luận là **nguồn vết có ảnh hưởng; vết tự viết
giữ mức bám bước tốt hơn**.

Người làm đề tài đã dự đoán ngược lại (`human` hơn). Kết quả không ủng hộ dự đoán đó.

## Chỉ số phụ (chỉ mô tả)

Bảng này tính trên 500 câu GSM-Plus. Mỗi cột có tập câu có kế hoạch can thiệp riêng, nên tỉ lệ `follows` của các cột
không so trực tiếp được với nhau.

| | self | human | Gốc | Plain 2.000 |
| --- | --- | --- | --- | --- |
| Có kế hoạch can thiệp | 227 | 209 | 214 | 317 |
| `follows` | 201 (88,5%) | 158 (75,6%) | 180 (84,1%) | 224 (70,7%) |
| Giải đúng / 500 | 414 | 363 | 424 | 369 |
| Wilson 95% | 79,2–85,9 | 68,5–76,3 | 81,4–87,7 | 69,8–77,5 |
| Đúng định dạng / 500 | 313 | 330 | 294 | 461 |
| Bị cắt ở 1.024 token | 14 | 27 | 3 | 5 |

| Phân loại | self | human | Gốc | Plain 2.000 |
| --- | --- | --- | --- | --- |
| follows | 201 | 158 | 180 | 224 |
| follows_rounded | 7 | 6 | 7 | 20 |
| follows_approximate | 3 | 4 | 2 | 3 |
| reverted | 7 | 13 | 8 | 17 |
| moved | 4 | 11 | 5 | 27 |
| other | 4 | 10 | 11 | 23 |
| no_answer | 1 | 7 | 1 | 3 |

## Hạn chế

- **Một seed.** Chênh lệch giữa hai adapter có chứa cả phần ngẫu nhiên của quá trình huấn luyện, và lượt này không đo
  được phần đó.
- **Một mốc số vòng (200), trên 229 câu.** Hai adapter có ít dòng đúng định dạng hơn Plain 2.000 nhiều (313 và 330 so
  với 461). H3 chỉ tính trên các câu có kế hoạch can thiệp, tức là các câu có vết đọc được, nên H3 không sai vì chuyện
  này. Tuy nhiên tập 140 câu này đã được lọc qua định dạng.
- **Câu được chọn theo mô hình gốc.** 229 câu huấn luyện đều là câu mà mô hình gốc viết đúng định dạng và giải đúng.
  Không so trực tiếp được hai adapter này với Plain.
- **Độ dài và văn phong.** Độ dài trung bình của hai tập gần như bằng nhau, nên độ dài khó là nguyên nhân. Văn phong
  thì chưa đo.

## Đọc kết quả

Giữ nguyên câu hỏi, số vòng và siêu tham số, chỉ đổi nguồn vết: mô hình học từ vết do chính nó viết làm theo bước bị
sửa nhiều hơn mô hình học từ vết chuyển từ lời giải của người.

**Thăm dò, chưa kiểm định:** vết `self` gần với cách mô hình vốn viết, nên huấn luyện có thể làm mô hình thay đổi ít
hơn. Lượt này không có phép đo nào cho ý đó, ví dụ độ lệch so với mô hình gốc. Vì vậy đây chỉ là một giả thuyết cho
lượt sau.
