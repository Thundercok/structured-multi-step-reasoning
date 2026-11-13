# Đăng ký trước: chạy tập test GSM8K niêm phong

Ghi ngày 2026-11-11, trước khi tải hay mở tập test. Bản này sửa đổi giao thức ngày 2026-11-08 trong
[research_plan.md](research_plan.md) (mục "Giao thức Niêm phong Tiền đăng ký"). Chỗ nào bản này không nói tới thì
giữ nguyên giao thức cũ. Commit chứa file này là mốc thời gian, và mọi kết quả test đều phải đến sau commit đó.

## 1. Dữ liệu

- Lấy `grade_school_math/data/test.jsonl` từ `openai/grade-school-math`, cùng revision `3101c7d5` với tập train
  (`data/gsm8k_source/manifest.json`). Ghi sha256 vào manifest ngay khi tải xong.
- Dùng cả 1.319 câu và không loại câu nào. `id` lấy từ 16 ký tự đầu của `gsm8k.rank_key(question)`, đáp án lấy bằng
  `gsm8k.gold_answer`.
- Kiểm tra trùng lặp với train, valid và dev sau khi chuẩn hóa bằng `gsm8k.normalize`. Báo số câu trùng. Nếu có câu
  trùng, báo kết quả cả khi giữ và khi bỏ chúng; kết luận chính dùng bản giữ.
- Không xem tay câu hỏi, đầu ra hay từng câu cụ thể nào trước khi chạy xong `analyze.py`.

## 2. Mô hình và cách chạy

| Tên | Adapter | Chế độ |
| --- | --- | --- |
| CF | `adapters/gsm8k_cf_enriched_2000_s0` | `tuned` |
| Plain | `adapters/gsm8k_enriched_2000_s0` | `tuned` |
| Gốc mồi | không | `base_prefill` |

Tất cả dùng greedy (temperature 0), tối đa 1.024 token, với bộ chấm, lời nhắc và bộ lập can thiệp ở commit này.
Phép can thiệp dùng `counterfactual.plan_intervention` trên chính đầu ra của từng mô hình, cho tối đa 512 token viết
tiếp, rồi phân loại bằng `intervene.classify`. Đây là đúng quy trình của đợt N=300
(`scripts/run_scaleup_eval_300.py`, hàm `run_standard_interventions`). Một lượt bị ngắt thì chạy tiếp bằng cùng
lệnh; vì dùng greedy, kết quả không đổi.

## 3. Giả thuyết chính

**H1.** Trên các câu mà cả CF và Plain đều có kế hoạch can thiệp, CF ra `follows` (đi theo giá trị bị sửa, khớp
chính xác) nhiều hơn Plain.

- Kiểm định: McNemar chính xác hai phía trên các cặp lệch, α = 0,05.
- **Ủng hộ** nếu CF có nhiều `follows` hơn và p < 0,05. Mọi trường hợp khác là **không ủng hộ**.
- Báo kèm tỉ lệ của từng mô hình, chênh lệch và khoảng tin cậy 95% của chênh lệch ghép cặp.
- Cơ sở: trên 199 câu dev+valid, kết quả thăm dò là 93 so với 81 trên 114 cặp (18/6, p = 0,023).

Chỉ H1 được dùng để rút kết luận chính của đề tài.

## 4. Chỉ số phụ

Báo đủ, kèm khoảng tin cậy 95%, nhưng không dùng thay cho H1.

| Mã | Nội dung | Cách đọc |
| --- | --- | --- |
| S1 | Độ đúng, CF so với Plain | McNemar chính xác hai phía. Trên dev, hai bên ngang nhau (165 so với 164) |
| S2 (thay T2 cũ) | Độ đúng của CF không thua `base_prefill` quá 3 điểm phần trăm | Đạt nếu cận dưới khoảng tin cậy 95% (Wald, ghép cặp) của hiệu CF − gốc lớn hơn −3 điểm |
| T1 (giữ) | `format_valid` của CF | Đạt nếu ≥ 90% và cận dưới Wilson 95% ≥ 88% |
| T3 (giữ, định nghĩa rõ) | Tỉ lệ dòng `Calc` tính sai của CF, gộp mọi dòng trên 1.319 đầu ra | Đạt nếu < 1% |
| S3 | Phân loại kết quả can thiệp (`follows_rounded`, `reverted`, `moved`, `other`) | Chỉ mô tả |
| S4 | Số đầu ra bị cắt ở 1.024 token, theo từng mô hình | Chỉ mô tả |

**Vì sao sửa T2.** T2 cũ coi p > 0,05 là "không thua kém". Kiểm định không có ý nghĩa không chứng minh được hai bên
bằng nhau, nhất là khi mẫu nhỏ. Chuẩn chung là kiểm không thua kém với biên chốt trước. Mức 3 điểm được chọn trước
khi có số liệu test.

## 5. Phần cắt bỏ so với giao thức cũ

Những phần sau không chạy trong lượt này. Nếu chạy sau, chúng phải được ghi là phân tích hậu nghiệm.

- `base_native`, `enriched_cf_tool`, seed 1 và 2: không giả thuyết nào ở trên cần đến, và mỗi phần tốn khoảng 15
  đến 20 giờ máy M1.
- Quét mọi bước (step sweep): đây là phân tích phụ trên dev, tốn thêm khoảng 10 giờ.
- MATH-500: thí nghiệm sạch trên dev (`docs/ablation_math_multistep_spec.md`, mục 5) không ủng hộ giả thuyết, nên
  chưa có giả thuyết MATH nào để kiểm. MATH-500 vẫn niêm phong.

## 6. Giới hạn biết trước

- Mỗi mô hình chỉ có một seed. Trên dev, ba seed CF cho 87, 82 và 82 trên 100 câu, nên S1 và S2 dao động theo
  seed. Kết luận chỉ áp dụng cho cặp seed 0.
- Mỗi mô hình được can thiệp trên vết của chính nó. Vì vậy cặp so sánh là theo câu hỏi, không theo cùng một vết.
- Chạy theo thứ tự CF, Plain, can thiệp của CF, can thiệp của Plain, rồi `base_prefill`. Nhờ vậy H1 có kết quả trước.
  Chạy khoảng 2,5 ngày trên M1 16 GB.

## 7. Tệp

- Chạy: `audit/gsm8k_sealed_test_20261111/run.sh`
- Chấm: `audit/gsm8k_sealed_test_20261111/analyze.py`. Script này được commit cùng bản đăng ký và đã thử trên đầu ra
  dev N=300 trước khi tải tập test.

## Kết quả

Đã chạy xong ngày 2026-11-13: H1 được ủng hộ, S2 và T3 không đạt. Xem [RESULTS.md](../audit/gsm8k_sealed_test_20261111/RESULTS.md).
