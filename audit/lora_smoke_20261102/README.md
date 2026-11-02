# LoRA smoke test, 2026-11-02

Đo tốc độ và bộ nhớ trên MacBook M1 16 GB bằng dữ liệu tổng hợp (`make_data.py`).
Không phải bằng chứng về chất lượng mô hình; loss giảm chỉ vì dữ liệu lặp một mẫu.
Không có câu GSM8K nào được dùng. Adapter đã bỏ, không lưu vào repo.

- `run_log.txt`: lần đầu. Qwen3-8B lỗi Metal ở bước đầu; Qwen3.5-4B đạt, nhưng tốn 72 phút vì máy đang bận.
- `retry_log.txt`: Qwen3-8B với lô 1 và `MLX_MAX_OPS_PER_BUFFER=10`; kiểm tra adapter 4B sinh chữ được.
