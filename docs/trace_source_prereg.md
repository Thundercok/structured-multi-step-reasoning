# Đăng ký trước: nguồn vết huấn luyện và mức bám bước

Ghi ngày 2026-11-16, hoàn tất ngày 2026-11-17. Người làm đề tài chấp nhận quy tắc đọc ngày 2026-11-17, trước khi sinh
vết, huấn luyện hay chấm bất cứ gì. Hướng nghiên cứu: [khảo sát](related_work_survey_rl_stages_20261116.md), mục "Quyết định".
Code: `structured_llm/self_traces.py` (commit `454aee36`).

**N** và **số vòng** được điền ngày 2026-11-17, sau kết quả
[mức bám bước theo số vòng](sft_dose_response_prereg.md) (commit `39c7ecc6`) và trước khi sinh vết. Người làm đề tài
chọn 200 vòng vì chi phí: khoảng 10–11 giờ, so với khoảng 40 giờ cho 2.000 vòng. Kết quả số vòng là "không phân biệt
được", nên lựa chọn này **không** dựa trên kết luận rằng mức giảm xảy ra sớm. Ở 200 vòng, Plain có `follows` 73%, so
với 71% ở 2.000 vòng và 84% ở mô hình gốc; các con số này chỉ để mô tả.

## Câu hỏi

H2 cho thấy SFT trên vết chuyển từ lời giải của người (Plain) làm mô hình bám bước bị sửa ít hơn mô hình gốc. RFEval
lại thấy SFT trên vết dài do mô hình viết không làm giảm. Một khác biệt giữa hai bên là **nguồn vết**.

Câu hỏi: giữ nguyên câu hỏi, số vòng và mọi siêu tham số, chỉ đổi nguồn vết, thì mức bám bước có khác không?

- **`self`:** vết đúng do chính mô hình gốc viết (`base_prefill`).
- **`human`:** vết chuyển từ lời giải GSM8K của người, cùng cách chuyển với Plain (`gsm8k.convert`, `enrich_step1=True`).

## Dự đoán

Ghi ngày 2026-11-17, trước khi sinh vết. Người làm đề tài chọn dự đoán từ ba hướng được đưa ra trong chat (`self`
nhiều hơn, `human` nhiều hơn, không khác), và câu chữ do agent ghi lại theo lựa chọn đó:

**`human` bám bước bị sửa nhiều hơn `self`.** Lý do: theo Xu và cs. (2611.01967), huấn luyện trên chính lời giải của
mô hình làm nó bỏ qua bằng chứng bị sửa nhiều hơn.

Dự đoán không đổi phép kiểm. H3 vẫn là kiểm định hai phía.

## Thiết kế

### Dữ liệu huấn luyện

1. `self_traces items N` lấy N câu đầu của tập train (thứ tự `rank_key`) có vết người chuyển được.
2. Mô hình gốc chạy `evaluate --modes base_prefill` trên N câu đó, `--max-tokens 1024`, greedy.
3. `self_traces build` giữ các vết qua `keep()`: không bị cắt, đúng định dạng, đúng đáp án, mọi Calc đúng. Gọi số vết
   giữ được là **K**.
4. Cả `self` và `human` dùng **đúng K câu đó**. Hai tập chỉ khác nhau ở phần vết. Tập valid giống nhau
   (`data/structured_gsm8k_enriched_v1/valid.jsonl`).

`keep()` đã chốt trong commit `454aee36` và không sửa sau khi thấy tỉ lệ giữ. Vết bị loại không được sửa tay.

- **N:** bắt đầu với **400**. Chọn sao cho K ≥ số vòng, để với batch size 1 không câu nào bị học
  hai lần, giống Plain. Trên GSM-Plus `keep()` giữ khoảng 50%, nên dự kiến N ≈ 2 × số vòng. Tỉ lệ trên tập train
  GSM8K có thể khác. Nếu K vẫn nhỏ hơn số vòng thì chạy thêm câu (N tăng dần) cho đến khi đủ, không đổi `keep()`.
- **Kiểm tra trước khi huấn luyện** (không xem nội dung từng vết):
  - Hai file `train.jsonl` có cùng số dòng và cùng thứ tự câu hỏi.
  - Định dạng vết `self` sau `training_row` khớp định dạng vết `human` (cùng prompt chatml, cùng thẻ mở đầu phần suy
    nghĩ, phần "Step 1:" được điền sẵn trong `base_prefill` có mặt trong vết).
  - Báo phân bố số token của hai tập, và số vết vượt `--max-seq-length`.

