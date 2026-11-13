# Kết quả tập test GSM8K niêm phong

Chạy một lần duy nhất, từ 2026-11-11 17:37 đến 2026-11-13 17:25, theo [bản đăng ký trước](../../docs/sealed_test_gsm8k_prereg.md)
ở commit `bfa6181b`. Commit đó được push trước khi tải tập test. Số liệu lấy từ `results.json`, sinh bởi
`analyze.py`. Các giá trị p đã được tính lại độc lập và khớp.

- Dữ liệu: 1.319 câu, sha256 trong `data_manifest.json`, không câu nào trùng với train, valid hay dev, không loại câu nào.
- Lượt chạy bị tạm dừng một lần (SIGSTOP/SIGCONT) trong bước can thiệp của Plain. Vì dùng greedy nên việc này không đổi đầu ra.

## Giả thuyết chính H1: ủng hộ

Trên 671 câu mà cả hai mô hình đều có kế hoạch can thiệp:

| | CF | Plain |
| --- | :---: | :---: |
| `follows` | 544 (81,1%) | 512 (76,3%) |
| Chỉ mô hình này `follows` | 66 | 34 |

McNemar chính xác hai phía: p = 0,0018. Chênh lệch ghép cặp là +4,8 điểm phần trăm, khoảng tin cậy 95% (Wald) từ +1,9
đến +7,7 điểm.

## Chỉ số phụ

| Mã | Kết quả | Theo quy tắc |
| --- | --- | --- |
| S1 | Độ đúng: CF 1.052 (79,8%), Plain 1.040 (78,8%); 115/103 cặp lệch; p = 0,456 | Không khác biệt |
| S2 | CF 1.052 (79,8%) so với `base_prefill` 1.167 (88,5%); hiệu −8,7 điểm, khoảng tin cậy 95% từ −10,8 đến −6,7 | **Không đạt** (cần cận dưới > −3) |
| T1 | `format_valid` của CF: 1.212/1.319 (91,9%), Wilson 95% từ 90,3% đến 93,2% | Đạt |
| T3 | Dòng `Calc` sai của CF: 44/4.332 (1,02%) | **Không đạt** (cần < 1%) |
| S4 | Bị cắt ở 1.024 token: CF 11, Plain 27, `base_prefill` 3 | Mô tả |

Phân loại can thiệp (S3) trên 671 câu chung:

| Kết quả | CF | Plain |
| --- | :---: | :---: |
| `follows` | 544 | 512 |
| `follows_rounded` | 29 | 35 |
| `follows_approximate` | 5 | 5 |
| `reverted` | 26 | 41 |
| `moved` | 17 | 27 |
| `other` | 48 | 49 |
| `no_answer` | 2 | 2 |

Số câu có kế hoạch can thiệp: CF 781, Plain 808.

## Được nói và không được nói

- **Được nói:** trên tập test niêm phong, huấn luyện phản thực làm đáp án đi theo bước bị sửa nhiều hơn huấn luyện
  thường, mà không làm độ đúng khác đi.
- **Không được nói:** tinh chỉnh giữ được độ đúng của mô hình gốc. `base_prefill` đúng nhiều hơn CF khoảng 8,7 điểm.
  Cũng không được nói tỉ lệ tính sai dưới 1%.
- **Giới hạn:** mỗi mô hình chỉ có seed 0. Mỗi mô hình bị can thiệp trên vết của chính nó, nên cặp so sánh là theo câu
  hỏi, không theo cùng một vết.
