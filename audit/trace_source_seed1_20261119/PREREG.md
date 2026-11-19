# Đăng ký trước: lặp lại H3 với seed thứ hai

Ghi ngày 2026-11-19, trước khi huấn luyện hay chấm. Người làm đề tài chọn chạy lượt này trong chat ("Chạy seed 2").
Quy tắc đọc do agent đề xuất theo đúng H3 gốc.

## Câu hỏi

H3 ([đăng ký trước](../../docs/trace_source_prereg.md), [kết quả](../trace_source_20261117/RESULTS.md)) cho thấy
`self` ra `follows` nhiều hơn `human` (18 / 6 lệch, p = 0,023), nhưng chỉ với seed 0. Đổi seed thì kết quả còn không?

## Thiết kế

Giữ mọi thứ như lượt gốc, chỉ đổi seed huấn luyện từ 0 sang **1**.

- Dữ liệu: dùng nguyên hai tập của lượt gốc, không sinh lại. Hai tập nằm ở `audit/trace_source_20261117/data/{self,human}`.
  sha256 của `train.jsonl` là `fc300891…` với `self` và `3723d40b…` với `human`, và `run.sh` kiểm tra lại cả hai.
- Huấn luyện: `structured_llm/train.sh`, 200 vòng, `--max-seq-length` 512, seed 1. Seed đổi cả khởi tạo LoRA lẫn thứ tự
  câu khi học. Adapter lưu ở `adapters/trace_self_200_s1` và `adapters/trace_human_200_s1`.
- Chấm: 500 câu GSM-Plus (`data/gsm_plus_v1/test.jsonl`, sha256 `e7ba7125…`), chế độ `tuned`, `--max-tokens 1024`, rồi
  `run_standard_interventions`. Cùng quy trình với lượt gốc.
- Phân tích: `audit/trace_source_20261117/analyze.py` chạy trên thư mục này, không sửa gì.

## Quy tắc đọc

- **Chỉ số:** `follows` khớp chính xác, trên các câu mà cả hai adapter seed 1 đều có kế hoạch can thiệp.
- **Kiểm định:** McNemar chính xác, hai phía, α = 0,05. Chỉ một kiểm định.
- **Cách đọc:**
  - `self` hơn và p < 0,05: **H3 lặp lại được ở seed 1**.
  - `human` hơn và p < 0,05: **ngược chiều ở seed 1**. Khi đó nguồn vết không cho một chiều ổn định qua các seed.
  - p ≥ 0,05: **không lặp lại được ở cỡ mẫu này**. Không được đọc là "H3 sai". Lượt gốc có chênh +8,6 điểm (CI +1,9
    đến +15,3), nên một lượt có cùng cỡ mẫu có thể trượt ngưỡng dù hiệu ứng là thật.
- Không gộp hai seed để tính p. Nếu báo số gộp thì chỉ để mô tả.

## Hạn chế đã biết trước

- Hai seed vẫn là ít. Lượt này cho biết H3 có sống qua một lần đổi seed không, chứ không đo được độ biến thiên do seed.
- Dữ liệu huấn luyện giữ nguyên, nên lượt này không kiểm tra ảnh hưởng của việc chọn câu theo mô hình gốc.

## Thời gian ước tính

Lấy từ lượt gốc: huấn luyện khoảng 19 phút mỗi adapter, chấm khoảng 3,5 giờ mỗi adapter, can thiệp khoảng 40–50 phút
mỗi adapter. Tổng cộng khoảng **9 giờ**.
