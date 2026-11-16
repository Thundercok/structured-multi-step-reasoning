# Đăng ký trước: mức bám bước theo số vòng huấn luyện (bản nháp)

Ghi ngày 2026-11-16. Bản nháp, chưa commit. Chưa chấm checkpoint trung gian nào. Hướng nghiên cứu:
[khảo sát](related_work_survey_rl_stages_20261116.md), mục "Quyết định".

## Câu hỏi

H2 cho thấy Plain (`adapters/gsm8k_enriched_2000_s0`, 2.000 vòng) bám bước bị sửa ít hơn mô hình gốc. Mức giảm đó
xuất hiện ngay ở đầu quá trình huấn luyện, hay tăng dần theo số vòng?

- Giảm ngay từ đầu: nhiều khả năng do mô hình học **định dạng** hoặc kiểu viết.
- Giảm dần: nhiều khả năng do mô hình **tích lũy** kiến thức từ dữ liệu.

Đã biết lúc ghi: batch size là 1, nên 2.000 vòng chỉ đi qua 2.000 trên 7.061 bài huấn luyện (khoảng 0,28 lần tập
dữ liệu). Không có bài nào được học hai lần, nên "học thuộc do lặp lại" không phải giải thích ở đây.

## Thiết kế

- **Mô hình:** chỉ Plain, vì H2 nói về Plain. Các checkpoint **50, 200 và 1.000** vòng, chế độ `tuned`, cùng lệnh chấm
  như lượt GSM-Plus. Mỗi checkpoint được chép vào thư mục riêng, theo cách của
  `audit/lora_math_multistep_clean_20261109/run_early.sh`.
- **Đầu mút đã có sẵn:** mô hình gốc (`base_prefill`) và vòng 2.000, cùng 500 câu, ở
  `audit/gsm_plus_replication_20261114/`.
- **Câu hỏi:** đúng 500 câu GSM-Plus của lượt 2026-11-14 (`data/gsm_plus_v1/test.jsonl`, sha256 `e7ba7125…`).
  Các câu này đã chạy trước đó, nên lượt này có thể dùng lại hai đầu mút.
- **Can thiệp:** `run_standard_interventions`, tối đa 512 token, phân loại bằng `intervene.classify`.
- **Thời gian ước tính:** khoảng 3,5 giờ cho mỗi checkpoint (2,5 giờ chấm và 1 giờ can thiệp), tổng khoảng 10,5 giờ.

**Hạn chế đã biết trước:**

- Vòng 0 không phải mô hình gốc ở cùng điều kiện: `base_prefill` dùng prompt có hướng dẫn và bắt đầu sẵn bằng
  "Step 1:", còn `tuned` thì không.
- Ở checkpoint sớm, mô hình có thể chưa viết đúng định dạng `Step`/`Calc`, nên có ít kế hoạch can thiệp hơn. Tập câu
  được so sánh vì vậy thay đổi theo checkpoint. Số kế hoạch phải được báo kèm theo từng checkpoint.

## Quy tắc đọc

Người làm đề tài chấp nhận quy tắc này ngày 2026-11-16, trước khi chấm checkpoint nào.

- **Chỉ số:** `follows` khớp chính xác, trên các câu mà cả hai mốc được so đều có kế hoạch can thiệp.
- **T1 (giảm sớm):** mô hình gốc (`base_prefill`) so với vòng 50. Đúng chiều khi vòng 50 ra `follows` ít hơn.
- **T2 (giảm tiếp):** vòng 50 so với vòng 2.000. Đúng chiều khi vòng 2.000 ra `follows` ít hơn.
- **Phép kiểm:** McNemar chính xác hai phía, Holm–Bonferroni cho 2 kiểm định, α tổng 0,05. Một kiểm định **đạt** khi
  đúng chiều và qua ngưỡng Holm.
- **Cách đọc:** chỉ T1 đạt: **giảm ngay từ đầu**. Chỉ T2 đạt: **giảm dần**. Cả hai đạt: **giảm từ đầu và còn giảm
  tiếp**. Không cái nào đạt: **không phân biệt được**, chỉ báo đường cong để mô tả.
- Mốc 200 và 1.000 chỉ để mô tả hình dạng đường cong, không dùng để kết luận.
- Đã biết trước: nếu mức giảm chia đều cho hai đoạn, cả hai kiểm định có thể cùng không đạt (gốc so với vòng 2.000
  trên 185 cặp chỉ lệch 10/27). Kết quả "không phân biệt được" khi đó là kết luận hợp lệ.

## Chỉ số phụ (chỉ mô tả)

- Tỉ lệ `follows` và số kế hoạch can thiệp ở từng mốc (gốc, 50, 200, 1.000, 2.000).
- Độ đúng và phân loại kết quả can thiệp ở từng mốc.
- Số đầu ra đúng định dạng ở từng mốc.