### Huấn luyện

- Hai adapter, `adapters/trace_self_<iters>_s0` và `adapters/trace_human_<iters>_s0`.
- `structured_llm/train.sh`, cùng siêu tham số với Plain (LoRA 8 lớp, batch 1, lr 5e-5, seed 0, `--max-seq-length`
  512). Hai lần chạy chỉ khác `data-dir`.
- **Số vòng:** **200**. Adapter là `adapters/trace_self_200_s0` và `adapters/trace_human_200_s0`.

### Chấm

- 500 câu GSM-Plus của lượt 2026-11-14 (`data/gsm_plus_v1/test.jsonl`, sha256 `e7ba7125…`), chế độ `tuned`,
  `--max-tokens 1024`, rồi `run_standard_interventions` (tối đa 512 token, phân loại bằng `intervene.classify`).
  Cùng quy trình với `audit/sft_dose_response_20261116/run.sh`.
- Lưu ở `audit/trace_source_<YYYYMMDD>/`: script, vết sinh ra, `manifest.json` của `build`, kết quả chấm và can thiệp.

### Thời gian ước tính

Lượt dose-response chấm khoảng 23–30 giây mỗi câu.

- Sinh vết: N × khoảng 25 giây. Ví dụ N = 400 mất khoảng 3 giờ; N = 4.000 mất khoảng 28 giờ.
- Huấn luyện: hai lần, mỗi lần tỉ lệ với số vòng.
- Chấm: khoảng 3,5 giờ cho mỗi adapter, tổng khoảng 7 giờ.

Vì vậy số vòng quyết định phần lớn chi phí.

## Quy tắc đọc

- **Chỉ số:** `follows` khớp chính xác, trên các câu mà **cả hai** adapter đều có kế hoạch can thiệp.
- **H3:** `self` so với `human`. McNemar chính xác hai phía, α = 0,05, một kiểm định nên không hiệu chỉnh.
- **Cách đọc:**
  - `self` ra `follows` nhiều hơn và p < 0,05: **nguồn vết có ảnh hưởng; vết tự viết giữ mức bám bước tốt hơn**.
  - `human` ra `follows` nhiều hơn và p < 0,05: **nguồn vết có ảnh hưởng; vết của người giữ mức bám bước tốt hơn**.
  - p ≥ 0,05: **không phân biệt được** ở cỡ mẫu này. Không được đọc là "nguồn vết không ảnh hưởng".
- Chỉ H3 dùng để kết luận. Mọi so sánh khác là mô tả.

## Hạn chế đã biết trước

- **Câu hỏi được chọn theo mô hình gốc:** K câu đều là câu mô hình gốc đã giải đúng hoàn toàn, nên dễ hơn trung bình.
  Hai tập dùng cùng câu nên H3 không bị ảnh hưởng, nhưng không so trực tiếp được hai adapter này với Plain (huấn
  luyện trên câu không chọn lọc). So với Plain chỉ để mô tả.
- **Vết `self` có thể dài hơn hoặc khác văn phong.** Nếu H3 đạt, nguyên nhân có thể là độ dài hay kiểu viết chứ không
  phải "tự viết" theo nghĩa hẹp. Phân bố số token được báo kèm để người đọc tự cân nhắc.
- **Một seed.** Khác biệt giữa hai adapter gồm cả độ ngẫu nhiên của huấn luyện. Không có lần chạy lặp để ước lượng
  phần này.
- **Cỡ mẫu:** gộp 1.319 câu GSM-Plus, CF hơn Plain 1,4 điểm (95% CI −1,6 đến +4,5), không phân biệt được. Lượt này
  chỉ có 500 câu, nên một khác biệt cỡ đó giữa `self` và `human` càng không phân biệt được.

## Chỉ số phụ (chỉ mô tả)

- Tỉ lệ `follows`, số kế hoạch can thiệp, độ đúng, phân loại kết quả can thiệp của `self`, `human`, mô hình gốc
  (`base_prefill`) và Plain 2.000 vòng, trên cùng 500 câu.
- K, số vết bị loại theo từng lý do của `keep()`, và phân bố số token của hai tập huấn luyện.
- Số đầu ra đúng định dạng của mỗi adapter.
