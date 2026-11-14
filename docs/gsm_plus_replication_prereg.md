# Đăng ký trước: kiểm chứng lại trên GSM-Plus

Ghi ngày 2026-11-14, trước khi tải nội dung GSM-Plus. Đến lúc này mới chỉ đọc thẻ dữ liệu (README) và danh sách
trường. Commit chứa file này là mốc thời gian, và mọi kết quả GSM-Plus đều phải đến sau commit đó.

Mục đích: kiểm xem hai kết quả trên tập test GSM8K niêm phong
([RESULTS.md](../audit/gsm8k_sealed_test_20261111/RESULTS.md)) có lặp lại trên dữ liệu mới hay không. Kết quả thứ hai
(Plain đi theo bước ít hơn mô hình gốc) ở lượt trước là hậu nghiệm; lượt này đăng ký nó trước. Cả hai kết quả đã được
báo trong các công trình trước ([khảo sát](related_work_survey_20261114.md)), nên đây là kiểm chứng lại, không phải
luận điểm mới.

## 1. Dữ liệu

- Nguồn: `qintongli/GSM-Plus` trên Hugging Face, revision `3b708db57b96a16e8e3368ed2956990c0809440e`, file
  `data/test-00000-of-00001.jsonl`. Giấy phép CC BY-SA 4.0, chỉ dùng để đánh giá. Ghi sha256 ngay khi tải xong.
  Không commit dữ liệu.
- Chỉ lấy loại biến thể numerical substitution (đổi số, giữ nguyên cấu trúc bài). Mỗi câu test GSM8K có đúng một
  biến thể loại này, nên các câu độc lập với nhau. Nếu số câu loại này khác 1.319 thì dừng lại trước khi chạy mô hình
  và báo lại.
- Lấy 500 câu đầu tiên theo `gsm8k.rank_key(question)`. `id` là 16 ký tự đầu của khóa đó. Đáp án lấy từ trường
  `answer`.
- Kiểm tra trùng với train, valid và dev sau khi chuẩn hóa bằng `gsm8k.normalize`, rồi báo số câu trùng. Câu trùng
  bị bỏ ra trước khi lấy mẫu.
- Đã biết trước: các câu này là biến thể của câu test GSM8K, mà tập đó đã chạy ngày 2026-11-13. Không có quyết định
  nào được chỉnh theo từng câu test, và các mô hình không được huấn luyện trên tập test.
- Không xem tay câu hỏi, đầu ra hay từng câu cụ thể nào trước khi chạy xong `analyze.py`.

## 2. Mô hình và cách chạy

Giống hệt lượt GSM8K: CF `adapters/gsm8k_cf_enriched_2000_s0` (`tuned`), Plain `adapters/gsm8k_enriched_2000_s0`
(`tuned`), và mô hình gốc `base_prefill`. Greedy, tối đa 1.024 token. Can thiệp bằng `counterfactual.plan_intervention`
trên chính đầu ra của từng mô hình, tối đa 512 token viết tiếp, phân loại bằng `intervene.classify`. Mô hình gốc được
can thiệp bằng `structured_llm.intervene --modes base_prefill`, cùng bộ lập và bộ phân loại. Một lượt bị ngắt thì
chạy tiếp bằng cùng lệnh.

## 3. Giả thuyết chính

Cả hai dùng `follows` (khớp chính xác giá trị bị sửa) và McNemar chính xác hai phía.

- **H1.** Trên các câu mà cả CF và Plain đều có kế hoạch can thiệp, CF ra `follows` nhiều hơn Plain.
- **H2.** Trên các câu mà cả Plain và mô hình gốc đều có kế hoạch can thiệp, Plain ra `follows` ít hơn mô hình gốc.

Hiệu chỉnh Holm–Bonferroni cho hai kiểm định, α tổng là 0,05: giá trị p nhỏ hơn phải dưới 0,025, giá trị p lớn hơn
phải dưới 0,05. Một giả thuyết được **ủng hộ** khi đúng chiều và qua ngưỡng Holm. Mọi trường hợp khác là **không ủng
hộ**. Báo kèm tỉ lệ từng mô hình, chênh lệch và khoảng tin cậy 95% (Wald, ghép cặp).

Cơ sở: trên GSM8K test, H1 là 544 so với 512 trên 671 cặp (66/34, p = 0,0018); H2 là 346 so với 376 trên 441 câu chung
cả ba (18/48, p = 0,0003, hậu nghiệm). Với 500 câu, số cặp chung dự kiến khoảng 254 cho H1 và 185 cho H2.

**Độ mạnh, tính trước khi chạy.** Giả sử hiệu ứng bằng đúng mức trên GSM8K test và ngưỡng Holm 0,025, độ mạnh là
khoảng **34% cho H1** và **56% cho H2** (ở 1.319 câu sẽ là 82% và 97%). Người làm đề tài chọn 500 câu để giữ thời
gian máy khoảng 1 ngày, biết trước điều này. Vì vậy kết quả "không ủng hộ" ở lượt này **không** được đọc là bằng
chứng không có hiệu ứng; nó chỉ có nghĩa là lượt này không đủ để thấy hiệu ứng.

Đã biết trước khi chạy: trên GSM8K test, so sánh CF với mô hình gốc cho p = 0,070 trên 441 câu chung cả ba, nhưng
p = 0,018 trên 485 câu chung hai mô hình. Vì vậy lượt này chốt trước tập so sánh: mỗi kiểm định dùng các câu mà
**cả hai** mô hình trong cặp đều có kế hoạch can thiệp.

## 4. Chỉ số phụ (chỉ mô tả)

- Độ đúng của ba mô hình, kèm Wilson 95%.
- CF so với mô hình gốc về `follows`, McNemar hai phía, không dùng để kết luận.
- Phân loại kết quả can thiệp và số đầu ra bị cắt ở 1.024 token, theo từng mô hình.

## 5. Tệp

- `audit/gsm_plus_replication_20261114/prepare.py`: tải, lọc, lấy mẫu, ghi manifest.
- `audit/gsm_plus_replication_20261114/run.sh`: chạy toàn bộ.
- `audit/gsm_plus_replication_20261114/analyze.py`: tính H1, H2 và chỉ số phụ.

Ước tính khoảng 1 ngày trên M1 16 GB.
