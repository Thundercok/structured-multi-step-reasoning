# Phân tích lỗi của mô hình gốc, 2026-11-02

Đọc lại đầu ra thô của Qwen3-8B ở `runs/gsm8k-qwen3-8b-staged-pilot-reviewed93-20261031/`
(93 câu GSM8K train đã dùng để phát triển, mỗi chiến lược một lần). Không gọi mô hình mới.
Đây là tư liệu định hướng trên dữ liệu đã lộ, không phải kết quả để công bố.

Chạy lại: `.venv/bin/python audit/base_error_anatomy_20261102/error_anatomy.py`. Kết quả ở `output.txt`.

- CoT đúng 81/93, DIRECT 85/93, PAL 90/93. Hai câu PAL sai là lỗi số thực (`11.000000000000002`,
  `107.99999999999983`), nên PAL thực chất sai 1 câu.
- Prompt CoT cũ yêu cầu "Write concise steps in plain English" và tắt thinking. 34/93 đầu ra chỉ
  có kế hoạch, không có phép tính: đúng 23/34. Có viết phép tính: đúng 58/59. Mô hình tự chọn có
  viết hay không, nên đây là tương quan, chưa phải nhân quả.
- Prompt DIRECT yêu cầu không viết các bước, nhưng mẫu đã xem vẫn viết phép tính. Nhãn DIRECT và
  CoT trong các báo cáo cũ vì vậy không khớp hành vi thật.
- Trong 12 câu CoT sai, 11 câu không viết phép tính nào. Chỉ `gsm8k-dev-06412` tính ra đàng hoàng
  mà vẫn sai vì hiểu sai đề, và PAL cũng sai câu đó. Phân loại này do agent đọc, chưa có người rà.
- Phát hiện câu sai: logprob AUROC 0,70 (câu sai vẫn có confidence 0,94 đến 0,98). CoT khác PAL bắt
  11/12 câu sai, báo nhầm 0/81, nhưng tốn gấp đôi token.
