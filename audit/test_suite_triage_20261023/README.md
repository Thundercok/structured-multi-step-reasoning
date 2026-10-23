# Rà soát ban đầu bộ test RAT–CoT — 2026-10-23

Phạm vi: checkout hiện tại, có thay đổi chưa commit từ các công việc khác.
Đây là triage, chưa phải audit toàn diện hay kết quả đo chất lượng mô hình.
Không sửa mã sản phẩm, test, CI hoặc các thay đổi đang có trong lần rà soát này.

## Kết quả chạy

- `python -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q`: **29 passed in 9.33s**. Log: `core.log`.
- `python -m pytest --collect-only -q`: tiến trình abort khi import Qt trong `tests/test_assistant_worker.py:5`; chưa có tổng số test được collection thành công. Log: `collection.log`.
- Import riêng `PyQt6.QtCore` cũng abort với `Incompatible processor. This Qt build requires the following features: neon`. Log: `qt_import.log`. Không quy lỗi này cho logic RAT hay kết luận suite có bao nhiêu test thất bại.
- Collection nhóm online reasoning, research scoring, execution flow cũng abort. Log: `selected_collection.log`.
- Kiểm kê AST các file `tests/test*.py` và `test*.py` ở root: 154 file, 1.473 hàm tên `test_*` (chưa nhân parametrization, không phải số test pytest thu thập).
- 51/154 file có chuỗi `PyQt6`; đây là kiểm kê văn bản, không chứng minh dependency closure. Không coi mọi file còn lại là headless.
- Python hiện tại là `/Users/thundercock2/.local/bin/python`; `.venv/pyvenv.cfg` dùng Python 3.12.6 và `include-system-site-packages = true`. CI khai báo Python 3.10. Chưa chạy ma trận môi trường để khẳng định tương đương.

## Phát hiện và thứ tự xử lý

### 1. CI còn nhắm vào thành phần đã gỡ — xác nhận từ source

`.github/workflows/ci.yml:22` vẫn có job cài `rep_watch_bot/[dev]`, lint và test `rep_watch_bot/` ở dòng 36, 40, 44. Thành phần này đã gỡ theo quyết định dự án. Job research còn lại chỉ gọi ba file của nhóm 29 test nêu trên; không có job kiểm tra đường runtime RAT trong workflow này.

Xử lý: bỏ job lỗi thời; bổ sung nhóm runtime headless đã xác minh dependencies và nhóm Qt riêng. Chưa chạy GitHub Actions trong lần này, chưa kết luận trạng thái remote.

### 2. Collection phụ thuộc native environment — đã tái hiện

`pytest.ini` hiện chỉ cấu hình loại thư mục và pythonpath. Lệnh mặc định thu cả GUI và research. Qt abort ngay lúc import nên chọn `-k`/marker sau collection không đủ để tránh crash nếu các module Qt vẫn được import.

Xử lý đầu tiên: tạo danh sách lệnh chạy rõ ràng cho research headless, RAT runtime headless và Qt; nhóm headless phải tránh import module GUI ngay từ discovery. Kiểm tra Qt bằng subprocess trước khi chạy nhóm Qt; giữ trạng thái không chạy được là lỗi môi trường rõ ràng, không biến thành PASS hoặc âm thầm skip.

### 3. Mock MLX làm thay đổi trạng thái chung ngay khi collection — xác nhận từ source

`test_qwen_mlx_backend_mocked.py:79-82` gán giả `mlx_lm` và `mlx_lm.sample_utils` vào `sys.modules` ở cấp module rồi import backend. Không có fixture phục hồi cho các gán đó. Khi collection nhiều file, module khác có thể nhận dependency giả; nếu backend đã được import trước đó, việc thay `sys.modules` cũng không thay các tên hàm backend đã bind.

Đây là nguy cơ phụ thuộc thứ tự import; chưa tái hiện một cặp test cho kết quả khác nhau trong môi trường hiện tại.

Xử lý: cô lập mock và backend import bằng fixture có teardown hoặc subprocess; xác minh chạy riêng và chạy chung cho cùng kết quả. Không chỉ phục hồi `mlx_lm` mà bỏ quên backend đã cache.

### 4. Tên test mạnh hơn điều nó thực sự chứng minh — ví dụ cụ thể

`tests/test_native_acceptance_readiness.py:82-101` đặt tên `test_case_1_token_streaming`, nhưng kết nối `step_completed`, đợi worker hoàn tất rồi kiểm tra strategy COT. Backend double ghép toàn bộ câu trả về. Test này chứng minh step progress và kết quả worker trong ca synthetic; chưa chứng minh token streaming hay hiển thị token trước khi inference kết thúc. Docstring tại dòng 83 đã mô tả step progress chính xác hơn tên test.

Xử lý: đổi tên cho đúng hợp đồng hiện tại. Nếu sản phẩm yêu cầu token streaming thì cần ca quan sát token đến trước khi backend hoàn tất, có cancellation và callback trễ. Mock/double vẫn hữu ích cho hợp đồng, không là bằng chứng chất lượng model hoặc nghiệm thu native đầy đủ.

### 5. Vòng đời Qt application chưa thống nhất — cần kiểm tra tiếp

`tests/test_cot_ui.py:16-19` và `tests/test_claude_widget.py:13` tạo QApplication khi import. `tests/test_quick_pdf.py:26` có thể tạo QGuiApplication, trong khi các test khác yêu cầu QApplication (widget). Các test worker còn tạo QCoreApplication. Đây là trạng thái singleton dùng chung và có nguy cơ phụ thuộc thứ tự. Chưa tái hiện lỗi trộn các lớp application vì native import đang abort.

Xử lý sau khi Qt chạy được: thống nhất fixture sống đủ lâu cho nhóm GUI; kiểm tra chạy riêng/chung, teardown worker và timer. Không đưa Qt vào harness nghiên cứu.

## Điểm bắt đầu đề xuất

1. Làm cho lệnh chạy và môi trường có thể tin được: CI cũ, discovery headless/Qt và kiểm tra môi trường.
2. Loại trạng thái mock/application rò rỉ giữa các test.
3. Rà assertion theo hành vi người dùng: submit → runtime → execution/verification → kết quả hoặc lỗi; kiểm tra hủy, timeout, callback trễ. Mỗi ca phải ghi rõ dependency thật và double.
4. Sau đó mới đánh giá chỗ thiếu hoặc trùng test. Không thêm test chỉ để tăng số lượng hoặc sửa assertion cho xanh.

29 test xanh chỉ là baseline phần mềm cho nhóm đã chạy. Stage 0, reviewed data, train/calibration/test separation và yêu cầu artifact nghiên cứu không thay đổi.
